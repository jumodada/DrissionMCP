"""0.7.7 contracts for browser-owned permissions, artifacts, uploads, and auth."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from drissionpage_mcp.browser.artifacts import (
    ArtifactFileValidationError,
    PageArtifactOperations,
    PageExportError,
    inspect_artifact_file,
)
from drissionpage_mcp.browser.auth import (
    HttpAuthError,
    HttpAuthOperations,
    _http_origin,
    _safe_origin,
)
from drissionpage_mcp.browser.file_chooser import (
    FileChooserError,
    FileChooserOperations,
)
from drissionpage_mcp.browser.permissions import (
    PermissionOperations,
    PermissionUnsupportedError,
    _origin_from_url,
)
from drissionpage_mcp.context import DrissionPageContext
from drissionpage_mcp.server import DrissionPageMCPServer
from drissionpage_mcp.tools import get_all_tools
from drissionpage_mcp.tools.base import ToolSpec

EXPECTED_077_TOOLS = (
    "browser_permission_get",
    "browser_permission_set",
    "browser_permissions_reset",
    "page_export_artifact",
    "element_click_and_upload",
    "page_navigate_with_http_auth",
)


def _tool(name: str) -> ToolSpec[Any, Any]:
    for tool in get_all_tools():
        if tool.name == name:
            return tool
    pytest.fail(f"0.7.7 tool {name!r} is not registered in the default tool surface")


def _json_payload(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _assert_secret_redacted(value: Any, *secrets: str) -> None:
    encoded = _json_payload(value)
    for secret in secrets:
        assert secret not in encoded


def test_077_browser_owned_tools_are_loaded_by_default() -> None:
    """0.7.7 adds six atomic tools without requiring a user-selected full profile."""

    tools = get_all_tools()
    names = [tool.name for tool in tools]

    assert len(tools) == 69
    assert len(set(names)) == 69
    assert set(EXPECTED_077_TOOLS).issubset(names)


def test_077_inputs_are_strict_and_bounded(tmp_path: Path) -> None:
    """New browser-owned tools reject extras, unsafe paths, secrets gaps, and wide waits."""

    upload_file = tmp_path / "upload.txt"
    upload_file.write_text("upload", encoding="utf-8")

    PermissionGetInput = _tool("browser_permission_get").input_model
    PermissionSetInput = _tool("browser_permission_set").input_model
    PermissionsResetInput = _tool("browser_permissions_reset").input_model
    ExportInput = _tool("page_export_artifact").input_model
    ClickUploadInput = _tool("element_click_and_upload").input_model
    HttpAuthInput = _tool("page_navigate_with_http_auth").input_model

    assert PermissionGetInput(permission="geolocation").permission == "geolocation"
    assert PermissionSetInput(
        permission="clipboard-read",
        setting="granted",
        origin="https://example.test",
    ).setting == "granted"
    assert PermissionsResetInput().model_dump() == {"tab_id": None}
    assert ExportInput(format="pdf", filename="report.pdf").format == "pdf"
    assert ClickUploadInput(
        selector="#file", paths=[str(upload_file)], timeout=5
    ).paths == [str(upload_file)]
    auth = HttpAuthInput(
        url="https://secure.example.test/private",
        username="agent",
        password="secret-token",
        timeout=5,
    )
    assert auth.username.get_secret_value() == "agent"

    invalid_payloads: tuple[tuple[type[Any], dict[str, Any]], ...] = (
        (PermissionGetInput, {"permission": "", "unknown": True}),
        (PermissionSetInput, {"permission": "geolocation", "setting": "allow"}),
        (PermissionsResetInput, {"unknown": True}),
        (ExportInput, {"format": "png"}),
        (ExportInput, {"format": "pdf", "filename": "../secret.pdf"}),
        (ExportInput, {"format": "mhtml", "operation_key": " "}),
        (ClickUploadInput, {"selector": "", "paths": [str(upload_file)]}),
        (ClickUploadInput, {"selector": "#file", "paths": []}),
        (ClickUploadInput, {"selector": "#file", "paths": [str(upload_file)], "timeout": 121}),
        (HttpAuthInput, {"url": "not-a-url", "username": "agent", "password": "secret"}),
        (HttpAuthInput, {"url": "https://example.test", "username": "", "password": "secret"}),
        (HttpAuthInput, {"url": "https://example.test", "username": "agent", "password": ""}),
        (HttpAuthInput, {"url": "https://example.test", "username": "agent", "password": "secret", "unknown": True}),
    )
    for model, payload in invalid_payloads:
        with pytest.raises(ValidationError):
            model.model_validate(payload)

    assert ExportInput(format="pdf", filename="report").filename == "report.pdf"
    pdf = ExportInput(
        format="pdf", paper_width=8.5, paper_height=11, page_ranges="1-2"
    )
    assert pdf.pdf_options()["paperWidth"] == 8.5
    assert pdf.pdf_options()["paperHeight"] == 11
    with pytest.raises(ValidationError):
        ExportInput(format="pdf", filename="report.mhtml")
    with pytest.raises(ValidationError):
        ExportInput(format="mhtml", landscape=True)


class _ExportPage:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.saved: list[tuple[Path, str, bool]] = []

    def save(
        self,
        path: str | Path | None = None,
        name: str | None = None,
        as_pdf: bool = False,
        **_: Any,
    ) -> Path:
        if path is None or name is None:
            raise AssertionError("page export must pass an explicit safe directory/name")
        directory = Path(path)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / name
        target.write_bytes(b"%PDF fixture" if as_pdf else b"MHTML fixture")
        self.saved.append((directory, name, as_pdf))
        if self.fail:
            raise OSError("disk write failed at /private/tmp/secret-export.pdf")
        return target


class _UploadChooser:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.cleaned = False

    async def click_and_upload(
        self, selector: Any, paths: list[str], *, timeout: float
    ) -> dict[str, Any]:
        self.calls.append({"selector": selector, "paths": paths, "timeout": timeout})
        self.cleaned = True
        return {
            "selector": selector,
            "locator": f"css:{selector}",
            "selector_strategy": "css",
            "selector_normalized": True,
            "uploaded": True,
            "file_count": len(paths),
            "filenames": [Path(path).name for path in paths],
        }


class _BrowserOwnedTab:
    def __init__(self, *, export_fail: bool = False) -> None:
        self.url = "https://example.test/current?token=private"
        self.mcp_tab_id = "t0"
        self.page = _ExportPage(fail=export_fail)
        self.file_chooser = _UploadChooser()


def _context_with_tab(tab: _BrowserOwnedTab) -> DrissionPageContext:
    context = DrissionPageContext()
    context._current_tab = tab  # type: ignore[assignment]
    return context


@pytest.mark.asyncio
async def test_page_export_artifact_records_page_export_receipt_and_replays(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Generated PDF/MHTML files are task artifacts with exact-once replay evidence."""

    monkeypatch.setenv("DP_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    tab = _BrowserOwnedTab()
    context = _context_with_tab(tab)
    tool = _tool("page_export_artifact")
    args = tool.input_model(
        format="pdf", filename="contract.pdf", operation_key="export-contract"
    )

    first = await tool.execute(context, args)
    replay = await tool.execute(context, args)
    conflict = await tool.execute(
        context,
        tool.input_model(
            format="pdf",
            filename="different.pdf",
            operation_key="export-contract",
        ),
    )

    assert first.is_error is False
    assert replay.structured_content()["data"] == first.structured_content()["data"]
    assert conflict.structured_content()["error"]["code"] == "OPERATION_KEY_CONFLICT"
    assert len(tab.page.saved) == 1
    data = first.structured_content()["data"]
    artifact = data["artifact"]
    receipt = data["receipt"]
    assert artifact["kind"] == "page_export"
    assert artifact["filename"] == "contract.pdf"
    assert artifact["producing_action_id"] == receipt["action_id"]
    assert artifact["artifact_id"] in receipt["artifact_ids"]
    assert receipt["side_effect"] == "artifact_write"
    assert receipt["status"] == "success"
    assert not Path(artifact["safe_relative_path"]).is_absolute()
    assert str(tmp_path) not in _json_payload(data)


@pytest.mark.asyncio
async def test_page_export_artifact_write_failure_cleans_up_without_path_leak(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Failed generated artifact writes release reservations and redact local paths."""

    monkeypatch.setenv("DP_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    context = _context_with_tab(_BrowserOwnedTab(export_fail=True))
    tool = _tool("page_export_artifact")

    args = tool.input_model(
        format="pdf", filename="contract.pdf", operation_key="export-fail"
    )
    outcome = await tool.execute(
        context,
        args,
    )
    replay = await tool.execute(context, args)

    assert outcome.is_error is True
    assert replay.is_error is True
    assert len(context.current_tab().page.saved) == 1
    assert context._artifact_reservations == set()
    assert list(context._artifacts.values()) == []
    _assert_secret_redacted(outcome.structured_content(), str(tmp_path), "/private/tmp")


@pytest.mark.asyncio
async def test_page_export_policy_denies_before_browser_or_artifact_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DP_MCP_ARTIFACT_ROOT", raising=False)
    context = DrissionPageContext()
    tool = _tool("page_export_artifact")

    outcome = await tool.execute(context, tool.input_model(format="mhtml"))

    assert outcome.structured_content()["error"]["code"] == "POLICY_DENIED"
    assert context._artifact_reservations == set()
    assert context._operation_receipts == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback_result", [b"%PDF fallback", "not-bytes"])
async def test_page_artifact_pdf_save_uses_bounded_drissionpage_fallback(
    tmp_path: Path, fallback_result: Any
) -> None:
    calls: list[dict[str, Any]] = []

    def save(**kwargs: Any) -> Any:
        calls.append(kwargs)
        if kwargs.get("path") is not None:
            raise ValueError("binary mode doesn't take a newline argument")
        return fallback_result

    operations = PageArtifactOperations(SimpleNamespace(page=SimpleNamespace(save=save)))  # type: ignore[arg-type]
    if isinstance(fallback_result, bytes):
        output = await operations.save(tmp_path, "fallback.pdf", "pdf", {})
        assert output.read_bytes() == fallback_result
        assert len(calls) == 2
    else:
        with pytest.raises(PageExportError) as exc_info:
            await operations.save(tmp_path, "fallback.pdf", "pdf", {})
        assert exc_info.value.reason_code == "DRISSIONPAGE_PDF_FALLBACK_FAILED"


@pytest.mark.asyncio
@pytest.mark.parametrize("save", [None, lambda **_: (_ for _ in ()).throw(OSError())])
async def test_page_artifact_save_reports_missing_or_failed_drissionpage_api(
    tmp_path: Path, save: Any
) -> None:
    operations = PageArtifactOperations(SimpleNamespace(page=SimpleNamespace(save=save)))  # type: ignore[arg-type]

    with pytest.raises(PageExportError) as exc_info:
        await operations.save(tmp_path, "failed.mhtml", "mhtml", {})

    assert exc_info.value.reason_code in {
        "DRISSIONPAGE_SAVE_UNAVAILABLE",
        "DRISSIONPAGE_SAVE_FAILED",
    }


def test_artifact_integrity_rejects_leaf_inode_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "artifact.pdf"
    path.write_bytes(b"%PDF stable")
    real_stat = os.stat

    def mismatched_stat(
        candidate: Any, *args: Any, **kwargs: Any
    ) -> Any:
        result = real_stat(candidate, *args, **kwargs)
        if Path(candidate) == path and kwargs.get("follow_symlinks") is False:
            return SimpleNamespace(
                st_mode=result.st_mode,
                st_dev=result.st_dev,
                st_ino=result.st_ino + 1,
            )
        return result

    monkeypatch.setattr(os, "stat", mismatched_stat)
    with pytest.raises(ArtifactFileValidationError, match="changed"):
        inspect_artifact_file(path, approved_root=tmp_path)


def test_artifact_integrity_rejects_leaf_swap_after_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "artifact.pdf"
    original = tmp_path / "artifact.original"
    outside = tmp_path / "outside-secret.pdf"
    path.write_bytes(b"%PDF stable")
    outside.write_bytes(b"%PDF outside secret")
    real_fdopen = os.fdopen
    swapped = False

    class SwappingReader:
        def __init__(self, stream: Any) -> None:
            self._stream = stream

        def __enter__(self) -> SwappingReader:
            self._stream.__enter__()
            return self

        def __exit__(self, *args: object) -> object:
            return self._stream.__exit__(*args)

        def read(self, size: int = -1) -> bytes:
            nonlocal swapped
            chunk = self._stream.read(size)
            if chunk and not swapped:
                swapped = True
                path.rename(original)
                path.symlink_to(outside)
            return chunk

    def swapping_fdopen(
        descriptor: int, mode: str, closefd: bool = True
    ) -> SwappingReader:
        return SwappingReader(real_fdopen(descriptor, mode, closefd=closefd))

    monkeypatch.setattr(os, "fdopen", swapping_fdopen)
    with pytest.raises(ArtifactFileValidationError, match="changed"):
        inspect_artifact_file(path, approved_root=tmp_path)

    assert swapped is True
    assert outside.read_bytes() == b"%PDF outside secret"


class _BlockingExporter:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cleaned: list[Path | None] = []
        self.save_calls = 0

    async def save(
        self,
        directory: Path,
        filename: str,
        _export_format: str,
        _pdf_options: dict[str, Any],
    ) -> Path:
        self.save_calls += 1
        self.started.set()
        await self.release.wait()
        output = directory / filename
        output.write_bytes(b"%PDF cancelled")
        return output

    async def cleanup(self, directory: Path | None) -> None:
        self.cleaned.append(directory)
        if directory is not None:
            await asyncio.to_thread(shutil.rmtree, directory, True)


@pytest.mark.asyncio
async def test_page_export_cancellation_drains_write_then_records_indeterminate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DP_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    exporter = _BlockingExporter()
    tab = _BrowserOwnedTab()
    tab.artifacts = exporter  # type: ignore[attr-defined]
    context = _context_with_tab(tab)
    tool = _tool("page_export_artifact")
    args = tool.input_model(
        format="pdf", filename="cancelled.pdf", operation_key="export-cancel"
    )
    task = asyncio.create_task(
        tool.execute(context, args)
    )
    await exporter.started.wait()

    task.cancel()
    exporter.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert context._artifact_reservations == set()
    receipt = next(iter(context._operation_receipts.values()))
    assert receipt.status == "indeterminate"
    assert exporter.cleaned and exporter.cleaned[0] is not None
    frozen = context.operation_result("export-cancel")
    assert frozen is not None
    assert frozen["status"] == "indeterminate"
    assert frozen["artifact"] is None
    assert frozen["receipt"] == receipt.model_dump(mode="json")

    replay = await tool.execute(context, args)
    assert replay.is_error is True
    assert replay.structured_content()["error"]["code"] == "TIMEOUT"
    assert replay.structured_content()["data"] == frozen
    assert exporter.save_calls == 1


@pytest.mark.asyncio
async def test_page_export_concurrent_key_reports_in_flight_without_second_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DP_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    exporter = _BlockingExporter()
    tab = _BrowserOwnedTab()
    tab.artifacts = exporter  # type: ignore[attr-defined]
    context = _context_with_tab(tab)
    tool = _tool("page_export_artifact")
    args = tool.input_model(
        format="pdf", filename="concurrent.pdf", operation_key="export-concurrent"
    )
    first = asyncio.create_task(tool.execute(context, args))
    await exporter.started.wait()

    duplicate = await tool.execute(context, args)
    exporter.release.set()
    completed = await first

    assert duplicate.structured_content()["error"]["code"] == "OPERATION_IN_FLIGHT"
    assert completed.is_error is False
    assert len(exporter.cleaned) == 0


@pytest.mark.asyncio
async def test_page_export_artifact_rejects_symlink_leaf_without_reading_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Generated artifacts never follow a leaf symlink outside the approved root."""

    artifact_root = tmp_path / "artifacts"
    outside = tmp_path / "outside-secret.pdf"
    outside.write_bytes(b"%PDF outside secret must never be hashed")
    monkeypatch.setenv("DP_MCP_ARTIFACT_ROOT", str(artifact_root))
    context = _context_with_tab(_BrowserOwnedTab())
    tool = _tool("page_export_artifact")
    real_open = os.open

    def swapping_open(
        path: object, flags: int, *args: object, **kwargs: object
    ) -> int:
        candidate = Path(path) if isinstance(path, (str, os.PathLike)) else None
        if candidate is not None and candidate.name == "contract.pdf":
            candidate.unlink()
            candidate.symlink_to(outside)
        return real_open(path, flags, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", swapping_open)
    outcome = await tool.execute(
        context,
        tool.input_model(
            format="pdf", filename="contract.pdf", operation_key="export-symlink"
        ),
    )

    assert outcome.is_error is True
    assert list(context._artifacts.values()) == []
    assert outside.read_bytes() == b"%PDF outside secret must never be hashed"
    assert not artifact_root.exists() or not list(artifact_root.rglob("contract.pdf"))


@pytest.mark.asyncio
async def test_page_export_artifact_rejects_file_changed_during_integrity_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A generated file that changes while hashing is never committed."""

    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("DP_MCP_ARTIFACT_ROOT", str(artifact_root))
    context = _context_with_tab(_BrowserOwnedTab())
    tool = _tool("page_export_artifact")
    real_fdopen = os.fdopen
    mutated = False

    class MutatingReader:
        def __init__(self, stream: Any) -> None:
            self._stream = stream

        def __enter__(self) -> MutatingReader:
            self._stream.__enter__()
            return self

        def __exit__(self, *args: object) -> object:
            return self._stream.__exit__(*args)

        def read(self, size: int = -1) -> bytes:
            nonlocal mutated
            chunk = self._stream.read(size)
            if chunk and not mutated:
                mutated = True
                next(artifact_root.rglob("contract.pdf")).write_bytes(
                    chunk + b"mutated"
                )
            return chunk

    def mutating_fdopen(
        descriptor: int, mode: str, closefd: bool = True
    ) -> MutatingReader:
        return MutatingReader(real_fdopen(descriptor, mode, closefd=closefd))

    monkeypatch.setattr(os, "fdopen", mutating_fdopen)
    outcome = await tool.execute(
        context,
        tool.input_model(
            format="pdf", filename="contract.pdf", operation_key="export-mutated"
        ),
    )

    assert outcome.is_error is True
    assert mutated is True
    assert list(context._artifacts.values()) == []
    assert not artifact_root.exists() or not list(artifact_root.rglob("contract.pdf"))


@pytest.mark.asyncio
async def test_element_click_and_upload_uses_browser_file_chooser_and_redacts_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The file chooser workflow is browser-owned and never asks for manual OS input."""

    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    upload_file = upload_root / "fixture.txt"
    upload_file.write_text("upload", encoding="utf-8")
    monkeypatch.setenv("DP_MCP_UPLOAD_ROOT", str(upload_root))
    tab = _BrowserOwnedTab()
    context = _context_with_tab(tab)
    tool = _tool("element_click_and_upload")

    outcome = await tool.execute(
        context,
        tool.input_model(selector="#picker", paths=[str(upload_file)], timeout=5),
    )

    assert outcome.is_error is False
    data = outcome.structured_content()["data"]
    assert data["uploaded"] is True
    assert data["filenames"] == ["fixture.txt"]
    assert tab.file_chooser.cleaned is True
    _assert_secret_redacted(data, str(upload_file), str(upload_root))


class _AuthContext(DrissionPageContext):
    def __init__(self) -> None:
        super().__init__()
        self.cleaned = False
        self.calls: list[dict[str, Any]] = []

    async def navigate_with_http_auth(
        self,
        *,
        url: str,
        username: str,
        password: str,
        realm: str | None,
        timeout: float,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "url": url,
                "username": username,
                "password": password,
                "realm": realm,
                "timeout": timeout,
            }
        )
        self.cleaned = True
        return {
            "url": url,
            "final_url": "https://secure.example.test/private",
            "authenticated": True,
            "tab_id": "isolated-auth-tab",
            "realm": realm,
        }


@pytest.mark.asyncio
async def test_http_auth_navigation_redacts_credentials_and_cleans_handlers() -> None:
    """HTTP auth uses a scoped browser flow and never exposes credentials publicly."""

    context = _AuthContext()
    tool = _tool("page_navigate_with_http_auth")

    outcome = await tool.execute(
        context,
        tool.input_model(
            url="https://secure.example.test/private",
            username="agent",
            password="secret-token",
            realm="staging",
            timeout=5,
        ),
    )

    assert outcome.is_error is False
    assert context.cleaned is True
    assert context.calls[0]["password"] == "secret-token"
    payload = outcome.structured_content()
    assert payload["data"]["authenticated"] is True
    _assert_secret_redacted(payload, "secret-token", "agent:secret-token")


class _CallbackDriver:
    def __init__(self) -> None:
        self.event_handlers: dict[str, Any] = {}
        self.callbacks: dict[str, Any] = {}

    def set_callback(self, name: str, callback: Any) -> None:
        if callback is None:
            self.event_handlers.pop(name, None)
            self.callbacks.pop(name, None)
        else:
            self.event_handlers[name] = callback
            self.callbacks[name] = callback


class _AuthPage:
    def __init__(self, *, fail_command: str | None = None) -> None:
        self.driver = _CallbackDriver()
        self.fail_command = fail_command
        self.commands: list[tuple[str, dict[str, Any]]] = []

    def run_cdp(self, command: str, **kwargs: Any) -> dict[str, Any]:
        self.commands.append((command, kwargs))
        if command == self.fail_command:
            raise RuntimeError("private CDP failure")
        return {}

    def get(self, url: str, *, retry: int, timeout: float) -> bool:
        auth = self.driver.callbacks["Fetch.authRequired"]
        paused = self.driver.callbacks["Fetch.requestPaused"]
        request_url = url.split("#", 1)[0]
        challenge = {"realm": "secure"}
        event = {
            "requestId": "request-1",
            "request": {"url": request_url},
            "authChallenge": challenge,
        }
        auth(**event)
        auth(**event)
        auth(
            requestId="request-2",
            request={"url": "https://outside.example.test/private"},
            authChallenge=challenge,
        )
        paused(
            requestId="request-1",
            request={"url": request_url},
            responseStatusCode=200,
        )
        return True


@pytest.mark.asyncio
async def test_http_auth_browser_lifetime_scopes_credentials_and_cleans_callbacks() -> None:
    page = _AuthPage()
    tab = SimpleNamespace(
        page=page,
        url="https://secure.example.test/private?session=redacted",
        mcp_tab_id="t-auth",
    )

    result = await HttpAuthOperations(tab).navigate(  # type: ignore[arg-type]
        url="https://secure.example.test/private?token=redacted#fragment",
        username="agent",
        password="secret-token",
        realm="secure",
        timeout=2,
    )

    responses = [
        kwargs["authChallengeResponse"]
        for command, kwargs in page.commands
        if command == "Fetch.continueWithAuth"
    ]
    assert [response["response"] for response in responses] == [
        "ProvideCredentials",
        "CancelAuth",
        "CancelAuth",
    ]
    assert responses[0]["username"] == "agent"
    assert responses[0]["password"] == "secret-token"
    assert result["authenticated"] is True
    assert result["challenge_count"] == 3
    assert result["response_status"] == 200
    assert result["handlers_cleaned"] is True
    assert page.driver.callbacks == {}
    _assert_secret_redacted(result, "secret-token", "token=redacted", "session=redacted")


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["callback", "cdp", "navigate"])
async def test_http_auth_rejects_missing_fetch_capability(missing: str) -> None:
    driver = SimpleNamespace(set_callback=lambda *_: None, event_handlers={})
    page = SimpleNamespace(
        driver=driver,
        run_cdp=lambda *_args, **_kwargs: {},
        get=lambda *_args, **_kwargs: True,
    )
    if missing == "callback":
        driver.set_callback = None
    elif missing == "cdp":
        page.run_cdp = None
    else:
        page.get = None
    tab = SimpleNamespace(page=page, url="https://example.test", mcp_tab_id="t0")

    with pytest.raises(HttpAuthError) as exc_info:
        await HttpAuthOperations(tab).navigate(  # type: ignore[arg-type]
            url="https://example.test",
            username="agent",
            password="secret",
            realm=None,
            timeout=1,
        )

    assert exc_info.value.reason_code == "FETCH_AUTH_API_UNAVAILABLE"


@pytest.mark.asyncio
async def test_http_auth_rejects_active_handlers_and_callback_failures() -> None:
    active = _AuthPage()
    active.driver.event_handlers["Fetch.requestPaused"] = object()
    active_tab = SimpleNamespace(
        page=active, url="https://example.test", mcp_tab_id="t0"
    )
    with pytest.raises(HttpAuthError) as active_error:
        await HttpAuthOperations(active_tab).navigate(  # type: ignore[arg-type]
            url="https://example.test",
            username="agent",
            password="secret",
            realm=None,
            timeout=1,
        )
    assert active_error.value.reason_code == "FETCH_HANDLER_ALREADY_ACTIVE"

    failing = _AuthPage(fail_command="Fetch.continueWithAuth")
    failing_tab = SimpleNamespace(
        page=failing, url="https://example.test", mcp_tab_id="t0"
    )
    with pytest.raises(HttpAuthError) as callback_error:
        await HttpAuthOperations(failing_tab).navigate(  # type: ignore[arg-type]
            url="https://example.test",
            username="agent",
            password="secret",
            realm="secure",
            timeout=1,
        )
    assert callback_error.value.reason_code == "CONTINUE_AUTH_FAILED"
    assert failing.driver.callbacks == {}

    paused_failure = _AuthPage(fail_command="Fetch.continueRequest")
    paused_tab = SimpleNamespace(
        page=paused_failure, url="https://example.test", mcp_tab_id="t0"
    )
    with pytest.raises(HttpAuthError) as paused_error:
        await HttpAuthOperations(paused_tab).navigate(  # type: ignore[arg-type]
            url="https://example.test",
            username="agent",
            password="secret",
            realm="secure",
            timeout=1,
        )
    assert paused_error.value.reason_code == "CONTINUE_REQUEST_FAILED"


@pytest.mark.asyncio
async def test_http_auth_reports_fetch_cleanup_failure() -> None:
    page = _AuthPage(fail_command="Fetch.disable")
    tab = SimpleNamespace(page=page, url="https://example.test", mcp_tab_id="t0")

    with pytest.raises(HttpAuthError) as exc_info:
        await HttpAuthOperations(tab).navigate(  # type: ignore[arg-type]
            url="https://example.test",
            username="agent",
            password="secret",
            realm="secure",
            timeout=1,
        )

    assert exc_info.value.reason_code == "FETCH_DISABLE_FAILED"


@pytest.mark.asyncio
async def test_http_auth_does_not_claim_success_without_target_response_status() -> None:
    page = _AuthPage()

    def get_without_response(url: str, *, retry: int, timeout: float) -> bool:
        page.driver.callbacks["Fetch.authRequired"](
            requestId="request-1",
            request={"url": url},
            authChallenge={"realm": "secure"},
        )
        return True

    page.get = get_without_response  # type: ignore[method-assign]
    tab = SimpleNamespace(page=page, url="https://example.test", mcp_tab_id="t0")

    result = await HttpAuthOperations(tab).navigate(  # type: ignore[arg-type]
        url="https://example.test",
        username="agent",
        password="secret",
        realm="secure",
        timeout=1,
    )

    assert result["challenge_count"] == 1
    assert result["response_status"] is None
    assert result["authenticated"] is False


def test_http_auth_lifetime_falls_back_and_reports_cleanup_and_rejection() -> None:
    commands: list[str] = []
    callbacks: list[tuple[str, Any]] = []
    errors: list[str] = []

    def run_cdp(command: str, **_: Any) -> None:
        commands.append(command)
        if command == "Fetch.disable":
            raise RuntimeError("disable failed")

    def set_callback(name: str, callback: Any) -> None:
        callbacks.append((name, callback))

    def navigate(_url: str) -> bool:
        return False

    cleanup_error = HttpAuthOperations._run_auth_lifetime(
        run_cdp=run_cdp,
        set_callback=set_callback,
        continue_paused=lambda **_: None,
        continue_auth=lambda **_: None,
        navigate=navigate,
        url="https://example.test",
        timeout=1,
        callback_errors=errors,
    )

    assert cleanup_error == "FETCH_DISABLE_FAILED"
    assert errors == ["AUTHENTICATION_REJECTED"]
    assert commands == ["Fetch.enable", "Fetch.disable"]
    assert callbacks[-2:] == [
        ("Fetch.requestPaused", None),
        ("Fetch.authRequired", None),
    ]


@pytest.mark.parametrize("failure", ["enable", "callback_cleanup"])
def test_http_auth_lifetime_classifies_setup_and_callback_cleanup_failures(
    failure: str,
) -> None:
    errors: list[str] = []

    def run_cdp(command: str, **_: Any) -> None:
        if failure == "enable" and command == "Fetch.enable":
            raise RuntimeError("enable failed")

    def set_callback(_name: str, callback: Any) -> None:
        if failure == "callback_cleanup" and callback is None:
            raise RuntimeError("cleanup failed")

    cleanup_error = HttpAuthOperations._run_auth_lifetime(
        run_cdp=run_cdp,
        set_callback=set_callback,
        continue_paused=lambda **_: None,
        continue_auth=lambda **_: None,
        navigate=lambda *_args, **_kwargs: True,
        url="https://example.test",
        timeout=1,
        callback_errors=errors,
    )

    if failure == "enable":
        assert errors == ["AUTH_NAVIGATION_INVOCATION_FAILED"]
        assert cleanup_error is None
    else:
        assert errors == []
        assert cleanup_error == "FETCH_CALLBACK_CLEANUP_FAILED"


def test_http_auth_does_not_retry_internal_navigation_type_error() -> None:
    calls = 0
    errors: list[str] = []

    def navigate(
        _url: str, *, retry: int | None = None, timeout: float | None = None
    ) -> bool:
        nonlocal calls
        calls += 1
        raise TypeError("internal navigation failure")

    cleanup_error = HttpAuthOperations._run_auth_lifetime(
        run_cdp=lambda *_args, **_kwargs: None,
        set_callback=lambda *_args, **_kwargs: None,
        continue_paused=lambda **_: None,
        continue_auth=lambda **_: None,
        navigate=navigate,
        url="https://example.test",
        timeout=1,
        callback_errors=errors,
    )

    assert cleanup_error is None
    assert errors == ["AUTH_NAVIGATION_INVOCATION_FAILED"]
    assert calls == 1


@pytest.mark.asyncio
async def test_http_auth_cleanup_failure_closes_browser_state_fail_closed() -> None:
    class FailedAuth:
        async def navigate(self, **_: Any) -> dict[str, Any]:
            raise HttpAuthError("AUTHENTICATION_REJECTED")

    tab = SimpleNamespace(http_auth=FailedAuth())

    class FailedCleanupContext(DrissionPageContext):
        def __init__(self) -> None:
            super().__init__()
            self.closed_browser = False

        async def new_isolated_tab(self) -> Any:
            return tab

        async def close_tab(self, _tab: Any = None) -> None:
            raise RuntimeError("private context disposal failure")

        async def close_browser(self) -> bool:
            self.closed_browser = True
            return True

    context = FailedCleanupContext()

    with pytest.raises(RuntimeError, match="cleanup failed") as exc_info:
        await context.navigate_with_http_auth(
            url="https://example.test",
            username="agent",
            password="secret-token",
            realm=None,
            timeout=1,
        )

    assert context.closed_browser is True
    assert "secret-token" not in str(exc_info.value)


def test_http_auth_origin_helpers_reject_unsafe_urls_and_normalize_ipv6() -> None:
    with pytest.raises(HttpAuthError) as exc_info:
        _http_origin("file:///private/page.html")
    assert exc_info.value.reason_code == "INVALID_AUTH_ORIGIN"
    assert _safe_origin("https://user:pass@example.test/private") == ""
    assert _safe_origin("https://example.test:bad") == ""
    assert _safe_origin("https://[::1]:8443/private") == "https://[::1]:8443"


class _PermissionBrowser:
    def __init__(self, *, fail_command: str | None = None) -> None:
        self.fail_command = fail_command
        self.commands: list[tuple[str, dict[str, Any]]] = []

    def _run_cdp(self, command: str, **kwargs: Any) -> dict[str, Any]:
        self.commands.append((command, kwargs))
        if command == self.fail_command:
            raise RuntimeError("private permission failure")
        if command == "Target.getBrowserContexts":
            return {"browserContextIds": ["context-1"]}
        if command == "Target.getTargetInfo":
            return {"targetInfo": {"browserContextId": "context-1"}}
        return {}


def _permission_operations(
    *,
    run_js: Any = lambda *_: {"supported": True, "state": "granted"},
    browser: Any | None = None,
    url: str = "https://example.test/path",
) -> PermissionOperations:
    page = SimpleNamespace(
        run_js=run_js,
        browser=browser if browser is not None else _PermissionBrowser(),
    )
    tab = SimpleNamespace(page=page, url=url, native_tab_id="native-tab")
    return PermissionOperations(tab)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("run_js", "reason"),
    [
        (None, "NAVIGATOR_PERMISSIONS_UNAVAILABLE"),
        (lambda *_: (_ for _ in ()).throw(RuntimeError("query failed")), "PERMISSION_QUERY_FAILED"),
        (lambda *_: [], "PERMISSION_QUERY_INVALID_RESULT"),
    ],
)
def test_permission_query_rejects_missing_failed_or_invalid_runtime_results(
    run_js: Any, reason: str
) -> None:
    with pytest.raises(PermissionUnsupportedError) as exc_info:
        _permission_operations(run_js=run_js).get("geolocation")

    assert exc_info.value.reason_code == reason


def test_permission_query_reports_unsupported_and_normalizes_ipv6_origin() -> None:
    operations = _permission_operations(
        run_js=lambda *_: {"supported": False, "error_name": "TypeError"},
        url="https://[::1]:8443/path",
    )

    assert operations.get("notifications") == {
        "permission": "notifications",
        "state": "unsupported",
        "origin": "https://[::1]:8443",
        "query_supported": False,
    }


def test_permission_set_and_reset_use_current_browser_context() -> None:
    browser = _PermissionBrowser()
    operations = _permission_operations(browser=browser)

    changed = operations.set("geolocation", "granted", "https://example.test")
    reset = operations.reset()

    assert changed["verified"] is True
    assert changed["observed_state"] == "granted"
    assert reset["reset"] is True
    set_call = next(call for call in browser.commands if call[0] == "Browser.setPermission")
    reset_call = next(
        call for call in browser.commands if call[0] == "Browser.resetPermissions"
    )
    assert set_call[1]["browserContextId"] == "context-1"
    assert reset_call[1]["browserContextId"] == "context-1"


def test_permission_set_reports_applied_when_post_write_query_is_unavailable() -> None:
    operations = _permission_operations(
        run_js=lambda *_: (_ for _ in ()).throw(RuntimeError("query unavailable"))
    )

    changed = operations.set("geolocation", "granted", "https://example.test")

    assert changed["applied"] is True
    assert changed["verified"] is False
    assert changed["observed_state"] is None


@pytest.mark.parametrize(
    ("command", "reason"),
    [
        ("Browser.setPermission", "BROWSER_SET_PERMISSION_FAILED"),
        ("Browser.resetPermissions", "BROWSER_RESET_PERMISSIONS_FAILED"),
    ],
)
def test_permission_mutations_report_safe_cdp_failures(command: str, reason: str) -> None:
    operations = _permission_operations(browser=_PermissionBrowser(fail_command=command))

    with pytest.raises(PermissionUnsupportedError) as exc_info:
        if command == "Browser.setPermission":
            operations.set("camera", "denied", "https://outside.test")
        else:
            operations.reset()

    assert exc_info.value.reason_code == reason


def test_permission_operations_reject_missing_browser_cdp_and_invalid_origin() -> None:
    operations = _permission_operations(browser=SimpleNamespace())
    with pytest.raises(PermissionUnsupportedError) as exc_info:
        operations.reset()
    assert exc_info.value.reason_code == "BROWSER_CDP_UNAVAILABLE"

    with pytest.raises(ValueError, match="valid HTTP"):
        _permission_operations(url="file:///tmp/page.html").current_origin()
    with pytest.raises(ValueError, match="valid HTTP"):
        _origin_from_url("https://example.test:bad")

    failing_contexts = _PermissionBrowser(fail_command="Target.getBrowserContexts")
    assert _permission_operations(browser=failing_contexts).browser_context_id() is None


class _ResolvedChooserTarget:
    def __init__(self, click: Any) -> None:
        self.element = SimpleNamespace(click=click)

    def metadata(self) -> dict[str, Any]:
        return {
            "selector": "#picker",
            "locator": "css:#picker",
            "selector_strategy": "css",
            "selector_normalized": True,
        }


class _ChooserTargeting:
    def __init__(self, click: Any) -> None:
        self.click = click

    async def resolve(self, _selector: Any, *, timeout: float) -> _ResolvedChooserTarget:
        return _ResolvedChooserTarget(self.click)


class _ChooserPage:
    def __init__(self) -> None:
        self._upload_list: list[str] | None = None
        self.driver = _CallbackDriver()
        self.commands: list[tuple[str, dict[str, Any]]] = []
        self.set = SimpleNamespace(upload_files=self._set_upload_files)

    def _set_upload_files(self, paths: list[str]) -> None:
        self._upload_list = paths

    def run_cdp(self, command: str, **kwargs: Any) -> None:
        self.commands.append((command, kwargs))


class _ChooserTab:
    def __init__(self, page: _ChooserPage, click: Any) -> None:
        self.page = page
        self.dom_targeting = _ChooserTargeting(click)
        self.stabilized = False

    async def _stabilize(self, *_args: Any, **_kwargs: Any) -> None:
        self.stabilized = True


@pytest.mark.asyncio
async def test_file_chooser_success_returns_basenames_and_cleans_interception() -> None:
    page = _ChooserPage()

    def click() -> None:
        page._upload_list = None

    tab = _ChooserTab(page, click)
    result = await FileChooserOperations(tab).click_and_upload(  # type: ignore[arg-type]
        "#picker", ["/private/root/one.txt", "/private/root/two.txt"], timeout=1
    )

    assert result["filenames"] == ["one.txt", "two.txt"]
    assert result["file_count"] == 2
    assert tab.stabilized is True
    assert page._upload_list is None
    assert page.driver.callbacks == {}
    assert page.commands[-1] == (
        "Page.setInterceptFileChooserDialog",
        {"enabled": False},
    )


@pytest.mark.asyncio
async def test_file_chooser_timeout_still_disarms_browser_interception() -> None:
    page = _ChooserPage()
    tab = _ChooserTab(page, lambda: None)

    with pytest.raises(TimeoutError, match="timed out"):
        await FileChooserOperations(tab).click_and_upload(  # type: ignore[arg-type]
            "#picker", ["/private/root/one.txt"], timeout=0.001
        )

    assert page._upload_list is None
    assert page.driver.callbacks == {}
    assert page.commands[-1][1] == {"enabled": False}


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["setter", "cdp", "callback", "armed", "click"])
async def test_file_chooser_rejects_unavailable_or_conflicting_runtime(
    missing: str,
) -> None:
    page = _ChooserPage()

    def click() -> None:
        return None

    click_action: Any = click
    if missing == "setter":
        page.set.upload_files = None
    elif missing == "cdp":
        page.run_cdp = None  # type: ignore[method-assign]
    elif missing == "callback":
        page.driver.set_callback = None  # type: ignore[method-assign]
    elif missing == "armed":
        page._upload_list = ["already-armed"]
    else:
        click_action = None
    tab = _ChooserTab(page, click_action)

    with pytest.raises(FileChooserError):
        await FileChooserOperations(tab).click_and_upload(  # type: ignore[arg-type]
            "#picker", ["/private/root/one.txt"], timeout=1
        )


def test_file_chooser_cleanup_is_best_effort() -> None:
    class LockedPage:
        def __setattr__(self, _name: str, _value: Any) -> None:
            raise RuntimeError("locked")

    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("cleanup unavailable")

    FileChooserOperations._cleanup(LockedPage(), fail, fail)


@pytest.mark.asyncio
async def test_new_navigation_and_upload_tools_enforce_policy_before_browser_use(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DP_MCP_NAV_ALLOWLIST", "allowed.example.test")
    auth_context = _AuthContext()
    auth_tool = _tool("page_navigate_with_http_auth")
    auth_outcome = await auth_tool.execute(
        auth_context,
        auth_tool.input_model(
            url="https://blocked.example.test/private",
            username="agent",
            password="secret-token",
        ),
    )
    assert auth_outcome.structured_content()["error"]["code"] == "POLICY_DENIED"
    assert auth_context.calls == []

    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    monkeypatch.setenv("DP_MCP_UPLOAD_ROOT", str(upload_root))
    upload_tool = _tool("element_click_and_upload")
    upload_outcome = await upload_tool.execute(
        DrissionPageContext(),
        upload_tool.input_model(selector="#picker", paths=[str(outside)]),
    )
    assert upload_outcome.structured_content()["error"]["code"] == "POLICY_DENIED"


class _ToolPermissions:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def current_origin(self) -> str:
        return "https://example.test"

    def get(self, permission: str) -> dict[str, Any]:
        self.calls.append(("get", permission))
        return {
            "permission": permission,
            "state": "prompt",
            "origin": "https://example.test",
            "query_supported": True,
        }

    def set(self, permission: str, setting: str, origin: str) -> dict[str, Any]:
        self.calls.append(("set", permission, setting, origin))
        return {
            "permission": permission,
            "setting": setting,
            "origin": origin,
            "applied": True,
            "verified": True,
            "observed_state": setting,
            "context_scope": "current_browser_context",
        }

    def reset(self) -> dict[str, Any]:
        self.calls.append(("reset",))
        return {"reset": True, "context_scope": "current_browser_context"}


@pytest.mark.asyncio
async def test_permission_tools_delegate_typed_get_set_and_reset_results() -> None:
    permissions = _ToolPermissions()
    context = DrissionPageContext()
    context._current_tab = SimpleNamespace(permissions=permissions)  # type: ignore[assignment]

    get_tool = _tool("browser_permission_get")
    set_tool = _tool("browser_permission_set")
    reset_tool = _tool("browser_permissions_reset")
    observed = await get_tool.execute(
        context, get_tool.input_model(permission="geolocation")
    )
    changed = await set_tool.execute(
        context,
        set_tool.input_model(permission="geolocation", setting="granted"),
    )
    reset = await reset_tool.execute(context, reset_tool.input_model())

    assert observed.structured_content()["data"]["state"] == "prompt"
    assert changed.structured_content()["data"]["observed_state"] == "granted"
    assert reset.structured_content()["data"]["reset"] is True
    assert permissions.calls == [
        ("get", "geolocation"),
        ("set", "geolocation", "granted", "https://example.test"),
        ("reset",),
    ]
    assert set_tool.idempotent is True
    assert reset_tool.idempotent is True


@pytest.mark.asyncio
async def test_permission_set_policy_denial_does_not_call_cdp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DP_MCP_NAV_ALLOWLIST", "allowed.example.test")
    permissions = _ToolPermissions()
    context = DrissionPageContext()
    context._current_tab = SimpleNamespace(permissions=permissions)  # type: ignore[assignment]
    tool = _tool("browser_permission_set")

    outcome = await tool.execute(
        context,
        tool.input_model(
            permission="camera",
            setting="denied",
            origin="https://blocked.example.test",
        ),
    )

    assert outcome.structured_content()["error"]["code"] == "POLICY_DENIED"
    assert permissions.calls == []


def test_auth_url_and_permission_origin_validators_handle_ports_and_ipv6() -> None:
    AuthInput = _tool("page_navigate_with_http_auth").input_model
    PermissionSetInput = _tool("browser_permission_set").input_model

    with pytest.raises(ValidationError):
        AuthInput(
            url="https://example.test:bad",
            username="agent",
            password="secret",
        )
    with pytest.raises(ValidationError):
        PermissionSetInput(
            permission="camera",
            setting="granted",
            origin="https://example.test:bad",
        )
    assert (
        PermissionSetInput(
            permission="camera",
            setting="granted",
            origin="https://[::1]:8443",
        ).origin
        == "https://[::1]:8443"
    )


@pytest.mark.asyncio
async def test_http_auth_validation_failure_never_echoes_rejected_credentials() -> None:
    server = DrissionPageMCPServer()
    secret = "validation-secret-token"

    result = await server._call_tool_impl(
        "page_navigate_with_http_auth",
        {
            "url": "https://example.test",
            "username": "agent",
            "password": secret,
            "unknown": secret,
        },
    )

    payload = _json_payload(result)
    assert result.isError is True
    assert result.structuredContent["error"]["code"] == "MCP_ARGUMENT_INVALID"
    assert "unknown" in result.structuredContent["message"]
    assert secret not in payload
