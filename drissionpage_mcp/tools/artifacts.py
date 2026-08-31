"""Managed PDF and MHTML page-export artifacts."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import Field, StrictStr, StringConstraints, model_validator

from ..browser.artifacts import (
    ArtifactFile,
    ArtifactFileChangedError,
    ArtifactFileValidationError,
    PageArtifactOperations,
    PageExportError,
    inspect_artifact_file,
)
from ..policy import PolicyDeniedError, SafetyPolicy
from ..response_errors import ErrorCode
from ..tool_outputs import ActionReceipt, ArtifactRef, PageExportArtifactData
from .base import TabScopedInput, ToolOutcome, ToolType, define_tool, identity_tab_id

if TYPE_CHECKING:
    from ..context import DrissionPageContext
    from ..tab import PageTab


OperationKey = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=128, strip_whitespace=True),
]
ExportFilename = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=255, strip_whitespace=True),
]
PageRanges = Annotated[
    StrictStr,
    StringConstraints(max_length=200, pattern=r"^[0-9,\- ]*$"),
]
MAX_PAGE_EXPORT_BYTES = 50 * 1024 * 1024


class PageExportArtifactInput(TabScopedInput):
    """Create one managed PDF or MHTML artifact from the current page."""

    format: Literal["pdf", "mhtml"]
    filename: ExportFilename | None = None
    operation_key: OperationKey | None = None
    landscape: bool = False
    print_background: bool = True
    scale: float = Field(default=1.0, ge=0.1, le=2.0)
    paper_width: float | None = Field(default=None, gt=0, le=100)
    paper_height: float | None = Field(default=None, gt=0, le=100)
    margin_top: float = Field(default=0.4, ge=0, le=10)
    margin_bottom: float = Field(default=0.4, ge=0, le=10)
    margin_left: float = Field(default=0.4, ge=0, le=10)
    margin_right: float = Field(default=0.4, ge=0, le=10)
    page_ranges: PageRanges = ""
    prefer_css_page_size: bool = False

    @model_validator(mode="after")
    def validate_export_options(self) -> PageExportArtifactInput:
        extension = f".{self.format}"
        filename = self.filename or f"page-export{extension}"
        if (
            filename in {".", ".."}
            or Path(filename).name != filename
            or "/" in filename
            or "\\" in filename
        ):
            raise ValueError("filename must be a basename")
        suffix = Path(filename).suffix.lower()
        if suffix and suffix != extension:
            raise ValueError(f"filename extension must match {self.format}")
        if not suffix:
            filename += extension
        self.filename = filename
        if self.format == "mhtml" and self.model_fields_set.intersection(
            {
                "landscape",
                "print_background",
                "scale",
                "paper_width",
                "paper_height",
                "margin_top",
                "margin_bottom",
                "margin_left",
                "margin_right",
                "page_ranges",
                "prefer_css_page_size",
            }
        ):
            raise ValueError("PDF print options cannot be used for MHTML export")
        return self

    def pdf_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {
            "landscape": self.landscape,
            "printBackground": self.print_background,
            "scale": self.scale,
            "marginTop": self.margin_top,
            "marginBottom": self.margin_bottom,
            "marginLeft": self.margin_left,
            "marginRight": self.margin_right,
            "pageRanges": self.page_ranges,
            "preferCSSPageSize": self.prefer_css_page_size,
        }
        if self.paper_width is not None:
            options["paperWidth"] = self.paper_width
        if self.paper_height is not None:
            options["paperHeight"] = self.paper_height
        return options


@define_tool(
    name="page_export_artifact",
    title="Export Page Artifact",
    description="Generate one PDF or MHTML file under DP_MCP_ARTIFACT_ROOT and return checksum, safe relative path, and exact-once receipt evidence.",
    input_schema=PageExportArtifactInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=PageExportArtifactData,
    failure_message=lambda args, exc: _export_failure_message(exc),
)
async def page_export_artifact(
    context: DrissionPageContext, args: PageExportArtifactInput
) -> ToolOutcome:
    action_id, operation_key, fingerprint = _export_identity(context, args)
    replay = _export_replay(context, operation_key, fingerprint)
    if replay is not None:
        return replay

    try:
        root = SafetyPolicy.from_env().validate_artifact_root()
    except PolicyDeniedError as exc:
        outcome = ToolOutcome()
        outcome.add_error(
            str(exc), ErrorCode.POLICY_DENIED, rule=exc.rule, value=exc.value
        )
        return outcome

    tab = context.current_tab_or_die()
    exporter = getattr(tab, "artifacts", None) or PageArtifactOperations(tab)
    artifact_id = context.new_artifact_id()
    directory: Path | None = None
    reserved = False
    claim = None
    started_at = datetime.now(timezone.utc)
    try:
        context.reserve_artifact_slot(artifact_id)
        reserved = True
        directory = _allocate_export_dir(root, context.task_id, action_id)
        claim = context.claim_operation(operation_key, fingerprint)
        output = await _invoke_export(exporter, directory, args)
        artifact = _build_artifact(
            context,
            tab,
            root,
            action_id,
            artifact_id,
            output,
            args.format,
        )
        receipt = _export_receipt(
            context,
            tab,
            action_id,
            operation_key,
            fingerprint,
            started_at,
            "success",
            artifact_ids=(artifact_id,),
        )
        data = PageExportArtifactData.model_validate(
            {
                "operation_key": operation_key,
                "format": args.format,
                "artifact": artifact,
                "receipt": receipt.model_dump(mode="json"),
                "tab_id": receipt.tab_id,
            }
        ).model_dump(mode="json")
        context.complete_artifact_operation(
            claim, receipt, artifact, result=data
        )
        reserved = False
        outcome = ToolOutcome()
        outcome.set_result(f"Exported current page as {args.format}", data)
        return outcome
    except asyncio.CancelledError:
        if reserved:
            context.release_artifact_slot(artifact_id)
        await exporter.cleanup(directory)
        if claim is not None:
            receipt = _export_receipt(
                context,
                tab,
                action_id,
                operation_key,
                fingerprint,
                started_at,
                "indeterminate",
            )
            context.complete_operation(
                claim,
                receipt,
                result=_export_failure_data(
                    operation_key, args.format, receipt, "indeterminate"
                ),
            )
        raise
    except Exception:
        if reserved:
            context.release_artifact_slot(artifact_id)
        await exporter.cleanup(directory)
        if claim is not None:
            receipt = _export_receipt(
                context,
                tab,
                action_id,
                operation_key,
                fingerprint,
                started_at,
                "failed",
            )
            context.complete_operation(
                claim,
                receipt,
                result=_export_failure_data(
                    operation_key, args.format, receipt, "failed"
                ),
            )
        raise


def _export_identity(
    context: DrissionPageContext, args: PageExportArtifactInput
) -> tuple[str, str, str]:
    action_id = context.new_action_id()
    operation_key = args.operation_key or f"page-export-{action_id}"
    resolved_tab_id = identity_tab_id(context, args.tab_id, operation_key)
    request = args.model_dump(mode="json")
    request["tab_id"] = resolved_tab_id
    request["operation_key"] = operation_key
    request["resolved_tab_id"] = resolved_tab_id
    fingerprint = context.request_fingerprint(
        {"tool": "page_export_artifact", **request}
    )
    return action_id, operation_key, fingerprint


def _export_replay(
    context: DrissionPageContext, operation_key: str, fingerprint: str
) -> ToolOutcome | None:
    replay = context.preview_operation(operation_key, fingerprint)
    if replay is None:
        return None
    if replay.cached_result is None:
        raise RuntimeError("Cached page export has no frozen result.")
    outcome = ToolOutcome()
    if replay.cached_result.get("artifact") is not None:
        outcome.set_result(
            f"Replayed completed page export for operation key {operation_key}",
            replay.cached_result,
        )
        return outcome
    indeterminate = replay.cached_result.get("status") == "indeterminate"
    outcome.add_error(
        (
            "The previous page export outcome is indeterminate; no second file "
            "was written."
            if indeterminate
            else "The previous page export failed; no second file was written."
        ),
        ErrorCode.TIMEOUT if indeterminate else ErrorCode.UNKNOWN_ERROR,
        tool_name="page_export_artifact",
    )
    outcome._data = replay.cached_result
    return outcome


def _export_failure_data(
    operation_key: str,
    export_format: Literal["pdf", "mhtml"],
    receipt: ActionReceipt,
    status: Literal["failed", "indeterminate"],
) -> dict[str, Any]:
    return {
        "status": status,
        "operation_key": operation_key,
        "format": export_format,
        "artifact": None,
        "receipt": receipt.model_dump(mode="json"),
        "tab_id": receipt.tab_id,
    }


async def _invoke_export(
    exporter: PageArtifactOperations,
    directory: Path,
    args: PageExportArtifactInput,
) -> ArtifactFile:
    task = asyncio.create_task(
        exporter.save(
            directory,
            str(args.filename),
            args.format,
            args.pdf_options(),
        )
    )
    cancellation: asyncio.CancelledError | None = None
    while True:
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as exc:
            cancellation = exc
            if not task.done():
                continue
        break
    if cancellation is not None:
        try:
            task.result()
        except Exception:
            pass
        raise cancellation
    output = task.result()
    try:
        artifact = await asyncio.to_thread(
            inspect_artifact_file,
            output,
            approved_root=directory,
            prefix_bytes=4,
        )
    except ArtifactFileValidationError as exc:
        raise PageExportError("GENERATED_FILE_UNSAFE") from exc
    except ArtifactFileChangedError as exc:
        raise PageExportError("GENERATED_FILE_CHANGED") from exc
    if artifact.size_bytes <= 0 or artifact.size_bytes > MAX_PAGE_EXPORT_BYTES:
        raise PageExportError("GENERATED_FILE_SIZE_INVALID")
    if args.format == "pdf" and artifact.prefix != b"%PDF":
        raise PageExportError("PDF_SIGNATURE_INVALID")
    return artifact


def _build_artifact(
    context: DrissionPageContext,
    tab: PageTab,
    root: Path,
    action_id: str,
    artifact_id: str,
    output: ArtifactFile,
    export_format: Literal["pdf", "mhtml"],
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        task_id=context.task_id,
        producing_action_id=action_id,
        kind="page_export",
        filename=output.path.name,
        mime_type=(
            "application/pdf" if export_format == "pdf" else "multipart/related"
        ),
        size_bytes=output.size_bytes,
        sha256=output.sha256,
        safe_relative_path=output.path.relative_to(root.resolve()).as_posix(),
        source_url=tab.url,
        created_at=datetime.now(timezone.utc),
    )


def _export_receipt(
    context: DrissionPageContext,
    tab: PageTab,
    action_id: str,
    operation_key: str,
    fingerprint: str,
    started_at: datetime,
    status: Literal["success", "failed", "indeterminate"],
    *,
    artifact_ids: tuple[str, ...] = (),
) -> ActionReceipt:
    return ActionReceipt(
        action_id=action_id,
        task_id=context.task_id,
        operation_key=operation_key,
        request_fingerprint=fingerprint,
        kind="page_export_artifact",
        side_effect="artifact_write",
        status=status,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        tab_id=tab.mcp_tab_id or "untracked-tab",
        target_fingerprint=context.request_fingerprint(
            {"tab_id": tab.mcp_tab_id or "untracked-tab", "url": tab.url}
        ),
        artifact_ids=artifact_ids,
        error_code=None if status == "success" else f"PAGE_EXPORT_{status.upper()}",
        redacted=True,
    )


def _allocate_export_dir(root: Path, task_id: str, action_id: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise PolicyDeniedError(
            "DP_MCP_ARTIFACT_ROOT must identify a directory.",
            rule="DP_MCP_ARTIFACT_ROOT",
            value="<redacted>",
        )
    task_dir = root / task_id
    if task_dir.is_symlink() or (task_dir.exists() and not task_dir.is_dir()):
        raise PolicyDeniedError(
            "The task artifact directory is unsafe.",
            rule="DP_MCP_ARTIFACT_ROOT",
            value="<redacted>",
        )
    task_dir.mkdir(exist_ok=True)
    action_dir = task_dir / action_id
    action_dir.mkdir(exist_ok=False)
    resolved = action_dir.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise PolicyDeniedError(
            "The allocated artifact directory escaped DP_MCP_ARTIFACT_ROOT.",
            rule="DP_MCP_ARTIFACT_ROOT",
            value="<redacted>",
        ) from exc
    return resolved


def _export_failure_message(exc: Exception) -> str:
    if isinstance(exc, PolicyDeniedError):
        return str(exc)
    return "Page export failed; local paths and page content were redacted."


__all__ = ["PageExportArtifactInput", "page_export_artifact"]
