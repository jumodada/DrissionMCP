"""Context management for DrissionPage MCP."""

import asyncio
import logging
from typing import List, Optional

from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.errors import PageDisconnectedError

from .tab import PageTab

logger = logging.getLogger(__name__)


class DrissionPageContext:
    """Manages DrissionPage browser context and tabs."""
    
    def __init__(self):
        self._page: Optional[ChromiumPage] = None
        self._current_tab: Optional[PageTab] = None
        self._tabs: List[PageTab] = []
        self._is_initialized = False
    
    async def initialize(self) -> None:
        """Initialize the browser context."""
        if self._is_initialized:
            return
            
        try:
            # Configure ChromiumPage options
            options = ChromiumOptions()
            options.set_argument('--no-sandbox')
            options.set_argument('--disable-dev-shm-usage')
            options.set_argument('--disable-web-security')
            options.set_argument('--disable-features=VizDisplayCompositor')
            
            # Create the page
            self._page = ChromiumPage(addr_or_opts=options)
            
            # Create initial tab
            tab = PageTab(self._page, self)
            self._tabs.append(tab)
            self._current_tab = tab
            
            self._is_initialized = True
            logger.info("DrissionPage context initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize DrissionPage context: {e}")
            raise
    
    async def ensure_initialized(self) -> None:
        """Ensure the context is initialized."""
        if not self._is_initialized:
            await self.initialize()
    
    def current_tab(self) -> Optional[PageTab]:
        """Get the current active tab."""
        return self._current_tab
    
    def current_tab_or_die(self) -> PageTab:
        """Get the current tab or raise an error."""
        if not self._current_tab:
            raise RuntimeError("No active tab. Use navigate tool to open a page first.")
        return self._current_tab
    
    def tabs(self) -> List[PageTab]:
        """Get all tabs."""
        return self._tabs.copy()
    
    async def ensure_tab(self) -> PageTab:
        """Ensure there's an active tab, creating one if necessary."""
        await self.ensure_initialized()
        
        if not self._current_tab:
            # Create a new tab if none exists
            if self._page:
                tab = PageTab(self._page, self)
                self._tabs.append(tab)
                self._current_tab = tab
        
        return self._current_tab
    
    async def new_tab(self) -> PageTab:
        """Create a new tab."""
        await self.ensure_initialized()
        
        if not self._page:
            raise RuntimeError("Browser context not initialized")
        
        # For DrissionPage, we typically work with a single page
        # but we can simulate tabs by navigating the same page
        tab = PageTab(self._page, self)
        self._tabs.append(tab)
        self._current_tab = tab
        return tab
    
    async def close_tab(self, tab: Optional[PageTab] = None) -> None:
        """Close a tab."""
        target_tab = tab or self._current_tab
        if not target_tab:
            return
        
        # Remove from tabs list
        if target_tab in self._tabs:
            self._tabs.remove(target_tab)
        
        # Update current tab
        if self._current_tab == target_tab:
            self._current_tab = self._tabs[0] if self._tabs else None
        
        await target_tab.close()
    
    async def close_browser(self) -> None:
        """Close the browser context."""
        if self._page:
            try:
                self._page.quit()
            except (PageDisconnectedError, Exception) as e:
                logger.warning(f"Error closing browser: {e}")
            finally:
                self._page = None
        
        self._tabs.clear()
        self._current_tab = None
        self._is_initialized = False
        logger.info("Browser context closed")
    
    async def cleanup(self) -> None:
        """Clean up all resources."""
        await self.close_browser()

    async def wait(self, seconds: float) -> None:
        """Wait for a specified number of seconds."""
        await asyncio.sleep(seconds)

    def is_active(self) -> bool:
        """Check if the context is active."""
        return self._is_initialized and self._page is not None