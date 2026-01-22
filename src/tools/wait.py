"""Wait operation tools for DrissionPage MCP."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .base import define_tool, ToolType

if TYPE_CHECKING:
    from ..context import DrissionPageContext
    from ..response import ToolResponse


class WaitElementInput(BaseModel):
    """Input schema for waiting for elements."""
    selector: str = Field(..., description="CSS selector or XPath to wait for")
    timeout: int = Field(default=10, description="Timeout in seconds")


class WaitTimeInput(BaseModel):
    """Input schema for waiting a specific time."""
    seconds: float = Field(..., description="Number of seconds to wait")


@define_tool(
    name="wait_for_element",
    title="Wait for Element",
    description="Wait for an element to appear on the page",
    input_schema=WaitElementInput,
    tool_type=ToolType.READ_ONLY
)
async def wait_for_element(
    context: "DrissionPageContext",
    args: WaitElementInput,
    response: "ToolResponse"
) -> None:
    """Wait for an element to appear."""
    try:
        tab = context.current_tab_or_die()
        await tab.wait_for_element(args.selector, timeout=args.timeout)
        
        response.add_code(f"page.wait.ele_loaded('{args.selector}', timeout={args.timeout})")
        response.add_result(f"Element '{args.selector}' appeared within {args.timeout} seconds")
        
    except Exception as e:
        response.add_error(f"Element '{args.selector}' did not appear within {args.timeout} seconds: {str(e)}")


@define_tool(
    name="wait_time",
    title="Wait Time",
    description="Wait for a specific amount of time",
    input_schema=WaitTimeInput,
    tool_type=ToolType.READ_ONLY
)
async def wait_time(
    context: "DrissionPageContext",
    args: WaitTimeInput,
    response: "ToolResponse"
) -> None:
    """Wait for a specific time."""
    try:
        await context.wait(args.seconds)
        
        response.add_code(f"time.sleep({args.seconds})")
        response.add_result(f"Waited for {args.seconds} seconds")
        
    except Exception as e:
        response.add_error(f"Failed to wait: {str(e)}")


# Export all tools
tools = [wait_for_element, wait_time]