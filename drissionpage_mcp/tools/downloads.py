"""Atomic browser click/download workflow with typed artifact receipts."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
    model_validator,
)

from ..browser.downloads import (
    DownloadFailedError,
    DownloadIndeterminateError,
    DownloadUnsupportedError,
    DownloadValidationError,
)
from ..browser.motion import PointerProfile
from ..browser.targeting import DomTargetResolver
from ..limits import MAX_WAIT_SECONDS
from ..policy import PolicyDeniedError, SafetyPolicy
from ..response_errors import ErrorCode
from ..runtime import OperationClaim
from ..target import (
    AccessibilityTargetInput,
    SelectorTargetInput,
    TargetString,
    target_payload,
)
from ..tool_outputs import (
    ActionReceipt,
    ArtifactRef,
    CapabilityProbe,
    ElementClickAndDownloadData,
)
from .base import TabScopedInput, ToolOutcome, ToolType, define_tool, identity_tab_id

if TYPE_CHECKING:
    from ..context import DrissionPageContext
    from ..tab import PageTab


OperationKey = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=128, strip_whitespace=True),
]
Filename = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=255, strip_whitespace=True),
]
MimeType = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=200, strip_whitespace=True),
]


class CoordinateDownloadTriggerInput(BaseModel):
    """One left click at bounded viewport coordinates."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["coordinate"]
    x: float = Field(..., ge=0, le=100000)
    y: float = Field(..., ge=0, le=100000)
    profile: PointerProfile = "direct"
    delay_before_press_ms: int = Field(default=0, ge=0, le=10000)


class KeyboardDownloadTriggerInput(BaseModel):
    """One bounded keyboard input sent to the active page element."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["keyboard"]
    keys: Annotated[StrictStr, StringConstraints(min_length=1, max_length=256)]
    interval: float = Field(default=0, ge=0, le=2)


StructuredDownloadTrigger = Annotated[
    SelectorTargetInput
    | AccessibilityTargetInput
    | CoordinateDownloadTriggerInput
    | KeyboardDownloadTriggerInput,
    Field(discriminator="kind"),
]
DownloadTriggerArg = TargetString | StructuredDownloadTrigger


class ElementClickAndDownloadInput(TabScopedInput):
    """Strict request for one native click and one correlated download."""

    selector: DownloadTriggerArg = Field(
        ...,
        description=(
            "Selector/accessibility target, viewport coordinate click, or keyboard "
            "input that starts one download."
        ),
    )
    operation_key: OperationKey | None = Field(
        default=None,
        description="Optional live-task key. Reusing the same key replays the frozen artifact result without clicking again.",
    )
    timeout: float = Field(
        default=30.0,
        gt=0,
        le=MAX_WAIT_SECONDS,
        description="Shared maximum seconds for target resolution, click, and download completion.",
    )
    expected_filename: Filename | None = Field(
        default=None,
        description="Optional exact basename constraint for the downloaded artifact.",
    )
    expected_mime_type: MimeType | None = Field(
        default=None,
        description="Optional MIME constraint inferred from the completed filename.",
    )

    @model_validator(mode="after")
    def validate_filename(self) -> ElementClickAndDownloadInput:
        if self.expected_filename is not None and (
            self.expected_filename in {".", ".."}
            or "/" in self.expected_filename
            or "\\" in self.expected_filename
        ):
            raise ValueError("expected_filename must be a basename")
        return self


@dataclass(slots=True)
class _DownloadPreflight:
    root: Path
    tab: PageTab
    deadline: float
    target_metadata: dict[str, Any]
    trigger: DownloadTriggerArg
    element: Any | None
    action_id: str
    operation_key: str
    fingerprint: str


@dataclass(slots=True)
class _ClaimedDownload:
    preflight: _DownloadPreflight
    artifact_id: str
    download_dir: Path
    claim: OperationClaim
    started_at: datetime
    target_fingerprint: str
    reserved: bool = True
    committed: bool = False


@define_tool(
    name="element_click_and_download",
    title="Click And Download",
    description=(
        "Perform one selector, coordinate, or keyboard trigger, await one completed "
        "download, and return an integrity-checked safe artifact receipt."
    ),
    input_schema=ElementClickAndDownloadInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=ElementClickAndDownloadData,
    failure_message=lambda args, exc: _download_failure_message(exc),
)
async def element_click_and_download(
    context: DrissionPageContext, args: ElementClickAndDownloadInput
) -> ToolOutcome:
    """Execute one download boundary after all non-side-effect preconditions."""

    action_id, operation_key, fingerprint = _download_identity(context, args)
    replay = _download_replay_outcome(context, operation_key, fingerprint)
    if replay is not None:
        return replay

    try:
        policy = SafetyPolicy.from_env()
        policy.validate_external_download()
        root = policy.validate_download_root()
    except PolicyDeniedError as exc:
        outcome = ToolOutcome()
        outcome.add_error(
            str(exc), ErrorCode.POLICY_DENIED, rule=exc.rule, value=exc.value
        )
        return outcome

    preflight = await _download_preflight(
        context,
        args,
        root=root,
        action_id=action_id,
        operation_key=operation_key,
        fingerprint=fingerprint,
    )
    claimed = await _claim_download(context, preflight)
    return await _execute_claimed_download(context, args, claimed)


def _download_identity(
    context: DrissionPageContext, args: ElementClickAndDownloadInput
) -> tuple[str | None, str, str]:
    action_id: str | None = None
    operation_key = args.operation_key
    if operation_key is None:
        action_id = context.new_action_id()
        operation_key = f"download-{action_id}"
    resolved_tab_id = identity_tab_id(context, args.tab_id, operation_key)
    request = {
        "tab_id": resolved_tab_id,
        "selector": _download_trigger_payload(args.selector),
        "operation_key": operation_key,
        "timeout": args.timeout,
        "expected_filename": args.expected_filename,
        "expected_mime_type": args.expected_mime_type,
        "resolved_tab_id": resolved_tab_id,
    }
    fingerprint = context.request_fingerprint(
        {"tool": "element_click_and_download", **request}
    )
    return action_id, operation_key, fingerprint


def _download_replay_outcome(
    context: DrissionPageContext, operation_key: str, fingerprint: str
) -> ToolOutcome | None:
    replay = context.preview_operation(operation_key, fingerprint)
    if replay is None:
        return None
    if replay.cached_result is None:
        raise RuntimeError("Cached download operation has no frozen result.")
    if replay.cached_result.get("status") == "success":
        outcome = ToolOutcome()
        outcome.set_result(
            f"Replayed completed download for operation key {operation_key}",
            replay.cached_result,
        )
        return outcome
    return _failure_outcome(
        replay.cached_result,
        _download_error_from_status(str(replay.cached_result.get("status"))),
    )


async def _download_preflight(
    context: DrissionPageContext,
    args: ElementClickAndDownloadInput,
    *,
    root: Path,
    action_id: str | None,
    operation_key: str,
    fingerprint: str,
) -> _DownloadPreflight:
    capability_name = _download_capability_name(args.selector)
    _validate_download_capability(context, capability_name)
    tab = context.current_tab_or_die()
    deadline = monotonic() + args.timeout
    element: Any | None = None
    try:
        if isinstance(
            args.selector,
            (CoordinateDownloadTriggerInput, KeyboardDownloadTriggerInput),
        ):
            tab.downloads.probe_trigger()
            target_metadata = {"trigger": _public_trigger_metadata(args.selector)}
        else:
            target_timeout = max(0, math.ceil(deadline - monotonic()))
            targeting = getattr(tab, "dom_targeting", DomTargetResolver(tab))
            resolved = await targeting.resolve(args.selector, timeout=target_timeout)
            element = resolved.element
            tab.downloads.probe(element)
            target_metadata = resolved.metadata()
    except DownloadUnsupportedError as exc:
        context.record_capability_probe(
            _download_probe(
                "unsupported",
                exc.reason_code,
                name=capability_name,
            )
        )
        raise
    _validate_task_download_directory(root, context.task_id)
    return _DownloadPreflight(
        root=root,
        tab=tab,
        deadline=deadline,
        target_metadata=target_metadata,
        trigger=args.selector,
        element=element,
        action_id=action_id or context.new_action_id(),
        operation_key=operation_key,
        fingerprint=fingerprint,
    )


async def _claim_download(
    context: DrissionPageContext, preflight: _DownloadPreflight
) -> _ClaimedDownload:
    artifact_id = context.new_artifact_id()
    reserved = False
    download_dir: Path | None = None
    try:
        context.reserve_artifact_slot(artifact_id)
        reserved = True
        download_dir = _allocate_download_dir(
            preflight.root,
            context.task_id,
            preflight.action_id,
        )
        claim = context.claim_operation(
            preflight.operation_key,
            preflight.fingerprint,
        )
    except Exception:
        if reserved:
            context.release_artifact_slot(artifact_id)
        rollback_cancellation = await _cleanup_download_dir(
            preflight.tab,
            download_dir,
        )
        if rollback_cancellation is not None:
            raise rollback_cancellation from None
        raise

    target_fingerprint = context.request_fingerprint(
        {
            "tab_id": preflight.tab.mcp_tab_id or "untracked-tab",
            "trigger": _download_trigger_payload(preflight.trigger),
            "url": preflight.tab.url,
        }
    )
    return _ClaimedDownload(
        preflight=preflight,
        artifact_id=artifact_id,
        download_dir=download_dir,
        claim=claim,
        started_at=datetime.now(timezone.utc),
        target_fingerprint=target_fingerprint,
    )


async def _execute_claimed_download(
    context: DrissionPageContext,
    args: ElementClickAndDownloadInput,
    state: _ClaimedDownload,
) -> ToolOutcome:
    try:
        result = await _invoke_download(args, state)
        return _complete_download_success(context, state, result)
    except asyncio.CancelledError:
        await _complete_cancelled_download(context, state)
        raise
    except Exception as exc:
        if state.committed:
            raise
        return await _complete_failed_download(context, state, exc)


async def _invoke_download(
    args: ElementClickAndDownloadInput,
    state: _ClaimedDownload,
) -> dict[str, Any]:
    remaining = state.preflight.deadline - monotonic()
    if remaining <= 0:
        raise TimeoutError("Download deadline expired before native invocation.")
    trigger = state.preflight.trigger
    if isinstance(trigger, CoordinateDownloadTriggerInput):

        async def invoke() -> Any:
            return await state.preflight.tab.pointer.click_at(
                trigger.x,
                trigger.y,
                profile=trigger.profile,
                button="left",
                delay_before_press_ms=trigger.delay_before_press_ms,
            )

        result = await state.preflight.tab.downloads.trigger_and_wait(
            invoke,
            download_dir=state.download_dir,
            timeout=remaining,
        )
    elif isinstance(trigger, KeyboardDownloadTriggerInput):

        async def invoke() -> Any:
            return await state.preflight.tab.interaction.keyboard_press(
                trigger.keys,
                interval=trigger.interval,
            )

        result = await state.preflight.tab.downloads.trigger_and_wait(
            invoke,
            download_dir=state.download_dir,
            timeout=remaining,
        )
    else:
        result = await state.preflight.tab.downloads.click_and_wait(
            state.preflight.element,
            download_dir=state.download_dir,
            timeout=remaining,
        )
    if (
        args.expected_filename is not None
        and result["filename"] != args.expected_filename
    ):
        raise DownloadValidationError(
            "Downloaded filename did not match the requested constraint."
        )
    if (
        args.expected_mime_type is not None
        and result["mime_type"] != args.expected_mime_type
    ):
        raise DownloadValidationError(
            "Downloaded MIME type did not match the requested constraint."
        )
    return result


def _complete_download_success(
    context: DrissionPageContext,
    state: _ClaimedDownload,
    result: dict[str, Any],
) -> ToolOutcome:
    preflight = state.preflight
    artifact = ArtifactRef(
        artifact_id=state.artifact_id,
        task_id=context.task_id,
        producing_action_id=preflight.action_id,
        kind="download",
        filename=result["filename"],
        mime_type=result["mime_type"],
        size_bytes=result["size_bytes"],
        sha256=result["sha256"],
        safe_relative_path=result["path"]
        .relative_to(preflight.root.resolve())
        .as_posix(),
        source_url=result["source_url"],
        created_at=datetime.now(timezone.utc),
    )
    receipt = _download_receipt_for_state(
        context,
        state,
        status="success",
        artifact_ids=(state.artifact_id,),
    )
    data = _download_data(state, receipt, artifact=artifact)
    context.complete_artifact_operation(
        state.claim,
        receipt,
        artifact,
        result=data,
    )
    state.reserved = False
    state.committed = True
    try:
        context.record_capability_probe(
            _download_probe(
                "supported",
                name=_download_capability_name(preflight.trigger),
            )
        )
    except Exception:
        pass

    outcome = ToolOutcome()
    outcome.set_result("Downloaded one integrity-checked artifact", data)
    return outcome


async def _complete_cancelled_download(
    context: DrissionPageContext, state: _ClaimedDownload
) -> None:
    await _release_and_cleanup_download(context, state)
    receipt = _download_receipt_for_state(
        context,
        state,
        status="indeterminate",
        error_code="DOWNLOAD_INDETERMINATE",
    )
    failure_data = _download_data(state, receipt)
    context.complete_operation(state.claim, receipt, result=failure_data)


async def _complete_failed_download(
    context: DrissionPageContext,
    state: _ClaimedDownload,
    exc: Exception,
) -> ToolOutcome:
    cleanup_cancellation = await _release_and_cleanup_download(context, state)
    status = _download_failure_status(exc, cleanup_cancellation)
    receipt = _download_receipt_for_state(
        context,
        state,
        status=status,
        error_code=f"DOWNLOAD_{status.upper()}",
    )
    failure_data = _download_data(state, receipt)
    context.complete_operation(state.claim, receipt, result=failure_data)
    if cleanup_cancellation is not None:
        raise cleanup_cancellation
    return _failure_outcome(failure_data, exc)


async def _release_and_cleanup_download(
    context: DrissionPageContext, state: _ClaimedDownload
) -> asyncio.CancelledError | None:
    if state.reserved:
        context.release_artifact_slot(state.artifact_id)
        state.reserved = False
    return await _cleanup_download_dir(state.preflight.tab, state.download_dir)


async def _cleanup_download_dir(
    tab: PageTab, download_dir: Path | None
) -> asyncio.CancelledError | None:
    if download_dir is None:
        return None
    cleanup = asyncio.create_task(tab.downloads.cleanup(download_dir))
    return await _drain_cleanup(cleanup)


def _download_failure_status(
    exc: Exception,
    cleanup_cancellation: asyncio.CancelledError | None,
) -> Literal["failed", "validation_failed", "indeterminate"]:
    if cleanup_cancellation is not None:
        return "indeterminate"
    if isinstance(exc, DownloadValidationError):
        return "validation_failed"
    if isinstance(exc, (DownloadFailedError, DownloadUnsupportedError)):
        return "failed"
    return "indeterminate"


def _download_receipt_for_state(
    context: DrissionPageContext,
    state: _ClaimedDownload,
    *,
    status: Literal["success", "failed", "validation_failed", "indeterminate"],
    artifact_ids: tuple[str, ...] = (),
    error_code: str | None = None,
) -> ActionReceipt:
    preflight = state.preflight
    return _receipt(
        context=context,
        action_id=preflight.action_id,
        operation_key=preflight.operation_key,
        fingerprint=preflight.fingerprint,
        tab_id=preflight.tab.mcp_tab_id or "untracked-tab",
        target_fingerprint=state.target_fingerprint,
        started_at=state.started_at,
        status=status,
        artifact_ids=artifact_ids,
        error_code=error_code,
    )


def _download_data(
    state: _ClaimedDownload,
    receipt: ActionReceipt,
    *,
    artifact: ArtifactRef | None = None,
) -> dict[str, Any]:
    data = {
        "status": receipt.status,
        "operation_key": state.preflight.operation_key,
        "tab_id": receipt.tab_id,
        **state.preflight.target_metadata,
        "artifact": (
            artifact.model_dump(mode="json") if artifact is not None else None
        ),
        "receipt": receipt.model_dump(mode="json"),
    }
    validated: dict[str, Any] = ElementClickAndDownloadData.model_validate(
        data
    ).model_dump(mode="json")
    selector_fields = (
        "selector",
        "locator",
        "selector_strategy",
        "selector_normalized",
        "target_kind",
        "frame_selectors",
        "shadow_hosts",
        "role",
        "name",
        "exact",
    )
    if "trigger" in state.preflight.target_metadata:
        for field in selector_fields:
            validated.pop(field, None)
    else:
        validated.pop("trigger", None)
        validated["target_kind"] = validated["target_kind"] or "selector"
        validated["frame_selectors"] = validated["frame_selectors"] or []
        validated["shadow_hosts"] = validated["shadow_hosts"] or []
    return validated


def _download_trigger_payload(
    trigger: DownloadTriggerArg,
) -> str | dict[str, object]:
    if isinstance(
        trigger,
        (CoordinateDownloadTriggerInput, KeyboardDownloadTriggerInput),
    ):
        return trigger.model_dump(mode="json")
    return target_payload(trigger)


def _public_trigger_metadata(
    trigger: CoordinateDownloadTriggerInput | KeyboardDownloadTriggerInput,
) -> dict[str, Any]:
    if isinstance(trigger, CoordinateDownloadTriggerInput):
        return trigger.model_dump(mode="json")
    return {
        "kind": "keyboard",
        "keys": {
            "provided": bool(trigger.keys),
            "length": len(trigger.keys),
            "redacted": True,
        },
        "interval": trigger.interval,
    }


async def _drain_cleanup(
    task: asyncio.Task[Any],
) -> asyncio.CancelledError | None:
    cancellation: asyncio.CancelledError | None = None
    while True:
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as exc:
            cancellation = exc
            if task.done():
                break
            continue
        break
    try:
        task.result()
    except asyncio.CancelledError as exc:
        cancellation = exc
    except Exception:
        pass
    return cancellation


def _allocate_download_dir(root: Path, task_id: str, action_id: str) -> Path:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise PolicyDeniedError(
            "DP_MCP_DOWNLOAD_ROOT must identify a directory.",
            rule="DP_MCP_DOWNLOAD_ROOT",
            value="<redacted>",
        )
    task_dir = root / task_id
    if task_dir.exists() and task_dir.is_symlink():
        raise PolicyDeniedError(
            "The task download directory is a symlink.",
            rule="DP_MCP_DOWNLOAD_ROOT",
            value="<redacted>",
        )
    task_dir.mkdir(exist_ok=True)
    action_dir = task_dir / action_id
    action_dir.mkdir(exist_ok=False)
    resolved = action_dir.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PolicyDeniedError(
            "The allocated download directory escaped DP_MCP_DOWNLOAD_ROOT.",
            rule="DP_MCP_DOWNLOAD_ROOT",
            value="<redacted>",
        ) from exc
    return resolved


def _validate_task_download_directory(root: Path, task_id: str) -> None:
    task_dir = root.expanduser().resolve() / task_id
    if task_dir.is_symlink():
        raise PolicyDeniedError(
            "The task download directory is a symlink.",
            rule="DP_MCP_DOWNLOAD_ROOT",
            value="<redacted>",
        )
    if task_dir.exists() and not task_dir.is_dir():
        raise PolicyDeniedError(
            "The task download directory must be a directory.",
            rule="DP_MCP_DOWNLOAD_ROOT",
            value="<redacted>",
        )


def _validate_download_capability(
    context: DrissionPageContext,
    capability_name: str,
) -> None:
    for capability in context.capability_set().capabilities:
        if capability.name == capability_name and capability.status in {
            "unsupported",
            "degraded",
        }:
            raise DownloadUnsupportedError(
                capability.reason_code or "RECORDED_CAPABILITY_UNAVAILABLE"
            )


def _download_probe(
    status: Literal["supported", "unsupported"],
    reason: str | None = None,
    *,
    name: str = "download.click_and_wait",
) -> CapabilityProbe:
    return CapabilityProbe(
        name=name,
        status=status,
        evidence_source="runtime_probe"
        if status == "unsupported"
        else "integration_probe",
        reason_code=reason,
        checked_at=datetime.now(timezone.utc),
    )


def _download_capability_name(trigger: DownloadTriggerArg) -> str:
    if isinstance(
        trigger,
        (CoordinateDownloadTriggerInput, KeyboardDownloadTriggerInput),
    ):
        return "download.trigger_and_wait"
    return "download.click_and_wait"


def _receipt(
    *,
    context: DrissionPageContext,
    action_id: str,
    operation_key: str,
    fingerprint: str,
    tab_id: str,
    target_fingerprint: str,
    started_at: datetime,
    status: Literal["success", "failed", "validation_failed", "indeterminate"],
    artifact_ids: tuple[str, ...] = (),
    error_code: str | None = None,
) -> ActionReceipt:
    return ActionReceipt(
        action_id=action_id,
        task_id=context.task_id,
        operation_key=operation_key,
        request_fingerprint=fingerprint,
        kind="element_click_and_download",
        side_effect="external_download",
        status=status,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        tab_id=tab_id,
        target_fingerprint=target_fingerprint,
        artifact_ids=artifact_ids,
        error_code=(
            error_code
            if error_code is not None
            else (None if status == "success" else f"DOWNLOAD_{status.upper()}")
        ),
        redacted=True,
    )


def _download_failure_message(exc: Exception) -> str:
    if isinstance(exc, DownloadUnsupportedError):
        return str(exc)
    if isinstance(exc, DownloadValidationError):
        return "Download artifact validation failed; no artifact was published."
    if isinstance(exc, DownloadFailedError):
        return "The browser download failed before producing an artifact."
    if isinstance(exc, (DownloadIndeterminateError, TimeoutError)):
        return "The browser download outcome is indeterminate; inspect the artifact inventory before retrying."
    if isinstance(exc, PolicyDeniedError):
        return str(exc)
    return (
        "The browser download outcome is indeterminate; diagnostic text was redacted."
    )


def _download_error_from_status(status: str) -> Exception:
    if status == "validation_failed":
        return DownloadValidationError(
            "The previous download failed artifact validation; no retry was performed."
        )
    if status == "failed":
        return DownloadFailedError(
            "The previous browser download failed; no retry was performed."
        )
    return DownloadIndeterminateError(
        "The previous browser download outcome is indeterminate; no retry was performed."
    )


def _failure_outcome(data: dict[str, object], exc: Exception) -> ToolOutcome:
    outcome = ToolOutcome()
    status = str(data.get("status") or "indeterminate")
    if status == "validation_failed":
        code = ErrorCode.PRECONDITION_FAILED
    elif status == "indeterminate":
        code = ErrorCode.TIMEOUT
    else:
        code = ErrorCode.UNKNOWN_ERROR
    outcome.add_error(
        _download_failure_message(exc),
        code,
        tool_name="element_click_and_download",
    )
    outcome._data = data
    return outcome
