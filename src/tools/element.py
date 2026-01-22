"""Element interaction tools for DrissionPage MCP."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .base import define_tool, ToolType

if TYPE_CHECKING:
    from ..context import DrissionPageContext
    from ..response import ToolResponse


class FindElementInput(BaseModel):
    """Input schema for finding elements."""
    selector: str = Field(..., description="CSS selector or XPath to find the element")
    timeout: int = Field(default=10, description="Timeout in seconds to wait for element")


class ClickElementInput(BaseModel):
    """Input schema for clicking elements."""
    selector: str = Field(..., description="CSS selector or XPath to find the element")
    timeout: int = Field(default=10, description="Timeout in seconds to wait for element")


class TypeTextInput(BaseModel):
    """Input schema for typing text."""
    selector: str = Field(..., description="CSS selector or XPath to find the input element")
    text: str = Field(..., description="Text to type into the element")
    timeout: int = Field(default=10, description="Timeout in seconds to wait for element")


@define_tool(
    name="element_find",
    title="Find Element",
    description="Find an element on the page using CSS selector or XPath",
    input_schema=FindElementInput,
    tool_type=ToolType.READ_ONLY
)
async def find_element(
    context: "DrissionPageContext",
    args: FindElementInput,
    response: "ToolResponse"
) -> None:
    """Find an element on the page."""
    try:
        tab = context.current_tab_or_die()
        element = await tab.find_element(args.selector, timeout=args.timeout)
        
        response.add_code(f"element = page.ele('{args.selector}')")
        response.add_result(f"Found element: {element}")
        
    except Exception as e:
        response.add_error(f"Failed to find element '{args.selector}': {str(e)}")


@define_tool(
    name="element_click",
    title="Click Element",
    description="Click on an element found by CSS selector or XPath",
    input_schema=ClickElementInput,
    tool_type=ToolType.DESTRUCTIVE
)
async def click_element(
    context: "DrissionPageContext",
    args: ClickElementInput,
    response: "ToolResponse"
) -> None:
    """Click on an element."""
    try:
        tab = context.current_tab_or_die()
        await tab.click_element(args.selector, timeout=args.timeout)
        
        response.add_code(f"page.ele('{args.selector}').click()")
        response.add_result(f"Successfully clicked element: {args.selector}")
        response.set_include_snapshot(True)
        
    except Exception as e:
        response.add_error(f"Failed to click element '{args.selector}': {str(e)}")


@define_tool(
    name="element_type",
    title="Type Text",
    description="Type text into an input element",
    input_schema=TypeTextInput,
    tool_type=ToolType.DESTRUCTIVE
)
async def type_text(
    context: "DrissionPageContext",
    args: TypeTextInput,
    response: "ToolResponse"
) -> None:
    """Type text into an element."""
    try:
        tab = context.current_tab_or_die()
        await tab.type_text(args.selector, args.text, timeout=args.timeout)
        
        response.add_code(f"page.ele('{args.selector}').input('{args.text}')")
        response.add_result(f"Successfully typed text into element: {args.selector}")
        response.set_include_snapshot(True)
        
    except Exception as e:
        response.add_error(f"Failed to type text into element '{args.selector}': {str(e)}")


# Export all tools
tools = [find_element, click_element, type_text]