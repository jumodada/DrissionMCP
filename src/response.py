"""Response handling for DrissionPage MCP tools."""

import base64
import logging
from typing import Any, List, Optional, Sequence, Union

from mcp.types import TextContent, ImageContent

logger = logging.getLogger(__name__)


class ToolResponse:
    """Handles responses from DrissionPage MCP tools."""
    
    def __init__(self):
        self._content: List[Union[TextContent, ImageContent]] = []
        self._code_snippets: List[str] = []
        self._include_snapshot = False
        self._is_error = False
    
    def add_text(self, text: str) -> None:
        """Add text content to the response."""
        self._content.append(TextContent(type="text", text=text))
    
    def add_error(self, error: str) -> None:
        """Add error content to the response."""
        self._is_error = True
        error_text = f"### Error\n{error}"
        self._content.append(TextContent(type="text", text=error_text))
    
    def add_result(self, result: str) -> None:
        """Add result content to the response."""
        result_text = f"### Result\n{result}"
        self._content.append(TextContent(type="text", text=result_text))
    
    def add_code(self, code: str) -> None:
        """Add code snippet to the response."""
        self._code_snippets.append(code)
    
    def add_image(self, image_data: Union[str, bytes], mime_type: str = "image/png") -> None:
        """Add image content to the response."""
        if isinstance(image_data, bytes):
            image_data = base64.b64encode(image_data).decode()
        elif not isinstance(image_data, str):
            raise ValueError("Image data must be string or bytes")
        
        self._content.append(ImageContent(
            type="image",
            data=image_data,
            mimeType=mime_type
        ))
    
    def add_screenshot(self, screenshot_data: str) -> None:
        """Add screenshot to the response."""
        self.add_image(screenshot_data, "image/png")
        self.add_text("Screenshot taken.")
    
    def set_include_snapshot(self, include: bool = True) -> None:
        """Set whether to include a snapshot in the response."""
        self._include_snapshot = include
    
    def get_content(self) -> Sequence[Union[TextContent, ImageContent]]:
        """Get all response content."""
        # Add code snippets if any
        if self._code_snippets:
            code_text = "### Code\n```python\n" + "\n".join(self._code_snippets) + "\n```"
            # Insert code at the beginning
            self._content.insert(0, TextContent(type="text", text=code_text))
        
        # Add default content if empty
        if not self._content:
            if self._is_error:
                self._content.append(TextContent(type="text", text="### Error\nUnknown error occurred."))
            else:
                self._content.append(TextContent(type="text", text="### Result\nOperation completed successfully."))
        
        return self._content
    
    def is_error(self) -> bool:
        """Check if the response contains an error."""
        return self._is_error
    
    def should_include_snapshot(self) -> bool:
        """Check if a snapshot should be included."""
        return self._include_snapshot
    
    def clear(self) -> None:
        """Clear all response content."""
        self._content.clear()
        self._code_snippets.clear()
        self._include_snapshot = False
        self._is_error = False