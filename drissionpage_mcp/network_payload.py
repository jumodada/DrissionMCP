"""Network packet payload normalization helpers."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from typing import Any

from .response_json import (
    redact_public_payload,
    redact_public_text,
    redact_public_url,
    strict_json_dumps,
)

SENSITIVE_NETWORK_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "proxy-authorization",
}


def _redact_network_url(value: Any) -> str:
    return redact_public_url(str(value or ""))


def _redact_body_text(text: str) -> str:
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return redact_public_text(text, include_network_fields=True)
    return strict_json_dumps(
        redact_public_payload(
            parsed,
            _context="network_body",
            _force_redact_values=True,
        ),
        ensure_ascii=False,
        sort_keys=True,
    )


def _network_packet_payload(
    packet: Any,
    *,
    index: int,
    include_headers: bool,
    include_body: bool,
    max_body_chars: int,
) -> dict[str, Any]:
    request = _safe_packet_attr(packet, "request")
    response = _safe_packet_attr(packet, "response")
    failed = bool(_safe_packet_attr(packet, "is_failed", False))
    fail_info = _safe_packet_attr(packet, "fail_info") if failed else None
    payload: dict[str, Any] = {
        "index": index,
        "url": _redact_network_url(_safe_packet_attr(packet, "url", "")),
        "method": str(_safe_packet_attr(packet, "method", "") or ""),
        "resource_type": str(_safe_packet_attr(packet, "resourceType", "") or ""),
        "status": _safe_int_or_none(_safe_packet_attr(response, "status")),
        "mime_type": str(_safe_packet_attr(response, "mimeType", "") or ""),
        "failed": failed,
        "fail_error": str(_safe_packet_attr(fail_info, "errorText", "") or ""),
    }
    if include_headers:
        payload["request_headers"] = _redact_network_headers(
            _safe_packet_attr(request, "headers", {})
        )
        payload["response_headers"] = _redact_network_headers(
            _safe_packet_attr(response, "headers", {})
        )
    if include_body:
        body = _safe_packet_attr(response, "body", None)
        body_excerpt, body_truncated, body_type = _bounded_body(body, max_body_chars)
        payload.update(
            {
                "body_excerpt": body_excerpt,
                "body_truncated": body_truncated,
                "body_type": body_type,
            }
        )
        request_body = _safe_packet_attr(request, "postData", None)
        request_excerpt, request_truncated, request_type = _bounded_body(
            request_body,
            max_body_chars,
        )
        payload.update(
            {
                "request_body_excerpt": request_excerpt,
                "request_body_truncated": request_truncated,
                "request_body_type": request_type,
            }
        )
    return payload


def _safe_packet_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _safe_int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _redact_network_headers(headers: Any) -> dict[str, str]:
    if not isinstance(headers, Mapping):
        try:
            headers = dict(headers or {})
        except Exception:
            headers = {}
    redacted: dict[str, str] = {}
    for key, value in dict(headers).items():
        key_text = str(key)
        lowered = key_text.lower()
        if lowered in SENSITIVE_NETWORK_HEADERS or any(
            marker in lowered for marker in ("token", "secret", "api-key")
        ):
            redacted[key_text] = "<redacted>"
        else:
            redacted[key_text] = "" if value is None else str(value)
    return redacted


def _bounded_body(value: Any, max_chars: int) -> tuple[str, bool, str]:
    if value in (None, False):
        return "", False, "none"
    if isinstance(value, (bytes, bytearray)):
        text = base64.b64encode(bytes(value)).decode("ascii")
        body_type = "bytes_base64"
    elif isinstance(value, (dict, list, tuple)):
        text = strict_json_dumps(value, ensure_ascii=False, sort_keys=True)
        body_type = "json"
    else:
        text = str(value)
        body_type = "text"
    text = _redact_body_text(text)
    limit = max(0, int(max_chars))
    return text[:limit], len(text) > limit, body_type
