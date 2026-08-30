"""Common tools for DrissionPage MCP."""

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field, StrictStr, StringConstraints

from ..metadata import with_response_meta
from ..policy import PolicyDeniedError, SafetyPolicy
from ..response_errors import ErrorCode
from ..response_media import build_screenshot_metadata
from ..target import ElementTargetArg
from ..tool_outputs import (
    BrowserCacheClearData,
    BrowserHeadersSetData,
    BrowserUserAgentSetData,
    PageAccessibilitySnapshotData,
    PageCloseData,
    PageEvaluateData,
    PageGetUrlData,
    PageObservation,
    PageResizeData,
    PageScreenshotData,
    PageScreenshotSaveData,
    PageSnapshotData,
)
from .base import EmptyInput, ToolInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext


HeaderName = Annotated[
    StrictStr,
    StringConstraints(
        min_length=1,
        max_length=256,
        pattern=r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$",
    ),
]
HeaderValue = Annotated[
    StrictStr,
    StringConstraints(max_length=8192, pattern=r"^[^\r\n]*$"),
]
UserAgentValue = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=2048),
]
PlatformValue = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=256),
]


class ResizeInput(ToolInput):
    """Input schema for resize tool."""

    width: int = Field(..., description="Width of the browser window")
    height: int = Field(..., description="Height of the browser window")


class ScreenshotInput(ToolInput):
    """Input schema for screenshot tool."""

    full_page: bool = Field(default=False, description="Take a full page screenshot")


class ScreenshotSaveInput(ScreenshotInput):
    """Input schema for saving screenshots to an approved local path."""

    path: str = Field(
        ...,
        description="Local file path under DP_MCP_SCREENSHOT_ROOT to save screenshot",
    )


class PageSnapshotInput(ToolInput):
    """Input schema for page snapshot tool."""

    include_html: bool = Field(
        default=False,
        description="Include bounded outerHTML excerpts for summarized elements",
    )
    max_elements: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum total headings/links/buttons/inputs/forms to return",
    )
    max_text_chars: int = Field(
        default=4000,
        ge=0,
        le=20000,
        description="Maximum page text excerpt characters to return",
    )


class PageAccessibilitySnapshotInput(ToolInput):
    """Input schema for a bounded accessibility-tree snapshot."""

    scope: ElementTargetArg | None = Field(
        default=None,
        description="Optional selector/accessibility element whose AX subtree is returned.",
    )
    max_nodes: int = Field(default=200, ge=1, le=1000)
    include_ignored: bool = False
    include_values: bool = Field(
        default=False,
        description="Return accessibility field values. Defaults to false to avoid leaking secrets.",
    )


class PageObserveInput(ToolInput):
    """Input schema for compact page observation."""

    max_texts: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of visible text samples to return",
    )
    max_text_chars: int = Field(
        default=160,
        ge=20,
        le=1000,
        description="Maximum characters per visible text sample",
    )


class PageEvaluateInput(ToolInput):
    """Input schema for bounded JavaScript evaluation."""

    script: str = Field(
        ...,
        description="JavaScript function body to run in the current page. Use return to provide a JSON-serializable result.",
    )
    args: list[Any] = Field(
        default_factory=list,
        description="JSON arguments passed to the JavaScript function body",
    )
    max_chars: int = Field(
        default=4000,
        ge=100,
        le=20000,
        description="Maximum serialized JSON characters returned in result",
    )


class BrowserHeadersSetInput(ToolInput):
    """Input schema for replacing extra HTTP request headers."""

    headers: dict[HeaderName, HeaderValue] = Field(
        ...,
        max_length=64,
        description="Extra request headers. An empty object clears all configured values.",
    )


class BrowserUserAgentSetInput(ToolInput):
    """Input schema for overriding the current tab's user agent."""

    user_agent: UserAgentValue
    platform: PlatformValue | None = Field(default=None)


@define_tool(
    name="page_resize",
    title="Resize Window",
    description="Resize the browser window to specified dimensions",
    input_schema=ResizeInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=PageResizeData,
    failure_message=lambda args, exc: "Failed to resize window: " + str(exc),
)
async def resize(context: "DrissionPageContext", args: ResizeInput) -> "ToolOutcome":
    """Resize the browser window."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    await tab.page_ops.resize(args.width, args.height)
    outcome.add_result(
        f"Successfully resized window to {args.width}x{args.height}",
        width=args.width,
        height=args.height,
    )
    return outcome


@define_tool(
    name="page_screenshot",
    title="Take Screenshot",
    description="Take an inline screenshot of the current page",
    input_schema=ScreenshotInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=PageScreenshotData,
    failure_message=lambda args, exc: "Failed to take screenshot: " + str(exc),
)
async def screenshot(
    context: "DrissionPageContext", args: ScreenshotInput
) -> "ToolOutcome":
    """Take an inline screenshot."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    screenshot_data = await tab.page_ops.screenshot(path=None, full_page=args.full_page)
    outcome.add_screenshot(screenshot_data, {"full_page": args.full_page})
    return outcome


@define_tool(
    name="page_screenshot_save",
    title="Save Screenshot",
    description="Save a screenshot to a local path under DP_MCP_SCREENSHOT_ROOT",
    input_schema=ScreenshotSaveInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=PageScreenshotSaveData,
    failure_message=lambda args, exc: "Failed to take screenshot: " + str(exc),
)
async def screenshot_save(
    context: "DrissionPageContext", args: ScreenshotSaveInput
) -> "ToolOutcome":
    """Save a screenshot to an approved local path."""
    outcome = ToolOutcome()
    try:
        policy = SafetyPolicy.from_env()
        destination = policy.validate_screenshot_path(args.path)
    except PolicyDeniedError as exc:
        outcome.add_error(
            str(exc), ErrorCode.POLICY_DENIED, rule=exc.rule, value=exc.value
        )
        return outcome
    tab = context.current_tab_or_die()
    screenshot_data = await tab.page_ops.screenshot(
        path=str(destination), full_page=args.full_page
    )
    assert policy.screenshot_root is not None
    safe_relative_path = destination.relative_to(policy.screenshot_root).as_posix()
    outcome.add_result(
        "Screenshot saved.",
        screenshot=build_screenshot_metadata(
            path=screenshot_data,
            safe_relative_path=safe_relative_path,
            full_page=args.full_page,
            inline=False,
        ),
    )
    return outcome


@define_tool(
    name="page_snapshot",
    title="Page Snapshot",
    description="Return a bounded page outline with text excerpt, headings, links, buttons, inputs, forms, and recommended selectors.",
    input_schema=PageSnapshotInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=PageSnapshotData,
    failure_message=lambda args, exc: "Failed to build page snapshot: " + str(exc),
)
async def page_snapshot(
    context: "DrissionPageContext", args: PageSnapshotInput
) -> "ToolOutcome":
    """Get a bounded page outline for LLM page understanding."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    snapshot = await tab.observation.snapshot(
        include_html=args.include_html,
        max_elements=args.max_elements,
        max_text_chars=args.max_text_chars,
    )
    outcome.add_result("Captured page snapshot", **with_response_meta(snapshot))
    return outcome


@define_tool(
    name="page_accessibility_snapshot",
    title="Accessibility Snapshot",
    description="Return a bounded Chromium accessibility tree for the page or a scoped selector/frame/shadow target.",
    input_schema=PageAccessibilitySnapshotInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=PageAccessibilitySnapshotData,
    failure_message=lambda args, exc: "Failed to capture accessibility snapshot: "
    + str(exc),
)
async def page_accessibility_snapshot(
    context: "DrissionPageContext", args: PageAccessibilitySnapshotInput
) -> "ToolOutcome":
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    snapshot = await tab.accessibility.snapshot(
        scope=args.scope,
        max_nodes=args.max_nodes,
        include_ignored=args.include_ignored,
        include_values=args.include_values,
    )
    outcome.add_result(
        "Captured accessibility snapshot", **with_response_meta(snapshot)
    )
    return outcome


@define_tool(
    name="page_observe",
    title="Observe Page",
    description="Return a compact current-page fingerprint with URL, title, ready state, element counts, visible text samples, active element, and recent console summary.",
    input_schema=PageObserveInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=PageObservation,
    failure_message=lambda args, exc: "Failed to observe page: " + str(exc),
)
async def page_observe(
    context: "DrissionPageContext", args: PageObserveInput
) -> "ToolOutcome":
    """Observe the current page state."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    observation = await tab.observation.observe(
        max_texts=args.max_texts, max_text_chars=args.max_text_chars
    )
    outcome.add_result("Observed page state", **observation)
    return outcome


@define_tool(
    name="page_evaluate",
    title="Evaluate JavaScript",
    description="Run a bounded JavaScript function body in the current page and return a JSON-safe result. This can mutate the page.",
    input_schema=PageEvaluateInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=PageEvaluateData,
    failure_message=lambda args, exc: "Failed to evaluate JavaScript: " + str(exc),
)
async def page_evaluate(
    context: "DrissionPageContext", args: PageEvaluateInput
) -> "ToolOutcome":
    """Evaluate JavaScript in the current page with bounded output."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.observation.evaluate(
        args.script, args=args.args, max_chars=args.max_chars
    )
    outcome.add_result("Evaluated JavaScript", **result)
    return outcome


@define_tool(
    name="page_close",
    title="Close Browser",
    description="Close the current page/browser",
    input_schema=EmptyInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=PageCloseData,
    failure_message=lambda args, exc: "Failed to close browser: " + str(exc),
)
async def close(context: "DrissionPageContext", args: EmptyInput) -> "ToolOutcome":
    """Close the browser."""
    outcome = ToolOutcome()
    closed = await context.close_browser()
    if closed is False:
        raise RuntimeError("Browser close failed; local MCP state was cleared.")
    outcome.add_result("Successfully closed browser", closed=True)
    return outcome


@define_tool(
    name="page_get_url",
    title="Get Current URL",
    description="Get the current URL of the page",
    input_schema=EmptyInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=PageGetUrlData,
    failure_message=lambda args, exc: "Failed to get URL: " + str(exc),
)
async def get_url(context: "DrissionPageContext", args: EmptyInput) -> "ToolOutcome":
    """Get current URL."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    url = tab.url
    outcome.add_result(f"Current URL: {url}", url=url)
    return outcome


@define_tool(
    name="browser_headers_set",
    title="Set Browser Headers",
    description=(
        "Replace extra HTTP request headers for the current tab. Successful "
        "results return header names with values redacted; an empty object clears them."
    ),
    input_schema=BrowserHeadersSetInput,
    tool_type=ToolType.DESTRUCTIVE,
    idempotent=True,
    output_model=BrowserHeadersSetData,
    failure_message=lambda args, exc: "Failed to set browser headers: " + str(exc),
)
async def browser_headers_set(
    context: "DrissionPageContext", args: BrowserHeadersSetInput
) -> "ToolOutcome":
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.page_ops.set_headers(args.headers)
    outcome.add_result(f"Set {result['count']} browser header(s)", **result)
    return outcome


@define_tool(
    name="browser_user_agent_set",
    title="Set Browser User Agent",
    description=(
        "Override the current tab user agent and optional platform, returning the "
        "previous user agent so callers can restore it."
    ),
    input_schema=BrowserUserAgentSetInput,
    tool_type=ToolType.DESTRUCTIVE,
    idempotent=True,
    output_model=BrowserUserAgentSetData,
    failure_message=lambda args, exc: "Failed to set browser user agent: " + str(exc),
)
async def browser_user_agent_set(
    context: "DrissionPageContext", args: BrowserUserAgentSetInput
) -> "ToolOutcome":
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.page_ops.set_user_agent(args.user_agent, args.platform)
    outcome.add_result("Set browser user agent", **result)
    return outcome


@define_tool(
    name="browser_cache_clear",
    title="Clear Browser Cache",
    description="Clear HTTP cache without clearing cookies or Web Storage.",
    input_schema=EmptyInput,
    tool_type=ToolType.DESTRUCTIVE,
    idempotent=True,
    output_model=BrowserCacheClearData,
    failure_message=lambda args, exc: "Failed to clear browser cache: " + str(exc),
)
async def browser_cache_clear(
    context: "DrissionPageContext", args: EmptyInput
) -> "ToolOutcome":
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.page_ops.clear_cache()
    outcome.add_result("Cleared browser cache", **result)
    return outcome
