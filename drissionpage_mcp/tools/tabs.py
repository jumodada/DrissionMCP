"""Browser tab management tools for DrissionPage MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from ..tool_outputs import TabCloseData, TabListData, TabSwitchData
from .base import EmptyInput, ToolInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext


class TabIdInput(ToolInput):
    """Input schema for tab id based operations."""

    tab_id: str = Field(
        ...,
        description="MCP tab id from tab_list, or the underlying DrissionPage native tab id.",
    )


@define_tool(
    name="tab_list",
    title="List Tabs",
    description="List browser tabs tracked by the current DrissionPage MCP session.",
    input_schema=EmptyInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=TabListData,
    failure_message=lambda args, exc: "Failed to list tabs: " + str(exc),
)
async def tab_list(context: DrissionPageContext, args: EmptyInput) -> ToolOutcome:
    """List current browser tabs."""
    await context.sync_tabs()
    summaries = context.tab_summaries()
    active_tab = next((tab for tab in summaries if tab.get("active")), None)
    return ToolOutcome().add_result(
        f"Found {len(summaries)} browser tabs",
        tabs=summaries,
        count=len(summaries),
        active_tab_id=str(active_tab.get("id", "")) if active_tab else "",
    )


@define_tool(
    name="tab_switch",
    title="Switch Tab",
    description="Switch the active browser tab by id from tab_list.",
    input_schema=TabIdInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=TabSwitchData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to switch to tab {args.tab_id!r}: {e}"
    )(exc),
)
async def tab_switch(context: DrissionPageContext, args: TabIdInput) -> ToolOutcome:
    """Switch active browser tab."""
    tab = await context.switch_tab(args.tab_id)
    summaries = context.tab_summaries()
    active = next(
        (item for item in summaries if item.get("id") == tab.mcp_tab_id),
        tab.summary(active=True),
    )
    return ToolOutcome().add_result(
        f"Switched to tab: {tab.mcp_tab_id}",
        tab=active,
        tab_id=tab.mcp_tab_id,
        url=tab.url,
    )


@define_tool(
    name="tab_close",
    title="Close Tab",
    description="Close a browser tab by id from tab_list without closing the whole browser.",
    input_schema=TabIdInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=TabCloseData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to close tab {args.tab_id!r}: {e}"
    )(exc),
)
async def tab_close(context: DrissionPageContext, args: TabIdInput) -> ToolOutcome:
    """Close a browser tab."""
    await context.close_tab_by_id(args.tab_id)
    summaries = context.tab_summaries()
    active_tab = next((tab for tab in summaries if tab.get("active")), None)
    return ToolOutcome().add_result(
        f"Closed tab: {args.tab_id}",
        closed=True,
        tab_id=args.tab_id,
        remaining_count=len(summaries),
        active_tab_id=str(active_tab.get("id", "")) if active_tab else "",
    )
