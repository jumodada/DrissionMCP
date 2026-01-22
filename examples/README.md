# Configuration Examples

This directory contains configuration examples for different MCP clients and installation methods.

## 📁 Files

### For Source Installation (Development)

- **`claude-code-config.json`** - Configuration for Claude Code CLI
- **`claude-desktop-config.json`** - Configuration for Claude Desktop App

**Usage**:
1. Clone the repository and install in development mode
2. Copy the appropriate config file
3. Replace `<REPLACE_WITH_YOUR_DRISSIONMCP_PATH>` with your actual project path
4. Add the configuration to your MCP settings file

**Example**:
```bash
# Install in development mode
git clone https://github.com/your-username/DrissionMCP.git
cd DrissionMCP
pip install -e .

# For Claude Code
# Edit: ~/.config/claude-code/mcp_settings.json
# Copy content from claude-code-config.json and replace path
```

---

### For PyPI Installation (Recommended)

- **`pypi-install-config.json`** - Configuration after installing from PyPI

**Usage**:
1. Install the package from PyPI
2. Copy the configuration content
3. Add to your MCP settings file
4. No need to specify `cwd` - it works globally!

**Example**:
```bash
# Install from PyPI
pip install drissionpage-mcp

# For Claude Code
# Edit: ~/.config/claude-code/mcp_settings.json
# Copy content from pypi-install-config.json
```

---

## 🗂️ Configuration File Locations

### Claude Code
- **macOS/Linux**: `~/.config/claude-code/mcp_settings.json`
- **Windows**: `%APPDATA%\claude-code\mcp_settings.json`

### Claude Desktop
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

---

## 🚀 Quick Setup

### Method 1: From PyPI (Recommended for Users)

```bash
# 1. Install
pip install drissionpage-mcp

# 2. Add to Claude Code config
cat examples/pypi-install-config.json >> ~/.config/claude-code/mcp_settings.json

# 3. Restart Claude Code
```

### Method 2: From Source (Recommended for Developers)

```bash
# 1. Clone and install
git clone https://github.com/your-username/DrissionMCP.git
cd DrissionMCP
pip install -e .

# 2. Copy config and edit path
cp examples/claude-code-config.json temp-config.json
# Edit temp-config.json and replace <REPLACE_WITH_YOUR_DRISSIONMCP_PATH>

# 3. Add to your MCP settings
cat temp-config.json >> ~/.config/claude-code/mcp_settings.json

# 4. Restart Claude Code
```

---

## 🔧 Configuration Options

### Basic Configuration

```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp"
    }
  }
}
```

### Advanced Configuration with Environment Variables

```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "python",
      "args": ["-m", "src.cli", "--log-level", "DEBUG"],
      "cwd": "/path/to/DrissionMCP",
      "env": {
        "CHROME_PATH": "/custom/path/to/chrome",
        "LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

### Options Explanation

- **`command`**: The command to start the MCP server
  - PyPI install: `"drissionpage-mcp"`
  - Source install: `"python"`

- **`args`**: Command line arguments
  - `["-m", "src.cli"]` - Run as Python module
  - `["--log-level", "DEBUG"]` - Set logging level

- **`cwd`**: Working directory (required for source installation)
  - Absolute path to your DrissionMCP project directory

- **`env`**: Environment variables
  - Custom browser path, logging configuration, etc.

---

## ✅ Verify Installation

After configuration, test your setup:

```bash
# In Claude Code, try:
"Use DrissionPage to navigate to https://example.com and take a screenshot"

# Or test manually:
python playground/quick_start.py
```

---

## 🐛 Troubleshooting

### Config not loading?
- Check file path is correct
- Ensure JSON syntax is valid (use jsonlint.com)
- Restart Claude Code/Desktop after changes

### Server not starting?
- Verify Python and dependencies are installed
- Check the `cwd` path exists (for source installation)
- Try running manually: `python -m src.cli --log-level DEBUG`

### Tools not appearing?
- Ensure server started successfully
- Check Claude Code logs
- Verify the configuration was added to the right JSON file

---

## 📚 More Information

- [Main README](../README.md)
- [Testing Guide](../TESTING_AND_INTEGRATION.md)
- [Quick Start](../QUICKSTART.md)
- [Publishing Guide](../PUBLISHING.md)
