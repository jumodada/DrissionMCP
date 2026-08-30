"""Page media and browser-window operations."""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..tab import PageTab

logger = logging.getLogger(__name__)


class PageOperations:
    """Own page media, browser-window, and request-environment changes."""

    def __init__(self, tab: PageTab) -> None:
        self._tab = tab

    @property
    def _page(self) -> Any:
        return self._tab.page

    async def screenshot(self, path: str | None = None, full_page: bool = False) -> str:
        try:
            if path:
                self._page.get_screenshot(path=path, full_page=full_page)
                return path
            screenshot_data = self._page.get_screenshot(
                as_base64=True, full_page=full_page
            )
            if isinstance(screenshot_data, bytes):
                return base64.b64encode(screenshot_data).decode()
            if isinstance(screenshot_data, str):
                return screenshot_data
            raise TypeError(
                "DrissionPage get_screenshot(as_base64=True) returned "
                f"unsupported type: {type(screenshot_data).__name__}"
            )
        except Exception as exc:
            logger.error("Failed to take screenshot (%s)", type(exc).__name__)
            raise

    async def resize(self, width: int, height: int) -> None:
        try:
            self._page.set.window.size(width, height)
        except Exception as exc:
            logger.error("Failed to resize window (%s)", type(exc).__name__)
            raise

    async def set_headers(self, headers: dict[str, str]) -> dict[str, Any]:
        """Replace extra request headers and return value-free metadata."""

        try:
            self._page.set.headers(headers)
            return {
                "count": len(headers),
                "headers": {
                    name: "<redacted>" if value else ""
                    for name, value in headers.items()
                },
                "set": True,
            }
        except Exception as exc:
            logger.error(
                "Failed to set browser request headers (%s)", type(exc).__name__
            )
            raise

    async def set_user_agent(
        self, user_agent: str, platform: str | None = None
    ) -> dict[str, Any]:
        """Override the current tab's user agent and return the previous value."""

        try:
            previous_user_agent = str(self._page.user_agent)
            self._page.set.user_agent(user_agent, platform=platform)
            return {
                "previous_user_agent": previous_user_agent,
                "user_agent": user_agent,
                "platform": platform,
                "set": True,
            }
        except Exception as exc:
            logger.error("Failed to set browser user agent (%s)", type(exc).__name__)
            raise

    async def clear_cache(self) -> dict[str, Any]:
        """Clear HTTP cache without clearing cookies or Web Storage."""

        try:
            self._page.clear_cache(
                session_storage=False,
                local_storage=False,
                cache=True,
                cookies=False,
            )
            return {"cleared": True}
        except Exception as exc:
            logger.error("Failed to clear browser cache (%s)", type(exc).__name__)
            raise
