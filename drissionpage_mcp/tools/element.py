"""Element interaction tools for DrissionPage MCP."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, StrictInt

from ..browser.elements import ClickUnsupportedError
from ..browser.targeting import DomTarget
from ..limits import MAX_WAIT_SECONDS
from ..metadata import with_response_meta
from ..response_json import json_safe_value
from ..selector import normalize_selector
from ..target import ElementTargetArg, PageOrElementTargetArg, target_label
from ..tool_outputs import (
    CapabilityProbe,
    ElementClickData,
    ElementFindAllData,
    ElementFindData,
    ElementGetAttributeData,
    ElementGetHtmlData,
    ElementGetPropertyData,
    ElementGetTextData,
    ElementStateData,
    ElementTypeData,
)
from ._observe import maybe_observe, observed_changes
from .base import TabScopedInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext


class FindElementInput(TabScopedInput):
    """Input schema for finding elements."""

    selector: ElementTargetArg = Field(
        ...,
        description="CSS selector or XPath to find the element. Bare selectors are CSS; use text:... for text matching or explicit tag:/css:/xpath:/@attr locators.",
    )
    timeout: float = Field(
        default=3,
        ge=0,
        le=MAX_WAIT_SECONDS,
        description="Timeout in seconds to wait for element",
    )


class FindAllElementsInput(TabScopedInput):
    """Input schema for bounded multi-element extraction."""

    selector: ElementTargetArg = Field(
        ...,
        description="CSS selector, XPath, or explicit DrissionPage locator for repeated elements. Bare selectors are CSS.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of matched elements to return",
    )
    include_html: bool = Field(
        default=False,
        description="Include bounded outerHTML excerpts for each returned element",
    )


class ClickElementInput(TabScopedInput):
    """Input schema for clicking elements."""

    selector: ElementTargetArg = Field(
        ...,
        description="CSS selector or XPath to find the element. Bare selectors are CSS; use text:... for text matching or explicit tag:/css:/xpath:/@attr locators.",
    )
    timeout: float = Field(
        default=10,
        ge=0,
        le=MAX_WAIT_SECONDS,
        description="Timeout in seconds to wait for element",
    )
    observe: bool = Field(
        default=False, description="Return a compact before/after page change summary."
    )
    button: Literal["left", "right", "middle"] = Field(
        default="left", description="Native pointer button to use."
    )
    click_count: Annotated[StrictInt, Field(ge=1, le=2)] = Field(
        default=1, description="Native click count; 2 requests double-click semantics."
    )


class TypeTextInput(TabScopedInput):
    """Input schema for typing text."""

    selector: ElementTargetArg = Field(
        ...,
        description="CSS selector or XPath to find the input element. Bare selectors are CSS; use text:... for text matching or explicit tag:/css:/xpath:/@attr locators.",
    )
    text: str = Field(..., description="Text to type into the element")
    timeout: float = Field(
        default=10,
        ge=0,
        le=MAX_WAIT_SECONDS,
        description="Timeout in seconds to wait for element",
    )
    clear: bool = Field(
        default=True, description="Clear existing input content before typing"
    )
    observe: bool = Field(
        default=False, description="Return a compact before/after page change summary."
    )


class GetTextInput(TabScopedInput):
    """Input schema for getting text."""

    selector: PageOrElementTargetArg = Field(
        default="",
        description="CSS selector or XPath; empty means whole page. Bare selectors are CSS; use text:... for text matching.",
    )


class GetAttributeInput(TabScopedInput):
    """Input schema for getting an element attribute."""

    selector: ElementTargetArg = Field(
        ...,
        description="CSS selector or XPath to find the element. Bare selectors are CSS; use text:... for text matching or explicit tag:/css:/xpath:/@attr locators.",
    )
    attribute: str = Field(..., description="Attribute name to retrieve")


class GetPropertyInput(TabScopedInput):
    """Input schema for getting a live DOM property."""

    selector: ElementTargetArg = Field(
        ...,
        description="CSS selector or XPath to find the element. Bare selectors are CSS; use text:... for text matching or explicit tag:/css:/xpath:/@attr locators.",
    )
    property: str = Field(..., description="DOM property to retrieve, e.g. value")


class GetHtmlInput(TabScopedInput):
    """Input schema for getting HTML."""

    selector: PageOrElementTargetArg = Field(
        default="",
        description="CSS selector or XPath; empty means whole page. Bare selectors are CSS; use text:... for text matching.",
    )


class ElementStateInput(TabScopedInput):
    """Input schema for inspecting element state and geometry."""

    selector: ElementTargetArg = Field(
        ...,
        description="String locator or structured selector/accessibility target with frame and shadow scope.",
    )
    timeout: float = Field(default=3, ge=0, le=MAX_WAIT_SECONDS)


@define_tool(
    name="element_find",
    title="Find Element",
    description="Find an element on the page using CSS selector or XPath. Bare selectors are treated as CSS; use text:... for text matching.",
    input_schema=FindElementInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=ElementFindData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to find element '{target_label(args.selector)}': {e}"
    )(exc),
)
async def find_element(
    context: "DrissionPageContext", args: FindElementInput
) -> "ToolOutcome":
    """Find an element on the page."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    element = await tab.elements.find(args.selector, timeout=args.timeout)
    outcome.add_result(f"Found element: {target_label(args.selector)}", element=element)
    return outcome


@define_tool(
    name="element_find_all",
    title="Find All Elements",
    description="Find multiple matching elements with bounded text/attribute summaries and recommended selectors for repeated lists, cards, and tables.",
    input_schema=FindAllElementsInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=ElementFindAllData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to find elements '{target_label(args.selector)}': {e}"
    )(exc),
)
async def find_all_elements(
    context: "DrissionPageContext", args: FindAllElementsInput
) -> "ToolOutcome":
    """Find multiple elements on the page."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.elements.find_all(
        args.selector, limit=args.limit, include_html=args.include_html
    )
    outcome.add_result(
        f"Found {result['returned']} of {result['count']} elements: {target_label(args.selector)}",
        **with_response_meta(result),
    )
    return outcome


@define_tool(
    name="element_click",
    title="Click Element",
    description="Click an element found by CSS selector or XPath. Bare selectors are treated as CSS; use text:... for text matching.",
    input_schema=ClickElementInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=ElementClickData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to click element '{target_label(args.selector)}': {e}"
    )(exc),
)
async def click_element(
    context: "DrissionPageContext", args: ClickElementInput
) -> "ToolOutcome":
    """Click on an element."""
    outcome = ToolOutcome()
    _validate_click_capability(context, args)
    tab = context.current_tab_or_die()
    metadata = DomTarget.from_input(args.selector).metadata()
    before = await maybe_observe(tab, args.observe)
    try:
        if args.button == "left" and args.click_count == 1:
            await tab.elements.click(args.selector, timeout=args.timeout)
        else:
            await tab.elements.click(
                args.selector,
                timeout=args.timeout,
                button=args.button,
                click_count=args.click_count,
            )
    except ClickUnsupportedError as exc:
        context.record_capability_probe(
            _click_capability_probe(
                name=_click_capability_name(args),
                status="unsupported",
                evidence_source="runtime_probe",
                reason_code=exc.reason_code,
            )
        )
        raise
    changes = await observed_changes(tab, before)
    data = {
        **metadata,
        "url": tab.url,
        "button": args.button,
        "click_count": args.click_count,
    }
    if changes is not None:
        data["changes"] = changes
    outcome.add_result(
        f"Successfully clicked element: {target_label(args.selector)}", **data
    )
    return outcome


def _click_capability_probe(
    *,
    name: str,
    status: Literal["unsupported"],
    evidence_source: Literal["runtime_probe"],
    reason_code: str | None = None,
) -> CapabilityProbe:
    return CapabilityProbe(
        name=name,
        status=status,
        evidence_source=evidence_source,
        reason_code=reason_code,
        checked_at=datetime.now(timezone.utc),
    )


def _validate_click_capability(
    context: "DrissionPageContext", args: ClickElementInput
) -> None:
    """Reject a recorded unsupported variant before tab or DOM access."""

    if args.button == "left" and args.click_count == 1:
        return
    capability_name = _click_capability_name(args)
    for capability in context.capability_set().capabilities:
        if capability.name == capability_name and capability.status in {
            "unsupported",
            "degraded",
        }:
            raise ClickUnsupportedError(
                capability.reason_code or "RECORDED_CAPABILITY_UNAVAILABLE"
            )


def _click_capability_name(args: ClickElementInput) -> str:
    if args.button == "left" and args.click_count == 2:
        return "element.click.double"
    if args.click_count == 1:
        return f"element.click.{args.button}"
    return f"element.click.{args.button}_double"


@define_tool(
    name="element_type",
    title="Type Text",
    description="Type text into an input element",
    input_schema=TypeTextInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=ElementTypeData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to type text into element '{target_label(args.selector)}': {e}"
    )(exc),
)
async def type_text(
    context: "DrissionPageContext", args: TypeTextInput
) -> "ToolOutcome":
    """Type text into an element."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    before = await maybe_observe(tab, args.observe)
    metadata = await tab.elements.type(
        args.selector, args.text, timeout=args.timeout, clear=args.clear
    )
    if metadata is None:
        metadata = DomTarget.from_input(args.selector).metadata()
    changes = await observed_changes(tab, before)
    data = {**metadata, "typed": True, "cleared": args.clear}
    if changes is not None:
        data["changes"] = changes
    outcome.add_result(
        f"Successfully typed text into element: {target_label(args.selector)}", **data
    )
    return outcome


@define_tool(
    name="element_get_text",
    title="Get Text",
    description="Get text from an element or the whole page",
    input_schema=GetTextInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=ElementGetTextData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to get text from '{target_label(args.selector) if args.selector else 'page'}': {e}"
    )(exc),
)
async def get_text(context: "DrissionPageContext", args: GetTextInput) -> "ToolOutcome":
    """Get text from an element or the page."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    metadata = _target_metadata(args.selector)
    text = await tab.elements.text(args.selector)
    outcome.add_result(text or "", text=text or "", **metadata)
    return outcome


@define_tool(
    name="element_get_attribute",
    title="Get Attribute",
    description="Get an attribute value from an element",
    input_schema=GetAttributeInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=ElementGetAttributeData,
    failure_message=lambda args, exc: (
        lambda e: (
            f"Failed to get attribute '{args.attribute}' from '{target_label(args.selector)}': {e}"
        )
    )(exc),
)
async def get_attribute(
    context: "DrissionPageContext", args: GetAttributeInput
) -> "ToolOutcome":
    """Get an attribute value from an element."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    value = await tab.elements.attribute(args.selector, args.attribute)
    outcome.add_result(
        "" if value is None else str(value),
        **DomTarget.from_input(args.selector).metadata(),
        attribute=args.attribute,
        value=value,
    )
    return outcome


@define_tool(
    name="element_get_property",
    title="Get Property",
    description="Get a live DOM property value from an element, such as an input's current value",
    input_schema=GetPropertyInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=ElementGetPropertyData,
    failure_message=lambda args, exc: (
        lambda e: (
            f"Failed to get property '{args.property}' from '{target_label(args.selector)}': {e}"
        )
    )(exc),
)
async def get_property(
    context: "DrissionPageContext", args: GetPropertyInput
) -> "ToolOutcome":
    """Get a live DOM property value from an element."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    value = await tab.elements.property(args.selector, args.property)
    outcome.add_result(
        "" if value is None else str(value),
        **DomTarget.from_input(args.selector).metadata(),
        property=args.property,
        value=_json_safe(value),
    )
    return outcome


@define_tool(
    name="element_get_html",
    title="Get HTML",
    description="Get HTML from an element or the whole page",
    input_schema=GetHtmlInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=ElementGetHtmlData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to get HTML from '{target_label(args.selector) if args.selector else 'page'}': {e}"
    )(exc),
)
async def get_html(context: "DrissionPageContext", args: GetHtmlInput) -> "ToolOutcome":
    """Get HTML from an element or the page."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    metadata = _target_metadata(args.selector)
    html = await tab.elements.html(args.selector)
    outcome.add_result(html or "", html=html or "", **metadata)
    return outcome


@define_tool(
    name="element_state_get",
    title="Get Element State",
    description="Return DrissionPage element state and page/viewport geometry for a selector or accessibility target.",
    input_schema=ElementStateInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=ElementStateData,
    failure_message=lambda args, exc: (
        f"Failed to inspect element '{target_label(args.selector)}': {exc}"
    ),
)
async def element_state_get(
    context: "DrissionPageContext", args: ElementStateInput
) -> "ToolOutcome":
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    state = await tab.elements.state(args.selector, timeout=args.timeout)
    outcome.add_result(f"Inspected element: {target_label(args.selector)}", **state)
    return outcome


def _target_metadata(target: ElementTargetArg) -> dict[str, object]:
    if not target:
        return normalize_selector("").metadata()
    return DomTarget.from_input(target).metadata()


def _json_safe(value):
    return json_safe_value(value)
