"""Typed tool specifications and execution outcomes."""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from mcp.types import ImageContent, TextContent
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from ..response_errors import (
    ErrorCode,
    ToolError,
    classify_error,
    public_failure_message,
    recovery_hints,
)
from ..response_json import (
    _sanitize_string,
    redact_public_payload,
    redact_public_text,
    strict_json_dumps,
)
from ..response_media import build_screenshot_metadata

if TYPE_CHECKING:
    from ..context import DrissionPageContext

JSON_RESULT_SENTINEL = "### JSON_RESULT"
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class ToolType(Enum):
    """Tool operation types."""

    READ_ONLY = "readOnly"
    DESTRUCTIVE = "destructive"


class ToolExecutionMode(Enum):
    """How a tool participates in the shared browser execution lane."""

    SERIALIZED = "serialized"
    CONCURRENT = "concurrent"


class ToolTargetScope(Enum):
    """Browser object scope used to schedule one tool invocation."""

    CONTEXT = "context"
    TAB = "tab"


class ToolInput(BaseModel):
    """Strict input model for public MCP tools."""

    model_config = ConfigDict(extra="forbid")


TabIdValue = StrictStr


class TabScopedInput(ToolInput):
    """Strict input shared by tools that operate on one browser tab.

    ``None`` intentionally means "resolve the current tab once at call start".
    The server binds that resolved object for the whole handler invocation, so a
    concurrent ``tab_switch`` cannot silently redirect an in-flight call.
    """

    tab_id: TabIdValue | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Optional MCP or native DrissionPage tab id. When omitted, the "
            "current tab is captured at call start."
        ),
    )


class TabScopedEmptyInput(TabScopedInput):
    """Empty argument shape for a tab-scoped tool."""


class EmptyInput(ToolInput):
    """Empty input schema for tools that don't require arguments."""


def identity_tab_id(
    context: DrissionPageContext,
    requested_tab_id: str | None,
    operation_key: str | None = None,
) -> str | None:
    """Return the canonical tab identity used by exact-once operation keys.

    Server calls bind the resolved MCP id before entering a handler. Direct
    handler calls do not have that binding, so retain a narrow compatibility
    fallback to the requested id or the current tab's MCP id.
    """

    bound_getter = getattr(context, "bound_tab_id", None)
    if callable(bound_getter):
        bound_tab_id = bound_getter()
        if bound_tab_id:
            return str(bound_tab_id)
    if requested_tab_id:
        tabs_getter = getattr(context, "tabs", None)
        if callable(tabs_getter):
            try:
                tracked_tabs = tabs_getter()
            except Exception:
                tracked_tabs = ()
            for tab in tracked_tabs:
                mcp_tab_id = getattr(tab, "mcp_tab_id", None)
                native_tab_id = getattr(tab, "native_tab_id", None)
                if requested_tab_id in {mcp_tab_id, native_tab_id} and mcp_tab_id:
                    return str(mcp_tab_id)
    if requested_tab_id:
        return str(requested_tab_id)
    current_getter = getattr(context, "current_tab", None)
    if callable(current_getter):
        current = current_getter()
        current_tab_id = getattr(current, "mcp_tab_id", None)
        if current_tab_id:
            return str(current_tab_id)
    current_or_die = getattr(context, "current_tab_or_die", None)
    if callable(current_or_die):
        try:
            current = current_or_die()
        except Exception:
            current = None
        current_tab_id = getattr(current, "mcp_tab_id", None)
        if current_tab_id:
            return str(current_tab_id)
    receipt_getter = getattr(context, "operation_receipt", None)
    if operation_key and callable(receipt_getter):
        receipt = receipt_getter(operation_key)
        receipt_tab_id = getattr(receipt, "tab_id", None)
        if receipt_tab_id:
            return str(receipt_tab_id)
    return None


@dataclass(slots=True)
class ToolOutcome:
    """Structured tool result plus MCP text or image content."""

    _content: list[TextContent | ImageContent] = field(default_factory=list)
    _is_error: bool = False
    _message: str = ""
    _data: dict[str, Any] = field(default_factory=dict)
    _error: ToolError | None = None

    def add_text(self, text: str) -> None:
        self._content.append(TextContent(type="text", text=redact_public_text(text)))

    def add_error(
        self,
        error: str,
        code: str | ErrorCode | None = None,
        **details: Any,
    ) -> None:
        self._is_error = True
        error_code = code if code is not None else classify_error(Exception(error))
        error_details = dict(details)
        if "hints" not in error_details:
            hints = recovery_hints(
                error_code,
                tool_name=str(error_details.get("tool_name", "")),
                message=error,
            )
            if hints:
                error_details["hints"] = hints
        code_value = (
            error_code.value if isinstance(error_code, ErrorCode) else str(error_code)
        )
        safe_error = _sanitize_string(error)
        self._message = safe_error
        safe_details = redact_public_payload(error_details)
        self._error = ToolError(code=code_value, message=safe_error, details=safe_details)
        self._content.append(TextContent(type="text", text=f"### Error\n{safe_error}"))

    def add_result(self, message: str, **data: Any) -> None:
        safe_message = _sanitize_string(message)
        self.set_result(safe_message, data)
        self._content.append(TextContent(type="text", text=f"### Result\n{safe_message}"))

    def set_result(self, message: str, data: dict[str, Any]) -> None:
        """Set structured success data without adding a presentation block."""

        self._message = _sanitize_string(message)
        self._data = data

    def add_image(self, image_data: str | bytes, mime_type: str = "image/png") -> None:
        if isinstance(image_data, bytes):
            image_data = base64.b64encode(image_data).decode()
        elif not isinstance(image_data, str):
            raise ValueError("Image data must be string or bytes")
        self._content.append(
            ImageContent(type="image", data=image_data, mimeType=mime_type)
        )

    def add_screenshot(
        self, screenshot_data: str, metadata: dict[str, Any] | None = None
    ) -> None:
        self.add_image(screenshot_data, "image/png")
        self.add_text("Screenshot taken.")
        screenshot_metadata = build_screenshot_metadata(screenshot_data)
        if metadata:
            screenshot_metadata.update(metadata)
        self._message = "Screenshot taken."
        self._data = {"screenshot": screenshot_metadata}

    def structured_content(self) -> dict[str, Any]:
        if self._is_error:
            error = self._error or ToolError(
                code=ErrorCode.UNKNOWN_ERROR.value,
                message=self._message or "Unknown error occurred.",
                details={},
            )
            payload: dict[str, Any] = {
                "ok": False,
                "message": self._message or error.message,
                "error": error.to_dict(),
            }
            if self._data:
                payload["data"] = self._data
            return cast(dict[str, Any], redact_public_payload(payload))
        return cast(
            dict[str, Any],
            redact_public_payload(
                {
                    "ok": True,
                    "message": self._message or "Operation completed successfully.",
                    "data": self._data,
                }
            ),
        )

    def content(self) -> list[TextContent | ImageContent]:
        content = list(self._content)
        if not content:
            heading = "Error" if self._is_error else "Result"
            message = self._message or (
                "Unknown error occurred."
                if self._is_error
                else "Operation completed successfully."
            )
            content.append(TextContent(type="text", text=f"### {heading}\n{message}"))
        body = strict_json_dumps(
            self.structured_content(), ensure_ascii=False, sort_keys=True
        )
        content.insert(
            0,
            TextContent(
                type="text", text=f"{JSON_RESULT_SENTINEL}\n```json\n{body}\n```"
            ),
        )
        return content

    @property
    def is_error(self) -> bool:
        return self._is_error

ToolHandler = Callable[["DrissionPageContext", InputT], Awaitable[ToolOutcome]]


@dataclass(frozen=True, slots=True)
class ToolSpec(Generic[InputT, OutputT]):
    """Single source of truth for one public MCP tool."""

    name: str
    title: str
    description: str
    input_model: type[InputT]
    output_model: type[OutputT]
    handler: ToolHandler[InputT]
    tool_type: ToolType = ToolType.READ_ONLY
    idempotent: bool = False
    execution_mode: ToolExecutionMode = ToolExecutionMode.SERIALIZED
    failure_message: Callable[[InputT, Exception], str] | None = None

    @property
    def input_schema(self) -> type[InputT]:
        return self.input_model

    @property
    def target_scope(self) -> ToolTargetScope:
        """Infer tab scope from the strict public input base class."""

        return (
            ToolTargetScope.TAB
            if issubclass(self.input_model, TabScopedInput)
            else ToolTargetScope.CONTEXT
        )

    async def execute(
        self, context: DrissionPageContext, args: InputT
    ) -> ToolOutcome:
        try:
            outcome = await self.handler(context, args)
            if not isinstance(outcome, ToolOutcome):
                raise TypeError(
                    f"Tool {self.name!r} returned {type(outcome).__name__}, expected ToolOutcome"
                )
            bound_tab_getter = getattr(type(context), "bound_tab_id", None)
            bound_tab_id = (
                bound_tab_getter(context)
                if callable(bound_tab_getter)
                else None
            )
            # Public server calls bind a stable tab before entering the handler.
            # Add its id before success validation and to any typed failure data;
            # direct handler/unit-test calls remain backwards compatible.
            if (
                bound_tab_id
                and isinstance(outcome._data, dict)
                and not outcome._data.get("tab_id")
            ):
                outcome._data["tab_id"] = bound_tab_id
            if not outcome.is_error:
                validated = self.output_model.model_validate(
                    outcome.structured_content()["data"]
                )
                outcome._data = validated.model_dump(mode="json", exclude_unset=True)
            return outcome
        except Exception as exc:
            outcome = ToolOutcome()
            error_code = classify_error(exc, self.name)
            candidate = (
                self.failure_message(args, exc)
                if self.failure_message is not None
                else f"Failed to execute {self.name}: {exc}"
            )
            message = public_failure_message(exc, error_code, candidate)
            outcome.add_error(message, error_code, tool_name=self.name)
            return outcome

    def output_schema(self) -> dict[str, Any]:
        from ..tool_outputs import tool_outcome_schema

        schema = tool_outcome_schema(self.output_model)  # type: ignore[arg-type]
        if self.target_scope is ToolTargetScope.TAB:
            _require_public_tab_id(schema)
        return schema


def _require_public_tab_id(value: Any) -> None:
    """Make internally optional tab ids required in the public success schema."""

    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict) and "tab_id" in properties:
            properties["tab_id"] = {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
                "description": "MCP tab id captured for this operation.",
            }
            required = value.setdefault("required", [])
            if isinstance(required, list) and "tab_id" not in required:
                required.append("tab_id")
        for nested in value.values():
            _require_public_tab_id(nested)
    elif isinstance(value, list):
        for nested in value:
            _require_public_tab_id(nested)


def define_tool(
    *,
    name: str,
    title: str,
    description: str,
    input_schema: type[InputT],
    output_model: type[OutputT],
    tool_type: ToolType = ToolType.READ_ONLY,
    idempotent: bool = False,
    execution_mode: ToolExecutionMode = ToolExecutionMode.SERIALIZED,
    failure_message: Callable[[InputT, Exception], str] | None = None,
) -> Callable[[ToolHandler[InputT]], ToolSpec[InputT, OutputT]]:
    """Define a typed tool specification from a two-argument async handler."""

    def decorator(handler: ToolHandler[InputT]) -> ToolSpec[InputT, OutputT]:
        return ToolSpec(
            name=name,
            title=title,
            description=description,
            input_model=input_schema,
            output_model=output_model,
            handler=handler,
            tool_type=tool_type,
            idempotent=idempotent,
            execution_mode=execution_mode,
            failure_message=failure_message,
        )

    return decorator


__all__ = [
    "EmptyInput",
    "JSON_RESULT_SENTINEL",
    "ToolInput",
    "TabScopedEmptyInput",
    "TabScopedInput",
    "TabIdValue",
    "ToolExecutionMode",
    "ToolTargetScope",
    "ToolOutcome",
    "ToolSpec",
    "ToolType",
    "identity_tab_id",
    "classify_error",
    "define_tool",
]
