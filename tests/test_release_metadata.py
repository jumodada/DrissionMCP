"""Release metadata checks for the current release and historical contracts."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback.
    import tomli as tomllib

import drissionpage_mcp


def test_package_version_metadata_is_0_8_6() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == "0.8.6"
    assert drissionpage_mcp.__version__ == "0.8.6"


def test_release_pins_mcp_sdk_to_supported_major_version() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "mcp>=1.0.0,<2" in pyproject["project"]["dependencies"]
    assert "mcp>=1.0.0,<2" in requirements


def test_changelog_describes_breaking_alias_removal() -> None:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")

    assert "## [0.4.1]" in changelog
    assert "## [0.4.0]" in changelog
    assert "element_input_text" in changelog
    assert "wait_sleep" in changelog


def test_readmes_and_changelog_publish_latest_0_8_6_summary() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_cn = Path("README_CN.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    latest_changelog = changelog.split("## [0.8.6]", 1)[1].split("## [0.8.5]", 1)[0]
    previous_changelog = changelog.split("## [0.8.5]", 1)[1].split("## [0.8.4]", 1)[0]
    current_changelog = changelog.split("## [0.8.0]", 1)[1].split("## [0.7.9]", 1)[0]
    install_changelog = changelog.split("## [0.7.8]", 1)[1].split("## [0.7.7]", 1)[0]
    request_changelog = changelog.split("## [0.7.5]", 1)[1].split("## [0.7.4]", 1)[0]
    cookie_changelog = changelog.split("## [0.7.4]", 1)[1].split("## [0.7.3]", 1)[0]
    boundary_changelog = changelog.split("## [0.7.3]", 1)[1].split("## [0.7.2]", 1)[0]
    cleanup_changelog = changelog.split("## [0.7.2]", 1)[1].split("## [0.7.1]", 1)[0]

    browser_lab_url = "https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/drissionpage-mcp-browser-lab.gif"
    assert browser_lab_url in readme and browser_lab_url in readme_cn
    assert "vision-natural-pointer-demo.gif" not in readme
    assert "vision-natural-pointer-demo.gif" not in readme_cn
    assert "website/public/og-browser-lab.png" not in readme
    assert "website/public/og-browser-lab.png" not in readme_cn
    assert "Watch the original natural pointer demo" not in readme
    assert "观看原始自然指针演示" not in readme_cn
    assert "## 🆕 Latest Version: v0.8.6" in readme
    assert "Released on 2026-08-30" in readme
    assert "69 Typed Browser Tools" in readme
    assert "Form Operations" not in readme
    assert "page_dialog_respond" in readme
    assert "element_click_and_download" in readme
    assert "optional Skill" in readme
    assert "### 🌐 Navigation (5 tools)" in readme
    assert "### 🎯 Element Interaction & Extraction (16 tools)" in readme
    assert "### 📸 Page Operations (18 tools)" in readme
    assert "### 🌍 Browser Environment (6 tools)" in readme
    assert "### 🌐 Network Control & Observation (4 tools)" in readme
    assert "## 🆕 最新版本：v0.8.6" in readme_cn
    assert "发布日期：2026-08-30" in readme_cn
    assert "69 个类型化浏览器工具" in readme_cn
    assert "表单工具（3 个）" not in readme_cn
    assert "page_dialog_respond" in readme_cn
    assert "element_click_and_download" in readme_cn
    assert "可选 Skill" in readme_cn
    assert "### 🌐 导航工具（5 个）" in readme_cn
    assert "### 🎯 元素交互与提取（16 个）" in readme_cn
    assert "### 📸 页面操作（18 个）" in readme_cn
    assert "### 🌍 浏览器环境（6 个）" in readme_cn
    assert "### 🌐 网络控制与观察（4 个）" in readme_cn
    assert "## [0.8.6] - 2026-08-30" in changelog
    assert "redaction" in latest_changelog
    assert "network_listen_wait" in latest_changelog
    assert "MCP Registry" in previous_changelog
    assert "GitHub OIDC" in previous_changelog
    assert "No MCP tools" in previous_changelog
    assert "## [0.8.0] - 2026-07-31" in changelog
    assert "include_values=true" in current_changelog
    assert "keyboard_press" in current_changelog
    assert "coordinate" in current_changelog and "keyboard" in current_changelog
    assert "250" in current_changelog
    assert "BrowserConnectError" in current_changelog
    assert "mypy" in current_changelog
    assert "No new public tool" in current_changelog
    assert "mcp>=1.0.0,<2" in install_changelog
    assert "doctor" in install_changelog
    assert "wheel" in install_changelog
    assert "stdio" in install_changelog
    assert "browser_headers_set" in request_changelog
    assert "network_blocked_urls_set" in request_changelog
    assert (
        "Cookies, localStorage, and sessionStorage are preserved" in request_changelog
    )
    assert "browser_cookies_set" in cookie_changelog
    assert "56 tools" in cookie_changelog
    assert "echoes Cookie values" in cookie_changelog
    assert "cross-origin OOPIF" in boundary_changelog
    assert "closed Shadow DOM" in boundary_changelog
    assert "ten-cycle" in boundary_changelog
    assert "browser event-scheduling jitter" in boundary_changelog
    assert "## [0.7.2] - 2026-07-21" in changelog
    assert "No compatibility aliases" in cleanup_changelog
    assert "ActionReceipt" in cleanup_changelog
    assert "ArtifactRef" in cleanup_changelog
    assert "ten-run" in cleanup_changelog
    assert "24-step" in cleanup_changelog
    assert "drissionpage://skills/catalog" in cleanup_changelog
    assert "## [0.6.2] - 2026-07-15" in changelog
    assert "optional ordered `waypoints`" in changelog
    assert "no new public tool" in changelog
    assert "## [0.6.1] - 2026-07-14" in changelog
    assert "Added `page_pointer_drag_element`" in changelog
    assert "distance-aware timing" in changelog
    assert "layout-drift recovery" in changelog
    assert (
        "[Unreleased]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.6...HEAD"
        in changelog
    )
    assert (
        "[0.8.6]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.5...0.8.6"
        in changelog
    )
    assert (
        "[0.8.5]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.4...0.8.5"
        in changelog
    )
    assert (
        "[0.8.4]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.3...0.8.4"
        in changelog
    )
    assert (
        "[0.8.3]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.2...0.8.3"
        in changelog
    )
    assert (
        "[0.8.2]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.1...0.8.2"
        in changelog
    )
    assert (
        "[0.8.1]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.8.0...0.8.1"
        in changelog
    )
    assert (
        "[0.8.0]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.9...0.8.0"
        in changelog
    )
    assert (
        "[0.7.9]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.8...0.7.9"
        in changelog
    )
    assert (
        "[0.7.8]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.7...0.7.8"
        in changelog
    )
    assert (
        "[0.7.7]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.6...0.7.7"
        in changelog
    )
    assert (
        "[0.7.6]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.5...0.7.6"
        in changelog
    )
    assert (
        "[0.7.5]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.4...0.7.5"
        in changelog
    )
    assert (
        "[0.7.4]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.3...0.7.4"
        in changelog
    )
    assert (
        "[0.7.3]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/0.7.2...0.7.3"
        in changelog
    )
    assert (
        "[0.7.2]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.7.1...v0.7.2"
        in changelog
    )
    assert (
        "[0.7.1]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.7.0...v0.7.1"
        in changelog
    )
    assert (
        "[0.7.0]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.6.2...v0.7.0"
        in changelog
    )
    assert (
        "[0.6.2]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.6.1...v0.6.2"
        in changelog
    )
    assert (
        "[0.6.1]: https://github.com/jumodada/Drissionpage-MCP-Server/compare/v0.6.0...v0.6.1"
        in changelog
    )


def test_release_guides_publish_0_8_6_contract_state() -> None:
    compatibility = Path("docs/compatibility.md").read_text(encoding="utf-8")
    contract = Path("docs/tool-contract.md").read_text(encoding="utf-8")
    troubleshooting = Path("docs/troubleshooting.md").read_text(encoding="utf-8")
    eval_readme = Path("tests/evals/README.md").read_text(encoding="utf-8")

    assert "## 0.7.9 to 0.8.0 Migration" in compatibility
    assert "## Unreleased Contract Changes" not in compatibility
    assert "## 0.8.5 to 0.8.6 Migration" in compatibility
    assert "The 0.8.6 registry contains 69 typed browser tools" in contract
    assert "DrissionPage MCP 0.8.6 exposes no MCP prompts" in contract
    assert "Challenge Surface 0.8.6 Checks" in troubleshooting
    assert "benchmark-results/0.8.6-task-completion.json" in troubleshooting
    assert "benchmark-results/0.8.6-task-completion.json" in eval_readme


def test_repository_example_skills_have_frontmatter_and_documented_entries() -> None:
    skills = {
        path.parent.name: path.read_text(encoding="utf-8")
        for path in Path("skills").glob("*/SKILL.md")
    }
    assert {
        "cross-origin-iframe-probe",
        "turnstile-testing",
        "xiaohongshu-content-research",
    } <= skills.keys()
    for name, text in skills.items():
        assert text.startswith("---\n")
        assert f"name: {name}" in text
        assert "description:" in text
        assert "drissionpage-mcp" in text
    guide = Path("docs/skills.md").read_text(encoding="utf-8")
    for name in skills:
        assert name in guide
    assert "--args -I -m drissionpage_mcp.cli" in guide
    assert "playground/validate_skills.py --json" in guide
    assert "v0.8.4" in guide


def test_public_readmes_advertise_atomic_core_and_optional_skills() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_cn = Path("README_CN.md").read_text(encoding="utf-8")
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    for text in (readme, readme_cn):
        assert "drissionpage://skills/catalog" in text
        assert "skills/<skill-name>/SKILL.md" in text
        assert 'profile="natural"' in text
        assert "zero MCP prompts" in text or "零个 MCP Prompt" in text
        for removed_surface in (
            "drissionpage://guide/model-usage",
            "drissionpage://tools/catalog",
            "drissionpage_mcp_usage_playbook",
            "browser_vision_guided_interaction",
        ):
            assert removed_surface not in text
    assert pyproject["project"]["urls"]["Skills"].endswith("/skills-manager")


def test_public_guides_show_exact_high_confusion_parameter_names() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_cn = Path("README_CN.md").read_text(encoding="utf-8")
    contract = Path("docs/tool-contract.md").read_text(encoding="utf-8")

    exact_calls = (
        '`wait_for_url(url_pattern="...")`',
        '`wait_until(condition="text_contains", value="...")`',
        '`page_dialog_respond(action="accept")`',
        "`page_scroll(pixels=...)`",
        '`frame_snapshot(frame_selector="...")`',
        "`element_upload_file(paths=[...])`",
        "`network_blocked_urls_set(urls=[...])`",
        '`browser_permission_set(setting="granted")`',
    )
    for text in (readme, readme_cn):
        for call in exact_calls:
            assert call in text

    assert "## Common Call Examples" in contract
    for field in (
        '"url_pattern"',
        '"text_contains"',
        '"action": "accept"',
        '"pixels"',
        '"frame_selector"',
        '"paths"',
        '"urls"',
        '"setting": "granted"',
    ):
        assert field in contract


def test_current_public_readmes_do_not_advertise_removed_workflow_tools() -> None:
    removed_tools = {
        "form_inspect",
        "form_fill",
        "form_fill_preview",
        "form_submit",
        "page_detect_challenges",
        "page_click_xy_batch",
        "page_wait_challenge_result",
        "browser_open_and_snapshot",
        "browser_extract_links",
    }

    for path in (Path("README.md"), Path("README_CN.md")):
        text = path.read_text(encoding="utf-8")
        for tool_name in removed_tools:
            assert tool_name not in text, (path, tool_name)


def test_public_readmes_keep_no_sandbox_out_of_general_setup_examples() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_cn = Path("README_CN.md").read_text(encoding="utf-8")

    assert '# DP_NO_SANDBOX = "1"' not in readme
    assert '# DP_NO_SANDBOX = "1"' not in readme_cn
    assert '"DP_NO_SANDBOX": "1"' not in readme
    assert '"DP_NO_SANDBOX": "1"' not in readme_cn


def test_public_guides_do_not_advertise_removed_alias_tools() -> None:
    for path in (
        Path("README.md"),
        Path("README_CN.md"),
        Path("playground/README.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "element_input_text" not in text
        assert "wait_sleep" not in text
        assert "19 tools" not in text
        assert "19 powerful tools" not in text
        assert "19 automation tools" not in text
        assert "19 个" not in text


def test_public_readmes_include_codex_mcp_configuration() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_cn = Path("README_CN.md").read_text(encoding="utf-8")
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    for text in (readme, readme_cn):
        assert "[mcp_servers.drissionpage]" in text
        assert 'command = "drissionpage-mcp"' in text

    assert "Codex CLI/IDE" in readme
    assert "Codex CLI/IDE" in readme_cn
    assert "recursive-include examples" not in manifest
    assert "Codex" in pyproject["project"]["description"]
    assert "codex" in pyproject["project"]["keywords"]


def test_public_readmes_do_not_point_to_removed_or_stale_setup_paths() -> None:
    public_files = {
        "README.md": Path("README.md").read_text(encoding="utf-8"),
        "README_CN.md": Path("README_CN.md").read_text(encoding="utf-8"),
        "playground/README.md": Path("playground/README.md").read_text(
            encoding="utf-8"
        ),
        "playground/run_mcp_lab.py": Path("playground/run_mcp_lab.py").read_text(
            encoding="utf-8"
        ),
    }

    for path, text in public_files.items():
        assert "mcp-config.json" not in text, path
        assert "examples/" not in text, path
        assert "current 75% floor" not in text, path
        assert "当前 75% 覆盖率底线" not in text, path

    assert "current 95% floor" in public_files["README.md"]
    assert "当前 95% 覆盖率底线" in public_files["README_CN.md"]
    assert 'args = ["-m", "drissionpage_mcp.cli"]' in public_files["README.md"]
    assert 'args = ["-m", "drissionpage_mcp.cli"]' in public_files["README_CN.md"]
    assert "playground/quick_start.py" not in "\n".join(public_files.values())
    assert "playground/local_test.py" not in "\n".join(public_files.values())
    assert "playground/run_mcp_lab.py --case registry" in public_files["README.md"]
    assert "playground/run_mcp_lab.py --case registry" in public_files["README_CN.md"]


def test_maintenance_files_do_not_retain_deleted_examples_or_old_versions() -> None:
    security = Path("SECURITY.md").read_text(encoding="utf-8")
    codecov = Path("codecov.yml").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_cn = Path("README_CN.md").read_text(encoding="utf-8")

    assert "0.3.2" not in security
    assert "Chrome sandboxing enabled" in security
    assert "DP_NO_SANDBOX=1" in security
    assert "examples/**" not in codecov
    assert "docs/release-checklist.md" not in readme
    assert "docs/release-checklist.md" not in readme_cn


def test_distribution_configuration_excludes_private_guidance_and_skills() -> None:
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    forbidden = (
        "AGENTS.md",
        "SKILL.md",
        "skills/",
        "docs/core-and-skills-strategy.md",
        "docs/0.7.3-to-0.8.0-capability-plan.md",
        "docs/0.9.0-field-evaluation-and-roadmap.md",
        "docs/skills.md",
        ".omx/",
    )

    assert "recursive-include docs" not in manifest
    for name in forbidden:
        assert name not in manifest
    assert pyproject["tool"]["setuptools"]["packages"] == [
        "drissionpage_mcp",
        "drissionpage_mcp.browser",
        "drissionpage_mcp.tools",
    ]
    for deleted_module in (
        Path("drissionpage_mcp/prompts.py"),
        Path("drissionpage_mcp/browser/vision.py"),
        Path("drissionpage_mcp/browser/workflows.py"),
        Path("drissionpage_mcp/tools/vision.py"),
        Path("drissionpage_mcp/tools/workflow.py"),
    ):
        assert not deleted_module.exists()
