# 多项目并发支持改造方案

> 📅 **方案版本**: v1.0  
> 📅 **创建日期**: 2025年12月30日  
> 🎯 **目标**: 支持多个 VS Code 项目同时调用 MCP 服务而互不干扰  
> 📊 **改造等级**: ⭐⭐⭐⭐ (中等复杂度重构)

---

## 📋 目录

- [1. 问题分析](#1-问题分析)
- [2. 架构设计方案](#2-架构设计方案)
- [3. 技术实现路线](#3-技术实现路线)
- [4. 详细改造步骤](#4-详细改造步骤)
- [5. 测试验证方案](#5-测试验证方案)
- [6. 风险评估与回退方案](#6-风险评估与回退方案)
- [7. 性能优化建议](#7-性能优化建议)

---

## 1. 问题分析

### 1.1 当前架构限制

#### 核心问题：单一活跃会话架构

```python
# src/mcp_feedback_enhanced/web/main.py (Line 115)
class WebUIManager:
    def __init__(self, host: str = "127.0.0.1", port: int | None = None):
        # ❌ 问题：只有一个 current_session
        self.current_session: WebFeedbackSession | None = None
        
        # ⚠️ 问题：sessions 字典存在但未充分利用
        self.sessions: dict[str, WebFeedbackSession] = {}
```

#### 端口冲突问题

```python
# 当前每个 MCP 实例尝试绑定同一端口 (默认 8765)
preferred_port = 8765  # src/mcp_feedback_enhanced/web/main.py (Line 49)

# 多项目场景：
# Project A: MCP on 127.0.0.1:8765 ✅
# Project B: MCP on 127.0.0.1:8765 ❌ 端口冲突
# Project C: MCP on 127.0.0.1:8765 ❌ 端口冲突
```

### 1.2 影响范围分析

| 模块 | 当前限制 | 改造影响 |
|------|---------|---------|
| `server.py` | MCP 工具调用创建会话时默认替换当前会话 | 需改为多会话并发管理 |
| `web/main.py` | WebUIManager 单一端口、单一会话 | 需支持多端口实例或单端口多会话 |
| `web/routes/main_routes.py` | 路由依赖 `get_current_session()` | 需改为基于 session_id 路由 |
| `web/templates/index.html` | Web UI 假设只有一个活跃会话 | 需添加多项目切换或隔离机制 |
| `session_cleanup_manager.py` | 清理策略保护单一活跃会话 | 需调整清理逻辑 |

### 1.3 用户需求澄清

#### 场景描述

```
用户开启 3 个 VS Code 窗口：
- Window 1: 项目 A (D:\Projects\ProjectA)
- Window 2: 项目 B (D:\Projects\ProjectB)
- Window 3: 项目 C (E:\Work\ProjectC)

每个窗口都配置了 mcp-feedback-enhanced-local：
{
  "mcpServers": {
    "mcp-feedback-enhanced-local": {
      "command": "uv",
      "args": ["run", "--directory", "D:\\...\\fix-MCP-Feedback-Enhanced", ...]
    }
  }
}

期望：
- AI 在 Project A 中调用 interactive_feedback → 打开专属于 A 的反馈页面
- AI 在 Project B 中调用 interactive_feedback → 打开专属于 B 的反馈页面
- 三个项目的反馈互不干扰，可以同时等待用户输入
```

---

## 2. 架构设计方案

### 2.1 方案对比

#### 方案 A：多端口 + 多进程架构 ⭐⭐⭐⭐⭐ (推荐)

```
┌─────────────────────────────────────────┐
│ VS Code Window 1 (Project A)            │
│   MCP Client → MCP Server Instance 1    │
└────────────┬────────────────────────────┘
             │ stdio
┌────────────▼────────────────────────────┐
│ MCP Server Process 1 (PID: 12345)       │
│   └─ WebUIManager(port=8765)            │
│      └─ Session A1, A2, A3...           │
└────────────┬────────────────────────────┘
             │ http://127.0.0.1:8765
┌────────────▼────────────────────────────┐
│ Browser Tab: Project A Feedback         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ VS Code Window 2 (Project B)            │
│   MCP Client → MCP Server Instance 2    │
└────────────┬────────────────────────────┘
             │ stdio
┌────────────▼────────────────────────────┐
│ MCP Server Process 2 (PID: 12346)       │
│   └─ WebUIManager(port=8766)            │  ← 自动分配不同端口
│      └─ Session B1, B2, B3...           │
└────────────┬────────────────────────────┘
             │ http://127.0.0.1:8766
┌────────────▼────────────────────────────┐
│ Browser Tab: Project B Feedback         │
└─────────────────────────────────────────┘
```

**优点**:
- ✅ **完全隔离**: 每个项目独立进程，资源隔离彻底
- ✅ **配置简单**: 无需用户配置，自动端口分配
- ✅ **兼容性好**: 不破坏现有架构
- ✅ **稳定性高**: 一个项目崩溃不影响其他项目

**缺点**:
- ⚠️ 资源占用略高（每进程约 50-100MB）
- ⚠️ 端口管理需要健壮性处理

**实现复杂度**: ⭐⭐ (低 - 已有端口管理机制)

---

#### 方案 B：单端口 + 项目隔离架构 ⭐⭐⭐

```
┌─────────────────────────────────────────┐
│ All VS Code Windows (A, B, C)           │
│   MCP Clients → Shared MCP Server       │
└────────────┬────────────────────────────┘
             │ stdio (多个连接)
┌────────────▼────────────────────────────┐
│ MCP Server Process (PID: 12345)         │
│   └─ WebUIManager(port=8765)            │
│      ├─ Project A Sessions (A1, A2...)  │
│      ├─ Project B Sessions (B1, B2...)  │
│      └─ Project C Sessions (C1, C2...)  │
└────────────┬────────────────────────────┘
             │ http://127.0.0.1:8765
┌────────────▼────────────────────────────┐
│ Browser Tabs with Project Selector      │
│   [Project A ▼] [Project B] [Project C] │
└─────────────────────────────────────────┘
```

**优点**:
- ✅ 资源占用最低（单进程）
- ✅ 统一管理方便

**缺点**:
- ❌ **进程隔离问题**: VS Code 每个窗口会启动独立 MCP 进程
- ❌ 需要复杂的进程间同步机制
- ❌ 稳定性降低（单点故障）

**实现复杂度**: ⭐⭐⭐⭐ (高 - 需要 IPC 机制)

---

#### 方案 C：混合架构（多端口 + 会话命名空间）⭐⭐⭐⭐

```
每个项目独立端口 + 同项目内多会话隔离

Project A → Port 8765 → Sessions: {A1, A2, A3}
Project B → Port 8766 → Sessions: {B1, B2, B3}
Project C → Port 8767 → Sessions: {C1, C2, C3}
```

**优点**:
- ✅ 平衡了隔离性和资源占用
- ✅ 支持同项目多会话场景

**缺点**:
- ⚠️ 实现复杂度中等

**实现复杂度**: ⭐⭐⭐ (中等)

---

### 2.2 最终推荐方案：**方案 A（多端口多进程）**

#### 核心理念

```
"每个 VS Code 窗口 → 独立 MCP 服务器进程 → 自动分配端口"
```

#### 关键设计决策

1. **进程隔离**: 利用 VS Code 的天然隔离（每个窗口独立进程）
2. **端口自动分配**: 从 8765 开始查找可用端口
3. **会话命名空间**: 使用项目路径作为会话命名前缀
4. **浏览器标识**: 在页面标题显示项目名称

---

## 3. 技术实现路线

### 3.1 改造优先级

```
Phase 1: 端口管理增强 (P0 - 必须)
├─ 强化 PortManager 的端口查找逻辑
├─ 添加端口锁文件机制（防止竞态条件）
└─ 支持环境变量 MCP_WEB_PORT_RANGE

Phase 2: 会话命名空间 (P0 - 必须)
├─ 为会话添加 project_path 标识
├─ 生成项目唯一 ID（基于路径哈希）
└─ 在 Web UI 显示项目信息

Phase 3: 浏览器标识优化 (P1 - 重要)
├─ 页面标题包含项目名称
├─ 添加项目路径显示
└─ 不同项目使用不同颜色主题（可选）

Phase 4: 并发测试 (P0 - 必须)
├─ 编写多项目并发测试用例
├─ 压力测试（5+ 项目同时运行）
└─ 端口耗尽场景测试
```

### 3.2 代码改动清单

| 文件 | 改动类型 | 优先级 | 预估工作量 |
|------|---------|--------|-----------|
| `web/main.py` | 🔧 修改 | P0 | 2h |
| `web/utils/port_manager.py` | 🔧 修改 | P0 | 1h |
| `web/models/feedback_session.py` | ➕ 新增字段 | P0 | 0.5h |
| `web/templates/index.html` | 🔧 修改 | P1 | 1h |
| `server.py` | 🔧 修改 | P0 | 1h |
| `tests/integration/test_concurrent.py` | ➕ 新增 | P0 | 2h |
| **总计** | - | - | **7.5h** |

---

## 4. 详细改造步骤

### Step 1: 增强端口管理机制

#### 4.1 添加端口锁文件（防止竞态条件）

**文件**: `src/mcp_feedback_enhanced/web/utils/port_manager.py`

**改造前**:
```python
@staticmethod
def is_port_available(host: str, port: int) -> bool:
    """检查端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False
```

**改造后**:
```python
import fcntl  # Unix
import msvcrt  # Windows
from pathlib import Path
import tempfile

PORT_LOCK_DIR = Path(tempfile.gettempdir()) / "mcp-feedback-ports"

@staticmethod
def is_port_available(host: str, port: int) -> bool:
    """检查端口是否可用（带锁文件保护）"""
    # 1. 传统 socket 检查
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            return False
    
    # 2. 检查锁文件（避免竞态条件）
    PORT_LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = PORT_LOCK_DIR / f"port_{port}.lock"
    
    try:
        if lock_file.exists():
            # 检查锁文件是否过期（进程可能已死）
            if time.time() - lock_file.stat().st_mtime > 60:
                lock_file.unlink()  # 清理僵尸锁
            else:
                return False  # 有活跃锁
        
        # 尝试创建锁文件
        with open(lock_file, 'w') as f:
            f.write(f"{os.getpid()}\n{time.time()}")
        return True
    except Exception:
        return False

@staticmethod
def release_port_lock(port: int):
    """释放端口锁（在服务器关闭时调用）"""
    lock_file = PORT_LOCK_DIR / f"port_{port}.lock"
    try:
        if lock_file.exists():
            lock_file.unlink()
    except:
        pass
```

#### 4.2 支持端口范围配置

**环境变量**:
```bash
# 允许用户配置端口范围
MCP_WEB_PORT_RANGE="8765-8774"  # 支持最多 10 个并发项目
```

**代码实现**:
```python
@staticmethod
def find_free_port_enhanced(
    preferred_port: int = 8765,
    auto_cleanup: bool = True,
    host: str = "127.0.0.1"
) -> int:
    """增强的端口查找（支持范围配置）"""
    
    # 解析环境变量端口范围
    port_range_str = os.getenv("MCP_WEB_PORT_RANGE", "")
    if port_range_str and "-" in port_range_str:
        try:
            start, end = map(int, port_range_str.split("-"))
            port_range = range(start, end + 1)
        except:
            port_range = range(preferred_port, preferred_port + 100)
    else:
        port_range = range(preferred_port, preferred_port + 100)
    
    # 从偏好端口开始尝试
    for port in port_range:
        if PortManager.is_port_available(host, port):
            debug_log(f"✅ 找到可用端口: {port}")
            return port
    
    # 所有端口都被占用，抛出异常
    raise RuntimeError(
        f"无法在范围 {port_range.start}-{port_range.stop-1} 内找到可用端口。"
        f"请检查是否有过多 MCP 实例运行。"
    )
```

---

### Step 2: 会话命名空间改造

#### 2.1 为会话添加项目标识

**文件**: `src/mcp_feedback_enhanced/web/models/feedback_session.py`

**改造**:
```python
class WebFeedbackSession:
    def __init__(
        self,
        session_id: str,
        project_directory: str,
        summary: str,
        timeout: int = 604800,
        # ➕ 新增：项目唯一标识
        project_id: str | None = None,
    ):
        self.session_id = session_id
        self.project_directory = project_directory
        self.summary = summary
        self.timeout = timeout
        
        # ➕ 生成项目唯一 ID
        if project_id is None:
            self.project_id = self._generate_project_id(project_directory)
        else:
            self.project_id = project_id
        
        # ➕ 提取项目名称（用于显示）
        self.project_name = Path(project_directory).name
    
    @staticmethod
    def _generate_project_id(project_path: str) -> str:
        """根据项目路径生成唯一 ID"""
        import hashlib
        # 规范化路径（处理 Windows/Unix 差异）
        normalized_path = Path(project_path).resolve().as_posix()
        # 生成短哈希
        hash_obj = hashlib.md5(normalized_path.encode())
        return hash_obj.hexdigest()[:8]  # 取前 8 位
```

#### 2.2 在 server.py 中传递项目标识

**文件**: `src/mcp_feedback_enhanced/server.py`

**改造**:
```python
@mcp.tool()
async def interactive_feedback(
    project_directory: Annotated[str, Field(description="專案目錄路徑")] = ".",
    summary: Annotated[str, Field(description="AI 工作完成的摘要說明")] = "我已完成了您請求的任務。",
    timeout: Annotated[int, Field(description="等待用戶回饋的超時時間（秒）")] = 604800,
) -> list[TextContent | ImageContent]:
    """收集互動式回饋"""
    
    # ➕ 生成会话 ID 时包含项目标识
    project_id = _generate_project_id(project_directory)
    session_id = f"{project_id}_{uuid.uuid4().hex[:8]}_{int(time.time())}"
    
    # 启动 Web UI 并传递项目信息
    result = await _start_web_ui(
        session_id=session_id,
        project_directory=project_directory,
        summary=summary,
        timeout=timeout,
        project_id=project_id,  # ➕ 传递项目 ID
    )
    
    return result

def _generate_project_id(project_path: str) -> str:
    """生成项目唯一标识"""
    import hashlib
    normalized_path = Path(project_path).resolve().as_posix()
    return hashlib.md5(normalized_path.encode()).hexdigest()[:8]
```

---

### Step 3: Web UI 项目标识显示

#### 3.1 在页面标题显示项目名称

**文件**: `src/mcp_feedback_enhanced/web/templates/index.html`

**改造**:
```html
<!-- 改造前 -->
<title>MCP Feedback Enhanced</title>

<!-- 改造后 -->
<title>{{ project_name }} - MCP Feedback Enhanced</title>
```

#### 3.2 在页面头部显示项目信息

**改造**:
```html
<div class="project-info-banner">
    <div class="project-icon">📁</div>
    <div class="project-details">
        <div class="project-name">{{ project_name }}</div>
        <div class="project-path" title="{{ project_directory }}">
            {{ project_directory }}
            <button class="copy-btn" onclick="copyToClipboard('{{ project_directory }}')">
                📋 复制路径
            </button>
        </div>
    </div>
    <div class="project-id">
        <span class="label">项目 ID:</span>
        <code>{{ project_id }}</code>
    </div>
</div>

<style>
.project-info-banner {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 15px 20px;
    margin-bottom: 20px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 15px;
}

.project-icon {
    font-size: 32px;
}

.project-details {
    flex: 1;
}

.project-name {
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 5px;
}

.project-path {
    font-size: 12px;
    opacity: 0.9;
    font-family: monospace;
    display: flex;
    align-items: center;
    gap: 8px;
}

.copy-btn {
    background: rgba(255,255,255,0.2);
    border: none;
    padding: 2px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
    color: white;
}

.copy-btn:hover {
    background: rgba(255,255,255,0.3);
}

.project-id {
    text-align: right;
    font-size: 12px;
}

.project-id code {
    background: rgba(255,255,255,0.2);
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: bold;
}
</style>
```

#### 3.3 WebSocket 消息包含项目信息

**文件**: `src/mcp_feedback_enhanced/web/routes/main_routes.py`

**改造**:
```python
@router.get("/")
async def index(request: Request, manager: WebUIManager = Depends(get_manager)):
    """渲染主頁面"""
    current_session = manager.get_current_session()
    
    if not current_session:
        raise HTTPException(status_code=404, detail="No active session")
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "session_id": current_session.session_id,
            "project_directory": current_session.project_directory,
            "summary": current_session.summary,
            "timeout": current_session.timeout,
            # ➕ 新增项目信息
            "project_id": current_session.project_id,
            "project_name": current_session.project_name,
        },
    )
```

---

### Step 4: 服务器关闭时清理端口锁

**文件**: `src/mcp_feedback_enhanced/web/main.py`

**改造**:
```python
class WebUIManager:
    def shutdown(self):
        """關閉 Web UI 伺服器"""
        debug_log("開始關閉 Web UI 伺服器...")
        
        try:
            # ➕ 释放端口锁
            from .utils.port_manager import PortManager
            PortManager.release_port_lock(self.port)
            debug_log(f"已释放端口 {self.port} 的锁文件")
            
            # 原有关闭逻辑...
            if self.server_process:
                self.server_process.shutdown()
            
            # 清理会话...
            if self.current_session:
                self.current_session.cleanup()
            
            debug_log("Web UI 伺服器已關閉")
        except Exception as e:
            debug_log(f"關閉 Web UI 時發生錯誤: {e}")
```

---

## 5. 测试验证方案

### 5.1 单元测试

**新增文件**: `tests/unit/test_port_manager.py`

```python
import pytest
from src.mcp_feedback_enhanced.web.utils.port_manager import PortManager

def test_port_lock_mechanism():
    """测试端口锁机制"""
    port = 8765
    
    # 第一次应该成功
    assert PortManager.is_port_available("127.0.0.1", port)
    
    # 模拟端口被占用
    # （实际测试中启动一个临时服务器）
    
    # 清理
    PortManager.release_port_lock(port)

def test_port_range_configuration():
    """测试端口范围配置"""
    import os
    os.environ["MCP_WEB_PORT_RANGE"] = "9000-9005"
    
    port = PortManager.find_free_port_enhanced(preferred_port=9000)
    assert 9000 <= port <= 9005
```

### 5.2 集成测试

**新增文件**: `tests/integration/test_concurrent_projects.py`

```python
import pytest
import asyncio
import subprocess
import time
from pathlib import Path

@pytest.mark.asyncio
async def test_three_projects_concurrent():
    """测试 3 个项目同时运行"""
    
    # 创建 3 个临时项目目录
    projects = [
        Path("/tmp/test-project-a"),
        Path("/tmp/test-project-b"),
        Path("/tmp/test-project-c"),
    ]
    
    for proj in projects:
        proj.mkdir(parents=True, exist_ok=True)
    
    processes = []
    ports = []
    
    try:
        # 启动 3 个 MCP 服务器进程
        for i, proj in enumerate(projects):
            env = {
                **os.environ,
                "MCP_WEB_PORT": str(8765 + i),  # 或使用自动分配
            }
            
            proc = subprocess.Popen(
                ["python", "-m", "mcp_feedback_enhanced"],
                cwd=proj,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(proc)
            time.sleep(2)  # 等待启动
            
            # 检查端口
            port = 8765 + i
            assert is_port_listening("127.0.0.1", port)
            ports.append(port)
        
        # 验证 3 个服务器都在运行
        assert len(ports) == 3
        
        # 验证每个服务器的独立性
        for port in ports:
            response = requests.get(f"http://127.0.0.1:{port}/")
            assert response.status_code == 200
        
    finally:
        # 清理所有进程
        for proc in processes:
            proc.terminate()
            proc.wait(timeout=5)

def is_port_listening(host: str, port: int) -> bool:
    """检查端口是否在监听"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0
```

### 5.3 手动验证清单

```bash
# 1. 打开 3 个 VS Code 窗口，分别打开不同项目

# 2. 在每个项目中配置 MCP（使用本地路径）

# 3. 在每个项目的 AI 助手中执行：
AI: "请调用 interactive_feedback 获取我的反馈"

# 4. 验证点：
✅ 每个项目打开独立的浏览器标签页
✅ 每个标签页显示正确的项目名称
✅ 端口号不同（8765, 8766, 8767...）
✅ 在项目 A 提交反馈不影响项目 B 和 C
✅ 同时关闭 2 个项目后，第 3 个项目仍正常工作
✅ 重启某个项目后，端口自动分配不冲突
```

---

## 6. 风险评估与回退方案

### 6.1 潜在风险

| 风险项 | 可能性 | 影响 | 缓解措施 |
|--------|--------|------|---------|
| 端口耗尽（10+ 项目） | 低 | 中 | 支持配置端口范围，默认 100 个端口 |
| 锁文件竞态条件 | 低 | 低 | 使用原子文件操作 + 超时清理 |
| 向后兼容性破坏 | 中 | 高 | 保留原有单会话逻辑作为 fallback |
| 性能下降 | 低 | 低 | 每个进程独立，无共享状态 |

### 6.2 回退方案

**如果改造后出现严重问题，快速回退步骤**:

```bash
# 1. 切换到改造前的 git commit
git checkout <pre-refactor-commit>

# 2. 或使用环境变量禁用新功能
export MCP_LEGACY_MODE=true  # 强制使用旧的单会话模式

# 3. 通知用户临时使用单项目模式
```

**代码中的回退开关**:

```python
# src/mcp_feedback_enhanced/web/main.py

if os.getenv("MCP_LEGACY_MODE") == "true":
    debug_log("⚠️ 使用旧版单会话模式")
    # 使用旧逻辑...
else:
    debug_log("✅ 使用新版多项目并发模式")
    # 使用新逻辑...
```

---

## 7. 性能优化建议

### 7.1 资源占用优化

#### 当前（单进程）
```
内存: ~80MB
端口: 1 个
线程: ~5 个
```

#### 改造后（3 个项目）
```
内存: 80MB × 3 = 240MB  ← 可接受
端口: 3 个
线程: 5 × 3 = 15 个
```

#### 优化策略

1. **延迟加载**: 仅在 `interactive_feedback` 调用时启动 Web 服务器
2. **空闲关闭**: 无会话超过 10 分钟自动关闭 Web 服务器
3. **资源复用**: 静态资源使用 CDN（可选）

```python
class WebUIManager:
    def __init__(self, idle_timeout: int = 600):
        self.idle_timeout = idle_timeout
        self._last_activity_time = time.time()
        self._idle_check_task = None
    
    async def _start_idle_checker(self):
        """空闲检查器：无活动时自动关闭"""
        while True:
            await asyncio.sleep(60)  # 每分钟检查一次
            
            if time.time() - self._last_activity_time > self.idle_timeout:
                if not self.current_session:  # 无活跃会话
                    debug_log("检测到空闲超时，自动关闭 Web 服务器")
                    await self.shutdown()
                    break
```

### 7.2 并发极限测试

**场景**: 10 个项目同时运行

**预期结果**:
- 端口范围: 8765-8774 (10 个)
- 总内存: 800MB (可接受)
- 启动时间: 每个 < 2 秒

**瓶颈分析**:
- ✅ CPU: 低影响（MCP 主要是 I/O 密集型）
- ✅ 内存: 每个项目独立，无共享状态，内存可预测
- ⚠️ 端口: 默认支持 100 个端口 (8765-8864)

---

## 8. 实施时间表

```
Week 1: 核心改造
├─ Day 1-2: 端口管理增强 (Step 1)
├─ Day 3-4: 会话命名空间 (Step 2)
└─ Day 5: Web UI 改造 (Step 3)

Week 2: 测试与优化
├─ Day 1-2: 单元测试 + 集成测试
├─ Day 3: 手动验证（3+ 项目并发）
├─ Day 4: 性能优化 + 文档更新
└─ Day 5: Code Review + 发布准备

Total: ~10 个工作日
```

---

## 9. 总结与建议

### 9.1 核心改造要点

1. ✅ **利用天然隔离**: VS Code 每个窗口本来就是独立进程，直接利用
2. ✅ **端口自动分配**: 健壮的端口查找 + 锁文件机制
3. ✅ **项目可视化**: 在 Web UI 清晰显示项目信息
4. ✅ **向后兼容**: 单项目场景无影响

### 9.2 用户体验改进

**改造前**:
```
用户打开 3 个项目 → 只有最后一个项目能正常使用 MCP 反馈
```

**改造后**:
```
用户打开 3 个项目 → 每个项目独立反馈页面，互不干扰
浏览器标签页标题:
  [ProjectA - MCP Feedback]
  [ProjectB - MCP Feedback]
  [ProjectC - MCP Feedback]
```

### 9.3 下一步行动

1. **Review 本方案**: 确认技术路线和优先级
2. **创建 Feature Branch**: `git checkout -b feature/multi-project-support`
3. **按步骤实施**: 从 Step 1 开始逐步改造
4. **持续测试**: 每完成一个步骤就进行测试
5. **文档更新**: 更新 README 和 MAINTENANCE.md

---

**方案文档结束** - 任何问题或调整需求请随时反馈。
