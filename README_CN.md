# DrissionPage MCP Server

> 基于 [DrissionPage](https://github.com/g1879/DrissionPage) 为 Codex、Claude Code 和 MCP 客户端提供专业的浏览器自动化能力。
>
> DrissionPage 是一个以 Chromium/CDP 直接控制为核心、同时支持 requests 风格 HTTP 会话的 Python 网页自动化库。本项目将其中面向浏览器的能力封装为类型化、原子化的 MCP 工具。

[![PyPI](https://img.shields.io/pypi/v/drissionpage-mcp.svg?cacheSeconds=3600)](https://pypi.org/project/drissionpage-mcp/) [![Downloads](https://pepy.tech/badge/drissionpage-mcp/month)](https://pepy.tech/project/drissionpage-mcp) [![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) [![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![CI](https://github.com/jumodada/Drissionpage-MCP-Server/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jumodada/Drissionpage-MCP-Server/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/jumodada/Drissionpage-MCP-Server/branch/main/graph/badge.svg)](https://codecov.io/gh/jumodada/Drissionpage-MCP-Server) [![Status](https://img.shields.io/badge/status-beta-yellow.svg)]()

[![DrissionPage MCP 交互式 Browser Lab](https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/drissionpage-mcp-browser-lab.gif)](https://drissionpage-mcp.vercel.app)

**[打开交互式 Browser Lab](https://drissionpage-mcp.vercel.app)**，重放有界自然指针轨迹、拖动控件并验证可观察状态。

**官方仓库**: [GitHub](https://github.com/jumodada/Drissionpage-MCP-Server) | [GitCode](https://gitcode.com/g1879/DrissionMCP)

[English Version](README.md) | [中文版本](README_CN.md)

## 🖱️ 带自然指针轨迹的原子化浏览器控制

**DrissionPage MCP 0.8.6 提供 69 个类型化浏览器能力。** MCP 服务负责准确的底层观察与操作，客户端或可选 Skill 负责组合站点、组件库、挑战与业务流程。

> **模型决定做什么，MCP 严格执行请求的浏览器操作。**

```text
截图 / 页面观察
        ↓
多模态模型识别 viewport 坐标
        ↓
page_click_xy(x=442, y=369, profile="natural")
        ↓
24 步缓动三次曲线 → 精确终点 → 按下 → 释放
        ↓
观察并验证页面状态变化
```

### 核心交互保证

- **两种有界 profile**：`direct` 发出一次精确移动；`natural` 发出确定性的 24 步缓动三次曲线，使用可复现的 8-14ms 间隔，并精确到达终点。
- **没有隐藏随机性**：相同起点、终点和 profile 生成相同轨迹，不包含抖动、overshoot 或反检测逻辑。指针位置有状态，因此重复调用可能从上一次终点开始。
- **显式动作序列**：点击是选定的移动 profile、可选调用方延迟、按下、释放；拖拽在选定轨迹和有序路径点之间保持一次按下。
- **失败安全**：按下之后执行失败时，仍会尝试释放鼠标按钮。
- **新鲜浏览器证据**：基于 selector 的拖拽会在动作前即时解析几何位置。
- **类型化结果**：输出记录实际坐标、按键、步骤数和显式延迟。

存在可靠 selector 时优先使用结构化 DOM 目标。对于 canvas、编辑器、地图、图表等视觉界面，使用坐标、`natural` 轨迹和显式路径点。组件目标识别、挑战观察、多步点击、登录流程和其他业务策略属于客户端或可选 Skill。

```json
{
  "x": 442,
  "y": 369,
  "profile": "natural",
  "button": "left",
  "element": "视觉识别出的控件"
}
```

该能力用于获得授权的浏览器自动化、测试、无障碍工作流和技术研究；核心不提供验证挑战或站点专用工作流。

## 🧭 客户端安装导航

- [原子化浏览器控制](#-带自然指针轨迹的原子化浏览器控制)
- [安装与截图指引](#-首次成功路径)
- [Codex CLI/IDE 快速配置](#-在-codex-cliide-中配置30-秒)
- [Codex CLI/IDE 集成示例](#codex-cli--ide)
- [Skills 与可复用流程](#-skills-与可复用流程)
- [Claude Code 配置](#claude-code)
- [Cursor 配置](#cursor)
- [Claude Desktop 配置](#claude-desktop)
- [故障排除](#-故障排除)

---

## 🚀 什么是 DrissionPage MCP？

**DrissionPage MCP Server** 是一个本地模型上下文协议（MCP）服务器，为 Codex CLI/IDE、Claude Code、Claude Desktop 和其他 MCP 客户端提供 DrissionPage 浏览器自动化工具。

独立服务提供 69 个类型化工具、零个 MCP Prompt 和一个静态可选 Skills 目录资源。0.8.6 保持这套注册表稳定，强化公共结果脱敏，并将长时间 network listener 等待与无关浏览器操作隔离。全部工具默认加载，不存在能力 profile 或需要选择的 `full` 模式。模型组合这些原子能力，挑战与站点流程以可选 Skill 形式放在发行包之外。浏览器执行由 [DrissionPage](https://github.com/g1879/DrissionPage) 提供。

### 🌟 为什么选择 DrissionPage MCP？

- **结构化优先、视觉就绪**：有可靠 DOM 时使用结构化信息，需要视觉操作时接收多模态模型坐标
- **确定性**：通过 CSS/XPath 归一化实现适合 LLM 的可靠元素选择
- **自然指针轨迹**：同一组原子工具同时提供精确直达和有界、确定性的 24 步缓动轨迹
- **快速轻量**：基于 DrissionPage 高效引擎构建，开销最小
- **类型安全**：所有工具都具有完整的类型提示和 Pydantic 验证
- **开源友好**：包含兼容性说明、故障排除和 CI 检查，便于维护和贡献
- **易于集成**：简单的 `pip install` + Codex TOML 或 MCP JSON 配置即可使用

### ✅ 质量保障与真实场景验证

DrissionPage MCP 有严格的回归测试和真实浏览器场景验证：

- **严格自动化测试**：CI 会运行单元、协议、schema snapshot、响应合同、资源、发布元数据、安全策略、浏览器集成和覆盖率检查。
- **95% 覆盖率底线**：CI 强制执行当前 95% 覆盖率门槛，并上传覆盖率报告。
- **真实浏览器验证**：Chrome/Chromium 集成测试会直接调用暴露给客户端的 MCP 工具。
- **文档边界验证**：聚焦浏览器测试证明公共工具可读取跨域 OOPIF 和 DrissionPage 暴露的 closed Shadow DOM，不使用 JavaScript 穿透 fallback。
- **挑战表面验证**：本地 fixture 覆盖正常、隐藏、首屏外、延迟和 CSS 3D 跨域 widget；官方 Turnstile dummy key 覆盖 visible、invisible、pass、fail 和 forced-interactive callback，且不保留 token。
- **场景化验证**：playground MCP Lab 覆盖表单、电商页面、社交 feed、时间线、动态等待、iframe 和失败恢复等场景，不依赖公共演示网站。

---

## ⚡ 首次成功路径

```bash
# 安装或更新 Codex CLI（macOS/Linux）
curl -fsSL https://chatgpt.com/codex/install.sh | sh

# 从 PyPI 安装
python -m pip install -U "drissionpage-mcp>=0.8.6"

# 验证包和本地环境
drissionpage-mcp --version
drissionpage-mcp doctor
```

官方安装脚本也可用于更新已有的 Codex CLI。Windows 和 Codex 桌面应用请参阅[官方
Codex CLI 与应用文档](https://developers.openai.com/codex/cli/)。

然后添加下面的 Codex 或 MCP 客户端配置并重启客户端。

<p align="center">
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/01-install.png" width="700" alt="pip install drissionpage-mcp">
  <br><br>
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/03-doctor.png" width="700" alt="drissionpage-mcp doctor 全部检查通过">
</p>

---

## 📦 在 Codex CLI/IDE 中配置（30 秒）

Codex 通过 `config.toml` 支持本地 stdio MCP Server；Codex CLI 和 IDE 扩展共用同一份 MCP 配置。

1. **编辑 Codex 配置文件**：
   - 用户级：`~/.codex/config.toml`
   - 项目级：受信任项目中的 `.codex/config.toml`

2. **添加以下配置**：
   ```toml
   [mcp_servers.drissionpage]
   command = "drissionpage-mcp"
   startup_timeout_sec = 20
   tool_timeout_sec = 60
   ```

3. **重启 Codex**。TUI 中可运行 `/mcp`，终端可运行 `codex mcp list` 检查连接。

<p align="center">
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/06-codex.png" width="700" alt="Codex config.toml 配置">
</p>

Claude Code、Claude Desktop 和其他 JSON 配置 MCP 客户端见[集成示例](#-集成示例)。

---

## 🎯 快速示例

### 导航和截图
```
"访问 https://example.com 并为我截图"
```

### 搜索和提取
```
"打开维基百科，搜索 Python，获取第一段文字"
```

### 表单自动化
```
"填写 https://httpbin.org/forms/post 的表单并提交"
```

### 数据抓取
```
"从 news.ycombinator.com 获取前 10 条新闻标题"
```

---

## 🛠️ 69 个类型化浏览器工具

### 🌐 导航工具（5 个）
- `page_navigate` - 导航到任意 URL；可用 `new_tab` 在新标签页打开，也可用 `observe` 返回变化摘要
- `page_navigate_with_http_auth` - 在专用可销毁 Chromium context 中完成限定范围的 HTTP Auth 导航，且不回显凭证
- `page_go_back` - 返回浏览器历史上一页
- `page_go_forward` - 前进到浏览器历史下一页
- `page_refresh` - 重新加载当前页面

### 🗂️ 标签页工具（3 个）
- `tab_list` - 列出当前打开的浏览器标签页和稳定 MCP tab ID
- `tab_switch` - 切换到 `tab_list` 返回的标签页
- `tab_close` - 关闭单个标签页，不关闭整个浏览器

### 🎯 元素交互与提取（16 个）
- `element_find` - 通过 CSS 选择器或 XPath 查找单个元素；`h1` 等裸选择器按 CSS 处理
- `element_find_all` - 提取重复列表、卡片和表格元素，返回有界文本、属性和推荐 selector
- `element_click` - 点击任意元素，并以兼容方式支持左/右/中键和单击/双击语义
- `element_click_and_download` - 将一次 selector、坐标或键盘触发与 `DP_MCP_DOWNLOAD_ROOT` 下的一份完整性校验产物关联
- `element_type` - 向元素输入文本
- `element_upload_file` - 使用 `element_upload_file(paths=[...])` 从 `DP_MCP_UPLOAD_ROOT` 上传文件到 `input[type=file]`
- `element_click_and_upload` - 自动拦截 Chromium 文件选择器、点击触发器并注入受控文件，无需用户操作系统文件窗口
- `element_scroll_into_view` - 将元素滚动到视口内
- `element_hover` - 悬停元素以触发菜单/提示状态
- `element_select` - 按 value、text 或 index 选择下拉选项
- `element_check` - 勾选或取消 checkbox/radio
- `element_get_text` - 获取元素或整页文本
- `element_get_attribute` - 获取 HTML attribute
- `element_get_property` - 获取实时 DOM property，例如输入框当前 value
- `element_get_html` - 获取元素或整页 HTML
- `element_state_get` - 读取单个元素的 DrissionPage 实时状态和文档/viewport 几何

### 📸 页面操作（18 个）
- `page_screenshot` - 捕获完整页面或视口
- `page_screenshot_save` - 保存截图到 `DP_MCP_SCREENSHOT_ROOT`
- `page_export_artifact` - 在 `DP_MCP_ARTIFACT_ROOT` 下生成受管 PDF/MHTML，并返回 SHA-256 与 receipt 证据
- `page_snapshot` - 返回有界页面 outline，包括标题、链接、按钮、输入框、表单和 selector 推荐
- `page_accessibility_snapshot` - 返回整页或指定 scope 的有界 Chromium accessibility tree；字段值默认脱敏，仅在显式请求时返回
- `page_observe` - 返回紧凑页面指纹，包括 URL、标题、元素数量、可见文本样本、当前焦点元素和最近 console 摘要
- `page_evaluate` - 在当前页面运行有界 JavaScript，并返回 JSON-safe 结果
- `page_scroll` - 使用 `page_scroll(pixels=...)` 相对滚动，或传入 `x`/`y` 绝对位置
- `keyboard_press` - 向当前焦点元素/页面发送键盘输入，结果不回显输入内容
- `page_resize` - 调整浏览器窗口
- `page_pointer_move` - 使用 `direct` 或有界、确定性的 `natural` 轨迹移动到精确 viewport CSS 坐标
- `page_pointer_drag` - 使用选定 profile 执行失败安全的坐标拖拽，可经过最多六个可选有序路径点
- `page_pointer_drag_element` - 在动作前即时解析 source 与目标几何；支持顶层文档或一个同源 iframe 中的 CSS/XPath，以及嵌套 open Shadow DOM 中的 CSS 路径
- `page_click_xy` - 使用 `direct` 或 `natural` 移动，可选等待显式延迟，然后在精确终点按下并释放
- `page_close` - 关闭浏览器
- `page_get_url` - 获取当前 URL
- `page_dialog_observe` - 等待并读取待处理原生 alert、confirm 或 prompt，但不进行响应
- `page_dialog_respond` - 使用 `page_dialog_respond(action="accept")`（或 `"dismiss"`）处理待处理 alert、confirm 或 prompt

### 🧱 iframe / Shadow DOM（5 个）
- `frame_list` - 列出 iframe/frame，不改变全局 frame 状态
- `frame_snapshot` - 使用 `frame_snapshot(frame_selector="...")` 或 `frame_index` 读取一个 iframe 的有界 outline
- `frame_find` - 在指定 iframe 内查找元素
- `shadow_find` - 在当前受支持 DrissionPage 运行时暴露的 shadow root 内查找单个元素，包括已验证的 closed root
- `shadow_find_all` - 从 DrissionPage 暴露的 shadow root 内提取重复元素

### 🌍 浏览器环境（6 个）
- `browser_headers_set` - 替换额外请求 header，结果保留名称并脱敏 value；传空对象可清空
- `browser_user_agent_set` - 覆盖 user-agent 和可选 platform，同时返回写入值与原 user-agent
- `browser_cache_clear` - 仅清理 HTTP cache，保留 Cookie、localStorage 和 sessionStorage
- `browser_permission_get` - 查询当前文档 origin 的一个浏览器权限，不打开操作系统提示
- `browser_permission_set` - 使用 `browser_permission_set(setting="granted")`（或 `"denied"`/`"prompt"`）为精确 origin 设置权限
- `browser_permissions_reset` - 重置当前 Chromium context 的权限覆盖

### 🍪 Cookie 与 Storage（7 个）
- `browser_cookies_get` - 读取归一化 cookie，默认脱敏 value
- `browser_cookies_set` - 单次设置最多 100 个 Cookie，成功结果保留元数据并脱敏 value
- `browser_cookies_delete` - 按名称删除 Cookie，可选 URL/domain/path 精确范围
- `browser_cookies_clear` - 清空全部浏览器 Cookie
- `storage_get` - 按 key 或整体读取 localStorage/sessionStorage；value 默认脱敏，仅在 `include_values=true` 时返回
- `storage_set` - 设置一个 storage 项，结果不回显 value
- `storage_clear` - 清理一个 storage key 或整个区域

### 🧪 调试与可观察性（1 个）
- `page_console_logs` - 读取有界浏览器 console 消息，支持级别过滤、cursor 分页和数量限制

### ⏱️ 等待操作（4 个）
- `wait_for_element` - 等待元素出现（带超时）
- `wait_for_url` - 使用 `wait_for_url(url_pattern="...")` 等待当前 URL 包含指定文本
- `wait_until` - 使用 `wait_until(condition="text_contains", value="...")` 或其他已记录的 condition/value 组合
- `wait_time` - 延迟执行

### 🌐 网络控制与观察（4 个）
- `network_listen_start` - 通过 DrissionPage 启动有界 HTTP/XHR/Fetch 观察
- `network_listen_wait` - 等待有界 packet metadata，可选返回脱敏 header 或 body 摘要
- `network_listen_stop` - 停止观察，并可选清理排队 packet
- `network_blocked_urls_set` - 使用 `network_blocked_urls_set(urls=[...])` 替换 URL 屏蔽 pattern；传空列表可清空

### 🧩 可选 Skills 发现
- Resource：`drissionpage://skills/catalog`
- Prompts：无
- 仓库示例：`cross-origin-iframe-probe`、`turnstile-testing`、`xiaohongshu-content-research`
- 入口：`skills/<skill-name>/SKILL.md`；catalog schema v2 包含 Skill/MCP 版本、必需工具、fixture、固定 `v0.8.4` 来源 revision、验证状态和 SHA-256
- Skills 是提供给 MCP host 的 Markdown 流程，不是 Python 模块，不由服务器执行，并且不会进入 wheel/sdist。

源码目录可运行 `python playground/validate_skills.py --json` 进行校验。
从
[`skills-manager@v0.8.4`](https://github.com/jumodada/skills-manager/tree/v0.8.4)
安装固定版本：Codex 使用 `python install.py install --client codex --json`，
Claude Code 使用 `python install.py install --client claude --json`。

### 📖 Skills 与可复用流程

MCP 核心提供原子浏览器操作，Skills 在服务之外提供可审阅、可复用的流程：

| 示例 Skill | 展示内容 | 停止边界 |
| --- | --- | --- |
| [`cross-origin-iframe-probe`](skills/cross-origin-iframe-probe/SKILL.md) | frame 发现、跨源判断、坐标回退和外部验证 | 不能读取跨源 iframe 内部 DOM |
| [`turnstile-testing`](skills/turnstile-testing/SKILL.md) | Cloudflare 测试 fixture、授权生产挑战交互、坐标几何和父页面校验 | 按支持矩阵运行并验证最终页面状态 |
| [`xiaohongshu-content-research`](skills/xiaohongshu-content-research/SKILL.md) | 有界只读笔记研究和确定性的 `social-notes` fixture | 遇到 robots、登录、验证码、安全页或限流立即停止 |

完整规范见 [Skills 指南](docs/skills.md)。Skill 必须复用已有 typed
tools，采集新证据，验证后置条件，脱敏秘密并声明不支持场景；不能新增 MCP
工具或覆盖服务器的导航与安全策略。

---

## 📚 文档

| 指南 | 描述 |
|-------|-------------|
| [README_CN.md](README_CN.md) | 安装、工具和架构说明 |
| [docs/compatibility.md](docs/compatibility.md) | Python、DrissionPage、MCP 和浏览器兼容性 |
| [docs/tool-contract.md](docs/tool-contract.md) | MCP 工具名称、输入、注解和响应格式 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | doctor 命令、浏览器启动和客户端配置排查 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更 |

---

## 🏗️ 架构

采用**清晰、模块化的设计**：

```
DrissionMCP/
├── drissionpage_mcp/
│   ├── cli.py              # 进程入口
│   ├── server.py           # MCP 传输和请求路由
│   ├── context.py          # 浏览器和标签页生命周期门面
│   ├── runtime.py          # Operation key、receipt、artifact 和 capability 状态
│   ├── tool_outputs.py     # 类型化公共结果合同
│   ├── browser/            # 聚焦的 DrissionPage 能力和页面脚本
│   └── tools/              # 69 个类型化 MCP 工具定义和薄适配层
├── tests/                  # 单元测试
└── playground/             # MCP Lab 业务场景测试场
```

**核心原则**：
- ✅ 所有工具使用类型安全的 Pydantic 模型
- ✅ 全面使用 async/await
- ✅ 清晰的关注点分离
- ✅ 全面的错误处理
- ✅ 核心工具注册和响应行为具有单元/协议测试覆盖

---

## 🔧 配置

### Codex CLI / IDE（推荐）
```toml
[mcp_servers.drissionpage]
command = "drissionpage-mcp"
startup_timeout_sec = 20
tool_timeout_sec = 60

# 可选浏览器/运行时环境变量：
# [mcp_servers.drissionpage.env]
# CHROME_PATH = "/custom/path/to/chrome"
# DP_HEADLESS = "1"
```

也可以用 Codex CLI 添加：

```bash
codex mcp add drissionpage -- drissionpage-mcp
```

如果 Codex/Cursor/Claude Desktop 从 GUI 启动后找不到 shell `PATH` 或
虚拟环境中的 `drissionpage-mcp`，请改用绝对 Python 路径：

```toml
[mcp_servers.drissionpage]
command = "/absolute/path/to/python"
args = ["-m", "drissionpage_mcp.cli"]
startup_timeout_sec = 20
tool_timeout_sec = 60
```

### JSON MCP 客户端
```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp"
    }
  }
}
```

GUI 客户端的绝对 Python fallback：

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

### JSON 高级配置
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

---

## 📋 环境要求

- **Python 3.10+**（推荐 3.11+）
- **Chrome 或 Chromium** 浏览器
- **任何 MCP 兼容客户端**：Codex CLI/IDE、Claude Code、Claude Desktop、Cursor、VS Code 等

---

## 🧪 测试

### 验证安装
```bash
# 环境诊断；加 --launch-browser 可测试浏览器启动
drissionpage-mcp doctor
drissionpage-mcp doctor --launch-browser

# 源码检出测试
python -m pip install -e ".[dev]"
python -m pytest tests/

# 覆盖率报告（CI 会执行当前 95% 覆盖率底线并上传 coverage.xml）
python -m pytest tests/ --cov=drissionpage_mcp --cov-report=term-missing --cov-report=xml

# 真实浏览器 MCP Lab 场景检查
DP_HEADLESS=1 python playground/run_mcp_lab.py --all --json
```

GitHub Actions 已配置 lint、单元、协议、打包、浏览器集成和覆盖率检查；
Codecov 通过 `codecov.yml` 和 CI workflow 上传覆盖率。

### 试用
```bash
# 无浏览器 MCP 工具注册检查
python playground/run_mcp_lab.py --case registry

# 本地确定性测试站点检查
python playground/run_mcp_lab.py --case site

# 真实浏览器表单检查场景
DP_HEADLESS=1 python playground/run_mcp_lab.py --case form-inspect
```

---

## 🚀 使用场景

✅ **自动化测试** - 测试 Web 应用程序
✅ **数据抓取** - 从网站提取结构化数据
✅ **表单自动化** - 填写和提交表单
✅ **监控** - 检查更新或变化
✅ **截图验证** - 捕获和验证页面状态
✅ **内容分析** - 以编程方式分析网页内容

---

## 🐛 故障排除

### 工具未加载？
```bash
drissionpage-mcp --version
```
应输出已安装的包版本，例如：`drissionpage-mcp 0.8.6`。

`drissionpage-mcp doctor` 还必须将 `mcp_supported` 和
`mcp_server_wiring` 都报告为 `ok`；只看到版本号并不能证明 MCP 客户端能够完成初始化。

### 浏览器问题？
```bash
# 检查浏览器安装
which google-chrome    # Linux
which chromium         # macOS
```

### Codex / MCP 客户端找不到服务器？
- Codex：运行 `codex mcp list`，TUI 中运行 `/mcp`
- JSON 客户端：验证配置文件路径和 JSON 语法
- 修改后重启 Codex 或 MCP 客户端
- 检查日志：`drissionpage-mcp --log-level DEBUG`

完整故障排除指南请参阅 [docs/troubleshooting.md](docs/troubleshooting.md)。

---

## 📊 项目状态

| 组件 | 状态 |
|-----------|--------|
| **核心功能** | ✅ 完成 |
| **测试** | ✅ 严格单元/协议/schema 检查 + 真实浏览器场景验证 |
| **文档** | ✅ 安装、兼容性、故障排除和公共工具合同 |
| **包** | ✅ PyPI 元数据和构建检查 |
| **状态** | 🟡 Beta；真实浏览器行为取决于本地 Chrome/Chromium 和目标站点 |

**版本**: 0.8.6 | **许可证**: Apache 2.0 | **维护**: ✅ 活跃

---

## 🗺️ 路线图

### 当前版本 (v0.8.6)
- [x] 69 个默认加载的原子导航、标签页/frame/shadow、accessibility、观察、交互、浏览器环境、网络、Cookie/storage、等待与 console 工具
- [x] stdio MCP 服务器集成
- [x] 本地环境 doctor 诊断
- [x] 稳定 JSON 镜像、`structuredContent` 和逐工具 typed MCP `outputSchema`
- [x] 常见失败会在 `error.details.hints` 中返回结构化恢复建议
- [x] 浏览器异常公开信息脱敏，提供 `DIALOG_PENDING`/`DIALOG_NOT_FOUND` 恢复路径，并为 JavaScript 非有限数提供严格 JSON 结果
- [x] `page_snapshot` 会平衡输出预算，链接密集页面仍能暴露按钮、输入框和表单
- [x] 输入、选择、勾选、点击、键盘、上传、等待和状态读取原语覆盖原生控件与框架驱动组件，不包含组件库专用分支
- [x] 标签页管理：`tab_list`、`tab_switch`、`tab_close` 和 `page_navigate(new_tab=true)`
- [x] 可观察动作：`page_observe`、`page_evaluate`、`wait_until`，以及导航、点击、输入中的可选 `observe=true` 变化摘要
- [x] Console 可观察性：`page_console_logs`、`page_observe` 中的 console 摘要，以及 `observe=true` 中的 console 变化字段
- [x] 表单、组件库、验证挑战和便利工作流留在 MCP 核心之外
- [x] 跨源 iframe、授权 Turnstile fixture、有界小红书类研究三个仓库示例 Skill 通过静态 catalog 发现，且不进入 wheel/sdist
- [x] 能力探测后的 `page_dialog_respond`、兼容扩展的双击/右键语义，以及返回安全 `ArtifactRef` 的 selector/坐标/键盘下载关联
- [x] Web Storage 敏感 value 需显式设置 `include_values=true`；键盘和键盘下载结果只返回脱敏元数据
- [x] 下载触发按 tab 加锁，共享 deadline，保证 cleanup/replay，并在超时后使用 250ms 失败闭合的延迟 mission 保护
- [x] 可复现的 W01-W08 公共工具 benchmark，每个工作负载运行十轮，保存机器可读证据且重复副作用为零
- [x] Network listener beta：`network_listen_start`、`network_listen_wait`、`network_listen_stop`，用于 HTTP/XHR/Fetch 观察
- [x] 公共结果对 URL、凭证、header、Cookie、network body、错误、receipt 和文本镜像统一脱敏；listener 等待与无关浏览器操作隔离
- [x] 纯浏览器请求环境控制：header、user-agent 和 URL 屏蔽写操作结果脱敏，cache-only 清理保留 Cookie 与 Web Storage
- [x] `page_pointer_move`、`page_pointer_drag` 与 `page_click_xy` 提供 `direct` 和有界、确定性的 `natural` profile，终点精确且失败安全释放
- [x] 有界的可选 `page_pointer_drag.waypoints`，在一次按住手势中完成画布路径、地图操作、框选或可视化编辑器连线
- [x] 文件上传、滚动、hover、select/check、键盘、iframe、shadow DOM、cookie 和 storage 工具，面向 DrissionPage 4.x
- [x] 纯浏览器 Cookie set/get/delete/clear 流程，包括成功结果保留元数据并脱敏 value 的有界批量写入
- [x] 在受支持浏览器矩阵中通过原生 DrissionPage 输入完成受控输入与验证输入的十轮替换回归
- [x] `frame_*` 读取跨源 OOPIF、DrissionPage 支持的 `shadow_*` 查找 closed Shadow DOM，并单独记录更窄的指针目标边界
- [x] 为生产挑战流程提供 frame 边界/文档访问分类，以及外层呈现、顶层 viewport 坐标、滚动回执和坐标可操作性证据
- [x] 提供本地挑战表面和显式外网 opt-in 的官方 Turnstile 测试 key benchmark，验证父页面后置条件、截图和 token 脱敏证据
- [x] element 读取、动作、等待、上传和点击下载均兼容字符串与结构化 selector/accessibility target，先依次进入 frame，再依次进入 Shadow DOM host
- [x] 提供有界 accessibility snapshot、只观察不处理的原生 dialog 工具，以及元素实时状态/几何，支持自主定位-操作-验证闭环
- [x] 浏览器权限查询/设置/重置、受管 PDF/MHTML、自动文件选择器，以及由可销毁 Chromium context 隔离且不回显凭证的 HTTP Auth
- [x] 默认保持 Chrome sandbox 开启；`DP_NO_SANDBOX=1` 仅用于受限容器/root 环境
- [x] 不保留动作历史，不生成代码片段，公开截图结果不暴露绝对路径
- [x] 针对导航和截图路径的可选本地安全策略
- [x] 一个包含仓库示例元数据的可选 Skills resource、零个 prompts，以及 Skills、eval、兼容性和故障排除文档
- [x] PyPI 发布
- [x] 官方 MCP Registry 包元数据和由版本标签触发的发布工作流

---

## 📖 集成示例

### Codex CLI / IDE
```toml
[mcp_servers.drissionpage]
command = "drissionpage-mcp"
startup_timeout_sec = 20
tool_timeout_sec = 60
```

验证：

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

配置文件：`~/.config/claude-code/mcp_settings.json`（macOS/Linux）或
`%APPDATA%\claude-code\mcp_settings.json`（Windows）。

<p align="center">
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/04-claude-code.png" width="700" alt="Claude Code mcp_settings.json 配置">
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

配置文件：`~/.cursor/mcp.json`（全局）或 `.cursor/mcp.json`（项目）。也可以从
**Cursor Settings → Tools & MCPs → New MCP Server** 添加。

<p align="center">
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/05-cursor.png" width="700" alt="Cursor mcp.json 配置">
  <br><br>
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/08-cursor-ui.png" width="540" alt="Cursor 设置 — 添加新的 MCP 服务器">
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

连接成功后，工具会自动加载：

<p align="center">
  <img src="https://raw.githubusercontent.com/jumodada/Drissionpage-MCP-Server/assets/07-connected.png" width="700" alt="MCP 客户端已加载 DrissionPage 工具">
</p>

---

## 🤝 贡献

欢迎贡献！

1. Fork 仓库
2. 创建功能分支
3. 进行聚焦修改
4. 运行相关检查
5. 提交 Pull Request

开发设置、验证和兼容性要求请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 🔒 安全

- 在您的本地环境中运行
- 使用本地浏览器，可能访问已登录会话、Cookie、下载内容和页面内容
- 可以打开并操作本机可访问的网站
- 不需要外部 API 凭据

**最佳实践**：
- 对敏感工作流使用专用浏览器配置文件
- 在认证站点或生产系统上执行操作前，先检查 MCP 客户端提示
- 遵守网站服务条款、robots.txt 和速率限制
- 安全报告和使用建议见 [SECURITY.md](SECURITY.md)

---

## 📄 许可证

采用 **Apache License 2.0** 许可 - 详见 [LICENSE](LICENSE)

---

## 📈 统计

[![Downloads](https://pepy.tech/badge/drissionpage-mcp)](https://pepy.tech/project/drissionpage-mcp)
[![PyPI Version](https://img.shields.io/pypi/v/drissionpage-mcp.svg?cacheSeconds=3600)](https://pypi.org/project/drissionpage-mcp/)

---

## 🌟 表达支持

如果您觉得这个项目有用，请考虑：
- ⭐ 在 [GitHub](https://github.com/jumodada/Drissionpage-MCP-Server) 上加星
- 📤 分享给您的网络
- 💬 留下反馈或建议
- 🐛 报告问题以帮助改进

---

**用 ❤️ 制作，作者 [Wukunyun](https://github.com/jumodada)**

**准备好自动化您的工作流程了吗？** 立即安装：`python -m pip install -U drissionpage-mcp`

---

## 🆕 最新版本：v0.8.6

发布日期：2026-08-30。本版本保持现有 69 个浏览器工具合同，同时强化隐私与 listener 并发：

- 为公共 URL、凭证、header、Cookie 写入、network body、错误、receipt 和文本镜像建立统一脱敏边界。
- header 与 Cookie 写入结果只保留安全元数据，避免配置值进入 MCP 响应。
- `network_listen_wait` 不再占用全局 action lock，并按 tab 串行化 listener 生命周期，同时保留既有 cleanup 与 replay 合同。
- 公共面仍为 69 tools、0 prompts、1 Skills catalog resource；外部 Skills catalog 继续固定在 `skills-manager` `v0.8.4`。
