#!/usr/bin/env python3
"""
Local Testing - Test DrissionPage MCP functionality without MCP client

This script allows you to test all MCP tools directly without needing Claude or MCP client.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any

# Add src to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class LocalMCPTester:
    """Local tester for MCP tools."""
    
    def __init__(self):
        self.context = None
        self.setup_mocks()
    
    def setup_mocks(self):
        """Setup mock dependencies for testing."""
        from unittest.mock import Mock
        
        # Mock MCP types
        mock_mcp = Mock()
        mock_mcp.types = Mock()
        mock_mcp.types.TextContent = lambda type="text", text="": Mock(type=type, text=text)
        mock_mcp.types.ImageContent = lambda type="image", data="", mimeType="image/png": Mock(type=type, data=data, mimeType=mimeType)
        
        sys.modules['mcp'] = mock_mcp
        sys.modules['mcp.types'] = mock_mcp.types
        
        # Mock DrissionPage if not available
        try:
            import DrissionPage
            logger.info("✅ Using real DrissionPage")
        except ImportError:
            logger.warning("⚠️ DrissionPage not found, using mock")
            self.setup_drissionpage_mock()
    
    def setup_drissionpage_mock(self):
        """Setup DrissionPage mock for testing."""
        from unittest.mock import Mock
        
        class MockChromiumPage:
            def __init__(self, *args, **kwargs):
                self.url = "about:blank"
            
            def get(self, url):
                self.url = url
                logger.info(f"🌐 Mock: Navigated to {url}")
            
            def quit(self):
                logger.info("🔚 Mock: Browser closed")
            
            @property
            def text(self):
                return "Mock page text content"
            
            @property
            def html(self):
                return "<html><body>Mock HTML content</body></html>"
            
            def ele(self, selector):
                mock_element = Mock()
                mock_element.text = f"Mock element text for {selector}"
                mock_element.click = lambda: logger.info(f"🖱️ Mock: Clicked {selector}")
                mock_element.input = lambda text: logger.info(f"⌨️ Mock: Input '{text}' to {selector}")
                mock_element.clear = lambda: logger.info(f"🗑️ Mock: Cleared {selector}")
                mock_element.attr = lambda attr: f"mock-{attr}-value"
                mock_element.html = f"<div>Mock HTML for {selector}</div>"
                return mock_element
            
            def get_screenshot(self, path=None, full_page=False):
                logger.info(f"📸 Mock: Screenshot saved to {path or 'base64'}")
                return "mock_screenshot_data"
            
            def back(self):
                logger.info("⬅️ Mock: Went back")
            
            def forward(self):
                logger.info("➡️ Mock: Went forward")
            
            def refresh(self):
                logger.info("🔄 Mock: Refreshed page")
        
        class MockChromiumOptions:
            def set_argument(self, arg):
                pass
        
        # Create mock module
        mock_dp = Mock()
        mock_dp.ChromiumPage = MockChromiumPage
        mock_dp.ChromiumOptions = MockChromiumOptions
        
        # Create mock errors
        mock_errors = Mock()
        mock_errors.ElementNotFoundError = Exception
        mock_errors.PageDisconnectedError = Exception
        
        sys.modules['DrissionPage'] = mock_dp
        sys.modules['DrissionPage.errors'] = mock_errors
    
    async def load_tools(self):
        """Load all available tools."""
        try:
            from tools import get_all_tools
            self.tools = get_all_tools()
            logger.info(f"✅ Loaded {len(self.tools)} tools")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load tools: {e}")
            return False

    async def setup_context(self):
        """Setup DrissionPage context."""
        try:
            from context import DrissionPageContext
            self.context = DrissionPageContext()
            logger.info("✅ Context initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to setup context: {e}")
            return False
    
    async def test_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Test a specific tool."""
        # Find the tool
        tool = None
        for t in self.tools:
            if t.name == tool_name:
                tool = t
                break
        
        if not tool:
            logger.error(f"❌ Tool '{tool_name}' not found")
            return False
        
        try:
            # Validate arguments
            validated_args = tool.input_schema.model_validate(arguments)

            # Create response
            from response import ToolResponse
            response = ToolResponse()
            
            # Execute tool
            logger.info(f"🔧 Executing {tool_name}...")
            await tool.execute(self.context, validated_args, response)
            
            # Show results
            content = response.get_content()
            logger.info(f"✅ {tool_name} completed with {len(content)} response items")
            
            for i, item in enumerate(content[:3]):  # Show first 3 items
                preview = item.text[:100] + "..." if len(item.text) > 100 else item.text
                logger.info(f"  📄 Item {i+1}: {preview}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {e}")
            return False
    
    def show_available_tools(self):
        """Display all available tools."""
        print("\n🛠️ Available Tools:")
        print("=" * 50)
        
        categories = {}
        for tool in self.tools:
            category = tool.name.split('_')[0]
            if category not in categories:
                categories[category] = []
            categories[category].append(tool)
        
        for category, cat_tools in categories.items():
            print(f"\n📁 {category.upper()} ({len(cat_tools)} tools):")
            for tool in cat_tools:
                print(f"  • {tool.name}: {tool.description}")
    
    async def run_test_scenarios(self):
        """Run predefined test scenarios."""
        scenarios = [
            {
                "name": "Navigation Test",
                "tool": "page_navigate",
                "args": {"url": "https://www.example.com"}
            },
            {
                "name": "Screenshot Test", 
                "tool": "page_screenshot",
                "args": {"full_page": False}
            },
            {
                "name": "Element Click Test",
                "tool": "element_click",
                "args": {"selector": "#submit-button"}
            },
            {
                "name": "Element Find Test",
                "tool": "element_find",
                "args": {"selector": ".content"}
            },
            {
                "name": "Wait Test",
                "tool": "wait_for_element", 
                "args": {"selector": ".loading", "timeout": 5}
            }
        ]
        
        print("\n🧪 Running Test Scenarios:")
        print("=" * 50)
        
        passed = 0
        for scenario in scenarios:
            print(f"\n▶️ {scenario['name']}")
            success = await self.test_tool(scenario['tool'], scenario['args'])
            if success:
                passed += 1
                print("  ✅ PASSED")
            else:
                print("  ❌ FAILED")
        
        print(f"\n📊 Results: {passed}/{len(scenarios)} tests passed")
        return passed == len(scenarios)


async def interactive_mode(tester: LocalMCPTester):
    """Interactive testing mode."""
    print("\n🎮 Interactive Mode")
    print("=" * 30)
    print("Available commands:")
    print("  list          - Show all tools")
    print("  test <tool>   - Test a specific tool")
    print("  scenarios     - Run test scenarios")
    print("  quit          - Exit")
    
    while True:
        try:
            command = input("\n> ").strip().lower()
            
            if command == 'quit' or command == 'exit':
                break
            elif command == 'list':
                tester.show_available_tools()
            elif command == 'scenarios':
                await tester.run_test_scenarios()
            elif command.startswith('test '):
                tool_name = command[5:].strip()
                # Simple test with default args
                default_args = {
                    "page_navigate": {"url": "https://www.example.com"},
                    "page_screenshot": {"full_page": False},
                    "element_click": {"selector": "#button"},
                    "element_find": {"selector": "body"},
                    "wait_time": {"seconds": 1.0}
                }
                
                args = default_args.get(tool_name, {})
                await tester.test_tool(tool_name, args)
            else:
                print("❓ Unknown command. Try 'list', 'test <tool>', 'scenarios', or 'quit'")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"💥 Error: {e}")


async def main():
    """Main testing function."""
    print("🧪 DrissionPage MCP - Local Tester")
    print("=" * 50)
    
    # Initialize tester
    tester = LocalMCPTester()
    
    # Load tools
    if not await tester.load_tools():
        return
    
    # Setup context
    if not await tester.setup_context():
        return
    
    # Show available tools
    tester.show_available_tools()
    
    # Ask what to do
    print("\n🎯 Choose testing mode:")
    print("  1. Run test scenarios")
    print("  2. Interactive mode")
    print("  3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == '1':
        await tester.run_test_scenarios()
    elif choice == '2':
        await interactive_mode(tester)
    else:
        print("👋 Goodbye!")
    
    # Cleanup
    if tester.context:
        try:
            await tester.context.cleanup()
        except:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        sys.exit(1)