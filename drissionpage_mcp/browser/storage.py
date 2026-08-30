"""Cookie and Web Storage operations for a browser tab."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from ..response_json import redact_public_url

if TYPE_CHECKING:
    from ..tab import PageTab

logger = logging.getLogger(__name__)


class StorageOperations:
    """Own cookie and Web Storage behavior for one tab."""

    def __init__(self, tab: PageTab) -> None:
        self._tab = tab

    @property
    def _page(self) -> Any:
        return self._tab.page

    async def cookies_get(
        self,
        *,
        all_domains: bool = False,
        all_info: bool = False,
        include_values: bool = False,
    ) -> dict[str, Any]:
        """Return normalized browser cookies with opt-in values."""

        try:
            cookies = self._cookies(
                all_domains=all_domains,
                all_info=all_info,
                include_values=include_values,
            )
            return {
                "count": len(cookies),
                "include_values": include_values,
                "all_domains": all_domains,
                "cookies": cookies,
            }
        except Exception as exc:
            logger.error("Failed to read cookies (%s)", type(exc).__name__)
            raise

    async def cookies_set(
        self, *, cookies: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Set one bounded cookie batch and return redacted write metadata."""

        try:
            normalized = [dict(cookie) for cookie in cookies]
            upstream = [_to_drissionpage_cookie(cookie) for cookie in normalized]
            self._page.set.cookies(upstream)
            return {
                "count": len(normalized),
                "set": True,
                "cookies": [_cookie_write_metadata(cookie) for cookie in normalized],
            }
        except Exception as exc:
            logger.error("Failed to set browser cookies (%s)", type(exc).__name__)
            raise

    async def cookies_delete(
        self,
        *,
        name: str,
        url: str | None = None,
        domain: str | None = None,
        path: str | None = None,
    ) -> dict[str, Any]:
        """Delete one named cookie within an optional exact scope."""

        try:
            self._page.set.cookies.remove(
                name,
                url=url,
                domain=domain,
                path=path,
            )
            return {
                "name": name,
                "url": url,
                "domain": domain,
                "path": path,
                "deleted": True,
            }
        except Exception as exc:
            logger.error("Failed to delete browser cookie (%s)", type(exc).__name__)
            raise

    async def cookies_clear(self) -> dict[str, Any]:
        """Clear all cookies from the browser cookie store."""

        try:
            self._page.set.cookies.clear()
            return {"cleared": True}
        except Exception as exc:
            logger.error("Failed to clear browser cookies (%s)", type(exc).__name__)
            raise

    async def get(
        self, *, area: str = "local", key: str = "", include_values: bool = False
    ) -> dict[str, Any]:
        """Read localStorage or sessionStorage."""

        try:
            return self._get(area=area, key=key, include_values=include_values)
        except Exception as exc:
            logger.error("Failed to read browser storage (%s)", type(exc).__name__)
            raise

    async def set(self, *, area: str, key: str, value: str) -> dict[str, Any]:
        """Set one localStorage or sessionStorage item."""

        try:
            storage_name = _storage_name(area)
            self._page.run_js(
                (
                    "(() => {"
                    f"{storage_name}.setItem({json.dumps(key)}, {json.dumps(value)});"
                    "return true;"
                    "})()"
                ),
                as_expr=True,
            )
            return {"area": area, "key": key, "set": True}
        except Exception as exc:
            logger.error("Failed to set browser storage (%s)", type(exc).__name__)
            raise

    async def clear(self, *, area: str, key: str = "") -> dict[str, Any]:
        """Clear one or all localStorage/sessionStorage items."""

        try:
            storage_name = _storage_name(area)
            script = (
                f"{storage_name}.removeItem({json.dumps(key)});"
                if key
                else f"{storage_name}.clear();"
            )
            self._page.run_js(f"(() => {{{script} return true;}})()", as_expr=True)
            return {"area": area, "key": key, "cleared": True}
        except Exception as exc:
            logger.error("Failed to clear browser storage (%s)", type(exc).__name__)
            raise

    def session_state(self) -> dict[str, Any]:
        """Return a redacted current-tab cookie/storage summary."""

        cookies = self._cookies(include_values=False)
        return {
            "available": True,
            "browser_active": bool(self._tab.context and self._tab.context.is_active()),
            "current_url": self._tab.url,
            "cookies": {
                "count": len(cookies),
                "names": [cookie["name"] for cookie in cookies if cookie.get("name")],
            },
            "storage": {
                "local": _storage_summary(
                    self._get(area="local", include_values=False)
                ),
                "session": _storage_summary(
                    self._get(area="session", include_values=False)
                ),
            },
        }

    def _cookies(
        self,
        *,
        all_domains: bool = False,
        all_info: bool = False,
        include_values: bool = False,
    ) -> list[dict[str, Any]]:
        raw = self._page.cookies(all_domains=all_domains, all_info=all_info)
        if isinstance(raw, Mapping):
            items = [{"name": str(name), "value": value} for name, value in raw.items()]
        else:
            try:
                items = list(raw or [])
            except TypeError:
                items = []
        return [
            _normalize_cookie(item, include_values=include_values) for item in items
        ]

    def _get(
        self, *, area: str = "local", key: str = "", include_values: bool = False
    ) -> dict[str, Any]:
        storage_name = _storage_name(area)
        script = f"""
(() => {{
  const storage = {storage_name};
  const key = {json.dumps(key)};
  const items = {{}};
  if (key) {{
    const value = storage.getItem(key);
    if (value !== null) items[key] = value;
  }} else {{
    for (let i = 0; i < storage.length; i += 1) {{
      const itemKey = storage.key(i);
      if (itemKey !== null) items[itemKey] = storage.getItem(itemKey);
    }}
  }}
  return items;
}})()
"""
        result = self._page.run_js(script, as_expr=True)
        items = dict(result) if isinstance(result, Mapping) else {}
        if include_values:
            normalized = {
                str(item_key): "" if item_value is None else str(item_value)
                for item_key, item_value in items.items()
            }
        else:
            normalized = {
                str(item_key): "<redacted>" if item_value not in ("", None) else ""
                for item_key, item_value in items.items()
            }
        return {
            "area": area,
            "key": key,
            "include_values": include_values,
            "count": len(normalized),
            "items": normalized,
        }


def _normalize_cookie(cookie: Any, *, include_values: bool = False) -> dict[str, Any]:
    if isinstance(cookie, Mapping):
        get = cookie.get
    else:

        def get(name: str, default: Any = None) -> Any:
            return getattr(cookie, name, default)

    value = get("value", "")
    if not include_values and value not in ("", None):
        value = "<redacted>"
    return {
        "name": "" if get("name", "") is None else str(get("name", "")),
        "value": "" if value is None else str(value),
        "domain": "" if get("domain", "") is None else str(get("domain", "")),
        "path": "" if get("path", "") is None else str(get("path", "")),
        "expires": get("expires", None),
        "secure": bool(get("secure", False)),
        "http_only": bool(get("httpOnly", get("http_only", False))),
    }


def _to_drissionpage_cookie(cookie: Mapping[str, Any]) -> dict[str, Any]:
    """Map the public snake-case cookie contract to DrissionPage fields."""

    mapped: dict[str, Any] = {}
    field_names = {
        "http_only": "httpOnly",
        "same_site": "sameSite",
        "source_scheme": "sourceScheme",
    }
    for name, value in cookie.items():
        if name in {"url", "domain", "path"} and value == "":
            continue
        mapped[field_names.get(name, name)] = value
    return mapped


def _cookie_write_metadata(cookie: Mapping[str, Any]) -> dict[str, Any]:
    """Return the accepted cookie shape without its secret value or URL secrets."""

    metadata = dict(cookie)
    metadata["value"] = "<redacted>" if metadata.get("value") else ""
    if "url" in metadata:
        metadata["url"] = redact_public_url(metadata.get("url"))
    return metadata


def _storage_name(area: str) -> str:
    if area == "local":
        return "localStorage"
    if area == "session":
        return "sessionStorage"
    raise ValueError(f"Unsupported storage area: {area}")


def _storage_summary(storage_payload: dict[str, Any]) -> dict[str, Any]:
    items = storage_payload.get("items") or {}
    keys = sorted(str(key) for key in items) if isinstance(items, Mapping) else []
    return {"count": len(keys), "keys": keys}
