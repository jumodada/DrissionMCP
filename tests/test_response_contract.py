"""Response contract tests for machine-readable MCP tool results."""

from __future__ import annotations

import base64
import json
import re

import pytest
from jsonschema import ValidationError, validate

from drissionpage_mcp.browser.network import NetworkListenerNotFoundError
from drissionpage_mcp.response_errors import (
    ErrorCode,
    classify_error,
    public_exception_message,
    recovery_hints,
)
from drissionpage_mcp.response_media import build_screenshot_metadata
from drissionpage_mcp.tools import get_all_tools
from drissionpage_mcp.tools.base import ToolOutcome

JSON_RESULT_SENTINEL = "### JSON_RESULT"


def tool_result_output_schema(tool_name: str) -> dict[str, object]:
    return next(
        tool for tool in get_all_tools() if tool.name == tool_name
    ).output_schema()


class ToolResult:
    """Payload factory used only to validate generated public schemas."""

    @staticmethod
    def success(message: str = "", **data: object):
        class Payload:
            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "message": message, "data": data}

        return Payload()

    @staticmethod
    def failure(code: ErrorCode | str, message: str, **details: object):
        code_value = code.value if isinstance(code, ErrorCode) else str(code)

        class Payload:
            def to_dict(self) -> dict[str, object]:
                return {
                    "ok": False,
                    "message": message,
                    "error": {
                        "code": code_value,
                        "message": message,
                        "details": details,
                    },
                }

        return Payload()


ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


def test_result_content_starts_with_json_result_sentinel() -> None:
    """returns the JSON_RESULT sentinel as the first text content item for results."""
    response = ToolOutcome()
    response.add_result('{"ok": true}')
    content = response.content()
    assert content[0].type == "text"
    assert content[0].text.startswith(JSON_RESULT_SENTINEL)


def test_default_success_content_starts_with_json_result_sentinel() -> None:
    """returns the JSON_RESULT sentinel for default successful empty responses."""
    content = ToolOutcome().content()
    assert content[0].type == "text"
    assert content[0].text.startswith(JSON_RESULT_SENTINEL)


def test_error_without_explicit_code_is_classified_from_message() -> None:
    """maps common tool-level failure messages to stable error codes."""
    response = ToolOutcome()
    response.add_error("Failed to find element '#missing': Element not found")
    payload = response.structured_content()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "ELEMENT_NOT_FOUND"


def test_stale_network_listener_has_stable_public_error_contract() -> None:
    error = NetworkListenerNotFoundError("private stale token value")

    assert classify_error(error, "network_listen_wait") is ErrorCode.LISTENER_NOT_FOUND
    assert public_exception_message(error, ErrorCode.LISTENER_NOT_FOUND) == (
        "The requested network listener is stale or not active."
    )


def test_add_error_includes_actionable_recovery_hints() -> None:
    """adds machine-readable next steps without changing the error envelope."""
    response = ToolOutcome()
    response.add_error(
        "Failed to find element '#missing': Element not found",
        ErrorCode.ELEMENT_NOT_FOUND,
        selector="#missing",
    )
    details = response.structured_content()["error"]["details"]
    hints = details["hints"]
    assert details["selector"] == "#missing"
    assert {hint["action"] for hint in hints} >= {
        "inspect_page_snapshot",
        "find_similar_elements",
        "wait_for_element",
        "check_iframe_or_dynamic_content",
    }
    assert {hint.get("tool") for hint in hints} >= {
        "page_snapshot",
        "element_find_all",
        "wait_for_element",
    }


def test_recovery_hints_cover_common_runtime_failures() -> None:
    """keeps recovery hints deterministic for high-frequency failure categories."""
    timeout_hints = recovery_hints(ErrorCode.TIMEOUT, tool_name="wait_for_url")
    browser_hints = recovery_hints(ErrorCode.BROWSER_START_FAILED)
    not_initialized_hints = recovery_hints(ErrorCode.BROWSER_NOT_INITIALIZED)
    argument_hints = recovery_hints(ErrorCode.MCP_ARGUMENT_INVALID)
    not_found_hints = recovery_hints(ErrorCode.TOOL_NOT_FOUND)
    screenshot_policy_hints = recovery_hints(
        ErrorCode.POLICY_DENIED, message="Screenshot path denied by policy"
    )
    unsupported_hints = recovery_hints(
        ErrorCode.UNSUPPORTED_OPERATION,
        tool_name="network_listen_start",
        message="listener unavailable",
    )
    pending_dialog_hints = recovery_hints(ErrorCode.DIALOG_PENDING)
    missing_dialog_hints = recovery_hints(ErrorCode.DIALOG_NOT_FOUND)
    missing_listener_hints = recovery_hints(ErrorCode.LISTENER_NOT_FOUND)
    assert {hint["action"] for hint in timeout_hints} >= {
        "increase_timeout",
        "inspect_current_page",
    }
    assert any(
        hint.get("command") == "drissionpage-mcp doctor --launch-browser"
        for hint in browser_hints
    )
    assert not_initialized_hints[0] == {
        "action": "navigate_first",
        "message": "Open a page with page_navigate, then inspect it with page_snapshot or another read-only tool.",
        "tool": "page_navigate",
    }
    assert argument_hints[0]["action"] == "check_input_schema"
    catalog_hint = next(
        hint for hint in argument_hints if hint["action"] == "inspect_tool_schema"
    )
    assert "tools/list" in catalog_hint["message"]
    assert "complete JSON Schema" in catalog_hint["message"]
    assert not_found_hints[0]["action"] == "list_available_tools"
    assert any(
        hint.get("env") == "DP_MCP_SCREENSHOT_ROOT" for hint in screenshot_policy_hints
    )
    assert any(hint["action"] == "verify_listener_api" for hint in unsupported_hints)
    assert {hint.get("tool") for hint in pending_dialog_hints} >= {
        "page_dialog_observe",
        "page_dialog_respond",
    }
    assert {hint.get("tool") for hint in missing_dialog_hints} >= {
        "page_dialog_observe",
        "page_dialog_respond",
    }
    assert missing_listener_hints == [
        {
            "action": "restart_network_listener",
            "message": "Start a new network listener and use its returned listener_token.",
            "tool": "network_listen_start",
        }
    ]


def test_screenshot_result_includes_image_content_and_json_metadata() -> None:
    """emits PNG image content plus parseable screenshot metadata."""
    response = ToolOutcome()
    response.add_screenshot(ONE_PIXEL_PNG, {"full_page": False})
    content = response.content()
    payload = response.structured_content()
    screenshot = payload["data"]["screenshot"]
    assert any(item.type == "image" for item in content)
    assert screenshot == {
        "mime_type": "image/png",
        "inline": True,
        "encoding": "base64",
        "full_page": False,
        "bytes": len(base64.b64decode(ONE_PIXEL_PNG)),
        "width": 1,
        "height": 1,
    }
    text_mirror_payload = json.loads(
        re.search("```json\\n(.*?)\\n```", content[0].text, re.S).group(1)
    )
    assert text_mirror_payload["data"]["screenshot"] == screenshot


def test_errors_module_reexports_stable_error_api() -> None:
    """keeps the public error helper module from becoming dead re-export slop."""
    from drissionpage_mcp.errors import ErrorCode, ToolError, classify_error

    assert ErrorCode.TIMEOUT.value == "TIMEOUT"
    assert ToolError(code="X", message="m").to_dict() == {"code": "X", "message": "m"}
    assert classify_error(TimeoutError("timed out")) is ErrorCode.TIMEOUT


@pytest.mark.parametrize(
    ("exc", "tool_name", "expected"),
    [
        (
            type("PolicyError", (Exception,), {"code": ErrorCode.POLICY_DENIED})(
                "blocked"
            ),
            "",
            ErrorCode.POLICY_DENIED,
        ),
        (ValueError("selector syntax invalid"), "", ErrorCode.SELECTOR_INVALID),
        (RuntimeError("operation timed out"), "", ErrorCode.TIMEOUT),
        (RuntimeError("No active tab"), "", ErrorCode.BROWSER_NOT_INITIALIZED),
        (
            RuntimeError("failed to navigate to url"),
            "",
            ErrorCode.PAGE_NAVIGATION_FAILED,
        ),
        (
            type("BrowserConnectError", (Exception,), {})("opaque upstream failure"),
            "page_navigate",
            ErrorCode.BROWSER_START_FAILED,
        ),
        (
            type("AlertExistsError", (Exception,), {})("opaque upstream failure"),
            "page_observe",
            ErrorCode.DIALOG_PENDING,
        ),
        (
            RuntimeError("browser initialization failed"),
            "page_navigate",
            ErrorCode.BROWSER_START_FAILED,
        ),
        (RuntimeError("boom"), "page_navigate", ErrorCode.PAGE_NAVIGATION_FAILED),
        (RuntimeError("screenshot failed"), "", ErrorCode.SCREENSHOT_FAILED),
        (RuntimeError("policy allowlist denied"), "", ErrorCode.POLICY_DENIED),
        (RuntimeError("browser launch failed"), "", ErrorCode.BROWSER_START_FAILED),
        (RuntimeError("listener unsupported"), "", ErrorCode.UNSUPPORTED_OPERATION),
        (
            RuntimeError("存在未处理的提示框。 版本: 4.1.1.4"),
            "page_observe",
            ErrorCode.DIALOG_PENDING,
        ),
    ],
)
def test_classify_error_maps_mcp_recovery_categories(
    exc: Exception, tool_name: str, expected: ErrorCode
) -> None:
    assert classify_error(exc, tool_name) is expected


def test_classify_error_accepts_known_string_codes_and_ignores_unknown_ones() -> None:
    known = type("KnownCodeError", (Exception,), {"code": "POLICY_DENIED"})(
        "blocked"
    )
    unknown = type("UnknownCodeError", (Exception,), {"code": "NOT_REGISTERED"})(
        "element not found"
    )

    assert classify_error(known) is ErrorCode.POLICY_DENIED
    assert classify_error(unknown) is ErrorCode.ELEMENT_NOT_FOUND


@pytest.mark.parametrize(
    ("exc", "code", "expected"),
    [
        (
            RuntimeError("没有找到元素。 版本: 4.1.1.4"),
            ErrorCode.ELEMENT_NOT_FOUND,
            "Element not found.",
        ),
        (
            RuntimeError(
                "CDP error {'objectId': 'secret-object', 'stackTrace': {'callFrames': []}}"
            ),
            ErrorCode.UNKNOWN_ERROR,
            "Unexpected browser operation failure.",
        ),
        (
            RuntimeError("存在未处理的提示框。 版本: 4.1.1.4"),
            ErrorCode.DIALOG_PENDING,
            "A JavaScript dialog is pending and blocks this browser operation.",
        ),
    ],
)
def test_public_exception_message_never_reflects_runtime_internals(
    exc: Exception, code: ErrorCode, expected: str
) -> None:
    message = public_exception_message(exc, code)

    assert message == expected
    assert "版本" not in message
    assert "4.1.1.4" not in message
    assert "objectId" not in message
    assert "secret-object" not in message


def test_tool_outcome_content_is_strict_json_for_non_finite_values() -> None:
    outcome = ToolOutcome()
    outcome.add_result("number", value=float("inf"))

    content = outcome.content()
    encoded = re.search("```json\\n(.*?)\\n```", content[0].text, re.S).group(1)
    payload = json.loads(encoded, parse_constant=lambda value: pytest.fail(value))

    assert payload["data"]["value"] is None


def test_selector_invalid_hints_include_syntax_recovery() -> None:
    hints = recovery_hints(ErrorCode.SELECTOR_INVALID)

    assert hints[0]["action"] == "check_selector_syntax"
    assert "XPath" in hints[0]["message"]


def test_failure_outcome_controls_error_state_and_default_error_content() -> None:
    response = ToolOutcome()
    response.add_error("explicit failure", ErrorCode.UNKNOWN_ERROR)
    content = response.content()
    payload = response.structured_content()
    assert response.is_error is True
    assert payload["ok"] is False
    assert payload["error"]["code"] == ErrorCode.UNKNOWN_ERROR.value
    assert "explicit failure" in content[1].text


def test_tool_result_output_schema_validates_real_payloads() -> None:
    schema = tool_result_output_schema("page_close")
    validate(
        ToolResult.success("Successfully closed browser", closed=True).to_dict(), schema
    )
    validate(
        ToolResult.failure(
            ErrorCode.MCP_ARGUMENT_INVALID,
            "Input validation error",
            tool_name="page_close",
        ).to_dict(),
        schema,
    )
    validate(
        {
            "ok": False,
            "message": "Generic failure with diagnostic data",
            "error": {
                "code": ErrorCode.UNKNOWN_ERROR.value,
                "message": "Generic failure with diagnostic data",
            },
            "data": {"unrestricted": {"nested": [1, True, None]}},
        },
        schema,
    )
    with pytest.raises(ValidationError):
        validate(
            {
                "ok": True,
                "message": "Successfully closed browser",
                "data": {"closed": True},
                "unexpected": True,
            },
            schema,
        )


def test_page_understanding_output_schemas_validate_success_payloads() -> None:
    snapshot_payload = ToolResult.success(
        "Captured page snapshot",
        tab_id="t0",
        url="https://example.test/catalog",
        title="Catalog",
        text_excerpt="Alpha Beta",
        headings=[],
        links=[],
        buttons=[],
        inputs=[],
        forms=[],
        counts={"headings": 0},
        truncated={"text": False, "elements": False, "returned_elements": 0},
        limits={"max_elements": 50, "max_text_chars": 4000},
        meta={"approx_tokens": 10, "json_chars": 35, "truncated": False},
    ).to_dict()
    find_all_payload = ToolResult.success(
        "Found 1 of 1 elements: .card",
        tab_id="t0",
        selector=".card",
        locator="css:.card",
        selector_strategy="css",
        selector_normalized=True,
        count=1,
        returned=1,
        limit=20,
        truncated=False,
        elements=[
            {
                "index": 0,
                "tag": "article",
                "text": "Alpha",
                "selector": "#alpha",
                "attributes": {"id": "alpha"},
            }
        ],
        meta={"approx_tokens": 10, "json_chars": 35, "truncated": False},
    ).to_dict()
    validate(snapshot_payload, tool_result_output_schema("page_snapshot"))
    validate(find_all_payload, tool_result_output_schema("element_find_all"))


def test_0_5_5_output_schemas_validate_new_capability_payloads() -> None:
    upload_payload = ToolResult.success(
        "Uploaded 1 file",
        tab_id="t0",
        selector="#upload",
        locator="css:#upload",
        selector_strategy="css",
        selector_normalized=True,
        uploaded=True,
        file_count=1,
        filenames=["fixture.txt"],
    ).to_dict()
    frame_payload = ToolResult.success(
        "Captured frame snapshot",
        tab_id="t0",
        frame={
            "index": 0,
            "selector": "#fixture-frame",
            "id": "fixture-frame",
            "name": "fixture-frame",
            "title": "Frame",
            "url": "https://example.test/frame",
            "boundary": "cross_origin",
            "document_access": "readable",
            "outer": {
                "displayed": True,
                "enabled": True,
                "alive": True,
                "clickable": True,
                "checked": False,
                "selected": False,
                "in_viewport": True,
                "whole_in_viewport": True,
                "covered": False,
                "covering_backend_node_id": None,
                "rect": {
                    "location": {"x": 10.0, "y": 20.0},
                    "size": {"width": 300.0, "height": 65.0},
                    "midpoint": {"x": 160.0, "y": 52.5},
                    "click_point": {"x": 42.0, "y": 52.0},
                    "viewport_location": {"x": 10.0, "y": 20.0},
                    "viewport_midpoint": {"x": 160.0, "y": 52.5},
                    "viewport_click_point": {"x": 42.0, "y": 52.0},
                    "coordinate_space": "target_document",
                    "viewport_coordinate_space": "top_level_viewport",
                },
                "presentation": {
                    "display": "inline",
                    "visibility": "visible",
                    "opacity": 1.0,
                    "pointer_events": "auto",
                    "transform": "none",
                    "transform_style": "flat",
                    "perspective": "none",
                    "transformed": False,
                    "ancestor_3d": False,
                    "three_dimensional": False,
                    "coordinate_actionability": "ready",
                },
            },
        },
        url="https://example.test/frame",
        title="Frame",
        text_excerpt="Frame text",
        headings=[],
        links=[],
        buttons=[],
        inputs=[],
        forms=[],
        counts={},
        truncated={"text": False, "elements": False, "returned_elements": 0},
        limits={"max_elements": 20, "max_text_chars": 1000},
        meta={"approx_tokens": 10, "json_chars": 35, "truncated": False},
    ).to_dict()
    storage_payload = ToolResult.success(
        "Read local storage",
        tab_id="t0",
        area="local",
        key="",
        include_values=True,
        count=1,
        items={"mode": "dark"},
    ).to_dict()
    validate(upload_payload, tool_result_output_schema("element_upload_file"))
    validate(frame_payload, tool_result_output_schema("frame_snapshot"))
    validate(storage_payload, tool_result_output_schema("storage_get"))


def test_page_dialog_respond_output_schema_validates_redacted_receipt() -> None:
    receipt = {
        "schema_version": "1",
        "action_id": "action-000003",
        "task_id": "task-000001",
        "operation_key": "dialog-response-action-000003",
        "request_fingerprint": "d" * 64,
        "kind": "page_dialog_respond",
        "side_effect": "dialog_response",
        "status": "success",
        "started_at": "2026-07-17T00:00:00Z",
        "finished_at": "2026-07-17T00:00:01Z",
        "tab_id": "t0",
        "target_fingerprint": "e" * 64,
        "artifact_ids": [],
        "error_code": None,
        "redacted": True,
    }
    payload = ToolResult.success(
        "Handled pending prompt dialog with action accept",
        tab_id="t0",
        dialog_type="prompt",
        action="accept",
        handled=True,
        dialog_message={"present": True, "length": 14, "redacted": True},
        prompt={"provided": True, "length": 17, "redacted": True},
        final_url="https://example.test/dialog",
        receipt=receipt,
    ).to_dict()

    schema = tool_result_output_schema("page_dialog_respond")
    validate(payload, schema)
    success_data = schema["oneOf"][0]["properties"]["data"]
    assert success_data["title"] == "PageDialogRespondData"
    assert {
        "dialog_type",
        "action",
        "handled",
        "dialog_message",
        "prompt",
        "final_url",
        "receipt",
    } <= set(success_data["required"])
    assert "message" not in payload["data"]
    assert "prompt_text" not in payload["data"]
    payload["data"]["dialog_message"]["redacted"] = False
    with pytest.raises(ValidationError):
        validate(payload, schema)


def test_click_and_download_output_schema_validates_artifact_receipt_link() -> None:
    receipt = {
        "schema_version": "1",
        "action_id": "action-000004",
        "task_id": "task-000001",
        "operation_key": "download-report-1",
        "request_fingerprint": "f" * 64,
        "kind": "element_click_and_download",
        "side_effect": "external_download",
        "status": "success",
        "started_at": "2026-07-17T00:00:00Z",
        "finished_at": "2026-07-17T00:00:01Z",
        "tab_id": "t0",
        "target_fingerprint": "a" * 64,
        "artifact_ids": ["artifact-000001"],
        "error_code": None,
        "redacted": True,
    }
    artifact = {
        "schema_version": "1",
        "artifact_id": "artifact-000001",
        "task_id": "task-000001",
        "producing_action_id": "action-000004",
        "kind": "download",
        "filename": "fixture-report.csv",
        "mime_type": "text/csv",
        "size_bytes": 55,
        "sha256": "b" * 64,
        "safe_relative_path": ("task-000001/action-000004/fixture-report.csv"),
        "source_url": "https://example.test/report.csv",
        "created_at": "2026-07-17T00:00:01Z",
        "status": "complete",
        "redacted": False,
    }
    payload = ToolResult.success(
        "Downloaded one integrity-checked artifact",
        tab_id="t0",
        status="success",
        operation_key="download-report-1",
        selector="#download",
        locator="css:#download",
        selector_strategy="css",
        selector_normalized=True,
        artifact=artifact,
        receipt=receipt,
    ).to_dict()

    schema = tool_result_output_schema("element_click_and_download")
    validate(payload, schema)
    data_schema = schema["oneOf"][0]["properties"]["data"]
    assert data_schema["title"] == "ElementClickAndDownloadData"
    assert len(data_schema["oneOf"]) == 4
    assert receipt["artifact_ids"] == [artifact["artifact_id"]]
    assert artifact["producing_action_id"] == receipt["action_id"]
    payload["data"]["artifact"]["safe_relative_path"] = "/tmp/fixture-report.csv"
    with pytest.raises(ValidationError):
        validate(payload, schema)
    payload["data"]["artifact"]["safe_relative_path"] = (
        "task-000001/action-000004/fixture-report.csv"
    )
    payload["data"]["artifact"]["source_url"] = "file:///Users/private/report.csv"
    with pytest.raises(ValidationError):
        validate(payload, schema)


def test_click_and_download_output_schema_accepts_redacted_keyboard_trigger() -> None:
    payload = _click_and_download_error_payload()
    data = payload["data"]
    assert isinstance(data, dict)
    for field in (
        "selector",
        "locator",
        "selector_strategy",
        "selector_normalized",
    ):
        data.pop(field)
    data["trigger"] = {
        "kind": "keyboard",
        "keys": {"provided": True, "length": 1, "redacted": True},
        "interval": 0,
    }

    validate(payload, tool_result_output_schema("element_click_and_download"))


@pytest.mark.parametrize("target_shape", ["missing", "mixed"])
def test_click_and_download_output_schema_requires_exactly_one_target_shape(
    target_shape: str,
) -> None:
    payload = _click_and_download_error_payload()
    data = payload["data"]
    assert isinstance(data, dict)
    if target_shape == "missing":
        for field in (
            "selector",
            "locator",
            "selector_strategy",
            "selector_normalized",
        ):
            data.pop(field)
    else:
        data["trigger"] = {
            "kind": "coordinate",
            "x": 10,
            "y": 20,
            "profile": "direct",
            "delay_before_press_ms": 0,
        }

    with pytest.raises(ValidationError):
        validate(payload, tool_result_output_schema("element_click_and_download"))


def _click_and_download_error_payload() -> dict[str, object]:
    return {
        "ok": False,
        "message": "Download failed",
        "error": {
            "code": ErrorCode.UNKNOWN_ERROR.value,
            "message": "Download failed",
            "details": {},
        },
        "data": {
            "tab_id": "t0",
            "status": "failed",
            "operation_key": "download-report-1",
            "selector": "#download",
            "locator": "css:#download",
            "selector_strategy": "css",
            "selector_normalized": True,
            "artifact": None,
            "receipt": {
                "schema_version": "1",
                "action_id": "action-000004",
                "task_id": "task-000001",
                "operation_key": "download-report-1",
                "request_fingerprint": "f" * 64,
                "kind": "element_click_and_download",
                "side_effect": "external_download",
                "status": "failed",
                "started_at": "2026-07-17T00:00:00Z",
                "finished_at": "2026-07-17T00:00:01Z",
                "tab_id": "t0",
                "target_fingerprint": "a" * 64,
                "artifact_ids": [],
                "error_code": "DOWNLOAD_FAILED",
                "redacted": True,
            },
        },
    }


def test_click_and_download_output_schema_validates_error_data() -> None:
    validate(
        _click_and_download_error_payload(),
        tool_result_output_schema("element_click_and_download"),
    )


@pytest.mark.parametrize(
    "invalid_case",
    ["failed_with_artifact", "status_mismatch", "nonempty_artifact_ids"],
)
def test_click_and_download_output_schema_rejects_invalid_error_data(
    invalid_case: str,
) -> None:
    payload = _click_and_download_error_payload()
    data = payload["data"]
    assert isinstance(data, dict)
    receipt = data["receipt"]
    assert isinstance(receipt, dict)

    if invalid_case == "failed_with_artifact":
        data["artifact"] = {
            "schema_version": "1",
            "artifact_id": "artifact-000001",
            "task_id": "task-000001",
            "producing_action_id": "action-000004",
            "kind": "download",
            "filename": "fixture-report.csv",
            "mime_type": "text/csv",
            "size_bytes": 55,
            "sha256": "b" * 64,
            "safe_relative_path": "task-000001/action-000004/fixture-report.csv",
            "source_url": "https://example.test/report.csv",
            "created_at": "2026-07-17T00:00:01Z",
            "status": "complete",
            "redacted": False,
        }
    elif invalid_case == "status_mismatch":
        receipt["status"] = "validation_failed"
    else:
        receipt["artifact_ids"] = ["artifact-000001"]

    with pytest.raises(ValidationError):
        validate(payload, tool_result_output_schema("element_click_and_download"))


@pytest.mark.parametrize(
    ("data_status", "receipt_status", "artifact_present", "artifact_ids"),
    [
        ("success", "success", False, ["artifact-000001"]),
        ("success", "failed", True, ["artifact-000001"]),
        ("failed", "failed", True, []),
        ("validation_failed", "failed", False, []),
        ("indeterminate", "indeterminate", False, ["artifact-000001"]),
    ],
)
def test_click_and_download_output_schema_rejects_contradictory_shapes(
    data_status: str,
    receipt_status: str,
    artifact_present: bool,
    artifact_ids: list[str],
) -> None:
    receipt = {
        "schema_version": "1",
        "action_id": "action-000004",
        "task_id": "task-000001",
        "operation_key": "download-report-1",
        "request_fingerprint": "f" * 64,
        "kind": "element_click_and_download",
        "side_effect": "external_download",
        "status": receipt_status,
        "started_at": "2026-07-17T00:00:00Z",
        "finished_at": "2026-07-17T00:00:01Z",
        "tab_id": "t0",
        "target_fingerprint": "a" * 64,
        "artifact_ids": artifact_ids,
        "error_code": None,
        "redacted": True,
    }
    artifact = {
        "schema_version": "1",
        "artifact_id": "artifact-000001",
        "task_id": "task-000001",
        "producing_action_id": "action-000004",
        "kind": "download",
        "filename": "fixture-report.csv",
        "mime_type": "text/csv",
        "size_bytes": 55,
        "sha256": "b" * 64,
        "safe_relative_path": "task-000001/action-000004/fixture-report.csv",
        "source_url": "https://example.test/report.csv",
        "created_at": "2026-07-17T00:00:01Z",
        "status": "complete",
        "redacted": False,
    }
    payload = ToolResult.success(
        "Download result",
        tab_id="t0",
        status=data_status,
        operation_key="download-report-1",
        selector="#download",
        locator="css:#download",
        selector_strategy="css",
        selector_normalized=True,
        artifact=artifact if artifact_present else None,
        receipt=receipt,
    ).to_dict()

    with pytest.raises(ValidationError):
        validate(payload, tool_result_output_schema("element_click_and_download"))


@pytest.mark.parametrize(
    ("receipt_field", "value"),
    [
        ("kind", "page_dialog_respond"),
        ("side_effect", "dialog_response"),
    ],
)
def test_click_and_download_output_schema_rejects_wrong_receipt_contract(
    receipt_field: str, value: str
) -> None:
    schema = tool_result_output_schema("element_click_and_download")
    receipt = {
        "schema_version": "1",
        "action_id": "action-000004",
        "task_id": "task-000001",
        "operation_key": "download-report-1",
        "request_fingerprint": "f" * 64,
        "kind": "element_click_and_download",
        "side_effect": "external_download",
        "status": "success",
        "started_at": "2026-07-17T00:00:00Z",
        "finished_at": "2026-07-17T00:00:01Z",
        "tab_id": "t0",
        "target_fingerprint": "a" * 64,
        "artifact_ids": ["artifact-000001"],
        "error_code": None,
        "redacted": True,
    }
    receipt[receipt_field] = value
    receipt_schema = {
        "$ref": "#/$defs/ElementClickAndDownloadSuccessReceipt",
        "$defs": schema["$defs"],
    }

    with pytest.raises(ValidationError):
        validate(receipt, receipt_schema)


def test_observable_action_output_schemas_validate_success_payloads() -> None:
    changes = {
        "url_before": "https://example.test/start",
        "url_after": "https://example.test/done",
        "url_changed": True,
        "title_before": "Start",
        "title_after": "Done",
        "title_changed": True,
        "ready_state": "complete",
        "counts_before": {"buttons": 1},
        "counts_after": {"buttons": 2},
        "counts_delta": {"buttons": 1},
        "appeared_texts": ["Saved"],
        "removed_texts": ["Loading"],
        "active_element": None,
        "console_errors_added": 1,
        "console_warnings_added": 0,
        "new_console_messages": [
            {
                "index": 2,
                "level": "error",
                "text": "save failed",
                "url": "https://example.test/done",
                "line": 12,
                "column": 4,
                "source": "console-api",
            }
        ],
    }
    observe_payload = ToolResult.success(
        "Observed page state",
        tab_id="t0",
        url="https://example.test",
        title="Observable",
        ready_state="complete",
        counts={"buttons": 1, "inputs": 1},
        text_samples=["Ready"],
        active_element=None,
        console={
            "available": True,
            "listening": True,
            "count": 1,
            "total": 1,
            "next_cursor": 0,
            "error_count": 0,
            "warning_count": 0,
            "recent": [
                {
                    "index": 0,
                    "level": "log",
                    "text": "ready",
                    "url": "https://example.test",
                    "line": 1,
                    "column": 1,
                    "source": "console-api",
                }
            ],
        },
        limits={"max_texts": 20, "max_text_chars": 160},
    ).to_dict()
    console_payload = ToolResult.success(
        "Read 1 console log",
        tab_id="t0",
        available=True,
        listening=True,
        count=1,
        total=1,
        next_cursor=0,
        logs=[
            {
                "index": 0,
                "level": "log",
                "text": "ready",
                "url": "https://example.test",
                "line": 1,
                "column": 1,
                "source": "console-api",
            }
        ],
    ).to_dict()
    evaluate_payload = ToolResult.success(
        "Evaluated JavaScript",
        tab_id="t0",
        result={"status": "ready"},
        result_type="object",
        truncated=False,
        original_json_chars=18,
        max_chars=4000,
    ).to_dict()
    navigate_payload = ToolResult.success(
        "Successfully navigated",
        url="https://example.test/start",
        final_url="https://example.test/done",
        new_tab=False,
        tab_id="t0",
        changes=changes,
    ).to_dict()
    click_payload = ToolResult.success(
        "Successfully clicked element",
        tab_id="t0",
        selector="#save",
        locator="css:#save",
        selector_strategy="css",
        selector_normalized=True,
        url="https://example.test/done",
        button="left",
        click_count=1,
        changes=changes,
    ).to_dict()
    type_payload = ToolResult.success(
        "Successfully typed text",
        tab_id="t0",
        selector="#name",
        locator="css:#name",
        selector_strategy="css",
        selector_normalized=True,
        typed=True,
        cleared=True,
        changes=changes,
    ).to_dict()
    wait_payload = ToolResult.success(
        "Condition matched",
        tab_id="t0",
        condition="clickable",
        selector="#save",
        value="",
        name="",
        matched=True,
        timeout=2.0,
        elapsed_ms=100,
        state={"visible": True, "disabled": False},
    ).to_dict()
    validate(observe_payload, tool_result_output_schema("page_observe"))
    validate(console_payload, tool_result_output_schema("page_console_logs"))
    validate(evaluate_payload, tool_result_output_schema("page_evaluate"))
    validate(navigate_payload, tool_result_output_schema("page_navigate"))
    validate(click_payload, tool_result_output_schema("element_click"))
    validate(type_payload, tool_result_output_schema("element_type"))
    validate(wait_payload, tool_result_output_schema("wait_until"))


def test_network_schemas_validate_success_payloads() -> None:
    start_payload = ToolResult.success(
        "Started network listener",
        listening=True,
        filters={
            "targets": ["/api"],
            "is_regex": False,
            "method": "",
            "resource_type": "",
        },
        started_at="2026-07-07T00:00:00+00:00",
        tab_id="t0",
        cleared=True,
        listener_token="listener-1",
        state="listening",
        consumed_count=0,
        next_cursor=0,
        timing={"startup_ms": 3},
    ).to_dict()
    wait_payload = ToolResult.success(
        "Captured 1 network packet",
        tab_id="t0",
        listening=True,
        timed_out=False,
        count=1,
        limit=10,
        packets=[
            {
                "index": 0,
                "url": "https://example.test/api/data.json",
                "method": "GET",
                "resource_type": "Fetch",
                "status": 200,
                "mime_type": "application/json",
                "failed": False,
                "fail_error": "",
                "request_headers": {"authorization": "<redacted>"},
                "response_headers": {"content-type": "application/json"},
                "body_excerpt": '{"ok":true}',
                "body_truncated": False,
                "body_type": "json",
            }
        ],
        meta={"approx_tokens": 10, "json_chars": 35, "truncated": False},
        listener_token="listener-1",
        state="listening",
        consumed_count=1,
        next_cursor=1,
        timeout_ms=5000,
        elapsed_ms=40,
        remaining_timeout_ms=4960,
    ).to_dict()
    stop_payload = ToolResult.success(
        "Stopped network listener",
        tab_id="t0",
        listening=False,
        was_listening=True,
        cleared=True,
        listener_token="listener-1",
        state="stopped",
        consumed_count=1,
        next_cursor=1,
    ).to_dict()
    validate(start_payload, tool_result_output_schema("network_listen_start"))
    validate(wait_payload, tool_result_output_schema("network_listen_wait"))
    validate(stop_payload, tool_result_output_schema("network_listen_stop"))


def test_add_image_accepts_bytes_and_rejects_invalid_input() -> None:
    response = ToolOutcome()
    response.add_image(b"image-bytes", "image/png")
    images = [item for item in response.content() if item.type == "image"]
    assert images[0].data == base64.b64encode(b"image-bytes").decode()
    with pytest.raises(ValueError, match="Image data must be string or bytes"):
        response.add_image(object())


def test_screenshot_metadata_handles_non_inline_and_malformed_images(tmp_path) -> None:
    raw_png = base64.b64decode(ONE_PIXEL_PNG)
    png_path = tmp_path / "screen.png"
    png_path.write_bytes(raw_png)
    assert build_screenshot_metadata(raw_png, full_page=True)["width"] == 1
    assert build_screenshot_metadata(
        path=str(png_path), safe_relative_path="screen.png", inline=False
    ) == {
        "mime_type": "image/png",
        "inline": False,
        "safe_relative_path": "screen.png",
        "bytes": len(raw_png),
        "width": 1,
        "height": 1,
    }
    invalid_base64 = build_screenshot_metadata("not base64", full_page=False)
    assert invalid_base64 == {
        "mime_type": "image/png",
        "inline": True,
        "encoding": "base64",
        "full_page": False,
    }
    missing_file = build_screenshot_metadata(
        path=str(tmp_path / "missing.png"), safe_relative_path="missing.png"
    )
    assert missing_file == {
        "mime_type": "image/png",
        "safe_relative_path": "missing.png",
    }
    assert build_screenshot_metadata(b"short") == {
        "mime_type": "image/png",
        "inline": True,
        "encoding": "base64",
        "bytes": len(b"short"),
    }
    non_png = b"x" * 24
    assert build_screenshot_metadata(non_png)["bytes"] == len(non_png)
    assert "width" not in build_screenshot_metadata(non_png)
