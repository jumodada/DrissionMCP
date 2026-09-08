"""Shadow DOM read-only tools for DrissionPage MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from ..limits import MAX_WAIT_SECONDS
from ..metadata import with_response_meta
from ..tool_outputs import ShadowFindAllData, ShadowFindData
from .base import TabScopedInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext


class ShadowFindInput(TabScopedInput):
    """Input schema for finding one element inside an exposed shadow root."""

    host_selector: str = Field(..., description="Selector for the shadow host element.")
    selector: str = Field(..., description="Selector inside the shadow root.")
    timeout: float = Field(default=3, ge=0, le=MAX_WAIT_SECONDS)


class ShadowFindAllInput(TabScopedInput):
    """Input schema for repeated elements inside an exposed shadow root."""

    host_selector: str = Field(..., description="Selector for the shadow host element.")
    selector: str = Field(..., description="Selector inside the shadow root.")
    limit: int = Field(default=20, ge=1, le=100)
    include_html: bool = Field(default=False)


@define_tool(
    name="shadow_find",
    title="Find Shadow Element",
    description="Find one element inside a shadow root exposed by the supported DrissionPage runtime.",
    input_schema=ShadowFindInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=ShadowFindData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to find shadow element '{args.selector}': {e}"
    )(exc),
)
async def shadow_find(
    context: DrissionPageContext, args: ShadowFindInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.frames.shadow_find(
        host_selector=args.host_selector, selector=args.selector, timeout=args.timeout
    )
    return ToolOutcome().add_result(f"Found shadow element: {args.selector}", **result)


@define_tool(
    name="shadow_find_all",
    title="Find Shadow Elements",
    description="Find repeated elements inside a shadow root exposed by the supported DrissionPage runtime.",
    input_schema=ShadowFindAllInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=ShadowFindAllData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to find shadow elements '{args.selector}': {e}"
    )(exc),
)
async def shadow_find_all(
    context: DrissionPageContext, args: ShadowFindAllInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.frames.shadow_find_all(
        host_selector=args.host_selector,
        selector=args.selector,
        limit=args.limit,
        include_html=args.include_html,
    )
    return ToolOutcome().add_result(
        f"Found {result['returned']} of {result['count']} shadow elements",
        **with_response_meta(result),
    )
