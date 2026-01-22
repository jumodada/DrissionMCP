"""Test tools functionality."""

import pytest
import asyncio
from unittest.mock import Mock, patch

from drissionpage_mcp.context import DrissionPageContext
from drissionpage_mcp.response import ToolResponse
from drissionpage_mcp.tools import get_all_tools
from drissionpage_mcp.tools.navigate import NavigateInput, NavigateTools


class TestNavigateTools:
    """Test navigation tools."""
    
    @pytest.mark.asyncio
    async def test_get_all_tools(self):
        """Test that we can get all tools."""
        tools = get_all_tools()
        assert len(tools) > 0
        
        # Check that we have some expected tools
        tool_names = [tool.name for tool in tools]
        assert "page_navigate" in tool_names
        assert "element_click" in tool_names
        assert "wait_for_element" in tool_names
    
    @pytest.mark.asyncio
    async def test_navigate_tool_definition(self):
        """Test navigate tool definition."""
        tools = NavigateTools.get_tools()
        navigate_tool = next(tool for tool in tools if tool.name == "page_navigate")
        
        assert navigate_tool.name == "page_navigate"
        assert "navigate" in navigate_tool.description.lower()
        assert navigate_tool.input_schema == NavigateInput
    
    @pytest.mark.asyncio
    async def test_navigate_input_validation(self):
        """Test navigate input validation."""
        # Valid input
        valid_input = NavigateInput(url="https://example.com")
        assert valid_input.url == "https://example.com"
        
        # Test that URL is required
        with pytest.raises(Exception):  # Pydantic validation error
            NavigateInput()
    
    @pytest.mark.asyncio
    async def test_navigate_execution_mock(self):
        """Test navigate tool execution with mocked DrissionPage."""
        # Create mocked context and tab
        mock_context = Mock(spec=DrissionPageContext)
        mock_tab = Mock()
        mock_tab.navigate = Mock(return_value=asyncio.coroutine(lambda: None)())
        mock_context.ensure_tab = Mock(return_value=asyncio.coroutine(lambda: mock_tab)())
        
        # Create response object
        response = ToolResponse()
        
        # Create input
        input_data = NavigateInput(url="https://example.com")
        
        # Execute the tool
        await NavigateTools._navigate(mock_context, input_data, response)
        
        # Verify that navigate was called
        mock_context.ensure_tab.assert_called_once()
        mock_tab.navigate.assert_called_once_with("https://example.com")
        
        # Check response
        content = response.get_content()
        assert len(content) > 0
        assert any("successfully navigated" in str(content_item).lower() for content_item in content)


class TestToolResponse:
    """Test ToolResponse functionality."""
    
    def test_add_text(self):
        """Test adding text to response."""
        response = ToolResponse()
        response.add_text("Test message")
        
        content = response.get_content()
        assert len(content) == 1
        assert content[0].type == "text"
        assert "Test message" in content[0].text
    
    def test_add_error(self):
        """Test adding error to response."""
        response = ToolResponse()
        response.add_error("Test error")
        
        content = response.get_content()
        assert len(content) == 1
        assert content[0].type == "text"
        assert "Error" in content[0].text
        assert "Test error" in content[0].text
        assert response.is_error()
    
    def test_add_code(self):
        """Test adding code to response."""
        response = ToolResponse()
        response.add_code("print('hello')")
        
        content = response.get_content()
        assert len(content) == 1
        assert "```python" in content[0].text
        assert "print('hello')" in content[0].text
    
    def test_empty_response(self):
        """Test empty response gets default content."""
        response = ToolResponse()
        content = response.get_content()
        
        assert len(content) == 1
        assert "operation completed successfully" in content[0].text.lower()


if __name__ == "__main__":
    pytest.main([__file__])