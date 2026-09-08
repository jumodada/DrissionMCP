"""Iframe/frame read-only tools for DrissionPage MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from ..limits import MAX_WAIT_SECONDS
from ..metadata import with_response_meta
from ..tool_outputs import FrameFindData, FrameListData, FrameSnapshotData
from .base import TabScopedInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext


class FrameListInput(TabScopedInput):
    """Input schema for listing frames."""

    limit: int = Field(default=20, ge=1, le=100)


class FrameSnapshotInput(TabScopedInput):
    """Input schema for frame snapshots."""

    frame_selector: str = Field(
        default="",
        description="Optional iframe/frame selector. When empty, frame_index is used.",
    )
    frame_index: int = Field(default=0, ge=0, description="Zero-based frame index.")
    include_html: bool = Field(default=False)
    max_elements: int = Field(default=50, ge=1, le=200)
    max_text_chars: int = Field(default=4000, ge=0, le=20000)
    timeout: float = Field(default=3, ge=0, le=MAX_WAIT_SECONDS)


class FrameFindInput(TabScopedInput):
    """Input schema for finding one element inside a frame."""

    selector: str = Field(..., description="Selector inside the target frame.")
    frame_selector: str = Field(default="")
    frame_index: int = Field(default=0, ge=0)
    timeout: float = Field(default=3, ge=0, le=MAX_WAIT_SECONDS)


@define_tool(
    name="frame_list",
    title="List Frames",
    description="List iframe/frame contexts on the current page without changing global state.",
    input_schema=FrameListInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=FrameListData,
    failure_message=lambda args, exc: "Failed to list frames: " + str(exc),
)
async def frame_list(
    context: DrissionPageContext, args: FrameListInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.frames.list_frames(limit=args.limit)
    return ToolOutcome().add_result(f"Found {result['count']} frame(s)", **result)


@define_tool(
    name="frame_snapshot",
    title="Frame Snapshot",
    description="Return a bounded page outline from a selected iframe/frame.",
    input_schema=FrameSnapshotInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=FrameSnapshotData,
    failure_message=lambda args, exc: "Failed to capture frame snapshot: " + str(exc),
)
async def frame_snapshot(
    context: DrissionPageContext, args: FrameSnapshotInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.frames.snapshot(
        frame_selector=args.frame_selector,
        frame_index=args.frame_index,
        include_html=args.include_html,
        max_elements=args.max_elements,
        max_text_chars=args.max_text_chars,
        timeout=args.timeout,
    )
    return ToolOutcome().add_result("Captured frame snapshot", **with_response_meta(result))


@define_tool(
    name="frame_find",
    title="Find Element In Frame",
    description="Find an element inside a selected iframe/frame without global frame state.",
    input_schema=FrameFindInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=FrameFindData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to find '{args.selector}' in frame: {e}"
    )(exc),
)
async def frame_find(
    context: DrissionPageContext, args: FrameFindInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.frames.find(
        selector=args.selector,
        frame_selector=args.frame_selector,
        frame_index=args.frame_index,
        timeout=args.timeout,
    )
    return ToolOutcome().add_result(f"Found frame element: {args.selector}", **result)
