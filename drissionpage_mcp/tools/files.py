"""File-related element tools for DrissionPage MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field, StrictStr, StringConstraints

from ..limits import MAX_WAIT_SECONDS
from ..policy import PolicyDeniedError, validate_upload_paths
from ..response_errors import ErrorCode
from ..target import ElementTargetArg, target_label
from ..tool_outputs import ElementClickAndUploadData, ElementUploadFileData
from .base import TabScopedInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext


class UploadFileInput(TabScopedInput):
    """Input schema for file uploads."""

    selector: ElementTargetArg = Field(
        ..., description="CSS/XPath/DrissionPage locator for an input[type=file]."
    )
    paths: list[str] = Field(
        ...,
        min_length=1,
        description="One or more local file paths under DP_MCP_UPLOAD_ROOT. Absolute paths are accepted but never echoed back in tool results.",
    )
    timeout: float = Field(
        default=10,
        ge=0,
        le=MAX_WAIT_SECONDS,
        description="Timeout in seconds to wait for the file input.",
    )


UploadPath = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=4096),
]


class ElementClickAndUploadInput(TabScopedInput):
    """Input for one browser-owned file chooser click and upload."""

    selector: ElementTargetArg = Field(
        ..., description="Selector/accessibility target that opens a file chooser."
    )
    paths: list[UploadPath] = Field(..., min_length=1, max_length=20)
    timeout: float = Field(default=10.0, gt=0, le=MAX_WAIT_SECONDS)


@define_tool(
    name="element_upload_file",
    title="Upload File",
    description="Set files on an input[type=file]. Paths must exist under DP_MCP_UPLOAD_ROOT and response data only returns safe file names.",
    input_schema=UploadFileInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=ElementUploadFileData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to upload file into '{target_label(args.selector)}': {e}"
    )(exc),
)
async def element_upload_file(
    context: DrissionPageContext, args: UploadFileInput
) -> ToolOutcome:
    """Upload one or more files into a file input."""
    outcome = ToolOutcome()
    try:
        safe_paths = validate_upload_paths(args.paths)
    except PolicyDeniedError as exc:
        outcome.add_error(
            str(exc), ErrorCode.POLICY_DENIED, rule=exc.rule, value=exc.value
        )
        return outcome
    tab = context.current_tab_or_die()
    result = await tab.elements.upload(
        args.selector, [str(path) for path in safe_paths], timeout=args.timeout
    )
    outcome.add_result(
        f"Uploaded {result['file_count']} file{('' if result['file_count'] == 1 else 's')}",
        **result,
    )
    return outcome


@define_tool(
    name="element_click_and_upload",
    title="Click And Upload",
    description="Arm Chromium's file chooser, click one trigger, inject approved files, and always remove interception without opening a native operating-system picker.",
    input_schema=ElementClickAndUploadInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=ElementClickAndUploadData,
    failure_message=lambda args, exc: (
        "Browser file chooser upload failed; local paths were redacted."
    ),
)
async def element_click_and_upload(
    context: DrissionPageContext, args: ElementClickAndUploadInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    try:
        safe_paths = validate_upload_paths(args.paths)
    except PolicyDeniedError as exc:
        outcome.add_error(
            str(exc), ErrorCode.POLICY_DENIED, rule=exc.rule, value=exc.value
        )
        return outcome
    tab = context.current_tab_or_die()
    result = await tab.file_chooser.click_and_upload(
        args.selector,
        [str(path) for path in safe_paths],
        timeout=args.timeout,
    )
    outcome.set_result(
        f"Uploaded {result['file_count']} file(s) through the browser chooser",
        result,
    )
    return outcome
