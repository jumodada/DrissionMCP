"""Regression coverage for explicit tab targeting and per-tab scheduling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from drissionpage_mcp.context import DrissionPageContext, TabClosedError
from drissionpage_mcp.runtime import OperationKeyConflictError
from drissionpage_mcp.server import DrissionPageMCPServer
from drissionpage_mcp.tool_outputs import TabScopedData
from drissionpage_mcp.tools import get_all_tools
from drissionpage_mcp.tools.artifacts import PageExportArtifactInput, _export_identity
from drissionpage_mcp.tools.base import (
    TabScopedInput,
    ToolOutcome,
    ToolSpec,
    ToolType,
)
from drissionpage_mcp.tools.downloads import (
    ElementClickAndDownloadInput,
    _download_identity,
)
from drissionpage_mcp.tools.navigate import NavigateInput


class _Page:
    def __init__(self, tab_id: str) -> None:
        self.tab_id = tab_id
        self.url = f"https://example.test/{tab_id}"
        self.title = tab_id


class _Browser:
    def __init__(self) -> None:
        self.pages = {"a": _Page("a"), "b": _Page("b")}
        self.active_tab_id = "a"
        self.closed_tabs: list[str] = []
        self.quit_called = False

    @property
    def latest_tab(self) -> _Page:
        return self.pages[self.active_tab_id]

    @property
    def tab_ids(self) -> list[str]:
        return list(self.pages)

    def get_tab(self, tab_id: str | None = None) -> _Page:
        return self.pages[tab_id or self.active_tab_id]

    def get_tabs(self) -> list[_Page]:
        return list(self.pages.values())

    def activate_tab(self, tab_id: str) -> None:
        self.active_tab_id = tab_id

    def close_tabs(self, tab_id: str) -> None:
        self.closed_tabs.append(tab_id)
        self.pages.pop(tab_id)
        if self.active_tab_id == tab_id:
            self.active_tab_id = next(iter(self.pages), "")

    def quit(self) -> None:
        self.quit_called = True


class _ProbeInput(TabScopedInput):
    gate: str = ""


class _ProbeData(TabScopedData):
    native_tab_id: str


def _context() -> tuple[DrissionPageContext, _Browser]:
    browser = _Browser()
    context = DrissionPageContext()
    context._browser = browser
    context._is_initialized = True
    return context, browser


def _probe_tool(handler) -> ToolSpec:
    return ToolSpec(
        name="tab_probe",
        title="Tab Probe",
        description="Exercise tab scheduling",
        input_model=_ProbeInput,
        output_model=_ProbeData,
        handler=handler,
        tool_type=ToolType.READ_ONLY,
    )


@pytest.mark.asyncio
async def test_explicit_and_implicit_targets_remain_bound_across_switch() -> None:
    context, _browser = _context()
    await context.sync_tabs()
    started = asyncio.Event()
    release = asyncio.Event()
    observations: list[tuple[str, str]] = []

    async def probe(ctx: DrissionPageContext, _args: _ProbeInput) -> ToolOutcome:
        first = ctx.current_tab_or_die().native_tab_id
        started.set()
        await release.wait()
        second = ctx.current_tab_or_die().native_tab_id
        observations.append((first, second))
        outcome = ToolOutcome()
        outcome.add_result("captured", native_tab_id=second)
        return outcome

    server = DrissionPageMCPServer()
    server.context = context
    server.tools["tab_probe"] = _probe_tool(probe)

    implicit = asyncio.create_task(server._call_tool_impl("tab_probe", {}))
    await started.wait()
    await context.switch_tab("t1")
    release.set()
    result = await implicit

    assert observations == [("a", "a")]
    assert result.structuredContent["data"] == {
        "tab_id": "t0",
        "native_tab_id": "a",
    }

    explicit = await server._call_tool_impl("tab_probe", {"tab_id": "a"})
    assert explicit.structuredContent["data"]["tab_id"] == "t0"
    assert explicit.structuredContent["data"]["native_tab_id"] == "a"


@pytest.mark.asyncio
async def test_unknown_explicit_target_fails_without_falling_back() -> None:
    context, _browser = _context()
    await context.sync_tabs()
    called = False

    async def probe(_ctx: DrissionPageContext, _args: _ProbeInput) -> ToolOutcome:
        nonlocal called
        called = True
        outcome = ToolOutcome()
        outcome.add_result("captured", native_tab_id="unexpected")
        return outcome

    server = DrissionPageMCPServer()
    server.context = context
    server.tools["tab_probe"] = _probe_tool(probe)
    result = await server._call_tool_impl(
        "tab_probe", {"tab_id": "does-not-exist"}
    )

    assert result.isError is True
    assert result.structuredContent["error"]["code"] == "TAB_NOT_FOUND"
    assert called is False


@pytest.mark.asyncio
async def test_bound_target_replaces_internal_null_tab_id() -> None:
    context, _browser = _context()
    await context.sync_tabs()

    async def probe(ctx: DrissionPageContext, _args: _ProbeInput) -> ToolOutcome:
        outcome = ToolOutcome()
        outcome.add_result(
            "captured",
            tab_id=None,
            native_tab_id=ctx.current_tab_or_die().native_tab_id,
        )
        return outcome

    server = DrissionPageMCPServer()
    server.context = context
    server.tools["tab_probe"] = _probe_tool(probe)
    result = await server._call_tool_impl("tab_probe", {"tab_id": "t1"})

    assert result.isError is False
    assert result.structuredContent["data"] == {
        "tab_id": "t1",
        "native_tab_id": "b",
    }


@pytest.mark.asyncio
async def test_page_navigate_honors_explicit_existing_tab_target() -> None:
    context, _browser = _context()
    await context.sync_tabs()
    current = await context.resolve_tab("t0")
    target = await context.resolve_tab("t1")
    current_navigate = AsyncMock()
    target_navigate = AsyncMock()
    current.navigation.navigate = current_navigate
    target.navigation.navigate = target_navigate

    server = DrissionPageMCPServer()
    server.context = context
    result = await server._call_tool_impl(
        "page_navigate",
        {"url": "https://target.example", "tab_id": "t1"},
    )

    assert result.isError is False
    assert result.structuredContent["data"]["tab_id"] == "t1"
    assert result.structuredContent["data"]["active"] is False
    current_navigate.assert_not_awaited()
    target_navigate.assert_awaited_once_with("https://target.example")


@pytest.mark.asyncio
async def test_independent_tabs_run_in_parallel_and_same_tab_serializes() -> None:
    context, _browser = _context()
    await context.sync_tabs()
    active = 0
    max_active = 0

    async def probe(ctx: DrissionPageContext, _args: _ProbeInput) -> ToolOutcome:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.03)
        tab = ctx.current_tab_or_die()
        active -= 1
        outcome = ToolOutcome()
        outcome.add_result("captured", native_tab_id=tab.native_tab_id)
        return outcome

    server = DrissionPageMCPServer()
    server.context = context
    server.tools["tab_probe"] = _probe_tool(probe)

    await asyncio.gather(
        server._call_tool_impl("tab_probe", {"tab_id": "t0"}),
        server._call_tool_impl("tab_probe", {"tab_id": "t1"}),
    )
    assert max_active == 2

    active = 0
    max_active = 0
    await asyncio.gather(
        server._call_tool_impl("tab_probe", {"tab_id": "t0"}),
        server._call_tool_impl("tab_probe", {"tab_id": "a"}),
    )
    assert max_active == 1


@pytest.mark.asyncio
async def test_tab_close_drains_in_flight_action_and_rejects_new_action() -> None:
    context, browser = _context()
    await context.sync_tabs()
    started = asyncio.Event()
    release = asyncio.Event()

    async def probe(ctx: DrissionPageContext, _args: _ProbeInput) -> ToolOutcome:
        started.set()
        await release.wait()
        tab = ctx.current_tab_or_die()
        outcome = ToolOutcome()
        outcome.add_result("captured", native_tab_id=tab.native_tab_id)
        return outcome

    server = DrissionPageMCPServer()
    server.context = context
    server.tools["tab_probe"] = _probe_tool(probe)

    action = asyncio.create_task(
        server._call_tool_impl("tab_probe", {"tab_id": "t0"})
    )
    await started.wait()
    closing = asyncio.create_task(context.close_tab_by_id("t0"))
    await asyncio.sleep(0)
    assert browser.closed_tabs == []

    rejected = await server._call_tool_impl("tab_probe", {"tab_id": "t0"})
    assert rejected.isError is True
    assert rejected.structuredContent["error"]["code"] == "TAB_CLOSED"

    release.set()
    completed = await action
    await closing
    assert completed.isError is False
    assert browser.closed_tabs == ["a"]


@pytest.mark.asyncio
async def test_browser_cleanup_drains_tab_actions_before_quit() -> None:
    context, browser = _context()
    await context.sync_tabs()
    tab = await context.resolve_tab("t0")
    started = asyncio.Event()
    release = asyncio.Event()

    async def action() -> None:
        async with tab.action():
            started.set()
            await release.wait()

    running = asyncio.create_task(action())
    await started.wait()
    cleanup = asyncio.create_task(context.close_browser())
    await asyncio.sleep(0)
    assert browser.quit_called is False

    release.set()
    await running
    assert await cleanup is True
    assert browser.quit_called is True


@pytest.mark.asyncio
async def test_browser_cleanup_rejects_new_tabs_while_draining() -> None:
    context, browser = _context()
    await context.sync_tabs()
    tab = await context.resolve_tab("t0")
    started = asyncio.Event()
    release = asyncio.Event()

    async def action() -> None:
        async with tab.action():
            started.set()
            await release.wait()

    running = asyncio.create_task(action())
    await started.wait()
    cleanup = asyncio.create_task(context.close_browser())
    await asyncio.sleep(0)

    with pytest.raises(TabClosedError, match="browser context is closing"):
        await context.new_tab()
    assert browser.quit_called is False

    release.set()
    await running
    assert await cleanup is True
    assert browser.quit_called is True


@pytest.mark.asyncio
async def test_owned_context_close_drains_and_closes_sibling_tabs() -> None:
    context, _browser = _context()
    first = context._wrap_page(
        _Page("owned-a"),
        browser_context_id="context-1",
        owns_browser_context=True,
    )
    sibling = context._wrap_page(
        _Page("owned-b"),
        browser_context_id="context-1",
        owns_browser_context=True,
    )
    context._tabs = [first, sibling]
    context._current_tab = first
    context._owned_browser_context_ids = {"context-1"}
    disposed: list[str] = []
    context._dispose_browser_context = disposed.append
    started = asyncio.Event()
    release = asyncio.Event()

    async def sibling_action() -> None:
        async with sibling.action():
            started.set()
            await release.wait()

    running = asyncio.create_task(sibling_action())
    await started.wait()
    closing = asyncio.create_task(context.close_tab(first))
    await asyncio.sleep(0)
    assert disposed == []

    release.set()
    await running
    await closing
    assert disposed == ["context-1"]
    assert first.is_closed is True
    assert sibling.is_closed is True
    assert context.tabs() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["export", "download"])
async def test_exact_once_identity_includes_bound_tab(kind: str) -> None:
    context, _browser = _context()
    await context.sync_tabs()
    operation_key = f"cross-tab-{kind}"
    if kind == "export":
        args = PageExportArtifactInput(
            format="pdf", operation_key=operation_key, filename="page.pdf"
        )
        identity = _export_identity
    else:
        args = ElementClickAndDownloadInput(
            selector="#download", operation_key=operation_key
        )
        identity = _download_identity

    async with context.bind_tab("t0"):
        _action_0, _key_0, fingerprint_0 = identity(context, args)
    async with context.bind_tab("t1"):
        _action_1, _key_1, fingerprint_1 = identity(context, args)

    assert fingerprint_0 != fingerprint_1
    context.claim_operation(operation_key, fingerprint_0)
    with pytest.raises(OperationKeyConflictError):
        context.claim_operation(operation_key, fingerprint_1)


def test_exact_once_identity_normalizes_native_tab_alias() -> None:
    context, _browser = _context()
    context._tabs = [
        type(
            "TrackedTab",
            (),
            {"mcp_tab_id": "t0", "native_tab_id": "a"},
        )()
    ]
    args = PageExportArtifactInput(
        format="pdf", operation_key="native-alias", filename="page.pdf", tab_id="a"
    )
    _action, _key, native_fingerprint = _export_identity(context, args)
    args.tab_id = "t0"
    _action, _key, mcp_fingerprint = _export_identity(context, args)
    assert native_fingerprint == mcp_fingerprint


def test_all_tab_scoped_tools_publish_optional_tab_id() -> None:
    tab_scoped = [
        tool for tool in get_all_tools() if issubclass(tool.input_model, TabScopedInput)
    ]

    assert len(tab_scoped) == 63
    for tool in tab_scoped:
        schema = tool.input_schema.model_json_schema()
        assert "tab_id" in schema["properties"], tool.name
        assert "tab_id" not in schema.get("required", []), tool.name
        output_schema = tool.output_schema()
        tab_id_contracts = _tab_id_contracts(output_schema)
        assert tab_id_contracts, tool.name
        assert all(required for required, _definition in tab_id_contracts), tool.name
        assert all(
            definition.get("type") == "string"
            for _required, definition in tab_id_contracts
        ), tool.name


def test_navigation_creation_options_have_unambiguous_target_semantics() -> None:
    created = NavigateInput(
        url="https://example.test",
        new_tab=True,
        background=True,
        new_window=True,
        new_context=True,
    )
    assert created.background is True

    with pytest.raises(ValidationError, match="require new_tab=true"):
        NavigateInput(url="https://example.test", background=True)
    with pytest.raises(ValidationError, match="cannot be combined"):
        NavigateInput(
            url="https://example.test",
            new_tab=True,
            tab_id="t0",
        )


def _tab_id_contracts(value) -> list[tuple[bool, dict]]:
    contracts: list[tuple[bool, dict]] = []
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict) and isinstance(properties.get("tab_id"), dict):
            contracts.append(
                ("tab_id" in value.get("required", []), properties["tab_id"])
            )
        for nested in value.values():
            contracts.extend(_tab_id_contracts(nested))
    elif isinstance(value, list):
        for nested in value:
            contracts.extend(_tab_id_contracts(nested))
    return contracts
