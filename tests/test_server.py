"""Test MCP server functionality."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from mcp.types import CallToolResult
from pydantic import BaseModel

import drissionpage_mcp.server as server_module
from drissionpage_mcp import __version__
from drissionpage_mcp.server import DrissionPageMCPServer, _tool_supports_output_schema
from drissionpage_mcp.tools import get_all_tools
from drissionpage_mcp.tools.base import (
    JSON_RESULT_SENTINEL,
    ToolExecutionMode,
    ToolSpec,
    ToolType,
)


class TestDrissionPageMCPServer:
    """Test MCP server."""

    def test_server_initialization(self):
        """Test server can be initialized."""
        server = DrissionPageMCPServer()
        assert server.name == "DrissionPage MCP"
        assert server.version == __version__
        assert server.context is None
        assert server.server.instructions
        assert "standalone" in server.server.instructions.lower()
        assert "atomic" in server.server.instructions.lower()
        assert "drissionpage://skills/catalog" in server.server.instructions
        assert "skills/<skill-name>/SKILL.md" in server.server.instructions
        assert "optional" in server.server.instructions.lower()

    def test_server_custom_name_version(self):
        """Test server with custom name and version."""
        server = DrissionPageMCPServer(name="Custom MCP", version="1.0.0")
        assert server.name == "Custom MCP"
        assert server.version == "1.0.0"

    def test_server_rejects_unsupported_mcp_sdk_before_handler_registration(
        self, monkeypatch
    ):
        """fails with the compatibility message instead of an SDK AttributeError."""

        def reject_sdk() -> str:
            raise RuntimeError(
                'Unsupported MCP Python SDK version 2.0.0; requires mcp>=1.0.0,<2'
            )

        monkeypatch.setattr(server_module, "ensure_supported_mcp_sdk", reject_sdk)

        with pytest.raises(RuntimeError, match=r"mcp>=1\.0\.0,<2"):
            DrissionPageMCPServer()

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test server cleanup."""
        server = DrissionPageMCPServer()
        mock_context = Mock()
        mock_context.cleanup = Mock(return_value=None)
        server.context = mock_context
        await server.cleanup()
        mock_context.cleanup.assert_called_once()
        assert server.context is None


class TestToolsIntegration:
    """Test tools integration."""

    def test_all_tools_have_required_attributes(self):
        """Test that all tools have required attributes."""
        tools = get_all_tools()
        for tool in tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "input_schema")
            assert hasattr(tool, "handler")
            assert isinstance(tool.name, str)
            assert isinstance(tool.description, str)
            assert len(tool.name) > 0
            assert len(tool.description) > 0

    def test_tool_names_are_unique(self):
        """Test that all tool names are unique."""
        tools = get_all_tools()
        names = [tool.name for tool in tools]
        assert len(names) == len(set(names)), "Tool names should be unique"

    def test_expected_tools_present(self):
        """Test that expected tools are present."""
        tools = get_all_tools()
        tool_names = [tool.name for tool in tools]
        assert "page_navigate" in tool_names
        assert "page_go_back" in tool_names
        assert "page_go_forward" in tool_names
        assert "page_refresh" in tool_names
        assert "tab_list" in tool_names
        assert "tab_switch" in tool_names
        assert "tab_close" in tool_names
        assert "page_resize" in tool_names
        assert "page_screenshot" in tool_names
        assert "page_screenshot_save" in tool_names
        assert "page_snapshot" in tool_names
        assert "page_accessibility_snapshot" in tool_names
        assert "page_observe" in tool_names
        assert "page_console_logs" in tool_names
        assert "page_evaluate" in tool_names
        assert "page_pointer_move" in tool_names
        assert "page_pointer_drag" in tool_names
        assert "page_pointer_drag_element" in tool_names
        assert "page_click_xy" in tool_names
        assert "page_close" in tool_names
        assert "page_get_url" in tool_names
        assert "element_find" in tool_names
        assert "element_find_all" in tool_names
        assert "element_click" in tool_names
        assert "element_type" in tool_names
        assert "element_upload_file" in tool_names
        assert "element_scroll_into_view" in tool_names
        assert "element_hover" in tool_names
        assert "element_select" in tool_names
        assert "element_check" in tool_names
        assert "element_input_text" not in tool_names
        assert "element_get_text" in tool_names
        assert "element_get_attribute" in tool_names
        assert "element_get_property" in tool_names
        assert "element_get_html" in tool_names
        assert "page_scroll" in tool_names
        assert "keyboard_press" in tool_names
        assert "frame_list" in tool_names
        assert "frame_snapshot" in tool_names
        assert "frame_find" in tool_names
        assert "shadow_find" in tool_names
        assert "shadow_find_all" in tool_names
        assert "browser_cookies_get" in tool_names
        assert "browser_cookies_set" in tool_names
        assert "browser_cookies_delete" in tool_names
        assert "browser_cookies_clear" in tool_names
        assert "browser_headers_set" in tool_names
        assert "browser_user_agent_set" in tool_names
        assert "browser_cache_clear" in tool_names
        assert "storage_get" in tool_names
        assert "storage_set" in tool_names
        assert "storage_clear" in tool_names
        assert "page_dialog_respond" in tool_names
        assert "page_dialog_observe" in tool_names
        assert "element_state_get" in tool_names
        assert "element_click_and_download" in tool_names
        assert "network_listen_start" in tool_names
        assert "network_listen_wait" in tool_names
        assert "network_listen_stop" in tool_names
        assert "network_blocked_urls_set" in tool_names
        assert "wait_for_element" in tool_names
        assert "wait_for_url" in tool_names
        assert "wait_time" in tool_names
        assert "wait_until" in tool_names
        assert "wait_sleep" not in tool_names
        assert {
            "form_inspect",
            "form_fill",
            "form_submit",
            "form_fill_preview",
        }.isdisjoint(tool_names)
        assert {
            "page_detect_challenges",
            "page_click_xy_batch",
            "page_wait_challenge_result",
            "browser_open_and_snapshot",
            "browser_extract_links",
        }.isdisjoint(tool_names)
        assert len(tool_names) == 69


if __name__ == "__main__":
    pytest.main([__file__])


class TestCallToolResultContract:
    """Test server call result shape."""

    def test_call_result_has_structured_content_and_text_mirror(self):
        server = DrissionPageMCPServer()
        from drissionpage_mcp.tools.base import ToolOutcome

        response = ToolOutcome()
        response.add_result("done")
        result = server._call_result(response)
        assert isinstance(result, CallToolResult)
        assert result.structuredContent["ok"] is True
        assert result.content[0].text.startswith(JSON_RESULT_SENTINEL)
        assert result.isError is False


@pytest.mark.asyncio
async def test_internal_call_tool_impl_success_path_uses_context() -> None:
    server = DrissionPageMCPServer()
    result = await server._call_tool_impl("wait_time", {"seconds": 0})
    assert result.isError is False
    assert result.structuredContent == {
        "ok": True,
        "message": "Waited for 0.0 seconds",
        "data": {"waited_seconds": 0.0},
    }
    assert server.context is not None
    assert not hasattr(server.context, "action_history")


@pytest.mark.asyncio
async def test_internal_call_tool_impl_serializes_shared_context(monkeypatch) -> None:
    active = 0
    max_active = 0
    contexts = []

    class FakeContext:
        def current_tab(self):
            return None

        async def cleanup(self) -> None:
            return None

    class EmptyArgs(BaseModel):
        pass

    async def probe(context, _args):
        nonlocal active, max_active
        contexts.append(context)
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        from drissionpage_mcp.tools.base import ToolOutcome

        outcome = ToolOutcome()
        outcome.add_result("done", closed=True)
        return outcome

    from drissionpage_mcp.tool_outputs import PageCloseData

    monkeypatch.setattr(server_module, "DrissionPageContext", FakeContext)
    server = DrissionPageMCPServer()
    server.tools["probe"] = ToolSpec(
        name="probe",
        title="Probe",
        description="Track concurrent execution",
        input_model=EmptyArgs,
        output_model=PageCloseData,
        handler=probe,
        tool_type=ToolType.READ_ONLY,
    )

    first, second = await asyncio.gather(
        server._call_tool_impl("probe", {}),
        server._call_tool_impl("probe", {}),
    )

    assert first.isError is False
    assert second.isError is False
    assert max_active == 1
    assert len(contexts) == 2
    assert contexts[0] is contexts[1]


@pytest.mark.asyncio
async def test_listener_wait_does_not_block_unrelated_serialized_action(monkeypatch) -> None:
    """A bounded network wait must release the global action lane while polling."""

    wait_started = asyncio.Event()
    action_started = asyncio.Event()

    class FakeContext:
        async def cleanup(self) -> None:
            return None

    class EmptyArgs(BaseModel):
        pass

    async def listener_wait(_context, _args):
        wait_started.set()
        await asyncio.sleep(0.15)
        from drissionpage_mcp.tools.base import ToolOutcome

        outcome = ToolOutcome()
        outcome.add_result(
            "Captured 0 network packets",
            listening=True,
            timed_out=True,
            count=0,
            limit=1,
            packets=[],
            meta={"approx_tokens": 1, "json_chars": 1, "truncated": False},
        )
        return outcome

    async def get_url(_context, _args):
        action_started.set()
        from drissionpage_mcp.tools.base import ToolOutcome

        outcome = ToolOutcome()
        outcome.add_result("Current URL", url="https://example.test")
        return outcome

    from drissionpage_mcp.tool_outputs import NetworkListenWaitData, PageGetUrlData

    monkeypatch.setattr(server_module, "DrissionPageContext", FakeContext)
    server = DrissionPageMCPServer()
    server.tools["network_listen_wait"] = ToolSpec(
        name="network_listen_wait",
        title="Wait",
        description="Wait for packets",
        input_model=EmptyArgs,
        output_model=NetworkListenWaitData,
        handler=listener_wait,
        tool_type=ToolType.READ_ONLY,
        execution_mode=ToolExecutionMode.CONCURRENT,
    )
    server.tools["page_get_url"] = ToolSpec(
        name="page_get_url",
        title="URL",
        description="Read URL",
        input_model=EmptyArgs,
        output_model=PageGetUrlData,
        handler=get_url,
        tool_type=ToolType.READ_ONLY,
    )

    wait_task = asyncio.create_task(server._call_tool_impl("network_listen_wait", {}))
    await asyncio.wait_for(wait_started.wait(), timeout=0.1)
    await asyncio.wait_for(
        server._call_tool_impl("page_get_url", {}),
        timeout=0.08,
    )
    assert action_started.is_set()
    result = await wait_task
    assert result.isError is False


@pytest.mark.asyncio
async def test_dialog_responder_can_run_with_serialized_trigger(monkeypatch) -> None:
    responder_ready = asyncio.Event()
    dialog_triggered = asyncio.Event()
    contexts = []

    class FakeContext:
        async def cleanup(self) -> None:
            return None

    class EmptyArgs(BaseModel):
        pass

    async def respond(context, _args):
        contexts.append(context)
        responder_ready.set()
        await asyncio.wait_for(dialog_triggered.wait(), timeout=0.1)
        from drissionpage_mcp.tools.base import ToolOutcome

        outcome = ToolOutcome()
        outcome.add_result("responded", closed=True)
        return outcome

    async def trigger(context, _args):
        contexts.append(context)
        dialog_triggered.set()
        from drissionpage_mcp.tools.base import ToolOutcome

        outcome = ToolOutcome()
        outcome.add_result("triggered", closed=True)
        return outcome

    from drissionpage_mcp.tool_outputs import PageCloseData

    monkeypatch.setattr(server_module, "DrissionPageContext", FakeContext)
    server = DrissionPageMCPServer()
    server.tools["page_dialog_respond"] = ToolSpec(
        name="page_dialog_respond",
        title="Respond",
        description="Wait for a dialog trigger",
        input_model=EmptyArgs,
        output_model=PageCloseData,
        handler=respond,
        tool_type=ToolType.DESTRUCTIVE,
    )
    server.tools["trigger"] = ToolSpec(
        name="trigger",
        title="Trigger",
        description="Trigger a pending dialog",
        input_model=EmptyArgs,
        output_model=PageCloseData,
        handler=trigger,
        tool_type=ToolType.DESTRUCTIVE,
    )

    responder = asyncio.create_task(server._call_tool_impl("page_dialog_respond", {}))
    await asyncio.wait_for(responder_ready.wait(), timeout=0.1)
    response, triggered = await asyncio.gather(
        responder,
        server._call_tool_impl("trigger", {}),
    )

    assert response.isError is False
    assert triggered.isError is False
    assert contexts[0] is contexts[1]


@pytest.mark.asyncio
async def test_cleanup_waits_for_responder_and_serialized_tool(monkeypatch) -> None:
    all_started = asyncio.Event()
    release = asyncio.Event()
    started = 0

    class FakeContext:
        def __init__(self) -> None:
            self.cleaned = False

        async def cleanup(self) -> None:
            self.cleaned = True

    class EmptyArgs(BaseModel):
        pass

    async def hold(_context, _args):
        nonlocal started
        started += 1
        if started == 2:
            all_started.set()
        await release.wait()
        from drissionpage_mcp.tools.base import ToolOutcome

        outcome = ToolOutcome()
        outcome.add_result("done", closed=True)
        return outcome

    from drissionpage_mcp.tool_outputs import PageCloseData

    monkeypatch.setattr(server_module, "DrissionPageContext", FakeContext)
    server = DrissionPageMCPServer()
    responder_spec = ToolSpec(
        name="page_dialog_respond",
        title="Respond",
        description="Hold the responder lane",
        input_model=EmptyArgs,
        output_model=PageCloseData,
        handler=hold,
        tool_type=ToolType.DESTRUCTIVE,
    )
    trigger_spec = ToolSpec(
        name="trigger",
        title="Trigger",
        description="Hold the serialized lane",
        input_model=EmptyArgs,
        output_model=PageCloseData,
        handler=hold,
        tool_type=ToolType.DESTRUCTIVE,
    )
    server.tools["page_dialog_respond"] = responder_spec
    server.tools["trigger"] = trigger_spec

    responder = asyncio.create_task(server._call_tool_impl("page_dialog_respond", {}))
    trigger = asyncio.create_task(server._call_tool_impl("trigger", {}))
    await asyncio.wait_for(all_started.wait(), timeout=0.1)
    context = server.context
    cleanup = asyncio.create_task(server.cleanup())
    await asyncio.sleep(0)

    assert cleanup.done() is False
    assert context is not None
    assert context.cleaned is False

    release.set()
    await asyncio.gather(responder, trigger, cleanup)

    assert context.cleaned is True
    assert server.context is None


@pytest.mark.asyncio
async def test_invalid_or_unknown_tool_does_not_initialize_context(monkeypatch) -> None:
    created = 0

    class FakeContext:
        def __init__(self) -> None:
            nonlocal created
            created += 1

    monkeypatch.setattr(server_module, "DrissionPageContext", FakeContext)
    server = DrissionPageMCPServer()

    unknown = await server._call_tool_impl("missing_tool", {})
    invalid = await server._call_tool_impl("wait_time", {"unexpected": True})

    assert unknown.isError is True
    assert invalid.isError is True
    assert created == 0
    assert server.context is None


@pytest.mark.asyncio
async def test_context_initialization_failure_uses_tool_error_contract(
    monkeypatch,
) -> None:
    class FailingContext:
        def __init__(self) -> None:
            raise RuntimeError("browser launch failed")

    monkeypatch.setattr(server_module, "DrissionPageContext", FailingContext)
    server = DrissionPageMCPServer()

    result = await server._call_tool_impl("wait_time", {"seconds": 0})

    assert result.isError is True
    assert result.structuredContent["error"]["code"] == "BROWSER_START_FAILED"
    assert result.structuredContent["error"]["details"]["tool_name"] == "wait_time"
    assert server.context is None
    assert server._active_tool_calls == 0


@pytest.mark.asyncio
async def test_navigate_browser_connect_failure_uses_startup_error_code() -> None:
    from DrissionPage.errors import BrowserConnectError

    server = DrissionPageMCPServer()
    context = Mock()
    context.ensure_tab = AsyncMock(
        side_effect=BrowserConnectError("opaque browser connection failure")
    )
    server.context = context

    result = await server._call_tool_impl(
        "page_navigate", {"url": "https://example.test/"}
    )

    assert result.isError is True
    assert result.structuredContent["error"]["code"] == "BROWSER_START_FAILED"
    assert result.structuredContent["message"] == "Browser failed to start."
    assert server._active_tool_calls == 0


@pytest.mark.asyncio
async def test_internal_call_tool_impl_does_not_retain_dialog_prompt() -> None:
    server = DrissionPageMCPServer()
    secret = "dialog-history-secret"
    result = await server._call_tool_impl(
        "page_dialog_respond",
        {"action": "accept", "prompt_text": secret, "timeout": 0.1},
    )

    assert result.isError is True
    assert server.context is not None
    assert secret not in json.dumps(result.structuredContent, ensure_ascii=False)
    assert not hasattr(server.context, "action_history")


@pytest.mark.asyncio
async def test_dialog_native_failure_secret_is_absent_from_error() -> None:
    from drissionpage_mcp.browser.dialogs import DialogResponseIndeterminateError
    from drissionpage_mcp.context import DrissionPageContext

    secret = "dialog-native-failure-secret"

    class FailingDialogs:
        def probe(self) -> None:
            return None

        async def wait_for_pending(self, *, timeout: float) -> dict[str, str]:
            return {"dialog_type": "prompt", "message": "redacted"}

        async def respond(self, **kwargs: object) -> None:
            raise DialogResponseIndeterminateError(f"native response exposed {secret}")

    server = DrissionPageMCPServer()
    server.context = DrissionPageContext()
    server.context._current_tab = SimpleNamespace(  # type: ignore[assignment]
        url="https://example.test/dialog",
        mcp_tab_id="t0",
        dialogs=FailingDialogs(),
    )

    result = await server._call_tool_impl(
        "page_dialog_respond",
        {"action": "accept", "prompt_text": secret, "timeout": 1},
    )

    assert result.isError is True
    public = json.dumps(result.structuredContent, ensure_ascii=False)
    assert secret not in public
    assert not hasattr(server.context, "action_history")
    receipt = list(server.context._operation_receipts.values())[0]
    assert receipt.status == "indeterminate"
    assert receipt.error_code == "DIALOG_RESPONSE_INDETERMINATE"


@pytest.mark.asyncio
async def test_internal_call_tool_impl_converts_unexpected_exceptions() -> None:

    class EmptyArgs(BaseModel):
        pass

    async def boom(_context, _args):
        raise RuntimeError("browser launch failed")

    server = DrissionPageMCPServer()
    from drissionpage_mcp.tool_outputs import PageCloseData

    server.tools["boom"] = ToolSpec(
        name="boom",
        title="Boom",
        description="Raise for tests",
        input_model=EmptyArgs,
        output_model=PageCloseData,
        handler=boom,
        tool_type=ToolType.READ_ONLY,
    )
    result = await server._call_tool_impl("boom", {})
    assert result.isError is True
    assert result.structuredContent["error"]["code"] == "BROWSER_START_FAILED"
    assert result.structuredContent["error"]["details"]["tool_name"] == "boom"
    assert any(
        hint.get("command") == "drissionpage-mcp doctor --launch-browser"
        for hint in result.structuredContent["error"]["details"]["hints"]
    )


@pytest.mark.asyncio
async def test_internal_call_tool_impl_redacts_runtime_exception_details() -> None:
    class EmptyArgs(BaseModel):
        pass

    secret = "secret-object-id"

    async def boom(_context, _args):
        raise RuntimeError(
            "CDP failure "
            + repr(
                {
                    "objectId": secret,
                    "stackTrace": {"callFrames": [{"url": "file:///private/path"}]},
                    "版本": "4.1.1.4",
                }
            )
        )

    server = DrissionPageMCPServer()
    from drissionpage_mcp.tool_outputs import PageCloseData

    server.tools["boom"] = ToolSpec(
        name="boom",
        title="Boom",
        description="Raise internal details for tests",
        input_model=EmptyArgs,
        output_model=PageCloseData,
        handler=boom,
        tool_type=ToolType.READ_ONLY,
    )

    result = await server._call_tool_impl("boom", {})
    public = json.dumps(result.structuredContent, ensure_ascii=False)

    assert result.isError is True
    assert result.structuredContent["error"]["code"] == "UNKNOWN_ERROR"
    assert secret not in public
    assert "objectId" not in public
    assert "stackTrace" not in public
    assert "file:///private/path" not in public
    assert "版本" not in public
    assert "4.1.1.4" not in public


@pytest.mark.asyncio
async def test_run_server_cleans_up_after_server_error() -> None:

    class FakeLowLevelServer:
        def get_capabilities(self, **_kwargs):
            return {}

        async def run(self, *_args, **_kwargs) -> None:
            raise RuntimeError("stdio failed")

    class AsyncCleanupContext:
        def __init__(self) -> None:
            self.cleaned = False

        async def cleanup(self) -> None:
            self.cleaned = True

    server = DrissionPageMCPServer()
    context = AsyncCleanupContext()
    server.context = context
    server.server = FakeLowLevelServer()
    with pytest.raises(RuntimeError, match="stdio failed"):
        await server.run_server(object(), object())
    assert context.cleaned is True
    assert server.context is None


def test_tool_supports_output_schema_signature_fallback(monkeypatch) -> None:

    def fake_tool(*, outputSchema=None):
        return outputSchema

    monkeypatch.setattr(server_module, "Tool", fake_tool)
    assert _tool_supports_output_schema() is True

    def fail_signature(_obj):
        raise ValueError("not inspectable")

    monkeypatch.setattr(server_module.inspect, "signature", fail_signature)
    assert _tool_supports_output_schema() is False
