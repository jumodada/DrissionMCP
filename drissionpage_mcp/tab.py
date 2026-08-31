"""Tab management for DrissionPage MCP."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from DrissionPage.errors import ElementNotFoundError

from .browser import (
    AccessibilityOperations,
    DialogOperations,
    DomTargetResolver,
    DownloadOperations,
    ElementOperations,
    FileChooserOperations,
    FrameOperations,
    HttpAuthOperations,
    InteractionOperations,
    NavigationOperations,
    NetworkOperations,
    ObservationOperations,
    PageArtifactOperations,
    PageOperations,
    PermissionOperations,
    PointerOperations,
    StorageOperations,
    TargetResolver,
    WaitOperations,
)
from .selector import SelectorPlan

if TYPE_CHECKING:
    from .context import DrissionPageContext

logger = logging.getLogger(__name__)


class TabClosedError(RuntimeError):
    """Raised when an action targets a tab that is closed or closing."""

    code = "TAB_CLOSED"


class TabNotFoundError(ValueError):
    """Raised when an MCP/native tab id cannot be resolved."""

    code = "TAB_NOT_FOUND"


class PageTab:
    """Wrapper around a DrissionPage Chromium tab/page object."""

    def __init__(
        self,
        page: Any,
        context: "DrissionPageContext",
        *,
        mcp_tab_id: str = "",
        browser_context_id: str = "",
        owns_browser_context: bool = False,
    ):
        # Keep the historical ``page`` attribute name while allowing it to hold
        # DrissionPage 4.2 ChromiumTab objects.
        self.page = page
        self.context = context
        self.mcp_tab_id = mcp_tab_id
        self.browser_context_id = browser_context_id
        self.owns_browser_context = owns_browser_context
        self._url = ""
        # Serialize actions per tab instead of holding one process-wide lane.
        # The condition also counts callers queued on the action lock so close
        # can reject new work and drain all existing claims deterministically.
        self.action_lock = asyncio.Lock()
        self._lifecycle_condition = asyncio.Condition()
        self._close_lock = asyncio.Lock()
        self._in_flight_actions = 0
        self._closing = False
        self._closed = False
        self.dom_targeting = DomTargetResolver(self)
        self.accessibility = AccessibilityOperations(self)
        self.artifacts = PageArtifactOperations(self)
        self.dialogs = DialogOperations(self)
        self.downloads = DownloadOperations(self)
        self.elements = ElementOperations(self)
        self.file_chooser = FileChooserOperations(self)
        self.frames = FrameOperations(self)
        self.interaction = InteractionOperations(self)
        self.navigation = NavigationOperations(self)
        self.network = NetworkOperations(self)
        self.observation = ObservationOperations(self)
        self.page_ops = PageOperations(self)
        self.permissions = PermissionOperations(self)
        self.pointer = PointerOperations(self)
        self.storage = StorageOperations(self)
        self.targeting = TargetResolver(self)
        self.waits = WaitOperations(self)
        self.http_auth = HttpAuthOperations(self)

    @property
    def native_tab_id(self) -> str:
        """Return the underlying DrissionPage tab id when available."""

        try:
            value = getattr(self.page, "tab_id", "")
        except Exception:
            value = ""
        return "" if value is None else str(value)

    @property
    def url(self) -> str:
        """Get the current URL of the tab."""
        try:
            return self.page.url or self._url
        except Exception:
            return self._url

    @property
    def title(self) -> str:
        """Get the current page title for tab summaries."""

        try:
            value = getattr(self.page, "title", "")
        except Exception:
            value = ""
        return "" if value is None else str(value)

    def summary(self, *, active: bool = False) -> dict[str, Any]:
        """Return a bounded public tab summary."""

        return {
            "id": self.mcp_tab_id,
            "native_id": self.native_tab_id,
            "url": self.url,
            "title": self.title,
            "active": active,
            "connected": self.is_connected(),
            "isolated_context": self.owns_browser_context,
        }

    @property
    def in_flight_actions(self) -> int:
        """Return the number of actions that have claimed this tab."""

        return self._in_flight_actions

    @property
    def is_closing(self) -> bool:
        """Whether the tab has begun lifecycle shutdown."""

        return self._closing

    @property
    def is_closed(self) -> bool:
        """Whether the native close operation completed."""

        return self._closed

    @asynccontextmanager
    async def action(self, *, serialized: bool = True) -> AsyncIterator["PageTab"]:
        """Claim one tab action and release it on success, failure, or cancel.

        ``serialized=False`` is reserved for lifetimes that must overlap a
        browser action (currently native dialog observation/response). Those
        calls still count as in-flight so tab close waits for them.
        """

        async with self._lifecycle_condition:
            if self._closing or self._closed:
                raise TabClosedError("The requested browser tab is closed or closing.")
            self._in_flight_actions += 1

        acquired = False
        try:
            if serialized:
                await self.action_lock.acquire()
                acquired = True
                async with self._lifecycle_condition:
                    if self._closing or self._closed:
                        raise TabClosedError(
                            "The requested browser tab is closed or closing."
                        )
            yield self
        finally:
            if acquired:
                self.action_lock.release()
            async with self._lifecycle_condition:
                self._in_flight_actions -= 1
                self._lifecycle_condition.notify_all()

    async def mark_closing(self) -> None:
        """Reject new actions while allowing already claimed work to drain."""

        async with self._lifecycle_condition:
            if not self._closed:
                self._closing = True
                self._lifecycle_condition.notify_all()

    async def wait_for_idle(self) -> None:
        """Wait until no action (including queued action claims) remains."""

        async with self._lifecycle_condition:
            while self._in_flight_actions:
                await self._lifecycle_condition.wait()

    async def _mark_closed(self, closed: bool) -> None:
        async with self._lifecycle_condition:
            if closed:
                self._closed = True
                self._closing = True
            else:
                self._closing = False
            self._lifecycle_condition.notify_all()

    async def _element_by_plan(self, plan: SelectorPlan, *, timeout: float = 10) -> Any:
        if timeout > 0:
            loaded = await self.waits.for_plan(plan, timeout)
            if not loaded:
                raise ElementNotFoundError(f"Element not found: {plan.original}")
        element = self.page.ele(plan.locator, timeout=0)
        if not element:
            raise ElementNotFoundError(f"Element not found: {plan.original}")
        return element

    async def _stabilize(
        self,
        action: str,
        *,
        timeout: float = 1.0,
        fallback_sleep: float = 0.02,
    ) -> None:
        """Prefer DrissionPage-native load waits with a bounded async fallback."""

        try:
            if bool(self.page.states.has_alert):
                return
        except Exception:
            pass

        wait = getattr(self.page, "wait", None)
        doc_loaded = getattr(wait, "doc_loaded", None)
        if callable(doc_loaded):
            call_shapes: tuple[dict[str, Any], ...] = (
                {"timeout": timeout, "raise_err": False},
                {"timeout": timeout},
                {},
            )
            for kwargs in call_shapes:
                try:
                    doc_loaded(**kwargs)
                    return
                except TypeError:
                    continue
                except Exception:
                    logger.debug(
                        "Post-%s stabilization via doc_loaded failed",
                        action,
                    )
                    break

        await asyncio.sleep(fallback_sleep)

    async def close(self) -> bool:
        """Close the tab."""
        async with self._close_lock:
            if self._closed:
                return True
            await self.mark_closing()
            await self.wait_for_idle()
            try:
                browser_context_id = self.browser_context_id
                if (
                    self.owns_browser_context
                    and browser_context_id
                    and hasattr(self.context, "_dispose_browser_context")
                ):
                    self.context._dispose_browser_context(browser_context_id)
                else:
                    browser = getattr(self.context, "browser", None)
                    tab_id = getattr(self.page, "tab_id", None)
                    if browser is not None and tab_id and hasattr(browser, "close_tabs"):
                        browser.close_tabs(tab_id)
                    elif hasattr(self.page, "close"):
                        self.page.close()
                await self._mark_closed(True)
                logger.info("Tab closed")
                return True
            except Exception as e:
                await self._mark_closed(False)
                logger.error("Failed to close tab (%s)", type(e).__name__)
                return False

    def is_connected(self) -> bool:
        """Check if the tab is still connected."""
        if self._closed:
            return False
        try:
            # Try to access a basic property
            _ = self.page.url
            return True
        except Exception:
            return False
