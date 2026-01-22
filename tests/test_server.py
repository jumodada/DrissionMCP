"""Test MCP server functionality."""

import pytest
from unittest.mock import Mock, patch

from drissionpage_mcp.server import DrissionPageMCPServer
from drissionpage_mcp.tools import get_all_tools


class TestDrissionPageMCPServer:
    """Test MCP server."""
    
    def test_server_initialization(self):
        """Test server can be initialized."""
        server = DrissionPageMCPServer()
        assert server.name == "DrissionPage MCP"
        assert server.version == "0.1.0"
        assert server.context is None
    
    def test_server_custom_name_version(self):
        """Test server with custom name and version."""
        server = DrissionPageMCPServer(name="Custom MCP", version="1.0.0")
        assert server.name == "Custom MCP" 
        assert server.version == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test server cleanup."""
        server = DrissionPageMCPServer()
        
        # Mock context
        mock_context = Mock()
        mock_context.cleanup = Mock(return_value=None)
        server.context = mock_context
        
        await server.cleanup()
        
        mock_context.cleanup.assert_called_once()
        assert server.context is None


class TestToolsIntegration:
    """Test tools integration."""
    
    def test_all_tools_have_required_attributes(self):
        """Test that all tools have required attributes."""
        tools = get_all_tools()
        
        for tool in tools:
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'input_schema')
            assert hasattr(tool, 'execute_func')
            
            assert isinstance(tool.name, str)
            assert isinstance(tool.description, str)
            assert len(tool.name) > 0
            assert len(tool.description) > 0
    
    def test_tool_names_are_unique(self):
        """Test that all tool names are unique."""
        tools = get_all_tools()
        names = [tool.name for tool in tools]
        
        assert len(names) == len(set(names)), "Tool names should be unique"
    
    def test_expected_tools_present(self):
        """Test that expected tools are present."""
        tools = get_all_tools()
        tool_names = [tool.name for tool in tools]
        
        # Navigation tools
        assert "page_navigate" in tool_names
        assert "page_go_back" in tool_names
        assert "page_go_forward" in tool_names
        assert "page_refresh" in tool_names
        
        # Common tools
        assert "page_resize" in tool_names
        assert "page_screenshot" in tool_names
        assert "page_click_xy" in tool_names
        assert "page_close" in tool_names
        assert "page_get_url" in tool_names
        
        # Element tools
        assert "element_click" in tool_names
        assert "element_input_text" in tool_names
        assert "element_get_text" in tool_names
        assert "element_get_attribute" in tool_names
        assert "element_get_html" in tool_names
        
        # Wait tools
        assert "wait_for_element" in tool_names
        assert "wait_for_url" in tool_names
        assert "wait_sleep" in tool_names


if __name__ == "__main__":
    pytest.main([__file__])