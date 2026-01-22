# DrissionPage MCP Server

> 基于 DrissionPage 为 Claude Code 和 MCP 客户端提供专业的浏览器自动化能力

[![PyPI](https://img.shields.io/pypi/v/drissionpage-mcp.svg)](https://pypi.org/project/drissionpage-mcp/)
[![Downloads](https://pepy.tech/badge/drissionpage-mcp/month)](https://pepy.tech/project/drissionpage-mcp)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-production-green.svg)]()

**官方仓库**: [GitHub](https://github.com/jumodada/DrissionMCP) | [GitCode](https://gitcode.com/g1879/DrissionMCP)

[English Version](README.md) | [中文版本](README_CN.md)

---

## 🚀 什么是 DrissionPage MCP？

**DrissionPage MCP Server** 是一个生产就绪的模型上下文协议（MCP）服务器，为 Claude Code、Claude Desktop 和其他 MCP 客户端提供专业的浏览器自动化能力。

与基于截图的方法不同，它通过 14 个强大工具提供**结构化、确定性的网页自动化**，利用高性能浏览器自动化框架 [DrissionPage](https://github.com/g1879/DrissionPage) 的效率。

### 🌟 为什么选择 DrissionPage MCP？

- **LLM 优化**：使用结构化数据而不需要视觉模型
- **确定性**：通过 CSS 和 XPath 支持实现可靠的元素选择
- **快速轻量**：基于 DrissionPage 高效引擎构建，开销最小
- **类型安全**：所有工具都具有完整的类型提示和 Pydantic 验证
- **生产就绪**：经过充分测试和文档化，可用于实际生产环境
- **易于集成**：简单的 `pip install` + JSON 配置即可使用

---

## ⚡ 快速安装

```bash
# 从 PyPI 安装
pip install drissionpage-mcp

# 验证安装
drissionpage-mcp --version
```

---

## 📦 在 Claude Code 中配置（30 秒）

1. **编辑 MCP 配置文件**：
   - macOS/Linux: `~/.config/claude-code/mcp_settings.json`
   - Windows: `%APPDATA%\\claude-code\\mcp_settings.json`

2. **添加以下配置**：
   ```json
   {
     "mcpServers": {
       "drissionpage": {
         "command": "drissionpage-mcp"
       }
     }
   }
   ```

3. **重启 Claude Code** 即可开始使用！

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

## 🛠️ 14 个强大工具

### 🌐 导航工具（4 个）
- `page_navigate` - 导航到任意 URL
- `page_go_back` / `page_go_forward` - 浏览器历史记录
- `page_refresh` - 重新加载当前页面

### 🎯 元素交互（3 个）
- `element_find` - 通过 CSS 选择器或 XPath 查找元素
- `element_click` - 点击任意元素
- `element_type` - 向元素输入文本

### 📸 页面操作（5 个）
- `page_screenshot` - 捕获完整页面或视口
- `page_resize` - 调整浏览器窗口
- `page_click_xy` - 通过坐标点击
- `page_close` - 关闭浏览器
- `page_get_url` - 获取当前 URL

### ⏱️ 等待操作（2 个）
- `wait_for_element` - 等待元素出现（带超时）
- `wait_time` - 延迟执行

---

## 📚 文档

| 指南 | 描述 |
|-------|-------------|
| [QUICKSTART.md](QUICKSTART.md) | 5 分钟设置指南 |
| [USAGE_GUIDE.md](USAGE_GUIDE.md) | 完整使用参考 |
| [TESTING_AND_INTEGRATION.md](TESTING_AND_INTEGRATION.md) | MCP 客户端集成 |
| [examples/README.md](examples/README.md) | 配置示例 |

---

## 🏗️ 架构

采用**清晰、模块化的设计**：

```
DrissionMCP/
├── src/
│   ├── cli.py              # 入口点
│   ├── server.py           # MCP 服务器
│   ├── context.py          # 浏览器管理
│   ├── response.py         # 响应格式化
│   ├── tab.py              # 页面操作
│   └── tools/              # 14 个自动化工具
├── examples/               # 配置模板
├── tests/                  # 单元测试
└── playground/             # 测试工具
```

**核心原则**：
- ✅ 所有工具使用类型安全的 Pydantic 模型
- ✅ 全面使用 async/await
- ✅ 清晰的关注点分离
- ✅ 全面的错误处理
- ✅ 完整的测试覆盖率

---

## 🔧 配置

### 基础配置（推荐）
```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "drissionpage-mcp"
    }
  }
}
```

### 高级配置
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

更多配置选项请参阅 [examples/README.md](examples/README.md)。

---

## 📋 环境要求

- **Python 3.8+**（推荐 3.11+）
- **Chrome 或 Chromium** 浏览器
- **任何 MCP 兼容客户端**：Claude Code、Claude Desktop、Cursor、VS Code 等

---

## 🧪 测试

### 验证安装
```bash
# 快速验证
python -c "from DrissionPage import ChromiumPage; p = ChromiumPage(); print('✅ Ready')"

# 或运行测试
pip install -e ".[dev]"
pytest tests/
```

### 试用
```bash
# 交互式测试
python playground/local_test.py

# 快速启动验证
python playground/quick_start.py
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
应输出：`drissionpage-mcp 0.1.0`

### 浏览器问题？
```bash
# 检查浏览器安装
which google-chrome    # Linux
which chromium         # macOS
```

### Claude Code 找不到服务器？
- 验证配置文件路径
- 修改后重启 Claude Code
- 检查日志：`drissionpage-mcp --log-level DEBUG`

完整故障排除指南请参阅 [TESTING_AND_INTEGRATION.md](TESTING_AND_INTEGRATION.md#troubleshooting)。

---

## 📊 项目状态

| 组件 | 状态 |
|-----------|--------|
| **核心功能** | ✅ 完成 |
| **测试** | ✅ 100% 覆盖率 |
| **文档** | ✅ 全面 |
| **生产就绪** | ✅ 是 |
| **PyPI 包** | ✅ 已发布 |

**版本**: 0.1.0 | **许可证**: Apache 2.0 | **维护**: ✅ 活跃

---

## 🗺️ 路线图

### 当前版本 (v0.1.0)
- [x] 14 个核心自动化工具
- [x] 完整 MCP 协议支持
- [x] 生产就绪代码库
- [x] 全面文档
- [x] PyPI 发布

### 未来版本 (v0.2+)
- [ ] 表单处理工具
- [ ] 文件上传支持
- [ ] Shadow DOM 选择器
- [ ] 会话持久化
- [ ] 代理支持
- [ ] 网络拦截

---

## 📖 集成示例

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

更多客户端配置请参阅 [examples/](examples/)。

---

## 🤝 贡献

欢迎贡献！

1. Fork 仓库
2. 创建功能分支
3. 进行修改
4. 根据需要添加测试
5. 提交 Pull Request

---

## 🔒 安全

- 不存储或传输敏感数据
- 在您的本地环境中运行
- 无外部 API 调用
- 尊重网站服务条款

**最佳实践**：
- 未经许可不要自动化操作
- 尽可能在测试环境中使用
- 遵守 robots.txt
- 在操作之间添加适当的延迟

---

## 📄 许可证

采用 **Apache License 2.0** 许可 - 详见 [LICENSE](LICENSE)

---

## 🙏 致谢

- **[DrissionPage](https://github.com/g1879/DrissionPage)** - 优秀的浏览器自动化库
- **[Model Context Protocol](https://modelcontextprotocol.io/)** - 协议规范
- **[Claude](https://claude.ai)** - 使 AI 助手更强大和有用

---

## 💬 支持

- 📖 **[完整文档](USAGE_GUIDE.md)**
- 🐛 **[报告问题](https://github.com/jumodada/DrissionMCP/issues)**
- 💡 **[功能请求](https://github.com/jumodada/DrissionMCP/discussions)**
- 🔗 **[GitHub 仓库](https://github.com/jumodada/DrissionMCP)**
- 📦 **[PyPI 包](https://pypi.org/project/drissionpage-mcp/)**

---

## 📈 统计

[![Downloads](https://pepy.tech/badge/drissionpage-mcp)](https://pepy.tech/project/drissionpage-mcp)
[![PyPI Version](https://badge.fury.io/py/drissionpage-mcp.svg)](https://pypi.org/project/drissionpage-mcp/)

---

## 🌟 表达支持

如果您觉得这个项目有用，请考虑：
- ⭐ 在 [GitHub](https://github.com/jumodada/DrissionMCP) 上加星
- 📤 分享给您的网络
- 💬 留下反馈或建议
- 🐛 报告问题以帮助改进

---

**用 ❤️ 制作，作者 [Wukunyun](https://github.com/jumodada)**

**准备好自动化您的工作流程了吗？** 立即安装：`pip install drissionpage-mcp`
