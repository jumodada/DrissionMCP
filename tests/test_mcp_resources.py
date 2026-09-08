"""Minimal optional-Skills discovery resource contracts."""

from __future__ import annotations

import json
import socket

import pytest
from mcp.types import (
    ListResourcesRequest,
    ReadResourceRequest,
    ReadResourceRequestParams,
)

from drissionpage_mcp.resources import (
    RESOURCE_JSON_MAX_CHARS,
    SKILL_EXAMPLES,
    SKILLS_CATALOG_URI,
)
from drissionpage_mcp.server import DrissionPageMCPServer


@pytest.mark.asyncio
async def test_only_optional_skills_catalog_is_listed() -> None:
    server = DrissionPageMCPServer()
    handler = server.server.request_handlers[ListResourcesRequest]

    result = await handler(ListResourcesRequest(method="resources/list"))

    assert len(result.root.resources) == 1
    resource = result.root.resources[0]
    assert str(resource.uri) == SKILLS_CATALOG_URI
    assert resource.name == "skills_catalog"
    assert resource.mimeType == "application/json"
    assert "optional" in resource.description.lower()
    assert server.context is None


@pytest.mark.asyncio
async def test_catalog_read_is_static_bounded_and_browser_independent(
    monkeypatch,
) -> None:
    def deny_network(*_args, **_kwargs):
        raise AssertionError("Skills catalog reads must not access the network")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    server = DrissionPageMCPServer()
    handler = server.server.request_handlers[ReadResourceRequest]

    result = await handler(
        ReadResourceRequest(
            method="resources/read",
            params=ReadResourceRequestParams(uri=SKILLS_CATALOG_URI),
        )
    )

    assert server.context is None
    assert len(result.root.contents) == 1
    content = result.root.contents[0]
    assert content.mimeType == "application/json"
    assert len(content.text) <= RESOURCE_JSON_MAX_CHARS
    payload = json.loads(content.text)
    assert payload == {
        "schema_version": "2",
        "mcp_version": "0.8.8",
        "optional": True,
        "catalog_url": "https://github.com/jumodada/skills-manager",
        "repository_url": "https://github.com/jumodada/skills-manager",
        "source_revision": "v0.8.4",
        "catalog_path": "skills/",
        "skill_entrypoint": "skills/<skill-name>/SKILL.md",
        "status": "repository_examples",
        "skills": list(SKILL_EXAMPLES),
    }


@pytest.mark.asyncio
async def test_unknown_resource_is_rejected_without_browser_initialization() -> None:
    server = DrissionPageMCPServer()
    handler = server.server.request_handlers[ReadResourceRequest]

    with pytest.raises(ValueError, match="Unknown resource URI"):
        await handler(
            ReadResourceRequest(
                method="resources/read",
                params=ReadResourceRequestParams(uri="drissionpage://unknown"),
            )
        )

    assert server.context is None
