# DrissionPage MCP Server ⚠️ 开发中

[English Version](README.md) | [中文版本](README_CN.md)

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

⚠️ **该项目目前正在积极开发中，尚未准备好用于生产环境。**

基于 DrissionPage 的 MCP（模型上下文协议）工具 - 一个让 Claude 和其他 MCP 客户端能够通过 DrissionPage 控制网页浏览器的自动化服务器。

## 概述

该项目提供了一个 MCP 服务器，将 DrissionPage 的网页自动化功能暴露给 Claude 等 MCP 客户端。DrissionPage 是一个 Python 库，结合了 requests 的简洁性和浏览器自动化的强大功能，非常适合网页抓取和自动化任务。

## 功能特性

### 当前功能 (v0.1.0)

- **导航工具**：导航到 URL、前进/后退、刷新页面
- **元素交互**：点击元素、输入文本、获取元素文本/属性/HTML
- **通用操作**：截图、调整浏览器窗口大小、关闭浏览器
- **等待操作**：等待元素、URL 变化或简单延时
- **MCP 集成**：完整的 MCP 服务器实现，包含适当的工具定义

### 工具分类

#### 导航工具 (`page_*`)
- `page_navigate`：导航到 URL
- `page_go_back`：返回浏览器历史
- `page_go_forward`：前进浏览器历史
- `page_refresh`：刷新当前页面
- `page_get_url`：获取当前页面 URL
- `page_close`：关闭浏览器

#### 元素交互 (`element_*`)
- `element_click`：通过选择器点击元素
- `element_input_text`：向表单字段输入文本
- `element_get_text`：从元素或页面提取文本内容
- `element_get_attribute`：获取元素属性
- `element_get_html`：从元素或页面获取 HTML 内容

#### 通用操作 (`page_*`)
- `page_screenshot`：截取页面截图
- `page_resize`：调整浏览器窗口大小
- `page_click_xy`：在特定坐标点击

#### 等待操作 (`wait_*`)
- `wait_for_element`：等待元素出现
- `wait_for_url`：等待 URL 模式匹配
- `wait_sleep`：简单的时间延迟

## 安装

### 前提条件

- Python 3.8 或更高版本
- 已安装 Chrome/Chromium 浏览器

### 从源码安装

```bash
# 克隆仓库
git clone <repository-url>
cd DrissionPageMCP

# 开发模式安装
pip install -e .

# 安装开发依赖（可选）
pip install -e ".[dev]"
```

## 使用方法

### 与 Claude Desktop 集成

1. 在 Claude 桌面应用的 MCP 配置中添加以下内容（macOS 路径：`~/Library/Application Support/Claude/claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "drissionpage": {
      "command": "python",
      "args": ["-m", "drissionpage_mcp.cli"]
    }
  }
}
```

2. 重启 Claude Desktop

3. 现在可以在对话中使用 DrissionPage 工具：

```
"请导航到 https://example.com 并截图"
"点击文本为'提交'的按钮"
"获取 class 为'result'的元素的文本内容"
"等待 id 为'loading'的元素消失"
```

### 命令行运行

直接运行 MCP 服务器：

```bash
python -m drissionpage_mcp.cli
```

### 编程使用

```python
import asyncio
from drissionpage_mcp.server import DrissionPageMCPServer

async def main():
    server = DrissionPageMCPServer()
    # 配置并运行服务器
    await server.run_server(transport)

asyncio.run(main())
```

## 开发

### 运行测试

```bash
# 安装测试依赖
pip install -e ".[dev]"

# 运行测试
python -m pytest tests/

# 运行覆盖率测试
python -m pytest tests/ --cov=drissionpage_mcp
```

### 代码质量

```bash
# 格式化代码
black src/ tests/

# 排序导入
isort src/ tests/

# 代码检查
flake8 src/ tests/

# 类型检查
mypy src/
```

## 测试和使用指南

### 基础功能测试

1. **快速功能验证**：
```bash
# 运行简单演示（不需要浏览器）
python simple_demo.py
```

2. **完整功能测试**：
```bash
# 安装依赖
pip install DrissionPage pydantic

# 运行测试套件
python -m pytest tests/ -v
```

3. **交互式测试**：
```bash
# 运行示例脚本
python example_usage.py
```

### MCP 服务器测试

1. **本地服务器启动**：
```bash
# 直接运行 MCP 服务器
python -m drissionpage_mcp.cli
```

2. **与 Claude 集成**：
   - 按照上述配置方法设置 Claude Desktop
   - 重启 Claude
   - 在对话中尝试使用网页自动化命令

### 常见使用场景

#### 1. 网页导航
```python
# 通过 Claude 或直接调用
"导航到 https://www.google.com"
"返回上一页"
"刷新页面"
```

#### 2. 元素交互
```python
# 点击元素
"点击搜索按钮"
"点击 id 为 'submit' 的按钮"

# 输入文本
"在搜索框中输入 'DrissionPage'"
"向用户名字段输入 'admin'"
```

#### 3. 信息提取
```python
# 获取页面内容
"获取页面标题"
"获取所有链接的文本"
"获取 class 为 'content' 的元素的 HTML"
```

#### 4. 等待操作
```python
# 等待页面加载
"等待加载完成指示器消失"
"等待搜索结果出现"
"延时 3 秒"
```

## 项目架构

项目采用模块化架构：

- **`server.py`**：主要的 MCP 服务器实现
- **`context.py`**：浏览器上下文和会话管理
- **`tab.py`**：单个浏览器标签/页面包装器
- **`response.py`**：工具响应格式化和内容管理
- **`tools/`**：按类别组织的各个工具实现
- **`cli.py`**：命令行接口

## 示例

查看 `example_usage.py` 获取详细的使用示例和工具演示。

## 故障排除

### 常见问题

1. **导入错误**：确保已安装所有依赖项
```bash
pip install DrissionPage pydantic
```

2. **浏览器启动失败**：确保系统安装了 Chrome 或 Chromium
```bash
# Ubuntu/Debian
sudo apt-get install chromium-browser

# macOS
brew install --cask google-chrome
```

3. **MCP 连接问题**：检查 Claude Desktop 配置文件格式是否正确

### 调试模式

启用详细日志记录：
```bash
python -m drissionpage_mcp.cli --log-level DEBUG
```

## 剩余工作

### 高优先级

1. **MCP SDK 兼容性**：更新以使用最新的 MCP Python SDK API
2. **错误处理**：改进错误处理和恢复机制
3. **浏览器管理**：更好的浏览器生命周期管理和清理
4. **配置选项**：添加浏览器设置、超时等配置选项

### 中优先级

5. **高级元素选择**：支持更复杂的选择器和元素查找策略
6. **表单处理**：专用的表单填写和提交工具
7. **文件上传**：支持文件上传操作
8. **会话管理**：更好的会话持久化和状态管理
9. **并行操作**：支持并发浏览器操作
10. **性能优化**：优化响应时间

### 低优先级

11. **身份验证**：常见身份验证模式的内置支持
12. **代理支持**：代理配置和轮换
13. **移动端模拟**：移动设备模拟功能
14. **网络拦截**：请求/响应拦截和修改
15. **高级等待条件**：更复杂的等待条件
16. **批处理操作**：支持批量/批处理操作

## 贡献

1. Fork 仓库
2. 创建功能分支
3. 进行更改
4. 为新功能添加测试
5. 确保所有测试通过
6. 提交拉取请求

## 许可证

该项目采用 Apache License 2.0 许可。详情请参阅 [LICENSE](LICENSE)。

## 致谢

- 基于 [DrissionPage](https://github.com/g1879/DrissionPage) 构建
- 受 [playwright-mcp](https://github.com/microsoft/playwright-mcp) 启发
- 使用 [Model Context Protocol](https://modelcontextprotocol.io/)

## 支持

如有问题和疑问：
1. 查看 [GitHub Issues](../../issues)
2. 查阅 `example_usage.py` 中的示例
3. 查看 DrissionPage 文档解决浏览器特定问题