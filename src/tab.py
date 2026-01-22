"""Tab management for DrissionPage MCP."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Union

from DrissionPage import ChromiumPage
from DrissionPage.errors import ElementNotFoundError, PageDisconnectedError

if TYPE_CHECKING:
    from .context import DrissionPageContext

logger = logging.getLogger(__name__)


class PageTab:
    """Wrapper around DrissionPage ChromiumPage for tab management."""
    
    def __init__(self, page: ChromiumPage, context: "DrissionPageContext"):
        self.page = page
        self.context = context
        self._url = ""
    
    @property
    def url(self) -> str:
        """Get the current URL of the tab."""
        try:
            return self.page.url or self._url
        except (PageDisconnectedError, Exception):
            return self._url
    
    async def navigate(self, url: str) -> None:
        """Navigate to a URL."""
        try:
            self.page.get(url)
            self._url = url
            # Wait for page load
            await asyncio.sleep(0.5)  # Basic wait, can be improved
            logger.info(f"Navigated to: {url}")
        except Exception as e:
            logger.error(f"Failed to navigate to {url}: {e}")
            raise
    
    async def go_back(self) -> None:
        """Go back in history."""
        try:
            self.page.back()
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to go back: {e}")
            raise
    
    async def go_forward(self) -> None:
        """Go forward in history."""
        try:
            self.page.forward()
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to go forward: {e}")
            raise
    
    async def refresh(self) -> None:
        """Refresh the page."""
        try:
            self.page.refresh()
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to refresh: {e}")
            raise
    
    async def click(self, x: int, y: int) -> None:
        """Click at coordinates."""
        try:
            self.page.actions.click((x, y))
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to click at ({x}, {y}): {e}")
            raise
    
    async def click_element(self, selector: str, timeout: int = 10) -> None:
        """Click an element by selector."""
        try:
            # Wait for element if timeout is specified
            if timeout > 0:
                await self.wait_for_element(selector, timeout)

            element = self.page.ele(selector)
            if element:
                element.click()
                await asyncio.sleep(0.1)
            else:
                raise ElementNotFoundError(f"Element not found: {selector}")
        except Exception as e:
            logger.error(f"Failed to click element {selector}: {e}")
            raise
    
    async def input_text(self, selector: str, text: str, clear: bool = True) -> None:
        """Input text into an element."""
        try:
            element = self.page.ele(selector)
            if element:
                if clear:
                    element.clear()
                element.input(text)
                await asyncio.sleep(0.1)
            else:
                raise ElementNotFoundError(f"Element not found: {selector}")
        except Exception as e:
            logger.error(f"Failed to input text to {selector}: {e}")
            raise

    async def type_text(self, selector: str, text: str, timeout: int = 10, clear: bool = True) -> None:
        """Type text into an element (alias for input_text with timeout support)."""
        try:
            # Wait for element if timeout is specified
            if timeout > 0:
                await self.wait_for_element(selector, timeout)

            await self.input_text(selector, text, clear)
        except Exception as e:
            logger.error(f"Failed to type text to {selector}: {e}")
            raise

    async def find_element(self, selector: str, timeout: int = 10) -> Dict[str, Any]:
        """Find an element and return its information."""
        try:
            # Wait for element to appear
            element_exists = await self.wait_for_element(selector, timeout)

            if not element_exists:
                raise ElementNotFoundError(f"Element not found: {selector}")

            element = self.page.ele(selector)
            if not element:
                raise ElementNotFoundError(f"Element not found: {selector}")

            # Return element information
            return {
                "found": True,
                "selector": selector,
                "text": element.text or "",
                "tag": element.tag if hasattr(element, 'tag') else "unknown",
                "visible": True  # DrissionPage elements are visible if found
            }
        except Exception as e:
            logger.error(f"Failed to find element {selector}: {e}")
            raise
    
    async def get_text(self, selector: str = "") -> str:
        """Get text content from element or page."""
        try:
            if selector:
                element = self.page.ele(selector)
                if element:
                    return element.text
                else:
                    raise ElementNotFoundError(f"Element not found: {selector}")
            else:
                # Get page text
                return self.page.text
        except Exception as e:
            logger.error(f"Failed to get text from {selector or 'page'}: {e}")
            raise
    
    async def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Get attribute value from an element."""
        try:
            element = self.page.ele(selector)
            if element:
                return element.attr(attribute)
            else:
                raise ElementNotFoundError(f"Element not found: {selector}")
        except Exception as e:
            logger.error(f"Failed to get attribute {attribute} from {selector}: {e}")
            raise
    
    async def get_html(self, selector: str = "") -> str:
        """Get HTML content."""
        try:
            if selector:
                element = self.page.ele(selector)
                if element:
                    return element.html
                else:
                    raise ElementNotFoundError(f"Element not found: {selector}")
            else:
                return self.page.html
        except Exception as e:
            logger.error(f"Failed to get HTML from {selector or 'page'}: {e}")
            raise
    
    async def screenshot(self, path: Optional[str] = None, full_page: bool = False) -> str:
        """Take a screenshot."""
        try:
            if path:
                self.page.get_screenshot(path=path, full_page=full_page)
                return path
            else:
                # Return base64 encoded screenshot
                import tempfile
                import base64
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                    self.page.get_screenshot(path=f.name, full_page=full_page)
                    with open(f.name, 'rb') as img_file:
                        return base64.b64encode(img_file.read()).decode()
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            raise
    
    async def wait_for_element(self, selector: str, timeout: int = 10) -> bool:
        """Wait for an element to appear."""
        try:
            element = self.page.wait.ele_loaded(selector, timeout=timeout)
            return element is not None
        except Exception as e:
            logger.warning(f"Element {selector} not found within {timeout}s: {e}")
            return False
    
    async def wait_for_url(self, url_pattern: str, timeout: int = 10) -> bool:
        """Wait for URL to match pattern."""
        try:
            # Simple implementation - can be improved with proper pattern matching
            import time
            start_time = time.time()
            while time.time() - start_time < timeout:
                if url_pattern in self.url:
                    return True
                await asyncio.sleep(0.5)
            return False
        except Exception as e:
            logger.warning(f"URL pattern {url_pattern} not matched within {timeout}s: {e}")
            return False
    
    async def resize(self, width: int, height: int) -> None:
        """Resize the browser window."""
        try:
            self.page.set.window.size(width, height)
        except Exception as e:
            logger.error(f"Failed to resize window to {width}x{height}: {e}")
            raise
    
    async def close(self) -> None:
        """Close the tab."""
        try:
            # For DrissionPage, we don't close individual tabs
            # but we can navigate away or clear the page
            logger.info("Tab closed (DrissionPage context)")
        except Exception as e:
            logger.error(f"Failed to close tab: {e}")
    
    def is_connected(self) -> bool:
        """Check if the tab is still connected."""
        try:
            # Try to access a basic property
            _ = self.page.url
            return True
        except (PageDisconnectedError, Exception):
            return False