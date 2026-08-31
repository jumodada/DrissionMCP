"""Browser and tab context for DrissionPage MCP."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

from .compat import create_browser, get_latest_tab, new_tab, quit_browser
from .limits import MAX_WAIT_SECONDS
from .runtime import (
    DEFAULT_ARTIFACT_LIMIT,
    DEFAULT_OPERATION_LIMIT,
    OperationClaim,
    OperationInFlightError,
    OperationKeyConflictError,
    TaskLedgerFullError,
    TaskRuntime,
)
from .tab import PageTab, TabClosedError, TabNotFoundError

logger = logging.getLogger(__name__)


class DrissionPageContext(TaskRuntime):
    """Manage DrissionPage browser/tabs and expose the private task runtime."""

    def __init__(
        self,
        *,
        operation_limit: int = DEFAULT_OPERATION_LIMIT,
        artifact_limit: int = DEFAULT_ARTIFACT_LIMIT,
    ) -> None:
        super().__init__(
            operation_limit=operation_limit,
            artifact_limit=artifact_limit,
        )
        self._browser: Any | None = None
        self._current_tab: PageTab | None = None
        self._tabs: list[PageTab] = []
        self._owned_browser_context_ids: set[str] = set()
        self._next_tab_index = 0
        self._is_initialized = False
        self._browser_closing = False
        self._browser_close_task: asyncio.Task[bool] | None = None
        # Browser lifecycle operations (initialize/sync/create/switch/close)
        # share this short-held lock.  Tab actions never hold it while doing
        # browser work, which permits independent tabs to progress in parallel.
        self._lifecycle_lock = asyncio.Lock()
        self._bound_tab: ContextVar[PageTab | None] = ContextVar(
            f"drissionpage_mcp_bound_tab_{id(self)}", default=None
        )

    async def initialize(self) -> None:
        """Initialize the browser context."""
        async with self._lifecycle_lock:
            await self._initialize_unlocked()

    async def ensure_initialized(self) -> None:
        """Ensure the context is initialized."""
        await self.initialize()

    def current_tab(self) -> PageTab | None:
        """Get the current active tab."""
        return self._current_tab

    def current_tab_or_die(self) -> PageTab:
        """Get the call-bound tab or current tab for legacy direct callers."""
        bound = self._bound_tab.get()
        tab = bound or self._current_tab
        if not tab:
            raise RuntimeError("No active tab. Use navigate tool to open a page first.")
        if bound is not None:
            # A bound call claimed the tab before close began. Close waits for
            # that claim, so the handler must be allowed to finish normally.
            return bound
        if getattr(tab, "is_closed", False) or getattr(tab, "is_closing", False):
            raise TabClosedError("The requested browser tab is closed or closing.")
        return tab

    def bound_tab(self) -> PageTab | None:
        """Return the tab captured for the current async tool call, if any."""

        return self._bound_tab.get()

    def bound_tab_id(self) -> str | None:
        """Return the MCP id captured for the current async tool call."""

        tab = self._bound_tab.get()
        return tab.mcp_tab_id if tab is not None else None

    @asynccontextmanager
    async def bind_tab(self, tab_id: str | None = None) -> AsyncIterator[PageTab]:
        """Resolve and bind one tab for the duration of a tool invocation."""

        tab = await self.resolve_tab(tab_id)
        token = self._bound_tab.set(tab)
        try:
            yield tab
        finally:
            self._bound_tab.reset(token)

    @asynccontextmanager
    async def tab_action(
        self,
        tab_id: str | None = None,
        *,
        serialized: bool = True,
    ) -> AsyncIterator[PageTab]:
        """Resolve, bind, and claim one tab-scoped action."""

        async with self.bind_tab(tab_id) as tab:
            action = getattr(tab, "action", None)
            if callable(action):
                async with action(serialized=serialized):
                    yield tab
            else:
                # Supports narrow test doubles and older embedded callers. Real
                # PageTab instances always own the per-tab lifecycle primitive.
                yield tab

    async def resolve_tab(self, tab_id: str | None = None) -> PageTab:
        """Capture a stable target before a handler performs browser I/O.

        ``tab_id=None`` reads ``_current_tab`` exactly once while holding the
        lifecycle lock.  The returned object is then bound to the caller's
        context, so later active-tab switches cannot redirect the operation.
        """

        async with self._lifecycle_lock:
            if self._browser_closing:
                raise TabClosedError("The browser context is closing.")
            if not self._is_initialized or self._browser is None:
                current = self._current_tab
                if current is not None and (
                    tab_id is None
                    or tab_id
                    in {
                        getattr(current, "mcp_tab_id", ""),
                        getattr(current, "native_tab_id", ""),
                    }
                ):
                    return current
                if current is not None and tab_id is not None:
                    raise TabNotFoundError(f"Tab not found: {tab_id}")
                raise RuntimeError(
                    "No active tab. Use navigate tool to open a page first."
                )
            self._sync_tabs_unlocked()
            tab = self._find_tab(tab_id) if tab_id else self._current_tab
            if tab_id is not None and tab is None:
                raise TabNotFoundError(f"Tab not found: {tab_id}")
            if tab is None and self._tabs:
                tab = self._tabs[0]
            if tab is None:
                raise RuntimeError("No active tab. Use navigate tool to open a page first.")
            if getattr(tab, "is_closed", False) or getattr(tab, "is_closing", False):
                raise TabClosedError("The requested browser tab is closed or closing.")
            return tab

    def tabs(self) -> list[PageTab]:
        """Get all tabs."""
        return self._tabs.copy()

    async def sync_tabs(self) -> list[PageTab]:
        """Synchronize tracked tabs with the underlying browser tab registry."""
        async with self._lifecycle_lock:
            await self._initialize_unlocked()
            self._sync_tabs_unlocked()
            return self.tabs()

    def tab_summaries(self) -> list[dict[str, Any]]:
        """Return public summaries for currently tracked tabs."""

        current = self._current_tab
        return [tab.summary(active=tab is current) for tab in self._tabs]

    async def switch_tab(self, tab_id: str) -> PageTab:
        """Switch the active tab by MCP id or native DrissionPage id."""
        await self.sync_tabs()
        async with self._lifecycle_lock:
            tab = self._find_tab(tab_id)
            if tab is None:
                raise TabNotFoundError(f"Tab not found: {tab_id}")
            if getattr(tab, "is_closed", False) or getattr(tab, "is_closing", False):
                raise TabClosedError("The requested browser tab is closed or closing.")

            if self._browser and hasattr(self._browser, "activate_tab"):
                try:
                    self._browser.activate_tab(tab.native_tab_id or tab.page)
                except Exception:
                    logger.debug("Browser activate_tab failed")
            self._current_tab = tab
            return tab

    async def close_tab_by_id(self, tab_id: str) -> None:
        """Close a tab by MCP id or native DrissionPage id."""
        await self.sync_tabs()
        async with self._lifecycle_lock:
            tab = self._find_tab(tab_id)
            if tab is None:
                raise TabNotFoundError(f"Tab not found: {tab_id}")
        await self._close_tracked_tab(tab)
        if self._browser:
            try:
                await self.sync_tabs()
            except Exception:
                logger.debug("Post-close tab sync failed")

    async def ensure_tab(self) -> PageTab:
        """Ensure there is an active tab, creating one if necessary."""
        async with self._lifecycle_lock:
            await self._initialize_unlocked()
            if not self._current_tab and self._browser:
                tab = self._wrap_page(new_tab(self._browser))
                self._tabs.append(tab)
                self._current_tab = tab

            if self._current_tab is None:
                raise RuntimeError("Browser context not initialized")
            if getattr(self._current_tab, "is_closed", False) or getattr(
                self._current_tab, "is_closing", False
            ):
                raise TabClosedError("The requested browser tab is closed or closing.")
            return self._current_tab

    async def new_tab(
        self,
        *,
        url: str | None = None,
        background: bool = False,
        new_window: bool = False,
        new_context: bool = False,
    ) -> PageTab:
        """Create a tab with explicit foreground/background/window semantics.

        DrissionPage's ``background`` and ``new_window`` flags are forwarded when
        supported.  A background tab is tracked but does not become the MCP
        current tab; foreground creation does.  ``new_context`` creates a
        disposable browser context and is used by HTTP-auth navigation.
        """

        async with self._lifecycle_lock:
            await self._initialize_unlocked()
            if not self._browser:
                raise RuntimeError("Browser context not initialized")

            if any((url is not None, background, new_window, new_context)):
                page = new_tab(
                    self._browser,
                    url=url,
                    background=background,
                    new_window=new_window,
                    new_context=new_context,
                )
            else:
                page = new_tab(self._browser)
            browser_context_id = self._browser_context_id(page)
            if new_context:
                if not browser_context_id:
                    try:
                        self._browser.close_tabs(getattr(page, "tab_id", page))
                    except Exception:
                        pass
                    raise RuntimeError(
                        "DrissionPage created a tab without a disposable browser context."
                    )
                self._owned_browser_context_ids.add(browser_context_id)
            tab = self._wrap_page(
                page,
                browser_context_id=browser_context_id,
                owns_browser_context=new_context,
            )
            self._tabs.append(tab)
            if not background:
                self._current_tab = tab
            return tab

    async def new_isolated_tab(self) -> PageTab:
        """Create and own one tab in a dedicated Chromium browser context."""
        return await self.new_tab(new_context=True)

    async def navigate_with_http_auth(
        self,
        *,
        url: str,
        username: str,
        password: str,
        realm: str | None,
        timeout: float,
    ) -> dict[str, Any]:
        """Navigate with Fetch auth inside a disposable isolated context."""

        tab = await self.new_isolated_tab()
        try:
            return await tab.http_auth.navigate(
                url=url,
                username=username,
                password=password,
                realm=realm,
                timeout=timeout,
            )
        except BaseException as auth_error:
            try:
                await self.close_tab(tab)
            except BaseException:
                await self.close_browser()
                if isinstance(auth_error, asyncio.CancelledError):
                    raise auth_error from None
                raise RuntimeError(
                    "HTTP authentication failed and isolated context cleanup failed; "
                    "browser state was closed."
                ) from auth_error
            raise

    async def close_tab(self, tab: PageTab | None = None) -> None:
        """Close a tab."""
        target_tab = tab or self._current_tab
        if not target_tab:
            return
        await self._close_tracked_tab(target_tab)

    async def close_browser(self) -> bool:
        """Close the browser context."""
        async with self._lifecycle_lock:
            task = self._browser_close_task
            if task is None:
                self._browser_closing = True
                tabs = list(self._tabs)
                for tab in tabs:
                    mark_closing = getattr(tab, "mark_closing", None)
                    if callable(mark_closing):
                        await mark_closing()
                task = asyncio.create_task(self._finish_browser_close(tabs))
                self._browser_close_task = task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # Browser shutdown is not cancellable once native state is marked
            # closing. Finish cleanup before propagating caller cancellation.
            await asyncio.shield(task)
            raise

    async def cleanup(self) -> None:
        """Clean up all resources."""
        await self.close_browser()

    async def wait(self, seconds: float) -> None:
        """Wait for a specified number of seconds."""
        if seconds < 0 or seconds > MAX_WAIT_SECONDS:
            raise ValueError(
                f"Wait seconds must be between 0 and {MAX_WAIT_SECONDS}; got {seconds}"
            )
        await asyncio.sleep(seconds)

    def is_active(self) -> bool:
        """Check if the context is active."""
        return self._is_initialized and self._browser is not None

    @property
    def browser(self) -> Any | None:
        """Return the underlying DrissionPage browser object."""
        return self._browser

    async def _initialize_unlocked(self) -> None:
        """Initialize while the lifecycle lock is already held."""

        if self._browser_closing:
            raise TabClosedError("The browser context is closing.")
        if self._is_initialized:
            return
        try:
            self._browser = create_browser()
            tab = self._wrap_page(get_latest_tab(self._browser))
            self._tabs.append(tab)
            self._current_tab = tab
            self._is_initialized = True
            logger.info("DrissionPage context initialized")
        except Exception as exc:
            logger.error(
                "Failed to initialize DrissionPage context (%s)",
                type(exc).__name__,
            )
            raise

    async def _close_tracked_tab(self, target_tab: PageTab) -> None:
        """Drain and close one tab or its whole owned browser context."""

        async with self._lifecycle_lock:
            targets = self._tab_close_scope(target_tab)
            for tab in targets:
                mark_closing = getattr(tab, "mark_closing", None)
                if callable(mark_closing):
                    await mark_closing()
        await asyncio.gather(
            *(
                tab.wait_for_idle()
                for tab in targets
                if callable(getattr(tab, "wait_for_idle", None))
            )
        )
        close_result = await target_tab.close()
        if close_result is False:
            async with self._lifecycle_lock:
                for tab in targets:
                    mark_closed = getattr(tab, "_mark_closed", None)
                    if callable(mark_closed):
                        await mark_closed(False)
            raise RuntimeError(f"Failed to close tab: {target_tab.mcp_tab_id}")
        async with self._lifecycle_lock:
            for tab in targets:
                mark_closed = getattr(tab, "_mark_closed", None)
                if callable(mark_closed):
                    await mark_closed(True)
            self._remove_closed_tab(target_tab)

    def _tab_close_scope(self, target_tab: PageTab) -> list[PageTab]:
        """Return every tab invalidated by closing the target's native scope."""

        browser_context_id = getattr(target_tab, "browser_context_id", "")
        if getattr(target_tab, "owns_browser_context", False) and browser_context_id:
            targets = [
                tab
                for tab in self._tabs
                if getattr(tab, "browser_context_id", "") == browser_context_id
            ]
            if targets:
                return targets
        return [target_tab]

    async def _finish_browser_close(self, tabs: list[PageTab]) -> bool:
        """Drain the captured browser state and complete non-cancellable cleanup."""

        try:
            await asyncio.gather(
                *(
                    tab.wait_for_idle()
                    for tab in tabs
                    if callable(getattr(tab, "wait_for_idle", None))
                )
            )
        except BaseException:
            async with self._lifecycle_lock:
                self._browser_closing = False
                self._browser_close_task = None
            raise

        async with self._lifecycle_lock:
            try:
                closed = True
                if self._browser:
                    try:
                        quit_browser(self._browser)
                    except Exception as exc:
                        logger.warning(
                            "Error closing browser (%s)", type(exc).__name__
                        )
                        closed = False
                    finally:
                        self._browser = None

                for tab in tabs:
                    mark_closed = getattr(tab, "_mark_closed", None)
                    if callable(mark_closed):
                        await mark_closed(True)
                self._tabs.clear()
                self._owned_browser_context_ids.clear()
                self._current_tab = None
                self._is_initialized = False
                logger.info("Browser context closed")
                return closed
            finally:
                self._browser_closing = False
                self._browser_close_task = None

    def _sync_tabs_unlocked(self) -> list[PageTab]:
        """Synchronize tabs while the lifecycle lock is already held."""

        if not self._browser:
            return []

        pages = self._browser_tabs()
        if not pages:
            try:
                pages = [get_latest_tab(self._browser)]
            except Exception:
                pages = []

        existing = {self._tab_key(tab.page): tab for tab in self._tabs}
        previous_current = self._current_tab
        previous_key = self._tab_key(previous_current.page) if previous_current else ""
        synced: list[PageTab] = []
        seen: set[str] = set()
        for page in pages:
            if page is None:
                continue
            key = self._tab_key(page)
            if key in seen:
                continue
            seen.add(key)
            tab = existing.get(key)
            if tab is None:
                tab = self._wrap_page(page)
            elif tab.in_flight_actions == 0 and not tab.is_closing:
                # Never replace a page object while an action may still be
                # executing against the previously captured object.
                tab.page = page
            if tab.is_connected() or tab.in_flight_actions:
                synced.append(tab)

        # Preserve a tracked tab that temporarily disappears from Chromium's
        # registry while an action is in flight. Retire it on a later sync.
        for tab in self._tabs:
            if (
                tab in synced
                or getattr(tab, "is_closed", False)
                or getattr(tab, "is_closing", False)
            ):
                continue
            if tab.in_flight_actions:
                synced.append(tab)

        self._tabs = synced
        current = self._find_tab_by_key(previous_key) if previous_key else None
        if current is not None:
            self._current_tab = current
        elif previous_current is None:
            # Initial discovery follows the native active/latest tab. Once MCP
            # has selected a current tab, later syncs preserve that selection.
            latest_key = ""
            try:
                latest_key = self._tab_key(get_latest_tab(self._browser))
            except Exception:
                pass
            self._current_tab = self._find_tab_by_key(latest_key)
            if self._current_tab is None:
                self._current_tab = self._tabs[0] if self._tabs else None
        elif self._current_tab not in self._tabs:
            self._current_tab = self._tabs[0] if self._tabs else None
        return self.tabs()

    def _remove_closed_tab(self, target_tab: PageTab) -> None:
        """Remove one successfully closed tab while lifecycle is locked."""

        browser_context_id = getattr(target_tab, "browser_context_id", "")
        if getattr(target_tab, "owns_browser_context", False) and browser_context_id:
            self._owned_browser_context_ids.discard(browser_context_id)
            self._tabs = [
                item
                for item in self._tabs
                if getattr(item, "browser_context_id", "") != browser_context_id
            ]
        elif target_tab in self._tabs:
            self._tabs.remove(target_tab)
        if self._current_tab == target_tab:
            self._current_tab = self._tabs[0] if self._tabs else None

    def _wrap_page(
        self,
        page: Any,
        *,
        browser_context_id: str = "",
        owns_browser_context: bool | None = None,
    ) -> PageTab:
        context_id = browser_context_id or self._browser_context_id(page)
        owns_context = (
            context_id in self._owned_browser_context_ids
            if owns_browser_context is None
            else owns_browser_context
        )
        tab = PageTab(
            page,
            self,
            mcp_tab_id=f"t{self._next_tab_index}",
            browser_context_id=context_id,
            owns_browser_context=owns_context,
        )
        self._next_tab_index += 1
        tab.observation.ensure_console_capture()
        return tab

    def _browser_context_id(self, page: Any) -> str:
        browser = self._browser
        run_cdp = getattr(browser, "_run_cdp", None)
        tab_id = getattr(page, "tab_id", "")
        if not callable(run_cdp) or not tab_id:
            return ""
        try:
            valid_contexts = set(
                run_cdp("Target.getBrowserContexts").get("browserContextIds", [])
            )
            target_info = run_cdp(
                "Target.getTargetInfo", targetId=tab_id
            ).get("targetInfo", {})
        except Exception:
            return ""
        context_id = str(target_info.get("browserContextId", ""))
        return context_id if context_id in valid_contexts else ""

    def _dispose_browser_context(self, browser_context_id: str) -> None:
        browser = self._browser
        run_cdp = getattr(browser, "_run_cdp", None)
        if not callable(run_cdp):
            raise RuntimeError("Browser context disposal is unavailable.")
        run_cdp(
            "Target.disposeBrowserContext", browserContextId=browser_context_id
        )
        self._owned_browser_context_ids.discard(browser_context_id)

    def _browser_tabs(self) -> list[Any]:
        browser = self._browser
        if browser is None:
            return []

        pages: list[Any] = []
        get_tabs = getattr(browser, "get_tabs", None)
        if callable(get_tabs):
            try:
                pages.extend(_normalize_browser_tab_list(browser, get_tabs()))
            except Exception:
                logger.debug("browser.get_tabs() failed")

        if not pages:
            tab_ids = getattr(browser, "tab_ids", None)
            if callable(tab_ids):
                try:
                    tab_ids = tab_ids()
                except Exception:
                    tab_ids = None
            if tab_ids:
                for tab_id in list(tab_ids):
                    try:
                        pages.append(browser.get_tab(tab_id))
                    except Exception:
                        logger.debug("browser.get_tab() failed")

        latest = get_latest_tab(browser)
        latest_key = self._tab_key(latest)
        if latest_key and all(self._tab_key(page) != latest_key for page in pages):
            pages.append(latest)
        return pages

    def _find_tab(self, tab_id: str) -> PageTab | None:
        return next(
            (
                tab
                for tab in self._tabs
                if tab.mcp_tab_id == tab_id or tab.native_tab_id == tab_id
            ),
            None,
        )

    def _find_tab_by_key(self, key: str) -> PageTab | None:
        return next((tab for tab in self._tabs if self._tab_key(tab.page) == key), None)

    @staticmethod
    def _tab_key(page: Any) -> str:
        try:
            native_id = getattr(page, "tab_id", "")
        except Exception:
            native_id = ""
        return str(native_id or id(page))


def _normalize_browser_tab_list(browser: Any, value: Any) -> list[Any]:
    if value is None:
        return []
    pages = []
    for item in list(value):
        if isinstance(item, str) and hasattr(browser, "get_tab"):
            pages.append(browser.get_tab(item))
        else:
            pages.append(item)
    return pages


__all__ = [
    "DrissionPageContext",
    "OperationClaim",
    "OperationInFlightError",
    "OperationKeyConflictError",
    "TaskLedgerFullError",
    "TabClosedError",
    "TabNotFoundError",
]
