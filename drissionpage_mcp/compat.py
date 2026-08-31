"""Compatibility helpers for DrissionPage 4.0 through 4.2."""

from __future__ import annotations

import inspect
import logging
import os
from typing import Any

from DrissionPage import ChromiumOptions

from .env import env_bool

try:  # DrissionPage 4.x exports Chromium; 4.2 makes it the preferred API.
    from DrissionPage import Chromium
except ImportError:  # pragma: no cover - kept for older/partial installs.
    Chromium = None

try:
    from DrissionPage import ChromiumPage
except ImportError:  # pragma: no cover - 4.2 still exports it, but it is deprecated.
    ChromiumPage = None

try:
    from DrissionPage.version import __version__ as DRISSIONPAGE_VERSION
except Exception:  # pragma: no cover - defensive for unusual builds.
    DRISSIONPAGE_VERSION = "unknown"


logger = logging.getLogger(__name__)


def accepts_parameters(callable_obj: Any, *names: str) -> bool:
    """Return whether a runtime callable accepts all named keyword arguments."""

    try:
        parameters = inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return False
    if any(item.kind == inspect.Parameter.VAR_KEYWORD for item in parameters.values()):
        return True
    return all(name in parameters for name in names)


def _new_chromium_options() -> ChromiumOptions:
    """Create ChromiumOptions without reading a user ini when supported."""

    try:
        signature = inspect.signature(ChromiumOptions)
        if "read_file" in signature.parameters:
            return ChromiumOptions(read_file=False)
    except (TypeError, ValueError):
        pass
    return ChromiumOptions()


def build_chromium_options() -> ChromiumOptions:
    """Build safe, deterministic Chromium options for an MCP-owned browser."""

    options = _new_chromium_options()

    # Isolate MCP browser sessions by default. This avoids attaching to a user's
    # existing browser/debug port and works in both DrissionPage 4.1 and 4.2.
    if env_bool("DP_AUTO_PORT", True) and hasattr(options, "auto_port"):
        options.auto_port()

    chrome_path = os.getenv("CHROME_PATH") or os.getenv("DP_BROWSER_PATH")
    if chrome_path and hasattr(options, "set_browser_path"):
        options.set_browser_path(chrome_path)

    user_data_path = os.getenv("DP_USER_DATA_PATH")
    if user_data_path and hasattr(options, "set_user_data_path"):
        options.set_user_data_path(user_data_path)

    if hasattr(options, "headless"):
        options.headless(env_bool("DP_HEADLESS", False))

    if hasattr(options, "set_load_mode"):
        options.set_load_mode(os.getenv("DP_LOAD_MODE", "normal"))

    if hasattr(options, "set_timeouts"):
        options.set_timeouts(
            base=float(os.getenv("DP_TIMEOUT", "10")),
            page_load=float(os.getenv("DP_PAGE_LOAD_TIMEOUT", "30")),
            script=float(os.getenv("DP_SCRIPT_TIMEOUT", "30")),
        )

    if hasattr(options, "set_argument"):
        # Keep Chrome sandbox enabled by default. Container/root environments
        # that cannot launch Chromium with sandboxing may opt in explicitly.
        if env_bool("DP_NO_SANDBOX", False):
            options.set_argument("--no-sandbox")
        options.set_argument("--disable-dev-shm-usage")
        # Do not disable web security by default. Users can opt in for local
        # test pages, but the MCP server should not weaken browser isolation.
        if env_bool("DP_DISABLE_WEB_SECURITY", False):
            options.set_argument("--disable-web-security")

    return options


def create_browser(options: ChromiumOptions | None = None) -> Any:
    """Create a browser using the 4.2-preferred API with older fallbacks."""

    opts = options or build_chromium_options()
    if Chromium is not None:
        return Chromium(opts)
    if ChromiumPage is not None:  # pragma: no cover - older fallback.
        return ChromiumPage(addr_or_opts=opts)
    raise RuntimeError("DrissionPage does not provide Chromium or ChromiumPage.")


def get_latest_tab(browser: Any) -> Any:
    """Return the active tab object from a Chromium/ChromiumPage-like object."""

    tab = getattr(browser, "latest_tab", None)
    if tab is None and hasattr(browser, "get_tab"):
        tab = browser.get_tab()

    # DrissionPage can be configured to return tab IDs instead of singleton tab
    # objects. Normalize to a tab object for the rest of the MCP code.
    if isinstance(tab, str) and hasattr(browser, "get_tab"):
        tab = browser.get_tab(tab)

    if tab is None:
        raise RuntimeError("Unable to obtain an active DrissionPage tab.")
    return tab


def new_tab(
    browser: Any,
    url: str | None = None,
    *,
    background: bool = False,
    new_window: bool = False,
    new_context: bool = False,
) -> Any:
    """Create a new tab across DrissionPage 4.x signature differences."""

    if not hasattr(browser, "new_tab"):
        if any((new_context, background, new_window)):
            if new_context:
                raise RuntimeError(
                    "This DrissionPage runtime cannot create an isolated browser context."
                )
            raise RuntimeError(
                "This DrissionPage runtime cannot honor the requested tab creation options."
            )
        return get_latest_tab(browser)

    try:
        requested = {
            "new_window": bool(new_window),
            "background": bool(background),
            "new_context": bool(new_context),
        }
        if any(requested.values()):
            supported = {
                name: value
                for name, value in requested.items()
                if accepts_parameters(browser.new_tab, name)
            }
            missing = [
                name
                for name, value in requested.items()
                if value and name not in supported
            ]
            if missing:
                if "new_context" in missing:
                    raise RuntimeError(
                        "This DrissionPage runtime cannot create an isolated browser context."
                    )
                raise RuntimeError(
                    "This DrissionPage runtime cannot honor tab creation option(s): "
                    + ", ".join(missing)
                )
            return browser.new_tab(url=url, **supported)
        return browser.new_tab(url=url)
    except TypeError:
        if any((new_context, background, new_window)):
            raise RuntimeError(
                "This DrissionPage runtime cannot honor the requested tab creation options."
            ) from None
        return browser.new_tab(url)


def quit_browser(browser: Any) -> None:
    """Close a DrissionPage browser/page object."""

    if browser is None:
        return
    if hasattr(browser, "quit"):
        browser.quit()
    elif hasattr(browser, "close"):
        browser.close()
