#!/usr/bin/env python3
"""
Quick Start - Test DrissionPage MCP Server locally

Simple test script to verify the MCP server functionality.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def test_tools():
    """Test that tools can be loaded."""
    try:
        from tools import get_all_tools
        tools = get_all_tools()
        logger.info(f"✅ Loaded {len(tools)} tools")
        for tool in tools[:3]:  # Show first 3 tools
            logger.info(f"   - {tool.name}: {tool.description}")
        if len(tools) > 3:
            logger.info(f"   ... and {len(tools) - 3} more tools")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to load tools: {e}")
        return False


async def main():
    """Main entry point."""
    logger.info("🧪 Testing DrissionPage MCP Server")
    
    # Test tools loading
    if not await test_tools():
        return
    
    logger.info("✅ All tests passed!")
    logger.info("🚀 To start the server: python -m drissionpage_mcp.cli")
    logger.info("📖 See mcp-config.json for configuration example")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        sys.exit(1)