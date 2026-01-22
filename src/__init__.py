"""DrissionPage MCP - DrissionPage Tools for Model Context Protocol."""

__version__ = "0.1.0"
__author__ = "DrissionPage MCP Team"
__license__ = "Apache-2.0"

# Lazy imports to avoid dependency issues during development
def _get_server():
    from .server import DrissionPageMCPServer
    return DrissionPageMCPServer

def _get_context():
    from .context import DrissionPageContext
    return DrissionPageContext

def _get_tab():
    from .tab import PageTab
    return PageTab

__all__ = [
    "__version__",
    "__author__", 
    "__license__",
]