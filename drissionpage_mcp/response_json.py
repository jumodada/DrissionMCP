"""Strict JSON normalization for public MCP response payloads."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, unquote_plus, urlsplit, urlunsplit

_SENSITIVE_KEY_RE = re.compile(
    r"(?:^|_)(?:authorization|cookie|password|passwd|secret|token|api_key|client_secret|credential|session_id|sid|jwt)(?:$|_)",
    re.I,
)
_SENSITIVE_QUERY_KEY_RE = re.compile(
    r"(?:^|_)(?:access|refresh|client|id|session|auth)?(?:token|secret|password|passwd|credential|key|auth|code)(?:$|_)",
    re.I,
)
_SENSITIVE_QUERY_NAMES = {
    "access_token",
    "api_key",
    "auth_code",
    "auth_token",
    "authorization",
    "auth",
    "code",
    "client_secret",
    "cookie",
    "credential",
    "credentials",
    "id_token",
    "jwt",
    "password",
    "passwd",
    "session",
    "session_id",
    "sid",
    "state",
    "token",
}
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
_AUTHORIZATION_ASSIGNMENT_RE = re.compile(
    r"(\bauthorization\b\s*[:=]\s*)"
    r"(?:(?:bearer|basic|digest|token)\s+)?"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;&}]+)",
    re.I,
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(\b(?:access[_-]?token|api[_-]?key|auth[_-]?code|auth[_-]?token|client[_-]?secret|cookie|credential|jwt|password|passwd|refresh[_-]?token|secret|session(?:[_-]?id)?|sid|token)\b\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;&}]+)",
    re.I,
)
_NETWORK_SECRET_ASSIGNMENT_RE = re.compile(
    r"(\b(?:access[_-]?token|api[_-]?key|auth[_-]?code|auth[_-]?token|client[_-]?secret|code|cookie|credential|jwt|password|passwd|refresh[_-]?token|secret|session(?:[_-]?id)?|sid|state|token)\b\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;&}]+)",
    re.I,
)
_URL_FIELDS = {
    "url",
    "current_url",
    "final_url",
    "source_url",
    "callback_url",
    "referrer",
}
_HEADER_FIELDS = {"headers"}
_COOKIE_FIELDS = {"cookies", "cookie"}
_STORAGE_VALUE_FIELDS = {"items", "values"}
_SAFE_METADATA_FIELDS = {"credential_scope"}
_SENSITIVE_EXACT_KEYS = {
    "access_token",
    "api_key",
    "auth_code",
    "auth_token",
    "client_secret",
    "jwt",
    "session",
    "session_id",
    "sid",
}
_PUBLIC_CODE_VALUES = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
_PUBLIC_STATE_VALUES = {
    "",
    "active",
    "canceled",
    "cancelled",
    "completed",
    "denied",
    "granted",
    "idle",
    "inactive",
    "loaded",
    "loading",
    "pending",
    "prompt",
    "ready",
    "skipped",
    "started",
    "stopped",
    "unsupported",
}
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _normalized_key(value: str) -> str:
    return _CAMEL_BOUNDARY_RE.sub("_", value.strip()).lower().replace("-", "_")


def _is_sensitive_key(value: str) -> bool:
    normalized = _normalized_key(value)
    return normalized not in _SAFE_METADATA_FIELDS and bool(
        normalized in _SENSITIVE_EXACT_KEYS or _SENSITIVE_KEY_RE.search(normalized)
    )


def _is_sensitive_query_key(value: str) -> bool:
    normalized = _normalized_key(unquote_plus(value))
    return normalized in _SENSITIVE_QUERY_NAMES or bool(
        _SENSITIVE_QUERY_KEY_RE.search(normalized)
    )


def redact_public_url(value: Any) -> str:
    """Return an HTTP(S) URL without credentials or fragment-bearing secrets.

    Non-HTTP values that are known browser sentinels (for example,
    ``about:blank``) are preserved. Other URL schemes are omitted because they
    can expose local paths or executable payloads.
    """

    if not isinstance(value, str) or not value:
        return ""
    if "\\" in value or any(
        character.isspace() or ord(character) < 32 for character in value
    ):
        return ""
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        _ = parts.port
    except (TypeError, ValueError):
        return ""

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        return value.split("#", 1)[0] if scheme == "about" else ""
    if not hostname or not hostname.strip("."):
        return ""

    # Reuse the artifact contract's strict host/path validator, then restore
    # only query components that are not classified as credentials.
    from .tool_outputs import sanitize_public_url

    base_url = sanitize_public_url(value)
    if not base_url:
        return ""
    base_parts = urlsplit(base_url)

    query_parts: list[str] = []
    for component in parts.query.split("&") if parts.query else []:
        if not component:
            continue
        raw_key, separator, raw_value = component.partition("=")
        if _is_sensitive_query_key(raw_key):
            replacement = quote("<redacted>", safe="")
            query_parts.append(f"{raw_key}={replacement}")
        elif separator:
            query_parts.append(f"{raw_key}={raw_value}")
        else:
            query_parts.append(raw_key)

    return urlunsplit(
        (base_parts.scheme, base_parts.netloc, base_parts.path, "&".join(query_parts), "")
    )


def redact_public_text(value: str, *, include_network_fields: bool = False) -> str:
    """Redact embedded URLs and obvious secret assignments in free text."""

    def replace_url(match: re.Match[str]) -> str:
        raw = match.group(0)
        trailing = ""
        while raw and raw[-1] in ".,;:!?)]}":
            trailing = raw[-1] + trailing
            raw = raw[:-1]
        redacted = redact_public_url(raw)
        return (redacted or "<redacted-url>") + trailing

    value = _URL_RE.sub(replace_url, value)

    def replace_secret(match: re.Match[str]) -> str:
        if match.group(2).lower() in {"<redacted>", "%3credacted%3e"}:
            return match.group(0)
        return f"{match.group(1)}<redacted>"

    value = _AUTHORIZATION_ASSIGNMENT_RE.sub(replace_secret, value)
    assignment_re = (
        _NETWORK_SECRET_ASSIGNMENT_RE
        if include_network_fields
        else _SECRET_ASSIGNMENT_RE
    )
    return assignment_re.sub(replace_secret, value)


def _sanitize_string(value: str, *, key: str | None = None) -> str:
    """Redact credential-bearing fields and query/fragment-bearing URLs."""
    if key and _is_sensitive_key(key):
        return "<redacted>"
    return redact_public_text(value)


def redact_public_payload(
    value: Any,
    *,
    _key: str | None = None,
    _allow_explicit_values: bool = False,
    _context: str | None = None,
    _force_redact_values: bool = False,
) -> Any:
    """Return a recursively JSON-safe value with public secrets redacted."""

    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        if _force_redact_values and _context in {"cookies", "storage_values"}:
            return "" if value == "" else "<redacted>"
        if _allow_explicit_values and _context in {"cookies", "storage_values"}:
            return value
        if _context == "cookies" and _normalized_key(_key or "") == "value":
            return "" if value == "" else "<redacted>"
        normalized_key = _normalized_key(_key or "")
        if (
            normalized_key == "code"
            and not _PUBLIC_CODE_VALUES.fullmatch(value)
        ):
            return "<redacted>"
        if (
            normalized_key == "state"
            and value.lower() not in _PUBLIC_STATE_VALUES
        ):
            return "<redacted>"
        return _sanitize_string(value, key=_key)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        explicit_values = (
            not _force_redact_values and value.get("include_values") is True
        )
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = _normalized_key(key)
            child_context = _context
            allow_values = (
                not _force_redact_values
                and (_allow_explicit_values or explicit_values)
            )
            if normalized in _HEADER_FIELDS:
                child_context = "headers"
            elif normalized in _COOKIE_FIELDS:
                child_context = "cookies"
            elif normalized in _STORAGE_VALUE_FIELDS:
                child_context = "storage_values"
            if child_context == "headers" and isinstance(item, Mapping):
                result[key] = {
                    str(header): (
                        "<redacted>"
                        if header_value not in (None, "")
                        else ""
                    )
                    for header, header_value in item.items()
                }
                continue
            if normalized in _URL_FIELDS and isinstance(item, str):
                result[key] = redact_public_url(item)
                continue
            result[key] = redact_public_payload(
                item,
                _key=key,
                _allow_explicit_values=allow_values,
                _context=child_context,
                _force_redact_values=_force_redact_values
                or _context == "network_body",
            )
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            redact_public_payload(
                item,
                _allow_explicit_values=_allow_explicit_values,
                _context=_context,
                _force_redact_values=_force_redact_values,
            )
            for item in value
        ]
    return redact_public_text(str(value))


def json_safe_value(value: Any) -> Any:
    """Return a JSON-safe public value with sensitive fields redacted."""

    return redact_public_payload(value)


def strict_json_dumps(
    value: Any,
    *,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
    separators: tuple[str, str] | None = None,
    indent: int | None = None,
) -> str:
    """Serialize public data as standards-compliant JSON."""

    return json.dumps(
        json_safe_value(value),
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
        separators=separators,
        indent=indent,
        allow_nan=False,
    )


def non_finite_number_label(value: Any) -> str | None:
    """Return the stable label for a non-finite Python number."""

    if not isinstance(value, float) or math.isfinite(value):
        return None
    if math.isnan(value):
        return "NaN"
    return "Infinity" if value > 0 else "-Infinity"
