"""Wait operation tools for DrissionPage MCP."""

from typing import TYPE_CHECKING, Literal

from pydantic import Field

from ..browser.targeting import DomTarget
from ..limits import MAX_WAIT_SECONDS
from ..target import ElementTargetArg, PageOrElementTargetArg, target_label
from ..tool_outputs import (
    WaitForElementData,
    WaitForUrlData,
    WaitTimeData,
    WaitUntilData,
)
from .base import TabScopedInput, ToolInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext


class WaitElementInput(TabScopedInput):
    """Input schema for waiting for elements."""

    selector: ElementTargetArg = Field(
        ...,
        description="CSS selector or XPath to wait for. Bare selectors are CSS; use text:... for text matching or explicit tag:/css:/xpath:/@attr locators.",
    )
    timeout: float = Field(
        default=10, ge=0, le=MAX_WAIT_SECONDS, description="Timeout in seconds"
    )


class WaitTimeInput(ToolInput):
    """Input schema for waiting a specific time."""

    seconds: float = Field(
        ..., ge=0, le=MAX_WAIT_SECONDS, description="Number of seconds to wait"
    )


class WaitUrlInput(TabScopedInput):
    """Input schema for waiting for URL changes."""

    url_pattern: str = Field(
        ..., description="Substring or pattern expected in the current URL"
    )
    timeout: float = Field(
        default=10, ge=0, le=MAX_WAIT_SECONDS, description="Timeout in seconds"
    )


class WaitUntilInput(TabScopedInput):
    """Input schema for generalized observable waits."""

    condition: Literal[
        "present",
        "visible",
        "hidden",
        "detached",
        "clickable",
        "stable",
        "text_contains",
        "text_matches",
        "url_contains",
        "url_matches",
        "attribute_equals",
        "attribute_nonempty",
        "property_equals",
        "property_nonempty",
    ] = Field(..., description="Condition to wait for")
    selector: PageOrElementTargetArg = Field(
        default="",
        description="CSS/XPath/DrissionPage locator for element or text conditions",
    )
    value: str = Field(
        default="",
        description="Expected value or substring/regular expression, depending on condition",
    )
    name: str = Field(
        default="",
        description="Attribute or property name for attribute/property conditions",
    )
    timeout: float = Field(
        default=10, ge=0, le=MAX_WAIT_SECONDS, description="Timeout in seconds"
    )
    interval: float = Field(
        default=0.1, ge=0.01, le=5, description="Polling interval in seconds"
    )
    stable_ms: int = Field(
        default=300,
        ge=0,
        le=5000,
        description="Element stability window for the stable condition",
    )


@define_tool(
    name="wait_for_element",
    title="Wait for Element",
    description="Wait for an element to appear on the page. Bare selectors are treated as CSS; use text:... for text matching.",
    input_schema=WaitElementInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=WaitForElementData,
    failure_message=lambda args, exc: (
        lambda e: f"Element '{target_label(args.selector)}' did not appear within {args.timeout:g} seconds: {e}"
    )(exc),
)
async def wait_for_element(
    context: "DrissionPageContext", args: WaitElementInput
) -> "ToolOutcome":
    """Wait for an element to appear."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    found = await tab.waits.element(args.selector, timeout=args.timeout)
    if not found:
        raise TimeoutError(f"Element '{target_label(args.selector)}' not found")
    outcome.add_result(
        f"Element '{target_label(args.selector)}' appeared within {args.timeout:g} seconds",
        **DomTarget.from_input(args.selector).metadata(),
        found=True,
        timeout=args.timeout,
    )
    return outcome


@define_tool(
    name="wait_for_url",
    title="Wait for URL",
    description="Wait for the current URL to contain a substring",
    input_schema=WaitUrlInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=WaitForUrlData,
    failure_message=lambda args, exc: (
        lambda e: f"URL did not match '{args.url_pattern}' within {args.timeout:g} seconds: {e}"
    )(exc),
)
async def wait_for_url(
    context: "DrissionPageContext", args: WaitUrlInput
) -> "ToolOutcome":
    """Wait for URL to match a pattern."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    matched = await tab.waits.url(args.url_pattern, timeout=args.timeout)
    if not matched:
        raise TimeoutError(f"URL did not contain '{args.url_pattern}'")
    outcome.add_result(
        f"URL matched '{args.url_pattern}' within {args.timeout:g} seconds",
        url_pattern=args.url_pattern,
        matched=True,
        url=tab.url,
        timeout=args.timeout,
    )
    return outcome


@define_tool(
    name="wait_time",
    title="Wait Time",
    description="Wait for a specific amount of time",
    input_schema=WaitTimeInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=WaitTimeData,
    failure_message=lambda args, exc: "Failed to wait: " + str(exc),
)
async def wait_time(
    context: "DrissionPageContext", args: WaitTimeInput
) -> "ToolOutcome":
    """Wait for a specific time."""
    outcome = ToolOutcome()
    await context.wait(args.seconds)
    outcome.add_result(
        f"Waited for {args.seconds} seconds", waited_seconds=args.seconds
    )
    return outcome


@define_tool(
    name="wait_until",
    title="Wait Until",
    description="Wait for observable page state: element present/visible/hidden/detached/clickable/stable, text contains/matches, or URL contains/matches.",
    input_schema=WaitUntilInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=WaitUntilData,
    failure_message=lambda args, exc: (
        lambda e: f"Condition '{args.condition}' was not met within {args.timeout:g} seconds: {e}"
    )(exc),
)
async def wait_until(
    context: "DrissionPageContext", args: WaitUntilInput
) -> "ToolOutcome":
    """Wait until an observable condition is satisfied."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.waits.until(
        condition=args.condition,
        selector=args.selector,
        value=args.value,
        name=args.name,
        timeout=args.timeout,
        interval=args.interval,
        stable_ms=args.stable_ms,
    )
    outcome.add_result(
        f"Condition '{args.condition}' matched within {args.timeout:g} seconds", **result
    )
    return outcome
