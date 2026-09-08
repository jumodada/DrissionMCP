# MCP Tool Contract

This document summarizes the public MCP tool contract exposed by DrissionPage MCP.

## Transport

DrissionPage MCP runs as a local stdio MCP server. MCP clients start the server process and communicate through standard input/output.

Minimal Codex CLI/IDE configuration (`~/.codex/config.toml`, or project `.codex/config.toml` in a trusted project):

```toml
[mcp_servers.drissionpage]
command = "drissionpage-mcp"
startup_timeout_sec = 20
tool_timeout_sec = 60
```

Minimal JSON MCP client configuration:

```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp"
    }
  }
}
```

Codex source checkout configuration:

```toml
[mcp_servers.drissionpage]
command = "python"
args = ["-m", "drissionpage_mcp.cli"]
cwd = "/absolute/path/to/DrissionMCP"
startup_timeout_sec = 20
tool_timeout_sec = 60
```

JSON source checkout configuration:

```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "python",
      "args": ["-m", "drissionpage_mcp.cli"],
      "cwd": "/absolute/path/to/DrissionMCP"
    }
  }
}
```

## Response Shape

Tools return MCP content blocks plus a stable machine-readable result payload:

- The first text item starts with `### JSON_RESULT` and contains a fenced JSON object.
- When supported by the active MCP Python SDK, the same object is also returned as `structuredContent`.
- When supported by the active MCP Python SDK, each listed tool exposes a typed
  `outputSchema` envelope with a tool-specific success `data` schema.
- Successful results use `ok: true`; tool-execution failures use `ok: false` with `error.code` and `error.message`.
- Failure details may include `hints`: a list of machine-readable next steps with
  stable `action` identifiers and optional `tool`, `command`, or `env` fields.
- Human-readable MCP text content still follows as `### Result` or `### Error` blocks.
- Screenshots include `ImageContent` with PNG data plus the JSON result block.
- Successful tab-scoped tools include the resolved MCP `tab_id` in `data`, and
  their public `outputSchema` requires that non-empty string.
- Tool input schemas reject unknown fields. Typos such as `fullPage` instead of
  `full_page` return `MCP_ARGUMENT_INVALID` instead of being silently ignored.

Example failure payload:

```json
{
  "ok": false,
  "message": "Tool 'missing' not found",
  "error": {
    "code": "TOOL_NOT_FOUND",
    "message": "Tool 'missing' not found",
    "details": {
      "tool_name": "missing",
      "hints": [
        {
          "action": "list_available_tools",
          "message": "Call tools/list and use one of the public tool names."
        }
      ]
    }
  }
}
```

All tools share this base output envelope, while success `data` is typed per tool:

```json
{
  "ok": true,
  "message": "Operation completed successfully.",
  "data": {}
}
```

For failures, `error` contains `code`, `message`, and optional `details`.
Common runtime failures include structured recovery hints under
`error.details.hints`; for example, `ELEMENT_NOT_FOUND` can suggest
`page_snapshot`, `element_find_all`, `wait_for_element`, and iframe/dynamic
content checks.

Stable tool-execution error codes include `BROWSER_START_FAILED`, `BROWSER_NOT_INITIALIZED`, `PAGE_NAVIGATION_FAILED`, `ELEMENT_NOT_FOUND`, `SELECTOR_INVALID`, `TIMEOUT`, `DIALOG_PENDING`, `DIALOG_NOT_FOUND`, `TAB_NOT_FOUND`, `TAB_CLOSED`, `SCREENSHOT_FAILED`, `POLICY_DENIED`, `UNSUPPORTED_OPERATION`, and `UNKNOWN_ERROR`. Public messages are normalized by the MCP server and do not reflect DrissionPage version suffixes, localized runtime text, CDP object IDs, stack payloads, or raw internal exception dictionaries. Protocol/validation diagnostics use `TOOL_NOT_FOUND` and `MCP_ARGUMENT_INVALID` where the SDK permits stable diagnostic data.

## Tool Annotations

The server marks tools with MCP annotations:

- Read-only tools use `readOnlyHint=true`.
- Browser or page mutation tools use `destructiveHint=true`.
- Advisory idempotent operations use `idempotentHint=true` where supported by the SDK.
- Tools operate on the open web, so `openWorldHint=true` is set.

## Common Call Examples

The Pydantic schema returned by `tools/list` is the source of truth. The objects
below show complete `arguments` payloads for fields that are easy to guess
incorrectly from a short tool description.

Target an existing tab by the stable MCP id returned from `tab_list` or any
successful tab-scoped call:

```json
{"tab_id": "t1", "selector": "#save"}
```

Omitting `tab_id` captures the current tab once at call start. A later
`tab_switch` cannot redirect that in-flight call. To create a background tab in
a disposable Chromium context, creation options require `new_tab: true` and
cannot be combined with an existing `tab_id`:

```json
{"url": "https://example.com", "new_tab": true, "background": true, "new_context": true}
```

Use `url_pattern` with `wait_for_url`:

```json
{"url_pattern": "/dashboard", "timeout": 10}
```

For text waits, `wait_until` uses an exact condition name plus `value`:

```json
{"condition": "text_contains", "selector": "#status", "value": "Ready", "timeout": 10}
```

Dialog response uses `action`, not a boolean `accept` field:

```json
{"action": "accept"}
```

The default `timeout: 0` checks immediately. Set a positive timeout only when the
response call must overlap an action that has not opened the dialog yet.

Relative page scrolling uses `pixels`:

```json
{"direction": "down", "pixels": 600}
```

Frame selection is explicit and stateless:

```json
{"frame_selector": "iframe#checkout"}
```

Uploads accept a list named `paths`, even for one file:

```json
{"selector": "input[type=file]", "paths": ["/approved-upload-root/report.csv"]}
```

Blocked URL replacement uses `urls`, and an empty list clears the override:

```json
{"urls": ["*analytics*", "*tracking.gif*"]}
```

Permission mutation uses `setting`:

```json
{"permission": "notifications", "setting": "granted"}
```

`page_pointer_drag_element` accepts a symmetric tagged source and destination.
For an offset destination, `dx` and `dy` are deltas from the freshly resolved
source point:

```json
{
  "source": {"kind": "element", "target": {"selector": "#thumb"}},
  "destination": {"kind": "offset", "dx": 120, "dy": 0},
  "profile": "direct"
}
```

Legacy bare `source` and offset `x`/`y` inputs remain accepted for compatibility.

Relative screenshot paths resolve beneath the configured root:

```json
{"path": "reports/home.png", "full_page": true}
```

<!-- GENERATED:TOOL-PARAMETERS:START -->
## Schema-derived Tool Parameters

This table is generated from the strict Pydantic input schemas exposed by `tools/list`. Do not edit rows manually; run `UPDATE_TOOL_CONTRACT=1 python -m pytest tests/test_tool_schema_snapshot.py -q` after an intentional schema change.

| Tool | Required parameters | Optional parameters |
| --- | --- | --- |
| `page_navigate` | `url: string` | `tab_id: string / null = null`<br>`new_tab: boolean = false`<br>`background: boolean = false`<br>`new_window: boolean = false`<br>`new_context: boolean = false`<br>`observe: boolean = false` |
| `page_navigate_with_http_auth` | `url: string`<br>`username: string`<br>`password: string` | `realm: string / null = null`<br>`timeout: number = 30.0` |
| `page_go_back` | — | `tab_id: string / null = null` |
| `page_go_forward` | — | `tab_id: string / null = null` |
| `page_refresh` | — | `tab_id: string / null = null` |
| `tab_list` | — | — |
| `tab_switch` | `tab_id: string` | — |
| `tab_close` | `tab_id: string` | — |
| `page_resize` | `width: integer`<br>`height: integer` | `tab_id: string / null = null` |
| `page_screenshot` | — | `tab_id: string / null = null`<br>`full_page: boolean = false` |
| `page_screenshot_save` | `path: string` | `tab_id: string / null = null`<br>`full_page: boolean = false` |
| `page_export_artifact` | `format: string` | `tab_id: string / null = null`<br>`filename: string / null = null`<br>`operation_key: string / null = null`<br>`landscape: boolean = false`<br>`print_background: boolean = true`<br>`scale: number = 1.0`<br>`paper_width: number / null = null`<br>`paper_height: number / null = null`<br>`margin_top: number = 0.4`<br>`margin_bottom: number = 0.4`<br>`margin_left: number = 0.4`<br>`margin_right: number = 0.4`<br>`page_ranges: string = ""`<br>`prefer_css_page_size: boolean = false` |
| `page_snapshot` | — | `tab_id: string / null = null`<br>`include_html: boolean = false`<br>`max_elements: integer = 50`<br>`max_text_chars: integer = 4000` |
| `page_accessibility_snapshot` | — | `tab_id: string / null = null`<br>`scope: string / SelectorTargetInput / AccessibilityTargetInput / null = null`<br>`max_nodes: integer = 200`<br>`include_ignored: boolean = false`<br>`include_values: boolean = false` |
| `page_observe` | — | `tab_id: string / null = null`<br>`max_texts: integer = 20`<br>`max_text_chars: integer = 160` |
| `page_evaluate` | `script: string` | `tab_id: string / null = null`<br>`args: array`<br>`max_chars: integer = 4000` |
| `page_pointer_move` | `x: number`<br>`y: number` | `tab_id: string / null = null`<br>`element: string = ""`<br>`profile: string = "direct"` |
| `page_pointer_drag` | `start_x: number`<br>`start_y: number`<br>`end_x: number`<br>`end_y: number` | `tab_id: string / null = null`<br>`waypoints: array`<br>`element: string = ""`<br>`profile: string = "direct"`<br>`button: string = "left"` |
| `page_pointer_drag_element` | `source: ElementTargetInput / ElementSourceInput`<br>`destination: ElementDestinationInput / OffsetDestinationInput / TrackRatioDestinationInput` | `tab_id: string / null = null`<br>`profile: string = "direct"`<br>`button: string = "left"` |
| `page_click_xy` | `x: number`<br>`y: number` | `tab_id: string / null = null`<br>`element: string = ""`<br>`profile: string = "direct"`<br>`button: string = "left"`<br>`delay_before_press_ms: integer = 0` |
| `page_close` | — | — |
| `page_get_url` | — | `tab_id: string / null = null` |
| `browser_headers_set` | `headers: object` | `tab_id: string / null = null` |
| `browser_user_agent_set` | `user_agent: string` | `tab_id: string / null = null`<br>`platform: string / null = null` |
| `browser_cache_clear` | — | `tab_id: string / null = null` |
| `browser_permission_get` | `permission: string` | `tab_id: string / null = null` |
| `browser_permission_set` | `permission: string`<br>`setting: string` | `tab_id: string / null = null`<br>`origin: string / null = null` |
| `browser_permissions_reset` | — | `tab_id: string / null = null` |
| `page_dialog_observe` | — | `tab_id: string / null = null`<br>`timeout: number = 0`<br>`max_message_chars: integer = 2000` |
| `page_dialog_respond` | `action: string` | `tab_id: string / null = null`<br>`prompt_text: string / null = null`<br>`timeout: number = 0.0` |
| `element_click_and_download` | `selector: string / SelectorTargetInput / AccessibilityTargetInput / CoordinateDownloadTriggerInput / KeyboardDownloadTriggerInput` | `tab_id: string / null = null`<br>`operation_key: string / null = null`<br>`timeout: number = 30.0`<br>`expected_filename: string / null = null`<br>`expected_mime_type: string / null = null` |
| `page_console_logs` | — | `tab_id: string / null = null`<br>`level: string = "all"`<br>`since: integer = -1`<br>`limit: integer = 20` |
| `element_find` | `selector: string / SelectorTargetInput / AccessibilityTargetInput` | `tab_id: string / null = null`<br>`timeout: number = 3` |
| `element_find_all` | `selector: string / SelectorTargetInput / AccessibilityTargetInput` | `tab_id: string / null = null`<br>`limit: integer = 20`<br>`include_html: boolean = false` |
| `element_click` | `selector: string / SelectorTargetInput / AccessibilityTargetInput` | `tab_id: string / null = null`<br>`timeout: number = 10`<br>`observe: boolean = false`<br>`button: string = "left"`<br>`click_count: integer = 1` |
| `element_type` | `selector: string / SelectorTargetInput / AccessibilityTargetInput`<br>`text: string` | `tab_id: string / null = null`<br>`timeout: number = 10`<br>`clear: boolean = true`<br>`observe: boolean = false` |
| `element_get_text` | — | `tab_id: string / null = null`<br>`selector: string / string / SelectorTargetInput / AccessibilityTargetInput = ""` |
| `element_get_attribute` | `selector: string / SelectorTargetInput / AccessibilityTargetInput`<br>`attribute: string` | `tab_id: string / null = null` |
| `element_get_property` | `selector: string / SelectorTargetInput / AccessibilityTargetInput`<br>`property: string` | `tab_id: string / null = null` |
| `element_get_html` | — | `tab_id: string / null = null`<br>`selector: string / string / SelectorTargetInput / AccessibilityTargetInput = ""` |
| `element_state_get` | `selector: string / SelectorTargetInput / AccessibilityTargetInput` | `tab_id: string / null = null`<br>`timeout: number = 3` |
| `element_upload_file` | `selector: string / SelectorTargetInput / AccessibilityTargetInput`<br>`paths: array` | `tab_id: string / null = null`<br>`timeout: number = 10` |
| `element_click_and_upload` | `selector: string / SelectorTargetInput / AccessibilityTargetInput`<br>`paths: array` | `tab_id: string / null = null`<br>`timeout: number = 10.0` |
| `page_scroll` | — | `tab_id: string / null = null`<br>`direction: string = "down"`<br>`pixels: integer = 300`<br>`x: integer = 0`<br>`y: integer = 0` |
| `element_scroll_into_view` | `selector: string / SelectorTargetInput / AccessibilityTargetInput` | `tab_id: string / null = null`<br>`center: boolean = true`<br>`timeout: number = 10` |
| `element_hover` | `selector: string / SelectorTargetInput / AccessibilityTargetInput` | `tab_id: string / null = null`<br>`timeout: number = 10`<br>`offset_x: integer / null = null`<br>`offset_y: integer / null = null` |
| `keyboard_press` | `keys: string` | `tab_id: string / null = null`<br>`interval: number = 0` |
| `element_select` | `selector: string / SelectorTargetInput / AccessibilityTargetInput`<br>`value: string` | `tab_id: string / null = null`<br>`by: string = "value"`<br>`timeout: number = 10` |
| `element_check` | `selector: string / SelectorTargetInput / AccessibilityTargetInput` | `tab_id: string / null = null`<br>`checked: boolean = true`<br>`by_js: boolean = false`<br>`timeout: number = 10` |
| `frame_list` | — | `tab_id: string / null = null`<br>`limit: integer = 20` |
| `frame_snapshot` | — | `tab_id: string / null = null`<br>`frame_selector: string = ""`<br>`frame_index: integer = 0`<br>`include_html: boolean = false`<br>`max_elements: integer = 50`<br>`max_text_chars: integer = 4000`<br>`timeout: number = 3` |
| `frame_find` | `selector: string` | `tab_id: string / null = null`<br>`frame_selector: string = ""`<br>`frame_index: integer = 0`<br>`timeout: number = 3` |
| `shadow_find` | `host_selector: string`<br>`selector: string` | `tab_id: string / null = null`<br>`timeout: number = 3` |
| `shadow_find_all` | `host_selector: string`<br>`selector: string` | `tab_id: string / null = null`<br>`limit: integer = 20`<br>`include_html: boolean = false` |
| `browser_cookies_get` | — | `tab_id: string / null = null`<br>`all_domains: boolean = false`<br>`all_info: boolean = false`<br>`include_values: boolean = false` |
| `browser_cookies_set` | `cookies: array` | `tab_id: string / null = null` |
| `browser_cookies_delete` | `name: string` | `tab_id: string / null = null`<br>`url: string / null = null`<br>`domain: string / null = null`<br>`path: string / null = null` |
| `browser_cookies_clear` | — | `tab_id: string / null = null` |
| `storage_get` | — | `tab_id: string / null = null`<br>`area: string = "local"`<br>`key: string = ""`<br>`include_values: boolean = false` |
| `storage_set` | `key: string`<br>`value: string` | `tab_id: string / null = null`<br>`area: string = "local"` |
| `storage_clear` | — | `tab_id: string / null = null`<br>`area: string = "local"`<br>`key: string = ""` |
| `wait_for_element` | `selector: string / SelectorTargetInput / AccessibilityTargetInput` | `tab_id: string / null = null`<br>`timeout: number = 10` |
| `wait_for_url` | `url_pattern: string` | `tab_id: string / null = null`<br>`timeout: number = 10` |
| `wait_time` | `seconds: number` | — |
| `wait_until` | `condition: string` | `tab_id: string / null = null`<br>`selector: string / string / SelectorTargetInput / AccessibilityTargetInput = ""`<br>`value: string = ""`<br>`name: string = ""`<br>`timeout: number = 10`<br>`interval: number = 0.1`<br>`stable_ms: integer = 300` |
| `network_listen_start` | — | `tab_id: string / null = null`<br>`targets: array`<br>`is_regex: boolean = false`<br>`method: string = ""`<br>`resource_type: string = ""`<br>`clear: boolean = true` |
| `network_listen_wait` | — | `tab_id: string / null = null`<br>`listener_token: string / null = null`<br>`timeout: number = 5.0`<br>`limit: integer = 10`<br>`include_headers: boolean = false`<br>`include_body: boolean = false`<br>`max_body_chars: integer = 2000` |
| `network_listen_stop` | — | `tab_id: string / null = null`<br>`listener_token: string / null = null`<br>`clear: boolean = true` |
| `network_blocked_urls_set` | `urls: array` | `tab_id: string / null = null` |
<!-- GENERATED:TOOL-PARAMETERS:END -->

## Tool Inventory

The 0.8.8 registry contains 69 typed browser tools. Site, component, challenge,
and business workflows are composed by clients or optional external Skills.

### Tab Targeting And Scheduling

- All 63 tab-scoped tools accept optional `tab_id`. Both stable MCP ids and
  native DrissionPage tab ids resolve to the same tracked `PageTab`; successful
  results always return the stable MCP id.
- `tab_id=null` is a compatibility fallback, not a late-bound alias. The server
  captures the current tab before browser work and keeps that object bound for
  the entire call.
- Actions on the same tab are serialized. Actions on independent tabs may run
  concurrently. Dialog observe/respond retain their intentional overlap with
  the action that opens a native modal, while still counting as in-flight work.
- `tab_close` marks the target as closing, rejects new calls with `TAB_CLOSED`,
  waits for claimed actions to finish, then closes it. Browser cleanup drains
  all tracked tabs before quitting Chromium.
- `page_navigate(new_tab=true)` may set `background`, `new_window`, or
  `new_context`. Background creation preserves the MCP current tab. A
  `new_context` tab owns a disposable Chromium browser context that is released
  by `tab_close`.
- Exact-once artifact operations bind `operation_key` fingerprints to the
  resolved tab. Reusing a key on another tab returns `OPERATION_KEY_CONFLICT`;
  it cannot replay an artifact or download receipt from the original tab.

### Reusable Element Targets

Existing string selectors remain valid and retain their previous result shape:

```json
{"selector": "#save"}
```

Element tools also accept a strict `kind`-discriminated target object. Selector
targets can cross up to four ordered frame selectors and eight ordered Shadow DOM
hosts through DrissionPage objects:

```json
{
  "selector": {
    "kind": "selector",
    "selector": "#save",
    "frame_selectors": ["#outer-frame", "#inner-frame"],
    "shadow_hosts": ["#app-host"]
  }
}
```

Scope resolution is intentionally ordered in two phases: every
`frame_selectors` entry is resolved outer-to-inner first, then every
`shadow_hosts` entry is resolved outer-to-inner. Arbitrarily interleaved
frame/shadow paths are not part of the 0.7.6 contract.

Accessibility targets query Chromium's accessibility tree by role and optional
accessible name. `exact` defaults to `true`; more than one matching node returns
`AMBIGUOUS_TARGET` instead of choosing an arbitrary element:

```json
{
  "selector": {
    "kind": "accessibility",
    "role": "button",
    "name": "Save",
    "exact": true,
    "frame_selectors": [],
    "shadow_hosts": ["#app-host"]
  }
}
```

The shared target contract is accepted by element discovery, read, click, type,
upload, scroll, hover, select, check, state, wait, and click-download tools.

### Network Control And Listener Beta

| Tool | Type | Required input | Description |
| --- | --- | --- | --- |
| `network_listen_start` | Destructive | none | Start a new DrissionPage 4.x listener generation for HTTP/XHR/Fetch packets and return its token, state, cursor, and startup timing. No interception or mocking. Optional: `targets`, `is_regex`, `method`, `resource_type`, `clear`. |
| `network_listen_wait` | Read-only | none | Return after the first matching packet, then briefly drain already-arriving matches up to `limit`; report explicit timeout/elapsed/remaining-budget evidence and cumulative cursor state. `limit` is a maximum, not a required count. Optional: `listener_token`, `timeout`, `include_headers`, `include_body`, `max_body_chars`. |
| `network_listen_stop` | Destructive | none | Stop network observation and optionally clear the listener queue. A supplied stale generation token fails with `LISTENER_NOT_FOUND`. Optional: `listener_token`, `clear`. |
| `network_blocked_urls_set` | Destructive | `urls` | Replace up to 100 blocked URL patterns and echo the accepted values. An empty list clears all patterns. |

### Browser Environment

| Tool | Type | Required input | Description |
| --- | --- | --- | --- |
| `browser_headers_set` | Destructive | `headers` | Replace up to 64 extra request headers. Successful results retain header names and redact non-empty values. An empty object clears all configured headers. |
| `browser_user_agent_set` | Destructive | `user_agent` | Override the current tab user agent and return the accepted and previous values. Optional: `platform`. |
| `browser_cache_clear` | Destructive | none | Clear HTTP cache while preserving Cookies, localStorage, and sessionStorage. |
| `browser_permission_get` | Read-only | `permission` | Query one supported Permissions API state for the current document origin without opening an operating-system prompt. |
| `browser_permission_set` | Destructive | `permission`, `setting` | Set one permission to `granted`, `denied`, or `prompt` for an exact HTTP(S) origin in the current Chromium context. Optional: `origin` (current origin by default). |
| `browser_permissions_reset` | Destructive | none | Reset all permission overrides in the current Chromium browser context. |

### Navigation

| Tool | Type | Required input | Description |
| --- | --- | --- | --- |
| `page_navigate` | Destructive | `url` | Open a URL in the captured/existing target, or create a new target. Optional: `tab_id`, `new_tab`, `background`, `new_window`, `new_context`, `observe`. Creation options require `new_tab=true`; `tab_id` and `new_tab=true` are mutually exclusive. |
| `page_navigate_with_http_auth` | Destructive | `url`, `username`, `password` | Create a dedicated Chromium BrowserContext, answer one bounded HTTP auth challenge, clean Fetch handlers, and retain the authenticated tab until `tab_close`. Credentials are never returned. Optional: `realm`, `timeout`. |
| `page_go_back` | Destructive | none | Go back in browser history. |
| `page_go_forward` | Destructive | none | Go forward in browser history. |
| `page_refresh` | Destructive | none | Reload the current page. |

### Tab Operations

| Tool | Type | Required input | Description |
| --- | --- | --- | --- |
| `tab_list` | Read-only | none | List open browser tabs with stable MCP tab IDs, native tab IDs, URLs, titles, and active state. |
| `tab_switch` | Destructive | `tab_id` | Switch to a tab returned by `tab_list`. |
| `tab_close` | Destructive | `tab_id` | Reject new calls for one tab, drain its in-flight actions, then close it without closing the whole browser. |

### Page Operations

| Tool | Type | Required input | Description |
| --- | --- | --- | --- |
| `page_resize` | Destructive | `width`, `height` | Resize the browser window. |
| `page_screenshot` | Read-only | none | Capture an inline viewport or full-page screenshot. Optional: `full_page`. |
| `page_screenshot_save` | Destructive | `path` | Save a viewport or full-page screenshot under `DP_MCP_SCREENSHOT_ROOT`. Relative paths resolve beneath that root; absolute paths must already be contained by it. Optional: `full_page`. |
| `page_export_artifact` | Destructive | `format` | Generate one PDF or MHTML file under `DP_MCP_ARTIFACT_ROOT`, returning a safe `ArtifactRef` and exact-once `ActionReceipt`. Optional: `filename`, `operation_key`, and bounded PDF print options. |
| `page_snapshot` | Read-only | none | Return a bounded page outline with text excerpt, headings, links, buttons, inputs, forms, counts, truncation metadata, and recommended selectors. Optional: `include_html`, `max_elements`, `max_text_chars`. |
| `page_accessibility_snapshot` | Read-only | none | Return a bounded Chromium accessibility tree for the page or an optional scoped element target. Field values and value-like properties are redacted by default; `include_values=true` explicitly returns them. Optional: `scope`, `max_nodes`, `include_ignored`, `include_values`. |
| `page_observe` | Read-only | none | Return a compact page fingerprint with URL, title, ready state, element counts, visible text samples, active element, recent console summary, and limits. Optional: `max_texts`, `max_text_chars`. |
| `page_evaluate` | Destructive | `script` | Run a bounded JavaScript function body in the current page and return a JSON-safe result. Optional: `args`, `max_chars`. |
| `page_scroll` | Destructive | none | Scroll the page by direction or to a position. Optional: `direction`, `pixels`, `x`, `y`. |
| `keyboard_press` | Destructive | `keys` | Send keys to the active page element. Successful results expose only redacted input metadata. Optional: `interval`. |
| `page_pointer_move` | Destructive | `x`, `y` | Move to exact viewport CSS coordinates without pressing a button. Optional: `profile` (`direct` default or deterministic 24-step `natural`) and `element`. |
| `page_pointer_drag` | Destructive | `start_x`, `start_y`, `end_x`, `end_y` | Perform one failure-safe held drag with exact endpoints. Optional: up to six ordered `waypoints`, `profile` (`direct` or `natural`), `element`, and `button`. |
| `page_pointer_drag_element` | Destructive | `source`, `destination` | Resolve CSS/XPath geometry immediately before an element, offset, or track-ratio drag. Supports one same-origin iframe and CSS paths through nested open Shadow DOM hosts. Optional: `profile` and `button`. |
| `page_click_xy` | Destructive | `x`, `y` | Move with the `direct` or deterministic bounded `natural` profile, optionally wait for `delay_before_press_ms`, then press and release at the exact viewport target. Optional: `profile`, `element`, and `button`. |
| `page_close` | Destructive | none | Close the browser context. |
| `page_get_url` | Read-only | none | Return the current page URL. |
| `page_dialog_observe` | Read-only | none | Wait for and return one pending native alert, confirm, or prompt without handling it. Optional: `timeout`, `max_message_chars`. |
| `page_dialog_respond` | Destructive | `action` | Accept or dismiss one currently pending alert, confirm, or prompt through a capability-probed native path. Optional: `prompt_text`, `timeout`. Prompt text is never returned. |

### Debug / Observability

| Tool | Type | Required input | Description |
| --- | --- | --- | --- |
| `page_console_logs` | Read-only | none | Read bounded browser console messages from the current tab. Optional: `level`, `since`, `limit`. |

### Element Operations

| Tool | Type | Required input | Description |
| --- | --- | --- | --- |
| `element_find` | Read-only | `selector` | Find one string or structured selector/accessibility target. Optional: `timeout` (default 3s). |
| `element_find_all` | Read-only | `selector` | Find multiple matching string or structured targets with bounded text, attributes, optional HTML, count/truncation metadata, and recommended selectors. Optional: `limit` (default 20), `include_html`. |
| `element_click` | Destructive | `selector` | Click one string or structured selector/accessibility target. Optional: `timeout`, `observe`, `button` (`left`, `right`, `middle`), `click_count` (`1`, `2`). Existing calls remain left single-clicks. Unsupported native variants return `UNSUPPORTED_OPERATION` rather than substituting another click. |
| `element_click_and_download` | Destructive | `selector` | Perform one string/structured selector click, bounded coordinate left click, or bounded keyboard input and await one correlated completed download under `DP_MCP_DOWNLOAD_ROOT`. Coordinate triggers accept `x`, `y`, optional `profile`, and optional `delay_before_press_ms`; keyboard triggers accept `keys` and optional `interval`. Returns an integrity-checked `ArtifactRef` and linked `ActionReceipt`. Optional: `operation_key`, `timeout`, `expected_filename`, `expected_mime_type`. |
| `element_type` | Destructive | `selector`, `text` | Type into one string or structured selector/accessibility target. Optional: `timeout`, `clear`, `observe`. |
| `element_upload_file` | Destructive | `selector`, `paths` | Upload one or more files from `DP_MCP_UPLOAD_ROOT` into an `input[type=file]`. Optional: `timeout`. |
| `element_click_and_upload` | Destructive | `selector`, `paths` | Arm Chromium's file-chooser interception, click one trigger, inject files from `DP_MCP_UPLOAD_ROOT`, and always disarm without user interaction with a native OS picker. Optional: `timeout`. |
| `element_scroll_into_view` | Destructive | `selector` | Scroll an element into the viewport. Optional: `center`, `timeout`. |
| `element_hover` | Destructive | `selector` | Hover an element. Optional: `timeout`, `offset_x`, `offset_y`. |
| `element_select` | Destructive | `selector`, `value` | Select an option from a `<select>` by value, text, or index. Optional: `by`, `timeout`. |
| `element_check` | Destructive | `selector` | Check or uncheck checkbox/radio controls. Optional: `checked`, `by_js`, `timeout`. |
| `element_get_text` | Read-only | none | Get page text, or element text when `selector` is set. |
| `element_get_attribute` | Read-only | `selector`, `attribute` | Read an HTML attribute. |
| `element_get_property` | Read-only | `selector`, `property` | Read a live DOM property such as `value`. |
| `element_get_html` | Read-only | none | Get page HTML, or element HTML when `selector` is set. |
| `element_state_get` | Read-only | `selector` | Return DrissionPage state flags plus document and viewport geometry for one string or structured target. Optional: `timeout`. |

### Frame / Shadow DOM

| Tool | Type | Required input | Description |
| --- | --- | --- | --- |
| `frame_list` | Read-only | none | List iframe/frame contexts without changing any global current-frame state. Optional: `limit`. |
| `frame_snapshot` | Read-only | none | Return a bounded outline from one iframe selected by `frame_selector` or `frame_index`. |
| `frame_find` | Read-only | `selector` | Find one element inside an iframe selected by `frame_selector` or `frame_index`. |
| `shadow_find` | Read-only | `host_selector`, `selector` | Find one element inside a shadow root exposed by the current supported DrissionPage runtime. The tested 4.x path includes open and closed roots. |
| `shadow_find_all` | Read-only | `host_selector`, `selector` | Find repeated elements inside a shadow root exposed by the supported DrissionPage runtime. Optional: `limit`, `include_html`. |

### Cookies and Storage

| Tool | Type | Required input | Description |
| --- | --- | --- | --- |
| `browser_cookies_get` | Read-only | none | Read normalized cookies. Values are redacted unless `include_values=true`. |
| `browser_cookies_set` | Destructive | `cookies` | Set a bounded batch of 1-100 cookies through DrissionPage. Successful results retain accepted metadata and redact Cookie values. |
| `browser_cookies_delete` | Destructive | `name` | Delete one named Cookie. Optional: `url`, `domain`, `path`. |
| `browser_cookies_clear` | Destructive | none | Clear all browser Cookies. |
| `storage_get` | Read-only | none | Read localStorage/sessionStorage by optional `key`. Values are redacted unless `include_values=true`. Optional: `area`, `include_values`. |
| `storage_set` | Destructive | `key`, `value` | Set one localStorage/sessionStorage value. The value is not echoed in the response. Optional: `area`. |
| `storage_clear` | Destructive | none | Clear one storage key or the whole selected storage area. Optional: `area`, `key`. |

### Wait Operations

| Tool | Type | Required input | Description |
| --- | --- | --- | --- |
| `wait_for_element` | Read-only | `selector` | Wait for an element to load. Bare selectors are treated as CSS. Optional: `timeout`. |
| `wait_for_url` | Read-only | `url_pattern` | Wait until the current URL contains text. Optional: `timeout`. |
| `wait_until` | Read-only | `condition` | Wait for observable conditions: `present`, `visible`, `hidden`, `detached`, `clickable`, `stable`, `text_contains`, `text_matches`, `url_contains`, or `url_matches`. Optional: `selector`, `value`, `timeout`, `interval`, `stable_ms`. |
| `wait_time` | Read-only | `seconds` | Sleep for a fixed duration. |

## Resources

The server exposes one deterministic JSON resource that does not initialize a
browser or perform a network request:

| URI | Purpose |
| --- | --- |
| `drissionpage://skills/catalog` | Versioned discovery metadata for optional repository example Skills. Schema v2 declares each example's Skill/MCP versions, required tools, fixture, verification status, pinned source revision/URL, SHA-256, catalog path, and entrypoint convention. |

Resource caps:

- Skills catalog JSON maximum: 8192 characters

## Prompts

DrissionPage MCP 0.8.8 exposes no MCP prompts. `tools/list`, typed schemas, and
typed errors describe the standalone core; procedural guidance belongs in
optional Skills.

## Compatibility Notes

- Selectors are normalized before calling DrissionPage: bare selectors are treated as CSS (`h1` -> `css:h1`, `input[name=q]` -> `css:input[name=q]`), XPath-looking strings are prefixed as XPath (`//h1` -> `xpath://h1`), and explicit DrissionPage forms such as `tag:h1`, `text:Submit`, `css:...`, `xpath:...`, and `@name=value` are preserved.
- Tool responses include selector metadata: `selector`, `locator`, `selector_strategy`, and `selector_normalized`.
- Structured target responses additionally include `target_kind`, ordered `frame_selectors`, ordered `shadow_hosts`, and accessibility role/name matching metadata. Legacy string-target responses omit these additive fields.
- Accessibility snapshots report `values_included`; field values and value-like properties are `<redacted>` unless `include_values=true`. Treat opt-in values as secrets.
- `page_snapshot` and `element_find_all` include `meta.approx_tokens`, `meta.json_chars`, and `meta.truncated` so clients can narrow later calls when a response is large.
- `page_snapshot` and `element_find_all` are preview page-understanding tools. Their outputs are intentionally bounded and include truncation metadata so clients can request narrower selectors instead of pulling full-page HTML by default. `page_snapshot.max_elements` remains a total cap, and the server balances that cap across headings, links, buttons, inputs, and forms before filling remaining capacity.
- Form and component workflows are composed from element discovery, type/select/check/click/keyboard, upload, wait, and state-read tools. The core does not classify widget libraries or infer business submission intent.
- `page_dialog_observe` returns a bounded pending-dialog message without accepting or dismissing it. Observation and response bypass ordinary browser-operation serialization so they can overlap the native click that opened a blocking dialog; no user action is required.
- `page_dialog_respond` checks immediately by default. No pending dialog returns `DIALOG_NOT_FOUND`; a positive `timeout` can overlap a not-yet-opened dialog. Capability gaps return `UNSUPPORTED_OPERATION`; prompt text and dialog messages are not retained in action history.
- `element_click_and_download` requires an approved `DP_MCP_DOWNLOAD_ROOT`. Its required `selector` field accepts existing selector/accessibility values plus strict `{kind: "coordinate", ...}` and `{kind: "keyboard", ...}` triggers; arbitrary scripts and action sequences are rejected. A successful response includes one checksum-verified regular file, safe relative path, sanitized HTTP(S) source URL, `ArtifactRef`, and correlated `ActionReceipt`. Keyboard trigger output contains redacted key length metadata, never the keys. Replaying the same operation key does not trigger again; failure and indeterminate results contain no artifact.
- `tab_list` synchronizes with browser tabs opened by normal page behavior, including `target="_blank"` links, without replacing an MCP-selected current tab merely because Chromium's latest tab changed.
- `page_observe` is designed for compact state checks. Use `page_snapshot` when you need selectors and structured page outline details. Its `console` field summarizes recent current-tab console messages when DrissionPage console capture is available.
- `page_console_logs` returns normalized console messages with `index`, `level`, `text`, `url`, `line`, `column`, and `source`. Use `since` with the previous `next_cursor` to fetch only newer messages.
- `page_evaluate` accepts a JavaScript function body; use `return` for values you want in `structuredContent.data.result`. The result is bounded by `max_chars`. Top-level `Infinity`, `-Infinity`, and `NaN` preserve `result_type: "number"`, return JSON `null`, and add `non_finite_number`; all public JSON mirrors use strict standards-compliant serialization.
- `element_upload_file` requires `DP_MCP_UPLOAD_ROOT`; absolute input paths are accepted only when they resolve inside that root, and successful responses return file names rather than absolute paths.
- `element_click_and_upload` uses DrissionPage's one-shot `Page.fileChooserOpened` path and performs cleanup after success, timeout, or failure. It controls the Chromium chooser event only; native operating-system picker windows are neither opened nor automated.
- `page_export_artifact` treats PDF/MHTML content as sensitive generated output. It requires `DP_MCP_ARTIFACT_ROOT`, exposes no absolute path, and replays a completed `operation_key` without writing a second file.
- `page_navigate_with_http_auth` removes its Fetch callbacks after the navigation. Chromium has no documented CDP command to purge HTTP auth cache, so the authenticated page lives in a dedicated browser context that `tab_close` disposes. Other tabs do not share that cache.
- Permission tools use `Browser.setPermission` and `Browser.resetPermissions`. `browser_permission_get` observes through the current document's Permissions API. Notification permission state is supported, but native OS permission dialogs and notification-center contents remain outside the MCP contract.
- `frame_*` tools are stateless: each call selects by `frame_selector` or zero-based `frame_index`; no global current-frame mode is stored. Frame summaries report `boundary`, `document_access`, and outer presentation/geometry evidence. The DrissionPage 4.x browser path is regression-tested against an attached cross-origin OOPIF that is parent-DOM-isolated but bridge-readable.
- `element_state_get` reports outer iframe geometry when its selector resolves to a frame. `rect.coordinate_space="target_document"` remains for compatibility; `viewport_coordinate_space` distinguishes top-level pointer coordinates from a nested target-document viewport. `presentation.coordinate_actionability` classifies ready, hidden, off-viewport, covered, pointer-disabled, 3D-transformed, and target-document-only evidence without choosing an action.
- `element_scroll_into_view` returns before/after evidence and `scroll_method`. Frame elements can report `page_fallback` when DrissionPage's frame scroller cannot scroll the outer iframe into the top-level viewport directly.
- `shadow_*` tools use DrissionPage's native shadow-root object instead of page-JavaScript `host.shadowRoot`. The current supported DrissionPage 4.x path is regression-tested against both open roots and a closed root that is invisible to page JavaScript. Capability failure is reported; the MCP does not inject a piercing fallback.
- `page_pointer_drag_element` has a different implementation boundary: its synchronous page script remains limited to the top document or one same-origin iframe and nested open Shadow DOM hosts. Tagged source plus `dx`/`dy` is preferred; legacy bare source plus `x`/`y` remains accepted.
- `browser_cookies_get` redacts cookie values by default. Use `include_values=true` only when the MCP client/session is allowed to handle cookie secrets.
- `browser_cookies_set` accepts `name`, `value`, optional `url`, `domain`, `path`, `expires`, `secure`, `http_only`, `same_site`, `priority`, and `source_scheme`. Its successful result keeps accepted metadata but replaces non-empty Cookie values with `<redacted>`.
- `browser_cookies_delete` and `browser_cookies_clear` use DrissionPage's browser Cookie setter directly; they require no user-side browser action and no tool-loading profile.
- `browser_headers_set` returns header names with non-empty values replaced by `<redacted>`. `browser_user_agent_set` continues to return its bounded user-agent metadata, and `network_blocked_urls_set` keeps accepted patterns subject to the public URL redaction boundary. Empty header and URL collections clear their respective overrides.
- `browser_user_agent_set` also returns `previous_user_agent` so callers can restore the original value without user-side browser action.
- `browser_cache_clear` explicitly disables Cookie, localStorage, and sessionStorage clearing while invalidating HTTP cache.
- `storage_get` redacts non-empty values by default. Use `include_values=true` only when the MCP client/session is allowed to handle storage secrets.
- `storage_set` does not echo the stored value in its success payload.
- `keyboard_press` never echoes the supplied text/key sequence. Its successful result reports only whether input was provided, its character length, and `redacted=true`.
- `observe=true` on `page_navigate`, `element_click`, and `element_type` adds an optional `changes` field with URL/title changes, count deltas, appeared/removed text samples, active element, `console_errors_added`, `console_warnings_added`, and `new_console_messages`. It is omitted by default.
- `wait_until` is the preferred recovery path for dynamic UI state such as delayed clickability, disappearing spinners, stable elements, text updates, or URL transitions.
- Pointer tools default to `profile="direct"`. `profile="natural"` uses a fixed,
  reproducible 24-step eased cubic path with bounded 8-14ms intervals and an exact final
  point. The path is deterministic for one start/target/profile tuple, while the
  browser pointer position remains stateful across calls. It changes one pointer
  action's execution semantics; it does not decide targets, challenges, or business
  workflow progression.
- A browser tab must exist before read-only page/element tools can inspect content. In a fresh session, call `page_navigate`, then collect `page_snapshot` or `page_observe` as a separate explicit step.
- Challenge observation, verified multi-click sequences, and site/business rules
  belong in external `skills/<skill-name>/SKILL.md` procedures and must use public
  MCP tools only.
- `element_input_text` and `wait_sleep` were removed in 0.4.0. Use
  `element_type` and `wait_time`.

## Optional Local Safety Policy

By default, DrissionPage MCP remains a local stdio browser automation server with open navigation behavior. Operators can opt in to stricter controls with environment variables:

| Variable | Effect |
| --- | --- |
| `DP_MCP_NAV_ALLOWLIST` | Comma-separated host names or URL prefixes. When set, navigation is allowlist-first. |
| `DP_MCP_NAV_BLOCKLIST` | Comma-separated host names or URL prefixes rejected after allowlist checks. |
| `DP_MCP_BLOCK_PRIVATE_NETWORK` | Set to `1`, `true`, or `yes` to reject localhost/private/link-local navigation. |
| `DP_MCP_SCREENSHOT_ROOT` | Required root directory for `page_screenshot_save` file writes. Relative tool paths resolve beneath this root; traversal and symlink escapes are rejected. |
| `DP_MCP_UPLOAD_ROOT` | Required root directory for `element_upload_file` and `element_click_and_upload` input files. |
| `DP_MCP_DOWNLOAD_ROOT` | Required approved root for `element_click_and_download` artifacts. Public results expose safe relative paths only. |
| `DP_MCP_ARTIFACT_ROOT` | Required approved root for `page_export_artifact` PDF/MHTML output. Public results expose safe relative paths only. |
| `DP_MCP_DENY_DOWNLOAD` | Deny `element_click_and_download` before the native click or filesystem allocation. |

Denied navigation is checked before `context.ensure_tab()`, so policy rejection does not start or initialize a browser.
