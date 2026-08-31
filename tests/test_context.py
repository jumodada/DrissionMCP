"""Context lifecycle coverage without launching a real browser."""

from __future__ import annotations

import pytest

from drissionpage_mcp.context import DrissionPageContext


class FakePage:
    def __init__(self, tab_id: str = "tab") -> None:
        self.tab_id = tab_id
        self.closed = False
        self.url = "about:blank"
        self.title = f"Title {tab_id}"

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self) -> None:
        self.closed_tabs: list[str] = []
        self.pages: dict[str, FakePage] = {}
        self.active_tab_id = ""

    def close_tabs(self, tab_id: str) -> None:
        self.closed_tabs.append(tab_id)
        self.pages.pop(tab_id, None)
        if self.active_tab_id == tab_id:
            self.active_tab_id = next(iter(self.pages), "")

    @property
    def latest_tab(self) -> FakePage | None:
        if self.active_tab_id:
            return self.pages[self.active_tab_id]
        return next(iter(self.pages.values()), None)

    @property
    def tab_ids(self) -> list[str]:
        return list(self.pages)

    def get_tab(self, tab_id: str | None = None) -> FakePage | None:
        if tab_id is None:
            return self.latest_tab
        return self.pages[tab_id]

    def get_tabs(self) -> list[FakePage]:
        return list(self.pages.values())

    def activate_tab(self, id_or_tab) -> None:
        self.active_tab_id = getattr(id_or_tab, "tab_id", id_or_tab)


class BrokenCloseBrowser(FakeBrowser):
    def close_tabs(self, tab_id: str) -> None:
        raise RuntimeError(f"cannot close {tab_id}")


class ManagedTab:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FailedManagedTab:
    async def close(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_initialize_is_idempotent_and_exposes_tab_state(monkeypatch) -> None:
    browser = FakeBrowser()
    page = FakePage("initial")
    create_calls = []

    def fake_create_browser():
        create_calls.append("create")
        return browser

    monkeypatch.setattr("drissionpage_mcp.context.create_browser", fake_create_browser)
    monkeypatch.setattr(
        "drissionpage_mcp.context.get_latest_tab", lambda _browser: page
    )

    context = DrissionPageContext()

    await context.initialize()
    await context.initialize()

    assert create_calls == ["create"]
    assert context.is_active() is True
    assert context.browser is browser
    assert context.current_tab() is context.current_tab_or_die()
    assert len(context.tabs()) == 1
    assert context.tabs() is not context.tabs()


@pytest.mark.asyncio
async def test_initialize_reraises_browser_creation_failure(monkeypatch) -> None:
    def fail_create_browser():
        raise RuntimeError("cannot launch")

    monkeypatch.setattr("drissionpage_mcp.context.create_browser", fail_create_browser)
    context = DrissionPageContext()

    with pytest.raises(RuntimeError, match="cannot launch"):
        await context.initialize()


@pytest.mark.asyncio
async def test_ensure_tab_creates_missing_current_tab_from_existing_browser(
    monkeypatch,
) -> None:
    context = DrissionPageContext()
    context._is_initialized = True
    context._browser = FakeBrowser()
    context._current_tab = None
    new_page = FakePage("new")
    monkeypatch.setattr("drissionpage_mcp.context.new_tab", lambda _browser: new_page)

    tab = await context.ensure_tab()

    assert tab.page is new_page
    assert context.current_tab() is tab
    assert context.tabs() == [tab]


@pytest.mark.asyncio
async def test_ensure_tab_and_new_tab_fail_without_browser() -> None:
    context = DrissionPageContext()
    context._is_initialized = True
    context._browser = None
    context._current_tab = None

    with pytest.raises(RuntimeError, match="Browser context not initialized"):
        await context.ensure_tab()

    with pytest.raises(RuntimeError, match="Browser context not initialized"):
        await context.new_tab()


@pytest.mark.asyncio
async def test_new_tab_tracks_new_page_and_makes_it_current(monkeypatch) -> None:
    context = DrissionPageContext()
    context._is_initialized = True
    context._browser = FakeBrowser()
    new_page = FakePage("new")
    monkeypatch.setattr("drissionpage_mcp.context.new_tab", lambda _browser: new_page)

    tab = await context.new_tab()

    assert tab.page is new_page
    assert context.current_tab() is tab
    assert context.tabs() == [tab]


@pytest.mark.asyncio
async def test_new_background_tab_is_tracked_without_changing_current(
    monkeypatch,
) -> None:
    context = DrissionPageContext()
    context._is_initialized = True
    context._browser = FakeBrowser()
    current = context._wrap_page(FakePage("current"))
    context._tabs = [current]
    context._current_tab = current
    created = FakePage("background")
    calls = []

    def fake_new_tab(_browser, **kwargs):
        calls.append(kwargs)
        return created

    monkeypatch.setattr("drissionpage_mcp.context.new_tab", fake_new_tab)

    tab = await context.new_tab(background=True, new_window=True)

    assert calls == [
        {
            "url": None,
            "background": True,
            "new_window": True,
            "new_context": False,
        }
    ]
    assert tab.native_tab_id == "background"
    assert context.current_tab() is current
    assert context.tabs() == [current, tab]


@pytest.mark.asyncio
async def test_sync_tabs_discovers_external_browser_tabs_and_switches() -> None:
    browser = FakeBrowser()
    browser.pages = {
        "a": FakePage("a"),
        "b": FakePage("b"),
    }
    browser.pages["a"].url = "https://example.test/a"
    browser.pages["b"].url = "https://example.test/b"
    browser.active_tab_id = "a"
    context = DrissionPageContext()
    context._browser = browser
    context._is_initialized = True

    tabs = await context.sync_tabs()

    assert [tab.native_tab_id for tab in tabs] == ["a", "b"]
    assert [tab.mcp_tab_id for tab in tabs] == ["t0", "t1"]
    assert context.current_tab().native_tab_id == "a"

    switched = await context.switch_tab("t1")

    assert switched.native_tab_id == "b"
    assert context.current_tab() is switched
    assert browser.active_tab_id == "b"


@pytest.mark.asyncio
async def test_close_tab_by_id_removes_tab_and_promotes_remaining() -> None:
    browser = FakeBrowser()
    browser.pages = {
        "a": FakePage("a"),
        "b": FakePage("b"),
    }
    browser.active_tab_id = "b"
    context = DrissionPageContext()
    context._browser = browser
    context._is_initialized = True
    await context.sync_tabs()

    await context.close_tab_by_id("t1")

    assert browser.closed_tabs == ["b"]
    assert [tab.native_tab_id for tab in context.tabs()] == ["a"]
    assert context.current_tab().native_tab_id == "a"


@pytest.mark.asyncio
async def test_close_tab_by_id_keeps_state_when_browser_close_fails() -> None:
    browser = BrokenCloseBrowser()
    browser.pages = {
        "a": FakePage("a"),
        "b": FakePage("b"),
    }
    browser.active_tab_id = "b"
    context = DrissionPageContext()
    context._browser = browser
    context._is_initialized = True
    await context.sync_tabs()

    with pytest.raises(RuntimeError, match="Failed to close tab"):
        await context.close_tab_by_id("t1")

    assert [tab.native_tab_id for tab in context.tabs()] == ["a", "b"]
    assert context.current_tab().native_tab_id == "b"


def test_context_does_not_retain_action_history() -> None:
    context = DrissionPageContext()
    assert not hasattr(context, "record_action")
    assert not hasattr(context, "action_history")


@pytest.mark.asyncio
async def test_close_tab_noops_without_target_and_promotes_remaining_tab() -> None:
    context = DrissionPageContext()
    await context.close_tab()

    first = ManagedTab()
    second = ManagedTab()
    context._tabs = [first, second]  # type: ignore[list-item]
    context._current_tab = second  # type: ignore[assignment]

    await context.close_tab()

    assert second.closed is True
    assert context.current_tab() is first
    assert context.tabs() == [first]


@pytest.mark.asyncio
async def test_close_browser_clears_state_even_when_quit_fails(monkeypatch) -> None:
    def fail_quit(_browser):
        raise RuntimeError("already disconnected")

    monkeypatch.setattr("drissionpage_mcp.context.quit_browser", fail_quit)
    context = DrissionPageContext()
    context._browser = FakeBrowser()
    context._current_tab = ManagedTab()  # type: ignore[assignment]
    context._tabs = [context._current_tab]
    context._is_initialized = True

    await context.close_browser()

    assert context.browser is None
    assert context.current_tab() is None
    assert context.tabs() == []
    assert context.is_active() is False


@pytest.mark.asyncio
async def test_wait_delegates_to_asyncio_sleep(monkeypatch) -> None:
    sleeps = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("drissionpage_mcp.context.asyncio.sleep", fake_sleep)
    context = DrissionPageContext()

    await context.wait(0.25)

    assert sleeps == [0.25]


class EmptyRegistryBrowser(FakeBrowser):
    def get_tabs(self) -> list[FakePage]:
        return []

    @property
    def tab_ids(self) -> list[str]:
        return []


class ExplodingActivateBrowser(FakeBrowser):
    def activate_tab(self, id_or_tab) -> None:
        raise RuntimeError("activation failed")


class TabDiscoveryFallbackBrowser(FakeBrowser):
    def get_tabs(self) -> list[FakePage]:
        raise RuntimeError("registry unavailable")

    def tab_ids(self) -> list[str]:  # type: ignore[override]
        return ["a", "missing"]


class TabIdsFailBrowser(FakeBrowser):
    def get_tabs(self) -> list[FakePage]:
        raise RuntimeError("registry unavailable")

    def tab_ids(self) -> list[str]:  # type: ignore[override]
        raise RuntimeError("ids unavailable")


class BadTabIdPage:
    @property
    def tab_id(self) -> str:
        raise RuntimeError("tab id unavailable")


class DisconnectedPage(FakePage):
    @property
    def url(self) -> str:  # type: ignore[override]
        raise RuntimeError("disconnected")

    @url.setter
    def url(self, value: str) -> None:
        self._url = value


def initialized_context(browser: FakeBrowser | None = None) -> DrissionPageContext:
    context = DrissionPageContext()
    context._is_initialized = True
    context._browser = browser if browser is not None else FakeBrowser()
    return context


def native_tab_ids(tabs) -> list[str]:
    return [tab.native_tab_id for tab in tabs]


@pytest.mark.asyncio
async def test_ensure_initialized_initializes_when_needed(monkeypatch) -> None:
    browser = FakeBrowser()
    page = FakePage("initial")
    monkeypatch.setattr("drissionpage_mcp.context.create_browser", lambda: browser)
    monkeypatch.setattr(
        "drissionpage_mcp.context.get_latest_tab", lambda _browser: page
    )
    context = DrissionPageContext()

    await context.ensure_initialized()

    assert context.is_active() is True
    assert context.current_tab().native_tab_id == "initial"


def test_current_tab_returns_none_when_no_tab_is_active() -> None:
    context = DrissionPageContext()

    assert context.current_tab() is None


def test_current_tab_or_die_raises_when_no_tab_is_active() -> None:
    context = DrissionPageContext()

    with pytest.raises(RuntimeError, match="No active tab"):
        context.current_tab_or_die()


@pytest.mark.asyncio
async def test_sync_tabs_returns_empty_when_initialized_without_browser() -> None:
    context = initialized_context()
    context._browser = None

    assert await context.sync_tabs() == []


@pytest.mark.asyncio
async def test_sync_tabs_wraps_latest_tab_when_registry_is_empty(monkeypatch) -> None:
    context = initialized_context(EmptyRegistryBrowser())
    latest = FakePage("latest")
    monkeypatch.setattr(
        "drissionpage_mcp.context.get_latest_tab", lambda _browser: latest
    )
    context._browser_tabs = lambda: []  # type: ignore[method-assign]

    tabs = await context.sync_tabs()

    assert native_tab_ids(tabs) == ["latest"]


@pytest.mark.asyncio
async def test_sync_tabs_ignores_duplicate_pages(monkeypatch) -> None:
    context = initialized_context()
    first = FakePage("first")
    second = FakePage("second")
    context._browser_tabs = lambda: [first, first, second]  # type: ignore[method-assign]
    monkeypatch.setattr(
        "drissionpage_mcp.context.get_latest_tab", lambda _browser: second
    )

    tabs = await context.sync_tabs()

    assert native_tab_ids(tabs) == ["first", "second"]


@pytest.mark.asyncio
async def test_sync_tabs_promotes_first_synced_tab_when_latest_is_untracked(
    monkeypatch,
) -> None:
    context = initialized_context()
    page = FakePage("remaining")
    previous = context._wrap_page(FakePage("previous"))
    context._tabs = [previous]
    context._current_tab = previous
    context._browser_tabs = lambda: [page]  # type: ignore[method-assign]
    monkeypatch.setattr(
        "drissionpage_mcp.context.get_latest_tab",
        lambda _browser: FakePage("untracked"),
    )

    tabs = await context.sync_tabs()

    assert native_tab_ids(tabs) == ["remaining"]
    assert context.current_tab().native_tab_id == "remaining"


@pytest.mark.asyncio
async def test_sync_tabs_clears_current_tab_when_no_pages_remain(monkeypatch) -> None:
    context = initialized_context()
    previous = context._wrap_page(FakePage("previous"))
    context._tabs = [previous]
    context._current_tab = previous
    context._browser_tabs = lambda: [DisconnectedPage("gone")]  # type: ignore[method-assign]
    monkeypatch.setattr(
        "drissionpage_mcp.context.get_latest_tab",
        lambda _browser: FakePage("untracked"),
    )

    tabs = await context.sync_tabs()

    assert tabs == []
    assert context.current_tab() is None


def test_tab_summaries_marks_only_current_tab_active() -> None:
    context = DrissionPageContext()
    first = context._wrap_page(FakePage("first"))
    second = context._wrap_page(FakePage("second"))
    context._tabs = [first, second]
    context._current_tab = second

    summaries = context.tab_summaries()

    assert [summary["active"] for summary in summaries] == [False, True]


@pytest.mark.asyncio
async def test_switch_tab_raises_when_requested_tab_is_unknown() -> None:
    browser = FakeBrowser()
    browser.pages = {"known": FakePage("known")}
    browser.active_tab_id = "known"
    context = initialized_context(browser)

    with pytest.raises(ValueError, match="Tab not found: missing"):
        await context.switch_tab("missing")


@pytest.mark.asyncio
async def test_switch_tab_still_switches_when_browser_activation_fails() -> None:
    browser = ExplodingActivateBrowser()
    browser.pages = {"a": FakePage("a")}
    browser.active_tab_id = "a"
    context = initialized_context(browser)
    await context.sync_tabs()

    switched = await context.switch_tab("a")

    assert context.current_tab() is switched
    assert switched.native_tab_id == "a"


@pytest.mark.asyncio
async def test_close_tab_by_id_raises_when_requested_tab_is_unknown() -> None:
    browser = FakeBrowser()
    browser.pages = {"known": FakePage("known")}
    browser.active_tab_id = "known"
    context = initialized_context(browser)

    with pytest.raises(ValueError, match="Tab not found: missing"):
        await context.close_tab_by_id("missing")


@pytest.mark.asyncio
async def test_close_tab_by_id_ignores_post_close_sync_failure() -> None:
    context = initialized_context()
    tab = context._wrap_page(FakePage("a"))
    context._tabs = [tab]
    context._current_tab = tab
    sync_calls = 0

    async def fake_sync_tabs():
        nonlocal sync_calls
        sync_calls += 1
        if sync_calls == 2:
            raise RuntimeError("sync failed")
        return context.tabs()

    context.sync_tabs = fake_sync_tabs  # type: ignore[method-assign]

    await context.close_tab_by_id("a")

    assert context.tabs() == []
    assert sync_calls == 2


@pytest.mark.asyncio
async def test_cleanup_closes_browser(monkeypatch) -> None:
    closed = []

    def fake_quit(browser):
        closed.append(browser)

    monkeypatch.setattr("drissionpage_mcp.context.quit_browser", fake_quit)
    browser = FakeBrowser()
    context = initialized_context(browser)

    await context.cleanup()

    assert closed == [browser]
    assert context.is_active() is False


@pytest.mark.asyncio
@pytest.mark.parametrize("seconds", [-0.01, 10_000.0])
async def test_wait_rejects_seconds_outside_allowed_range(seconds: float) -> None:
    context = DrissionPageContext()

    with pytest.raises(ValueError, match="Wait seconds must be between"):
        await context.wait(seconds)


def test_browser_tabs_returns_empty_without_browser() -> None:
    context = DrissionPageContext()

    assert context._browser_tabs() == []


def test_browser_tabs_falls_back_to_tab_ids_when_get_tabs_fails(monkeypatch) -> None:
    browser = TabDiscoveryFallbackBrowser()
    browser.pages = {"a": FakePage("a"), "latest": FakePage("latest")}
    context = DrissionPageContext()
    context._browser = browser
    monkeypatch.setattr(
        "drissionpage_mcp.context.get_latest_tab",
        lambda _browser: browser.pages["latest"],
    )

    pages = context._browser_tabs()

    assert [page.tab_id for page in pages] == ["a", "latest"]


def test_browser_tabs_uses_latest_when_tab_id_discovery_fails(monkeypatch) -> None:
    browser = TabIdsFailBrowser()
    latest = FakePage("latest")
    context = DrissionPageContext()
    context._browser = browser
    monkeypatch.setattr(
        "drissionpage_mcp.context.get_latest_tab", lambda _browser: latest
    )

    assert context._browser_tabs() == [latest]


def test_tab_key_falls_back_to_object_id_when_tab_id_raises() -> None:
    page = BadTabIdPage()

    assert DrissionPageContext._tab_key(page) == str(id(page))


def test_normalize_browser_tab_list_handles_none() -> None:
    from drissionpage_mcp.context import _normalize_browser_tab_list

    assert _normalize_browser_tab_list(FakeBrowser(), None) == []


def test_normalize_browser_tab_list_resolves_string_ids() -> None:
    from drissionpage_mcp.context import _normalize_browser_tab_list

    browser = FakeBrowser()
    browser.pages = {"a": FakePage("a")}

    assert _normalize_browser_tab_list(browser, ["a"]) == [browser.pages["a"]]
