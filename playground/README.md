# Playground - DrissionPage MCP Testing

This playground provides testing utilities for DrissionPage MCP.

## 🚀 Quick Start

### 1. Test Server
```bash
# Test tools loading
python playground/quick_start.py
```

### 2. Start MCP Server
```bash
# From project root
python -m drissionpage_mcp.cli
```

### 3. Test Locally (No MCP Client Required)
```bash
# Interactive testing
python playground/local_test.py
```

## 🧪 Test Scenarios

### Navigation Testing
```bash
python playground/test_scenarios/basic_navigation.py
```

### Form Interaction
```bash  
python playground/test_scenarios/form_interaction.py
```

### Data Extraction
```bash
python playground/test_scenarios/data_extraction.py
```

## 🤖 MCP Client Integration

### Setup Steps

1. **Start MCP Server**
   ```bash
   python -m drissionpage_mcp.cli
   ```

2. **Copy Configuration**
   See `mcp-config.json` in the project root for configuration example.
   Add it to your MCP client configuration:
   - **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **VS Code**: See project README for setup instructions

3. **Restart MCP Client**

4. **Test Commands**
   ```
   "Navigate to https://httpbin.org/html and take a screenshot"
   "Click the first link on the page"
   "Get all text from the page"
   ```

### Example Commands for Claude Code

#### Basic Navigation
```
Navigate to https://www.example.com
Take a screenshot of the current page
Get the current page URL
Go back to the previous page
```

#### Element Interaction  
```
Click the element with text 'Submit'
Input 'test@example.com' into the email field
Get the text content of the first paragraph
Click at coordinates (100, 200)
```

#### Data Extraction
```
Get all text from the page
Get the HTML content of the main content area
Get the href attribute of all links
Get text from elements with class 'article-title'
```

#### Wait Operations
```
Wait for an element with class 'loading' to appear
Wait for the URL to contain 'success'  
Sleep for 3 seconds
```

## 📁 File Structure

```
playground/
├── README.md                    # This file
├── quick_start.py              # Server testing utility
├── local_test.py               # Local testing without MCP client
└── test_scenarios/             # Test scenario scripts
    ├── basic_navigation.py     # Navigation tests
    ├── form_interaction.py     # Form filling tests
    └── data_extraction.py      # Data scraping tests
```

## 🛠️ Available MCP Tools

### Navigation (4 tools)
- `page_navigate`: Navigate to URL
- `page_go_back`: Go back in history  
- `page_go_forward`: Go forward in history
- `page_refresh`: Refresh current page

### Element Interaction (5 tools)
- `element_click`: Click element by selector
- `element_input_text`: Input text into fields
- `element_get_text`: Extract text content
- `element_get_attribute`: Get element attributes  
- `element_get_html`: Get HTML content

### Common Actions (5 tools)
- `page_screenshot`: Take screenshots
- `page_resize`: Resize browser window
- `page_click_xy`: Click at coordinates
- `page_close`: Close browser
- `page_get_url`: Get current URL

### Wait Operations (3 tools)
- `wait_for_element`: Wait for element to appear
- `wait_for_url`: Wait for URL pattern
- `wait_sleep`: Simple time delay

## 🎯 Testing Tips

### Good Test Websites
- **https://httpbin.org/html** - Simple HTML testing
- **https://httpbin.org/forms/post** - Form testing
- **https://quotes.toscrape.com/** - Scraping practice
- **https://the-internet.herokuapp.com/** - Various UI elements

### Common Selectors to Test
- `h1` - Tag selector
- `.class-name` - Class selector
- `#element-id` - ID selector  
- `[attribute="value"]` - Attribute selector
- `div > p` - Child combinator
- `:first-child` - Pseudo selector

### Debug Mode
Start server with debug logging:
```bash
python -m drissionpage_mcp.cli --log-level DEBUG
```

## ❓ Troubleshooting

### Server Won't Start
1. Check dependencies: `pip install -r requirements.txt`
2. Verify Python version: `python --version` (need 3.8+)
3. Check Chrome installation

### MCP Client Can't Connect
1. Verify config file path and format
2. Restart MCP client after config changes
3. Check server is running: `python -m drissionpage_mcp.cli`

### Tools Not Working
1. Test locally first: `python playground/local_test.py`
2. Check browser is installed and accessible
3. Verify network permissions

## 💡 Pro Tips

- Start with simple navigation before complex interactions
- Use screenshots to debug element selection issues  
- Test selectors in browser dev tools first
- Use wait operations for dynamic content
- Check the local_test.py output for debugging

Happy testing! 🎉