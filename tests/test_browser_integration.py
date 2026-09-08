"""Browser integration tests using the deterministic local HTTP fixture."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import urlopen

import pytest

from drissionpage_mcp.server import DrissionPageMCPServer
from drissionpage_mcp.tools.base import ToolOutcome
from tests.fixtures.http_fixture import (
    HTTP_AUTH_PASSWORD,
    HTTP_AUTH_REALM,
    HTTP_AUTH_USERNAME,
    TASK_COMPLETION_DOWNLOAD,
    TASK_COMPLETION_DOWNLOAD_SHA256,
    local_http_fixture,
)

SHARED_TEST_SITE_URL_ENV = "DP_TEST_SITE_URL"
_BROWSER_UNAVAILABLE_MARKERS = (
    "browser",
    "chrome",
    "chromium",
    "cannot find",
    "connection refused",
    "failed to initialize",
    "executable",
)


def test_local_http_fixture_serves_required_routes() -> None:
    """serves all deterministic fixture routes without external network access."""
    with local_http_fixture() as base_url:
        assert _read(base_url + "/")[0] == 200
        assert "DrissionMCP Fixture" in _read(base_url + "/")[1]
        assert "fixture-form" in _read(base_url + "/form")[1]
        assert "dynamic-root" in _read(base_url + "/dynamic")[1]
        assert "Observable Workflow" in _read(base_url + "/observable")[1]
        assert "New Tab Target" in _read(base_url + "/new-tab")[1]
        assert "Automation Catalog" in _read(base_url + "/catalog")[1]
        assert "Link Heavy Page" in _read(base_url + "/link-heavy")[1]
        assert "Console Workflow" in _read(base_url + "/console")[1]
        assert _read(base_url + "/redirect")[0] == 200
        assert _read(base_url + "/status/404")[0] == 404
        assert _read(base_url + "/status/500")[0] == 500
        assert "Iframe Content" in _read(base_url + "/iframe")[1]
        assert "Upload Workflow" in _read(base_url + "/upload")[1]
        assert "Browser Owned Export Marker" in _read(base_url + "/browser-owned")[1]
        assert _read(base_url + "/auth/basic")[0] == 401
        assert "Interaction Workflow" in _read(base_url + "/interactions")[1]
        assert "shadow-host" in _read(base_url + "/shadow")[1]
        assert "Document Boundaries" in _read(base_url + "/document-boundaries")[1]
        assert "Challenge Surfaces" in _read(base_url + "/challenge-surfaces")[1]
        assert "Fixture Challenge Frame" in _read(
            base_url + "/challenge-frame?widget=normal"
        )[1]
        assert "Fixture Turnstile Test Key" in _read(
            base_url + "/turnstile-test?sitekey=test"
        )[1]
        assert "Slider iframe" in _read(base_url + "/slider")[1]
        assert "Same-origin iframe slider" in _read(base_url + "/slider-frame")[1]
        assert "Storage Workflow" in _read(base_url + "/storage")[1]
        assert "Fixture Request Context" in _read(base_url + "/request-context")[1]
        assert "Fixture Resource Controls" in _read(base_url + "/resource-controls")[1]
        assert "Links Workflow" in _read(base_url + "/links")[1]
        assert "Workflow Form" in _read(base_url + "/workflow-form")[1]
        assert "Network Workflow" in _read(base_url + "/network")[1]
        assert "Fixture Dialog" in _read(base_url + "/dialog")[1]
        assert "Fixture Click Variants" in _read(base_url + "/click-variants")[1]
        assert _json(base_url + "/api/data.json")["ok"] is True


def test_shared_drissionpage_test_site_contract_when_configured() -> None:
    """verifies the external shared SSR test-site contract before MCP smoke."""
    base_url = _shared_test_site_url_or_skip()
    health = _json(_site_url(base_url, "/api/health.json"))
    assert health["ok"] is True
    assert health["service"] == "drissionpage-ssr-test-site"
    manifest = _json(_site_url(base_url, "/api/manifest.json"))
    assert manifest["ok"] is True
    case_ids = {item["id"] for item in manifest["cases"]}
    assert {"forms", "locators", "marketplace-flow", "social-notes-mobile"} <= case_ids


def test_shared_drissionpage_test_site_url_preserves_private_query() -> None:
    """keeps secret query tokens when building shared fixture case URLs."""
    base_url = "https://fixture.example.test/base?x-vercel-protection-bypass=secret"
    assert (
        _site_url(base_url, "/cases/forms")
        == "https://fixture.example.test/base/cases/forms?x-vercel-protection-bypass=secret"
    )


@pytest.mark.asyncio
async def test_mcp_browser_tools_use_shared_drissionpage_test_site() -> None:
    """runs MCP browser tools against the shared Astro SSR test-site."""
    base_url = _shared_test_site_url_or_skip()
    server = DrissionPageMCPServer()
    try:
        navigate = await _execute_tool_text(
            server, "page_navigate", {"url": _site_url(base_url, "/cases/forms")}
        )
        _skip_if_browser_unavailable(navigate)
        assert "Successfully navigated" in navigate
        _content, snapshot_payload = await _execute_tool(
            server, "page_snapshot", {"max_elements": 40}
        )
        assert snapshot_payload["ok"] is True
        assert snapshot_payload["data"]["counts"]["forms"] >= 1
        _content, form_payload = await _execute_tool(
            server, "element_find", {"selector": "#profile-form"}
        )
        assert form_payload["data"]["element"]["tag"] == "form"
        _content, name_payload = await _execute_tool(
            server,
            "element_get_property",
            {"selector": "#name", "property": "value"},
        )
        assert name_payload["data"]["value"] == "initial"
        _content, mode_payload = await _execute_tool(
            server, "element_find", {"selector": "#mode"}
        )
        assert mode_payload["data"]["element"]["tag"] == "select"

        _content, center_payload = await _execute_tool(
            server,
            "page_evaluate",
            {
                "script": "const rect = document.querySelector('#agree').getBoundingClientRect(); return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};"
            },
        )
        center = center_payload["data"]["result"]
        _content, pointer_payload = await _execute_tool(
            server,
            "page_click_xy",
            {
                "x": center["x"],
                "y": center["y"],
                "element": "agree checkbox",
            },
        )
        assert pointer_payload["ok"] is True
        motion = pointer_payload["data"]["motion"]
        assert motion["steps"] == 1
        assert motion["delay_before_press_ms"] == 0
        _content, checked_payload = await _execute_tool(
            server,
            "page_evaluate",
            {"script": "return document.querySelector('#agree').checked;"},
        )
        assert checked_payload["data"]["result"] is True
        _content, infinity_payload = await _execute_tool(
            server,
            "page_evaluate",
            {"script": "return 1 / 0;"},
        )
        assert infinity_payload["data"]["result"] is None
        assert infinity_payload["data"]["result_type"] == "number"
        assert infinity_payload["data"]["non_finite_number"] == "Infinity"
        json.dumps(infinity_payload, allow_nan=False)

        _content, drag_fixture = await _execute_tool(
            server,
            "page_evaluate",
            {
                "script": """
                const source = document.createElement('div');
                source.id = 'mcp-drag-source';
                source.style.cssText = 'position:fixed;left:80px;top:80px;width:40px;height:40px;background:red;z-index:2147483647';
                document.body.appendChild(source);
                window.__mcpDragEvents = [];
                source.addEventListener('mousedown', event => window.__mcpDragEvents.push({type: event.type, x: event.clientX, y: event.clientY}));
                document.addEventListener('mousemove', event => { if (event.buttons) window.__mcpDragEvents.push({type: event.type, buttons: event.buttons}); });
                document.addEventListener('mouseup', event => window.__mcpDragEvents.push({type: event.type, x: event.clientX, y: event.clientY}));
                return true;
                """
            },
        )
        assert drag_fixture["data"]["result"] is True
        _content, drag_payload = await _execute_tool(
            server,
            "page_pointer_drag",
            {
                "start_x": 100,
                "start_y": 100,
                "end_x": 260,
                "end_y": 180,
                "element": "integration drag fixture",
            },
        )
        assert drag_payload["ok"] is True
        assert drag_payload["data"]["motion"]["drag_steps"] == 1
        _content, drag_events = await _execute_tool(
            server,
            "page_evaluate",
            {"script": "return window.__mcpDragEvents;"},
        )
        event_types = [event["type"] for event in drag_events["data"]["result"]]
        assert event_types[0] == "mousedown"
        assert "mousemove" in event_types
        assert event_types[-1] == "mouseup"

        navigate = await _execute_tool_text(
            server, "page_navigate", {"url": _site_url(base_url, "/cases/locators")}
        )
        _skip_if_browser_unavailable(navigate)
        _content, target_payload = await _execute_tool(
            server, "element_find", {"selector": "#target", "timeout": 3}
        )
        assert target_payload["ok"] is True
        target = target_payload["data"]["element"]
        assert target["text"] == "target div"
        assert 'data-testid="xpath-target"' in target["html"]
        navigate = await _execute_tool_text(
            server,
            "page_navigate",
            {"url": _site_url(base_url, "/scenarios/marketplace")},
        )
        _skip_if_browser_unavailable(navigate)
        _content, snapshot_payload = await _execute_tool(
            server, "page_snapshot", {"max_elements": 40, "max_text_chars": 1500}
        )
        assert snapshot_payload["ok"] is True
        snapshot = snapshot_payload["data"]
        assert snapshot["title"] == "Marketplace full flow"
        assert "橙市集" in snapshot["text_excerpt"]
        _content, cards_payload = await _execute_tool(
            server,
            "element_find_all",
            {"selector": '[data-testid="marketplace-home-card"]', "limit": 3},
        )
        assert cards_payload["ok"] is True
        assert cards_payload["data"]["count"] >= 12
        assert cards_payload["data"]["returned"] == 3
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_browser_tools_can_read_local_fixture_page() -> None:
    """navigates to a local fixture page and reads page text through MCP tools."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/"}
            )
            _skip_if_browser_unavailable(navigate)
            assert "Successfully navigated" in navigate
            text = await _execute_tool_text(
                server, "element_get_text", {"selector": "#app"}
            )
            _skip_if_browser_unavailable(text)
            assert "DrissionMCP Fixture" in text
            frame = await _execute_tool_text(
                server,
                "element_get_attribute",
                {"selector": "#fixture-frame", "attribute": "src"},
            )
            _skip_if_browser_unavailable(frame)
            assert "/iframe" in frame
            form_nav = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/form"}
            )
            _skip_if_browser_unavailable(form_nav)
            assert "Successfully navigated" in form_nav
            typed = await _execute_tool_text(
                server,
                "element_type",
                {"selector": "#name", "text": "Ada", "clear": True},
            )
            _skip_if_browser_unavailable(typed)
            assert "Successfully typed" in typed
            value = await _execute_tool_text(
                server,
                "element_get_property",
                {"selector": "#name", "property": "value"},
            )
            _skip_if_browser_unavailable(value)
            assert "Ada" in value
            _content, infinity_payload = await _execute_tool(
                server, "page_evaluate", {"script": "return 1 / 0;"}
            )
            assert infinity_payload["data"]["result"] is None
            assert infinity_payload["data"]["result_type"] == "number"
            assert infinity_payload["data"]["non_finite_number"] == "Infinity"
            json.dumps(infinity_payload, allow_nan=False)
            screenshot, screenshot_payload = await _execute_tool(
                server, "page_screenshot", {}
            )
            text_content = "\n".join(
                item.text for item in screenshot if item.type == "text"
            )
            _skip_if_browser_unavailable(text_content)
            images = [item for item in screenshot if item.type == "image"]
            assert images
            assert base64.b64decode(images[0].data).startswith(b"\x89PNG")
            metadata = screenshot_payload["data"]["screenshot"]
            assert metadata["mime_type"] == "image/png"
            assert metadata["inline"] is True
            assert metadata["encoding"] == "base64"
            assert metadata["full_page"] is False
            assert metadata["bytes"] > 0
            assert metadata["width"] > 0
            assert metadata["height"] > 0
            closed = await _execute_tool_text(server, "page_close", {})
            assert "Successfully closed browser" in closed
    finally:
        await server.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("context", ["iframe", "shadow"])
async def test_selector_first_drag_resolves_embedded_slider_atomically(
    context: str,
) -> None:
    """resolves thumb and track immediately before a strict embedded drag."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/slider"}
            )
            _skip_if_browser_unavailable(navigate)
            await _execute_tool(server, "page_resize", {"width": 800, "height": 700})
            if context == "iframe":
                source = {
                    "selector": "#frame-knob",
                    "frame_selector": "#slider-frame",
                }
                track = {
                    "selector": "#frame-track",
                    "frame_selector": "#slider-frame",
                }
                result_script = """
                    const state = document.querySelector('#slider-frame').contentWindow.__frameSlider;
                    return {accepted: state.accepted, dragging: state.dragging, metrics: state.metrics};
                """
            else:
                path = ["#shadow-slider-host", "#nested-slider-host"]
                source = {"selector": "#shadow-knob", "shadow_hosts": path}
                track = {"selector": "#shadow-track", "shadow_hosts": path}
                result_script = """
                    const state = window.__shadowSlider;
                    return {accepted: state.accepted, dragging: state.dragging, metrics: state.metrics};
                """

            _content, drag_payload = await _execute_tool(
                server,
                "page_pointer_drag_element",
                {
                    "source": source,
                    "destination": {
                        "kind": "track_ratio",
                        "track": track,
                        "ratio": 1.0,
                        "axis": "x",
                    },
                },
            )
            assert drag_payload["ok"] is True
            data = drag_payload["data"]
            assert data["destination"]["kind"] == "track_ratio"
            assert data["destination"]["ratio"] == 1.0
            assert data["destination"]["axis"] == "x"
            assert data["motion"]["target_x"] == pytest.approx(data["destination"]["x"])
            if context == "iframe":
                assert data["source"]["frame_selector"] == "#slider-frame"
            else:
                assert data["source"]["shadow_hosts"] == [
                    "#shadow-slider-host",
                    "#nested-slider-host",
                ]

            _content, result_payload = await _execute_tool(
                server, "page_evaluate", {"script": result_script}
            )
            state = result_payload["data"]["result"]
            assert state["accepted"] is False, state["metrics"]
            assert state["dragging"] is False
            assert state["metrics"]["allTrusted"] is True
            assert state["metrics"]["moveCount"] == 1
            assert state["metrics"]["upCount"] == 1
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_selector_first_drag_uses_layout_after_shadow_host_moves() -> None:
    """proves selector resolution uses the final layout rather than stale coordinates."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/slider"}
            )
            _skip_if_browser_unavailable(navigate)
            await _execute_tool(server, "page_resize", {"width": 1000, "height": 700})
            _content, before_payload = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": """
                    const root = document.querySelector('#shadow-slider-host').shadowRoot
                      .querySelector('#nested-slider-host').shadowRoot;
                    const rect = root.querySelector('#shadow-knob').getBoundingClientRect();
                    return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
                    """
                },
            )
            old = before_payload["data"]["result"]
            _content, moved_payload = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": """
                    document.querySelector('#shadow-slider-host').style.left = '240px';
                    return true;
                    """
                },
            )
            assert moved_payload["data"]["result"] is True
            path = ["#shadow-slider-host", "#nested-slider-host"]
            _content, drag_payload = await _execute_tool(
                server,
                "page_pointer_drag_element",
                {
                    "source": {"selector": "#shadow-knob", "shadow_hosts": path},
                    "destination": {
                        "kind": "track_ratio",
                        "track": {
                            "selector": "#shadow-track",
                            "shadow_hosts": path,
                        },
                        "ratio": 1,
                        "axis": "x",
                    },
                },
            )
            assert drag_payload["ok"] is True
            assert drag_payload["data"]["source"]["x"] > old["x"] + 150
            _content, result_payload = await _execute_tool(
                server,
                "page_evaluate",
                {"script": "return window.__shadowSlider.accepted;"},
            )
            assert result_payload["data"]["result"] is False
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_direct_drag_is_rejected_by_strict_slider_trajectory_gate() -> None:
    """proves the fixture rejects teleport-like one-step dragging."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/slider"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, coordinate_payload = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": """
                    const frame = document.querySelector('#slider-frame');
                    const frameRect = frame.getBoundingClientRect();
                    const doc = frame.contentDocument;
                    const knob = doc.querySelector('#frame-knob').getBoundingClientRect();
                    const track = doc.querySelector('#frame-track').getBoundingClientRect();
                    return {
                      start_x: frameRect.left + knob.left + knob.width / 2,
                      start_y: frameRect.top + knob.top + knob.height / 2,
                      end_x: frameRect.left + track.right - knob.width / 2,
                      end_y: frameRect.top + knob.top + knob.height / 2
                    };
                    """
                },
            )
            _content, drag_payload = await _execute_tool(
                server,
                "page_pointer_drag",
                {
                    **coordinate_payload["data"]["result"],
                    "element": "strict iframe slider negative control",
                },
            )
            assert drag_payload["ok"] is True
            assert drag_payload["data"]["motion"]["drag_steps"] == 1
            _content, result_payload = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": "return document.querySelector('#slider-frame').contentWindow.__frameSlider;",
                    "max_chars": 20000,
                },
            )
            state = result_payload["data"]["result"]
            assert state["accepted"] is False
            assert state["dragging"] is False
            assert state["metrics"]["moveCount"] < 20
            assert state["metrics"]["eased"] is False
            assert state["metrics"]["upCount"] == 1
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_natural_drag_passes_strict_slider_trajectory_gate() -> None:
    """proves bounded natural motion reaches Chromium as one eased held gesture."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/slider"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, coordinate_payload = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": """
                    const frame = document.querySelector('#slider-frame');
                    const frameRect = frame.getBoundingClientRect();
                    const doc = frame.contentDocument;
                    const knob = doc.querySelector('#frame-knob').getBoundingClientRect();
                    const track = doc.querySelector('#frame-track').getBoundingClientRect();
                    return {
                      start_x: frameRect.left + knob.left + knob.width / 2,
                      start_y: frameRect.top + knob.top + knob.height / 2,
                      end_x: frameRect.left + track.right - knob.width / 2,
                      end_y: frameRect.top + knob.top + knob.height / 2
                    };
                    """
                },
            )
            _content, drag_payload = await _execute_tool(
                server,
                "page_pointer_drag",
                {
                    **coordinate_payload["data"]["result"],
                    "profile": "natural",
                    "element": "strict iframe slider natural trajectory",
                },
            )
            assert drag_payload["ok"] is True
            motion = drag_payload["data"]["motion"]
            assert motion["profile"] == "natural"
            assert motion["drag_steps"] == 24
            _content, result_payload = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": "return document.querySelector('#slider-frame').contentWindow.__frameSlider;",
                    "max_chars": 20000,
                },
            )
            state = result_payload["data"]["result"]
            assert state["accepted"] is True, state["metrics"]
            assert state["dragging"] is False
            assert state["metrics"]["moveCount"] == 24
            assert state["metrics"]["eased"] is True
            assert state["metrics"]["upCount"] == 1
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_pointer_drag_follows_waypoints_in_one_browser_gesture() -> None:
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/interactions"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, setup_payload = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": """
                    const events = [];
                    const surface = document.createElement('div');
                    surface.style.cssText = 'position:fixed;inset:0;z-index:2147483647';
                    document.body.appendChild(surface);
                    surface.addEventListener('mousedown', event => {
                      event.preventDefault();
                      events.push({type: event.type, x: event.clientX, y: event.clientY});
                    });
                    document.addEventListener('mousemove', event => {
                      if (event.buttons) events.push({type: event.type, x: event.clientX, y: event.clientY, buttons: event.buttons});
                    });
                    document.addEventListener('mouseup', event => events.push({type: event.type, x: event.clientX, y: event.clientY}));
                    window.__waypointDragEvents = events;
                    return true;
                    """
                },
            )
            assert setup_payload["data"]["result"] is True

            _content, drag_payload = await _execute_tool(
                server,
                "page_pointer_drag",
                {
                    "start_x": 100,
                    "start_y": 100,
                    "waypoints": [{"x": 240, "y": 100}, {"x": 240, "y": 240}],
                    "end_x": 100,
                    "end_y": 240,
                    "element": "integration waypoint path",
                },
            )
            assert drag_payload["ok"] is True
            assert drag_payload["data"]["motion"]["drag_steps"] == 3

            _content, events_payload = await _execute_tool(
                server,
                "page_evaluate",
                {"script": "return window.__waypointDragEvents;"},
            )
            events = events_payload["data"]["result"]
            assert [event["type"] for event in events] == [
                "mousedown",
                "mousemove",
                "mousemove",
                "mousemove",
                "mouseup",
            ]
            assert [(event["x"], event["y"]) for event in events[1:-1]] == [
                (240, 100),
                (240, 240),
                (100, 240),
            ]
            assert all(event["buttons"] == 1 for event in events[1:-1])
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_tab_tools_discover_target_blank_tabs() -> None:
    """discovers, switches, and closes a tab opened by target=_blank."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/"}
            )
            _skip_if_browser_unavailable(navigate)
            assert "Successfully navigated" in navigate
            _content, initial_tabs = await _execute_tool(server, "tab_list", {})
            assert initial_tabs["ok"] is True
            initial_count = initial_tabs["data"]["count"]
            active_id = initial_tabs["data"]["active_tab_id"]
            _content, click_payload = await _execute_tool(
                server, "element_click", {"selector": "#new-tab-link", "timeout": 2}
            )
            assert click_payload["ok"] is True
            _content, tabs_payload = await _execute_tool(server, "tab_list", {})
            assert tabs_payload["ok"] is True
            tabs_data = tabs_payload["data"]
            assert tabs_data["count"] >= initial_count + 1
            target_tabs = [
                tab for tab in tabs_data["tabs"] if tab["url"].endswith("/new-tab")
            ]
            assert target_tabs
            new_tab_id = target_tabs[0]["id"]
            _content, switch_payload = await _execute_tool(
                server, "tab_switch", {"tab_id": new_tab_id}
            )
            assert switch_payload["ok"] is True
            _content, url_payload = await _execute_tool(server, "page_get_url", {})
            assert url_payload["data"]["url"].endswith("/new-tab")
            _content, close_payload = await _execute_tool(
                server, "tab_close", {"tab_id": new_tab_id}
            )
            assert close_payload["ok"] is True
            _content, switch_back = await _execute_tool(
                server, "tab_switch", {"tab_id": active_id}
            )
            assert switch_back["ok"] is True
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_page_dialog_respond_handles_alert_confirm_and_redacted_prompt() -> (
    None
):
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/dialog"}
            )
            _skip_if_browser_unavailable(navigate)

            started = asyncio.get_running_loop().time()
            _content, no_dialog = await _execute_tool(
                server, "page_dialog_respond", {"action": "accept"}
            )
            assert no_dialog["ok"] is False
            assert no_dialog["error"]["code"] == "DIALOG_NOT_FOUND"
            assert asyncio.get_running_loop().time() - started < 0.5

            _content, scheduled = await _execute_tool(
                server,
                "page_evaluate",
                {
                        "script": (
                            "setTimeout(() => alert('pending-public-error-test'), 100); "
                            "return true;"
                        )
                },
            )
            assert scheduled["ok"] is True
            await asyncio.sleep(0.2)
            _content, blocked = await _execute_tool(server, "page_observe", {})
            assert blocked["ok"] is False
            assert blocked["error"]["code"] == "DIALOG_PENDING"
            blocked_public = json.dumps(blocked, ensure_ascii=False)
            assert "版本" not in blocked_public
            assert "4.1.1.4" not in blocked_public
            assert {hint.get("tool") for hint in blocked["error"]["details"]["hints"]} >= {
                "page_dialog_observe",
                "page_dialog_respond",
            }
            _content, cleared = await _execute_tool(
                server, "page_dialog_respond", {"action": "accept"}
            )
            assert cleared["ok"] is True

            async def trigger_and_respond(
                selector: str, *, action: str, prompt_text: str | None = None
            ) -> dict[str, Any]:
                click_task = asyncio.create_task(
                    _execute_tool(
                        server,
                        "element_click",
                        {"selector": selector, "timeout": 2},
                    )
                )
                arguments: dict[str, Any] = {"action": action, "timeout": 2}
                if prompt_text is not None:
                    arguments["prompt_text"] = prompt_text
                _content, payload = await _execute_tool(
                    server, "page_dialog_respond", arguments
                )
                await click_task
                return payload

            alert = await trigger_and_respond("#alert-button", action="accept")
            assert alert["ok"] is True
            assert alert["data"]["dialog_type"] == "alert"
            assert alert["data"]["action"] == "accept"
            assert alert["data"]["handled"] is True
            assert alert["data"]["dialog_message"] == {
                "present": True,
                "length": len("Fixture alert"),
                "redacted": True,
            }
            assert alert["data"]["receipt"]["side_effect"] == "dialog_response"
            _content, status = await _execute_tool(
                server, "element_get_text", {"selector": "#dialog-status"}
            )
            assert status["data"]["text"] == "alert accepted"

            for action, expected in (
                ("accept", "confirm accepted"),
                ("dismiss", "confirm dismissed"),
            ):
                confirm = await trigger_and_respond("#confirm-button", action=action)
                assert confirm["ok"] is True
                assert confirm["data"]["dialog_type"] == "confirm"
                assert confirm["data"]["action"] == action
                _content, status = await _execute_tool(
                    server, "element_get_text", {"selector": "#dialog-status"}
                )
                assert status["data"]["text"] == expected

            safe_prompt = "quarterly-review-ready"
            prompt = await trigger_and_respond(
                "#prompt-button", action="accept", prompt_text=safe_prompt
            )
            assert prompt["ok"] is True
            assert prompt["data"]["dialog_type"] == "prompt"
            assert prompt["data"]["prompt"] == {
                "provided": True,
                "length": len(safe_prompt),
                "redacted": True,
            }
            assert safe_prompt not in json.dumps(prompt, ensure_ascii=False)
            assert "Fixture prompt" not in json.dumps(prompt, ensure_ascii=False)
            _content, status = await _execute_tool(
                server, "element_get_text", {"selector": "#dialog-status"}
            )
            assert status["data"]["text"] == f"prompt accepted:{safe_prompt}"
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_dialog_observe_returns_message_without_handling_dialog() -> None:
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/dialog"}
            )
            _skip_if_browser_unavailable(navigate)

            observe_task = asyncio.create_task(
                _execute_tool(
                    server,
                    "page_dialog_observe",
                    {"timeout": 3, "max_message_chars": 100},
                )
            )
            await asyncio.sleep(0.05)
            click_task = asyncio.create_task(
                _execute_tool(
                    server,
                    "element_click",
                    {
                        "selector": {
                            "kind": "accessibility",
                            "role": "button",
                            "name": "Confirm",
                        },
                        "timeout": 2,
                    },
                )
            )
            _content, observed = await observe_task
            assert observed["ok"] is True
            assert observed["data"] == {
                "pending": True,
                "timed_out": False,
                "dialog_type": "confirm",
                "message": "Fixture confirm",
                "message_truncated": False,
                "timeout": 3.0,
            }

            _content, response = await _execute_tool(
                server,
                "page_dialog_respond",
                {"action": "dismiss", "timeout": 2},
            )
            assert response["ok"] is True
            _content, clicked = await click_task
            assert clicked["ok"] is True
            _content, status = await _execute_tool(
                server, "element_get_text", {"selector": "#dialog-status"}
            )
            assert status["data"]["text"] == "confirm dismissed"
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_element_click_preserves_default_and_exact_variant_semantics() -> (
    None
):
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/click-variants"}
            )
            _skip_if_browser_unavailable(navigate)

            _content, default_click = await _execute_tool(
                server,
                "element_click",
                {"selector": "#click-target", "timeout": 2},
            )
            assert default_click["ok"] is True
            assert default_click["data"]["button"] == "left"
            assert default_click["data"]["click_count"] == 1
            _content, default_events = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": "return {counts: window.__clickCounts, events: window.__clickEvents};"
                },
            )
            assert default_events["data"]["result"] == {
                "counts": {
                    "click": 1,
                    "dblclick": 0,
                    "contextmenu": 0,
                    "shortcut": 0,
                },
                "events": [
                    {"type": "click", "button": 0, "detail": 1, "trusted": True}
                ],
            }

            await _execute_tool(
                server, "page_navigate", {"url": base_url + "/click-variants"}
            )
            _content, double_click = await _execute_tool(
                server,
                "element_click",
                {
                    "selector": "#click-target",
                    "button": "left",
                    "click_count": 2,
                    "timeout": 2,
                },
            )
            assert double_click["ok"] is True
            assert double_click["data"]["button"] == "left"
            assert double_click["data"]["click_count"] == 2
            _content, double_events = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": "return {counts: window.__clickCounts, events: window.__clickEvents};"
                },
            )
            double_result = double_events["data"]["result"]
            assert double_result["counts"] == {
                "click": 1,
                "dblclick": 1,
                "contextmenu": 0,
                "shortcut": 0,
            }
            assert [event["type"] for event in double_result["events"]] == [
                "click",
                "dblclick",
            ]
            assert [event["detail"] for event in double_result["events"]] == [2, 2]
            assert all(event["button"] == 0 for event in double_result["events"])
            assert all(event["trusted"] is True for event in double_result["events"])

            await _execute_tool(
                server, "page_navigate", {"url": base_url + "/click-variants"}
            )
            _content, right_click = await _execute_tool(
                server,
                "element_click",
                {
                    "selector": "#click-target",
                    "button": "right",
                    "click_count": 1,
                    "timeout": 2,
                },
            )
            assert right_click["ok"] is True
            assert right_click["data"]["button"] == "right"
            assert right_click["data"]["click_count"] == 1
            _content, right_events = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": "return {counts: window.__clickCounts, events: window.__clickEvents};"
                },
            )
            assert right_events["data"]["result"] == {
                "counts": {
                    "click": 0,
                    "dblclick": 0,
                    "contextmenu": 1,
                    "shortcut": 0,
                },
                "events": [
                    {
                        "type": "contextmenu",
                        "button": 2,
                        "detail": 0,
                        "trusted": True,
                    }
                ],
            }

            _content, keyboard = await _execute_tool(
                server,
                "keyboard_press",
                {"keys": "\ue03ds"},
            )
            assert keyboard["ok"] is True
            _content, shortcut_events = await _execute_tool(
                server,
                "page_evaluate",
                {"script": "return window.__clickCounts;"},
            )
            assert shortcut_events["data"]["result"] == {
                "click": 0,
                "dblclick": 0,
                "contextmenu": 1,
                "shortcut": 1,
            }
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_element_click_and_download_returns_one_safe_integrity_checked_artifact(
    monkeypatch, tmp_path
) -> None:
    server = DrissionPageMCPServer()
    download_root = tmp_path / "mcp-downloads"
    monkeypatch.setenv("DP_MCP_DOWNLOAD_ROOT", str(download_root))
    monkeypatch.delenv("DP_MCP_DENY_DOWNLOAD", raising=False)
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/download"}
            )
            _skip_if_browser_unavailable(navigate)

            _content, first = await _execute_tool(
                server,
                "element_click_and_download",
                {
                    "selector": "#download-link",
                    "operation_key": "fixture-download-1",
                    "timeout": 10,
                    "expected_filename": "fixture-report.csv",
                    "expected_mime_type": "text/csv",
                },
            )
            assert first["ok"] is True
            data = first["data"]
            artifact = data["artifact"]
            assert data["status"] == "success"
            assert artifact["filename"] == "fixture-report.csv"
            assert artifact["mime_type"] == "text/csv"
            assert artifact["size_bytes"] == len(TASK_COMPLETION_DOWNLOAD)
            assert artifact["sha256"] == TASK_COMPLETION_DOWNLOAD_SHA256
            assert artifact["status"] == "complete"
            assert artifact["source_url"] == base_url + "/task/download.csv"
            assert not os.path.isabs(artifact["safe_relative_path"])
            assert ".." not in Path(artifact["safe_relative_path"]).parts
            assert artifact["producing_action_id"] == data["receipt"]["action_id"]
            assert data["receipt"]["artifact_ids"] == [artifact["artifact_id"]]
            assert (download_root / artifact["safe_relative_path"]).read_bytes() == (
                TASK_COMPLETION_DOWNLOAD
            )
            assert [path for path in download_root.rglob("*") if path.is_file()] == [
                download_root / artifact["safe_relative_path"]
            ]
            assert str(download_root) not in json.dumps(first, ensure_ascii=False)
            assert server.context is not None
            state = _json(base_url + "/__fixture__/state")
            assert state["counters"] == {"download_requests": 1}

            await _execute_tool(server, "page_close", {})
            monkeypatch.setenv("DP_MCP_DENY_DOWNLOAD", "1")
            monkeypatch.delenv("DP_MCP_DOWNLOAD_ROOT", raising=False)
            _content, replay = await _execute_tool(
                server,
                "element_click_and_download",
                {
                    "selector": "#download-link",
                    "operation_key": "fixture-download-1",
                    "timeout": 10,
                    "expected_filename": "fixture-report.csv",
                    "expected_mime_type": "text/csv",
                },
            )
            assert replay["ok"] is True
            assert replay["data"] == data
            assert _json(base_url + "/__fixture__/state")["counters"] == {
                "download_requests": 1
            }
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_coordinate_and_keyboard_download_triggers_correlate_once(
    monkeypatch, tmp_path
) -> None:
    server = DrissionPageMCPServer()
    download_root = tmp_path / "mcp-trigger-downloads"
    monkeypatch.setenv("DP_MCP_DOWNLOAD_ROOT", str(download_root))
    monkeypatch.delenv("DP_MCP_DENY_DOWNLOAD", raising=False)
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/download"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, center_payload = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": (
                        "const rect = document.querySelector('#download-link')"
                        ".getBoundingClientRect(); "
                        "return {x: rect.left + rect.width / 2, "
                        "y: rect.top + rect.height / 2};"
                    )
                },
            )
            center = center_payload["data"]["result"]
            coordinate_args = {
                "selector": {
                    "kind": "coordinate",
                    "x": center["x"],
                    "y": center["y"],
                    "profile": "direct",
                    "delay_before_press_ms": 0,
                },
                "operation_key": "fixture-coordinate-download",
                "timeout": 10,
                "expected_filename": "fixture-report.csv",
                "expected_mime_type": "text/csv",
            }

            _content, coordinate = await _execute_tool(
                server,
                "element_click_and_download",
                coordinate_args,
            )
            _content, coordinate_replay = await _execute_tool(
                server,
                "element_click_and_download",
                coordinate_args,
            )

            assert coordinate["ok"] is True
            coordinate_data = coordinate["data"]
            assert coordinate_replay["data"] == coordinate_data
            assert coordinate_data["trigger"] == {
                "kind": "coordinate",
                "x": center["x"],
                "y": center["y"],
                "profile": "direct",
                "delay_before_press_ms": 0,
            }
            assert "selector" not in coordinate_data
            assert _json(base_url + "/__fixture__/state")["counters"] == {
                "download_requests": 1
            }

            enter_key = "\ue007"
            _content, focus = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": (
                        "document.querySelector('#download-link').focus(); "
                        "return document.activeElement.id;"
                    )
                },
            )
            assert focus["data"]["result"] == "download-link"
            keyboard_args = {
                "selector": {
                    "kind": "keyboard",
                    "keys": enter_key,
                    "interval": 0,
                },
                "operation_key": "fixture-keyboard-download",
                "timeout": 10,
                "expected_filename": "fixture-report.csv",
                "expected_mime_type": "text/csv",
            }

            _content, keyboard = await _execute_tool(
                server,
                "element_click_and_download",
                keyboard_args,
            )
            _content, keyboard_replay = await _execute_tool(
                server,
                "element_click_and_download",
                keyboard_args,
            )

            assert keyboard["ok"] is True
            keyboard_data = keyboard["data"]
            assert keyboard_replay["data"] == keyboard_data
            assert keyboard_data["trigger"] == {
                "kind": "keyboard",
                "keys": {"provided": True, "length": 1, "redacted": True},
                "interval": 0,
            }
            assert enter_key not in json.dumps(keyboard, ensure_ascii=False)
            assert "selector" not in keyboard_data
            assert _json(base_url + "/__fixture__/state")["counters"] == {
                "download_requests": 2
            }

            artifacts = [
                coordinate_data["artifact"],
                keyboard_data["artifact"],
            ]
            assert {artifact["sha256"] for artifact in artifacts} == {
                TASK_COMPLETION_DOWNLOAD_SHA256
            }
            paths = [
                download_root / artifact["safe_relative_path"]
                for artifact in artifacts
            ]
            assert len({path.parent for path in paths}) == 2
            assert all(path.read_bytes() == TASK_COMPLETION_DOWNLOAD for path in paths)
            assert sorted(path for path in download_root.rglob("*") if path.is_file()) == (
                sorted(paths)
            )
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_element_click_and_download_failure_has_no_artifact_or_success(
    monkeypatch, tmp_path
) -> None:
    server = DrissionPageMCPServer()
    download_root = tmp_path / "mcp-download-failure"
    monkeypatch.setenv("DP_MCP_DOWNLOAD_ROOT", str(download_root))
    monkeypatch.delenv("DP_MCP_DENY_DOWNLOAD", raising=False)
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/download-fail"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, failure = await _execute_tool(
                server,
                "element_click_and_download",
                {
                    "selector": "#download-fail-link",
                    "operation_key": "fixture-download-fail-1",
                    "timeout": 2,
                },
            )
            assert failure["ok"] is False
            assert failure["error"]["code"] in {"TIMEOUT", "UNKNOWN_ERROR"}
            assert failure["data"]["artifact"] is None
            assert failure["data"]["status"] != "success"
            assert failure["data"]["receipt"]["status"] != "success"
            assert not [path for path in download_root.rglob("*") if path.is_file()]
            assert server.context is not None
            assert list(server.context._artifacts.values()) == []
            assert (
                list(server.context._operation_receipts.values())[0].status != "success"
            )
            assert _json(base_url + "/__fixture__/state")["counters"] == {
                "download_fail_requests": 1
            }
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_browser_tools_normalize_llm_friendly_selectors() -> None:
    """treats bare selectors as CSS and preserves explicit DrissionPage locators."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/selectors"}
            )
            _skip_if_browser_unavailable(navigate)
            assert "Successfully navigated" in navigate
            _content, h1_payload = await _execute_tool(
                server, "element_find", {"selector": "h1", "timeout": 2}
            )
            assert h1_payload["ok"] is True
            h1 = h1_payload["data"]["element"]
            assert h1["tag"] == "h1"
            assert h1["locator"] == "css:h1"
            assert h1["selector_strategy"] == "css"
            assert h1["selector_normalized"] is True
            _content, input_payload = await _execute_tool(
                server,
                "element_find",
                {"selector": "input[name='custname']", "timeout": 2},
            )
            assert input_payload["ok"] is True
            input_element = input_payload["data"]["element"]
            assert input_element["tag"] == "input"
            assert input_element["locator"] == "css:input[name='custname']"
            _content, explicit_payload = await _execute_tool(
                server, "element_find", {"selector": "tag:h1", "timeout": 2}
            )
            assert explicit_payload["ok"] is True
            explicit = explicit_payload["data"]["element"]
            assert explicit["tag"] == "h1"
            assert explicit["locator"] == "tag:h1"
            assert explicit["selector_normalized"] is False
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_browser_tools_complete_form_submission_flow() -> None:
    """fills and submits a local form through public MCP tools."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/form"}
            )
            _skip_if_browser_unavailable(navigate)
            assert "Successfully navigated" in navigate
            _content, field_payload = await _execute_tool(
                server, "element_find", {"selector": "#name", "timeout": 2}
            )
            assert field_payload["ok"] is True
            field = field_payload["data"]["element"]
            assert field["tag"] == "input"
            assert field["locator"] == "css:#name"
            assert field["selector_normalized"] is True
            _content, typed_payload = await _execute_tool(
                server,
                "element_type",
                {
                    "selector": "#name",
                    "text": "Ada Lovelace",
                    "clear": True,
                    "timeout": 2,
                },
            )
            assert typed_payload["ok"] is True
            assert typed_payload["data"]["typed"] is True
            assert typed_payload["data"]["cleared"] is True
            _content, value_payload = await _execute_tool(
                server,
                "element_get_property",
                {"selector": "#name", "property": "value"},
            )
            assert value_payload["ok"] is True
            assert value_payload["data"]["value"] == "Ada Lovelace"
            _content, click_payload = await _execute_tool(
                server, "element_click", {"selector": "#submit", "timeout": 2}
            )
            assert click_payload["ok"] is True
            assert click_payload["data"]["locator"] == "css:#submit"
            _content, url_payload = await _execute_tool(
                server, "wait_for_url", {"url_pattern": "name=Ada", "timeout": 3}
            )
            assert url_payload["ok"] is True
            assert "name=Ada" in url_payload["data"]["url"]
            _content, submitted_payload = await _execute_tool(
                server, "element_get_text", {"selector": "#submitted"}
            )
            assert submitted_payload["ok"] is True
            assert submitted_payload["data"]["text"] == "Ada Lovelace"
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_atomic_tools_handle_event_driven_and_aria_widgets() -> None:
    """Prove generic element tools operate stateful inputs and page-level widgets."""

    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/form-controlled"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, typed = await _execute_tool(
                server,
                "element_type",
                {
                    "selector": "#controlled-name",
                    "text": "Atomic input",
                    "clear": True,
                    "timeout": 2,
                },
            )
            assert typed["ok"] is True
            _content, value = await _execute_tool(
                server,
                "element_get_property",
                {"selector": "#controlled-name", "property": "value"},
            )
            assert value["data"]["value"] == "Atomic input"
            _content, rendered = await _execute_tool(
                server, "element_get_text", {"selector": "#controlled-rendered"}
            )
            assert rendered["data"]["text"].startswith("Atomic input; input=")

            _content, navigate_payload = await _execute_tool(
                server, "page_navigate", {"url": base_url + "/interactions"}
            )
            assert navigate_payload["ok"] is True
            _content, editor = await _execute_tool(
                server,
                "element_type",
                {
                    "selector": "#editable-notes",
                    "text": "Framework-neutral notes",
                    "clear": True,
                    "timeout": 2,
                },
            )
            assert editor["ok"] is True
            _content, editor_text = await _execute_tool(
                server, "element_get_text", {"selector": "#editable-notes"}
            )
            assert editor_text["data"]["text"] == "Framework-neutral notes"

            _content, switch = await _execute_tool(
                server, "element_click", {"selector": "#mode-switch", "timeout": 2}
            )
            assert switch["ok"] is True
            _content, checked = await _execute_tool(
                server,
                "element_get_attribute",
                {"selector": "#mode-switch", "attribute": "aria-checked"},
            )
            assert checked["data"]["value"] == "true"

            _content, opened = await _execute_tool(
                server, "element_click", {"selector": "#city-picker", "timeout": 2}
            )
            assert opened["ok"] is True
            _content, selected = await _execute_tool(
                server,
                "element_click",
                {
                    "selector": '#city-options [data-value="Shanghai"]',
                    "timeout": 2,
                },
            )
            assert selected["ok"] is True
            _content, city = await _execute_tool(
                server,
                "element_get_property",
                {"selector": "#city-picker", "property": "value"},
            )
            assert city["data"]["value"] == "Shanghai"
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_browser_tools_wait_for_dynamic_dom_content() -> None:
    """waits for deterministic JavaScript-rendered content before reading it."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/dynamic"}
            )
            _skip_if_browser_unavailable(navigate)
            assert "Successfully navigated" in navigate
            _content, wait_payload = await _execute_tool(
                server, "wait_for_element", {"selector": "#dynamic-ready", "timeout": 3}
            )
            assert wait_payload["ok"] is True
            assert wait_payload["data"] == {
                "selector": "#dynamic-ready",
                "locator": "css:#dynamic-ready",
                "selector_strategy": "css",
                "selector_normalized": True,
                "found": True,
                "timeout": 3,
            }
            _content, text_payload = await _execute_tool(
                server, "element_get_text", {"selector": "#dynamic-ready"}
            )
            assert text_payload["ok"] is True
            assert text_payload["data"]["text"] == "dynamic content ready"
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_observable_actions_cover_dynamic_business_flow() -> None:
    """uses observable tools to wait for and verify a delayed UI action."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/observable"}
            )
            _skip_if_browser_unavailable(navigate)
            assert "Successfully navigated" in navigate
            _content, clickable_payload = await _execute_tool(
                server,
                "wait_until",
                {"condition": "clickable", "selector": "#delayed", "timeout": 3},
            )
            assert clickable_payload["ok"] is True
            assert clickable_payload["data"]["state"]["disabled"] is False
            _content, hidden_payload = await _execute_tool(
                server,
                "wait_until",
                {"condition": "hidden", "selector": "#spinner", "timeout": 3},
            )
            assert hidden_payload["ok"] is True
            _content, observe_payload = await _execute_tool(
                server, "page_observe", {"max_texts": 5}
            )
            assert observe_payload["ok"] is True
            assert "ready" in observe_payload["data"]["text_samples"]
            _content, evaluate_payload = await _execute_tool(
                server,
                "page_evaluate",
                {"script": "return document.querySelector('#status').textContent;"},
            )
            assert evaluate_payload["ok"] is True
            assert evaluate_payload["data"]["result"] == "ready"
            _content, click_payload = await _execute_tool(
                server,
                "element_click",
                {"selector": "#delayed", "timeout": 2, "observe": True},
            )
            assert click_payload["ok"] is True
            changes = click_payload["data"]["changes"]
            assert changes["url_changed"] is True
            assert "saved=1" in changes["url_after"]
            assert "Saved successfully" in changes["appeared_texts"]
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_console_logs_and_observe_changes_cover_action_errors() -> None:
    """reads console output and reports new action-time console errors."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/console"}
            )
            _skip_if_browser_unavailable(navigate)
            assert "Successfully navigated" in navigate
            _content, logs_payload = await _execute_tool(
                server, "page_console_logs", {"level": "all", "limit": 20}
            )
            assert logs_payload["ok"] is True
            logs = logs_payload["data"]["logs"]
            assert {"log", "warning", "error"} <= {item["level"] for item in logs}
            assert any(item["text"] == "fixture console error" for item in logs)
            _content, error_payload = await _execute_tool(
                server, "page_console_logs", {"level": "error", "limit": 20}
            )
            assert error_payload["ok"] is True
            assert error_payload["data"]["logs"]
            assert {item["level"] for item in error_payload["data"]["logs"]} == {
                "error"
            }
            cursor = logs_payload["data"]["next_cursor"]
            _content, click_payload = await _execute_tool(
                server,
                "element_click",
                {"selector": "#console-action", "timeout": 2, "observe": True},
            )
            assert click_payload["ok"] is True
            changes = click_payload["data"]["changes"]
            assert changes["console_errors_added"] >= 1
            assert any(
                item["text"] == "fixture action failed"
                for item in changes["new_console_messages"]
            )
            _content, since_payload = await _execute_tool(
                server,
                "page_console_logs",
                {"level": "all", "since": cursor, "limit": 10},
            )
            assert since_payload["ok"] is True
            assert [item["text"] for item in since_payload["data"]["logs"]] == [
                "fixture action failed"
            ]
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_page_understanding_tools_extract_catalog_outline() -> None:
    """uses 0.4.9 preview tools to inspect repeated cards and page controls."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/catalog"}
            )
            _skip_if_browser_unavailable(navigate)
            assert "Successfully navigated" in navigate
            _content, snapshot_payload = await _execute_tool(
                server, "page_snapshot", {"max_elements": 30, "max_text_chars": 1000}
            )
            assert snapshot_payload["ok"] is True
            snapshot = snapshot_payload["data"]
            assert snapshot["title"] == "Fixture Catalog"
            assert "Automation Catalog" in snapshot["text_excerpt"]
            assert snapshot["headings"][0]["selector"] == "#catalog-title"
            assert {link["text"] for link in snapshot["links"]} >= {"Docs", "Pricing"}
            assert any(
                button["text"] == "Choose Alpha" for button in snapshot["buttons"]
            )
            assert any(input_["selector"] == "#query" for input_ in snapshot["inputs"])
            assert snapshot["limits"] == {"max_elements": 30, "max_text_chars": 1000}
            _content, cards_payload = await _execute_tool(
                server,
                "element_find_all",
                {"selector": ".product-card", "limit": 2, "include_html": True},
            )
            assert cards_payload["ok"] is True
            cards = cards_payload["data"]
            assert cards["locator"] == "css:.product-card"
            assert cards["count"] == 3
            assert cards["returned"] == 2
            assert cards["truncated"] is True
            assert [card["text"].split()[0] for card in cards["elements"]] == [
                "Alpha",
                "Beta",
            ]
            assert cards["elements"][0]["selector"] == "#alpha"
            assert "html" in cards["elements"][0]
            _content, rows_payload = await _execute_tool(
                server, "element_find_all", {"selector": "#people tbody tr", "limit": 5}
            )
            assert rows_payload["ok"] is True
            rows = rows_payload["data"]["elements"]
            assert [row["text"] for row in rows] == [
                "Ada Engineer",
                "Grace Researcher",
                "Katherine Mathematician",
            ]
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_page_snapshot_balances_link_heavy_pages() -> None:
    """keeps high-value controls visible when a page has many links."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/link-heavy"}
            )
            _skip_if_browser_unavailable(navigate)
            assert "Successfully navigated" in navigate
            _content, snapshot_payload = await _execute_tool(
                server, "page_snapshot", {"max_elements": 20, "max_text_chars": 1000}
            )
            assert snapshot_payload["ok"] is True
            snapshot = snapshot_payload["data"]
            returned = sum(
                len(snapshot[name])
                for name in ("headings", "links", "buttons", "inputs", "forms")
            )
            assert snapshot["counts"]["links"] == 75
            assert snapshot["counts"]["inputs"] == 1
            assert snapshot["counts"]["forms"] == 1
            assert snapshot["limits"]["max_elements"] == 20
            assert snapshot["truncated"]["elements"] is True
            assert snapshot["truncated"]["returned_elements"] == returned <= 20
            assert len(snapshot["links"]) < 20
            assert any(
                button["selector"] == "#search-button" for button in snapshot["buttons"]
            )
            assert any(
                input_["selector"] == "#search-input" for input_ in snapshot["inputs"]
            )
            assert any(form["selector"] == "#search-form" for form in snapshot["forms"])
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_browser_tools_return_structured_errors_for_bad_page_actions() -> (
    None
):
    """returns machine-readable errors for common LLM recovery paths."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/"}
            )
            _skip_if_browser_unavailable(navigate)
            assert "Successfully navigated" in navigate
            missing_content, missing_payload = await _execute_tool(
                server, "element_find", {"selector": "#never-appears", "timeout": 1}
            )
            assert missing_payload["ok"] is False
            assert missing_payload["error"]["code"] == "ELEMENT_NOT_FOUND"
            assert missing_payload["message"].startswith("Failed to find element")
            missing_hints = missing_payload["error"]["details"]["hints"]
            assert {hint.get("tool") for hint in missing_hints} >= {
                "page_snapshot",
                "element_find_all",
                "wait_for_element",
            }
            assert missing_content[0].text.startswith("### JSON_RESULT")
            _content, wait_payload = await _execute_tool(
                server,
                "wait_for_url",
                {"url_pattern": "not-in-current-url", "timeout": 0},
            )
            assert wait_payload["ok"] is False
            assert wait_payload["error"]["code"] == "TIMEOUT"
            wait_hints = wait_payload["error"]["details"]["hints"]
            assert any(hint["action"] == "increase_timeout" for hint in wait_hints)
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_0_5_5_interaction_and_upload_tools_use_local_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """exercises 0.5.5 interaction and upload tools in a real browser."""
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    upload_file = upload_root / "fixture-upload.txt"
    upload_file.write_text("fixture upload", encoding="utf-8")
    monkeypatch.setenv("DP_MCP_UPLOAD_ROOT", str(upload_root))
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/upload"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, upload_payload = await _execute_tool(
                server,
                "element_upload_file",
                {"selector": "#upload", "paths": [str(upload_file)], "timeout": 2},
            )
            assert upload_payload["ok"] is True
            assert upload_payload["data"]["filenames"] == ["fixture-upload.txt"]
            assert str(upload_file) not in json.dumps(upload_payload["data"])
            _content, upload_state = await _execute_tool(
                server,
                "page_evaluate",
                {"script": "return document.querySelector('#upload').files[0].name;"},
            )
            assert upload_state["data"]["result"] == "fixture-upload.txt"
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/interactions"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, scroll_payload = await _execute_tool(
                server, "page_scroll", {"direction": "bottom"}
            )
            assert scroll_payload["ok"] is True
            _content, into_view_payload = await _execute_tool(
                server,
                "element_scroll_into_view",
                {"selector": "#deep-target", "center": True, "timeout": 2},
            )
            assert into_view_payload["ok"] is True
            _content, hover_payload = await _execute_tool(
                server, "element_hover", {"selector": "#hover-target", "timeout": 2}
            )
            assert hover_payload["ok"] is True
            _content, select_payload = await _execute_tool(
                server,
                "element_select",
                {"selector": "#mode", "value": "advanced", "by": "value"},
            )
            assert select_payload["data"]["selected"] is True
            _content, check_payload = await _execute_tool(
                server,
                "element_check",
                {"selector": "#agree", "checked": True, "by_js": True},
            )
            assert check_payload["data"]["checked"] is True
            _content, click_payload = await _execute_tool(
                server, "element_click", {"selector": "#keyboard-input", "timeout": 2}
            )
            assert click_payload["ok"] is True
            key_content, key_payload = await _execute_tool(
                server, "keyboard_press", {"keys": "XYZ", "interval": 0}
            )
            assert key_payload["ok"] is True
            assert key_payload["data"]["keys"] == {
                "provided": True,
                "length": 3,
                "redacted": True,
            }
            assert "XYZ" not in key_content
            _content, state_payload = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": "return {mode: document.querySelector('#mode').value,checked: document.querySelector('#agree').checked,keys: document.querySelector('#keyboard-input').value,hovered: document.querySelector('#hover-status').textContent};"
                },
            )
            state = state_payload["data"]["result"]
            assert state["mode"] == "advanced"
            assert state["checked"] is True
            assert state["keys"].endswith("XYZ")
            assert state["hovered"] == "hovered"
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_0_5_5_frame_shadow_and_storage_tools_use_local_fixture() -> None:
    """exercises iframe, shadow DOM, cookies, and storage in a real browser."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, frames_payload = await _execute_tool(server, "frame_list", {})
            assert frames_payload["ok"] is True
            assert frames_payload["data"]["count"] >= 1
            _content, frame_find_payload = await _execute_tool(
                server,
                "frame_find",
                {"frame_selector": "#fixture-frame", "selector": "#frame-text"},
            )
            assert frame_find_payload["data"]["element"]["text"] == "frame ready"
            _content, frame_snapshot_payload = await _execute_tool(
                server,
                "frame_snapshot",
                {"frame_selector": "#fixture-frame", "max_elements": 10},
            )
            assert "Iframe Content" in frame_snapshot_payload["data"]["text_excerpt"]
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/shadow"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, shadow_payload = await _execute_tool(
                server,
                "shadow_find",
                {"host_selector": "#shadow-host", "selector": "#shadow-button"},
            )
            assert shadow_payload["data"]["element"]["text"] == "Shadow Action"
            _content, shadow_all_payload = await _execute_tool(
                server,
                "shadow_find_all",
                {"host_selector": "#shadow-host", "selector": ".shadow-item"},
            )
            assert shadow_all_payload["data"]["count"] == 2
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/storage"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, cookies_payload = await _execute_tool(
                server, "browser_cookies_get", {"include_values": False}
            )
            assert cookies_payload["ok"] is True
            assert any(
                item["name"] == "fixture_cookie"
                for item in cookies_payload["data"]["cookies"]
            )
            assert all(
                item["value"] in {"", "<redacted>"}
                for item in cookies_payload["data"]["cookies"]
            )
            _content, cookie_set_payload = await _execute_tool(
                server,
                "browser_cookies_set",
                {
                    "cookies": [
                        {
                            "name": "mcp_login",
                            "value": "callback-secret",
                            "url": base_url + "/storage",
                            "path": "/",
                            "http_only": True,
                            "same_site": "Lax",
                        }
                    ]
                },
            )
            assert cookie_set_payload["data"]["cookies"][0]["value"] == (
                "<redacted>"
            )
            assert "callback-secret" not in json.dumps(cookie_set_payload)
            _content, cookie_state_payload = await _execute_tool(
                server,
                "browser_cookies_get",
                {"all_info": True, "include_values": True},
            )
            assert any(
                item["name"] == "mcp_login" and item["value"] == "callback-secret"
                for item in cookie_state_payload["data"]["cookies"]
            )
            _content, cookie_delete_payload = await _execute_tool(
                server,
                "browser_cookies_delete",
                {"name": "mcp_login", "url": base_url + "/storage", "path": "/"},
            )
            assert cookie_delete_payload["data"]["deleted"] is True
            _content, cookie_deleted_state = await _execute_tool(
                server,
                "browser_cookies_get",
                {"all_info": True, "include_values": True},
            )
            assert all(
                item["name"] != "mcp_login"
                for item in cookie_deleted_state["data"]["cookies"]
            )
            await _execute_tool(
                server,
                "browser_cookies_set",
                {
                    "cookies": [
                        {
                            "name": "mcp_login",
                            "value": "clear-me",
                            "url": base_url + "/storage",
                        }
                    ]
                },
            )
            _content, cookie_clear_payload = await _execute_tool(
                server, "browser_cookies_clear", {}
            )
            assert cookie_clear_payload["data"]["cleared"] is True
            _content, cookie_cleared_state = await _execute_tool(
                server,
                "browser_cookies_get",
                {"all_domains": True, "all_info": True, "include_values": True},
            )
            assert cookie_cleared_state["data"]["cookies"] == []
            _content, set_payload = await _execute_tool(
                server,
                "storage_set",
                {"area": "local", "key": "mcp-mode", "value": "green"},
            )
            assert set_payload["data"] == {
                "area": "local",
                "key": "mcp-mode",
                "set": True,
            }
            _content, get_payload = await _execute_tool(
                server,
                "storage_get",
                {"area": "local", "key": "mcp-mode", "include_values": True},
            )
            assert get_payload["data"]["items"] == {"mcp-mode": "green"}
            _content, clear_payload = await _execute_tool(
                server, "storage_clear", {"area": "local", "key": "mcp-mode"}
            )
            assert clear_payload["data"]["cleared"] is True
            _content, state_payload = await _execute_tool(
                server, "storage_get", {"area": "local", "key": "mcp-mode"}
            )
            assert state_payload["data"]["items"] == {}
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_0_7_5_browser_environment_controls_use_local_fixture() -> None:
    """verifies request identity, cache-only clearing, and URL blocking."""

    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/"}
            )
            _skip_if_browser_unavailable(navigate)

            _content, headers_payload = await _execute_tool(
                server,
                "browser_headers_set",
                {"headers": {"X-MCP-Session": "callback-secret"}},
            )
            assert headers_payload["data"]["headers"] == {
                "X-MCP-Session": "<redacted>"
            }
            assert "callback-secret" not in json.dumps(headers_payload)
            _content, ua_payload = await _execute_tool(
                server,
                "browser_user_agent_set",
                {"user_agent": "MCPBrowser/0.7.6", "platform": "Linux"},
            )
            previous_user_agent = ua_payload["data"]["previous_user_agent"]
            assert previous_user_agent

            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/request-context"}
            )
            assert "Successfully navigated" in navigate
            _content, header_state = await _execute_tool(
                server,
                "element_get_attribute",
                {"selector": "#request-session-header", "attribute": "data-value"},
            )
            assert header_state["data"]["value"] == "callback-secret"
            _content, ua_state = await _execute_tool(
                server,
                "element_get_attribute",
                {"selector": "#request-user-agent", "attribute": "data-value"},
            )
            assert ua_state["data"]["value"] == "MCPBrowser/0.7.6"

            _content, blocked_payload = await _execute_tool(
                server,
                "network_blocked_urls_set",
                {"urls": ["*blocked-resource.js*"]},
            )
            assert blocked_payload["data"]["urls"] == ["*blocked-resource.js*"]
            await _execute_tool(
                server,
                "page_navigate",
                {"url": base_url + "/resource-controls?run=1"},
            )
            _content, first_resources = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": "return {cache: window.__cacheVersion, blocked: window.__blockedResourceLoaded === true};"
                },
            )
            assert first_resources["data"]["result"] == {
                "cache": 1,
                "blocked": False,
            }

            await _execute_tool(
                server, "page_navigate", {"url": base_url + "/?between=1"}
            )
            await _execute_tool(
                server,
                "page_navigate",
                {"url": base_url + "/resource-controls?run=2"},
            )
            _content, cached_resources = await _execute_tool(
                server,
                "page_evaluate",
                {"script": "return window.__cacheVersion;"},
            )
            assert cached_resources["data"]["result"] == 1

            await _execute_tool(
                server,
                "browser_cookies_set",
                {
                    "cookies": [
                        {
                            "name": "cache_guard",
                            "value": "cookie-survives",
                            "url": base_url + "/resource-controls",
                        }
                    ]
                },
            )
            await _execute_tool(
                server,
                "storage_set",
                {"area": "local", "key": "cache-guard", "value": "storage-survives"},
            )
            _content, cache_payload = await _execute_tool(
                server, "browser_cache_clear", {}
            )
            assert cache_payload["data"] == {"cleared": True}
            _content, cookie_guard = await _execute_tool(
                server,
                "browser_cookies_get",
                {"all_info": True, "include_values": True},
            )
            assert any(
                item["name"] == "cache_guard" and item["value"] == "cookie-survives"
                for item in cookie_guard["data"]["cookies"]
            )
            _content, storage_guard = await _execute_tool(
                server,
                "storage_get",
                {"area": "local", "key": "cache-guard", "include_values": True},
            )
            assert storage_guard["data"]["items"] == {"cache-guard": "storage-survives"}
            await _execute_tool(server, "network_blocked_urls_set", {"urls": []})
            await _execute_tool(
                server, "page_navigate", {"url": base_url + "/?between=2"}
            )
            await _execute_tool(
                server,
                "page_navigate",
                {"url": base_url + "/resource-controls?run=3"},
            )
            _content, cleared_resources = await _execute_tool(
                server,
                "page_evaluate",
                {
                    "script": "return {cache: window.__cacheVersion, blocked: window.__blockedResourceLoaded === true};"
                },
            )
            assert cleared_resources["data"]["result"] == {
                "cache": 2,
                "blocked": True,
            }

            await _execute_tool(server, "browser_headers_set", {"headers": {}})
            await _execute_tool(
                server,
                "browser_user_agent_set",
                {"user_agent": previous_user_agent},
            )
            await _execute_tool(
                server,
                "page_navigate",
                {"url": base_url + "/request-context?restored=1"},
            )
            _content, restored_header = await _execute_tool(
                server,
                "element_get_attribute",
                {"selector": "#request-session-header", "attribute": "data-value"},
            )
            assert restored_header["data"]["value"] == ""
            _content, restored_ua = await _execute_tool(
                server,
                "element_get_attribute",
                {"selector": "#request-user-agent", "attribute": "data-value"},
            )
            assert restored_ua["data"]["value"] == previous_user_agent
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_0_5_6_network_listener_captures_fetch_xhr() -> None:
    """observes local fetch/XHR packets without interception."""
    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/network"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, start_payload = await _execute_tool(
                server, "network_listen_start", {"targets": ["/api"], "clear": True}
            )
            if not start_payload["ok"]:
                if start_payload["error"]["code"] == "UNSUPPORTED_OPERATION":
                    pytest.skip(start_payload["message"])
                pytest.fail(start_payload["message"])
            assert start_payload["data"]["listening"] is True
            listener_token = start_payload["data"]["listener_token"]
            assert start_payload["data"]["state"] == "listening"
            assert start_payload["data"]["consumed_count"] == 0
            assert start_payload["data"]["next_cursor"] == 0
            assert start_payload["data"]["timing"]["startup_ms"] >= 0
            _content, click_payload = await _execute_tool(
                server, "element_click", {"selector": "#network-action", "timeout": 2}
            )
            assert click_payload["ok"] is True
            started = asyncio.get_running_loop().time()
            _content, wait_payload = await _execute_tool(
                server,
                "network_listen_wait",
                {
                    "timeout": 5,
                    "limit": 2,
                    "include_headers": True,
                    "include_body": True,
                    "max_body_chars": 500,
                    "listener_token": listener_token,
                },
            )
            assert asyncio.get_running_loop().time() - started < 2.0
            assert wait_payload["ok"] is True
            urls = {packet["url"] for packet in wait_payload["data"]["packets"]}
            assert any("/api/data.json" in url for url in urls)
            assert any("/api/echo.json" in url for url in urls)
            assert "fixture-secret" not in json.dumps(wait_payload["data"])
            assert wait_payload["data"]["listener_token"] == listener_token
            assert wait_payload["data"]["state"] == "listening"
            assert wait_payload["data"]["consumed_count"] == 2
            assert wait_payload["data"]["next_cursor"] == 2
            assert wait_payload["data"]["remaining_timeout_ms"] >= 0
            _content, stop_payload = await _execute_tool(
                server,
                "network_listen_stop",
                {"clear": True, "listener_token": listener_token},
            )
            assert stop_payload["ok"] is True
            assert stop_payload["data"]["listening"] is False
            assert stop_payload["data"]["state"] == "stopped"
            assert stop_payload["data"]["listener_token"] == listener_token

            for _ in range(100):
                _content, cycle_start = await _execute_tool(
                    server, "network_listen_start", {"clear": True}
                )
                assert cycle_start["ok"] is True
                _content, cycle_stop = await _execute_tool(
                    server,
                    "network_listen_stop",
                    {
                        "clear": True,
                        "listener_token": cycle_start["data"]["listener_token"],
                    },
                )
                assert cycle_stop["ok"] is True

            listener = server.context.current_tab_or_die().page.listen
            assert listener.listening is False
            assert listener._driver is None
            assert listener._caught.empty()
            assert listener._request_ids == {}
            assert listener._extra_info_ids == {}
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_0_8_8_network_listeners_are_isolated_per_tab() -> None:
    """keeps packet queues and listener generations bound to their owning tab."""

    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/network"}
            )
            _skip_if_browser_unavailable(navigate)
            _content, tabs = await _execute_scoped_tool(server, "tab_list", {})
            first_tab_id = tabs["data"]["active_tab_id"]
            _content, created = await _execute_scoped_tool(
                server,
                "page_navigate",
                {
                    "url": base_url + "/network",
                    "new_tab": True,
                    "background": True,
                },
            )
            second_tab_id = created["data"]["tab_id"]

            listeners: dict[str, str] = {}
            for tab_id in (first_tab_id, second_tab_id):
                _content, started = await _execute_scoped_tool(
                    server,
                    "network_listen_start",
                    {
                        "tab_id": tab_id,
                        "targets": ["/api/data.json"],
                        "clear": True,
                    },
                )
                assert started["ok"] is True
                assert started["data"]["tab_id"] == tab_id
                listeners[tab_id] = started["data"]["listener_token"]

            _content, first_click = await _execute_scoped_tool(
                server,
                "element_click",
                {
                    "tab_id": first_tab_id,
                    "selector": "#network-action",
                    "timeout": 2,
                },
            )
            assert first_click["ok"] is True
            _content, first_packets = await _execute_scoped_tool(
                server,
                "network_listen_wait",
                {
                    "tab_id": first_tab_id,
                    "listener_token": listeners[first_tab_id],
                    "timeout": 2,
                    "limit": 1,
                },
            )
            assert first_packets["data"]["count"] == 1
            assert first_packets["data"]["tab_id"] == first_tab_id

            _content, second_timeout = await _execute_scoped_tool(
                server,
                "network_listen_wait",
                {
                    "tab_id": second_tab_id,
                    "listener_token": listeners[second_tab_id],
                    "timeout": 0.2,
                    "limit": 1,
                },
            )
            assert second_timeout["data"]["timed_out"] is True
            assert second_timeout["data"]["count"] == 0

            _content, second_click = await _execute_scoped_tool(
                server,
                "element_click",
                {
                    "tab_id": second_tab_id,
                    "selector": "#network-action",
                    "timeout": 2,
                },
            )
            assert second_click["ok"] is True
            _content, second_packets = await _execute_scoped_tool(
                server,
                "network_listen_wait",
                {
                    "tab_id": second_tab_id,
                    "listener_token": listeners[second_tab_id],
                    "timeout": 2,
                    "limit": 1,
                },
            )
            assert second_packets["data"]["count"] == 1
            assert second_packets["data"]["tab_id"] == second_tab_id

            for tab_id, token in listeners.items():
                _content, stopped = await _execute_scoped_tool(
                    server,
                    "network_listen_stop",
                    {"tab_id": tab_id, "listener_token": token, "clear": True},
                )
                assert stopped["ok"] is True
    finally:
        await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_0_7_7_browser_owned_capabilities_are_fully_automated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """controls permissions, exports, chooser input, and isolated HTTP auth."""

    artifact_root = tmp_path / "artifacts"
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    upload_file = upload_root / "fixture-note.txt"
    upload_file.write_text("fixture upload", encoding="utf-8")
    monkeypatch.setenv("DP_MCP_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("DP_MCP_UPLOAD_ROOT", str(upload_root))

    server = DrissionPageMCPServer()
    try:
        with local_http_fixture() as base_url:
            navigate = await _execute_tool_text(
                server, "page_navigate", {"url": base_url + "/browser-owned"}
            )
            _skip_if_browser_unavailable(navigate)

            _content, initial_permission = await _execute_tool(
                server, "browser_permission_get", {"permission": "geolocation"}
            )
            assert initial_permission["ok"] is True
            assert initial_permission["data"]["state"] in {
                "prompt",
                "denied",
                "granted",
            }
            _content, granted = await _execute_tool(
                server,
                "browser_permission_set",
                {
                    "permission": "geolocation",
                    "setting": "granted",
                    "origin": base_url,
                },
            )
            assert granted["data"]["verified"] is True
            assert granted["data"]["observed_state"] == "granted"
            _content, reset = await _execute_tool(
                server, "browser_permissions_reset", {}
            )
            assert reset["data"]["reset"] is True
            _content, reset_state = await _execute_tool(
                server, "browser_permission_get", {"permission": "geolocation"}
            )
            assert reset_state["data"]["state"] != "granted"

            for export_format in ("pdf", "mhtml"):
                filename = f"fixture-export.{export_format}"
                _content, exported = await _execute_tool(
                    server,
                    "page_export_artifact",
                    {
                        "format": export_format,
                        "filename": filename,
                        "operation_key": f"fixture-export-{export_format}",
                    },
                )
                assert exported["ok"] is True
                artifact = exported["data"]["artifact"]
                output = artifact_root / artifact["safe_relative_path"]
                assert output.is_file()
                if export_format == "pdf":
                    assert output.read_bytes().startswith(b"%PDF")
                else:
                    message = BytesParser(policy=policy.default).parsebytes(
                        output.read_bytes()
                    )
                    html_parts = [
                        part.get_content()
                        for part in message.walk()
                        if part.get_content_type() == "text/html"
                    ]
                    assert any(
                        "Browser Owned Export Marker 0.7.7" in part
                        for part in html_parts
                    )

            _content, uploaded = await _execute_tool(
                server,
                "element_click_and_upload",
                {
                    "selector": "#chooser-trigger",
                    "paths": [str(upload_file)],
                    "timeout": 5,
                },
            )
            assert uploaded["data"]["filenames"] == ["fixture-note.txt"]
            chooser_text = await _execute_tool_text(
                server, "element_get_text", {"selector": "#chooser-result"}
            )
            assert "fixture-note.txt" in chooser_text

            _content, authenticated = await _execute_tool(
                server,
                "page_navigate_with_http_auth",
                {
                    "url": base_url + "/auth/basic",
                    "username": HTTP_AUTH_USERNAME,
                    "password": HTTP_AUTH_PASSWORD,
                    "realm": HTTP_AUTH_REALM,
                    "timeout": 10,
                },
            )
            assert authenticated["data"]["authenticated"] is True
            assert authenticated["data"]["handlers_cleaned"] is True
            assert (
                authenticated["data"]["credential_scope"]
                == "isolated_browser_context"
            )
            serialized = json.dumps(authenticated, ensure_ascii=False)
            assert HTTP_AUTH_PASSWORD not in serialized
            auth_text = await _execute_tool_text(
                server, "element_get_text", {"selector": "#auth-ok"}
            )
            assert "Authenticated Fixture" in auth_text
            auth_tab_id = authenticated["data"]["tab_id"]
            _content, closed = await _execute_tool(
                server, "tab_close", {"tab_id": auth_tab_id}
            )
            assert closed["data"]["closed"] is True
            assert server.context is not None
            assert server.context._owned_browser_context_ids == set()
            fixture_state = _json(base_url + "/__fixture__/state")
            assert HTTP_AUTH_PASSWORD not in json.dumps(fixture_state)
    finally:
        await server.cleanup()


async def _execute_tool_text(
    server: DrissionPageMCPServer, name: str, arguments: dict[str, Any]
) -> str:
    content = await _execute_tool_content(server, name, arguments)
    return "\n".join(item.text for item in content if item.type == "text")


async def _execute_tool_content(
    server: DrissionPageMCPServer, name: str, arguments: dict[str, Any]
) -> list[Any]:
    content, _payload = await _execute_tool(server, name, arguments)
    return content


async def _execute_tool(
    server: DrissionPageMCPServer, name: str, arguments: dict[str, Any]
) -> tuple[list[Any], dict[str, Any]]:
    tool = server.tools[name]
    if server.context is None:
        from drissionpage_mcp.context import DrissionPageContext

        server.context = DrissionPageContext()
    response = ToolOutcome()
    validated = tool.input_schema.model_validate(arguments)
    response = await tool.execute(server.context, validated)
    return (list(response.content()), response.structured_content())


async def _execute_scoped_tool(
    server: DrissionPageMCPServer, name: str, arguments: dict[str, Any]
) -> tuple[list[Any], dict[str, Any]]:
    """Execute through server scheduling so explicit tab targeting is honored."""

    result = await server._call_tool_impl(name, arguments)
    return list(result.content), dict(result.structuredContent or {})


def _shared_test_site_url_or_skip() -> str:
    base_url = (os.environ.get(SHARED_TEST_SITE_URL_ENV) or "").strip()
    if base_url:
        return base_url
    pytest.skip(f"shared DrissionPage test-site requires {SHARED_TEST_SITE_URL_ENV}")


def _site_url(base_url: str, path: str = "") -> str:
    if not path:
        return base_url
    parsed = urlsplit(base_url)
    base_path = parsed.path.rstrip("/") + "/"
    base_without_query = urlunsplit((parsed.scheme, parsed.netloc, base_path, "", ""))
    target = urljoin(base_without_query, path.lstrip("/"))
    return _merge_base_query(target, parsed.query)


def _merge_base_query(url: str, base_query: str) -> str:
    if not base_query:
        return url
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.extend(parse_qsl(base_query, keep_blank_values=True))
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _json(url: str) -> dict[str, Any]:
    return json.loads(_read(url)[1])


def _read(url: str) -> tuple[int, str]:
    try:
        response = urlopen(url, timeout=5)
        return (response.status, response.read().decode("utf-8"))
    except Exception as exc:
        status = getattr(getattr(exc, "fp", None), "status", None) or getattr(
            exc, "code", None
        )
        body = ""
        if getattr(exc, "fp", None) is not None:
            body = exc.fp.read().decode("utf-8")
        if status is not None:
            return (int(status), body)
        raise


def test_browser_unavailable_helper_skips_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DP_MCP_REQUIRE_BROWSER", raising=False)
    with pytest.raises(pytest.skip.Exception):
        _skip_if_browser_unavailable("### Error\nChrome failed to initialize")


def test_browser_unavailable_helper_fails_when_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DP_MCP_REQUIRE_BROWSER", "1")
    with pytest.raises(pytest.fail.Exception):
        _skip_if_browser_unavailable("### Error\nChrome failed to initialize")


def _skip_if_browser_unavailable(text: str) -> None:
    lowered = text.lower()
    if "### Error" in text and any(
        marker in lowered for marker in _BROWSER_UNAVAILABLE_MARKERS
    ):
        if os.environ.get("DP_MCP_REQUIRE_BROWSER", "").lower() in {"1", "true", "yes"}:
            pytest.fail(
                f"Chrome/Chromium browser is required but unavailable for DrissionPage integration: {text[:300]}"
            )
        pytest.skip(
            f"Chrome/Chromium browser unavailable for DrissionPage integration: {text[:300]}"
        )
