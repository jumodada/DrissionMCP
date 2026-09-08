"""Additional page and element interaction tools for DrissionPage MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field

from ..limits import MAX_WAIT_SECONDS
from ..target import ElementTargetArg, target_label
from ..tool_outputs import (
    ElementCheckData,
    ElementHoverData,
    ElementScrollIntoViewData,
    ElementSelectData,
    KeyboardPressData,
    PageScrollData,
)
from .base import TabScopedInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext
ScrollDirection = Literal[
    "down", "up", "left", "right", "top", "bottom", "half", "position"
]
SelectBy = Literal["value", "text", "index"]


class PageScrollInput(TabScopedInput):
    """Input schema for page scrolling."""

    direction: ScrollDirection = Field(
        default="down",
        description="Scroll direction or target: down, up, left, right, top, bottom, half, position.",
    )
    pixels: int = Field(
        default=300,
        ge=0,
        le=20000,
        description="Pixel distance for directional scrolling.",
    )
    x: int = Field(default=0, ge=0, description="X coordinate for direction=position.")
    y: int = Field(default=0, ge=0, description="Y coordinate for direction=position.")


class ElementScrollIntoViewInput(TabScopedInput):
    """Input schema for scrolling an element into view."""

    selector: ElementTargetArg = Field(
        ..., description="String locator or structured element target."
    )
    center: bool = Field(
        default=True, description="Center the element in the viewport."
    )
    timeout: float = Field(default=10, ge=0, le=MAX_WAIT_SECONDS)


class ElementHoverInput(TabScopedInput):
    """Input schema for hovering an element."""

    selector: ElementTargetArg = Field(
        ..., description="String locator or structured element target."
    )
    timeout: float = Field(default=10, ge=0, le=MAX_WAIT_SECONDS)
    offset_x: int | None = Field(default=None, description="Optional hover X offset.")
    offset_y: int | None = Field(default=None, description="Optional hover Y offset.")


class KeyboardPressInput(TabScopedInput):
    """Input schema for sending keys to the active element."""

    keys: str = Field(..., description="Text or DrissionPage key string to send.")
    interval: float = Field(
        default=0,
        ge=0,
        le=2,
        description="Optional interval between key events in seconds.",
    )


class ElementSelectInput(TabScopedInput):
    """Input schema for selecting an option."""

    selector: ElementTargetArg = Field(
        ..., description="String locator or structured select target."
    )
    value: str = Field(..., description="Option value, text, or index string.")
    by: SelectBy = Field(
        default="value", description="Select by value, text, or index."
    )
    timeout: float = Field(default=10, ge=0, le=MAX_WAIT_SECONDS)


class ElementCheckInput(TabScopedInput):
    """Input schema for checkbox/radio state."""

    selector: ElementTargetArg = Field(
        ..., description="String locator or structured checkbox target."
    )
    checked: bool = Field(default=True, description="Desired checked state.")
    by_js: bool = Field(default=False, description="Use JavaScript-backed checking.")
    timeout: float = Field(default=10, ge=0, le=MAX_WAIT_SECONDS)


@define_tool(
    name="page_scroll",
    title="Scroll Page",
    description="Scroll the current page by direction or to a position.",
    input_schema=PageScrollInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=PageScrollData,
    failure_message=lambda args, exc: "Failed to scroll page: " + str(exc),
)
async def page_scroll(
    context: DrissionPageContext, args: PageScrollInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.interaction.scroll_page(
        direction=args.direction, pixels=args.pixels, x=args.x, y=args.y
    )
    return ToolOutcome().add_result(f"Scrolled page {args.direction}", **result)


@define_tool(
    name="element_scroll_into_view",
    title="Scroll Element Into View",
    description="Scroll an element into the viewport before a later action.",
    input_schema=ElementScrollIntoViewInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=ElementScrollIntoViewData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to scroll element '{target_label(args.selector)}' into view: {e}"
    )(exc),
)
async def element_scroll_into_view(
    context: DrissionPageContext, args: ElementScrollIntoViewInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.interaction.scroll_element_into_view(
        args.selector, center=args.center, timeout=args.timeout
    )
    return ToolOutcome().add_result(
        f"Scrolled element into view: {target_label(args.selector)}", **result
    )


@define_tool(
    name="element_hover",
    title="Hover Element",
    description="Move the mouse over an element.",
    input_schema=ElementHoverInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=ElementHoverData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to hover element '{target_label(args.selector)}': {e}"
    )(exc),
)
async def element_hover(
    context: DrissionPageContext, args: ElementHoverInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.interaction.hover_element(
        args.selector,
        timeout=args.timeout,
        offset_x=args.offset_x,
        offset_y=args.offset_y,
    )
    return ToolOutcome().add_result(f"Hovered element: {target_label(args.selector)}", **result)


@define_tool(
    name="keyboard_press",
    title="Keyboard Press",
    description=(
        "Send keyboard text/keys to the active page element without echoing the "
        "input in the result."
    ),
    input_schema=KeyboardPressInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=KeyboardPressData,
    failure_message=lambda args, exc: "Failed to send keyboard keys: " + str(exc),
)
async def keyboard_press(
    context: DrissionPageContext, args: KeyboardPressInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.interaction.keyboard_press(args.keys, interval=args.interval)
    return ToolOutcome().add_result("Sent keyboard keys", **result)


@define_tool(
    name="element_select",
    title="Select Element Option",
    description="Select an option from a select element by value, text, or index.",
    input_schema=ElementSelectInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=ElementSelectData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to select option for '{target_label(args.selector)}': {e}"
    )(exc),
)
async def element_select(
    context: DrissionPageContext, args: ElementSelectInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.interaction.select_element(
        args.selector, value=args.value, by=args.by, timeout=args.timeout
    )
    return ToolOutcome().add_result(f"Selected option in: {target_label(args.selector)}", **result)


@define_tool(
    name="element_check",
    title="Check Element",
    description="Set a checkbox or radio element to checked/unchecked.",
    input_schema=ElementCheckInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=ElementCheckData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to set check state for '{target_label(args.selector)}': {e}"
    )(exc),
)
async def element_check(
    context: DrissionPageContext, args: ElementCheckInput
) -> ToolOutcome:
    tab = context.current_tab_or_die()
    result = await tab.interaction.check_element(
        args.selector, checked=args.checked, by_js=args.by_js, timeout=args.timeout
    )
    return ToolOutcome().add_result(f"Set check state for: {target_label(args.selector)}", **result)
