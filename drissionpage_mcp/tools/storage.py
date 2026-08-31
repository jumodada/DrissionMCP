"""Cookies and web storage tools for DrissionPage MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field

from ..tool_outputs import (
    BrowserCookiesClearData,
    BrowserCookiesDeleteData,
    BrowserCookiesGetData,
    BrowserCookiesSetData,
    StorageClearData,
    StorageGetData,
    StorageSetData,
)
from .base import TabScopedInput, ToolInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext
StorageArea = Literal["local", "session"]


class BrowserCookiesGetInput(TabScopedInput):
    """Input schema for reading cookies."""

    all_domains: bool = Field(default=False)
    all_info: bool = Field(default=False)
    include_values: bool = Field(
        default=False,
        description="Return cookie values. Defaults to false to avoid leaking secrets.",
    )


class BrowserCookieInput(ToolInput):
    """One cookie accepted by the DrissionPage browser cookie setter."""

    name: str = Field(..., min_length=1, max_length=1024)
    value: str = Field(..., max_length=16384)
    url: str = Field(default="", max_length=8192)
    domain: str = Field(default="", max_length=255)
    path: str = Field(default="", max_length=2048)
    expires: float | None = Field(default=None)
    secure: bool | None = Field(default=None)
    http_only: bool | None = Field(default=None)
    same_site: Literal["None", "Lax", "Strict", "no_restriction"] | None = Field(
        default=None
    )
    priority: Literal["Low", "Medium", "High"] | None = Field(default=None)
    source_scheme: Literal["Unset", "NonSecure", "Secure"] | None = Field(
        default=None
    )


class BrowserCookiesSetInput(TabScopedInput):
    """Input schema for setting a bounded cookie batch."""

    cookies: list[BrowserCookieInput] = Field(..., min_length=1, max_length=100)


class BrowserCookiesDeleteInput(TabScopedInput):
    """Input schema for deleting one named cookie."""

    name: str = Field(..., min_length=1, max_length=1024)
    url: str | None = Field(default=None, max_length=8192)
    domain: str | None = Field(default=None, max_length=255)
    path: str | None = Field(default=None, max_length=2048)


class BrowserCookiesClearInput(TabScopedInput):
    """Input schema for clearing all browser cookies."""


class StorageGetInput(TabScopedInput):
    """Input schema for reading web storage."""

    area: StorageArea = Field(default="local")
    key: str = Field(default="", description="Optional key. Empty returns all keys.")
    include_values: bool = Field(
        default=False,
        description="Return storage values instead of redacting non-empty values.",
    )


class StorageSetInput(TabScopedInput):
    """Input schema for setting web storage."""

    area: StorageArea = Field(default="local")
    key: str = Field(..., min_length=1)
    value: str = Field(..., description="String value to store. Not echoed in result.")


class StorageClearInput(TabScopedInput):
    """Input schema for clearing web storage."""

    area: StorageArea = Field(default="local")
    key: str = Field(default="", description="Optional key. Empty clears the area.")


@define_tool(
    name="browser_cookies_get",
    title="Get Browser Cookies",
    description="Read normalized cookies with values redacted by default.",
    input_schema=BrowserCookiesGetInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=BrowserCookiesGetData,
    failure_message=lambda args, exc: "Failed to read browser cookies: " + str(exc),
)
async def browser_cookies_get(
    context: DrissionPageContext, args: BrowserCookiesGetInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.storage.cookies_get(
        all_domains=args.all_domains,
        all_info=args.all_info,
        include_values=args.include_values,
    )
    outcome.add_result(f"Read {result['count']} cookie(s)", **result)
    return outcome


@define_tool(
    name="browser_cookies_set",
    title="Set Browser Cookies",
    description=(
        "Set a bounded batch of browser cookies. Successful results preserve "
        "accepted metadata while redacting cookie values."
    ),
    input_schema=BrowserCookiesSetInput,
    tool_type=ToolType.DESTRUCTIVE,
    idempotent=True,
    output_model=BrowserCookiesSetData,
    failure_message=lambda args, exc: "Failed to set browser cookies: " + str(exc),
)
async def browser_cookies_set(
    context: DrissionPageContext, args: BrowserCookiesSetInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    cookies = [cookie.model_dump(exclude_none=True) for cookie in args.cookies]
    result = await tab.storage.cookies_set(cookies=cookies)
    outcome.add_result(f"Set {result['count']} cookie(s)", **result)
    return outcome


@define_tool(
    name="browser_cookies_delete",
    title="Delete Browser Cookie",
    description="Delete one named browser cookie with optional URL/domain/path scope.",
    input_schema=BrowserCookiesDeleteInput,
    tool_type=ToolType.DESTRUCTIVE,
    idempotent=True,
    output_model=BrowserCookiesDeleteData,
    failure_message=lambda args, exc: (
        f"Failed to delete browser cookie {args.name!r}: {exc}"
    ),
)
async def browser_cookies_delete(
    context: DrissionPageContext, args: BrowserCookiesDeleteInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.storage.cookies_delete(
        name=args.name,
        url=args.url,
        domain=args.domain,
        path=args.path,
    )
    outcome.add_result(f"Deleted browser cookie: {args.name}", **result)
    return outcome


@define_tool(
    name="browser_cookies_clear",
    title="Clear Browser Cookies",
    description="Clear all cookies from the active browser context.",
    input_schema=BrowserCookiesClearInput,
    tool_type=ToolType.DESTRUCTIVE,
    idempotent=True,
    output_model=BrowserCookiesClearData,
    failure_message=lambda args, exc: "Failed to clear browser cookies: " + str(exc),
)
async def browser_cookies_clear(
    context: DrissionPageContext, args: BrowserCookiesClearInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.storage.cookies_clear()
    outcome.add_result("Cleared browser cookies", **result)
    return outcome


@define_tool(
    name="storage_get",
    title="Get Web Storage",
    description=(
        "Read localStorage or sessionStorage by key or as a bounded map, with "
        "values redacted unless explicitly requested."
    ),
    input_schema=StorageGetInput,
    tool_type=ToolType.READ_ONLY,
    idempotent=True,
    output_model=StorageGetData,
    failure_message=lambda args, exc: f"{f'Failed to read {args.area} storage'}: {exc}",
)
async def storage_get(
    context: DrissionPageContext, args: StorageGetInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.storage.get(
        area=args.area, key=args.key, include_values=args.include_values
    )
    outcome.add_result(f"Read {args.area} storage", **result)
    return outcome


@define_tool(
    name="storage_set",
    title="Set Web Storage",
    description="Set one localStorage/sessionStorage item. The value is not echoed.",
    input_schema=StorageSetInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=StorageSetData,
    failure_message=lambda args, exc: f"{f'Failed to set {args.area} storage'}: {exc}",
)
async def storage_set(
    context: DrissionPageContext, args: StorageSetInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.storage.set(area=args.area, key=args.key, value=args.value)
    outcome.add_result(f"Set {args.area} storage key: {args.key}", **result)
    return outcome


@define_tool(
    name="storage_clear",
    title="Clear Web Storage",
    description="Clear one key or all items from localStorage/sessionStorage.",
    input_schema=StorageClearInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=StorageClearData,
    failure_message=lambda args, exc: f"{f'Failed to clear {args.area} storage'}: {exc}",
)
async def storage_clear(
    context: DrissionPageContext, args: StorageClearInput
) -> ToolOutcome:
    outcome = ToolOutcome()
    tab = context.current_tab_or_die()
    result = await tab.storage.clear(area=args.area, key=args.key)
    outcome.add_result(f"Cleared {args.area} storage", **result)
    return outcome
