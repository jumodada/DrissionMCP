"""Common tools for DrissionPage MCP."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .base import define_tool, ToolType

if TYPE_CHECKING:
    from ..context import DrissionPageContext
    from ..response import ToolResponse


class ResizeInput(BaseModel):
    """Input schema for resize tool."""
    width: int = Field(..., description="Width of the browser window")
    height: int = Field(..., description="Height of the browser window")


class ScreenshotInput(BaseModel):
    """Input schema for screenshot tool."""
    full_page: bool = Field(default=False, description="Take a full page screenshot")


class ClickCoordinatesInput(BaseModel):
    """Input schema for clicking at coordinates."""
    x: int = Field(..., description="X coordinate to click")
    y: int = Field(..., description="Y coordinate to click")
    element: str = Field("", description="Human-readable element description for permission")


class EmptyInput(BaseModel):
    """Empty input schema."""
    pass

@define_tool(
    name="page_resize",
    title="Resize Window",
    description="Resize the browser window to specified dimensions",
    input_schema=ResizeInput,
    tool_type=ToolType.DESTRUCTIVE
)
async def resize(
    context: "DrissionPageContext", 
    args: ResizeInput, 
    response: "ToolResponse"
) -> None:
    """Resize the browser window."""
    try:
        tab = context.current_tab_or_die()
        await tab.resize(args.width, args.height)
        
        response.add_code(f"page.set.window.size({args.width}, {args.height})")
        response.add_result(f"Successfully resized window to {args.width}x{args.height}")
        
    except Exception as e:
        response.add_error(f"Failed to resize window: {str(e)}")


@define_tool(
    name="page_screenshot",
    title="Take Screenshot",
    description="Take a screenshot of the current page",
    input_schema=ScreenshotInput,
    tool_type=ToolType.READ_ONLY
)
async def screenshot(
    context: "DrissionPageContext",
    args: ScreenshotInput,
    response: "ToolResponse" 
) -> None:
    """Take a screenshot."""
    try:
        tab = context.current_tab_or_die()
        screenshot_data = await tab.screenshot(full_page=args.full_page)
        
        response.add_code(f"page.get_screenshot(full_page={args.full_page})")
        response.add_screenshot(screenshot_data)
        
    except Exception as e:
        response.add_error(f"Failed to take screenshot: {str(e)}")


@define_tool(
    name="page_click_xy",
    title="Click Coordinates",
    description="Click at specific coordinates on the page",
    input_schema=ClickCoordinatesInput,
    tool_type=ToolType.DESTRUCTIVE
)
async def click_coordinates(
    context: "DrissionPageContext",
    args: ClickCoordinatesInput,
    response: "ToolResponse"
) -> None:
    """Click at coordinates."""
    try:
        tab = context.current_tab_or_die()
        await tab.click(args.x, args.y)
        
        response.add_code(f"page.actions.click(({args.x}, {args.y}))")
        response.add_result(f"Successfully clicked at coordinates ({args.x}, {args.y})")
        response.set_include_snapshot(True)
        
    except Exception as e:
        response.add_error(f"Failed to click at ({args.x}, {args.y}): {str(e)}")


@define_tool(
    name="page_close",
    title="Close Browser",
    description="Close the current page/browser",
    input_schema=EmptyInput,
    tool_type=ToolType.DESTRUCTIVE
)
async def close(
    context: "DrissionPageContext",
    args: EmptyInput,
    response: "ToolResponse"
) -> None:
    """Close the browser."""
    try:
        await context.close_browser()
        
        response.add_code("page.quit()")
        response.add_result("Successfully closed browser")
        
    except Exception as e:
        response.add_error(f"Failed to close browser: {str(e)}")


@define_tool(
    name="page_get_url",
    title="Get Current URL",
    description="Get the current URL of the page",
    input_schema=EmptyInput,
    tool_type=ToolType.READ_ONLY
)
async def get_url(
    context: "DrissionPageContext",
    args: EmptyInput,
    response: "ToolResponse"
) -> None:
    """Get current URL."""
    try:
        tab = context.current_tab_or_die()
        url = tab.url
        
        response.add_code("page.url")
        response.add_result(f"Current URL: {url}")
        
    except Exception as e:
        response.add_error(f"Failed to get URL: {str(e)}")


# Export all tools
tools = [resize, screenshot, click_coordinates, close, get_url]