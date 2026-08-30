"""Pure unit coverage for tool success paths without launching DrissionPage."""

from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from DrissionPage.errors import ElementNotFoundError
from pydantic import ValidationError

from drissionpage_mcp.tools import (
    common,
    debug,
    dialogs,
    element,
    files,
    frame,
    interaction,
    navigate,
    network,
    pointer,
    shadow,
    storage,
    tabs,
    wait,
)
from drissionpage_mcp.tools.base import ToolOutcome

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
PNG_1X1_B64 = base64.b64encode(PNG_1X1).decode()


def _fake_viewport_evidence() -> dict[str, Any]:
    return {
        "displayed": True,
        "enabled": True,
        "alive": True,
        "clickable": True,
        "checked": False,
        "selected": False,
        "in_viewport": True,
        "whole_in_viewport": True,
        "covered": False,
        "covering_backend_node_id": None,
        "rect": {
            "location": {"x": 10.0, "y": 20.0},
            "size": {"width": 80.0, "height": 30.0},
            "midpoint": {"x": 50.0, "y": 35.0},
            "click_point": {"x": 50.0, "y": 23.0},
            "viewport_location": {"x": 10.0, "y": 20.0},
            "viewport_midpoint": {"x": 50.0, "y": 35.0},
            "viewport_click_point": {"x": 50.0, "y": 23.0},
            "coordinate_space": "target_document",
            "viewport_coordinate_space": "top_level_viewport",
        },
        "presentation": {
            "display": "block",
            "visibility": "visible",
            "opacity": 1.0,
            "pointer_events": "auto",
            "transform": "none",
            "transform_style": "flat",
            "perspective": "none",
            "transformed": False,
            "ancestor_3d": False,
            "three_dimensional": False,
            "coordinate_actionability": "ready",
        },
    }


def _fake_frame_summary(*, index: int = 0, selector: str = "#fixture-frame") -> dict[str, Any]:
    return {
        "index": index,
        "selector": selector,
        "id": "fixture-frame",
        "name": "fixture-frame",
        "title": "Frame",
        "url": "https://example.test/frame",
        "boundary": "cross_origin",
        "document_access": "readable",
        "outer": _fake_viewport_evidence(),
    }


class FakeTab:
    """Small async PageTab stand-in for tool handler tests."""

    def __init__(self) -> None:
        self.url = "https://example.test/current"
        self.title = "Fake Tab"
        self.mcp_tab_id = "t0"
        self.native_tab_id = "native-0"
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.wait_element_result = True
        self.wait_url_result = True
        self.observe_count = 0
        self.elements = SimpleNamespace(
            find=self.find_element,
            find_all=self.find_elements,
            click=self.click_element,
            type=self.type_text,
            text=self.get_text,
            attribute=self.get_attribute,
            property=self.get_property,
            html=self.get_html,
            upload=self.upload_file,
            state=self.element_state,
        )
        self.frames = SimpleNamespace(
            list_frames=self.list_frames,
            snapshot=self.snapshot,
            find=self.frame_find,
            shadow_find=self.shadow_find,
            shadow_find_all=self.shadow_find_all,
        )
        self.interaction = SimpleNamespace(
            scroll_page=self.scroll_page,
            scroll_element_into_view=self.scroll_element_into_view,
            hover_element=self.hover_element,
            keyboard_press=self.keyboard_press,
            select_element=self.select_element,
            check_element=self.check_element,
        )
        self.network = SimpleNamespace(
            start=self.network_listen_start,
            wait=self.network_listen_wait,
            stop=self.network_listen_stop,
            set_blocked_urls=self.network_blocked_urls_set,
        )
        self.navigation = SimpleNamespace(
            navigate=self.navigate,
            back=self.go_back,
            forward=self.go_forward,
            refresh=self.refresh,
        )
        self.storage = self
        self.waits = SimpleNamespace(
            element=self.wait_for_element, url=self.wait_for_url, until=self.wait_until
        )
        self.observation = SimpleNamespace(
            snapshot=self.page_snapshot,
            observe=self.observe,
            console_logs=self.console_logs,
            evaluate=self.evaluate_script,
        )
        self.accessibility = SimpleNamespace(snapshot=self.accessibility_snapshot)
        self.dialogs = SimpleNamespace(wait_for_pending=self.wait_for_pending_dialog)
        self.page_ops = SimpleNamespace(
            resize=self.resize,
            screenshot=self.screenshot,
            set_headers=self.set_headers,
            set_user_agent=self.set_user_agent,
            clear_cache=self.clear_cache,
        )
        self.pointer = SimpleNamespace(click_at=self.click)

    def summary(self, *, active: bool = False) -> dict[str, Any]:
        return {
            "id": self.mcp_tab_id,
            "native_id": self.native_tab_id,
            "url": self.url,
            "title": self.title,
            "active": active,
            "connected": True,
        }

    async def resize(self, width: int, height: int) -> None:
        self._record("resize", width, height)

    async def screenshot(self, path: str | None = None, full_page: bool = False) -> str:
        self._record("screenshot", path, full_page=full_page)
        if path is not None:
            Path(path).write_bytes(PNG_1X1)
            return path
        return PNG_1X1_B64

    async def set_headers(self, headers: dict[str, str]) -> dict[str, Any]:
        self._record("browser_headers_set", headers=headers)
        return {"count": len(headers), "headers": headers, "set": True}

    async def set_user_agent(
        self, user_agent: str, platform: str | None = None
    ) -> dict[str, Any]:
        self._record(
            "browser_user_agent_set", user_agent=user_agent, platform=platform
        )
        return {
            "previous_user_agent": "FixtureBrowser/1.0",
            "user_agent": user_agent,
            "platform": platform,
            "set": True,
        }

    async def clear_cache(self) -> dict[str, Any]:
        self._record("browser_cache_clear")
        return {"cleared": True}

    async def page_snapshot(
        self,
        *,
        include_html: bool = False,
        max_elements: int = 50,
        max_text_chars: int = 4000,
    ) -> dict[str, Any]:
        self._record(
            "page_snapshot",
            include_html=include_html,
            max_elements=max_elements,
            max_text_chars=max_text_chars,
        )
        return {
            "url": self.url,
            "title": "Fake Catalog",
            "text_excerpt": "Alpha Beta",
            "headings": [
                {
                    "index": 0,
                    "tag": "h1",
                    "text": "Fake Catalog",
                    "selector": "#title",
                    "attributes": {"id": "title"},
                }
            ],
            "links": [],
            "buttons": [],
            "inputs": [],
            "forms": [],
            "counts": {"headings": 1},
            "truncated": {"text": False, "elements": False, "returned_elements": 1},
            "limits": {"max_elements": max_elements, "max_text_chars": max_text_chars},
        }

    async def accessibility_snapshot(
        self,
        *,
        scope: object = None,
        max_nodes: int = 200,
        include_ignored: bool = False,
        include_values: bool = False,
    ) -> dict[str, Any]:
        self._record(
            "accessibility_snapshot",
            scope=scope,
            max_nodes=max_nodes,
            include_ignored=include_ignored,
            include_values=include_values,
        )
        nodes = [
            {
                "node_id": "ax-save",
                "parent_id": "ax-root",
                "backend_dom_node_id": 21,
                "role": "button",
                "name": "Save",
                "description": "Save changes",
                "value": "",
                "ignored": False,
                "properties": {"focusable": True},
            }
        ]
        return {
            "nodes": nodes[:max_nodes],
            "count": len(nodes),
            "returned": min(len(nodes), max_nodes),
            "max_nodes": max_nodes,
            "truncated": len(nodes) > max_nodes,
            "values_included": include_values,
            "scope": None,
        }

    async def wait_for_pending_dialog(self, *, timeout: float) -> dict[str, str]:
        self._record("wait_for_pending_dialog", timeout=timeout)
        return {"dialog_type": "confirm", "message": "Fixture confirm dialog"}

    async def observe(
        self, *, max_texts: int = 20, max_text_chars: int = 160
    ) -> dict[str, Any]:
        self._record("observe", max_texts=max_texts, max_text_chars=max_text_chars)
        phase = self.observe_count
        self.observe_count += 1
        return {
            "url": self.url,
            "title": self.title,
            "ready_state": "complete",
            "counts": {"buttons": 1 + phase, "inputs": 1},
            "text_samples": ["before"] if phase % 2 == 0 else ["after"],
            "active_element": None,
            "console": {
                "available": True,
                "listening": True,
                "count": phase + 1,
                "total": phase + 1,
                "next_cursor": phase,
                "error_count": 1 if phase else 0,
                "warning_count": 0,
                "recent": [
                    {
                        "index": phase,
                        "level": "error" if phase else "log",
                        "text": "after error" if phase else "before log",
                        "url": self.url,
                        "line": 1,
                        "column": 1,
                        "source": "console-api",
                    }
                ],
            },
            "limits": {"max_texts": max_texts, "max_text_chars": max_text_chars},
        }

    async def console_logs(
        self, *, level: str = "all", since: int = -1, limit: int = 20
    ) -> dict[str, Any]:
        self._record("console_logs", level=level, since=since, limit=limit)
        logs = [
            {
                "index": 0,
                "level": "log",
                "text": "before log",
                "url": self.url,
                "line": 1,
                "column": 1,
                "source": "console-api",
            },
            {
                "index": 1,
                "level": "error",
                "text": "after error",
                "url": self.url,
                "line": 2,
                "column": 1,
                "source": "console-api",
            },
        ]
        filtered = [item for item in logs if item["index"] > since]
        if level != "all":
            filtered = [item for item in filtered if item["level"] == level]
        return {
            "available": True,
            "listening": True,
            "count": len(filtered[:limit]),
            "total": len(logs),
            "next_cursor": logs[-1]["index"],
            "logs": filtered[:limit],
        }

    async def evaluate_script(
        self, script: str, *, args: list[Any] | None = None, max_chars: int = 4000
    ) -> dict[str, Any]:
        self._record("evaluate_script", script, args=args or [], max_chars=max_chars)
        return {
            "result": {"script": script, "args": args or []},
            "result_type": "object",
            "truncated": False,
            "original_json_chars": 42,
            "max_chars": max_chars,
        }

    async def network_listen_start(
        self,
        *,
        targets: list[str] | None = None,
        is_regex: bool = False,
        method: str = "",
        resource_type: str = "",
        clear: bool = True,
    ) -> dict[str, Any]:
        self._record(
            "network_listen_start",
            targets=targets or [],
            is_regex=is_regex,
            method=method,
            resource_type=resource_type,
            clear=clear,
        )
        return {
            "listening": True,
            "filters": {
                "targets": targets or [],
                "is_regex": is_regex,
                "method": method,
                "resource_type": resource_type,
            },
            "started_at": "2026-07-07T00:00:00+00:00",
            "tab_id": self.mcp_tab_id,
            "cleared": clear,
        }

    async def network_listen_wait(
        self,
        *,
        timeout: float = 5.0,
        limit: int = 10,
        include_headers: bool = False,
        include_body: bool = False,
        max_body_chars: int = 2000,
    ) -> dict[str, Any]:
        self._record(
            "network_listen_wait",
            timeout=timeout,
            limit=limit,
            include_headers=include_headers,
            include_body=include_body,
            max_body_chars=max_body_chars,
        )
        packet = {
            "index": 0,
            "url": "https://example.test/api/data.json",
            "method": "GET",
            "resource_type": "Fetch",
            "status": 200,
            "mime_type": "application/json",
            "failed": False,
            "fail_error": "",
        }
        if include_headers:
            packet["request_headers"] = {"authorization": "<redacted>"}
            packet["response_headers"] = {"content-type": "application/json"}
        if include_body:
            packet.update(
                {
                    "body_excerpt": '{"ok":true}',
                    "body_truncated": False,
                    "body_type": "json",
                    "request_body_excerpt": "",
                    "request_body_truncated": False,
                    "request_body_type": "none",
                }
            )
        return {
            "listening": True,
            "timed_out": False,
            "count": 1,
            "limit": limit,
            "packets": [packet],
        }

    async def network_listen_stop(self, *, clear: bool = True) -> dict[str, Any]:
        self._record("network_listen_stop", clear=clear)
        return {"listening": False, "was_listening": True, "cleared": clear}

    async def click(self, x: float, y: float, **kwargs: Any):
        self._record("click", x, y, **kwargs)
        return SimpleNamespace(
            to_dict=lambda: {
                "profile": kwargs.get("profile", "direct"),
                "button": kwargs.get("button", "left"),
                "start_x": 0.0,
                "start_y": 0.0,
                "target_x": x,
                "target_y": y,
                "steps": 1,
                "delay_before_press_ms": kwargs.get("delay_before_press_ms", 0),
                "planned_duration_ms": kwargs.get("delay_before_press_ms", 0),
            }
        )

    async def navigate(self, url: str) -> None:
        self._record("navigate", url)
        self.url = url

    async def go_back(self) -> None:
        self._record("go_back")

    async def go_forward(self) -> None:
        self._record("go_forward")

    async def refresh(self) -> None:
        self._record("refresh")

    async def wait_for_element(self, selector: str, timeout: int = 10) -> bool:
        self._record("wait_for_element", selector, timeout=timeout)
        return self.wait_element_result

    async def wait_for_url(self, pattern: str, timeout: int = 10) -> bool:
        self._record("wait_for_url", pattern, timeout=timeout)
        return self.wait_url_result

    async def wait_until(
        self,
        *,
        condition: str,
        selector: str = "",
        value: str = "",
        name: str = "",
        timeout: float = 10,
        interval: float = 0.1,
        stable_ms: int = 300,
    ) -> dict[str, Any]:
        self._record(
            "wait_until",
            condition=condition,
            selector=selector,
            value=value,
            field_name=name,
            timeout=timeout,
            interval=interval,
            stable_ms=stable_ms,
        )
        return {
            "condition": condition,
            "selector": selector,
            "value": value,
            "name": name,
            "matched": True,
            "timeout": timeout,
            "elapsed_ms": 15,
            "state": {"selector": selector, "visible": True},
        }

    async def find_element(self, selector: str, timeout: int = 10) -> dict[str, Any]:
        self._record("find_element", selector, timeout=timeout)
        return {
            "found": True,
            "selector": selector,
            "locator": "css:#name",
            "selector_strategy": "css",
            "selector_normalized": True,
            "text": "Ada",
            "tag": "input",
            "html": "<input id='name'>",
            "visible": True,
        }

    async def find_elements(
        self, selector: str, *, limit: int = 20, include_html: bool = False
    ) -> dict[str, Any]:
        self._record("find_elements", selector, limit=limit, include_html=include_html)
        elements = [
            {
                "index": 0,
                "tag": "article",
                "text": "Alpha",
                "selector": "#alpha",
                "attributes": {"id": "alpha", "class": "product-card"},
            },
            {
                "index": 1,
                "tag": "article",
                "text": "Beta",
                "selector": "#beta",
                "attributes": {"id": "beta", "class": "product-card"},
            },
        ][:limit]
        if include_html:
            for item in elements:
                item["html"] = f"<article>{item['text']}</article>"
        return {
            "selector": selector,
            "locator": "css:.product-card",
            "selector_strategy": "css",
            "selector_normalized": True,
            "count": 2,
            "returned": len(elements),
            "limit": limit,
            "truncated": limit < 2,
            "elements": elements,
        }

    async def click_element(
        self,
        selector: str,
        timeout: int = 10,
        *,
        button: str = "left",
        click_count: int = 1,
    ) -> None:
        self._record(
            "click_element",
            selector,
            timeout=timeout,
            button=button,
            click_count=click_count,
        )

    async def type_text(
        self, selector: str, text: str, timeout: int = 10, clear: bool = True
    ) -> None:
        self._record("type_text", selector, text, timeout=timeout, clear=clear)

    async def get_text(self, selector: str = "") -> str:
        self._record("get_text", selector)
        return "page text" if selector == "" else "element text"

    async def get_attribute(self, selector: str, attribute: str) -> str | None:
        self._record("get_attribute", selector, attribute)
        return None if attribute == "missing" else "attr-value"

    async def get_property(self, selector: str, property_name: str) -> str | None:
        self._record("get_property", selector, property_name)
        return None if property_name == "missing" else "prop-value"

    async def get_html(self, selector: str = "") -> str:
        self._record("get_html", selector)
        return "<html></html>" if selector == "" else "<input>"

    async def upload_file(
        self, selector: str, paths: list[str], timeout: int = 10
    ) -> dict[str, Any]:
        self._record("upload_file", selector, paths, timeout=timeout)
        return {
            "selector": selector,
            "locator": "css:#upload",
            "selector_strategy": "css",
            "selector_normalized": True,
            "uploaded": True,
            "file_count": len(paths),
            "filenames": [Path(path).name for path in paths],
        }

    async def element_state(
        self, selector: object, *, timeout: int = 3
    ) -> dict[str, Any]:
        self._record("element_state", selector, timeout=timeout)
        return {
            "selector": "role='button' name='Save'",
            "locator": "role='button' name='Save'",
            "selector_strategy": "accessibility",
            "selector_normalized": False,
            "target_kind": "accessibility",
            "frame_selectors": [],
            "shadow_hosts": ["#app-host"],
            "role": "button",
            "name": "Save",
            "exact": True,
            "tag": "button",
            "text": "Save",
            "displayed": True,
            "enabled": True,
            "alive": True,
            "clickable": True,
            "checked": False,
            "selected": False,
            "in_viewport": True,
            "whole_in_viewport": True,
            "covered": False,
            "covering_backend_node_id": None,
            "rect": {
                "location": {"x": 10.0, "y": 20.0},
                "size": {"width": 80.0, "height": 30.0},
                "midpoint": {"x": 50.0, "y": 35.0},
                "click_point": {"x": 50.0, "y": 35.0},
                "viewport_location": {"x": 10.0, "y": 20.0},
                "viewport_midpoint": {"x": 50.0, "y": 35.0},
                "viewport_click_point": {"x": 50.0, "y": 35.0},
                "coordinate_space": "target_document",
                "viewport_coordinate_space": "top_level_viewport",
            },
            "presentation": {
                "display": "block",
                "visibility": "visible",
                "opacity": 1.0,
                "pointer_events": "auto",
                "transform": "none",
                "transform_style": "flat",
                "perspective": "none",
                "transformed": False,
                "ancestor_3d": False,
                "three_dimensional": False,
                "coordinate_actionability": "ready",
            },
        }

    async def scroll_page(
        self, *, direction: str = "down", pixels: int = 300, x: int = 0, y: int = 0
    ) -> dict[str, Any]:
        self._record("scroll_page", direction=direction, pixels=pixels, x=x, y=y)
        return {
            "direction": direction,
            "pixels": pixels,
            "x": x,
            "y": y,
            "url": self.url,
        }

    async def scroll_element_into_view(
        self, selector: str, *, center: bool = True, timeout: int = 10
    ) -> dict[str, Any]:
        self._record(
            "scroll_element_into_view", selector, center=center, timeout=timeout
        )
        return {
            "selector": selector,
            "locator": "css:#deep",
            "selector_strategy": "css",
            "selector_normalized": True,
            "center": center,
            "scroll_method": "element",
            "before": _fake_viewport_evidence(),
            "after": _fake_viewport_evidence(),
            "url": self.url,
        }

    async def hover_element(
        self,
        selector: str,
        *,
        timeout: int = 10,
        offset_x: int | None = None,
        offset_y: int | None = None,
    ) -> dict[str, Any]:
        self._record(
            "hover_element",
            selector,
            timeout=timeout,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        return {
            "selector": selector,
            "locator": "css:#hover",
            "selector_strategy": "css",
            "selector_normalized": True,
            "url": self.url,
            "offset_x": offset_x,
            "offset_y": offset_y,
        }

    async def keyboard_press(self, keys: str, *, interval: float = 0) -> dict[str, Any]:
        self._record("keyboard_press", keys, interval=interval)
        return {
            "keys": {
                "provided": bool(keys),
                "length": len(keys),
                "redacted": True,
            },
            "interval": interval,
            "url": self.url,
        }

    async def select_element(
        self, selector: str, *, value: str, by: str = "value", timeout: int = 10
    ) -> dict[str, Any]:
        self._record("select_element", selector, value=value, by=by, timeout=timeout)
        return {
            "selector": selector,
            "locator": "css:#mode",
            "selector_strategy": "css",
            "selector_normalized": True,
            "selected": True,
            "by": by,
            "value": value,
        }

    async def check_element(
        self,
        selector: str,
        *,
        checked: bool = True,
        by_js: bool = False,
        timeout: int = 10,
    ) -> dict[str, Any]:
        self._record(
            "check_element", selector, checked=checked, by_js=by_js, timeout=timeout
        )
        return {
            "selector": selector,
            "locator": "css:#agree",
            "selector_strategy": "css",
            "selector_normalized": True,
            "checked": checked,
            "by_js": by_js,
        }

    async def list_frames(self, *, limit: int = 20) -> dict[str, Any]:
        self._record("list_frames", limit=limit)
        return {
            "count": 1,
            "returned": 1,
            "limit": limit,
            "frames": [_fake_frame_summary()],
        }

    async def snapshot(
        self,
        *,
        frame_selector: str = "",
        frame_index: int = 0,
        include_html: bool = False,
        max_elements: int = 50,
        max_text_chars: int = 4000,
        timeout: int = 3,
    ) -> dict[str, Any]:
        self._record(
            "frame_snapshot",
            frame_selector=frame_selector,
            frame_index=frame_index,
            include_html=include_html,
            max_elements=max_elements,
            max_text_chars=max_text_chars,
            timeout=timeout,
        )
        return {
            "frame": _fake_frame_summary(
                index=frame_index,
                selector=frame_selector or "#fixture-frame",
            ),
            "url": "https://example.test/frame",
            "title": "Frame",
            "text_excerpt": "Frame text",
            "headings": [],
            "links": [],
            "buttons": [],
            "inputs": [],
            "forms": [],
            "counts": {},
            "truncated": {"text": False, "elements": False, "returned_elements": 0},
            "limits": {"max_elements": max_elements, "max_text_chars": max_text_chars},
        }

    async def frame_find(
        self,
        *,
        selector: str,
        frame_selector: str = "",
        frame_index: int = 0,
        timeout: int = 3,
    ) -> dict[str, Any]:
        self._record(
            "frame_find",
            selector=selector,
            frame_selector=frame_selector,
            frame_index=frame_index,
            timeout=timeout,
        )
        return {
            "frame": _fake_frame_summary(
                index=frame_index,
                selector=frame_selector or "#fixture-frame",
            ),
            "element": {
                "found": True,
                "selector": selector,
                "locator": "css:#frame-text",
                "selector_strategy": "css",
                "selector_normalized": True,
                "text": "frame ready",
                "tag": "p",
                "html": "<p id='frame-text'>frame ready</p>",
                "visible": True,
            },
        }

    async def shadow_find(
        self, *, host_selector: str, selector: str, timeout: int = 3
    ) -> dict[str, Any]:
        self._record(
            "shadow_find",
            host_selector=host_selector,
            selector=selector,
            timeout=timeout,
        )
        return {
            "host": {
                "selector": host_selector,
                "locator": "css:#shadow-host",
                "selector_strategy": "css",
                "selector_normalized": True,
            },
            "element": {
                "found": True,
                "selector": selector,
                "locator": "css:#shadow-button",
                "selector_strategy": "css",
                "selector_normalized": True,
                "text": "Shadow Action",
                "tag": "button",
                "html": "<button id='shadow-button'>Shadow Action</button>",
                "visible": True,
            },
        }

    async def shadow_find_all(
        self,
        *,
        host_selector: str,
        selector: str,
        limit: int = 20,
        include_html: bool = False,
    ) -> dict[str, Any]:
        self._record(
            "shadow_find_all",
            host_selector=host_selector,
            selector=selector,
            limit=limit,
            include_html=include_html,
        )
        return {
            "host": {
                "selector": host_selector,
                "locator": "css:#shadow-host",
                "selector_strategy": "css",
                "selector_normalized": True,
            },
            "target": {
                "selector": selector,
                "locator": "css:.shadow-item",
                "selector_strategy": "css",
                "selector_normalized": True,
            },
            "count": 2,
            "returned": min(limit, 2),
            "limit": limit,
            "truncated": limit < 2,
            "elements": [
                {
                    "index": 0,
                    "tag": "li",
                    "text": "Shadow Alpha",
                    "selector": "#shadow-alpha",
                    "attributes": {"id": "shadow-alpha"},
                }
            ][:limit],
        }

    async def cookies_get(
        self,
        *,
        all_domains: bool = False,
        all_info: bool = False,
        include_values: bool = False,
    ) -> dict[str, Any]:
        self._record(
            "cookies_get",
            all_domains=all_domains,
            all_info=all_info,
            include_values=include_values,
        )
        value = "fixture-cookie" if include_values else "<redacted>"
        return {
            "count": 1,
            "include_values": include_values,
            "all_domains": all_domains,
            "cookies": [
                {
                    "name": "fixture",
                    "value": value,
                    "domain": "example.test",
                    "path": "/",
                    "expires": None,
                    "secure": False,
                    "http_only": False,
                }
            ],
        }

    async def cookies_set(self, *, cookies: list[dict[str, Any]]) -> dict[str, Any]:
        self._record("cookies_set", cookies=cookies)
        return {"count": len(cookies), "set": True, "cookies": cookies}

    async def cookies_delete(
        self,
        *,
        name: str,
        url: str | None = None,
        domain: str | None = None,
        path: str | None = None,
    ) -> dict[str, Any]:
        self._record(
            "cookies_delete", cookie_name=name, url=url, domain=domain, path=path
        )
        return {
            "name": name,
            "url": url,
            "domain": domain,
            "path": path,
            "deleted": True,
        }

    async def cookies_clear(self) -> dict[str, Any]:
        self._record("cookies_clear")
        return {"cleared": True}

    async def network_blocked_urls_set(
        self, urls: list[str]
    ) -> dict[str, Any]:
        self._record("network_blocked_urls_set", urls=urls)
        return {"count": len(urls), "urls": urls, "set": True}

    async def get(
        self, *, area: str = "local", key: str = "", include_values: bool = False
    ) -> dict[str, Any]:
        self._record("storage_get", area=area, key=key, include_values=include_values)
        return {
            "area": area,
            "key": key,
            "include_values": include_values,
            "count": 1,
            "items": {"mode": "dark" if include_values else "<redacted>"},
        }

    async def set(self, *, area: str, key: str, value: str) -> dict[str, Any]:
        self._record("storage_set", area=area, key=key, value=value)
        return {"area": area, "key": key, "set": True}

    async def clear(self, *, area: str, key: str = "") -> dict[str, Any]:
        self._record("storage_clear", area=area, key=key)
        return {"area": area, "key": key, "cleared": True}

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))


class FakeContext:
    def __init__(self) -> None:
        self.tab = FakeTab()
        self.created_tab = FakeTab()
        self.created_tab.mcp_tab_id = "t1"
        self.created_tab.native_tab_id = "native-1"
        self.created_tab.url = "https://example.test/new"
        self.closed = False
        self.waited: list[float] = []
        self.tab_infos = [
            {
                "id": "t0",
                "native_id": "native-0",
                "url": "https://example.test/current",
                "title": "Current",
                "active": True,
                "connected": True,
            },
            {
                "id": "t1",
                "native_id": "native-1",
                "url": "https://example.test/new",
                "title": "New",
                "active": False,
                "connected": True,
            },
        ]

    def current_tab_or_die(self) -> FakeTab:
        return self.tab

    async def ensure_tab(self) -> FakeTab:
        return self.tab

    async def new_tab(self) -> FakeTab:
        return self.created_tab

    async def sync_tabs(self):
        return [self.tab, self.created_tab]

    def tab_summaries(self):
        return self.tab_infos

    async def switch_tab(self, tab_id: str):
        self.tab_infos[0]["active"] = False
        self.tab_infos[1]["active"] = True
        self.tab = self.created_tab
        return self.created_tab

    async def close_tab_by_id(self, tab_id: str):
        self.tab_infos = [info for info in self.tab_infos if info["id"] != tab_id]

    async def close_browser(self) -> None:
        self.closed = True

    async def wait(self, seconds: float) -> None:
        self.waited.append(seconds)


async def _execute(tool, ctx: FakeContext, args) -> ToolOutcome:
    response = ToolOutcome()
    response = await tool.execute(ctx, args)
    return response


def _message(response: ToolOutcome) -> str:
    return response.structured_content()["message"]


@pytest.mark.asyncio
async def test_common_tools_success_paths(monkeypatch, tmp_path) -> None:
    ctx = FakeContext()
    resize_response = await _execute(
        common.resize, ctx, common.ResizeInput(width=640, height=480)
    )
    assert resize_response.structured_content()["data"] == {"width": 640, "height": 480}
    assert "640x480" in _message(resize_response)
    assert ctx.tab.calls[-1] == ("resize", (640, 480), {})
    inline_response = await _execute(
        common.screenshot, ctx, common.ScreenshotInput(full_page=True)
    )
    inline_payload = inline_response.structured_content()
    assert inline_payload["data"]["screenshot"]["inline"] is True
    assert inline_payload["data"]["screenshot"]["full_page"] is True
    monkeypatch.setenv("DP_MCP_SCREENSHOT_ROOT", str(tmp_path))
    path_response = await _execute(
        common.screenshot_save,
        ctx,
        common.ScreenshotSaveInput(path="screen.png", full_page=False),
    )
    path_payload = path_response.structured_content()
    assert path_payload["data"]["screenshot"]["safe_relative_path"] == "screen.png"
    assert "path" not in path_payload["data"]["screenshot"]
    assert path_payload["data"]["screenshot"]["inline"] is False
    snapshot_response = await _execute(
        common.page_snapshot,
        ctx,
        common.PageSnapshotInput(include_html=True, max_elements=5, max_text_chars=100),
    )
    snapshot_payload = snapshot_response.structured_content()
    assert snapshot_payload["data"]["title"] == "Fake Catalog"
    assert snapshot_payload["data"]["limits"] == {
        "max_elements": 5,
        "max_text_chars": 100,
    }
    assert ctx.tab.calls[-1] == (
        "page_snapshot",
        (),
        {"include_html": True, "max_elements": 5, "max_text_chars": 100},
    )
    accessibility_response = await _execute(
        common.page_accessibility_snapshot,
        ctx,
        common.PageAccessibilitySnapshotInput(max_nodes=5),
    )
    accessibility_data = accessibility_response.structured_content()["data"]
    assert accessibility_data["nodes"][0]["role"] == "button"
    assert accessibility_data["nodes"][0]["name"] == "Save"
    assert accessibility_data["returned"] == 1
    assert accessibility_data["values_included"] is False
    assert accessibility_data["meta"]["truncated"] is False
    dialog_response = await _execute(
        dialogs.page_dialog_observe,
        ctx,
        dialogs.PageDialogObserveInput(timeout=2, max_message_chars=7),
    )
    assert dialog_response.structured_content()["data"] == {
        "pending": True,
        "timed_out": False,
        "dialog_type": "confirm",
        "message": "Fixture",
        "message_truncated": True,
        "timeout": 2.0,
    }

    async def no_pending_dialog(*, timeout: float) -> dict[str, str]:
        raise TimeoutError(f"No dialog within {timeout}")

    ctx.tab.dialogs = SimpleNamespace(wait_for_pending=no_pending_dialog)
    no_dialog_response = await _execute(
        dialogs.page_dialog_observe,
        ctx,
        dialogs.PageDialogObserveInput(timeout=0.1),
    )
    assert no_dialog_response.structured_content()["data"] == {
        "pending": False,
        "timed_out": True,
        "dialog_type": None,
        "message": "",
        "message_truncated": False,
        "timeout": 0.1,
    }
    observe_response = await _execute(
        common.page_observe,
        ctx,
        common.PageObserveInput(max_texts=3, max_text_chars=80),
    )
    observe_payload = observe_response.structured_content()
    assert observe_payload["data"]["url"] == "https://example.test/current"
    assert observe_payload["data"]["limits"] == {"max_texts": 3, "max_text_chars": 80}
    evaluate_response = await _execute(
        common.page_evaluate,
        ctx,
        common.PageEvaluateInput(
            script="return {total: args[0] + args[1]};", args=[2, 3], max_chars=1000
        ),
    )
    evaluate_payload = evaluate_response.structured_content()
    assert evaluate_payload["data"]["result_type"] == "object"
    assert evaluate_payload["data"]["max_chars"] == 1000
    assert ctx.tab.calls[-1] == (
        "evaluate_script",
        ("return {total: args[0] + args[1]};",),
        {"args": [2, 3], "max_chars": 1000},
    )
    console_response = await _execute(
        debug.page_console_logs,
        ctx,
        debug.ConsoleLogsInput(level="error", since=0, limit=10),
    )
    console_payload = console_response.structured_content()
    assert console_payload["data"]["count"] == 1
    assert console_payload["data"]["logs"][0]["text"] == "after error"
    assert ctx.tab.calls[-1] == (
        "console_logs",
        (),
        {"level": "error", "since": 0, "limit": 10},
    )
    click_response = await _execute(
        pointer.click_coordinates, ctx, pointer.ClickCoordinatesInput(x=7, y=9)
    )
    assert click_response.structured_content()["data"] == {
        "x": 7.0,
        "y": 9.0,
        "element": "",
        "url": "https://example.test/current",
        "motion": {
            "profile": "direct",
            "button": "left",
            "start_x": 0.0,
            "start_y": 0.0,
            "target_x": 7.0,
            "target_y": 9.0,
            "steps": 1,
            "delay_before_press_ms": 0,
            "planned_duration_ms": 0,
        },
    }
    assert "(7, 9)" in _message(click_response)
    close_response = await _execute(common.close, ctx, common.EmptyInput())
    assert close_response.structured_content()["data"] == {"closed": True}
    assert ctx.closed is True
    assert "closed browser" in _message(close_response)
    url_response = await _execute(common.get_url, ctx, common.EmptyInput())
    assert url_response.structured_content()["data"] == {
        "url": "https://example.test/current"
    }
    assert "https://example.test/current" in _message(url_response)
    headers_response = await _execute(
        common.browser_headers_set,
        ctx,
        common.BrowserHeadersSetInput(
            headers={"X-MCP-Session": "callback-secret"}
        ),
    )
    assert headers_response.structured_content()["data"] == {
        "count": 1,
        "headers": {"X-MCP-Session": "<redacted>"},
        "set": True,
    }
    user_agent_response = await _execute(
        common.browser_user_agent_set,
        ctx,
        common.BrowserUserAgentSetInput(
            user_agent="MCPBrowser/0.7.6", platform="Linux"
        ),
    )
    assert user_agent_response.structured_content()["data"] == {
        "previous_user_agent": "FixtureBrowser/1.0",
        "user_agent": "MCPBrowser/0.7.6",
        "platform": "Linux",
        "set": True,
    }
    cache_response = await _execute(
        common.browser_cache_clear, ctx, common.EmptyInput()
    )
    assert cache_response.structured_content()["data"] == {"cleared": True}


@pytest.mark.asyncio
async def test_network_tools_success_paths() -> None:
    ctx = FakeContext()
    start_response = await _execute(
        network.network_listen_start,
        ctx,
        network.NetworkListenStartInput(targets=["/api"], method="GET"),
    )
    start_payload = start_response.structured_content()
    assert start_payload["data"]["listening"] is True
    assert start_payload["data"]["filters"]["targets"] == ["/api"]
    wait_response = await _execute(
        network.network_listen_wait,
        ctx,
        network.NetworkListenWaitInput(
            timeout=1,
            limit=5,
            include_headers=True,
            include_body=True,
            max_body_chars=20,
        ),
    )
    wait_payload = wait_response.structured_content()
    packet = wait_payload["data"]["packets"][0]
    assert wait_payload["data"]["count"] == 1
    assert packet["request_headers"]["authorization"] == "<redacted>"
    assert packet["body_excerpt"] == '{"ok":true}'
    assert wait_payload["data"]["meta"]["json_chars"] > 0
    stop_response = await _execute(
        network.network_listen_stop, ctx, network.NetworkListenStopInput(clear=True)
    )
    assert stop_response.structured_content()["data"] == {
        "listening": False,
        "was_listening": True,
        "cleared": True,
    }
    blocked_response = await _execute(
        network.network_blocked_urls_set,
        ctx,
        network.NetworkBlockedUrlsSetInput(urls=["*.png", "*analytics*"]),
    )
    assert blocked_response.structured_content()["data"] == {
        "count": 2,
        "urls": ["*.png", "*analytics*"],
        "set": True,
    }


@pytest.mark.asyncio
async def test_file_and_interaction_tools_success_paths(monkeypatch, tmp_path) -> None:
    ctx = FakeContext()
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    upload_file = upload_root / "fixture.txt"
    upload_file.write_text("upload", encoding="utf-8")
    monkeypatch.setenv("DP_MCP_UPLOAD_ROOT", str(upload_root))
    upload_response = await _execute(
        files.element_upload_file,
        ctx,
        files.UploadFileInput(selector="#upload", paths=[str(upload_file)], timeout=2),
    )
    upload_payload = upload_response.structured_content()
    assert upload_payload["data"] == {
        "selector": "#upload",
        "locator": "css:#upload",
        "selector_strategy": "css",
        "selector_normalized": True,
        "uploaded": True,
        "file_count": 1,
        "filenames": ["fixture.txt"],
    }
    assert str(upload_file) not in str(upload_payload["data"])
    scroll_response = await _execute(
        interaction.page_scroll, ctx, interaction.PageScrollInput(direction="bottom")
    )
    assert scroll_response.structured_content()["data"]["direction"] == "bottom"
    into_view_response = await _execute(
        interaction.element_scroll_into_view,
        ctx,
        interaction.ElementScrollIntoViewInput(
            selector="#deep", center=False, timeout=2
        ),
    )
    assert into_view_response.structured_content()["data"]["center"] is False
    hover_response = await _execute(
        interaction.element_hover,
        ctx,
        interaction.ElementHoverInput(selector="#hover", offset_x=1, offset_y=2),
    )
    assert hover_response.structured_content()["data"]["offset_x"] == 1
    keyboard_response = await _execute(
        interaction.keyboard_press,
        ctx,
        interaction.KeyboardPressInput(keys="callback-secret", interval=0.01),
    )
    assert keyboard_response.structured_content()["data"] == {
        "keys": {"provided": True, "length": 15, "redacted": True},
        "interval": 0.01,
        "url": "https://example.test/current",
    }
    response_text = "\n".join(
        getattr(block, "text", "") for block in keyboard_response.content()
    )
    assert "callback-secret" not in response_text
    select_response = await _execute(
        interaction.element_select,
        ctx,
        interaction.ElementSelectInput(selector="#mode", value="advanced", by="value"),
    )
    assert select_response.structured_content()["data"]["selected"] is True
    check_response = await _execute(
        interaction.element_check,
        ctx,
        interaction.ElementCheckInput(selector="#agree", checked=True, by_js=True),
    )
    assert check_response.structured_content()["data"]["checked"] is True


@pytest.mark.asyncio
async def test_frame_shadow_and_storage_tools_success_paths() -> None:
    ctx = FakeContext()
    frames_response = await _execute(
        frame.frame_list, ctx, frame.FrameListInput(limit=5)
    )
    frames_payload = frames_response.structured_content()
    assert frames_payload["data"]["count"] == 1
    assert frames_payload["data"]["frames"][0]["selector"] == "#fixture-frame"
    snapshot_response = await _execute(
        frame.frame_snapshot,
        ctx,
        frame.FrameSnapshotInput(frame_index=0, max_elements=3, max_text_chars=100),
    )
    snapshot_payload = snapshot_response.structured_content()
    assert snapshot_payload["data"]["frame"]["id"] == "fixture-frame"
    assert snapshot_payload["data"]["meta"]["truncated"] is False
    frame_find_response = await _execute(
        frame.frame_find,
        ctx,
        frame.FrameFindInput(frame_index=0, selector="#frame-text"),
    )
    assert (
        frame_find_response.structured_content()["data"]["element"]["text"]
        == "frame ready"
    )
    shadow_response = await _execute(
        shadow.shadow_find,
        ctx,
        shadow.ShadowFindInput(host_selector="#shadow-host", selector="#shadow-button"),
    )
    assert shadow_response.structured_content()["data"]["element"]["tag"] == "button"
    shadow_all_response = await _execute(
        shadow.shadow_find_all,
        ctx,
        shadow.ShadowFindAllInput(
            host_selector="#shadow-host", selector=".shadow-item", limit=1
        ),
    )
    shadow_all = shadow_all_response.structured_content()["data"]
    assert shadow_all["returned"] == 1
    assert shadow_all["meta"]["truncated"] is True
    cookies_response = await _execute(
        storage.browser_cookies_get,
        ctx,
        storage.BrowserCookiesGetInput(include_values=False),
    )
    cookies = cookies_response.structured_content()["data"]
    assert cookies["cookies"][0]["value"] == "<redacted>"
    cookies_set_response = await _execute(
        storage.browser_cookies_set,
        ctx,
        storage.BrowserCookiesSetInput(
            cookies=[
                storage.BrowserCookieInput(
                    name="sid",
                    value="callback-secret",
                    domain="example.test",
                    path="/",
                    http_only=True,
                    same_site="Lax",
                )
            ]
        ),
    )
    cookies_set = cookies_set_response.structured_content()["data"]
    assert cookies_set == {
        "count": 1,
        "set": True,
        "cookies": [
                {
                    "name": "sid",
                    "value": "<redacted>",
                "url": "",
                "domain": "example.test",
                "path": "/",
                "http_only": True,
                "same_site": "Lax",
            }
        ],
    }
    cookies_delete_response = await _execute(
        storage.browser_cookies_delete,
        ctx,
        storage.BrowserCookiesDeleteInput(
            name="sid", domain="example.test", path="/"
        ),
    )
    assert cookies_delete_response.structured_content()["data"] == {
        "name": "sid",
        "url": None,
        "domain": "example.test",
        "path": "/",
        "deleted": True,
    }
    cookies_clear_response = await _execute(
        storage.browser_cookies_clear,
        ctx,
        storage.BrowserCookiesClearInput(),
    )
    assert cookies_clear_response.structured_content()["data"] == {"cleared": True}
    storage_get_response = await _execute(
        storage.storage_get,
        ctx,
        storage.StorageGetInput(area="local"),
    )
    assert storage_get_response.structured_content()["data"]["items"] == {
        "mode": "<redacted>"
    }
    storage_get_response = await _execute(
        storage.storage_get,
        ctx,
        storage.StorageGetInput(area="local", include_values=True),
    )
    assert storage_get_response.structured_content()["data"]["items"] == {
        "mode": "dark"
    }
    storage_set_response = await _execute(
        storage.storage_set,
        ctx,
        storage.StorageSetInput(area="session", key="draft", value="42"),
    )
    assert storage_set_response.structured_content()["data"] == {
        "area": "session",
        "key": "draft",
        "set": True,
    }
    storage_clear_response = await _execute(
        storage.storage_clear,
        ctx,
        storage.StorageClearInput(area="session", key="draft"),
    )
    assert storage_clear_response.structured_content()["data"]["cleared"] is True


@pytest.mark.asyncio
async def test_navigation_tools_success_paths() -> None:
    ctx = FakeContext()
    nav_response = await _execute(
        navigate.navigate, ctx, navigate.NavigateInput(url="https://example.test/next")
    )
    assert nav_response.structured_content()["data"] == {
        "url": "https://example.test/next",
        "final_url": "https://example.test/next",
        "new_tab": False,
        "tab_id": "t0",
    }
    assert "Successfully navigated" in _message(nav_response)
    assert ctx.tab.url == "https://example.test/next"
    observed_ctx = FakeContext()
    observed_nav_response = await _execute(
        navigate.navigate,
        observed_ctx,
        navigate.NavigateInput(url="https://example.test/observed", observe=True),
    )
    observed_nav_data = observed_nav_response.structured_content()["data"]
    assert observed_nav_data["final_url"] == "https://example.test/observed"
    assert observed_nav_data["changes"]["url_changed"] is True
    assert observed_nav_data["changes"]["appeared_texts"] == ["after"]
    assert observed_nav_data["changes"]["console_errors_added"] == 1
    assert (
        observed_nav_data["changes"]["new_console_messages"][0]["text"] == "after error"
    )
    new_tab_response = await _execute(
        navigate.navigate,
        ctx,
        navigate.NavigateInput(url="https://example.test/new", new_tab=True),
    )
    new_tab_payload = new_tab_response.structured_content()
    assert new_tab_payload["data"]["url"] == "https://example.test/new"
    assert new_tab_payload["data"]["final_url"] == "https://example.test/new"
    assert new_tab_payload["data"]["new_tab"] is True
    for tool, expected_call, expected_message in [
        (navigate.go_back, "go_back", "went back"),
        (navigate.go_forward, "go_forward", "went forward"),
        (navigate.refresh, "refresh", "refreshed page"),
    ]:
        response = await _execute(tool, ctx, navigate.EmptyInput())
        assert response.structured_content()["data"] == {
            "url": "https://example.test/next"
        }
        assert expected_message in _message(response)
        assert ctx.tab.calls[-1][0] == expected_call


@pytest.mark.asyncio
async def test_wait_tools_success_and_timeout_paths() -> None:
    ctx = FakeContext()
    element_response = await _execute(
        wait.wait_for_element, ctx, wait.WaitElementInput(selector="#ready", timeout=2)
    )
    assert element_response.structured_content()["data"] == {
        "selector": "#ready",
        "locator": "css:#ready",
        "selector_strategy": "css",
        "selector_normalized": True,
        "found": True,
        "timeout": 2,
    }
    assert "appeared within 2 seconds" in _message(element_response)
    url_response = await _execute(
        wait.wait_for_url, ctx, wait.WaitUrlInput(url_pattern="ready", timeout=3)
    )
    assert url_response.structured_content()["data"] == {
        "url_pattern": "ready",
        "matched": True,
        "url": "https://example.test/current",
        "timeout": 3,
    }
    assert "URL matched" in _message(url_response)
    time_response = await _execute(
        wait.wait_time, ctx, wait.WaitTimeInput(seconds=0.25)
    )
    assert time_response.structured_content()["data"] == {"waited_seconds": 0.25}
    assert ctx.waited == [0.25]
    assert "Waited for 0.25 seconds" in _message(time_response)
    until_response = await _execute(
        wait.wait_until,
        ctx,
        wait.WaitUntilInput(
            condition="clickable",
            selector="#ready",
            timeout=2,
            interval=0.2,
            stable_ms=50,
        ),
    )
    until_payload = until_response.structured_content()
    assert until_payload["data"] == {
        "condition": "clickable",
        "selector": "#ready",
        "value": "",
        "name": "",
        "matched": True,
        "timeout": 2.0,
        "elapsed_ms": 15,
        "state": {"selector": "#ready", "visible": True},
    }
    ctx.tab.wait_element_result = False
    timeout_response = await _execute(
        wait.wait_for_element,
        ctx,
        wait.WaitElementInput(selector="#missing", timeout=1),
    )
    assert timeout_response.is_error is True
    assert "did not appear" in timeout_response.structured_content()["message"]
    ctx.tab.wait_url_result = False
    url_timeout_response = await _execute(
        wait.wait_for_url, ctx, wait.WaitUrlInput(url_pattern="never", timeout=1)
    )
    assert url_timeout_response.is_error is True
    assert "URL did not match" in url_timeout_response.structured_content()["message"]


def test_element_find_default_timeout_is_llm_friendly() -> None:
    args = element.FindElementInput(selector="h1")
    assert args.timeout == 3


def test_get_property_input_uses_property_field_only() -> None:
    args = element.GetPropertyInput.model_validate(
        {"selector": "#name", "property": "value"}
    )
    assert args.property == "value"
    with pytest.raises(Exception, match="property"):
        element.GetPropertyInput.model_validate(
            {"selector": "#name", "property_name": "value"}
        )


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (common.PageSnapshotInput, {"maxElements": 10}),
        (common.PageObserveInput, {"maxTexts": 10}),
        (common.PageEvaluateInput, {"script": "return 1", "maxChars": 100}),
        (common.ScreenshotInput, {"fullPage": True}),
        (common.ScreenshotInput, {"path": "/tmp/screen.png"}),
        (common.ResizeInput, {"width": 800, "height": 600, "extra": True}),
        (navigate.NavigateInput, {"url": "https://example.test", "background": True}),
        (element.FindElementInput, {"selector": "h1", "timeout_ms": 1}),
        (element.FindAllElementsInput, {"selector": "li", "max_items": 10}),
        (
            element.TypeTextInput,
            {"selector": "#name", "text": "Ada", "clear_first": False},
        ),
        (
            element.GetPropertyInput,
            {"selector": "#name", "property": "value", "property_name": "value"},
        ),
        (network.NetworkListenStartInput, {"target": "/api"}),
        (network.NetworkListenWaitInput, {"timeout_ms": 1000}),
        (wait.WaitTimeInput, {"seconds": 1, "milliseconds": 500}),
        (wait.WaitUntilInput, {"condition": "visible", "timeout_ms": 1}),
    ],
)
def test_tool_inputs_reject_unknown_fields(model, payload) -> None:
    """LLM/client field typos should fail instead of being silently ignored."""
    with pytest.raises(Exception, match="Extra inputs"):
        model.model_validate(payload)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (element.FindElementInput, {"selector": "h1", "timeout": 121}),
        (element.ClickElementInput, {"selector": "button", "timeout": 121}),
        (element.TypeTextInput, {"selector": "#name", "text": "Ada", "timeout": 121}),
        (wait.WaitElementInput, {"selector": "#ready", "timeout": 121}),
        (wait.WaitUrlInput, {"url_pattern": "ready", "timeout": 121}),
        (wait.WaitTimeInput, {"seconds": 121}),
    ],
)
def test_wait_inputs_reject_excessive_timeouts(model, payload) -> None:
    """Client-controlled waits should stay bounded."""
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.asyncio
async def test_tab_tools_success_paths() -> None:
    ctx = FakeContext()
    list_response = await _execute(tabs.tab_list, ctx, tabs.EmptyInput())
    list_payload = list_response.structured_content()
    assert list_payload["data"]["count"] == 2
    assert list_payload["data"]["active_tab_id"] == "t0"
    assert list_payload["data"]["tabs"][1]["url"] == "https://example.test/new"
    switch_response = await _execute(tabs.tab_switch, ctx, tabs.TabIdInput(tab_id="t1"))
    switch_payload = switch_response.structured_content()
    assert switch_payload["data"]["tab"]["id"] == "t1"
    assert switch_payload["data"]["tab"]["active"] is True
    close_response = await _execute(tabs.tab_close, ctx, tabs.TabIdInput(tab_id="t1"))
    close_payload = close_response.structured_content()
    assert close_payload["data"]["closed"] is True
    assert close_payload["data"]["tab_id"] == "t1"


@pytest.mark.asyncio
async def test_element_tools_success_paths() -> None:
    ctx = FakeContext()
    selector_metadata = {
        "selector": "#name",
        "locator": "css:#name",
        "selector_strategy": "css",
        "selector_normalized": True,
    }
    found_response = await _execute(
        element.find_element, ctx, element.FindElementInput(selector="#name", timeout=1)
    )
    assert found_response.structured_content()["data"] == {
        "element": {
            "found": True,
            **selector_metadata,
            "text": "Ada",
            "tag": "input",
            "html": "<input id='name'>",
            "visible": True,
        }
    }
    assert found_response.structured_content()["message"] == "Found element: #name"
    found_all_response = await _execute(
        element.find_all_elements,
        ctx,
        element.FindAllElementsInput(
            selector=".product-card", limit=1, include_html=True
        ),
    )
    found_all_payload = found_all_response.structured_content()
    found_all_data = dict(found_all_payload["data"])
    found_all_meta = found_all_data.pop("meta")
    assert found_all_meta["approx_tokens"] > 0
    assert found_all_meta["json_chars"] > 0
    assert found_all_meta["truncated"] is True
    assert found_all_data == {
        "selector": ".product-card",
        "locator": "css:.product-card",
        "selector_strategy": "css",
        "selector_normalized": True,
        "count": 2,
        "returned": 1,
        "limit": 1,
        "truncated": True,
        "elements": [
            {
                "index": 0,
                "tag": "article",
                "text": "Alpha",
                "selector": "#alpha",
                "attributes": {"id": "alpha", "class": "product-card"},
                "html": "<article>Alpha</article>",
            }
        ],
    }
    click_response = await _execute(
        element.click_element,
        ctx,
        element.ClickElementInput(selector="#name", timeout=1),
    )
    assert click_response.structured_content()["data"] == {
        **selector_metadata,
        "url": "https://example.test/current",
        "button": "left",
        "click_count": 1,
    }
    assert "Successfully clicked element" in _message(click_response)
    observed_click = await _execute(
        element.click_element,
        ctx,
        element.ClickElementInput(selector="#name", timeout=1, observe=True),
    )
    observed_click_data = observed_click.structured_content()["data"]
    assert observed_click_data["changes"]["appeared_texts"] == ["after"]
    type_response = await _execute(
        element.type_text,
        ctx,
        element.TypeTextInput(selector="#name", text="Ada", clear=False),
    )
    assert type_response.structured_content()["data"] == {
        **selector_metadata,
        "typed": True,
        "cleared": False,
    }
    assert "Ada" not in str(type_response.structured_content()["data"])
    assert "Successfully typed" in _message(type_response)
    observed_type = await _execute(
        element.type_text,
        ctx,
        element.TypeTextInput(selector="#name", text="Ada", clear=False, observe=True),
    )
    observed_type_data = observed_type.structured_content()["data"]
    assert observed_type_data["changes"]["counts_delta"]["buttons"] == 1
    text_response = await _execute(
        element.get_text, ctx, element.GetTextInput(selector="#name")
    )
    assert text_response.structured_content()["data"] == {
        "text": "element text",
        **selector_metadata,
    }
    page_text_response = await _execute(element.get_text, ctx, element.GetTextInput())
    assert page_text_response.structured_content()["data"] == {
        "text": "page text",
        "selector": "",
        "locator": "",
        "selector_strategy": "page",
        "selector_normalized": False,
    }
    attr_response = await _execute(
        element.get_attribute,
        ctx,
        element.GetAttributeInput(selector="#name", attribute="id"),
    )
    assert attr_response.structured_content()["data"] == {
        **selector_metadata,
        "attribute": "id",
        "value": "attr-value",
    }
    missing_attr_response = await _execute(
        element.get_attribute,
        ctx,
        element.GetAttributeInput(selector="#name", attribute="missing"),
    )
    assert missing_attr_response.structured_content()["data"]["value"] is None
    prop_response = await _execute(
        element.get_property,
        ctx,
        element.GetPropertyInput(selector="#name", property="value"),
    )
    assert prop_response.structured_content()["data"] == {
        **selector_metadata,
        "property": "value",
        "value": "prop-value",
    }
    missing_prop_response = await _execute(
        element.get_property,
        ctx,
        element.GetPropertyInput(selector="#name", property="missing"),
    )
    assert missing_prop_response.structured_content()["data"]["value"] is None
    html_response = await _execute(
        element.get_html, ctx, element.GetHtmlInput(selector="#name")
    )
    assert html_response.structured_content()["data"] == {
        "html": "<input>",
        **selector_metadata,
    }
    page_html_response = await _execute(element.get_html, ctx, element.GetHtmlInput())
    assert page_html_response.structured_content()["data"] == {
        "html": "<html></html>",
        "selector": "",
        "locator": "",
        "selector_strategy": "page",
        "selector_normalized": False,
    }
    state_response = await _execute(
        element.element_state_get,
        ctx,
        element.ElementStateInput(
            selector={
                "kind": "accessibility",
                "role": "button",
                "name": "Save",
                "shadow_hosts": ["#app-host"],
            },
            timeout=2,
        ),
    )
    state_data = state_response.structured_content()["data"]
    assert state_data["target_kind"] == "accessibility"
    assert state_data["clickable"] is True
    assert state_data["rect"]["size"] == {"width": 80.0, "height": 30.0}
    assert state_data["rect"]["coordinate_space"] == "target_document"


class MissingElementTypeTab(FakeTab):
    async def type_text(
        self, selector: str, text: str, timeout: int = 10, clear: bool = True
    ) -> None:
        self._record("type_text", selector, text, timeout=timeout, clear=clear)
        raise ElementNotFoundError(f"Element not found: {selector}")


@pytest.mark.asyncio
async def test_element_type_reports_structured_not_found_error() -> None:
    ctx = FakeContext()
    ctx.tab = MissingElementTypeTab()
    response = await _execute(
        element.type_text,
        ctx,
        element.TypeTextInput(selector="#missing", text="Ada", timeout=1),
    )
    payload = response.structured_content()
    assert response.is_error is True
    assert payload["error"]["code"] == "ELEMENT_NOT_FOUND"
    assert "#missing" in payload["message"]
