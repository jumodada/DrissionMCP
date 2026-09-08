# DrissionPage MCP Skills

DrissionPage MCP keeps browser primitives in the MCP server and publishes
procedural guidance as Skills. A Skill is a Markdown procedure that tells an
MCP client how to combine `tools/list`, typed inputs, fresh observations, and
postcondition checks for one bounded class of work.

## Where Skills live

The repository contains example Skills under `skills/<name>/SKILL.md`. They are
source documentation, not Python modules: the wheel and sdist intentionally do
not include them. The MCP server exposes discovery metadata through
`drissionpage://skills/catalog`. In 0.8.4, catalog schema v2 publishes a fixed
`v0.8.4` source revision from `skills-manager`, a SHA-256 for each `SKILL.md`,
the Skill and compatible MCP versions, required public tools, fixture, and
verification status.

## Example catalog

| Skill | Use it for | Important boundary |
| --- | --- | --- |
| `cross-origin-iframe-probe` | Decide whether an iframe is bridge-readable and choose frame, outer geometry, scroll, coordinate, keyboard, or parent-page paths | Use `boundary` plus `document_access`; origin alone is not a capability verdict |
| `turnstile-testing` | Turnstile test fixtures, authorized production challenge interaction, coordinate geometry, and parent-page verification | Use the documented support matrix and verify the resulting page state |
| `xiaohongshu-content-research` | Bounded, read-only note research and the local `social-notes` fixture | Stop on robots, login, captcha, safety restriction, or rate-limit boundaries |

## Skill contract

Every Skill should:

1. Declare only a stable `name` and a one-sentence `description` in YAML frontmatter.
2. State authorization, privacy, rate, login, captcha, and submission boundaries.
3. Compose existing atomic tools instead of inventing tool names or hidden APIs.
4. Re-observe after navigation and consequential actions; verify explicit
   postconditions instead of trusting a click result.
5. Describe unsupported cases and a stop condition.
6. Prefer deterministic local fixtures for repeatable tests.
7. In multi-tab flows, carry the MCP `tab_id` returned by a successful tool into
   later tab-scoped calls instead of depending on mutable current-tab state.

Skills must not add browser capabilities, silently change safety policy, or echo
secrets. Site-specific challenge and business decisions belong in the Skill or
host application and require the operator's authorization.

Validate all repository examples and their catalog metadata with:

```bash
python playground/validate_skills.py --json
```

Install the fixed 0.8.4 Skills release for Codex or Claude Code:

```bash
git clone --branch v0.8.4 https://github.com/jumodada/skills-manager.git
cd skills-manager
python install.py verify --json
python install.py install --client codex --json
# Or: python install.py install --client claude --json
```

Use `--skill turnstile-testing` to install one Skill or `--target` for another
host directory. Existing Skill directories are not overwritten unless the
operator supplies `--force`.

## Using a repository example

From a checkout, open the requested file and provide it to the MCP host as
Skill context. The Skill itself does not run a browser. The host performs the
tool calls against the connected DrissionPage MCP server:

```text
Repository: https://github.com/jumodada/skills-manager/tree/v0.8.4
Skill: skills/xiaohongshu-content-research/SKILL.md
Core server minimum: drissionpage-mcp 0.8.4; current release: 0.8.8
```

For release validation, install a built wheel or sdist in a clean environment,
then run the local fixture using that interpreter:

```bash
DP_HEADLESS=1 \
python playground/run_mcp_lab.py \
  --case social-notes \
  --command /tmp/clean-venv/bin/python \
  --json \
  --args -I -m drissionpage_mcp.cli --log-level ERROR
```

`-I` prevents the server subprocess from importing a repository checkout ahead
of the installed release package. This validates the Skill's tool sequence
without contacting Xiaohongshu.
