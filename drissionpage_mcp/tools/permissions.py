"""Browser permission observation and origin-scoped controls."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator

from ..browser.permissions import PermissionName, PermissionSetting
from ..policy import PolicyDeniedError, validate_navigation
from ..response_errors import ErrorCode
from ..tool_outputs import (
    BrowserPermissionGetData,
    BrowserPermissionSetData,
    BrowserPermissionsResetData,
)
from .base import (
    TabScopedEmptyInput,
    TabScopedInput,
    ToolOutcome,
    ToolType,
    define_tool,
)

if TYPE_CHECKING:
    from ..context import DrissionPageContext


class BrowserPermissionGetInput(TabScopedInput):
    """Query one permission in the current document origin."""

    permission: PermissionName


class BrowserPermissionSetInput(TabScopedInput):
    """Set one Chromium permission for one exact HTTP(S) origin."""

    permission: PermissionName
    setting: PermissionSetting
    origin: str | None = Field(
        default=None,
        description="Exact HTTP(S) origin. Defaults to the current page origin.",
    )

    @field_validator("origin")
    @classmethod
    def validate_origin(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_origin(value)


@define_tool(
    name="browser_permission_get",
    title="Get Browser Permission",
    description="Query one browser permission state for the current document origin without opening an operating-system prompt.",
    input_schema=BrowserPermissionGetInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=BrowserPermissionGetData,
    failure_message=lambda args, exc: "Failed to query browser permission state.",
)
async def browser_permission_get(
    context: DrissionPageContext, args: BrowserPermissionGetInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = tab.permissions.get(args.permission)
    outcome.set_result(
        f"Observed {args.permission} permission state {result['state']}", result
    )
    return outcome


@define_tool(
    name="browser_permission_set",
    title="Set Browser Permission",
    description="Set one permission to granted, denied, or prompt for one bounded origin in the current Chromium context.",
    input_schema=BrowserPermissionSetInput,
    tool_type=ToolType.DESTRUCTIVE,
    idempotent=True,
    output_model=BrowserPermissionSetData,
    failure_message=lambda args, exc: "Failed to set browser permission state.",
)
async def browser_permission_set(
    context: DrissionPageContext, args: BrowserPermissionSetInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    origin = args.origin or tab.permissions.current_origin()
    try:
        validate_navigation(origin)
    except PolicyDeniedError as exc:
        outcome.add_error(
            str(exc), ErrorCode.POLICY_DENIED, rule=exc.rule, value=exc.value
        )
        return outcome
    result = tab.permissions.set(args.permission, args.setting, origin)
    outcome.set_result(
        f"Set {args.permission} permission to {args.setting} for {origin}", result
    )
    return outcome


@define_tool(
    name="browser_permissions_reset",
    title="Reset Browser Permissions",
    description="Reset all Chromium permission overrides in the current browser context.",
    input_schema=TabScopedEmptyInput,
    tool_type=ToolType.DESTRUCTIVE,
    idempotent=True,
    output_model=BrowserPermissionsResetData,
    failure_message=lambda args, exc: "Failed to reset browser permissions.",
)
async def browser_permissions_reset(
    context: DrissionPageContext, args: TabScopedEmptyInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = tab.permissions.reset()
    outcome.set_result("Reset browser permission overrides", result)
    return outcome


def _normalize_origin(value: str) -> str:
    try:
        parts = urlsplit(value)
        port = parts.port
    except (TypeError, ValueError) as exc:
        raise ValueError("origin must be an absolute HTTP(S) origin") from exc
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise ValueError("origin must be an absolute HTTP(S) origin without a path")
    host = parts.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parts.scheme, netloc, "", "", ""))


__all__ = [
    "BrowserPermissionGetInput",
    "BrowserPermissionSetInput",
    "browser_permission_get",
    "browser_permission_set",
    "browser_permissions_reset",
]
