# Troubleshooting

Use this guide when the MCP server does not start, tools do not appear, or browser automation fails.

## First Checks

Run these commands from a shell:

```bash
python -m pip install -U "drissionpage-mcp>=0.8.6"
drissionpage-mcp --version
drissionpage-mcp doctor
drissionpage-mcp doctor --launch-browser
python playground/run_mcp_lab.py --case registry
```

Expected result:

- The version command prints the installed `drissionpage-mcp` version.
- `drissionpage-mcp doctor` reports Python, package, real MCP handler wiring, browser, and environment diagnostics. Both `mcp_supported` and `mcp_server_wiring` must be `ok`.
- `drissionpage-mcp doctor --launch-browser` proves Chrome/Chromium can actually start.
- `playground/run_mcp_lab.py --case registry` proves the stdio MCP registry loads successfully.

For a source checkout, install development dependencies first:

```bash
python -m pip install -e ".[dev]"
python playground/run_mcp_lab.py --case registry
```

## Client Shows `Connection closed` After Tools Load

If logs show tools loading and then fail with
`'Server' object has no attribute 'list_tools'`, the environment resolved the
incompatible MCP Python SDK 2.x. Repair both packages explicitly:

```bash
python -m pip install -U "drissionpage-mcp>=0.8.6" "mcp>=1.0.0,<2"
drissionpage-mcp doctor
```

Do not treat `drissionpage-mcp --version` as a connection test. Confirm the
doctor output contains successful `mcp_supported` and `mcp_server_wiring`
checks, then restart the MCP client.

## MCP Client Cannot Find the Server

Check the MCP client configuration uses the installed command.

For Codex CLI/IDE, `~/.codex/config.toml` or a trusted project `.codex/config.toml` should contain:

```toml
[mcp_servers.drissionpage]
command = "drissionpage-mcp"
startup_timeout_sec = 20
tool_timeout_sec = 60
```

For JSON MCP clients, configure:

```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp"
    }
  }
}
```

Then verify:

- Codex: run `codex mcp list`; in the TUI, run `/mcp`.
- JSON clients: restart the MCP client after editing JSON.
- Confirm the TOML or JSON syntax is valid.
- Confirm `drissionpage-mcp --version` works in the same shell environment used by the client.
- For source installs, prefer `python -m drissionpage_mcp.cli` with an absolute `cwd`.
- For GUI clients that do not inherit your shell `PATH` or virtualenv, use an
  absolute Python executable:

  ```json
  {
    "mcpServers": {
      "drissionpage": {
        "command": "/absolute/path/to/python",
        "args": ["-m", "drissionpage_mcp.cli"]
      }
    }
  }
  ```

- If `pip` cannot find a newly published version, your package mirror may be stale; retry with `python -m pip install -U --index-url https://pypi.org/simple drissionpage-mcp`.

## Tools Do Not Appear

1. Run diagnostics and, if needed, debug logging:

   ```bash
   drissionpage-mcp doctor
   python -m drissionpage_mcp.cli --log-level DEBUG
   ```

2. Check the MCP client logs for startup, TOML, or JSON configuration errors.
3. Confirm the package imports correctly:

   ```bash
   python -c "from drissionpage_mcp.tools import get_all_tools; print(len(get_all_tools()))"
   ```

The current tool registry should load 69 tools. Permission controls, PDF/MHTML
artifacts, file-chooser automation, isolated HTTP auth, structured targets,
accessibility snapshots, dialog observation, Cookie mutation, request-header,
user-agent, cache, and URL-blocking tools are included by default; no capability
profile or `full` mode is required.


## Task Completion / Challenge Surface 0.8.6 Checks

- For vision-directed hover/reveal actions, use `page_pointer_move`; for activation, use `page_click_xy`; for a selector-backed element/track drag use `page_pointer_drag_element`; for a bounded visual-coordinate drag use `page_pointer_drag`. Add up to six ordered `waypoints` only when the held gesture must follow a multi-segment path. Pointer tools default to `profile="direct"`; set `profile="natural"` for a deterministic 24-step eased trajectory with an exact endpoint.
- In a fresh session, call `page_navigate`, then collect `page_snapshot` or `page_observe` explicitly.
- Discover controls with `page_snapshot`, `element_find_all`, and `element_find`. Operate them with explicit type, select, check, click, keyboard, and upload calls, then verify live properties, attributes, text, URL, or bounded wait conditions.
- Use a structured selector target when the element is inside ordered frame or Shadow DOM scopes. The resolver enters all frames outer-to-inner before entering all Shadow DOM hosts outer-to-inner; it does not support arbitrary frame/shadow interleaving. Use a structured accessibility target for role/name lookup; narrow the name or scope when the server reports `AMBIGUOUS_TARGET`.
- Use `page_accessibility_snapshot` to inspect a bounded AX tree and `element_state_get` to verify live state and geometry after an action. AX field values are redacted by default; set `include_values=true` only when the workflow needs them and treat the response as secret-bearing.
- The core does not infer component libraries or business submission intent. Keep library- or site-specific matching in a client Skill and always collect fresh evidence before retrying a consequential action.
- Configure `DP_MCP_DOWNLOAD_ROOT` before `element_click_and_download`. Existing selector/accessibility targets remain supported; use a strict `coordinate` trigger for a viewport left click or a strict `keyboard` trigger for the active element. Keyboard values are never echoed. A replay with the same operation key returns the frozen result without another trigger; the successful tool result contains safe artifact metadata.
- Configure `DP_MCP_ARTIFACT_ROOT` before `page_export_artifact`. PDF/MHTML results expose a safe relative path and checksum only; generated content can contain page secrets.
- Use `browser_permission_get` before and after `browser_permission_set`, and call `browser_permissions_reset` when the workflow no longer needs the override. These tools do not automate native OS permission prompts or notification-center windows.
- Use `element_click_and_upload` when a button or custom control opens a browser file chooser. It injects files from `DP_MCP_UPLOAD_ROOT` and removes the chooser interception without any user action.
- Use `page_navigate_with_http_auth` for Basic/Digest-style browser challenges. Credentials are redacted and the authenticated page is isolated in a disposable context; close its returned `tab_id` when the workflow is complete.
- Start `page_dialog_observe` before the click when the action may open a blocking alert, confirm, or prompt, then call `page_dialog_respond`. The response tool checks immediately by default; pass a positive timeout only when it must overlap a not-yet-opened dialog. `DIALOG_PENDING` points blocked tools back to observe/respond, while `DIALOG_NOT_FOUND` means no response precondition exists yet.
- Use `network_listen_start` before the action that triggers fetch/XHR, then `network_listen_wait`, then `network_listen_stop`. `limit` is a maximum: wait returns after the first packet and briefly drains already-arriving matches. If the installed DrissionPage tab lacks listener APIs, the tools return `UNSUPPORTED_OPERATION` with recovery hints.
- Fractional timeouts such as `1.5` are accepted consistently by every public tool timeout field.
- `page_evaluate` returns top-level non-finite numbers as JSON `null` with `result_type: "number"` and `non_finite_number`; it never emits non-standard JSON NaN/Infinity tokens.
- Use `browser_headers_set` and `browser_user_agent_set` before navigation when a workflow requires a specific request environment. Header write results retain names but redact non-empty values; use the returned `previous_user_agent` to restore the original value.
- Use `network_blocked_urls_set` with an empty list to remove URL blocks. Use `browser_cache_clear` when HTTP cache must be invalidated without clearing Cookies or Web Storage.
- Use `drissionpage-mcp doctor` to inspect browser, headless, sandbox, and environment configuration without starting a workflow.
- Use `tools/list` for the current typed core contract. Optional Skills are discovered through `drissionpage://skills/catalog` and follow the external `skills/<skill-name>/SKILL.md` path convention.
- Keep challenge observation, repeated-click sequencing, and site/business decisions in an external Skill. Re-observe and verify between individual MCP actions instead of replaying stale coordinates.
- For iframe challenges, use `frame_list.boundary` and `document_access` to choose a frame-DOM or outer-element path. Read `outer.presentation.coordinate_actionability` or `element_state_get.presentation` before coordinate input; only `top_level_viewport` geometry is directly valid for `page_click_xy`.

For the release reliability gate, run the deterministic public-tool benchmark:

```bash
DP_HEADLESS=1 DP_NO_SANDBOX=1 DP_MCP_REQUIRE_BROWSER=1 \
python -m tests.evals.task_completion_benchmark \
  --iterations 10 \
  --output benchmark-results/0.8.6-task-completion.json
```

Run the local challenge-surface matrix and the explicitly opt-in official
Turnstile dummy-key matrix separately:

```bash
DP_HEADLESS=1 DP_NO_SANDBOX=1 DP_MCP_REQUIRE_BROWSER=1 \
python -m tests.evals.challenge_surface_benchmark --iterations 10

DP_HEADLESS=1 DP_NO_SANDBOX=1 DP_MCP_REQUIRE_BROWSER=1 \
python -m tests.evals.turnstile_testkey_benchmark \
  --iterations 10 --allow-external
```

The report is workload-scoped. Every W01-W08 workload must reach at least 9/10;
an overall average cannot hide one failing workload. Browser startup failures
are reported separately from workload failures. Each run includes the observed
fixture side-effect counters used to derive `duplicate_count`; CI uploads the
JSON on both success and failure. Failed runs are also printed directly under
`failed_runs` in the benchmark step log, including the workload, iteration,
error category, tool calls, and observed side-effect counters.

## Browser Does Not Start

DrissionPage requires a local Chrome or Chromium browser. Start with the launch
check because it catches missing binaries, sandbox failures, and no-display
remote environments:

```bash
drissionpage-mcp doctor --launch-browser
```

Check common browser commands:

```bash
which google-chrome || true
which chromium || true
which chromium-browser || true
```

On Windows, confirm Chrome or Chromium is installed and available to DrissionPage. If you use a custom browser path, configure it through your local environment or DrissionPage settings.

For SSH, Docker, Codespaces, CI, or other no-GUI environments, run headless and
set the browser path explicitly in your MCP client configuration:

```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp",
      "env": {
        "CHROME_PATH": "/usr/bin/chromium",
        "DP_HEADLESS": "1"
      }
    }
  }
}
```

Chrome sandboxing stays enabled by default. If Chromium is running as root or
inside a restricted container and `doctor --launch-browser` reports a sandbox
startup error, add `DP_NO_SANDBOX=1` only for that environment.

## Navigation or Element Actions Fail

Common causes:

- The page did not finish loading before the action.
- The selector does not match the page.
- The element is inside an iframe, shadow root, or dynamic UI state not yet exposed to DrissionPage.
- The site blocks automation or requires authentication.

Useful recovery steps:

1. Check `error.details.hints` in the `### JSON_RESULT` block. The server now
   returns structured next steps for common failures.
2. Use `page_snapshot` to inspect the current page outline and recommended
   selectors without pulling full-page HTML.
3. Use `element_find_all` with a broader selector to discover repeated cards,
   table rows, links, or similar candidate elements.
4. Use `wait_until` for dynamic conditions such as `clickable`, `hidden`,
   `stable`, text updates, or URL transitions.
5. Use `observe=true` on `page_navigate`, `element_click`, or `element_type`
   when you need a compact before/after change summary.
6. Use `page_console_logs` or inspect the `console_errors_added`,
   `console_warnings_added`, and `new_console_messages` fields from
   `observe=true` when an action silently fails on the page.
7. Use `wait_for_element` before simple `element_click` or `element_type` calls.
8. Increase the per-tool timeout where supported. `element_find` defaults to 3 seconds for fast feedback; explicit wait tools keep longer waits.
9. Re-check selectors in the browser devtools. Bare selectors are treated as CSS; use `text:Submit` for text matching and explicit `tag:`, `css:`, `xpath:`, or `@name=value` forms when needed.
10. If the element may be inside an iframe, inspect with `frame_list`,
   `frame_snapshot`, and `frame_find` before retrying the action.
11. If the element may be inside an open shadow root, inspect with `shadow_find`
   or `shadow_find_all`.

## Screenshots Fail

If `page_screenshot` fails:

- Confirm a page is open with `page_get_url`.
- Try a viewport screenshot before a full-page screenshot.
- Check whether the browser is still connected.

If `page_screenshot_save` fails:

- Set `DP_MCP_SCREENSHOT_ROOT` to the directory where screenshots may be written.
- Pass either a relative path (resolved beneath the configured root) or an absolute path already inside that directory.
- Directory traversal and symlink escapes are rejected.

## File Uploads Fail

`element_upload_file` is intentionally root-gated:

- Set `DP_MCP_UPLOAD_ROOT` to the directory containing files that MCP may upload.
- Pass paths that resolve inside that directory.
- Confirm each path exists and is a regular file.
- Successful responses return file names only, not absolute paths.

## Reporting Issues

When filing an issue, include:

- OS and Python version.
- `drissionpage-mcp --version` output.
- Browser name and version.
- MCP client name and version.
- Minimal MCP config with secrets removed.
- Debug logs from `python -m drissionpage_mcp.cli --log-level DEBUG`.
