"""Compatibility helper coverage for DrissionPage version seams."""

from __future__ import annotations

import inspect

import pytest

import drissionpage_mcp.compat as compat


class FakeOptions:
    def __init__(self, read_file=None) -> None:
        self.read_file = read_file
        self.calls: list[tuple[str, tuple, dict]] = []

    def auto_port(self) -> None:
        self.calls.append(("auto_port", (), {}))

    def set_browser_path(self, path: str) -> None:
        self.calls.append(("set_browser_path", (path,), {}))

    def set_user_data_path(self, path: str) -> None:
        self.calls.append(("set_user_data_path", (path,), {}))

    def headless(self, enabled: bool) -> None:
        self.calls.append(("headless", (enabled,), {}))

    def set_load_mode(self, mode: str) -> None:
        self.calls.append(("set_load_mode", (mode,), {}))

    def set_timeouts(self, **kwargs) -> None:
        self.calls.append(("set_timeouts", (), kwargs))

    def set_argument(self, argument: str) -> None:
        self.calls.append(("set_argument", (argument,), {}))


def _arguments(options: FakeOptions) -> list[str]:
    return [args[0] for name, args, _kwargs in options.calls if name == "set_argument"]


def test_accepts_parameters_handles_explicit_kwargs_and_uninspectable_callables(
    monkeypatch,
) -> None:
    def explicit(*, button, count):
        return button, count

    def flexible(**kwargs):
        return kwargs

    assert compat.accepts_parameters(explicit, "button", "count") is True
    assert compat.accepts_parameters(explicit, "missing") is False
    assert compat.accepts_parameters(flexible, "anything") is True

    monkeypatch.setattr(
        compat.inspect, "signature", lambda _obj: (_ for _ in ()).throw(ValueError())
    )
    assert compat.accepts_parameters(explicit, "button") is False


def test_new_chromium_options_uses_no_user_ini_when_supported(monkeypatch) -> None:
    monkeypatch.setattr(compat, "ChromiumOptions", FakeOptions)

    options = compat._new_chromium_options()

    assert isinstance(options, FakeOptions)
    assert options.read_file is False


def test_new_chromium_options_falls_back_for_uninspectable_builds(monkeypatch) -> None:
    class NoReadFileOptions(FakeOptions):
        def __init__(self) -> None:
            super().__init__(read_file="default")

    def fail_signature(_obj):
        raise ValueError("uninspectable")

    monkeypatch.setattr(compat, "ChromiumOptions", NoReadFileOptions)
    monkeypatch.setattr(compat.inspect, "signature", fail_signature)

    options = compat._new_chromium_options()

    assert isinstance(options, NoReadFileOptions)
    assert options.read_file == "default"


def test_build_chromium_options_applies_environment_contract(monkeypatch) -> None:
    monkeypatch.setenv("CHROME_PATH", "/tmp/chrome")
    monkeypatch.setenv("DP_BROWSER_PATH", "/tmp/ignored")
    monkeypatch.setenv("DP_USER_DATA_PATH", "/tmp/user-data")
    monkeypatch.setenv("DP_HEADLESS", "on")
    monkeypatch.setenv("DP_LOAD_MODE", "eager")
    monkeypatch.setenv("DP_TIMEOUT", "2")
    monkeypatch.setenv("DP_PAGE_LOAD_TIMEOUT", "3")
    monkeypatch.setenv("DP_SCRIPT_TIMEOUT", "4")
    monkeypatch.setenv("DP_NO_SANDBOX", "1")
    monkeypatch.setenv("DP_DISABLE_WEB_SECURITY", "true")
    options = FakeOptions()
    monkeypatch.setattr(compat, "_new_chromium_options", lambda: options)

    assert compat.build_chromium_options() is options

    assert ("auto_port", (), {}) in options.calls
    assert ("set_browser_path", ("/tmp/chrome",), {}) in options.calls
    assert ("set_user_data_path", ("/tmp/user-data",), {}) in options.calls
    assert ("headless", (True,), {}) in options.calls
    assert ("set_load_mode", ("eager",), {}) in options.calls
    assert (
        "set_timeouts",
        (),
        {"base": 2.0, "page_load": 3.0, "script": 4.0},
    ) in options.calls
    assert ("set_argument", ("--no-sandbox",), {}) in options.calls
    assert ("set_argument", ("--disable-dev-shm-usage",), {}) in options.calls
    assert ("set_argument", ("--disable-web-security",), {}) in options.calls


def test_build_chromium_options_keeps_chrome_sandbox_enabled_by_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DP_NO_SANDBOX", raising=False)
    monkeypatch.delenv("DP_DISABLE_WEB_SECURITY", raising=False)
    options = FakeOptions()
    monkeypatch.setattr(compat, "_new_chromium_options", lambda: options)

    compat.build_chromium_options()

    arguments = _arguments(options)
    assert "--no-sandbox" not in arguments
    assert "--disable-web-security" not in arguments
    assert "--disable-dev-shm-usage" in arguments


@pytest.mark.parametrize("value", ["0", "false", "no", "off"])
def test_build_chromium_options_respects_explicit_sandbox_opt_out_false(
    monkeypatch, value: str
) -> None:
    monkeypatch.setenv("DP_NO_SANDBOX", value)
    options = FakeOptions()
    monkeypatch.setattr(compat, "_new_chromium_options", lambda: options)

    compat.build_chromium_options()

    assert "--no-sandbox" not in _arguments(options)


def test_create_browser_prefers_chromium_and_falls_back_to_chromium_page(
    monkeypatch,
) -> None:
    class FakeChromium:
        def __init__(self, options) -> None:
            self.options = options

    class FakeChromiumPage:
        def __init__(self, addr_or_opts) -> None:
            self.options = addr_or_opts

    options = object()
    monkeypatch.setattr(compat, "Chromium", FakeChromium)
    assert isinstance(compat.create_browser(options), FakeChromium)

    monkeypatch.setattr(compat, "Chromium", None)
    monkeypatch.setattr(compat, "ChromiumPage", FakeChromiumPage)
    assert isinstance(compat.create_browser(options), FakeChromiumPage)

    monkeypatch.setattr(compat, "ChromiumPage", None)
    with pytest.raises(RuntimeError, match="does not provide Chromium"):
        compat.create_browser(options)


def test_get_latest_tab_normalizes_current_tab_shapes() -> None:
    direct_tab = object()
    assert compat.get_latest_tab(type("Browser", (), {"latest_tab": direct_tab})()) is (
        direct_tab
    )

    fallback_tab = object()

    class BrowserWithGetter:
        latest_tab = None

        def get_tab(self):
            return fallback_tab

    assert compat.get_latest_tab(BrowserWithGetter()) is fallback_tab

    id_tab = object()

    class BrowserWithTabId:
        latest_tab = "tab-id"

        def get_tab(self, tab_id=None):
            assert tab_id == "tab-id"
            return id_tab

    assert compat.get_latest_tab(BrowserWithTabId()) is id_tab

    with pytest.raises(RuntimeError, match="Unable to obtain"):
        compat.get_latest_tab(type("BrowserWithoutTabs", (), {"latest_tab": None})())


def test_new_tab_handles_missing_and_legacy_signatures() -> None:
    latest_tab = object()

    BrowserWithoutNewTab = type("BrowserWithoutNewTab", (), {"latest_tab": latest_tab})

    assert compat.new_tab(BrowserWithoutNewTab()) is latest_tab

    new_tab_obj = object()

    class BrowserWithModernNewTab:
        def new_tab(self, url=None):
            assert url == "https://example.test"
            return new_tab_obj

    assert compat.new_tab(BrowserWithModernNewTab(), "https://example.test") is (
        new_tab_obj
    )

    legacy_tab = object()

    class BrowserWithLegacyNewTab:
        def new_tab(self, *args, **kwargs):
            if kwargs:
                raise TypeError("legacy positional only")
            assert args == ("https://example.test",)
            return legacy_tab

    assert compat.new_tab(BrowserWithLegacyNewTab(), "https://example.test") is (
        legacy_tab
    )


def test_new_tab_requires_isolated_context_capability_before_creation() -> None:
    calls: list[dict[str, object]] = []

    class BrowserWithIsolatedNewTab:
        def new_tab(self, url=None, *, new_context=False):
            calls.append({"url": url, "new_context": new_context})
            return "isolated-tab"

    assert (
        compat.new_tab(
            BrowserWithIsolatedNewTab(),
            "https://example.test",
            new_context=True,
        )
        == "isolated-tab"
    )
    assert calls == [{"url": "https://example.test", "new_context": True}]

    latest_tab = object()
    browser_without_new_tab = type(
        "BrowserWithoutNewTab", (), {"latest_tab": latest_tab}
    )()
    with pytest.raises(RuntimeError, match="isolated browser context"):
        compat.new_tab(browser_without_new_tab, new_context=True)

    class BrowserWithoutContextParameter:
        def __init__(self) -> None:
            self.calls = 0

        def new_tab(self, url=None):
            self.calls += 1
            return object()

    unsupported = BrowserWithoutContextParameter()
    with pytest.raises(RuntimeError, match="isolated browser context"):
        compat.new_tab(unsupported, new_context=True)
    assert unsupported.calls == 0


def test_new_tab_forwards_background_and_window_semantics() -> None:
    calls: list[dict[str, object]] = []

    class BrowserWithCreationOptions:
        def new_tab(
            self,
            url=None,
            *,
            new_window=False,
            background=False,
            new_context=False,
        ):
            calls.append(
                {
                    "url": url,
                    "new_window": new_window,
                    "background": background,
                    "new_context": new_context,
                }
            )
            return "created-tab"

    assert (
        compat.new_tab(
            BrowserWithCreationOptions(),
            "https://example.test",
            new_window=True,
            background=True,
        )
        == "created-tab"
    )
    assert calls == [
        {
            "url": "https://example.test",
            "new_window": True,
            "background": True,
            "new_context": False,
        }
    ]

    class BrowserWithoutCreationOptions:
        def new_tab(self, url=None):
            return object()

    with pytest.raises(RuntimeError, match="background"):
        compat.new_tab(BrowserWithoutCreationOptions(), background=True)


def test_quit_browser_supports_quit_close_and_none() -> None:
    compat.quit_browser(None)

    class BrowserWithQuit:
        def __init__(self) -> None:
            self.quit_called = False

        def quit(self) -> None:
            self.quit_called = True

    browser = BrowserWithQuit()
    compat.quit_browser(browser)
    assert browser.quit_called is True

    class BrowserWithClose:
        def __init__(self) -> None:
            self.close_called = False

        def close(self) -> None:
            self.close_called = True

    close_browser = BrowserWithClose()
    compat.quit_browser(close_browser)
    assert close_browser.close_called is True


def test_signature_module_remains_real_after_monkeypatches() -> None:
    """Guard this module's monkeypatch-heavy tests from leaking global state."""

    assert inspect.signature is not None
