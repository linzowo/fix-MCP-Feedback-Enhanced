# MCP Feedback Enhanced 项目维护文档

> 📅 **文档版本**: v1.0  
> 📅 **最后更新**: 2025年12月30日  
> 👤 **维护者**: 项目维护团队  
> 🔖 **项目版本**: v2.6.0

---

## 📑 目录

- [1. 项目概述](#1-项目概述)
- [2. 技术栈与架构](#2-技术栈与架构)
- [3. 开发环境配置](#3-开发环境配置)
- [4. 项目结构详解](#4-项目结构详解)
- [5. 核心模块维护指南](#5-核心模块维护指南)
- [6. 构建与发布流程](#6-构建与发布流程)
- [7. 测试策略](#7-测试策略)
- [8. 国际化维护](#8-国际化维护)
- [9. 常见问题排查](#9-常见问题排查)
- [10. 依赖管理](#10-依赖管理)
- [11. 性能优化建议](#11-性能优化建议)
- [12. 安全注意事项](#12-安全注意事项)
- [13. 贡献指南](#13-贡献指南)

---

## 1. 项目概述

### 1.1 项目简介

**MCP Feedback Enhanced** 是一个增强的 MCP (Model Context Protocol) 服务器，用于在 AI 辅助开发过程中实现交互式用户反馈和命令执行。

### 1.2 核心特性

- ✅ **超时设置修复**: 默认支持 24 小时超时（最长一周）
- 🖼️ **图片上传支持**: 修复序列化错误，支持多种图片格式
- 🔗 **断网重连**: 离线场景下保持会话连接
- 🌐 **Web UI + 桌面应用**: 双界面支持
- 🌍 **多语言**: 简体中文、繁体中文、英文
- 🔊 **音效通知**: 智能音效提醒系统
- 📋 **会话管理**: 历史跟踪与统计分析
- 💡 **提示词管理**: CRUD 操作与快速选择

### 1.3 本地定制版改进

- 修复超时永远 600s 的问题 → 默认 24 小时（可配置至一周）
- 修复图片上传序列化错误
- 新增断网不断连接功能（适合热点场景）

---

## 2. 技术栈与架构

### 2.1 技术栈

#### 后端
- **Python**: 3.11+（要求 >= 3.11）
- **FastMCP**: 2.0.0+ - MCP 协议实现
- **FastAPI**: 0.115.0+ - Web 框架
- **Uvicorn**: 0.30.0+ - ASGI 服务器
- **Jinja2**: 3.1.0+ - 模板引擎
- **WebSockets**: 13.0.0+ - 实时通信
- **psutil**: 7.0.0+ - 系统监控

#### 桌面应用
- **Tauri**: Rust + 系统原生 WebView
- **Python 嵌入**: 桌面应用内嵌 Python 环境

#### 前端
- **HTML5 + CSS3**: 原生 Web 技术
- **JavaScript ES6+**: 无框架依赖
- **WebSocket API**: 双向通信
- **Web Audio API**: 音效系统（v2.4.3+）

### 2.2 架构模式

```
┌─────────────────────────────────────────┐
│         AI Assistant (Claude)           │
│      (通过 MCP 调用 interactive_feedback) │
└────────────────┬────────────────────────┘
                 │ MCP Protocol
┌────────────────▼────────────────────────┐
│      MCP Server (server.py)             │
│   ├─ 环境检测 (SSH/WSL/Local)           │
│   ├─ 会话管理 (单一活跃会话)            │
│   ├─ 资源管理 (临时文件/内存监控)       │
│   └─ WebSocket 服务器                   │
└────────────────┬────────────────────────┘
                 │ WebSocket + HTTP
┌────────────────▼────────────────────────┐
│       Web UI (templates/index.html)     │
│   ├─ 实时反馈表单                        │
│   ├─ 图片上传与预览                      │
│   ├─ 提示词管理                          │
│   ├─ 会话历史与统计                      │
│   └─ 音效通知系统                        │
└─────────────────────────────────────────┘
```

### 2.3 单一活跃会话架构

采用 **替代传统多会话管理** 的设计：

- **持久化 Web UI**: 无需每次重新打开浏览器
- **会话复用**: 同一个会话 ID 可多次调用
- **自动清理**: 超时或手动终止后释放资源
- **状态同步**: WebSocket 实时传递状态变化

---

## 3. 开发环境配置

### 3.1 前置要求

```bash
# Python 版本
Python >= 3.11

# 推荐使用 uv 包管理器
pip install uv

# 或使用传统 pip + venv
python -m venv .venv
```

### 3.2 快速启动

#### 开发模式

```bash
# 1. 克隆项目
git clone <your-fork-url>
cd fix-MCP-Feedback-Enhanced

# 2. 安装依赖
uv pip install -e ".[dev]"

# 3. 运行开发服务器
python -m mcp_feedback_enhanced

# 4. 或使用 uv run
uv run python -m mcp_feedback_enhanced
```

#### Cursor/Cline 集成配置

在 `mcp_config.json` 中添加：

```json
{
  "mcpServers": {
    "mcp-feedback-enhanced-local": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "D:\\code\\mcp\\fix-MCP-Feedback-Enhanced",
        "python",
        "-m",
        "mcp_feedback_enhanced"
      ],
      "timeout": 604800,
      "env": {
        "MCP_DEBUG": "false",
        "MCP_WEB_HOST": "127.0.0.1",
        "MCP_WEB_PORT": "8765",
        "MCP_DESKTOP_MODE": "false",
        "MCP_LANGUAGE": "zh-CN"
      },
      "autoApprove": ["interactive_feedback"]
    }
  }
}
```

### 3.3 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `MCP_DEBUG` | `false` | 调试模式开关 |
| `MCP_WEB_HOST` | `127.0.0.1` | Web 服务器地址 |
| `MCP_WEB_PORT` | `8765` | Web 服务器端口 |
| `MCP_DESKTOP_MODE` | `false` | 桌面应用模式 |
| `MCP_LANGUAGE` | `zh-CN` | 界面语言（zh-CN/zh-TW/en） |

---

## 4. 项目结构详解

```
fix-MCP-Feedback-Enhanced/
├── src/mcp_feedback_enhanced/          # 核心源码
│   ├── __init__.py                     # 包初始化
│   ├── __main__.py                     # 主入口
│   ├── server.py                       # MCP 服务器核心
│   ├── i18n.py                         # 国际化系统
│   ├── debug.py                        # 调试工具
│   │
│   ├── web/                            # Web 应用模块
│   │   ├── main.py                     # FastAPI 应用
│   │   ├── routes/                     # 路由处理
│   │   │   ├── main_routes.py          # 主路由
│   │   │   └── ...
│   │   ├── models/                     # 数据模型
│   │   │   ├── feedback_result.py      # 反馈结果
│   │   │   └── feedback_session.py     # 会话模型
│   │   ├── templates/                  # Jinja2 模板
│   │   │   └── index.html              # Web UI 主页
│   │   ├── static/                     # 静态资源
│   │   ├── locales/                    # 多语言文件
│   │   │   ├── en/messages.json
│   │   │   ├── zh-CN/messages.json
│   │   │   └── zh-TW/messages.json
│   │   └── constants/                  # 常量定义
│   │       └── message_codes.py        # 消息代码
│   │
│   ├── desktop_app/                    # 桌面应用模块
│   │   └── desktop_app.py
│   │
│   └── utils/                          # 工具模块
│       ├── error_handler.py            # 错误处理框架
│       ├── memory_monitor.py           # 内存监控
│       └── resource_manager.py         # 资源管理
│
├── src-tauri/                          # Tauri 桌面应用
│   ├── src/                            # Rust 源码
│   │   ├── main.rs
│   │   └── lib.rs
│   ├── python/                         # 桌面 Python 嵌入
│   ├── tauri.conf.json                 # Tauri 配置
│   └── Cargo.toml                      # Rust 依赖
│
├── tests/                              # 测试套件
│   ├── unit/                           # 单元测试
│   ├── integration/                    # 集成测试
│   └── helpers/                        # 测试辅助
│
├── scripts/                            # 构建脚本
│   ├── build_desktop.py                # 桌面应用构建
│   ├── release.py                      # 发布脚本
│   ├── validate_workflows.py          # 工作流验证
│   └── validate_message_codes.py      # 消息代码验证
│
├── docs/                               # 文档
│   ├── architecture/                   # 架构文档
│   │   ├── README.md                   # 架构总览
│   │   ├── system-overview.md          # 系统架构
│   │   ├── component-details.md        # 组件详解
│   │   ├── interaction-flows.md        # 交互流程
│   │   ├── api-reference.md            # API 参考
│   │   └── deployment-guide.md         # 部署指南
│   ├── en/                             # 英文文档
│   ├── zh-CN/                          # 简体中文文档
│   └── zh-TW/                          # 繁体中文文档
│
├── pyproject.toml                      # Python 项目配置
├── pytest.ini                          # Pytest 配置
├── Makefile                            # Make 构建脚本
└── README.md                           # 项目说明
```

### 4.1 关键文件说明

#### `server.py`
- **职责**: MCP 协议实现、环境检测、会话管理
- **主要工具**:
  - `interactive_feedback`: 交互式反馈收集
  - `get_system_info`: 系统信息获取
- **核心逻辑**: 单一活跃会话管理、资源生命周期

#### `web/main.py`
- **职责**: FastAPI 应用、WebSocket 服务器、路由分发
- **端点**:
  - `GET /`: 主页渲染
  - `WS /ws/{session_id}`: WebSocket 连接
  - `POST /upload`: 图片上传

#### `web/templates/index.html`
- **职责**: Web UI 核心界面
- **功能模块**:
  - 反馈表单
  - 图片上传与预览
  - 提示词管理（CRUD）
  - 会话历史（v2.4.3 页签化）
  - 音效通知系统（v2.4.3）
  - 自动提交倒计时

---

## 5. 核心模块维护指南

### 5.1 会话管理（`server.py`）

#### 会话生命周期

```python
# 创建会话
session = FeedbackSession(
    session_id=session_id,
    project_directory=project_directory,
    summary=summary,
    timeout=timeout
)

# 会话状态
WAITING_USER_INPUT    # 等待用户输入
PROCESSING            # 处理中
TIMEOUT               # 超时
COMPLETED             # 完成
```

#### 维护要点

1. **超时处理**: 确保 `timeout` 参数正确传递，默认 604800 秒（7 天）
2. **会话清理**: 超时或完成后自动清理资源
3. **断线重连**: Web UI 断开后可重新连接同一会话

### 5.2 图片处理（`server.py`）

#### 当前实现

```python
# 支持的图片格式
SUPPORTED_FORMATS = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp"
}

# 修复后的序列化逻辑
def process_image(image_data):
    # Base64 编码
    # 创建临时文件
    # 返回 MCPImage 对象
```

#### 维护要点

1. **Base64 编码**: 确保正确编码避免序列化错误
2. **临时文件**: 使用 `resource_manager.py` 管理临时文件生命周期
3. **内存优化**: 大图片自动压缩或拒绝

### 5.3 WebSocket 通信（`web/main.py`）

#### 消息格式

```json
{
  "type": "update|feedback|status|error",
  "data": {
    "user_input": "...",
    "images": ["base64_data"],
    "session_id": "..."
  }
}
```

#### 维护要点

1. **心跳检测**: 定期 ping/pong 保持连接
2. **错误恢复**: 连接断开后自动重连机制
3. **消息队列**: 避免消息丢失

### 5.4 国际化系统（`i18n.py`）

#### 语言文件结构

```
web/locales/
├── en/messages.json          # 英文
├── zh-CN/messages.json       # 简体中文
├── zh-TW/messages.json       # 繁体中文
```

#### 添加新语言步骤

1. 创建 `web/locales/{lang}/messages.json`
2. 翻译所有键值对
3. 在 `i18n.py` 中注册新语言
4. 在 Web UI 添加语言切换选项

---

## 6. 构建与发布流程

### 6.1 版本号管理

```bash
# 使用 bump2version
bump2version patch   # 2.6.0 -> 2.6.1
bump2version minor   # 2.6.0 -> 2.7.0
bump2version major   # 2.6.0 -> 3.0.0
```

### 6.2 构建步骤

#### Python 包构建

```bash
# 使用 hatchling
python -m build

# 检查构建产物
twine check dist/*
```

#### 桌面应用构建

```bash
# 使用 Tauri
cd src-tauri
cargo tauri build

# 或使用脚本
python scripts/build_desktop.py
```

### 6.3 发布检查清单

- [ ] 更新 `pyproject.toml` 版本号
- [ ] 更新 `CHANGELOG.md`
- [ ] 运行完整测试套件 `pytest`
- [ ] 验证 Ruff 和 Mypy `ruff check . && mypy .`
- [ ] 构建 Python 包和桌面应用
- [ ] 测试本地安装 `pip install dist/*.whl`
- [ ] 提交 Git 标签 `git tag v2.6.0`
- [ ] 推送到 PyPI `twine upload dist/*`
- [ ] 发布 GitHub Release

---

## 7. 测试策略

### 7.1 测试结构

```
tests/
├── unit/                  # 单元测试
│   ├── test_server.py     # server.py 测试
│   ├── test_i18n.py       # 国际化测试
│   └── ...
├── integration/           # 集成测试
│   ├── test_websocket.py  # WebSocket 测试
│   └── ...
└── helpers/               # 测试辅助工具
    └── mcp_client.py      # 模拟 MCP 客户端
```

### 7.2 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/unit/test_server.py

# 带覆盖率
pytest --cov=src/mcp_feedback_enhanced

# 超时保护
pytest --timeout=30
```

### 7.3 测试维护要点

1. **模拟环境**: 使用 `pytest fixtures` 模拟 MCP 环境
2. **异步测试**: 使用 `pytest-asyncio` 测试 WebSocket
3. **断言准确性**: 验证会话状态、消息格式、错误处理

---

## 8. 国际化维护

### 8.1 消息代码系统（`message_codes.py`）

```python
class MessageCode:
    ERROR_INVALID_SESSION = "ERROR_INVALID_SESSION"
    INFO_FEEDBACK_SUBMITTED = "INFO_FEEDBACK_SUBMITTED"
    # ...
```

### 8.2 翻译文件示例

```json
{
  "ERROR_INVALID_SESSION": "无效的会话 ID",
  "INFO_FEEDBACK_SUBMITTED": "反馈已提交",
  "ui.feedback.placeholder": "请输入您的反馈..."
}
```

### 8.3 添加新消息步骤

1. 在 `message_codes.py` 定义常量
2. 在所有语言文件中添加翻译
3. 运行验证脚本: `python scripts/validate_message_codes.py`
4. 在代码中使用: `i18n.get_message("ERROR_INVALID_SESSION")`

---

## 9. 常见问题排查

### 9.1 超时问题

**症状**: 会话总是 600 秒后断开

**诊断**:
```python
# 检查 server.py 中的超时参数传递
def interactive_feedback(timeout: int = 604800):
    session = FeedbackSession(..., timeout=timeout)
```

**解决**: 确保 `timeout` 参数从 MCP 调用正确传递到会话对象

### 9.2 图片上传失败

**症状**: 上传图片时报序列化错误

**诊断**:
```python
# 检查 Base64 编码
image_data = base64.b64encode(file_content).decode('utf-8')

# 检查 MIME 类型
if mime_type not in SUPPORTED_FORMATS:
    raise ValueError(f"Unsupported format: {mime_type}")
```

**解决**: 验证 Base64 编码和 MIME 类型检测逻辑

### 9.3 WebSocket 连接断开

**症状**: Web UI 频繁断开连接

**诊断**:
```bash
# 启用调试模式
export MCP_DEBUG=true

# 查看 WebSocket 日志
tail -f logs/websocket.log
```

**解决**: 
- 检查防火墙设置
- 验证心跳机制
- 确认浏览器不阻止 WebSocket

### 9.4 桌面应用启动失败

**症状**: 桌面应用无法启动或白屏

**诊断**:
```bash
# 检查 Python 环境
which python3

# 检查 Tauri 日志
tauri dev --verbose
```

**解决**:
- 确保 Python 3.11+ 已安装
- 验证 Tauri 依赖完整性
- 检查系统 WebView 版本

---

## 10. 依赖管理

### 10.1 核心依赖

```toml
[project.dependencies]
fastmcp = ">=2.0.0"         # MCP 协议核心
psutil = ">=7.0.0"          # 系统监控
fastapi = ">=0.115.0"       # Web 框架
uvicorn = ">=0.30.0"        # ASGI 服务器
jinja2 = ">=3.1.0"          # 模板引擎
websockets = ">=13.0.0"     # WebSocket 支持
aiohttp = ">=3.8.0"         # 异步 HTTP
mcp = ">=1.9.3"             # MCP SDK
```

### 10.2 依赖更新策略

```bash
# 检查过期依赖
pip list --outdated

# 更新次要版本
pip install -U fastapi

# 测试兼容性
pytest
```

### 10.3 锁定版本

在 `pyproject.toml` 中使用 `>=` 而非 `==`，允许补丁版本更新但需：
- 每次更新后运行完整测试
- 在 `CHANGELOG.md` 记录依赖变更

---

## 11. 性能优化建议

### 11.1 内存优化

```python
# 使用 memory_monitor.py 监控
from .utils.memory_monitor import MemoryMonitor

monitor = MemoryMonitor()
monitor.start_monitoring()

# 定期清理临时文件
resource_manager.cleanup_old_files()
```

### 11.2 WebSocket 优化

- **消息批处理**: 合并频繁的小消息
- **压缩**: 启用 `permessage-deflate` 压缩
- **连接池**: 复用 WebSocket 连接

### 11.3 数据库优化（未来考虑）

当前使用内存存储，大规模部署可考虑：
- SQLite: 本地持久化
- Redis: 会话缓存
- PostgreSQL: 生产环境

---

## 12. 安全注意事项

### 12.1 输入验证

```python
# 严格验证用户输入
def validate_session_id(session_id: str):
    if not re.match(r'^[a-zA-Z0-9_-]{8,64}$', session_id):
        raise ValueError("Invalid session ID format")
```

### 12.2 文件上传安全

```python
# 限制文件大小
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# 验证 MIME 类型
if not magic.from_buffer(file_content, mime=True) in ALLOWED_TYPES:
    raise ValueError("Invalid file type")
```

### 12.3 XSS 防护

- 使用 Jinja2 自动转义
- 避免直接插入 HTML
- 验证 CSP（Content Security Policy）

### 12.4 CSRF 防护

```python
# 为表单添加 CSRF Token
from fastapi_csrf import CsrfProtect

@app.post("/upload")
async def upload(csrf_token: str = Form(...)):
    # 验证 CSRF token
```

---

## 13. 贡献指南

### 13.1 代码风格

```bash
# 使用 Ruff 格式化
ruff check --fix .

# 类型检查
mypy src/

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### 13.2 提交规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型**:
- `feat`: 新功能
- `fix`: 修复 Bug
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

**示例**:
```
feat(websocket): 添加断线重连机制

- 实现指数退避重连策略
- 添加最大重连次数限制
- 更新相关测试

Closes #123
```

### 13.3 Pull Request 流程

1. Fork 项目到个人仓库
2. 创建功能分支 `git checkout -b feature/my-feature`
3. 提交代码并推送 `git push origin feature/my-feature`
4. 在 GitHub 创建 Pull Request
5. 等待 Code Review 并根据反馈修改
6. 合并到主分支

---

## 附录

### A. 有用的命令

```bash
# 查看项目依赖树
pip-tree

# 清理临时文件
python scripts/cleanup_cache.py

# 验证工作流配置
python scripts/validate_workflows.py

# 生成 Tauri 图标
cd src-tauri && python generate_icons.py
```

### B. 相关资源

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Tauri 文档](https://tauri.app/)
- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

### C. 维护者联系方式

- **原作者**: Minidoracat
- **GitHub**: [Minidoracat/mcp-feedback-enhanced](https://github.com/Minidoracat/mcp-feedback-enhanced)
- **本地定制版**: [你的 GitHub 仓库]

---

**文档结束** - 如有问题或建议，请提交 Issue 或 Pull Request。
