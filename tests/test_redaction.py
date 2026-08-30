"""Regression coverage for public MCP output redaction."""

from __future__ import annotations

import json

from drissionpage_mcp.response_json import (
    json_safe_value,
    redact_public_text,
    redact_public_url,
)
from drissionpage_mcp.tool_outputs import PageNavigateWithHttpAuthData
from drissionpage_mcp.tools.base import ToolOutcome


def test_tool_outcome_redacts_urls_in_message_data_details_and_text_mirror() -> None:
    secret_url = "https://user:pass@example.test/path?token=secret#private"
    outcome = ToolOutcome()
    outcome.add_error(
        f"Request failed at {secret_url}",
        "UNKNOWN_ERROR",
        callback_url=secret_url,
        authorization="Bearer secret",
    )

    structured = outcome.structured_content()
    public = json.dumps(structured, ensure_ascii=False)
    text = "\n".join(item.text for item in outcome.content() if item.type == "text")

    assert secret_url not in public
    assert "user:pass" not in public
    assert "token=secret" not in public
    assert structured["error"]["details"]["authorization"] == "<redacted>"
    assert "https://example.test/path" in public
    assert secret_url not in text


def test_explicit_storage_and_cookie_reads_preserve_requested_values() -> None:
    payload = {
        "include_values": True,
        "items": {"auth_token": "storage-secret"},
        "cookies": [{"name": "session", "value": "cookie-secret"}],
    }

    assert json_safe_value(payload) == payload


def test_sensitive_keys_are_redacted_without_explicit_read_opt_in() -> None:
    assert json_safe_value(
        {"authorization": "Bearer secret", "api_token": "secret"}
    ) == {"authorization": "<redacted>", "api_token": "<redacted>"}


def test_camel_case_credentials_are_redacted_in_payloads_and_urls() -> None:
    payload = json_safe_value(
        {
            "apiKey": "api-secret",
            "clientSecret": "client-secret",
            "sessionId": "session-secret",
            "authToken": "auth-secret",
            "safe": "visible",
        }
    )
    assert payload == {
        "apiKey": "<redacted>",
        "clientSecret": "<redacted>",
        "sessionId": "<redacted>",
        "authToken": "<redacted>",
        "safe": "visible",
    }

    url = redact_public_url(
        "https://example.test/callback?apiKey=api-secret&clientSecret=client-secret"
        "&sessionId=session-secret&authToken=auth-secret&safe=visible"
    )
    assert "api-secret" not in url
    assert "client-secret" not in url
    assert "session-secret" not in url
    assert "auth-secret" not in url
    assert "safe=visible" in url


def test_text_redaction_consumes_quoted_and_bearer_values() -> None:
    text = redact_public_text(
        'password="password-secret" token: "token-secret" '
        "authorization: Bearer bearer-secret clientSecret=client-secret"
    )

    for secret in (
        "password-secret",
        "token-secret",
        "bearer-secret",
        "client-secret",
    ):
        assert secret not in text
    assert text.count("<redacted>") >= 4


def test_known_protocol_codes_and_states_remain_public_metadata() -> None:
    payload = json_safe_value(
        {
            "code": "TIMEOUT",
            "state": "granted",
            "nested": {"state": {"exists": True}},
        }
    )

    assert payload == {
        "code": "TIMEOUT",
        "state": "granted",
        "nested": {"state": {"exists": True}},
    }

    assert json_safe_value(
        {"code": "oauth-code-secret", "state": "oauth-state-secret"}
    ) == {"code": "<redacted>", "state": "<redacted>"}


def test_credential_scope_remains_safe_typed_metadata() -> None:
    payload = {
        "url": "https://example.test/protected",
        "final_url": "https://example.test/protected",
        "authenticated": True,
        "tab_id": "tab-1",
        "credential_scope": "isolated_browser_context",
        "credentials_redacted": True,
    }

    public = json_safe_value(payload)

    assert public["credential_scope"] == "isolated_browser_context"
    assert PageNavigateWithHttpAuthData.model_validate(public).credential_scope == (
        "isolated_browser_context"
    )
