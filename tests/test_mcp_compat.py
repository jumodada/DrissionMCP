"""MCP Python SDK compatibility boundary coverage."""

from __future__ import annotations

import pytest

import drissionpage_mcp.mcp_compat as mcp_compat


@pytest.mark.parametrize("version", ["1.0.0", "1.12.4", "1.29.0", "1.99.0rc1"])
def test_supported_mcp_sdk_versions_are_limited_to_major_one(version: str) -> None:
    assert mcp_compat.is_supported_mcp_sdk_version(version) is True


@pytest.mark.parametrize("version", ["0.9.9", "2.0.0", "2.0.0a1", "unavailable"])
def test_unsupported_mcp_sdk_versions_are_rejected(version: str) -> None:
    assert mcp_compat.is_supported_mcp_sdk_version(version) is False


def test_ensure_supported_mcp_sdk_returns_supported_version() -> None:
    assert mcp_compat.ensure_supported_mcp_sdk("1.29.0") == "1.29.0"


def test_ensure_supported_mcp_sdk_raises_actionable_install_error() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        mcp_compat.ensure_supported_mcp_sdk("2.0.0")

    message = str(exc_info.value)
    assert "2.0.0" in message
    assert "mcp>=1.0.0,<2" in message
    assert "python -m pip install" in message
    assert "drissionpage-mcp>=0.8.8" in message
