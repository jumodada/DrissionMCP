# Changelog

All notable changes to the DrissionPage MCP Server project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.6] - 2026-08-30

### Security
- Added one public-response redaction boundary for URLs, credentials, headers,
  Cookie writes, network bodies, errors, receipts, and text mirrors. Explicit
  `include_values=true` storage/Cookie reads remain opt-in value-bearing paths.

### Changed
- Changed header and Cookie write results to retain names and bounded metadata
  while replacing values with `<redacted>`.
- Marked `network_listen_wait` as a non-global-locking wait and serialized each
  tab's listener start/wait/stop lifecycle under its own state lock.

### Fixed
- Prevented a cancelled listener wait from releasing per-tab lifecycle
  ownership while its underlying worker was still active, keeping start/wait/stop
  deterministic during cancellation.

## [0.8.5] - 2026-08-21

### Added
- Added the official MCP Registry ownership marker to the PyPI README and a
  versioned `server.json` describing the public `drissionpage-mcp` PyPI package
  and its `stdio` transport.
- Added a tag-gated release workflow that validates the release metadata,
  publishes the package to PyPI through trusted publishing, waits for PyPI
  availability, then publishes the Registry entry through GitHub OIDC.
- Added a distribution runbook covering the official Registry, Cursor Directory,
  and TRAE installation-link paths.

### Release Scope
- No MCP tools, prompts, resources, schemas, browser behavior, or Skills were
  changed. The public surface remains 69 tools, zero prompts, and one optional
  Skills catalog resource.

## [0.8.4] - 2026-08-20

### Added
- Added explicit `boundary`, `document_access`, and outer iframe evidence to
  `frame_list` and embedded frame summaries, including CSS presentation, 3D
  ancestry, and coordinate actionability.
- Added `viewport_coordinate_space` to element geometry and before/after
  geometry plus `scroll_method` to `element_scroll_into_view`.
- Added deterministic local challenge-surface fixtures and a ten-iteration
  benchmark for normal, hidden, below-viewport, delayed, and transformed 3D
  cross-origin widgets with parent-page postconditions and screenshot evidence.
- Added an opt-in benchmark for Cloudflare's five official Turnstile dummy keys,
  recording callback state and token presence/length without retaining tokens.

### Changed
- Updated `cross-origin-iframe-probe` and `turnstile-testing` Skills to choose
  DOM, outer geometry, scroll, pointer, keyboard, and verification paths from
  current capability evidence instead of treating cross-origin as always
  unreadable.
- Pinned the catalog to `skills-manager` `v0.8.4`, upgraded the two challenge
  Skills to version `0.2.0`, and refreshed their SHA-256 integrity metadata.
- Kept the legacy `rect.coordinate_space="target_document"` field while making
  top-level and target-document viewport coordinates explicit.

### Verification
- Added unit, typed-success, schema, eval-contract, public-MCP, and real-browser
  regressions for outer OOPIF geometry, actionability, scroll evidence, and
  parent-page challenge postconditions.
- Verified the local five-scenario challenge matrix and official visible,
  invisible, pass, fail, and forced-interactive Turnstile keys.

### Release Scope
- No provider-specific public tool was added. The surface remains 69 tools,
  zero MCP prompts, and one optional Skills catalog resource; provider workflow
  decisions remain in external Skills.

## [0.8.3] - 2026-08-17

### Added
- Added a versioned Skills catalog schema with per-Skill versions, MCP
  compatibility, required public tools, fixtures, verification status, pinned
  source revision, and SHA-256 content integrity.
- Added `playground/validate_skills.py` to validate cross-host frontmatter,
  catalog paths, public-tool dependencies, pinned source URLs, and content
  hashes without initializing a browser.

### Changed
- Pinned repository example Skill metadata to the `skills-manager` `v0.8.3`
  source revision instead of mutable `main` URLs.
- Increased the bounded optional catalog payload limit to 8192 characters for
  versioned dependency and integrity metadata.
- Updated English and Chinese release guidance, compatibility notes, tool
  contracts, troubleshooting, benchmark artifact names, and clean-package
  checks for 0.8.3.

### Verification
- Added repository Skill catalog, static resource, eval protocol, release
  metadata, and CI structure regressions.
- Kept catalog reads static and browser-independent and kept Skills excluded
  from wheel/sdist packages.

### Release Scope
- No new public tool names, prompts, browser behavior, input/output schemas, or
  server-side Skill execution. The public surface remains 69 tools, zero MCP
  prompts, and one optional Skills catalog resource.

## [0.8.2] - 2026-08-14

### Added
- Added repository example Skills for cross-origin iframe diagnosis,
  authorized Turnstile fixtures, and bounded Xiaohongshu-like content research.
- Added `docs/skills.md` with the Skill contract, catalog, safety boundaries,
  and clean-release fixture validation example.

### Changed
- Updated `drissionpage://skills/catalog` to list repository example metadata,
  including descriptions, paths, source URLs, and `repository_example` status.
- Rewrote English and Chinese README Skills sections and current-release
  guidance to distinguish host-loaded Markdown Skills from the atomic MCP core.
- Made the Linux browser-boundary CI matrix resolve `CHROME_PATH` explicitly
  and verify browser launch before running strict Chromium evidence tests.

### Release Scope
- No new MCP tools, prompts, browser capabilities, or input/output schemas.
- Skills are not imported or executed by the server and remain excluded from
  wheel/sdist packages.

## [0.8.1] - 2026-08-13

### Changed
- Synchronized package, runtime, README, playground, and troubleshooting
  version metadata for the 0.8.1 release.
- Extended `drissionpage-mcp doctor` with imported package path, source-tree
  detection, installed distribution metadata, and public surface checks for 69
  tools, zero MCP prompts, and one Skills catalog resource.

### Release Scope
- No new public tool names, input/output schema changes, browser behavior
  changes, network/download capability changes, or bundled Skills.
- Release verification must use a built wheel or sdist in a clean environment;
  doctor marks source-tree execution explicitly.

## [0.8.0] - 2026-07-31

### Changed
- `storage_get` now redacts non-empty localStorage and sessionStorage values by default; callers must set `include_values=true` to return values.
- `keyboard_press` and keyboard-triggered download results now return redacted input metadata instead of echoing the supplied text/key sequence.
- `element_click_and_download` preserves every selector/accessibility form and adds strict coordinate and keyboard triggers without adding another public tool.

### Fixed
- Classified `BrowserConnectError` and native-dialog failures before generic navigation/runtime fallback so browser startup and `DIALOG_PENDING` errors retain stable recovery codes while localized DrissionPage and CDP details stay redacted.
- Serialized coordinate and keyboard download triggers per tab under one shared deadline, restored prior download state on every terminal path, preserved operation-key replay/conflict detection, and added a 250 ms fail-closed guard that cancels late missions after indeterminate outcomes.

### Verification
- Made mypy a required GitHub CI lint gate alongside Ruff, multi-version unit/protocol jobs, browser-boundary and full-coverage jobs, W01-W08 reliability benchmarking, clean-wheel stdio smoke tests, and wheel/sdist privacy audits.
- Added focused security, response-contract, download success/failure/timeout/cleanup/replay, real-Chromium, schema snapshot, and CI structure regressions.

### Release Scope
- No new public tool names: the ordered registry remains at 69 typed tools, with zero MCP prompts and one bounded optional-Skills catalog resource.
- No bundled Skills, component-library adapters, site procedures, business workflows, held-key lifetimes, IME/composition, touch/pinch, or clipboard access were added to the Python distribution.

## [0.7.9] - 2026-07-29

### Fixed
- Sanitized public DrissionPage failures so version suffixes, localized runtime text, CDP `objectId`/stack payloads, and other implementation details do not leak through MCP error messages.
- Redacted policy-rejection detail values and failed-navigation destinations so query credentials, private URLs, and local paths are not reflected in public failure payloads.
- Classified DrissionPage browser connection failures before navigation fallback so startup failures retain `BROWSER_START_FAILED` and the correct recovery hints.
- Added `DIALOG_PENDING` recovery for browser operations blocked by a native dialog and `DIALOG_NOT_FOUND` for an immediate `page_dialog_respond` precondition failure.
- Made `page_dialog_respond` check immediately by default while preserving explicit concurrent wait budgets and a bounded response budget for an already-pending dialog.
- Changed `network_listen_wait.limit` back to a maximum: the tool now returns after the first packet and briefly drains already-arriving matches instead of waiting for the full requested count or timeout.
- Resolved relative `page_screenshot_save.path` values beneath `DP_MCP_SCREENSHOT_ROOT` while retaining traversal and symlink-escape rejection.
- Preserved JavaScript non-finite number semantics as `result_type="number"`, JSON `null`, and an additive `non_finite_number` label; all public JSON mirrors now reject NaN/Infinity serialization.

### Changed
- Standardized every public `timeout` input as a JSON `number`, so fractional values such as `1.5` are accepted consistently.
- Extended `page_pointer_drag_element.source` with the symmetric tagged element form, added preferred offset names `dx`/`dy`, and retained legacy bare-source plus `x`/`y` input compatibility.
- Added a schema-derived 69-tool parameter table to `docs/tool-contract.md`, locked to the Pydantic schemas by the schema snapshot test.

### Verification
- Added unit, schema, policy, strict-JSON, dialog, pointer, and network regressions plus real-Chromium checks for pending-dialog recovery, immediate no-dialog response, first-packet listener return, and non-finite JavaScript results.

## [0.7.8] - 2026-07-29

### Fixed
- Pinned the MCP Python SDK to `mcp>=1.0.0,<2`, preventing fresh installs from resolving MCP 2.x and failing during 1.x handler registration.
- Added an early SDK compatibility guard so already-broken environments receive an actionable pip repair command instead of an internal `Server.list_tools` `AttributeError`.

### Changed
- `drissionpage-mcp doctor` now reports the supported MCP range and constructs the real server to verify tools/list, tools/call, resources/list, and resources/read handler wiring.
- Documented exact argument names and JSON examples for frequently miscalled wait, dialog, scroll, frame, upload, URL-blocking, permission, and element-drag inputs.

### Verification
- Added a no-cache clean-wheel CI job that resolves dependencies from PyPI, validates doctor server wiring, and completes a real stdio initialize plus tools/list handshake.

## [0.7.7] - 2026-07-28

### Added
- Added six default-loaded browser-owned capabilities, growing the ordered registry to 69 tools: origin-scoped permission observation/set/reset, managed PDF/MHTML export, browser file-chooser upload, and isolated HTTP authentication navigation.
- Added `DP_MCP_ARTIFACT_ROOT` for generated page artifacts. Successful exports return safe relative paths, MIME type, size, SHA-256, sanitized source URL, `ArtifactRef`, and a linked exact-once `ActionReceipt`.

### Security
- HTTP auth credentials are never returned. Fetch handlers are removed after navigation, credentials are contained in a dedicated Chromium BrowserContext, and `tab_close` disposes that context because CDP does not provide an HTTP auth-cache purge command.
- File chooser paths remain restricted to `DP_MCP_UPLOAD_ROOT`, successful results return basenames only, and interception is disabled on success, failure, and timeout.
- Permission overrides are bounded to an exact HTTP(S) origin and the current browser context. Native operating-system permission prompts and notification-center control are not claimed.

### Verification
- Added strict schema, replay, cleanup, redaction, registry snapshot, and Chrome-backed tests for permission grant/reset, valid PDF/MHTML contents, chooser injection without an operating-system picker, Basic Auth handler cleanup, and isolated-context disposal.

## [0.7.6] - 2026-07-27

### Added
- Added a backward-compatible structured element target contract for selector and accessibility role/name lookup, with ordered DrissionPage frame and Shadow DOM scopes across element reads, actions, waits, uploads, and click-download correlation.
- Added default-registered `page_accessibility_snapshot`, `page_dialog_observe`, and `element_state_get`, bringing the ordered atomic registry to 63 tools. All tools load automatically without capability profiles or an opt-in `full` mode.

### Changed
- Native element clicks now run off the asyncio event loop so a concurrent dialog observer or responder can inspect and handle a blocking JavaScript dialog without user intervention.
- Structured target results include target kind and scope metadata while legacy string-selector calls retain their existing result shape.
- Accessibility snapshot field values and value-like properties are redacted by default and require explicit `include_values=true`; dialog responses are serialized per tab and native handling runs off the asyncio event loop.
- Structured target scope resolution enters all frames before all Shadow DOM hosts; arbitrary frame/shadow interleaving is not part of the 0.7.6 contract.

### Verification
- Added strict discriminated-target, accessibility ambiguity, typed success/schema, and real-browser coverage for cross-origin OOPIF input, closed Shadow DOM click/state, scoped accessibility snapshots, and dialog observe/respond concurrency.

## [0.7.5] - 2026-07-24

### Added
- Added default-registered `browser_headers_set`, `browser_user_agent_set`, `browser_cache_clear`, and `network_blocked_urls_set`, bringing the ordered atomic registry to 60 tools without capability profiles or an opt-in `full` mode.
- Added strict bounded schemas for request headers, user-agent overrides, optional platform metadata, and blocked URL patterns.

### Changed
- Successful header, user-agent, and blocked-URL writes echo the accepted values by default for MCP callbacks and verification. User-agent writes also return the previous value for explicit restoration.
- `browser_cache_clear` clears only the browser HTTP cache; Cookies, localStorage, and sessionStorage are preserved.

### Verification
- Added typed success, strict input, DrissionPage argument mapping, failure propagation, registry/schema, and real-browser request-environment regression coverage.
- Added real-browser checks for header and user-agent propagation, URL blocking and clearing, cache invalidation, and Cookie/Web Storage preservation.

## [0.7.4] - 2026-07-23

### Added
- Added default-registered `browser_cookies_set`, `browser_cookies_delete`, and `browser_cookies_clear` tools, bringing the ordered atomic registry to 56 tools without profiles or an opt-in `full` mode.
- Added bounded batch Cookie writes for browser-only login flows, with typed snake_case fields mapped to DrissionPage's Cookie setter contract.

### Changed
- `browser_cookies_set` returns the accepted Cookie payload and echoes Cookie values by default so MCP callbacks can consume and verify the write result.

### Verification
- Added strict input, typed output, field-mapping, failure propagation, registry/schema, and real-browser set/get/delete/clear regression coverage.

## [0.7.3] - 2026-07-22

### Changed
- Corrected the `shadow_find` and `shadow_find_all` descriptions: supported DrissionPage 4.x runtimes expose both tested open roots and closed roots that page JavaScript cannot access. Pointer element targeting remains limited to same-origin iframe and open-shadow paths.
- Kept the public registry at 53 generic browser tools with no component-library, site-specific, or business-workflow branches.

### Verification
- Added a deterministic cross-origin OOPIF and closed Shadow DOM fixture, public-MCP regression coverage, and a focused Ubuntu/macOS/Windows browser-boundary CI matrix.
- Added ten-cycle clear-before-native-input regression coverage for controlled and validation inputs without introducing form or component-library branches.
- Stabilized the strict natural-drag fixture by keeping deterministic planned-delay coverage separate from browser event-scheduling jitter while retaining held-move, duration, endpoint, bounded-step, and eased-path acceptance checks.

## [0.7.2] - 2026-07-21

### Removed
- Removed form, component-library, challenge, batch-action, and convenience-workflow tools from the public registry. These procedures compose safely from browser primitives and do not belong in the core capability layer.
- Deleted the dedicated form, challenge, vision-workflow, and convenience-workflow scripts, schemas, prompts, policy flags, and tests. No compatibility aliases or placeholder tools were added.
- Removed action-history retention, generic task/retry state, generated Python snippets, unused snapshot flags, and public runtime inventory resources.

### Changed
- Narrowed the ordered public registry to 53 generic browser tools. Form, challenge-observation, verified multi-click, and business workflows now compose observation, discovery, interaction, wait, upload, network, and state-read primitives in clients or external Skills.
- Reduced the MCP guidance surface to zero prompts and one static, browser-independent `drissionpage://skills/catalog` resource. The catalog declares the external `skills/<skill-name>/SKILL.md` path convention; Skills remain optional and outside the Python distribution.
- Simplified pointer execution to two atomic profiles: one-step exact `direct` movement and a reproducible 24-step eased cubic `natural` path. Both end at the exact target, drag holds one button across ordered waypoints, and failures after press still attempt release.
- Serialized tool execution and cleanup around the shared browser context. Unknown tools and invalid arguments are rejected before browser initialization.
- Saved screenshot results now expose only a normalized path relative to `DP_MCP_SCREENSHOT_ROOT`.
- Kept `element_click_and_download` and `page_dialog_respond` with correlated `ActionReceipt` and safe `ArtifactRef` evidence because their event timing and side-effect correlation cannot be reproduced safely as separate calls.
- Reworked W01-W04 to complete controlled inputs, contenteditable, ARIA widgets, native controls, uploads, and submission with retained atomic tools.
- Moved reusable form and visual workflow guidance to optional Skills outside the Python wheel and sdist.

### Verification
- Added regression coverage for serialized execution, no-history behavior, safe screenshot identifiers, direct/natural pointer semantics, optional-Skills discovery, and removed public surfaces.
- Regenerated the public tool schema snapshot and retained the ten-run W01-W08, browser integration, download/dialog receipt, replay, artifact, protocol, and packaging gates.

## [0.7.1] - 2026-07-20

### Fixed
- Fixed repeated native text input on Linux headless Chromium by using the platform-independent DrissionPage clear path before real input.
- Added a regression test for the clear-before-input contract and verified controlled-input event evidence after repeated writes.

### Changed
- Added the public-tool W01-W08 benchmark runner with ten isolated runs per workload, machine-readable results, browser/DrissionPage runtime evidence, and duplicate-side-effect accounting.
- Isolated the Ubuntu benchmark on its own runner, preferred the runner's preinstalled Chrome with a shared temporary directory for uploads, kept strict browser startup enforcement in the single coverage/browser gate and benchmark job, and printed failed-run evidence directly in CI logs.
- Kept the public registry at 62 tools and clarified that `TaskContext.retry_limit` is reserved metadata; 0.7.x does not perform automatic retries.
- Consolidated repeated receipt counter/state advancement inside the task context without changing receipt or resource output fields.

### Verification
- Local headless benchmark: 80/80 workload runs on both macOS/Chrome and Linux/Chromium, each W01-W08 at 10/10 with zero duplicate submissions or downloads.
- Full local coverage run: 553 passed, 2 skipped, 95.08% coverage. Ubuntu CI repeats the benchmark on a fresh runner and uploads the JSON report on both success and failure.

### Release Scope
- 0.7.1 is a reliability and simplification release. Table/grid extraction, `PageModel`, public `TargetRef`, checkpoints, planners, workflow DSLs, and other 0.8/0.9 capabilities remain out of scope.

## [0.7.0] - 2026-07-18

### Added
- Added `form_fill` for verified native and rich-control mutation and `form_submit` for one authorized, evidence-classified submission with live-task operation-key replay.
- Added capability-probed `page_dialog_respond` for pending alert, confirm, and prompt dialogs.
- Added `element_click_and_download` with policy-controlled storage, SHA-256 and size verification, safe relative paths, `ArtifactRef`, and correlated `ActionReceipt` output.
- Added `TaskContext`, action receipt, artifact inventory, capability, policy, resource, protocol, and schema contracts for externally consequential workflows.

### Changed
- Extended `element_click` additively with left/right/middle button selection and single/double-click semantics while preserving existing defaults.
- Updated model guidance so clearly authorized tasks can use `form_fill` and `form_submit` without redundant confirmation; `form_fill_preview` remains the stable no-submit compatibility path.
- Ambiguous submission and download results are frozen as non-success outcomes and never trigger an implicit second external action.
- Public registry now exposes 62 tools.

### Security
- Enforced submission/download policy denial before browser side effects, operation claims, or artifact allocation.
- Sanitized public URLs to well-formed HTTP(S) origin/path data and removed credentials, query, fragment, local paths, and unsafe schemes.
- Hardened downloads against cancellation bookkeeping leaks and path replacement races by draining native work and hashing a stable no-follow file descriptor.

### Release Scope
- 0.7.0 ships the browser-backed task-completion features and typed safety contracts. The W01-W08 ten-run 9/10 reliability benchmark, expanded branch coverage, and final stability audit are scheduled for 0.7.1; this release does not claim that ten-run threshold.

## [0.6.2] - 2026-07-15

### Added
- Added up to six optional ordered `waypoints` to `page_pointer_drag` for canvas paths, map gestures, box selection, and visual-editor connections without exposing persistent button state.
- Added real Chromium coverage proving one press, held movement through every waypoint, exact final arrival, and one release.

### Changed
- Multi-segment coordinate drags reuse the existing motion planner and failure-safe pointer executor; no new public tool, action DSL, dependency, or output model was added.
- Public registry remains at 58 tools.

## [0.6.1] - 2026-07-14

### Added
- Added `page_pointer_drag_element` for atomically resolved element-to-element, relative-offset, and track-ratio dragging through the top document or one same-origin iframe, plus CSS paths through nested open Shadow DOM hosts.
- Added drag-specific distance-aware timing, correlated event intervals, reaction/grip/release phases, optional micro-pauses, bounded overshoot, and exact-target correction metadata.
- Added strict local Chromium slider fixtures and positive/negative tests for same-origin iframe, nested open Shadow DOM, trusted held-button movement, direct-drag rejection, and layout-drift recovery.

### Changed
- Pointer input schemas and public tools moved from `tools/common.py` to `tools/pointer.py` without compatibility wrappers.
- `page_pointer_drag` now uses a dedicated held-drag kinematics profile rather than reusing ordinary pointer movement configuration.
- Model guidance now prefers selector-first `page_pointer_drag_element` and reserves coordinate `page_pointer_drag` for fresh visual evidence.
- Public registry now exposes 58 tools.

## [0.6.0] - 2026-07-13

### Added
- Added `page_detect_challenges`, `page_click_xy_batch`, and `page_wait_challenge_result` as general autonomous visual orchestration tools.
- Added generic attribute/property equals and non-empty conditions to `wait_until`.
- Added optional `page_click_xy.delay_before_press_ms` timing control.

### Changed
- Model guidance now teaches an autonomous detect, observe, visual-action, poll, classify, and bounded-retry workflow.
- Verification-related descriptions explicitly position the server as a fully autonomous general tool for authorized automation and technical exchange while not recommending bypass of human-verification systems or promising completion.
- Public registry now exposes 57 tools.

## [0.5.9] - 2026-07-12

### Added
- Added `page_pointer_move` for natural viewport movement without clicking.
- Added `page_pointer_drag` for one failure-safe natural drag with held-button CDP movement and guaranteed release cleanup.
- Added compact tool input guidance for required/optional fields, defaults, enums, bounds, types, and descriptions.

### Changed
- Model-facing MCP instructions, resources, and prompts now teach selector-first move/click/drag selection, viewport coordinate mapping, bounded verification, and stale-coordinate recovery.
- Pointer move, click, and drag share the same motion planner and immutable action sequence; the public registry now exposes 54 tools.
- Structured extraction guidance now allows navigation as the sole destructive setup step and keeps extraction read-only afterward.

## [0.5.8] - 2026-07-10

### Added
- Natural vision-directed pointer movement for `page_click_xy` with 20–35 cubic Bézier steps, 8–25 ms randomized point intervals, ±0.5 CSS-pixel intermediate jitter, and exact target arrival.
- Smoothstep ease-in-out sampling (`t*t*(3-2*t)`), 100–300 ms post-arrival reaction delay, and 50–120 ms mouse-button hold timing.
- `natural`, `precise`, and `direct` pointer profiles.
- Typed pointer motion metadata in `page_click_xy` results for step count, start/target coordinates, reaction delay, hold duration, and planned duration.

### Changed
- `page_click_xy` now executes an explicit Chromium CDP pointer move/press/release action chain instead of the former direct coordinate click.
- Pointer motion is owned by a dedicated per-tab capability; the old interaction-level coordinate-click method was removed without a compatibility wrapper.

## [0.5.7] - 2026-07-08

### Changed
- Model usage guidance is now workflow-first: fresh navigate-and-inspect tasks point to `browser_open_and_snapshot`, link discovery points to `browser_extract_links`, and navigation-only retries still use `page_navigate`.
- MCP prompt recipes now prefer workflow helpers and bounded page-understanding tools before lower-level primitives such as full HTML extraction.
- `drissionpage://tools/catalog` now includes tool descriptions alongside annotations and output data schema names so AI clients can choose tools with less guesswork.
- Recovery hints now route fresh-session, schema, and unknown-tool failures toward `browser_open_and_snapshot`, `drissionpage://tools/catalog`, and `drissionpage://guide/model-usage`.

### Compatibility
- Public registry remains 52 tools; this release adds no public tools and does not change input schemas, the `JSON_RESULT` envelope, `structuredContent`, or typed `outputSchema` contracts.

## [0.5.6] - 2026-07-07

### Added
- Added workflow tools: `browser_open_and_snapshot`, `browser_extract_links`, and `form_fill_preview`.
- Added network listener beta tools: `network_listen_start`, `network_listen_wait`, and `network_listen_stop` for HTTP/XHR/Fetch observation without interception.
- Added `drissionpage://session/config` for redacted browser/profile configuration visibility.
- Added MCP-exposed model usage guide through server instructions, `drissionpage://guide/model-usage`, and `drissionpage_mcp_usage_playbook`.
- Added deterministic local fixture coverage for workflow forms, links, and network fetch/XHR scenarios.

### Changed
- Tool registry now exposes 52 public tools.
- `drissionpage-mcp doctor` redacts configured paths and still reports DrissionPage 5.x as unsupported; 0.5.6 remains on `DrissionPage>=4.1.1.4,<5`.

### Security
- Form field maps, network headers, and body-like action-history arguments are redacted by default.
- Network body capture remains opt-in and bounded by `max_body_chars`.

## [0.5.5] - 2026-07-06

### Added
- Added `element_upload_file` with `DP_MCP_UPLOAD_ROOT` path policy and filename-only result data.
- Added interaction primitives: `page_scroll`, `element_scroll_into_view`, `element_hover`, `keyboard_press`, `element_select`, and `element_check`.
- Added iframe read-only tools: `frame_list`, `frame_snapshot`, and `frame_find`.
- Added shadow DOM read-only tools: `shadow_find` and `shadow_find_all`.
- Added cookie/storage tools: `browser_cookies_get`, `storage_get`, `storage_set`, and `storage_clear`.
- Added `drissionpage://session/state` for redacted cookie names and storage keys.
- Added browser integration coverage for upload, interactions, iframe, shadow DOM, cookies, and storage on local fixtures.

### Changed
- Tool registry now exposes 46 public tools.
- `drissionpage-mcp doctor` now reports DrissionPage 5.x as unsupported; 0.5.5 remains on `DrissionPage>=4.1.1.4,<5`.

## [0.5.4] - 2026-07-03

### Security
- Chrome sandbox now stays enabled by default. `DP_NO_SANDBOX=1` remains available only for restricted container/root environments that cannot launch Chromium with sandboxing.

### Changed
- `drissionpage-mcp doctor` now warns when `DP_NO_SANDBOX` disables Chrome sandboxing.
- Public setup examples no longer suggest `DP_NO_SANDBOX=1` for normal desktop/client installs.

## [0.5.3] - 2026-07-02

### Added
- Added `page_console_logs` for bounded current-tab console messages with level filtering, cursor pagination, and result limits.
- Added console summaries to `page_observe`.
- Added console change fields to observable action results: `console_errors_added`, `console_warnings_added`, and `new_console_messages`.
- Added browser fixture coverage for console logs emitted during page load and user actions.

### Changed
- Tool registry now exposes 29 public tools.
- Session history summaries include compact console-change information when a tool response contains observable `changes`.

## [0.5.2] - 2026-07-01

### Added
- Added `page_observe` for compact page fingerprints with URL, title, ready state, element counts, visible text samples, active element, and limits.
- Added `page_evaluate` for bounded JavaScript execution with JSON-safe result metadata.
- Added `wait_until` for observable dynamic UI conditions including present, visible, hidden, detached, clickable, stable, text, and URL waits.
- Added optional `observe=true` changes on `page_navigate`, `element_click`, and `element_type`.
- Added local browser fixture coverage for observable delayed UI flows.

### Changed
- Tool registry now exposes 28 public tools.
- Timeout recovery hints now include `wait_until` for condition-specific waits.
- Session history summaries include compact observable-change information when a tool response contains `changes`.

## [0.5.1] - 2026-06-30

### Added
- Added tab management tools: `tab_list`, `tab_switch`, and `tab_close`.
- Added `page_navigate(new_tab=true)` for opening a URL in a new tracked browser tab.
- Added `drissionpage://session/history` with redacted recent tool actions.
- Added response size metadata to bounded page, form, and repeated-element outputs.

### Changed
- Tool registry now exposes 25 public tools.
- Browser tab state is synchronized with tabs opened outside MCP commands, such as `target="_blank"` links.

## [0.5.0] - 2026-06-29

### Added
- Added `form_inspect`, a read-only form inventory tool that returns forms, controls, labels, selectors, methods/actions, required/disabled/read-only state, select options, and opt-in non-password values.
- Added deterministic browser coverage for form inspection on the local form fixture.

### Changed
- Tool registry now exposes 22 public tools while preserving the no-alias contract from 0.4.x.

## [0.4.10] - 2026-06-29

### Added
- Added machine-readable recovery hints under `error.details.hints` for common MCP failures, including missing elements, timeouts, browser startup failures, policy denials, screenshot failures, navigation failures, invalid arguments, and unknown tools.

### Changed
- Failure payloads now guide MCP clients toward safe next actions such as `page_snapshot`, `element_find_all`, `wait_for_element`, `page_get_url`, `drissionpage-mcp doctor --launch-browser`, or the relevant environment variable without changing the top-level JSON_RESULT envelope.
- `page_snapshot` now balances its total element budget across headings, links, buttons, inputs, and forms before filling remaining capacity, so link-heavy pages still expose high-value controls for recovery flows.
- Troubleshooting guidance now points users to structured recovery hints before manual selector debugging.

## [0.4.9] - 2026-06-29

### Added
- Added `page_snapshot` preview tool for bounded page outlines with text excerpts, headings, links, buttons, inputs, forms, counts, truncation metadata, and recommended selectors.
- Added `element_find_all` preview tool for bounded repeated-element extraction from lists, cards, tables, and search results.
- Added deterministic catalog fixture coverage plus read-only evals for LLM page-understanding tasks.

### Changed
- Tool registry now exposes 21 public tools while preserving the no-alias contract from 0.4.x.
- Typed `outputSchema` contracts now cover the new page-understanding payloads.

## [0.4.5] - 2026-06-29

### Changed
- Tool input schemas now reject unknown fields instead of silently ignoring MCP client or LLM argument typos.
- README and troubleshooting docs now include absolute-Python MCP configuration fallbacks for GUI clients and headless browser guidance for remote/container environments.
- Playground setup guidance now points to maintained README/tool-contract configuration snippets.

### Fixed
- Unknown MCP tool arguments now return structured `MCP_ARGUMENT_INVALID` errors before browser startup.
- Fixed `outputSchema` generation so MCP clients that validate `structuredContent` accept real successful tool responses.
- Removed stale coverage, security, and Codecov documentation references left from earlier releases.

## [0.4.1] - 2026-06-26

### Added
- Added selector normalization metadata (`selector`, `locator`, `selector_strategy`, and `selector_normalized`) to element and wait tool responses.
- Added real-browser selector regression coverage for LLM-friendly bare CSS selectors, explicit DrissionPage locators, and CSS attribute selectors.

### Changed
- Bare MCP selectors are now normalized as CSS before calling DrissionPage (`h1` -> `css:h1`, `input[name=q]` -> `css:input[name=q]`); use `text:...` for text matching.
- `element_get_property` now uses the LLM-friendly public input field `property` instead of `property_name`.
- `element_find` now defaults to a 3-second timeout for faster failed-selector feedback while explicit wait tools keep longer defaults.
- Browser-backed CI jobs now require Chrome/Chromium after installation instead of silently skipping browser integration failures.
- Documented Codex CLI/IDE MCP setup with `config.toml` examples and Codex verification commands.

### Fixed
- Fixed MCP `serverInfo.version` so clients see the `drissionpage-mcp` package version instead of the installed MCP SDK version.
- Fixed selector behavior where bare `h1` could match text inside `<style>` and bare CSS attribute selectors such as `input[name=q]` could fail.

## [0.4.0] - 2026-06-26

### Added
- MCP Resources for `drissionpage://session/summary`, `drissionpage://page/current`, `drissionpage://tools/catalog`, and `drissionpage://policy/summary`.
- MCP Prompts for navigation summaries, structured extraction, safe form filling, and page debugging.
- Typed per-tool MCP `outputSchema` data contracts for all 19 public tools.
- Deterministic pytest eval harness under `tests/evals/`.

### Changed
- Tool success responses now put primary machine-readable values in `structuredContent.data` instead of relying on result text.
- Documentation now describes the 0.4.0 resource, prompt, typed-output, and eval contracts.

### Removed
- Removed the 0.3.x public tool aliases `element_input_text` and `wait_sleep`; use `element_type` and `wait_time`.
- Removed internal compatibility facades used by older tests in favor of direct tool definitions.

## [0.3.2] - 2026-06-25

### Added
- Shared MCP `outputSchema` envelope for tools when supported by the installed MCP Python SDK.
- Opt-in local safety policy for navigation allowlists/blocklists, private-network blocking, and screenshot save-root restrictions.
- Release/documentation checks for version drift, Codecov upload configuration, and package-content expectations.

### Changed
- Navigation, history, refresh, click, and typing paths now prefer DrissionPage-native load stabilization with bounded async fallback sleeps.
- README and release docs now describe the current 0.3.2 package state and compatibility-alias policy.

### Security
- Disallowed navigation is rejected before browser initialization when safety policy variables are configured.
- Runtime request throttling remains deferred for the local stdio server; users should respect target-site rate limits and revisit throttling before adding remote transport.

## [0.3.1] - 2026-06-24

### Added
- CI coverage upload to Codecov with README badges and a local 75% coverage floor.
- CI wheel-content check to prevent broad top-level packages from leaking into release artifacts.

### Removed
- Removed the legacy top-level `src` compatibility shim package from source and release artifacts.

### Fixed
- `element_type` now stops immediately when its element wait fails instead of continuing to input.
- Release wheels now expose only the canonical `drissionpage_mcp` top-level package.

## [0.3.0] - 2026-06-24

### Added
- Stable MCP tool response contract with `### JSON_RESULT` text fallback and native `structuredContent`.
- Machine-readable tool error payloads and stable error codes exported from `drissionpage_mcp.errors`.
- `drissionpage-mcp doctor` / `self-test` diagnostics, including optional browser launch verification.
- Deterministic local HTTP fixture, MCP protocol tests, schema snapshot tests, response contract tests, doctor tests, browser integration tests, and CI workflow structure tests.
- GitHub CI jobs for lint, unit, protocol, package, and browser integration checks.
- Open-source governance docs: contributing guide, security policy, compatibility policy, troubleshooting, tool contract, release checklist, and issue/PR templates.
- DrissionPage 4.2 beta compatibility using the `Chromium` browser API instead of relying on deprecated `ChromiumPage`.
- Extraction tools: `element_get_text`, `element_get_attribute`, `element_get_property`, and `element_get_html`.
- Backward-compatible aliases: `element_input_text` and `wait_sleep`; URL wait tool `wait_for_url`.

### Changed
- Python support is now documented and packaged as Python `>=3.10`, matching the MCP SDK dependency floor.
- `page_screenshot` now returns MCP image content plus structured JSON metadata including MIME type, inline/path mode, `full_page`, byte size, width, and height.
- README and example configuration docs now emphasize a practical first-success path and verifiable MCP client setup.

### Fixed
- Correct package import path from the generic `src` package to `drissionpage_mcp`, with old `src` shims retained for source checkouts.
- MCP tool annotations now expose read-only/destructive/idempotent hints.
- Screenshot responses no longer leak temporary files.
- Response rendering is idempotent when `get_content()` is called more than once.
- Browser startup no longer disables web security by default.

### Planned
- Higher-level form workflows
- Optional session persistence
- Proxy support
- Network interception

## [0.1.0] - 2024-01-22

### Added
- Initial release of DrissionPage MCP Server
- 14 browser automation tools:
  - Navigation tools (4): navigate, go_back, go_forward, refresh
  - Element interaction tools (3): find, click, type
  - Page action tools (5): screenshot, resize, click_xy, close, get_url
  - Wait operation tools (2): wait_for_element, wait_time
- Full MCP (Model Context Protocol) integration
- Type-safe tool definitions using Pydantic
- Comprehensive documentation:
  - Quick Start Guide
  - Testing and Integration Guide
  - Publishing Guide
  - Configuration Examples
- Local testing utilities (playground/)
- Unit test suite
- Professional project structure

### Fixed
- Fixed missing method implementations in tab.py:
  - Added `find_element()` method
  - Added `type_text()` method
  - Updated `click_element()` to support timeout parameter
- Fixed missing `wait()` method in context.py
- Fixed syntax errors in playground/local_test.py
- Fixed import path issues in test and example files
- Updated MCP SDK integration for compatibility with latest version

### Changed
- Reorganized configuration examples into examples/ directory
- Updated README.md for professional presentation
- Enhanced pyproject.toml with comprehensive metadata
- Improved error handling throughout the codebase
- Optimized DrissionPage 4.x API usage

### Documentation
- Created comprehensive README.md
- Added QUICKSTART.md for 5-minute setup
- Added TESTING_AND_INTEGRATION.md for detailed usage
- Added PUBLISHING.md for maintainers
- Added examples/README.md for configuration guidance
- Created REFACTORING_SUMMARY.md documenting all changes

## [0.0.1] - 2024-01-08

### Added
- Initial project scaffold
- Basic MCP server structure
- DrissionPage integration framework
- Tool definition system

---

**Legend**:
- `Added` for new features
- `Changed` for changes in existing functionality
- `Deprecated` for soon-to-be removed features
- `Removed` for now removed features
- `Fixed` for any bug fixes
- `Security` in case of vulnerabilities

[Unreleased]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.6...HEAD
[0.8.6]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.5...0.8.6
[0.8.5]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.4...0.8.5
[0.8.4]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.3...0.8.4
[0.8.3]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.2...0.8.3
[0.8.2]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.1...0.8.2
[0.8.1]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.0...0.8.1
[0.8.0]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.9...0.8.0
[0.7.9]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.8...0.7.9
[0.7.8]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.7...0.7.8
[0.7.7]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.6...0.7.7
[0.7.6]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.5...0.7.6
[0.7.5]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.4...0.7.5
[0.7.4]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.3...0.7.4
[0.7.3]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.2...0.7.3
[0.7.2]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.6.2...v0.7.0
[0.6.2]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.5.9...v0.6.0
[0.5.9]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.5.8...v0.5.9
[0.5.8]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.5.7...v0.5.8
[0.5.7]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.5.6...v0.5.7
[0.5.6]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.5.5...v0.5.6
[0.5.5]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.5.4...v0.5.5
[0.5.4]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.5.3...v0.5.4
[0.5.3]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.4.10...v0.5.0
[0.4.10]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.4.9...v0.4.10
[0.4.9]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.4.5...v0.4.9
[0.4.5]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.4.1...v0.4.5
[0.4.1]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.2.0...v0.3.0
[0.1.0]: https://github.com/jumodada/Drissionpage-MCP-Server/releases/tag/v0.1.0
[0.0.1]: https://github.com/jumodada/Drissionpage-MCP-Server/releases/tag/v0.0.1
