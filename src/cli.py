"""Command line interface for DrissionPage MCP Server."""

import asyncio
import argparse
import logging
import sys
from typing import Optional

try:
    from mcp.server.stdio import stdio_server
except ImportError:
    # Fallback for different MCP SDK versions
    from mcp.server import stdio_server

from .server import DrissionPageMCPServer

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def main_async(args: Optional[list[str]] = None) -> None:
    """Main async function."""
    parser = argparse.ArgumentParser(
        description="DrissionPage MCP Server - Web automation tools for MCP",
        prog="drissionpage-mcp"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set the logging level"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )
    
    parsed_args = parser.parse_args(args)
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, parsed_args.log_level))
    
    # Create the MCP server
    server = DrissionPageMCPServer()
    
    # Run with stdio transport
    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("🚀 Starting DrissionPage MCP Server...")
            logger.info("📊 Server ready for MCP connections")
            await server.run_server(read_stream, write_stream)
    except KeyboardInterrupt:
        logger.info("👋 Server interrupted by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        raise
    finally:
        logger.info("🧹 Cleaning up...")
        await server.cleanup()


def main(args: Optional[list[str]] = None) -> None:
    """Main entry point."""
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()