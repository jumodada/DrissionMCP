"""Network listener beta tools for DrissionPage 4.x tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field, StrictStr, StringConstraints

from ..limits import MAX_WAIT_SECONDS
from ..metadata import with_response_meta
from ..tool_outputs import (
    NetworkBlockedUrlsSetData,
    NetworkListenStartData,
    NetworkListenStopData,
    NetworkListenWaitData,
)
from .base import (
    TabScopedInput,
    ToolExecutionMode,
    ToolOutcome,
    ToolType,
    define_tool,
)

if TYPE_CHECKING:
    from ..context import DrissionPageContext


BlockedUrlPattern = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=2000),
]


class NetworkListenStartInput(TabScopedInput):
    """Input schema for starting HTTP/XHR/Fetch observation."""

    targets: list[str] = Field(
        default_factory=list,
        description="Optional URL substrings or regex patterns passed to DrissionPage.",
    )
    is_regex: bool = Field(
        default=False,
        description="Treat targets as regular expressions when targets are provided.",
    )
    method: str = Field(
        default="", description="Optional HTTP method filter such as GET or POST."
    )
    resource_type: str = Field(
        default="",
        description="Optional resource type filter such as Fetch, XHR, or Document.",
    )
    clear: bool = Field(
        default=True, description="Clear any existing listener queue before starting."
    )


class NetworkListenWaitInput(TabScopedInput):
    """Input schema for waiting on observed packets."""

    timeout: float = Field(
        default=5.0,
        ge=0,
        le=MAX_WAIT_SECONDS,
        description="Maximum seconds to wait for packets.",
    )
    limit: int = Field(
        default=10, ge=1, le=100, description="Maximum packets to return."
    )
    include_headers: bool = Field(
        default=False,
        description="Include request/response headers with sensitive names redacted.",
    )
    include_body: bool = Field(
        default=False, description="Include bounded request/response body excerpts."
    )
    max_body_chars: int = Field(
        default=2000,
        ge=0,
        le=20000,
        description="Maximum characters for each body excerpt when include_body is true.",
    )


class NetworkListenStopInput(TabScopedInput):
    """Input schema for stopping packet observation."""

    clear: bool = Field(
        default=True, description="Clear the listener queue while stopping."
    )


class NetworkBlockedUrlsSetInput(TabScopedInput):
    """Input schema for replacing blocked URL patterns."""

    urls: list[BlockedUrlPattern] = Field(
        ...,
        max_length=100,
        description="URL patterns with optional wildcards. An empty list clears them.",
    )


@define_tool(
    name="network_listen_start",
    title="Start Network Listener",
    description="Start beta HTTP/XHR/Fetch network observation for the active tab. This observes packets only; it does not intercept or modify requests.",
    input_schema=NetworkListenStartInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=NetworkListenStartData,
    failure_message=lambda args, exc: "Failed to start network listener: " + str(exc),
)
async def network_listen_start(
    context: DrissionPageContext, args: NetworkListenStartInput
) -> ToolOutcome:
    """Start DrissionPage listener."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.network.start(
        targets=args.targets,
        is_regex=args.is_regex,
        method=args.method,
        resource_type=args.resource_type,
        clear=args.clear,
    )
    outcome.add_result("Started network listener", **result)
    return outcome


@define_tool(
    name="network_listen_wait",
    title="Wait Network Listener",
    description="Wait for observed HTTP/XHR/Fetch packets and return bounded metadata. Bodies and headers are opt-in and sensitive headers are redacted.",
    input_schema=NetworkListenWaitInput,
    tool_type=ToolType.READ_ONLY,
    execution_mode=ToolExecutionMode.CONCURRENT,
    output_model=NetworkListenWaitData,
    failure_message=lambda args, exc: "Failed to wait for network packets: " + str(exc),
)
async def network_listen_wait(
    context: DrissionPageContext, args: NetworkListenWaitInput
) -> ToolOutcome:
    """Wait for packets from DrissionPage listener."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.network.wait(
        timeout=args.timeout,
        limit=args.limit,
        include_headers=args.include_headers,
        include_body=args.include_body,
        max_body_chars=args.max_body_chars,
    )
    outcome.add_result(
        f"Captured {result['count']} network packet{('' if result['count'] == 1 else 's')}",
        **with_response_meta(result),
    )
    return outcome


@define_tool(
    name="network_listen_stop",
    title="Stop Network Listener",
    description="Stop beta network observation for the active tab and optionally clear it.",
    input_schema=NetworkListenStopInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=NetworkListenStopData,
    failure_message=lambda args, exc: "Failed to stop network listener: " + str(exc),
)
async def network_listen_stop(
    context: DrissionPageContext, args: NetworkListenStopInput
) -> ToolOutcome:
    """Stop DrissionPage listener."""
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.network.stop(clear=args.clear)
    outcome.add_result("Stopped network listener", **result)
    return outcome


@define_tool(
    name="network_blocked_urls_set",
    title="Set Blocked URLs",
    description=(
        "Replace URL patterns blocked for the current tab. Successful results "
        "echo patterns; an empty list clears them."
    ),
    input_schema=NetworkBlockedUrlsSetInput,
    tool_type=ToolType.DESTRUCTIVE,
    idempotent=True,
    output_model=NetworkBlockedUrlsSetData,
    failure_message=lambda args, exc: "Failed to set blocked URLs: " + str(exc),
)
async def network_blocked_urls_set(
    context: DrissionPageContext, args: NetworkBlockedUrlsSetInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.network.set_blocked_urls(args.urls)
    outcome.add_result(f"Set {result['count']} blocked URL pattern(s)", **result)
    return outcome
