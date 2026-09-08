"""Unit coverage for PageTab without launching a real browser."""

from __future__ import annotations

import asyncio
import base64
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from drissionpage_mcp.browser.network import NetworkListenerNotFoundError
from drissionpage_mcp.tab import PageTab
from drissionpage_mcp.target import SelectorTargetInput


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    """Keep PageTab async helper tests fast and deterministic."""

    async def _sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("drissionpage_mcp.tab.asyncio.sleep", _sleep)
    monkeypatch.setattr("drissionpage_mcp.browser.pointer.asyncio.sleep", _sleep)
    monkeypatch.setattr("drissionpage_mcp.browser.waits.asyncio.sleep", _sleep)


class FakeActions:
    def __init__(self) -> None:
        self.clicked = None
        self.curr_x = 0.0
        self.curr_y = 0.0
        self.modifier = 0

    def click(self, point):
        self.clicked = point


class FakeWindow:
    def __init__(self) -> None:
        self.size_args = None

    def size(self, width: int, height: int) -> None:
        self.size_args = (width, height)


class FakeCookiesSetter:
    def __init__(self) -> None:
        self.set_calls = []
        self.remove_calls = []
        self.clear_calls = 0

    def __call__(self, cookies) -> None:
        self.set_calls.append(cookies)

    def remove(self, name, url=None, domain=None, path=None) -> None:
        self.remove_calls.append((name, url, domain, path))

    def clear(self) -> None:
        self.clear_calls += 1


class FakeSet:
    def __init__(self) -> None:
        self.window = FakeWindow()
        self.cookies = FakeCookiesSetter()
        self.headers_calls = []
        self.user_agent_calls = []
        self.blocked_urls_calls = []

    def headers(self, headers) -> None:
        self.headers_calls.append(headers)

    def user_agent(self, user_agent, platform=None) -> None:
        self.user_agent_calls.append((user_agent, platform))

    def blocked_urls(self, urls) -> None:
        self.blocked_urls_calls.append(urls)


class FakeConsole:
    def __init__(
        self, *, messages=None, listening: bool = False, start_raises=False
    ) -> None:
        self.messages = list(messages or [])
        self.listening = listening
        self.start_raises = start_raises
        self.started = False

    def start(self) -> None:
        if self.start_raises:
            raise RuntimeError("console unavailable")
        self.started = True
        self.listening = True


class FakeWait:
    def __init__(self, loaded: bool = True, fail: bool = False) -> None:
        self.loaded = loaded
        self.fail = fail
        self.calls = []

    def ele_loaded(self, selector: str, timeout: int = 10) -> bool:
        if self.fail:
            raise RuntimeError("wait failed")
        self.calls.append(("ele_loaded", selector, timeout))
        return self.loaded


class FakeWaitFallback:
    def __init__(self) -> None:
        self.calls = []

    def eles_loaded(
        self, selector: str, timeout: int = 10, any_one: bool = True
    ) -> bool:
        self.calls.append((selector, timeout, any_one))
        return True


class FakeElement:
    def __init__(
        self,
        *,
        tag: str = "input",
        text: str = "Ada",
        html: str = '<input id="name" value="Ada">',
        attrs: dict[str, str | None] | None = None,
    ) -> None:
        self.tag = tag
        self.html = html
        self.text = text
        self.attrs = {"id": "name", "missing": None}
        if attrs:
            self.attrs.update(attrs)
        self.clicked = False
        self.cleared = False
        self.clear_calls = []
        self.inputs = []

    def click(self) -> None:
        self.clicked = True

    def clear(self, by_js: bool = False) -> None:
        self.cleared = True
        self.clear_calls.append(by_js)

    def input(self, text: str) -> None:
        self.inputs.append(text)
        self.text = text

    def attr(self, attribute: str):
        if attribute in self.attrs:
            return self.attrs[attribute]
        if attribute in {
            "class",
            "name",
            "type",
            "href",
            "value",
            "placeholder",
            "role",
            "aria-label",
            "data-testid",
        }:
            return None
        return "attr-value"

    def property(self, property_name: str):
        return {"value": self.text}.get(property_name)


_DEFAULT_ELEMENT = object()


class FakePage:
    def __init__(self, element=_DEFAULT_ELEMENT) -> None:
        self.url = "about:blank"
        self.text = "Whole page text"
        self.html = "<html><body>Whole page text</body></html>"
        self.tab_id = "tab-1"
        self.user_agent = "FakeBrowser/1.0"
        self.actions = FakeActions()
        self.wait = FakeWait()
        self.set = FakeSet()
        self.console = FakeConsole()
        self.element = FakeElement() if element is _DEFAULT_ELEMENT else element
        self.elements = [self.element] if self.element is not None else []
        self.calls = []
        self.closed = False
        self.cache_clear_calls = []
        self.snapshot = {
            "url": self.url,
            "title": "Fake Page",
            "text_excerpt": "Whole page text",
            "headings": [],
            "links": [],
            "buttons": [],
            "inputs": [],
            "forms": [],
            "counts": {},
            "truncated": {
                "text": False,
                "elements": False,
                "returned_elements": 0,
            },
            "limits": {"max_elements": 50, "max_text_chars": 4000},
        }

    def get(self, url: str):
        self.calls.append(("get", url))
        self.url = url
        return SimpleNamespace(url=url, ok=True)

    def run_cdp(self, method: str, **params):
        self.calls.append((method, params))
        return {}

    def back(self) -> None:
        self.calls.append(("back",))

    def forward(self) -> None:
        self.calls.append(("forward",))

    def refresh(self) -> None:
        self.calls.append(("refresh",))

    def ele(self, selector: str, **_kwargs):
        self.calls.append(("ele", selector))
        return self.element

    def eles(self, selector: str, **kwargs):
        self.calls.append(("eles", selector, kwargs))
        return self.elements

    def run_js(self, script: str, **kwargs):
        self.calls.append(("run_js", script[:40], kwargs))
        return self.snapshot

    def get_screenshot(self, **kwargs):
        self.calls.append(("screenshot", kwargs))
        path = kwargs.get("path")
        if path:
            Path(path).write_bytes(b"path-png")
            return None
        if kwargs.get("as_base64"):
            return b"inline-png"
        return None

    def close(self) -> None:
        self.closed = True

    def clear_cache(self, **kwargs) -> None:
        self.cache_clear_calls.append(kwargs)


class AttrConsoleMessage:
    def __init__(
        self,
        *,
        level: str = "log",
        text: str = "attr log",
        url: str = "https://example.test",
        line: int = 5,
        column: int = 2,
        source: str = "console-api",
    ) -> None:
        self.level = level
        self.text = text
        self.url = url
        self.line = line
        self.column = column
        self.source = source


class FakeContext:
    def __init__(self, browser=None) -> None:
        self.browser = browser


class FakeBrowser:
    def __init__(self) -> None:
        self.closed_tabs = []

    def close_tabs(self, tab_id: str) -> None:
        self.closed_tabs.append(tab_id)


class RaisingUrlPage:
    @property
    def url(self):
        raise RuntimeError("disconnected")


class RaisingIdentityPage(FakePage):
    @property
    def tab_id(self):
        raise RuntimeError("tab detached")

    @tab_id.setter
    def tab_id(self, _value):
        pass

    @property
    def title(self):
        raise RuntimeError("title detached")

    @title.setter
    def title(self, _value):
        pass


@pytest.mark.asyncio
async def test_navigation_coordinates_and_resize_paths() -> None:
    page = FakePage()
    tab = PageTab(page, FakeContext())

    await tab.navigation.navigate("https://example.test")
    await tab.navigation.back()
    await tab.navigation.forward()
    await tab.navigation.refresh()
    await tab.pointer.click_at(3, 4)
    await tab.page_ops.resize(800, 600)

    assert tab.url == "https://example.test"
    assert ("get", "https://example.test") in page.calls
    assert ("back",) in page.calls
    assert ("forward",) in page.calls
    assert ("refresh",) in page.calls
    pointer_events = [
        call[1]["type"]
        for call in page.calls
        if len(call) == 2 and call[0] == "Input.dispatchMouseEvent"
    ]
    assert pointer_events[-2:] == ["mousePressed", "mouseReleased"]
    assert page.actions.curr_x == 3
    assert page.actions.curr_y == 4
    assert page.set.window.size_args == (800, 600)


@pytest.mark.asyncio
async def test_element_actions_and_readers() -> None:
    element = FakeElement()
    page = FakePage(element)
    tab = PageTab(page, FakeContext())

    await tab.elements.click("#name")
    await tab.elements.input("#name", "Ada", clear=True)
    await tab.elements.type("#name", "Lovelace", clear=False)
    found = await tab.elements.find("#name")

    assert element.clicked is True
    assert element.cleared is True
    assert element.clear_calls == [True]
    assert element.inputs == ["Ada", "Lovelace"]
    assert found == {
        "found": True,
        "selector": "#name",
        "locator": "css:#name",
        "selector_strategy": "css",
        "selector_normalized": True,
        "text": "Lovelace",
        "tag": "input",
        "html": '<input id="name" value="Ada">',
        "visible": True,
    }
    assert await tab.elements.text("#name") == "Lovelace"
    assert await tab.elements.text() == "Whole page text"
    assert await tab.elements.attribute("#name", "id") == "name"
    assert await tab.elements.attribute("#name", "missing") is None
    assert await tab.elements.property("#name", "value") == "Lovelace"
    assert await tab.elements.html("#name") == '<input id="name" value="Ada">'
    assert await tab.elements.html() == "<html><body>Whole page text</body></html>"


@pytest.mark.asyncio
async def test_page_snapshot_and_find_elements_return_bounded_summaries() -> None:
    page = FakePage()
    page.snapshot = {
        "url": "https://example.test/catalog",
        "title": "Catalog",
        "text_excerpt": "Products",
        "headings": [
            {
                "index": 0,
                "tag": "h1",
                "text": "Products",
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
        "limits": {"max_elements": 5, "max_text_chars": 100},
    }
    page.elements = [
        FakeElement(
            tag="article",
            text="Alpha card",
            html="<article id='alpha'>Alpha card</article>",
            attrs={"id": "alpha", "class": "product-card"},
        ),
        FakeElement(
            tag="article",
            text="Beta card",
            html="<article id='beta'>Beta card</article>",
            attrs={"id": "beta", "class": "product-card"},
        ),
    ]
    tab = PageTab(page, FakeContext())

    snapshot = await tab.observation.snapshot(
        include_html=True,
        max_elements=5,
        max_text_chars=100,
    )
    found = await tab.elements.find_all(".product-card", limit=1, include_html=True)

    assert snapshot["title"] == "Catalog"
    assert ("run_js",) == (page.calls[-2][0],)
    assert found == {
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
                "text": "Alpha card",
                "selector": "#alpha",
                "attributes": {"id": "alpha", "class": "product-card"},
                "html": "<article id='alpha'>Alpha card</article>",
            }
        ],
    }


@pytest.mark.asyncio
async def test_observe_evaluate_and_wait_until_return_observable_state() -> None:
    class ObservablePage(FakePage):
        def run_js(self, script: str, **kwargs):
            self.calls.append(("run_js", script[:40], kwargs))
            if "__mcpFn" in script:
                return "abcdef"
            if "text_samples" in script:
                return {
                    "url": self.url,
                    "title": "Observable",
                    "ready_state": "complete",
                    "counts": {"buttons": 1, "inputs": 1},
                    "text_samples": ["Ready", "Save"],
                    "active_element": None,
                }
            if "const strategy" in script:
                return {
                    "exists": True,
                    "visible": True,
                    "disabled": False,
                    "tag": "button",
                    "text": "Save",
                    "signature": "button|save|enabled",
                }
            return super().run_js(script, **kwargs)

    page = ObservablePage()
    page.url = "https://example.test/ready"
    page.text = "Page is Ready"
    tab = PageTab(page, FakeContext())

    observation = await tab.observation.observe(max_texts=2, max_text_chars=50)
    evaluated = await tab.observation.evaluate(
        "return args[0];",
        args=["abcdef"],
        max_chars=4,
    )
    url_wait = await tab.waits.until(
        condition="url_contains",
        value="ready",
        timeout=0,
    )
    text_wait = await tab.waits.until(
        condition="text_contains",
        value="Ready",
        timeout=0,
    )
    clickable_wait = await tab.waits.until(
        condition="clickable",
        selector="#save",
        timeout=0,
    )
    stable_wait = await tab.waits.until(
        condition="stable",
        selector="#save",
        timeout=0,
        stable_ms=10,
    )

    assert observation["text_samples"] == ["Ready", "Save"]
    assert observation["active_element"] is None
    assert observation["limits"] == {"max_texts": 2, "max_text_chars": 50}
    assert evaluated == {
        "result": "abcd",
        "result_type": "string",
        "truncated": True,
        "original_json_chars": 8,
        "max_chars": 4,
    }
    assert url_wait["matched"] is True
    assert text_wait["state"]["text"] == "Page is Ready"
    assert clickable_wait["state"]["tag"] == "button"
    assert stable_wait["matched"] is True


@pytest.mark.asyncio
async def test_evaluate_preserves_non_finite_number_semantics_as_json_safe_data() -> None:
    class NonFinitePage(FakePage):
        def run_js(self, script: str, **kwargs):
            self.calls.append(("run_js", script[:40], kwargs))
            assert "Number.isFinite" in script
            return {
                "__drissionpage_mcp_result__": True,
                "kind": "non_finite_number",
                "value": "Infinity",
                "result_type": "number",
            }

    result = await PageTab(NonFinitePage(), FakeContext()).observation.evaluate(
        "return 1 / 0;"
    )

    assert result == {
        "result": None,
        "result_type": "number",
        "non_finite_number": "Infinity",
        "truncated": False,
        "original_json_chars": 4,
        "max_chars": 4000,
    }


@pytest.mark.asyncio
async def test_console_logs_are_normalized_filterable_and_cursor_based() -> None:
    page = FakePage()
    page.console = FakeConsole(
        messages=[
            AttrConsoleMessage(level="log", text="load log"),
            {
                "level": "warning",
                "text": "slow request",
                "url": "https://example.test/console",
                "line": "9",
                "column": "4",
                "source": "console-api",
            },
            AttrConsoleMessage(level="error", text="action failed", line=12),
        ]
    )
    tab = PageTab(page, FakeContext())

    all_logs = await tab.observation.console_logs(level="all", since=-1, limit=2)
    error_logs = await tab.observation.console_logs(level="error", since=-1, limit=20)
    cursor_logs = await tab.observation.console_logs(level="all", since=1, limit=20)

    assert page.console.started is True
    assert all_logs["available"] is True
    assert all_logs["listening"] is True
    assert all_logs["count"] == 2
    assert all_logs["total"] == 3
    assert all_logs["next_cursor"] == 2
    assert [item["index"] for item in all_logs["logs"]] == [1, 2]
    assert all_logs["logs"][0] == {
        "index": 1,
        "level": "warning",
        "text": "slow request",
        "url": "https://example.test/console",
        "line": 9,
        "column": 4,
        "source": "console-api",
    }
    assert [item["text"] for item in error_logs["logs"]] == ["action failed"]
    assert [item["index"] for item in cursor_logs["logs"]] == [2]


@pytest.mark.asyncio
async def test_console_logs_report_capability_when_unavailable() -> None:
    page = FakePage()
    page.console = None
    unavailable = await PageTab(page, FakeContext()).observation.console_logs()

    page.console = FakeConsole(start_raises=True)
    start_failed = await PageTab(page, FakeContext()).observation.console_logs()

    assert unavailable == {
        "available": False,
        "listening": False,
        "count": 0,
        "total": 0,
        "next_cursor": -1,
        "logs": [],
    }
    assert start_failed["available"] is True
    assert start_failed["listening"] is False
    assert start_failed["logs"] == []


@pytest.mark.asyncio
async def test_observe_includes_bounded_console_summary() -> None:
    class ObservablePage(FakePage):
        def run_js(self, script: str, **kwargs):
            self.calls.append(("run_js", script[:40], kwargs))
            return {
                "url": self.url,
                "title": "Observable",
                "ready_state": "complete",
                "counts": {"buttons": 1},
                "text_samples": ["Ready"],
                "active_element": None,
            }

    page = ObservablePage()
    page.console = FakeConsole(
        messages=[
            AttrConsoleMessage(level="warning", text="first warning"),
            AttrConsoleMessage(level="error", text="first error"),
            AttrConsoleMessage(level="log", text="plain log"),
        ]
    )
    tab = PageTab(page, FakeContext())

    observation = await tab.observation.observe()

    assert observation["console"]["available"] is True
    assert observation["console"]["error_count"] == 1
    assert observation["console"]["warning_count"] == 1
    assert observation["console"]["next_cursor"] == 2
    assert [item["text"] for item in observation["console"]["recent"]] == [
        "first warning",
        "first error",
        "plain log",
    ]


@pytest.mark.asyncio
async def test_observable_helpers_raise_on_invalid_page_results() -> None:
    class InvalidScriptPage(FakePage):
        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode

        def run_js(self, script: str, **kwargs):
            self.calls.append(("run_js", script[:40], kwargs))
            if self.mode == "raise":
                raise RuntimeError("script failed")
            return "not structured"

    with pytest.raises(RuntimeError, match="page snapshot script returned"):
        await PageTab(
            InvalidScriptPage("invalid"), FakeContext()
        ).observation.snapshot()

    with pytest.raises(RuntimeError, match="page observe script returned"):
        await PageTab(InvalidScriptPage("invalid"), FakeContext()).observation.observe()

    with pytest.raises(RuntimeError, match="script failed"):
        await PageTab(InvalidScriptPage("raise"), FakeContext()).observation.evaluate(
            "return 1;"
        )


@pytest.mark.asyncio
async def test_wait_until_conditions_cover_fallback_and_timeout_edges() -> None:
    page = FakePage(
        FakeElement(tag="button", text="Save", attrs={"data-state": "ready"})
    )
    tab = PageTab(page, FakeContext())

    present = await tab.waits.until(
        condition="present", selector="tag:button", timeout=0
    )
    visible = await tab.waits.until(
        condition="visible", selector="tag:button", timeout=0
    )
    hidden = await PageTab(FakePage(element=None), FakeContext()).waits.until(
        condition="hidden",
        selector="tag:missing",
        timeout=0,
    )
    detached = await PageTab(FakePage(element=None), FakeContext()).waits.until(
        condition="detached",
        selector="tag:missing",
        timeout=0,
    )

    assert present["state"]["exists"] is True
    assert visible["state"]["visible"] is True
    assert hidden["matched"] is True
    assert detached["matched"] is True

    property_wait = await tab.waits.until(
        condition="property_nonempty",
        selector="tag:button",
        name="value",
        timeout=0,
    )
    attribute_wait = await tab.waits.until(
        condition="attribute_equals",
        selector="tag:button",
        name="data-state",
        value="ready",
        timeout=0,
    )
    assert property_wait["state"]["nonempty"] is True
    assert attribute_wait["state"]["value_length"] == 5

    class SelectorJsFailPage(FakePage):
        def run_js(self, script: str, **kwargs):
            self.calls.append(("run_js", script[:40], kwargs))
            raise RuntimeError("selector js failed")

    fallback_visible = await PageTab(
        SelectorJsFailPage(FakeElement(tag="button", text="Save")),
        FakeContext(),
    ).waits.until(condition="visible", selector="#save", timeout=0)
    assert fallback_visible["state"]["visible"] is True

    with pytest.raises(TimeoutError):
        await PageTab(
            FakePage(FakeElement(tag="button", attrs={"disabled": ""})),
            FakeContext(),
        ).waits.until(condition="clickable", selector="tag:button", timeout=0)

    class EleRaisingPage(FakePage):
        def ele(self, selector: str, **_kwargs):
            self.calls.append(("ele", selector))
            raise RuntimeError("element lookup failed")

    with pytest.raises(TimeoutError):
        await PageTab(EleRaisingPage(), FakeContext()).waits.until(
            condition="text_contains",
            selector="#missing",
            value="never",
            timeout=0,
        )

    with pytest.raises(ValueError, match="selector is required"):
        await tab.waits.until(condition="visible", timeout=0)

    with pytest.raises(TimeoutError, match="was not met"):
        await PageTab(FakePage(element=None), FakeContext()).waits.until(
            condition="visible",
            selector="tag:missing",
            timeout=0,
        )

    class TextAndHtmlRaisingPage(FakePage):
        @property
        def text(self):
            raise RuntimeError("text detached")

        @text.setter
        def text(self, _value):
            pass

        @property
        def html(self):
            raise RuntimeError("html detached")

        @html.setter
        def html(self, _value):
            pass

    with pytest.raises(TimeoutError):
        await PageTab(TextAndHtmlRaisingPage(), FakeContext()).waits.until(
            condition="text_contains",
            value="never",
            timeout=0,
        )


def test_tab_identity_summary_handles_detached_properties() -> None:
    tab = PageTab(RaisingIdentityPage(), FakeContext(), mcp_tab_id="t0")

    assert tab.native_tab_id == ""
    assert tab.title == ""
    assert tab.summary(active=True)["native_id"] == ""


@pytest.mark.asyncio
async def test_missing_element_paths_raise() -> None:
    page = FakePage(element=None)
    page.wait = FakeWait(loaded=False)
    tab = PageTab(page, FakeContext())

    with pytest.raises(Exception, match="Element not found"):
        await tab.elements.click("#missing")
    with pytest.raises(Exception, match="Element not found"):
        await tab.elements.input("#missing", "text")
    with pytest.raises(Exception, match="Element not found"):
        await tab.elements.find("#missing")


@pytest.mark.asyncio
async def test_element_wait_success_but_lookup_missing_paths_raise() -> None:
    """wait success must not hide a second failed element lookup."""

    page = FakePage(element=None)
    page.wait = FakeWait(loaded=True)
    tab = PageTab(page, FakeContext())

    for call in (
        tab.elements.click("#missing"),
        tab.elements.find("#missing"),
        tab.elements.text("#missing"),
        tab.elements.attribute("#missing", "id"),
        tab.elements.property("#missing", "value"),
        tab.elements.html("#missing"),
    ):
        with pytest.raises(Exception, match="Element not found"):
            await call


@pytest.mark.asyncio
async def test_type_text_stops_when_wait_times_out() -> None:
    element = FakeElement()
    page = FakePage(element)
    page.wait = FakeWait(loaded=False)
    tab = PageTab(page, FakeContext())

    with pytest.raises(Exception, match="Element not found"):
        await tab.elements.type("#delayed", "should-not-type", timeout=1)

    assert element.inputs == []
    assert ("ele", "#delayed") not in page.calls


@pytest.mark.asyncio
async def test_page_text_falls_back_to_body_when_text_property_is_absent() -> None:
    page = FakePage()
    del page.text
    tab = PageTab(page, FakeContext())

    assert await tab.elements.text() == "Ada"
    assert ("ele", "tag:body") in page.calls

    empty_page = FakePage(element=None)
    del empty_page.text
    empty_tab = PageTab(empty_page, FakeContext())

    assert await empty_tab.elements.text() == ""


@pytest.mark.asyncio
async def test_screenshot_inline_path_and_errors_are_explicit(tmp_path) -> None:
    tab = PageTab(FakePage(), FakeContext())

    assert await tab.page_ops.screenshot() == base64.b64encode(b"inline-png").decode()

    output = tmp_path / "screen.png"
    assert await tab.page_ops.screenshot(path=str(output), full_page=True) == str(
        output
    )
    assert output.read_bytes() == b"path-png"

    class UnsupportedScreenshotPage(FakePage):
        def get_screenshot(self, **_kwargs):
            return None

    with pytest.raises(TypeError, match="unsupported type: NoneType"):
        await PageTab(UnsupportedScreenshotPage(), FakeContext()).page_ops.screenshot()

    class BrokenScreenshotPage(FakePage):
        def get_screenshot(self, **_kwargs):
            raise RuntimeError("screenshot failed")

    with pytest.raises(RuntimeError, match="screenshot failed"):
        await PageTab(BrokenScreenshotPage(), FakeContext()).page_ops.screenshot()


@pytest.mark.asyncio
async def test_browser_environment_controls_use_public_drissionpage_apis() -> None:
    page = FakePage()
    tab = PageTab(page, FakeContext())

    assert await tab.page_ops.set_headers(
        {"X-MCP-Session": "callback-value", "Accept-Language": "zh-CN"}
    ) == {
        "count": 2,
        "headers": {
            "X-MCP-Session": "<redacted>",
            "Accept-Language": "<redacted>",
        },
        "set": True,
    }
    assert page.set.headers_calls == [
        {"X-MCP-Session": "callback-value", "Accept-Language": "zh-CN"}
    ]

    assert await tab.page_ops.set_user_agent("MCPBrowser/0.7.6", "Linux") == {
        "previous_user_agent": "FakeBrowser/1.0",
        "user_agent": "MCPBrowser/0.7.6",
        "platform": "Linux",
        "set": True,
    }
    assert page.set.user_agent_calls == [("MCPBrowser/0.7.6", "Linux")]

    assert await tab.page_ops.clear_cache() == {"cleared": True}
    assert page.cache_clear_calls == [
        {
            "session_storage": False,
            "local_storage": False,
            "cache": True,
            "cookies": False,
        }
    ]

    assert await tab.network.set_blocked_urls(["*.png", "*analytics*"]) == {
        "count": 2,
        "urls": ["*.png", "*analytics*"],
        "set": True,
    }
    assert page.set.blocked_urls_calls == [["*.png", "*analytics*"]]
    assert await tab.network.set_blocked_urls([]) == {
        "count": 0,
        "urls": [],
        "set": True,
    }
    assert page.set.blocked_urls_calls[-1] == []


@pytest.mark.asyncio
async def test_browser_environment_control_failures_are_reraised() -> None:
    class BrokenEnvironmentSet(FakeSet):
        def headers(self, headers) -> None:
            raise RuntimeError("headers failed")

        def user_agent(self, user_agent, platform=None) -> None:
            raise RuntimeError("user agent failed")

        def blocked_urls(self, urls) -> None:
            raise RuntimeError("blocked urls failed")

    page = FakePage()
    page.set = BrokenEnvironmentSet()
    tab = PageTab(page, FakeContext())

    with pytest.raises(RuntimeError, match="headers failed"):
        await tab.page_ops.set_headers({"X-Test": "value"})
    with pytest.raises(RuntimeError, match="user agent failed"):
        await tab.page_ops.set_user_agent("MCPBrowser/0.7.6")
    with pytest.raises(RuntimeError, match="blocked urls failed"):
        await tab.network.set_blocked_urls(["*.png"])

    class BrokenCachePage(FakePage):
        def clear_cache(self, **kwargs) -> None:
            raise RuntimeError("cache failed")

    with pytest.raises(RuntimeError, match="cache failed"):
        await PageTab(BrokenCachePage(), FakeContext()).page_ops.clear_cache()


@pytest.mark.asyncio
async def test_wait_close_url_and_connection_helpers() -> None:
    page = FakePage()
    browser = FakeBrowser()
    tab = PageTab(page, FakeContext(browser))
    tab._url = "https://cached.test"

    assert await tab.waits.element("#ready") is True

    page.wait = FakeWaitFallback()
    assert await tab.waits.element("#ready", timeout=2) is True
    assert page.wait.calls == [("css:#ready", 2, True)]

    page.wait = FakeWait(fail=True)
    assert await tab.waits.element("#ready") is False

    page.url = "https://example.test/done"
    assert await tab.waits.url("done") is True
    assert await tab.waits.url("never", timeout=0) is False

    assert tab.is_connected() is True
    await tab.close()
    assert browser.closed_tabs == ["tab-1"]

    fallback_page = FakePage()
    fallback_page.tab_id = ""
    fallback_tab = PageTab(fallback_page, FakeContext())
    await fallback_tab.close()
    assert fallback_page.closed is True

    disconnected_tab = PageTab(RaisingUrlPage(), FakeContext())
    disconnected_tab._url = "https://cached.test"
    assert disconnected_tab.url == "https://cached.test"
    assert disconnected_tab.is_connected() is False


@pytest.mark.asyncio
async def test_wait_for_url_polls_and_handles_polling_errors(monkeypatch) -> None:
    page = FakePage()
    page.url = "https://example.test/loading"
    tab = PageTab(page, FakeContext())
    sleeps = []

    async def finish_after_first_poll(seconds: float) -> None:
        sleeps.append(seconds)
        page.url = "https://example.test/done"

    monkeypatch.setattr("drissionpage_mcp.tab.asyncio.sleep", finish_after_first_poll)

    assert await tab.waits.url("done", timeout=1) is True
    assert sleeps == [0.5]

    async def fail_sleep(_seconds: float) -> None:
        raise RuntimeError("clock failed")

    page.url = "https://example.test/loading"
    monkeypatch.setattr("drissionpage_mcp.tab.asyncio.sleep", fail_sleep)

    assert await tab.waits.url("done", timeout=1) is False


@pytest.mark.asyncio
async def test_navigation_failure_is_reraised() -> None:
    class FailedNavigationPage(FakePage):
        def get(self, url: str):
            return False

    tab = PageTab(FailedNavigationPage(), FakeContext())

    with pytest.raises(RuntimeError, match="Navigation failed"):
        await tab.navigation.navigate("https://bad.test")


@pytest.mark.asyncio
async def test_page_action_failures_are_reraised() -> None:
    class BrokenActions(FakeActions):
        def click(self, point):
            raise RuntimeError(f"cannot click {point}")

    class BrokenWindow(FakeWindow):
        def size(self, width: int, height: int) -> None:
            raise RuntimeError(f"cannot resize {width}x{height}")

    class BrokenSet(FakeSet):
        def __init__(self) -> None:
            self.window = BrokenWindow()

    class BrokenPage(FakePage):
        def __init__(self, broken_action: str) -> None:
            super().__init__()
            self.broken_action = broken_action
            self.actions = BrokenActions()
            self.set = BrokenSet()

        def back(self) -> None:
            if self.broken_action == "back":
                raise RuntimeError("back failed")
            super().back()

        def forward(self) -> None:
            if self.broken_action == "forward":
                raise RuntimeError("forward failed")
            super().forward()

        def refresh(self) -> None:
            if self.broken_action == "refresh":
                raise RuntimeError("refresh failed")
            super().refresh()

        def run_cdp(self, method: str, **params):
            if self.broken_action == "click":
                raise RuntimeError("click failed")
            return super().run_cdp(method, **params)

    for action, call in (
        ("back", lambda tab: tab.navigation.back()),
        ("forward", lambda tab: tab.navigation.forward()),
        ("refresh", lambda tab: tab.navigation.refresh()),
        ("click", lambda tab: tab.pointer.click_at(1, 2)),
        ("resize", lambda tab: tab.page_ops.resize(800, 600)),
    ):
        tab = PageTab(BrokenPage(action), FakeContext())
        with pytest.raises(RuntimeError):
            await call(tab)


@pytest.mark.asyncio
async def test_post_action_stabilization_prefers_doc_loaded() -> None:
    class WaitWithDocLoaded(FakeWait):
        def __init__(self) -> None:
            super().__init__()
            self.doc_loaded_calls = []

        def doc_loaded(self, **kwargs):
            self.doc_loaded_calls.append(kwargs)
            return True

    page = FakePage()
    page.wait = WaitWithDocLoaded()
    tab = PageTab(page, FakeContext())

    await tab.navigation.navigate("https://example.test")
    await tab.pointer.click_at(1, 2)

    assert page.wait.doc_loaded_calls[0] == {"timeout": 5.0, "raise_err": False}
    assert page.wait.doc_loaded_calls[1] == {"timeout": 1.0, "raise_err": False}


@pytest.mark.asyncio
async def test_post_action_stabilization_tries_compatible_doc_loaded_signatures() -> (
    None
):
    class WaitWithStrictDocLoaded(FakeWait):
        def __init__(self) -> None:
            super().__init__()
            self.doc_loaded_calls = []

        def doc_loaded(self, **kwargs):
            self.doc_loaded_calls.append(kwargs)
            if "raise_err" in kwargs or "timeout" in kwargs:
                raise TypeError("unsupported keyword")
            return True

    page = FakePage()
    page.wait = WaitWithStrictDocLoaded()
    tab = PageTab(page, FakeContext())

    await tab.navigation.refresh()

    assert page.wait.doc_loaded_calls == [
        {"timeout": 5.0, "raise_err": False},
        {"timeout": 5.0},
        {},
    ]


@pytest.mark.asyncio
async def test_post_action_stabilization_falls_back_when_doc_loaded_fails(
    monkeypatch,
) -> None:
    class WaitWithFailingDocLoaded(FakeWait):
        def doc_loaded(self, **_kwargs):
            raise RuntimeError("load waiter disconnected")

    sleeps = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    page = FakePage()
    page.wait = WaitWithFailingDocLoaded()
    tab = PageTab(page, FakeContext())
    monkeypatch.setattr("drissionpage_mcp.tab.asyncio.sleep", fake_sleep)

    await tab.pointer.click_at(1, 2)

    assert sleeps == [0.02]


@pytest.mark.asyncio
async def test_post_action_stabilization_falls_back_to_bounded_sleep(
    monkeypatch,
) -> None:
    sleeps = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("drissionpage_mcp.tab.asyncio.sleep", fake_sleep)
    page = FakePage()
    page.wait = object()
    tab = PageTab(page, FakeContext())

    await tab.navigation.back()

    assert sleeps == [0.05]


@pytest.mark.asyncio
async def test_close_reports_browser_close_errors_without_raising() -> None:
    class BrokenBrowser(FakeBrowser):
        def close_tabs(self, tab_id: str) -> None:
            raise RuntimeError(f"cannot close {tab_id}")

    tab = PageTab(FakePage(), FakeContext(BrokenBrowser()))

    assert await tab.close() is False


class RecordingActions(FakeActions):
    def __init__(self) -> None:
        super().__init__()
        self.typed = None

    def type(self, keys: str, *, interval: float = 0) -> None:
        self.typed = (keys, interval)


class RecordingScroll:
    def __init__(self) -> None:
        self.calls = []

    def down(self, pixels: int) -> None:
        self.calls.append(("down", pixels))

    def up(self, pixels: int) -> None:
        self.calls.append(("up", pixels))

    def left(self, pixels: int) -> None:
        self.calls.append(("left", pixels))

    def right(self, pixels: int) -> None:
        self.calls.append(("right", pixels))

    def to_top(self) -> None:
        self.calls.append(("top",))

    def to_bottom(self) -> None:
        self.calls.append(("bottom",))

    def to_half(self) -> None:
        self.calls.append(("half",))

    def to_location(self, x: int, y: int) -> None:
        self.calls.append(("position", x, y))


class RecordingElementScroll:
    def __init__(self) -> None:
        self.center = None

    def to_see(self, *, center: bool = True) -> None:
        self.center = center


class RecordingSelect:
    def __init__(self) -> None:
        self.calls = []

    def by_value(self, value: str, *, timeout: int = 10) -> None:
        self.calls.append(("value", value, timeout))

    def by_text(self, value: str, *, timeout: int = 10) -> None:
        self.calls.append(("text", value, timeout))

    def by_index(self, value: int, *, timeout: int = 10) -> None:
        self.calls.append(("index", value, timeout))


class InteractionElement(FakeElement):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.scroll = RecordingElementScroll()
        self.select = RecordingSelect()
        self.hover_calls = []
        self.check_calls = []
        self.shadow_root = None

    def hover(self, *, offset_x=None, offset_y=None) -> None:
        self.hover_calls.append((offset_x, offset_y))

    def check(self, *, uncheck: bool = False, by_js: bool = False) -> None:
        self.check_calls.append((uncheck, by_js))


@pytest.mark.asyncio
async def test_page_and_element_interaction_tools_cover_success_branches() -> None:
    element = InteractionElement(attrs={"id": "file", "disabled": None})
    page = FakePage(element)
    page.actions = RecordingActions()
    page.scroll = RecordingScroll()
    tab = PageTab(page, FakeContext())

    for direction in ("down", "up", "left", "right", "top", "bottom", "half"):
        result = await tab.interaction.scroll_page(direction=direction, pixels=17)
        assert result["direction"] == direction
    positioned = await tab.interaction.scroll_page(direction="position", x=11, y=22)
    assert positioned["x"] == 11
    assert page.scroll.calls == [
        ("down", 17),
        ("up", 17),
        ("left", 17),
        ("right", 17),
        ("top",),
        ("bottom",),
        ("half",),
        ("position", 11, 22),
    ]

    scrolled = await tab.interaction.scroll_element_into_view("#file", center=False)
    hovered = await tab.interaction.hover_element("#file", offset_x=3, offset_y=4)
    keyboard = await tab.interaction.keyboard_press("Hello", interval=0.01)
    uploaded = await tab.elements.upload("#file", ["/tmp/a.txt", "/var/tmp/b.bin"])
    await tab.interaction.select_element("#file", value="admin", by="value")
    await tab.interaction.select_element("#file", value="Admin", by="text")
    await tab.interaction.select_element("#file", value="2", by="index")
    checked = await tab.interaction.check_element("#file", checked=False, by_js=True)

    assert scrolled["center"] is False
    assert element.scroll.center is False
    assert hovered["offset_x"] == 3
    assert element.hover_calls == [(3, 4)]
    assert keyboard == {
        "keys": {"provided": True, "length": 5, "redacted": True},
        "interval": 0.01,
        "url": "about:blank",
    }
    assert page.actions.typed == ("Hello", 0.01)
    assert uploaded["file_count"] == 2
    assert uploaded["filenames"] == ["a.txt", "b.bin"]
    assert element.inputs == [["/tmp/a.txt", "/var/tmp/b.bin"]]
    assert element.select.calls == [
        ("value", "admin", 10),
        ("text", "Admin", 10),
        ("index", 2, 10),
    ]
    assert checked["checked"] is False
    assert element.check_calls == [(True, True)]


@pytest.mark.asyncio
async def test_page_and_element_interaction_tools_reraise_failures() -> None:
    tab = PageTab(FakePage(), FakeContext())

    with pytest.raises(RuntimeError, match="scroll API"):
        await tab.interaction.scroll_page()

    page = FakePage(InteractionElement())
    page.scroll = RecordingScroll()
    tab = PageTab(page, FakeContext())

    with pytest.raises(ValueError, match="Unsupported scroll direction"):
        await tab.interaction.scroll_page(direction="diagonal")
    with pytest.raises(ValueError, match="Unsupported select mode"):
        await tab.interaction.select_element("#name", value="x", by="label")

    class FailingInputElement(InteractionElement):
        def input(self, text):
            raise RuntimeError(f"cannot upload {text}")

    class FailingHoverElement(InteractionElement):
        def hover(self, *, offset_x=None, offset_y=None) -> None:
            raise RuntimeError("hover failed")

    class FailingCheckElement(InteractionElement):
        def check(self, *, uncheck: bool = False, by_js: bool = False) -> None:
            raise RuntimeError("check failed")

    class FailingScrollElement(InteractionElement):
        def __init__(self) -> None:
            super().__init__()
            self.scroll = SimpleNamespace(
                to_see=lambda **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("scroll failed")
                )
            )

    class FailingActionsPage(FakePage):
        def __init__(self) -> None:
            super().__init__(InteractionElement())
            self.actions = SimpleNamespace(
                type=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("type failed")
                )
            )

    for element, call in (
        (
            FailingInputElement(),
            lambda failing_tab: failing_tab.elements.upload("#x", ["a"]),
        ),
        (
            FailingHoverElement(),
            lambda failing_tab: failing_tab.interaction.hover_element("#x"),
        ),
        (
            FailingCheckElement(),
            lambda failing_tab: failing_tab.interaction.check_element("#x"),
        ),
        (
            FailingScrollElement(),
            lambda failing_tab: failing_tab.interaction.scroll_element_into_view("#x"),
        ),
    ):
        with pytest.raises(RuntimeError):
            await call(PageTab(FakePage(element), FakeContext()))

    with pytest.raises(RuntimeError, match="type failed"):
        await PageTab(FailingActionsPage(), FakeContext()).interaction.keyboard_press(
            "x"
        )


class FakeFrame:
    def __init__(
        self,
        *,
        frame_id: str = "frame1",
        frame_name: str = "main",
        text: str = "Frame body text",
        target=None,
        body=None,
        fail_body: bool = False,
        fail_eles: bool = False,
    ) -> None:
        self.frame_ele = FakeElement(
            tag="iframe",
            text="",
            attrs={"id": frame_id, "name": frame_name},
        )
        self.title = "Frame Title"
        self.url = "https://example.test/frame"
        self.text = text
        self.target = (
            target
            if target is not None
            else FakeElement(
                tag="button",
                text="Inside",
                html="<button id='inside'>Inside</button>",
                attrs={"id": "inside"},
            )
        )
        self.body = (
            body
            if body is not None
            else FakeElement(
                tag="body",
                text="Fallback body",
                html="<body>Fallback body</body>",
            )
        )
        self.fail_body = fail_body
        self.fail_eles = fail_eles

    def run_js(self, *_args, **_kwargs):
        return {}

    def ele(self, selector: str, **_kwargs):
        if self.fail_body and selector == "tag:body":
            raise RuntimeError("body unavailable")
        if selector == "tag:body":
            return self.body
        if selector in {"css:#inside", "#inside"}:
            return self.target
        return None

    def eles(self, selector: str, **_kwargs):
        if self.fail_eles:
            raise RuntimeError("frame lookup failed")
        if "h1" in selector:
            return [
                FakeElement(
                    tag="h1",
                    text="Frame Heading",
                    html="<h1 id='fh'>Frame Heading</h1>",
                    attrs={"id": "fh"},
                )
            ]
        if selector == "css:a":
            return [
                FakeElement(
                    tag="a",
                    text="Frame Link",
                    html="<a id='fl'>Frame Link</a>",
                    attrs={"id": "fl", "href": "/frame"},
                )
            ]
        return []


class FramePage(FakePage):
    def __init__(self, frames) -> None:
        super().__init__()
        self.frames = frames

    def get_frames(self, **_kwargs):
        return self.frames

    def get_frame(self, selector, **_kwargs):
        if selector in {"css:#frame1", "#frame1", "raw-ok"}:
            return self.frames[0] if self.frames else None
        if selector == "raw-bad":
            raise RuntimeError("raw frame detached")
        return None


@pytest.mark.asyncio
async def test_frame_tools_cover_resolution_snapshot_and_find_paths() -> None:
    frame = FakeFrame(text="")
    page = FramePage([frame])
    tab = PageTab(page, FakeContext())

    listed = await tab.frames.list_frames(limit=1)
    snapshot = await tab.frames.snapshot(frame_index=0, include_html=True)
    found = await tab.frames.find(selector="#inside", frame_selector="#frame1")

    assert listed["frames"][0]["selector"] == "#frame1"
    assert snapshot["frame"]["id"] == "frame1"
    assert snapshot["text_excerpt"] == "Fallback body"
    assert snapshot["counts"]["headings"] == 1
    assert found["frame"]["index"] == 0
    assert found["element"]["selector"] == "#inside"

    with pytest.raises(Exception, match="Element not found"):
        await tab.frames.find(selector="#missing", frame_index=0)


@pytest.mark.asyncio
async def test_frame_tools_cover_fallbacks_and_error_paths() -> None:
    assert await PageTab(FakePage(), FakeContext()).frames.list_frames() == {
        "count": 0,
        "returned": 0,
        "limit": 20,
        "frames": [],
    }

    class NoKeywordGetFramesPage(FramePage):
        def get_frames(self, **kwargs):
            if kwargs:
                raise TypeError("old signature")
            return self.frames

    old_signature = await PageTab(
        NoKeywordGetFramesPage([FakeFrame()]),
        FakeContext(),
    ).frames.list_frames()
    assert old_signature["count"] == 1

    raw_page = FramePage(["raw-ok", "raw-bad"])
    raw_page.frames = [FakeFrame()]
    raw_page.get_frames = lambda **_kwargs: ["raw-ok", "raw-bad"]
    raw_list = await PageTab(raw_page, FakeContext()).frames.list_frames()
    assert raw_list["count"] == 1

    class BrokenFramesPage(FakePage):
        def get_frames(self, **_kwargs):
            raise RuntimeError("frame list failed")

    with pytest.raises(RuntimeError, match="frame list failed"):
        await PageTab(BrokenFramesPage(), FakeContext()).frames.list_frames()

    with pytest.raises(Exception, match="Frames are not supported"):
        await PageTab(FakePage(), FakeContext()).frames.snapshot(frame_selector="#f")

    with pytest.raises(Exception, match="Frame not found"):
        await PageTab(FramePage([FakeFrame()]), FakeContext()).frames.snapshot(
            frame_selector="#missing"
        )

    with pytest.raises(Exception, match="Frame index not found"):
        await PageTab(FramePage([]), FakeContext()).frames.snapshot(frame_index=1)

    no_body_frame = FakeFrame(text="", fail_body=True, fail_eles=True)
    no_body_snapshot = await PageTab(
        FramePage([no_body_frame]),
        FakeContext(),
    ).frames.snapshot(frame_index=0)
    assert no_body_snapshot["text_excerpt"] == ""
    assert no_body_snapshot["counts"]["headings"] == 0


class FakeShadowRoot:
    def __init__(self, *, fail_many: bool = False) -> None:
        self.fail_many = fail_many
        self.element = FakeElement(
            tag="span",
            text="Shadow Item",
            html="<span id='shadow-item'>Shadow Item</span>",
            attrs={"id": "shadow-item"},
        )

    def ele(self, selector: str, **_kwargs):
        return self.element if selector == "css:.item" else None

    def eles(self, selector: str, **_kwargs):
        if self.fail_many:
            raise RuntimeError("shadow list failed")
        return [self.element] if selector == "css:.item" else []


@pytest.mark.asyncio
async def test_shadow_tools_cover_success_and_failure_paths() -> None:
    host = InteractionElement(attrs={"id": "host"})
    host.shadow_root = FakeShadowRoot()
    tab = PageTab(FakePage(host), FakeContext())

    one = await tab.frames.shadow_find(host_selector="#host", selector=".item")
    many = await tab.frames.shadow_find_all(
        host_selector="#host",
        selector=".item",
        limit=1,
        include_html=True,
    )

    assert one["host"]["locator"] == "css:#host"
    assert one["element"]["text"] == "Shadow Item"
    assert many["count"] == 1
    assert many["elements"][0]["html"] == "<span id='shadow-item'>Shadow Item</span>"

    with pytest.raises(Exception, match="Element not found"):
        await tab.frames.shadow_find(host_selector="#host", selector=".missing")

    no_root = InteractionElement(attrs={"id": "host"})
    with pytest.raises(Exception, match="Shadow root not found"):
        await PageTab(FakePage(no_root), FakeContext()).frames.shadow_find(
            host_selector="#host",
            selector=".item",
        )

    host_with_bad_root = InteractionElement(attrs={"id": "host"})
    host_with_bad_root.shadow_root = FakeShadowRoot(fail_many=True)
    with pytest.raises(RuntimeError, match="shadow list failed"):
        await PageTab(
            FakePage(host_with_bad_root), FakeContext()
        ).frames.shadow_find_all(
            host_selector="#host",
            selector=".item",
        )


class ActiveContext(FakeContext):
    def is_active(self) -> bool:
        return True


class CookieStoragePage(FakePage):
    def __init__(self) -> None:
        super().__init__()
        self.cookie_payload = {"sid": "secret"}
        self.storage_payload = {"token": "secret", "empty": None}
        self.storage_scripts = []

    def cookies(self, **_kwargs):
        return self.cookie_payload

    def run_js(self, script: str, **kwargs):
        self.calls.append(("run_js", script[:40], kwargs))
        if "localStorage" in script or "sessionStorage" in script:
            self.storage_scripts.append(script)
            if "return items" in script:
                return self.storage_payload
            return True
        return super().run_js(script, **kwargs)


@pytest.mark.asyncio
async def test_cookie_storage_and_session_state_paths_are_normalized() -> None:
    page = CookieStoragePage()
    tab = PageTab(page, ActiveContext())

    redacted = await tab.storage.cookies_get(include_values=False)
    assert redacted["cookies"] == [
        {
            "name": "sid",
            "value": "<redacted>",
            "domain": "",
            "path": "",
            "expires": None,
            "secure": False,
            "http_only": False,
        }
    ]

    page.cookie_payload = [
        SimpleNamespace(
            name="token",
            value=None,
            domain="example.test",
            path="/",
            expires=123,
            secure=True,
            httpOnly=True,
        )
    ]
    full_cookie = await tab.storage.cookies_get(
        all_domains=True, all_info=True, include_values=True
    )
    assert full_cookie["cookies"][0]["value"] == ""
    assert full_cookie["cookies"][0]["http_only"] is True

    page.cookie_payload = object()
    assert (await tab.storage.cookies_get())["cookies"] == []

    storage = await tab.storage.get(area="local")
    assert storage["include_values"] is False
    assert storage["items"] == {"token": "<redacted>", "empty": ""}
    assert await tab.storage.set(area="session", key="mode", value="test") == {
        "area": "session",
        "key": "mode",
        "set": True,
    }
    assert await tab.storage.clear(area="local", key="token") == {
        "area": "local",
        "key": "token",
        "cleared": True,
    }
    assert await tab.storage.clear(area="session") == {
        "area": "session",
        "key": "",
        "cleared": True,
    }

    page.cookie_payload = {"sid": "secret"}
    session = tab.storage.session_state()
    assert session["browser_active"] is True
    assert session["cookies"]["names"] == ["sid"]
    assert session["storage"]["local"]["keys"] == ["empty", "token"]


@pytest.mark.asyncio
async def test_cookie_write_paths_map_fields_and_echo_values() -> None:
    page = CookieStoragePage()
    tab = PageTab(page, ActiveContext())
    cookies = [
        {
            "name": "sid",
            "value": "secret-value",
            "url": "https://example.test/login",
            "domain": "example.test",
            "path": "/",
            "expires": 1893456000.0,
            "secure": True,
            "http_only": True,
            "same_site": "Lax",
            "priority": "High",
            "source_scheme": "Secure",
        },
        {"name": "theme", "value": "dark"},
    ]

    result = await tab.storage.cookies_set(cookies=cookies)

    assert page.set.cookies.set_calls == [
        [
            {
                "name": "sid",
                "value": "secret-value",
                "url": "https://example.test/login",
                "domain": "example.test",
                "path": "/",
                "expires": 1893456000.0,
                "secure": True,
                "httpOnly": True,
                "sameSite": "Lax",
                "priority": "High",
                "sourceScheme": "Secure",
            },
            {"name": "theme", "value": "dark"},
        ]
    ]
    assert result == {
        "count": 2,
        "set": True,
        "cookies": [
            {**cookies[0], "value": "<redacted>"},
            {**cookies[1], "value": "<redacted>"},
        ],
    }

    deleted = await tab.storage.cookies_delete(
        name="sid",
        url="https://example.test/login",
        domain="example.test",
        path="/",
    )
    assert page.set.cookies.remove_calls == [
        ("sid", "https://example.test/login", "example.test", "/")
    ]
    assert deleted == {
        "name": "sid",
        "url": "https://example.test/login",
        "domain": "example.test",
        "path": "/",
        "deleted": True,
    }

    assert await tab.storage.cookies_clear() == {"cleared": True}
    assert page.set.cookies.clear_calls == 1


@pytest.mark.asyncio
async def test_cookie_and_storage_failures_are_reraised() -> None:
    class BrokenCookiesPage(CookieStoragePage):
        def cookies(self, **_kwargs):
            raise RuntimeError("cookies failed")

    with pytest.raises(RuntimeError, match="cookies failed"):
        await PageTab(BrokenCookiesPage(), FakeContext()).storage.cookies_get()

    page = CookieStoragePage()
    tab = PageTab(page, FakeContext())

    with pytest.raises(ValueError, match="Unsupported storage area"):
        await tab.storage.get(area="bad")
    with pytest.raises(ValueError, match="Unsupported storage area"):
        await tab.storage.set(area="bad", key="x", value="y")
    with pytest.raises(ValueError, match="Unsupported storage area"):
        await tab.storage.clear(area="bad")

    class BrokenCookiesSetter(FakeCookiesSetter):
        def __call__(self, cookies) -> None:
            raise RuntimeError("cookie set failed")

        def remove(self, name, url=None, domain=None, path=None) -> None:
            raise RuntimeError("cookie delete failed")

        def clear(self) -> None:
            raise RuntimeError("cookie clear failed")

    broken_page = CookieStoragePage()
    broken_page.set.cookies = BrokenCookiesSetter()
    broken_tab = PageTab(broken_page, FakeContext())
    with pytest.raises(RuntimeError, match="cookie set failed"):
        await broken_tab.storage.cookies_set(cookies=[{"name": "sid", "value": "x"}])
    with pytest.raises(RuntimeError, match="cookie delete failed"):
        await broken_tab.storage.cookies_delete(name="sid")
    with pytest.raises(RuntimeError, match="cookie clear failed"):
        await broken_tab.storage.cookies_clear()


@pytest.mark.asyncio
async def test_console_helpers_cover_unreadable_and_noniterable_messages() -> None:
    class ConsolePropertyRaisesPage(FakePage):
        @property
        def console(self):
            raise RuntimeError("console detached")

        @console.setter
        def console(self, _value):
            pass

    unavailable = await PageTab(
        ConsolePropertyRaisesPage(), FakeContext()
    ).observation.console_logs()
    assert unavailable["available"] is False
    assert (
        PageTab(
            ConsolePropertyRaisesPage(), FakeContext()
        ).observation._console_summary()["available"]
        is False
    )

    class MessagesRaiseConsole(FakeConsole):
        @property
        def messages(self):
            raise RuntimeError("messages detached")

        @messages.setter
        def messages(self, _value):
            pass

    page = FakePage()
    page.console = MessagesRaiseConsole()
    assert (await PageTab(page, FakeContext()).observation.console_logs())["logs"] == []

    class NonIterableMessagesConsole(FakeConsole):
        def __init__(self) -> None:
            super().__init__(messages=[])
            self.messages = object()

    tab = PageTab(FakePage(), FakeContext())
    tab.page.console = NonIterableMessagesConsole()
    tab.observation._console_log_cache = [
        {
            "index": 0,
            "level": "log",
            "text": "cached",
            "url": "",
            "line": 0,
            "column": 0,
            "source": "",
        }
    ]
    assert (await tab.observation.console_logs())["logs"][0]["text"] == "cached"


@pytest.mark.asyncio
async def test_console_message_normalization_handles_edge_message_shapes() -> None:
    class FieldRaisesMessage:
        @property
        def level(self):
            raise RuntimeError("level unavailable")

        @property
        def text(self):
            raise RuntimeError("text unavailable")

        @property
        def message(self):
            return "fallback message"

    page = FakePage()
    page.console = FakeConsole(
        messages=[
            "plain string",
            {"level": "warn", "message": "warn fallback"},
            {"level": "verbose", "text": "unknown level"},
            FieldRaisesMessage(),
        ]
    )
    tab = PageTab(page, FakeContext())

    logs = (await tab.observation.console_logs(limit=10))["logs"]

    assert [item["text"] for item in logs] == [
        "plain string",
        "warn fallback",
        "unknown level",
        "fallback message",
    ]
    assert [item["level"] for item in logs] == ["log", "warning", "log", "log"]

    tab.observation._console_log_cache = [
        {
            "index": 0,
            "level": "warning",
            "text": "old",
            "url": "",
            "line": 0,
            "column": 0,
            "source": "",
        }
    ]
    tab.observation._merge_console_messages(
        [
            {"level": "error", "text": "new"},
            {"level": "warning", "text": "old"},
        ]
    )
    assert [item["text"] for item in tab.observation._console_log_cache] == [
        "old",
        "new",
    ]


@pytest.mark.asyncio
async def test_wait_condition_edge_paths_are_observable() -> None:
    page = FakePage(element=None)
    tab = PageTab(page, FakeContext())

    empty_text = await tab.waits.until(
        condition="text_contains",
        selector="#missing",
        value="",
        timeout=0,
    )
    assert empty_text["state"]["text"] == ""

    with pytest.raises(TimeoutError):
        await tab.waits.until(condition="stable", selector="#missing", timeout=0)

    with pytest.raises(ValueError, match="Unsupported wait condition"):
        await tab.waits.until(condition="unknown", selector="#missing", timeout=0)

    class SelectorAndElementFailPage(FakePage):
        def run_js(self, script: str, **kwargs):
            raise RuntimeError("selector js failed")

        def ele(self, selector: str, **_kwargs):
            raise RuntimeError("element lookup failed")

    with pytest.raises(TimeoutError):
        await PageTab(SelectorAndElementFailPage(), FakeContext()).waits.until(
            condition="visible",
            selector="#missing",
            timeout=0,
        )

    class AttrRaisesElement(FakeElement):
        def attr(self, attribute: str):
            if attribute in {"disabled", "aria-disabled"}:
                raise RuntimeError("attribute unavailable")
            return super().attr(attribute)

    class JsFailPage(FakePage):
        def run_js(self, script: str, **kwargs):
            raise RuntimeError("selector js failed")

    clickable = await PageTab(
        JsFailPage(AttrRaisesElement(tag="button", text="Save")),
        FakeContext(),
    ).waits.until(condition="clickable", selector="#save", timeout=0)
    assert clickable["matched"] is True


def test_page_tab_exposes_capabilities_without_legacy_domain_methods() -> None:
    """Keep capability boundaries explicit instead of rebuilding PageTab as a facade."""

    tab = PageTab(FakePage(), FakeContext())

    assert tab.elements is not None
    assert tab.frames is not None
    assert tab.interaction is not None
    assert tab.navigation is not None
    assert tab.network is not None
    assert tab.observation is not None
    assert tab.page_ops is not None
    assert tab.pointer is not None
    assert tab.storage is not None
    assert tab.waits is not None

    legacy_methods = {
        "click",
        "console_logs",
        "ensure_console_capture",
        "evaluate_script",
        "extract_links",
        "form_fill_preview",
        "inspect_forms",
        "open_and_snapshot",
        "observe",
        "page_snapshot",
        "resize",
        "screenshot",
        "click_element",
        "find_element",
        "find_elements",
        "get_attribute",
        "get_html",
        "get_property",
        "get_text",
        "go_back",
        "go_forward",
        "hover_element",
        "keyboard_press",
        "list_frames",
        "network_listen_start",
        "network_listen_stop",
        "network_listen_wait",
        "refresh",
        "scroll_element_into_view",
        "scroll_page",
        "select_element",
        "shadow_find",
        "shadow_find_all",
        "storage_clear",
        "storage_get",
        "storage_set",
        "type_text",
        "upload_file",
        "wait_for_element",
        "wait_for_url",
        "wait_until",
    }
    assert legacy_methods.isdisjoint(dir(tab))


class FakeNetworkListener:
    def __init__(
        self,
        *,
        listening: bool = False,
        wait_result=None,
        wait_results=None,
        start_type_error_once: bool = False,
        stop_raises: Exception | None = None,
    ) -> None:
        self.listening = listening
        self.wait_result = wait_result
        self.wait_results = list(wait_results or [])
        self.start_type_error_once = start_type_error_once
        self.stop_raises = stop_raises
        self.start_calls = []
        self.wait_calls = []
        self.stop_calls = 0
        self.clear_calls = 0
        self.pause_calls = []

    def start(self, *args, **kwargs) -> None:
        self.start_calls.append((args, kwargs))
        if self.start_type_error_once and len(self.start_calls) == 1:
            raise TypeError("legacy listener signature")
        self.listening = True

    def wait(self, **kwargs):
        self.wait_calls.append(kwargs)
        if self.wait_results:
            return self.wait_results.pop(0)
        return self.wait_result

    def stop(self) -> None:
        self.stop_calls += 1
        if self.stop_raises is not None:
            raise self.stop_raises
        self.listening = False

    def clear(self) -> None:
        self.clear_calls += 1

    def pause(self, **kwargs) -> None:
        self.pause_calls.append(kwargs)
        self.listening = False


class FakeNetworkPage(FakePage):
    def __init__(self, listener=None) -> None:
        super().__init__()
        self.listen = listener


class FakeRequest:
    def __init__(self) -> None:
        self.headers = {"Authorization": "secret", "Accept": "application/json"}
        self.postData = {"query": "abcdef"}


class FakeResponse:
    def __init__(self) -> None:
        self.status = "201"
        self.mimeType = "application/json"
        self.headers = {"set-cookie": "private", "X-Trace": "visible"}
        self.body = {"token": "abcdef"}


class FakePacket:
    def __init__(self, *, url: str = "https://example.test/api") -> None:
        self.url = url
        self.method = "POST"
        self.resourceType = "XHR"
        self.request = FakeRequest()
        self.response = FakeResponse()
        self.is_failed = False


@pytest.mark.asyncio
async def test_wait_element_handles_structured_targets_without_stale_success() -> None:
    target = SelectorTargetInput(kind="selector", selector="#missing")

    assert await PageTab(FakePage(), FakeContext()).waits.element(target, timeout=0)
    assert not await PageTab(FakePage(element=None), FakeContext()).waits.element(
        target, timeout=0
    )


@pytest.mark.asyncio
async def test_wait_conditions_report_missing_names_and_empty_properties() -> None:
    tab = PageTab(FakePage(FakeElement(attrs={"data-state": ""})), FakeContext())

    with pytest.raises(ValueError, match="name is required"):
        await tab.waits.until(
            condition="attribute_equals",
            selector="#status",
            timeout=0,
        )

    with pytest.raises(TimeoutError):
        await tab.waits.until(
            condition="attribute_nonempty",
            selector="#status",
            name="data-state",
            timeout=0,
        )

    with pytest.raises(TimeoutError):
        await tab.waits.until(
            condition="property_equals",
            selector="#status",
            name="value",
            value="different",
            timeout=0,
        )


@pytest.mark.asyncio
async def test_wait_conditions_resolve_structured_text_and_state_targets() -> None:
    class States:
        is_displayed = True
        is_enabled = False

    element = FakeElement(tag="button", text="Locked")
    element.states = States()
    tab = PageTab(FakePage(element), FakeContext())
    target = SelectorTargetInput(kind="selector", selector="#locked")

    text_match = await tab.waits.until(
        condition="text_matches",
        selector=target,
        value="Lock.*",
        timeout=0,
    )
    visible = await tab.waits.until(condition="visible", selector=target, timeout=0)

    assert text_match["state"] == {"text": "Locked"}
    assert visible["state"] == {
        "exists": True,
        "visible": True,
        "disabled": True,
        "tag": "button",
        "text": "Locked",
        "signature": "button|Locked|True|True",
    }


@pytest.mark.asyncio
async def test_wait_until_retries_transient_resolver_failures_without_sleep(
    monkeypatch,
) -> None:
    tab = PageTab(FakePage(element=None), FakeContext())
    states = iter([
        (False, {"exists": False, "text": ""}),
        (True, {"exists": True, "text": "ready"}),
    ])

    async def condition_matches(**_kwargs):
        return next(states)

    monkeypatch.setattr(tab.waits, "_condition_matches", condition_matches)

    result = await tab.waits.until(
        condition="present",
        selector="#later",
        timeout=1,
        interval=0.01,
    )

    assert result["matched"] is True
    assert result["state"]["text"] == "ready"


@pytest.mark.asyncio
async def test_network_start_records_filters_and_cleans_existing_listener() -> None:
    listener = FakeNetworkListener(listening=True)
    tab = PageTab(FakeNetworkPage(listener), FakeContext(), mcp_tab_id="mcp-tab")

    result = await tab.network.start(
        targets=["/api", "/graphql"],
        is_regex=True,
        method="POST",
        resource_type="XHR",
    )

    assert listener.stop_calls == 1
    assert listener.start_calls[-1] == (
        (),
        {
            "targets": ["/api", "/graphql"],
            "is_regex": True,
            "method": "POST",
            "res_type": "XHR",
        },
    )
    assert result["listening"] is True
    assert result["filters"] == {
        "targets": ["/api", "/graphql"],
        "is_regex": True,
        "method": "POST",
        "resource_type": "XHR",
    }
    assert result["tab_id"] == "mcp-tab"
    assert result["cleared"] is True
    assert isinstance(result["listener_token"], str)
    assert result["state"] == "listening"
    assert result["consumed_count"] == 0
    assert result["next_cursor"] == 0


@pytest.mark.asyncio
async def test_network_listener_token_tracks_consumption_and_rejects_stale_tokens() -> None:
    listener = FakeNetworkListener(
        wait_results=[FakePacket(), FakePacket()]
    )
    network = PageTab(FakeNetworkPage(listener), FakeContext()).network

    first = await network.start()
    first_token = first["listener_token"]
    consumed = await network.wait(listener_token=first_token, limit=1)
    assert consumed["consumed_count"] == 1
    assert consumed["next_cursor"] == 1
    assert consumed["packets"][0]["index"] == 0
    assert consumed["remaining_timeout_ms"] >= 0

    second = await network.wait(listener_token=first_token, limit=1)
    assert second["consumed_count"] == 2
    assert second["next_cursor"] == 2
    assert second["packets"][0]["index"] == 1

    replacement = await network.start()
    assert replacement["listener_token"] != first_token
    with pytest.raises(NetworkListenerNotFoundError):
        await network.wait(listener_token=first_token)
    with pytest.raises(NetworkListenerNotFoundError):
        await network.stop(listener_token=first_token)
    assert listener.listening is True


@pytest.mark.asyncio
async def test_cancelled_network_wait_preserves_packet_for_the_next_wait() -> None:
    started = threading.Event()
    release = threading.Event()
    packet = FakePacket()

    class BlockingPacketListener(FakeNetworkListener):
        def wait(self, **kwargs):
            self.wait_calls.append(kwargs)
            started.set()
            release.wait(1)
            return packet

    listener = BlockingPacketListener()
    network = PageTab(FakeNetworkPage(listener), FakeContext()).network
    token = (await network.start())["listener_token"]

    wait_task = asyncio.create_task(network.wait(listener_token=token, timeout=1))
    assert await asyncio.to_thread(started.wait, 0.2)
    wait_task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await wait_task

    resumed = await network.wait(listener_token=token, timeout=0, limit=1)
    assert resumed["packets"][0]["index"] == 0
    assert resumed["consumed_count"] == 1
    assert len(listener.wait_calls) == 1


@pytest.mark.asyncio
async def test_tab_close_stops_managed_network_listener() -> None:
    listener = FakeNetworkListener()
    tab = PageTab(FakeNetworkPage(listener), FakeContext())
    await tab.network.start()

    assert await tab.close() is True
    assert listener.stop_calls == 1
    assert tab.is_closed is True


@pytest.mark.asyncio
async def test_network_listener_repeats_one_hundred_clean_lifecycles() -> None:
    listener = FakeNetworkListener()
    network = PageTab(FakeNetworkPage(listener), FakeContext()).network
    tokens: set[str] = set()

    for _ in range(100):
        started = await network.start(clear=True)
        token = started["listener_token"]
        tokens.add(token)
        stopped = await network.stop(clear=True, listener_token=token)
        assert stopped["state"] == "stopped"
        assert stopped["listening"] is False

    assert len(tokens) == 100
    assert listener.stop_calls == 100
    assert listener.listening is False


@pytest.mark.asyncio
async def test_network_start_uses_clear_and_legacy_start_signature() -> None:
    listener = FakeNetworkListener(start_type_error_once=True)
    result = await PageTab(FakeNetworkPage(listener), FakeContext()).network.start(
        targets=["/events"], is_regex=True
    )

    assert listener.clear_calls == 1
    assert listener.start_calls == [
        (
            (),
            {"targets": "/events", "is_regex": True, "method": None, "res_type": None},
        ),
        (("/events", True), {}),
    ]
    assert result["filters"]["targets"] == ["/events"]


@pytest.mark.asyncio
async def test_network_wait_normalizes_packets_and_timeout_shapes() -> None:
    packet = FakePacket()
    listener = FakeNetworkListener(
        listening=True,
        wait_results=[packet, False],
    )
    tab = PageTab(FakeNetworkPage(listener), FakeContext())

    result = await tab.network.wait(
        timeout=1,
        limit=2,
        include_headers=True,
        include_body=True,
        max_body_chars=8,
    )

    assert listener.wait_calls[0] == {
        "count": 1,
        "timeout": 1,
        "fit_count": False,
        "raise_err": False,
    }
    assert listener.wait_calls[1]["count"] == 1
    assert 0 < listener.wait_calls[1]["timeout"] <= 0.1
    assert result["timed_out"] is False
    assert result["count"] == 1
    assert result["packets"][0]["request_headers"] == {
        "Authorization": "<redacted>",
        "Accept": "application/json",
    }
    assert result["packets"][0]["response_headers"] == {
        "set-cookie": "<redacted>",
        "X-Trace": "visible",
    }
    assert result["packets"][0]["body_excerpt"] == '{"token"'
    assert result["packets"][0]["body_truncated"] is True

    single_listener = FakeNetworkListener(
        listening=True, wait_results=[FakePacket(), False]
    )
    single = await PageTab(FakeNetworkPage(single_listener), FakeContext()).network.wait(
        limit=1
    )
    assert single["timed_out"] is False
    assert single["count"] == 1

    timeout_listener = FakeNetworkListener(listening=True, wait_result=False)
    timed_out = await PageTab(
        FakeNetworkPage(timeout_listener), FakeContext()
    ).network.wait(limit=3)
    assert timed_out["timed_out"] is True
    assert timed_out["packets"] == []

    none_listener = FakeNetworkListener(listening=True, wait_result=None)
    no_packets = await PageTab(FakeNetworkPage(none_listener), FakeContext()).network.wait(
        limit=3
    )
    assert no_packets["timed_out"] is True
    assert no_packets["packets"] == []


@pytest.mark.asyncio
async def test_network_wait_requires_active_listener() -> None:
    with pytest.raises(RuntimeError, match="not listening"):
        await PageTab(
            FakeNetworkPage(FakeNetworkListener(listening=False)), FakeContext()
        ).network.wait()


@pytest.mark.asyncio
async def test_network_wait_cancellation_keeps_listener_state_serialized() -> None:
    started = threading.Event()
    release = threading.Event()

    class BlockingListener(FakeNetworkListener):
        def wait(self, **kwargs):
            self.wait_calls.append(kwargs)
            started.set()
            release.wait(1)
            return False

    listener = BlockingListener(listening=True)
    network = PageTab(FakeNetworkPage(listener), FakeContext()).network
    await network.start(clear=False)

    wait_task = asyncio.create_task(network.wait(timeout=1))
    assert await asyncio.to_thread(started.wait, 0.2)

    wait_task.cancel()
    await asyncio.sleep(0.01)
    start_task = asyncio.create_task(network.start(clear=False))
    await asyncio.sleep(0.02)
    assert not start_task.done()
    wait_task.cancel()

    release.set()
    with pytest.raises(asyncio.CancelledError):
        await wait_task
    await asyncio.wait_for(start_task, timeout=0.5)
    assert len(listener.start_calls) == 2


@pytest.mark.asyncio
async def test_network_stop_clears_or_pauses_listener_state() -> None:
    listening = FakeNetworkListener(listening=True)
    paused = await PageTab(FakeNetworkPage(listening), FakeContext()).network.stop(
        clear=False
    )
    assert listening.pause_calls == [{"clear": False}]
    assert paused == {
        "listening": False,
        "was_listening": True,
        "cleared": False,
        "tab_id": "",
        "listener_token": None,
        "state": "stopped",
        "consumed_count": 0,
        "next_cursor": 0,
    }

    idle = FakeNetworkListener(listening=False)
    cleared = await PageTab(FakeNetworkPage(idle), FakeContext()).network.stop()
    assert idle.clear_calls == 1
    assert cleared == {
        "listening": False,
        "was_listening": False,
        "cleared": True,
        "tab_id": "",
        "listener_token": None,
        "state": "stopped",
        "consumed_count": 0,
        "next_cursor": 0,
    }


@pytest.mark.asyncio
async def test_network_reports_unavailable_and_partial_listener_capabilities() -> None:
    with pytest.raises(RuntimeError, match="unavailable"):
        await PageTab(FakeNetworkPage(None), FakeContext()).network.start()

    class MissingStopListener:
        listening = False

        def start(self):
            return None

        def wait(self):
            return None

    with pytest.raises(RuntimeError, match="missing: stop"):
        await PageTab(FakeNetworkPage(MissingStopListener()), FakeContext()).network.stop()


@pytest.mark.asyncio
async def test_network_stop_suppresses_partial_driver_attribute_errors() -> None:
    listener = FakeNetworkListener(
        listening=True, stop_raises=AttributeError("driver detached")
    )

    result = await PageTab(FakeNetworkPage(listener), FakeContext()).network.stop()

    assert listener.stop_calls == 1
    assert result == {
        "listening": True,
        "was_listening": True,
        "cleared": True,
        "tab_id": "",
        "listener_token": None,
        "state": "listening",
        "consumed_count": 0,
        "next_cursor": 0,
    }


@pytest.mark.asyncio
async def test_network_stop_reraises_unexpected_driver_errors() -> None:
    listener = FakeNetworkListener(listening=True, stop_raises=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await PageTab(FakeNetworkPage(listener), FakeContext()).network.stop()


@pytest.mark.asyncio
async def test_wait_conditions_treat_missing_structured_targets_as_empty_state() -> None:
    target = SelectorTargetInput(kind="selector", selector="#missing")
    tab = PageTab(FakePage(element=None), FakeContext())

    with pytest.raises(TimeoutError):
        await tab.waits.until(
            condition="text_contains",
            selector=target,
            value="ready",
            timeout=0,
        )

    detached = await tab.waits.until(
        condition="detached",
        selector=target,
        timeout=0,
    )
    assert detached["state"] == {
        "exists": False,
        "visible": False,
        "disabled": False,
        "tag": "",
        "text": "",
        "signature": "",
    }


@pytest.mark.asyncio
async def test_network_stop_without_clear_falls_back_to_stop_when_pause_missing() -> None:
    listener = FakeNetworkListener(listening=True)
    listener.pause = None

    result = await PageTab(FakeNetworkPage(listener), FakeContext()).network.stop(
        clear=False
    )

    assert listener.stop_calls == 1
    assert result == {
        "listening": False,
        "was_listening": True,
        "cleared": False,
        "tab_id": "",
        "listener_token": None,
        "state": "stopped",
        "consumed_count": 0,
        "next_cursor": 0,
    }
