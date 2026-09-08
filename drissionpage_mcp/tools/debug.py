"""Debugging and observability tools for DrissionPage MCP."""

from typing import TYPE_CHECKING, Literal

from pydantic import Field

from ..tool_outputs import ConsoleLogsData
from .base import TabScopedInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext
ConsoleLevel = Literal["all", "error", "warning", "warn", "info", "log"]


class ConsoleLogsInput(TabScopedInput):
    """Input schema for reading current-tab console logs."""

    level: ConsoleLevel = Field(
        default="all",
        description="Console level filter: all, error, warning, warn, info, or log.",
    )
    since: int = Field(
        default=-1,
        ge=-1,
        description="Return only log entries with index greater than this cursor.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of console entries to return.",
    )


@define_tool(
    name="page_console_logs",
    title="Console Logs",
    description="Read bounded browser console messages from the current tab. Supports level filtering, cursor pagination, and a maximum result limit.",
    input_schema=ConsoleLogsInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=ConsoleLogsData,
    failure_message=lambda args, exc: "Failed to read console logs: " + str(exc),
)
async def page_console_logs(
    context: "DrissionPageContext", args: ConsoleLogsInput
) -> "ToolOutcome":
    """Return current-tab console logs."""
    tab = context.current_tab_or_die()
    result = await tab.observation.console_logs(
        level=args.level, since=args.since, limit=args.limit
    )
    return ToolOutcome().add_result(
        f"Read {result['count']} console log{('' if result['count'] == 1 else 's')}",
        **result,
    )
