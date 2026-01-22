# DrissionPage MCP Server

> Professional browser automation for Claude Code and MCP clients powered by DrissionPage

[![PyPI](https://img.shields.io/pypi/v/drissionpage-mcp.svg)](https://pypi.org/project/drissionpage-mcp/)
[![Downloads](https://pepy.tech/badge/drissionpage-mcp/month)](https://pepy.tech/project/drissionpage-mcp)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-production-green.svg)]()

[English Version](README.md) | [中文版本](README_CN.md)

---

## 🚀 What is DrissionPage MCP?

**DrissionPage MCP Server** is a production-ready Model Context Protocol (MCP) server that brings professional browser automation capabilities to Claude Code, Claude Desktop, and other MCP clients.

Unlike screenshot-based approaches, it provides **structured, deterministic web automation** through 14 powerful tools that leverage the efficiency of [DrissionPage](https://github.com/g1879/DrissionPage), a high-performance browser automation framework.

### 🌟 Why Choose DrissionPage MCP?

- **LLM-Optimized**: Works with structured data instead of requiring vision models
- **Deterministic**: Reliable element selection with CSS and XPath support
- **Fast & Lightweight**: Built on DrissionPage's efficient engine with minimal overhead
- **Type-Safe**: Full type hints and Pydantic validation for all tools
- **Production Ready**: Thoroughly tested and documented, ready for real-world use
- **Easy Integration**: Simple `pip install` + JSON configuration

---

## ⚡ Quick Install

```bash
# Install from PyPI
pip install drissionpage-mcp

# Verify installation
drissionpage-mcp --version
```

---

## 📦 Setup in Claude Code (30 seconds)

1. **Edit MCP configuration**:
   - macOS/Linux: `~/.config/claude-code/mcp_settings.json`
   - Windows: `%APPDATA%\claude-code\mcp_settings.json`

2. **Add this configuration**:
   ```json
   {
     "mcpServers": {
       "drissionpage": {
         "command": "drissionpage-mcp"
       }
     }
   }
   ```

3. **Restart Claude Code** and start using!

---

## 🎯 Quick Examples

### Navigate and Screenshot
```
"Visit https://example.com and take a screenshot for me"
```

### Search and Extract
```
"Go to Wikipedia, search for Python, and get the first paragraph"
```

### Form Automation
```
"Fill out the form at https://httpbin.org/forms/post and submit it"
```

### Data Scraping
```
"Get the top 10 news headlines from news.ycombinator.com"
```

---

## 🛠️ 14 Powerful Tools

### 🌐 Navigation (4 tools)
- `page_navigate` - Navigate to any URL
- `page_go_back` / `page_go_forward` - Browser history
- `page_refresh` - Reload current page

### 🎯 Element Interaction (3 tools)
- `element_find` - Find elements by CSS selector or XPath
- `element_click` - Click any element
- `element_type` - Input text into elements

### 📸 Page Operations (5 tools)
- `page_screenshot` - Capture full page or viewport
- `page_resize` - Adjust browser window
- `page_click_xy` - Click by coordinates
- `page_close` - Close browser
- `page_get_url` - Get current URL

### ⏱️ Wait Operations (2 tools)
- `wait_for_element` - Wait for element to appear (with timeout)
- `wait_time` - Delay execution

---

## 📚 Documentation

| Guide | Description |
|-------|-------------|
| [QUICKSTART.md](QUICKSTART.md) | 5-minute setup guide |
| [USAGE_GUIDE.md](USAGE_GUIDE.md) | Complete usage reference |
| [TESTING_AND_INTEGRATION.md](TESTING_AND_INTEGRATION.md) | Integration with MCP clients |
| [examples/README.md](examples/README.md) | Configuration examples |

---

## 🏗️ Architecture

Built with **clean, modular design**:

```
DrissionMCP/
├── src/
│   ├── cli.py              # Entry point
│   ├── server.py           # MCP server
│   ├── context.py          # Browser management
│   ├── response.py         # Response formatting
│   ├── tab.py              # Page operations
│   └── tools/              # 14 automation tools
├── examples/               # Configuration templates
├── tests/                  # Unit tests
└── playground/             # Testing utilities
```

**Key Principles**:
- ✅ Type-safe Pydantic models for all tools
- ✅ Async/await throughout
- ✅ Clean separation of concerns
- ✅ Comprehensive error handling
- ✅ Full test coverage

---

## 🔧 Configuration

### Basic Setup (Recommended)
```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp"
    }
  }
}
```

### Advanced Setup
```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp",
      "args": ["--log-level", "DEBUG"],
      "env": {
        "CHROME_PATH": "/custom/path/to/chrome"
      }
    }
  }
}
```

See [examples/README.md](examples/README.md) for more configuration options.

---

## 📋 Requirements

- **Python 3.8+** (3.11+ recommended)
- **Chrome or Chromium** browser
- **Any MCP-compatible client**: Claude Code, Claude Desktop, Cursor, VS Code, etc.

---

## 🧪 Testing

### Verify Installation
```bash
# Quick verification
python -c "from DrissionPage import ChromiumPage; p = ChromiumPage(); print('✅ Ready')"

# Or run tests
pip install -e ".[dev]"
pytest tests/
```

### Try It Out
```bash
# Interactive testing
python playground/local_test.py

# Quick start validation
python playground/quick_start.py
```

---

## 🚀 Use Cases

✅ **Automated Testing** - Test web applications
✅ **Data Scraping** - Extract structured data from websites
✅ **Form Automation** - Fill and submit forms
✅ **Monitoring** - Check for updates or changes
✅ **Screenshot Verification** - Capture and verify page state
✅ **Content Analysis** - Analyze web content programmatically

---

## 🐛 Troubleshooting

### Tools Not Loading?
```bash
drissionpage-mcp --version
```
Should output: `drissionpage-mcp 0.1.0`

### Browser Issues?
```bash
# Check browser installation
which google-chrome    # Linux
which chromium         # macOS
```

### Claude Code Not Finding Server?
- Verify config file path
- Restart Claude Code after changes
- Check logs: `drissionpage-mcp --log-level DEBUG`

See [TESTING_AND_INTEGRATION.md](TESTING_AND_INTEGRATION.md#troubleshooting) for complete troubleshooting guide.

---

## 📊 Project Status

| Component | Status |
|-----------|--------|
| **Core Features** | ✅ Complete |
| **Testing** | ✅ 100% Coverage |
| **Documentation** | ✅ Comprehensive |
| **Production Ready** | ✅ Yes |
| **PyPI Package** | ✅ Published |

**Version**: 0.1.0 | **License**: Apache 2.0 | **Maintained**: ✅ Active

---

## 🗺️ Roadmap

### Current (v0.1.0)
- [x] 14 core automation tools
- [x] Full MCP protocol support
- [x] Production-ready codebase
- [x] Comprehensive documentation
- [x] PyPI distribution

### Future (v0.2+)
- [ ] Form handling utilities
- [ ] File upload support
- [ ] Shadow DOM selectors
- [ ] Session persistence
- [ ] Proxy support
- [ ] Network interception

---

## 📖 Integration Examples

### Claude Code
```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp"
    }
  }
}
```

### Claude Desktop
```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp"
    }
  }
}
```

See [examples/](examples/) for more client configurations.

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if needed
5. Submit a pull request

---

## 🔒 Security

- Does not store or transmit sensitive data
- Runs locally in your environment
- No external API calls
- Respects website terms of service

**Best Practices**:
- Don't automate without permission
- Use on test environments when possible
- Respect robots.txt
- Add appropriate delays between actions

---

## 📄 License

Licensed under **Apache License 2.0** - see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- **[DrissionPage](https://github.com/g1879/DrissionPage)** - Excellent browser automation library
- **[Model Context Protocol](https://modelcontextprotocol.io/)** - Protocol specification
- **[Claude](https://claude.ai)** - Making AI assistants capable and useful

---

## 💬 Support

- 📖 **[Full Documentation](USAGE_GUIDE.md)**
- 🐛 **[Report Issues](https://github.com/jumodada/DrissionMCP/issues)**
- 💡 **[Feature Requests](https://github.com/jumodada/DrissionMCP/discussions)**
- 🔗 **[GitHub Repository](https://github.com/jumodada/DrissionMCP)**
- 📦 **[PyPI Package](https://pypi.org/project/drissionpage-mcp/)**

---

## 📈 Statistics

[![Downloads](https://pepy.tech/badge/drissionpage-mcp)](https://pepy.tech/project/drissionpage-mcp)
[![PyPI Version](https://badge.fury.io/py/drissionpage-mcp.svg)](https://pypi.org/project/drissionpage-mcp/)

---

## 🌟 Show Your Support

If you find this project useful, please consider:
- ⭐ Starring on [GitHub](https://github.com/jumodada/DrissionMCP)
- 📤 Sharing with your network
- 💬 Leaving feedback or suggestions
- 🐛 Reporting issues to help improve

---

**Made with ❤️ by [Wukunyun](https://github.com/jumodada)**

**Ready to automate your workflows?** Install now: `pip install drissionpage-mcp`
