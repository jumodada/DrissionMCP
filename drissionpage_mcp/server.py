"""MCP Server implementation for DrissionPage."""

import asyncio
import inspect
import logging
from typing import Any

from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListResourcesRequest,
    ReadResourceRequest,
    ServerResult,
    Tool,
    ToolAnnotations,
)
from pydantic import ValidationError

from . import __version__
from .context import DrissionPageContext
from .guidance import server_instructions
from .mcp_compat import ensure_supported_mcp_sdk
from .resources import list_resources as list_resource_definitions
from .resources import read_resource as read_resource_definition
from .response_errors import ErrorCode, classify_error, public_failure_message
from .tools import ToolSpec as DrissionTool
from .tools import get_all_tools
from .tools.base import ToolExecutionMode, ToolOutcome, ToolType

logger = logging.getLogger(__name__)


class DrissionPageMCPServer:
    """MCP Server for DrissionPage automation."""

    def __init__(self, name: str = "DrissionPage MCP", version: str = __version__):
        self.mcp_sdk_version = ensure_supported_mcp_sdk()
        self.name = name
        self.version = version
        self.server = Server(
            name,
            version=version,
            instructions=server_instructions(version),
        )
        self.context: DrissionPageContext | None = None
        self.tools: dict[str, DrissionTool] = {}
        self._execution_lock = asyncio.Lock()
        self._lifecycle_condition = asyncio.Condition()
        self._active_tool_calls = 0
        self._cleanup_active = False

        # Load tools
        self._load_tools()

        # Register handlers
        self._setup_handlers()

    def _load_tools(self) -> None:
        """Load all available tools."""
        tools = get_all_tools()
        self.tools = {tool.name: tool for tool in tools}
        logger.info(f"Loaded {len(self.tools)} tools: {list(self.tools.keys())}")

    def _setup_handlers(self) -> None:
        """Set up MCP request handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [self._tool_to_mcp_tool(tool) for tool in self.tools.values()]

        @self.server.list_resources()
        async def list_resources():
            """List MCP resources."""
            return list_resource_definitions()

        @self.server.read_resource()
        async def read_resource(uri):
            """Read an MCP resource without initializing the browser."""
            return read_resource_definition(str(uri))

        async def call_tool_impl(
            name: str, arguments: dict[str, Any] | None = None
        ) -> CallToolResult:
            """Execute a tool with given arguments and preserve isError semantics."""
            tool = self.tools.get(name)
            if not tool:
                replacement = REMOVED_TOOL_REPLACEMENTS.get(name)
                message = f"Tool '{name}' not found"
                details: dict[str, Any] = {"tool_name": name}
                if replacement:
                    message = f"{message}. Use '{replacement}' instead."
                    details["suggested_tool"] = replacement
                outcome = ToolOutcome()
                outcome.add_error(message, ErrorCode.TOOL_NOT_FOUND, **details)
                return self._call_result(outcome)

            try:
                validated_args = tool.input_schema.model_validate(arguments or {})
            except ValidationError as exc:
                outcome = ToolOutcome()
                outcome.add_error(
                    _validation_error_message(exc),
                    ErrorCode.MCP_ARGUMENT_INVALID,
                    tool_name=name,
                )
                return self._call_result(outcome)

            call_started = False
            try:
                context = await self._begin_tool_call()
                call_started = True
                if (
                    name in _CONCURRENT_DIALOG_TOOLS
                    or tool.execution_mode is ToolExecutionMode.CONCURRENT
                ):
                    outcome = await tool.execute(context, validated_args)
                else:
                    async with self._execution_lock:
                        outcome = await tool.execute(context, validated_args)
                return self._call_result(outcome)
            except Exception as e:
                logger.error("Error executing tool %s (%s)", name, type(e).__name__)
                error_code = classify_error(e, name)
                outcome = ToolOutcome()
                outcome.add_error(
                    public_failure_message(
                        e,
                        error_code,
                        f"Error executing tool {name}: {e}",
                    ),
                    error_code,
                    tool_name=name,
                )
                return self._call_result(outcome)
            finally:
                if call_started:
                    await self._end_tool_call()

        async def call_tool_handler(req: CallToolRequest) -> ServerResult:
            """MCP request handler for tool calls.

            The low-level SDK decorator normalizes tuple/dict returns with
            ``isError=False``. Registering the handler directly keeps tool-level
            failures distinguishable while still returning structuredContent.
            """
            result = await call_tool_impl(
                req.params.name,
                dict(req.params.arguments or {}),
            )
            return ServerResult(result)

        self.server.request_handlers[CallToolRequest] = call_tool_handler
        self._call_tool_impl = call_tool_impl

        # Touch these imports so static analysis keeps the request types associated
        # with the decorators above.
        _ = (
            ListResourcesRequest,
            ReadResourceRequest,
        )

    def _tool_to_mcp_tool(self, tool: DrissionTool) -> Tool:
        """Convert an internal tool definition to an MCP SDK Tool model."""

        kwargs: dict[str, Any] = {
            "name": tool.name,
            "title": tool.title,
            "description": tool.description,
            "inputSchema": tool.input_schema.model_json_schema(),
            "annotations": ToolAnnotations(
                title=tool.title,
                readOnlyHint=tool.tool_type == ToolType.READ_ONLY,
                destructiveHint=tool.tool_type == ToolType.DESTRUCTIVE,
                idempotentHint=tool.idempotent,
                openWorldHint=True,
            ),
        }
        if _tool_supports_output_schema():
            kwargs["outputSchema"] = tool.output_schema()
        return Tool(**kwargs)

    def _call_result(self, outcome: ToolOutcome) -> CallToolResult:
        """Build a direct MCP call result for tests and internal callers."""
        return CallToolResult(
            content=list(outcome.content()),
            structuredContent=outcome.structured_content(),
            isError=outcome.is_error,
        )

    async def run_server(self, read_stream, write_stream) -> None:
        """Run the MCP server with stdio streams."""
        try:
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=self.name,
                    server_version=self.version,
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
        except Exception as e:
            logger.error("Server run error (%s)", type(e).__name__)
            raise
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Clean up resources."""
        async with self._lifecycle_condition:
            while self._cleanup_active:
                await self._lifecycle_condition.wait()
            self._cleanup_active = True
            while self._active_tool_calls:
                await self._lifecycle_condition.wait()
            context = self.context
            self.context = None
        try:
            if context:
                result = context.cleanup()
                if inspect.isawaitable(result):
                    await result
        finally:
            async with self._lifecycle_condition:
                self._cleanup_active = False
                self._lifecycle_condition.notify_all()
        logger.info("Server cleanup completed")

    async def _begin_tool_call(self) -> DrissionPageContext:
        """Claim one context user without racing cleanup or lazy creation."""

        async with self._lifecycle_condition:
            while self._cleanup_active:
                await self._lifecycle_condition.wait()
            if self.context is None:
                self.context = DrissionPageContext()
            self._active_tool_calls += 1
            return self.context

    async def _end_tool_call(self) -> None:
        async with self._lifecycle_condition:
            self._active_tool_calls -= 1
            if self._active_tool_calls == 0:
                self._lifecycle_condition.notify_all()


def _tool_supports_output_schema() -> bool:
    """Return whether the installed MCP SDK Tool model accepts outputSchema."""

    fields = getattr(Tool, "model_fields", None) or getattr(Tool, "__fields__", {})
    if "outputSchema" in fields:
        return True
    try:
        return "outputSchema" in inspect.signature(Tool).parameters
    except (TypeError, ValueError):
        return False


def _validation_error_message(exc: ValidationError) -> str:
    """Return actionable validation details without echoing rejected input values."""

    issues = []
    for error in exc.errors(include_input=False, include_url=False):
        location = ".".join(str(item) for item in error.get("loc", ())) or "input"
        issues.append(f"{location}: {error['msg']}")
    return f"Input validation error: {'; '.join(issues)}"


REMOVED_TOOL_REPLACEMENTS = {
    "element_input_text": "element_type",
    "wait_sleep": "wait_time",
}


# Dialog observation/response must overlap the serialized action that opens the
# native modal; both operations are bounded to the pending dialog lifecycle.
_CONCURRENT_DIALOG_TOOLS = frozenset(
    {"page_dialog_observe", "page_dialog_respond"}
)
