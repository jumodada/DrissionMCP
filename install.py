#!/usr/bin/env python3
"""
Installation helper for DrissionPage MCP Server

This script helps you configure Claude Code or Claude Desktop with DrissionPage MCP.
"""

import json
import os
import sys
from pathlib import Path


def find_config_file():
    """Find the appropriate MCP configuration file."""
    home = Path.home()

    # Try Claude Code first
    claude_code_configs = [
        home / ".config" / "claude-code" / "mcp_settings.json",  # Linux/macOS
        Path(os.environ.get("APPDATA", "")) / "claude-code" / "mcp_settings.json",  # Windows
    ]

    # Try Claude Desktop
    claude_desktop_configs = [
        home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",  # macOS
        Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json",  # Windows
        home / ".config" / "Claude" / "claude_desktop_config.json",  # Linux
    ]

    # Check if any exist
    for config_path in claude_code_configs + claude_desktop_configs:
        if config_path.exists():
            return config_path

    # If none exist, suggest Claude Code config
    return claude_code_configs[0] if sys.platform != "win32" else claude_code_configs[1]


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.resolve()


def create_config(config_path, project_root, use_pypi=False):
    """Create or update the MCP configuration."""

    if use_pypi:
        server_config = {
            "command": "drissionpage-mcp"
        }
    else:
        server_config = {
            "command": "python",
            "args": ["-m", "src.cli"],
            "cwd": str(project_root)
        }

    # Load existing config or create new
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            config = {"mcpServers": {}}
    else:
        config = {"mcpServers": {}}

    # Ensure mcpServers exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Add drissionpage server
    config["mcpServers"]["drissionpage"] = server_config

    return config


def main():
    """Main installation function."""
    print("🚀 DrissionPage MCP Installation Helper")
    print("=" * 50)

    # Detect config file
    config_path = find_config_file()
    print(f"\n📁 Config file: {config_path}")

    # Check if config exists
    if config_path.exists():
        print("✅ Config file exists")
    else:
        print("⚠️  Config file doesn't exist - will create it")
        config_path.parent.mkdir(parents=True, exist_ok=True)

    # Ask installation method
    print("\n📦 Installation Method:")
    print("  1. From PyPI (recommended for users)")
    print("  2. From source (recommended for developers)")
    choice = input("\nChoose (1 or 2): ").strip()

    use_pypi = (choice == "1")

    if not use_pypi:
        project_root = get_project_root()
        print(f"\n📂 Project root: {project_root}")
    else:
        project_root = None
        print("\n⚠️  Make sure you've installed the package first:")
        print("   pip install drissionpage-mcp")
        proceed = input("\nHave you installed it? (y/n): ").strip().lower()
        if proceed != 'y':
            print("\n❌ Please install first, then run this script again")
            return

    # Create config
    print("\n⚙️  Creating configuration...")
    config = create_config(config_path, project_root, use_pypi)

    # Ask for confirmation
    print("\n📝 Configuration to be written:")
    print(json.dumps(config, indent=2))

    confirm = input("\n✅ Write this configuration? (y/n): ").strip().lower()

    if confirm != 'y':
        print("\n❌ Installation cancelled")
        return

    # Write config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n✅ Configuration written to: {config_path}")

    # Next steps
    print("\n🎯 Next Steps:")
    print("  1. Restart Claude Code/Desktop")
    print("  2. Test with: 'Use DrissionPage to navigate to example.com'")
    print("\n📖 For more help, see: QUICKSTART.md")
    print("\n🎉 Installation complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Installation cancelled")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
