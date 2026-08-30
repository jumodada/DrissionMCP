# DrissionPage MCP Server

> Professional browser automation for Codex, Claude Code, and MCP clients, powered by [DrissionPage](https://github.com/g1879/DrissionPage).
>
> DrissionPage is a Python web automation library built around direct Chromium/CDP control with requests-style HTTP session support. This server exposes its browser-facing capabilities as typed, atomic MCP tools.

[![PyPI](https://img.shields.io/pypi/v/drissionpage-mcp.svg?cacheSeconds=3600)](https://pypi.org/project/drissionpage-mcp/) [![Downloads](https://pepy.tech/badge/drissionpage-mcp/month)](https://pepy.tech/project/drissionpage-mcp) [![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) [![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![CI](https://github.com/jumodada/Drissionpage-MCP-Server/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jumodada/Drissionpage-MCP-Server/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/jumodada/Drissionpage-MCP-Server/branch/main/graph/badge.svg)](https://codecov.io/gh/jumodada/Drissionpage-MCP-Server) [![Status](https://img.shields.io/badge/status-beta-yellow.svg)]()

[![DrissionPage MCP interactive Browser Lab](https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/drissionpage-mcp-browser-lab.gif)](https://drissionpage-mcp.vercel.app)

**[Open the interactive Browser Lab](https://drissionpage-mcp.vercel.app)** to replay bounded natural pointer motion, drag controls, and verify observable state.

**Official Repositories**: [GitHub](https://github.com/jumodada/Drissionpage-MCP-Server) | [GitCode](https://gitcode.com/g1879/DrissionMCP)

[English Version](README.md) | [中文版本](README_CN.md)

## 🖱️ Atomic Browser Control with Natural Pointer Motion

**DrissionPage MCP 0.8.6 exposes 69 typed browser capabilities.** The MCP server provides accurate low-level observation and interaction; the client or an optional Skill composes those capabilities for a site, component library, challenge, or business workflow.

<!-- mcp-name: io.github.jumodada/drissionpage-mcp -->

> **The model decides what to do; the MCP executes the requested browser operation exactly.**

```text
Screenshot / page observation
        ↓
Multimodal model identifies viewport coordinates
        ↓
page_click_xy(x=442, y=369, profile="natural")
        ↓
24-step eased cubic path → exact target → press → release
        ↓
Observe and verify the resulting page state
```

### Core interaction guarantees

- **Two bounded profiles**: `direct` emits one exact move; `natural` emits a deterministic 24-step eased cubic path with reproducible 8-14ms intervals and exact final arrival.
- **No hidden randomness**: the same start, target, and profile produce the same path; there is no jitter, overshoot, or anti-detection logic. Pointer position is stateful, so a repeated call can begin from the previous endpoint.
- **Explicit sequences**: click is the selected move profile, optional caller-specified delay, press, release; drag keeps one press across the selected path and ordered waypoints.
- **Failure-safe input**: a pressed pointer button is released if execution fails after the press.
- **Fresh browser evidence**: selector geometry is resolved immediately before selector-backed drag operations.
- **Typed results**: outputs report the executed coordinates, button, step count, and explicit delay metadata.

Use structured DOM targets when reliable selectors exist. Use coordinates, `natural` motion, and explicit drag waypoints for canvas controls, editors, maps, charts, and other visual-only surfaces. Component-specific target discovery, challenge observation, multi-click sequencing, login procedures, and other business policy belong in the client or an optional Skill.

```json
{
  "x": 442,
  "y": 369,
  "profile": "natural",
  "button": "left",
  "element": "visually identified control"
}
```

Designed for authorized browser automation, testing, accessibility workflows, and technical research. The core does not provide challenge-specific or site-specific workflows.

## 🧭 Client Setup Navigation

- [Atomic browser control](#-atomic-browser-control-with-natural-pointer-motion)
- [Install + screenshot walkthrough](#-first-success-path)
- [Codex CLI/IDE quick setup](#-setup-in-codex-cliide-30-seconds)
- [Codex CLI/IDE integration example](#codex-cli--ide)
- [Skills and reusable procedures](#-skills-and-reusable-procedures)
- [Claude Code setup](#claude-code)
- [Cursor setup](#cursor)
- [Claude Desktop setup](#claude-desktop)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 What is DrissionPage MCP?

**DrissionPage MCP Server** is a local Model Context Protocol (MCP) server that brings DrissionPage browser automation tools to Codex CLI/IDE, Claude Code, Claude Desktop, and other MCP clients.

The standalone server exposes 69 typed tools, zero MCP prompts, and one static optional-Skills catalog resource. Version 0.8.6 keeps that registry stable, hardens public-response redaction, and isolates long network-listener waits from unrelated browser actions. Every tool loads by default; there is no capability profile or opt-in `full` mode. Models compose these atomic capabilities, while reusable challenge and site procedures live outside the distribution as optional Skills. Browser execution is powered by [DrissionPage](https://github.com/g1879/DrissionPage).

### 🌟 Why Choose DrissionPage MCP?

- **Structured-First, Vision-Ready**: Uses DOM structure when available and multimodal coordinates when visual interaction is the better tool
- **Deterministic**: Reliable element selection with CSS/XPath normalization for LLM-friendly selectors
- **Natural Pointer Motion**: Offers exact direct movement and a bounded deterministic 24-step eased trajectory from the same atomic tools
- **Fast & Lightweight**: Built on DrissionPage's efficient engine with minimal overhead
- **Type-Safe**: Full type hints and Pydantic validation for all tools
- **Open-source Friendly**: Includes compatibility notes, troubleshooting, and CI checks for maintainable contributions
- **Easy Integration**: Simple `pip install` + Codex TOML or MCP JSON configuration

### ✅ Quality and Real-World Validation

DrissionPage MCP is backed by a strict regression suite and browser-backed scenario checks:

- **Strict automated tests**: unit, protocol, schema snapshot, response-contract, resource, release-metadata, security-policy, browser-integration, and coverage checks run in CI.
- **95% coverage floor**: CI enforces the current 95% coverage threshold and uploads coverage reports.
- **Real browser verification**: Chrome/Chromium-backed integration tests exercise the same MCP tools exposed to clients.
- **Document-boundary verification**: focused browser tests prove cross-origin OOPIF reads and DrissionPage-exposed closed Shadow DOM lookup without JavaScript piercing fallbacks.
- **Challenge-surface verification**: local fixtures cover normal, hidden, off-viewport, delayed, and CSS 3D cross-origin widgets; official Turnstile dummy keys cover visible, invisible, pass, fail, and forced-interactive callbacks without retaining tokens.
- **Scenario validation**: the playground MCP Lab covers realistic forms, commerce pages, social feeds, timelines, dynamic waits, iframe cases, and recovery paths without depending on public demo websites.

---

## ⚡ First Success Path

```bash
# Install or update Codex CLI (macOS/Linux)
curl -fsSL https://chatgpt.com/codex/install.sh | sh

# Install from PyPI
python -m pip install -U "drissionpage-mcp>=0.8.6"

# Verify package and environment
drissionpage-mcp --version
drissionpage-mcp doctor
```

The official installer updates an existing Codex CLI installation as well. For
Windows and the Codex desktop app, see the [official Codex CLI and app
documentation](https://developers.openai.com/codex/cli/).

Then add the Codex or MCP client configuration below and restart your client.

<p align="center">
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/01-install.png" width="700" alt="pip install drissionpage-mcp">
  <br><br>
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/03-doctor.png" width="700" alt="drissionpage-mcp doctor — all checks green">
</p>

---

## 📦 Setup in Codex CLI/IDE (30 seconds)

Codex supports local stdio MCP servers through `config.toml`; the CLI and IDE extension share the same MCP configuration.

1. **Edit Codex configuration**:
   - User-level: `~/.codex/config.toml`
   - Project-level: `.codex/config.toml` inside a trusted project

2. **Add this configuration**:
   ```toml
   [mcp_servers.drissionpage]
   command = "drissionpage-mcp"
   startup_timeout_sec = 20
   tool_timeout_sec = 60
   ```

3. **Restart Codex**. In the TUI, run `/mcp`; from a shell, run `codex mcp list`.

<p align="center">
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/06-codex.png" width="700" alt="Codex config.toml">
</p>

For Claude Code, Claude Desktop, and other JSON-based MCP clients, see [Integration Examples](#-integration-examples).

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

## 🛠️ 69 Typed Browser Tools

### 🌐 Navigation (5 tools)
- `page_navigate` - Navigate to any URL; optionally open it in a new tab with `new_tab` or return an `observe` change summary
- `page_navigate_with_http_auth` - Navigate through a scoped HTTP auth challenge in a dedicated disposable Chromium context without returning credentials
- `page_go_back` - Navigate backward in browser history
- `page_go_forward` - Navigate forward in browser history
- `page_refresh` - Reload current page

### 🗂️ Tab Operations (3 tools)
- `tab_list` - List open browser tabs with stable MCP tab IDs
- `tab_switch` - Switch to a tab returned by `tab_list`
- `tab_close` - Close one tab without closing the whole browser

### 🎯 Element Interaction & Extraction (16 tools)
- `element_find` - Find one element by CSS selector or XPath; bare selectors like `h1` are treated as CSS
- `element_find_all` - Extract bounded repeated elements with text, attributes, and recommended selectors
- `element_click` - Click any element with additive left/right/middle and single/double-click semantics
- `element_click_and_download` - Correlate one selector, coordinate, or keyboard trigger with one integrity-checked artifact under `DP_MCP_DOWNLOAD_ROOT`
- `element_type` - Input text into elements
- `element_upload_file` - Use `element_upload_file(paths=[...])` to upload files from `DP_MCP_UPLOAD_ROOT` to `input[type=file]`
- `element_click_and_upload` - Arm Chromium's file chooser, click its trigger, inject approved files, and clean interception without an operating-system picker
- `element_scroll_into_view` - Bring an element into the viewport before acting
- `element_hover` - Hover an element to trigger menu/tooltip states
- `element_select` - Select an option by value, text, or index
- `element_check` - Check or uncheck checkbox/radio controls
- `element_get_text` - Get element or page text
- `element_get_attribute` - Get an HTML attribute
- `element_get_property` - Get a live DOM property such as an input value
- `element_get_html` - Get element or page HTML
- `element_state_get` - Read live DrissionPage state flags and document/viewport geometry for one element

### 📸 Page Operations (18 tools)
- `page_screenshot` - Capture an inline full-page or viewport screenshot
- `page_screenshot_save` - Save a screenshot under `DP_MCP_SCREENSHOT_ROOT`
- `page_export_artifact` - Generate a managed PDF or MHTML artifact under `DP_MCP_ARTIFACT_ROOT` with SHA-256 and receipt evidence
- `page_snapshot` - Return a bounded page outline with headings, links, buttons, inputs, forms, and selector recommendations
- `page_accessibility_snapshot` - Return a bounded Chromium accessibility tree for the page or a scoped element, with field values redacted unless explicitly requested
- `page_observe` - Return a compact page fingerprint with URL, title, counts, visible text samples, active element, and recent console summary
- `page_evaluate` - Run bounded JavaScript in the current page and return a JSON-safe result
- `page_scroll` - Use `page_scroll(pixels=...)` for relative scrolling, or pass `x`/`y` for an absolute position
- `keyboard_press` - Send keys to the active element/page without echoing the input in results
- `page_resize` - Adjust browser window
- `page_pointer_move` - Move to exact viewport CSS coordinates with `direct` or bounded deterministic `natural` motion
- `page_pointer_drag` - Perform one failure-safe coordinate drag through up to six optional ordered waypoints with the selected profile
- `page_pointer_drag_element` - Resolve source and destination geometry immediately before dragging; supports CSS/XPath in the top document or one same-origin iframe, plus CSS paths through nested open Shadow DOM hosts
- `page_click_xy` - Move with `direct` or `natural` motion, optionally wait for an explicit delay, then press and release at the exact target
- `page_close` - Close browser
- `page_get_url` - Get current URL
- `page_dialog_observe` - Wait for and inspect a pending native alert, confirm, or prompt without handling it
- `page_dialog_respond` - Use `page_dialog_respond(action="accept")` (or `"dismiss"`) for one pending alert, confirm, or prompt

### 🧱 Frame / Shadow DOM (5 tools)
- `frame_list` - List iframe/frame contexts without changing global frame state
- `frame_snapshot` - Use `frame_snapshot(frame_selector="...")` or `frame_index` to inspect one iframe with bounded outline data
- `frame_find` - Find an element inside a selected iframe
- `shadow_find` - Find one element inside a shadow root exposed by the current supported DrissionPage runtime, including tested closed roots
- `shadow_find_all` - Extract repeated elements from a DrissionPage-exposed shadow root

### 🌍 Browser Environment (6 tools)
- `browser_headers_set` - Replace extra request headers and return names with redacted values; an empty object clears them
- `browser_user_agent_set` - Override the user agent and optional platform, returning both the accepted and previous user agents
- `browser_cache_clear` - Clear HTTP cache while preserving Cookies, localStorage, and sessionStorage
- `browser_permission_get` - Query one browser permission for the current document origin without opening an OS prompt
- `browser_permission_set` - Use `browser_permission_set(setting="granted")` (or `"denied"`/`"prompt"`) for an exact origin/current Chromium context
- `browser_permissions_reset` - Reset permission overrides for the current Chromium context

### 🍪 Cookies & Storage (7 tools)
- `browser_cookies_get` - Read normalized cookies with values redacted by default
- `browser_cookies_set` - Set up to 100 cookies in one call and return accepted metadata with redacted values
- `browser_cookies_delete` - Delete one named cookie with optional URL/domain/path scope
- `browser_cookies_clear` - Clear all browser cookies
- `storage_get` - Read localStorage/sessionStorage by key or as a map, with values redacted unless `include_values=true`
- `storage_set` - Set one localStorage/sessionStorage item without echoing the value
- `storage_clear` - Clear one storage key or an entire storage area

### 🧪 Debug / Observability (1 tool)
- `page_console_logs` - Read bounded browser console messages with level filtering, cursor pagination, and limits

### ⏱️ Wait Operations (4 tools)
- `wait_for_element` - Wait for element to appear (with timeout)
- `wait_for_url` - Use `wait_for_url(url_pattern="...")` until the current URL contains the supplied text
- `wait_until` - Use `wait_until(condition="text_contains", value="...")` or another documented condition/value pair
- `wait_time` - Delay execution

### 🌐 Network Control & Observation (4 tools)
- `network_listen_start` - Start bounded HTTP/XHR/Fetch observation through DrissionPage
- `network_listen_wait` - Wait for bounded packet metadata with optional redacted headers or body excerpts
- `network_listen_stop` - Stop observation and optionally clear queued packets
- `network_blocked_urls_set` - Use `network_blocked_urls_set(urls=[...])` to replace blocked URL patterns; an empty list clears them

### 🧩 Optional Skills Discovery
- Resource: `drissionpage://skills/catalog`
- Prompts: none
- Repository examples: `cross-origin-iframe-probe`, `turnstile-testing`, and `xiaohongshu-content-research`
- Entry point: `skills/<skill-name>/SKILL.md`; catalog schema v2 includes Skill/MCP versions, required tools, fixture, fixed `v0.8.4` source revision, verification status, and SHA-256
- Skills are Markdown procedures for the MCP host. They are not Python modules, are not executed by the server, and are excluded from wheel/sdist packages.

Validate a source checkout with `python playground/validate_skills.py --json`.
Install the fixed catalog release from
[`skills-manager@v0.8.4`](https://github.com/jumodada/skills-manager/tree/v0.8.4)
with `python install.py install --client codex --json` or
`python install.py install --client claude --json`.

### 📖 Skills and Reusable Procedures

The MCP core exposes atomic browser operations. Skills provide reusable,
reviewable procedures outside the server:

| Example Skill | What it demonstrates | Stop boundary |
| --- | --- | --- |
| [`cross-origin-iframe-probe`](skills/cross-origin-iframe-probe/SKILL.md) | Frame discovery, cross-origin diagnosis, coordinate fallback, and outside verification | Cannot read the inner DOM of a cross-origin iframe |
| [`turnstile-testing`](skills/turnstile-testing/SKILL.md) | Cloudflare test fixtures, authorized production challenge interaction, coordinate geometry, and parent-page checks | Use the documented support matrix and verify the resulting page state |
| [`xiaohongshu-content-research`](skills/xiaohongshu-content-research/SKILL.md) | Bounded read-only note research and the deterministic `social-notes` fixture | Stop on robots, login, captcha, safety page, or rate limit |

Read the full [Skills guide](docs/skills.md) before publishing a new procedure.
Skills must use existing typed tools, collect fresh evidence, verify
postconditions, redact secrets, and state unsupported cases. They do not add
new MCP tools or override the server's navigation and safety policy.

---

## 📚 Documentation

| Guide | Description |
|-------|-------------|
| [README.md](README.md) | Installation, tools, and architecture |
| [docs/compatibility.md](docs/compatibility.md) | Supported Python, DrissionPage, MCP, and browser versions |
| [docs/tool-contract.md](docs/tool-contract.md) | Public MCP tool names, inputs, annotations, and response shape |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Doctor command, browser startup, and client setup fixes |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |

---

## 🏗️ Architecture

Built with **clean, modular design**:

```
DrissionMCP/
├── drissionpage_mcp/
│   ├── cli.py              # Process entry point
│   ├── server.py           # MCP transport and request routing
│   ├── context.py          # Browser and tab lifecycle facade
│   ├── runtime.py          # Operation keys, receipts, artifacts, and capability state
│   ├── tool_outputs.py     # Typed public result contracts
│   ├── browser/            # Focused DrissionPage capabilities and page scripts
│   └── tools/              # 69 typed MCP tool definitions and thin adapters
├── tests/                  # Unit tests
└── playground/             # MCP Lab business-scenario playground
```

**Key Principles**:
- ✅ Type-safe Pydantic models for all tools
- ✅ Async/await throughout
- ✅ Clean separation of concerns
- ✅ Comprehensive error handling
- ✅ Unit and protocol test coverage for core tool registration/response behavior

---

## 🔧 Configuration

### Codex CLI / IDE (Recommended)
```toml
[mcp_servers.drissionpage]
command = "drissionpage-mcp"
startup_timeout_sec = 20
tool_timeout_sec = 60

# Optional browser/runtime environment variables:
# [mcp_servers.drissionpage.env]
# CHROME_PATH = "/custom/path/to/chrome"
# DP_HEADLESS = "1"
```

You can also add it with the Codex CLI:

```bash
codex mcp add drissionpage -- drissionpage-mcp
```

If Codex/Cursor/Claude Desktop is launched from a GUI and cannot see your shell
`PATH` or virtualenv, use the absolute Python executable instead:

```toml
[mcp_servers.drissionpage]
command = "/absolute/path/to/python"
args = ["-m", "drissionpage_mcp.cli"]
startup_timeout_sec = 20
tool_timeout_sec = 60
```

### JSON MCP Clients
```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp"
    }
  }
}
```

### Advanced JSON Setup
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

Absolute-Python fallback for GUI clients:

```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "drissionpage_mcp.cli"],
      "env": {
        "CHROME_PATH": "/custom/path/to/chrome",
        "DP_HEADLESS": "1"
      }
    }
  }
}
```

---

## 📋 Requirements

- **Python 3.10+** (3.11+ recommended)
- **Chrome or Chromium** browser
- **Any MCP-compatible client**: Codex CLI/IDE, Claude Code, Claude Desktop, Cursor, VS Code, etc.

---

## 🧪 Testing

### Verify Installation
```bash
# Environment diagnostics; add --launch-browser for a browser startup check
drissionpage-mcp doctor
drissionpage-mcp doctor --launch-browser

# Source checkout tests
python -m pip install -e ".[dev]"
python -m pytest tests/

# Coverage report (CI enforces the current 95% floor and uploads coverage.xml)
python -m pytest tests/ --cov=drissionpage_mcp --cov-report=term-missing --cov-report=xml

# Browser-backed MCP Lab scenario checks
DP_HEADLESS=1 python playground/run_mcp_lab.py --all --json
```

GitHub Actions runs lint, unit, protocol, package, browser integration, and
coverage jobs. Codecov is configured through `codecov.yml` and the CI workflow.

### Try It Out
```bash
# No-browser MCP registry check
python playground/run_mcp_lab.py --case registry

# Local deterministic site check
python playground/run_mcp_lab.py --case site

# Browser-backed form inspection scenario
DP_HEADLESS=1 python playground/run_mcp_lab.py --case form-inspect
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
Should output the installed package version, for example `drissionpage-mcp 0.8.6`.

`drissionpage-mcp doctor` must also report both `mcp_supported` and
`mcp_server_wiring` as `ok`; package-version output alone does not prove that an
MCP client can initialize the server.

### Browser Issues?
```bash
# Check browser installation
which google-chrome    # Linux
which chromium         # macOS
```

### Codex / MCP Client Not Finding Server?
- Codex: run `codex mcp list`; in the TUI, run `/mcp`
- JSON clients: verify config file path and JSON syntax
- Restart Codex or your MCP client after changes
- Check logs: `drissionpage-mcp --log-level DEBUG`

See [docs/troubleshooting.md](docs/troubleshooting.md) for the complete troubleshooting guide.

---

## 📊 Project Status

| Component | Status |
|-----------|--------|
| **Core Features** | ✅ Complete |
| **Testing** | ✅ Strict unit/protocol/schema checks plus browser-backed scenarios |
| **Documentation** | ✅ Setup, compatibility, troubleshooting, and public tool contracts |
| **Package** | ✅ PyPI metadata and build checks |
| **Status** | 🟡 Beta; real browser behavior depends on local Chrome/Chromium and target sites |

**Version**: 0.8.6 | **License**: Apache 2.0 | **Maintained**: ✅ Active

---

## 🗺️ Roadmap

### Current (v0.8.6)
- [x] 69 atomic navigation, tab/frame/shadow, accessibility, observation, interaction, browser-environment, network, Cookie/storage, wait, and console tools, all loaded by default
- [x] stdio MCP server integration
- [x] Doctor diagnostics for local setup
- [x] Stable JSON mirror, `structuredContent`, and typed per-tool MCP `outputSchema`
- [x] Structured recovery hints in `error.details.hints` for common failures
- [x] Sanitized browser failures with `DIALOG_PENDING`/`DIALOG_NOT_FOUND` recovery and strict standards-compliant JSON for non-finite JavaScript values
- [x] Balanced `page_snapshot` output so link-heavy pages still expose controls and forms
- [x] Atomic type, select, check, click, keyboard, upload, wait, and state-read tools cover native controls and framework-driven widgets without library-specific branches
- [x] Tab management with `tab_list`, `tab_switch`, `tab_close`, and `page_navigate(new_tab=true)`
- [x] Observable actions with `page_observe`, `page_evaluate`, `wait_until`, and optional `observe=true` changes on navigation, click, and type
- [x] Console observability with `page_console_logs`, console summary in `page_observe`, and console change fields in `observe=true`
- [x] Form, component-library, challenge, and convenience workflows remain outside the MCP core
- [x] Repository example Skills for cross-origin iframes, authorized Turnstile fixtures, and bounded Xiaohongshu-like research are discoverable through the static catalog and excluded from wheel/sdist packages
- [x] Capability-probed `page_dialog_respond`, additive double/context click behavior, and selector/coordinate/keyboard download correlation with safe `ArtifactRef` metadata
- [x] Secret-bearing Web Storage values require `include_values=true`; keyboard and keyboard-download results expose redacted metadata only
- [x] Per-tab download trigger locking, shared deadlines, cleanup/replay guarantees, and a 250ms fail-closed late-mission guard
- [x] Reproducible W01-W08 public-tool benchmark with ten isolated runs per workload, machine-readable evidence, and zero duplicate side effects
- [x] Network listener beta with `network_listen_start`, `network_listen_wait`, and `network_listen_stop` for HTTP/XHR/Fetch observation
- [x] Public-response redaction for URLs, credentials, headers, Cookies, network bodies, errors, receipts, and text mirrors; listener waits are isolated from unrelated browser actions
- [x] Browser-only request environment control with redacted header, user-agent, and blocked-URL write results plus cache-only clearing that preserves Cookies and Web Storage
- [x] `direct` and deterministic bounded `natural` profiles for `page_pointer_move`, `page_pointer_drag`, and `page_click_xy`, with exact endpoints and failure-safe release
- [x] Optional bounded `page_pointer_drag.waypoints` for one held multi-segment canvas, map, box-selection, or visual-editor gesture
- [x] File upload, scrolling, hover, select/check, keyboard, iframe, shadow DOM, cookie, and storage tools for DrissionPage 4.x
- [x] Pure browser Cookie set/get/delete/clear flow, including bounded batch writes whose successful results retain metadata with redacted values
- [x] Ten-cycle controlled and validation input replacement through native DrissionPage input on the supported browser matrix
- [x] Cross-origin OOPIF reads through `frame_*` and closed Shadow DOM lookup through DrissionPage-backed `shadow_*`, with narrower pointer targeting documented separately
- [x] Frame boundary/document-access classification plus outer presentation, top-level viewport coordinate, scroll receipt, and coordinate-actionability evidence for production challenge workflows
- [x] Local challenge-surface and opt-in official Turnstile test-key benchmarks with parent-page postconditions, screenshots, and token-safe evidence
- [x] Backward-compatible string or structured selector/accessibility targets across element reads, actions, waits, uploads, and click-download correlation, resolving ordered frames first and then ordered Shadow DOM hosts
- [x] Bounded accessibility snapshots, non-handling native dialog observation, and live element state/geometry for autonomous locate-act-verify loops
- [x] Browser permission observation/set/reset, managed PDF/MHTML artifacts, automatic file chooser interception, and credential-redacted HTTP auth isolated by disposable Chromium context
- [x] Chrome sandbox remains enabled by default; `DP_NO_SANDBOX=1` is reserved for restricted container/root environments
- [x] No retained action history, generated code snippets, or absolute screenshot paths in public results
- [x] Opt-in local safety policy for navigation and screenshot paths
- [x] One optional-Skills catalog resource with repository example metadata, zero prompts, plus Skills, eval, compatibility, and troubleshooting documentation
- [x] PyPI distribution
- [x] Official MCP Registry package metadata and tag-gated publishing workflow

---

## 📖 Integration Examples

### Codex CLI / IDE
```toml
[mcp_servers.drissionpage]
command = "drissionpage-mcp"
startup_timeout_sec = 20
tool_timeout_sec = 60
```

Verify with:

```bash
codex mcp list
```

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

Config file: `~/.config/claude-code/mcp_settings.json` (macOS/Linux) or
`%APPDATA%\claude-code\mcp_settings.json` (Windows).

<p align="center">
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/04-claude-code.png" width="700" alt="Claude Code mcp_settings.json">
</p>

### Cursor
```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp"
    }
  }
}
```

Config file: `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project). You
can also add it from **Cursor Settings → Tools & MCPs → New MCP Server**.

<p align="center">
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/05-cursor.png" width="700" alt="Cursor mcp.json">
  <br><br>
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/08-cursor-ui.png" width="540" alt="Cursor Settings — add a new MCP server">
</p>

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

Once connected, the tools load automatically:

<p align="center">
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/07-connected.png" width="700" alt="MCP client with DrissionPage tools loaded">
</p>

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Make focused changes
4. Run the relevant checks
5. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, validation, and compatibility expectations.

---

## 🔒 Security

- Runs locally in your environment
- Uses a local browser that may have access to authenticated sessions, cookies, downloads, and page content
- Can open and interact with any site reachable from the local machine
- Does not require external API credentials

**Best Practices**:
- Use a dedicated browser profile for sensitive workflows
- Review MCP client prompts before allowing actions on authenticated or production systems
- Respect website terms of service, robots.txt, and rate limits
- See [SECURITY.md](SECURITY.md) for reporting and safe-usage guidance

---

## 📄 License

Licensed under **Apache License 2.0** - see [LICENSE](LICENSE)

---

## 📈 Statistics

[![Downloads](https://pepy.tech/badge/drissionpage-mcp)](https://pepy.tech/project/drissionpage-mcp)
[![PyPI Version](https://img.shields.io/pypi/v/drissionpage-mcp.svg?cacheSeconds=3600)](https://pypi.org/project/drissionpage-mcp/)

---

## 🌟 Show Your Support

If you find this project useful, please consider:
- ⭐ Starring on [GitHub](https://github.com/jumodada/Drissionpage-MCP-Server)
- 📤 Sharing with your network
- 💬 Leaving feedback or suggestions
- 🐛 Reporting issues to help improve

---

**Made with ❤️ by [Wukunyun](https://github.com/jumodada)**

**Ready to automate your workflows?** Install now: `python -m pip install -U drissionpage-mcp`

---

## 🆕 Latest Version: v0.8.6

Released on 2026-08-30. This release keeps the existing 69-tool browser capability contract while hardening privacy and listener concurrency:

- Applies one redaction boundary to public URLs, credentials, headers, Cookie writes, network bodies, errors, receipts, and text mirrors.
- Returns metadata-only results for header and Cookie writes, preventing configured values from being echoed into MCP responses.
- Keeps `network_listen_wait` out of the global action lock and serializes listener lifecycle state per tab, while preserving the existing cleanup and replay contracts.
- Keeps the public surface at 69 tools, zero prompts, and one Skills catalog resource. The external Skills catalog remains pinned to `skills-manager` `v0.8.4`.
