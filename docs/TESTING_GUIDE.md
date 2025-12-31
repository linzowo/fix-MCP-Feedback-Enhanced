# MCP Feedback Enhanced 测试指南

## 目录

1. [测试概述](#测试概述)
2. [测试环境准备](#测试环境准备)
3. [单元测试](#单元测试)
4. [集成测试](#集成测试)
5. [手动测试场景](#手动测试场景)
6. [性能测试](#性能测试)
7. [回归测试](#回归测试)
8. [测试检查清单](#测试检查清单)
9. [常见问题排查](#常见问题排查)

---

## 测试概述

### 测试目标

- ✅ 验证多项目并发支持功能
- ✅ 确保端口管理机制稳定可靠
- ✅ 验证 Web UI 正确显示项目信息
- ✅ 确保跨平台兼容性（Windows/Linux/macOS）
- ✅ 验证错误处理和边缘情况
- ✅ 确保性能满足要求

### 测试层级

```
┌─────────────────────────────────────┐
│       端到端测试（E2E）              │  ← 完整用户流程
├─────────────────────────────────────┤
│       集成测试（Integration）        │  ← 多组件协作
├─────────────────────────────────────┤
│       单元测试（Unit）               │  ← 单个模块
└─────────────────────────────────────┘
```

---

## 测试环境准备

### 1. 基础环境

**必需软件**:
```bash
# Python 3.11+
python --version

# 虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

**安装依赖**:
```bash
# 安装开发依赖
pip install -e ".[dev]"

# 或直接安装 pytest
pip install pytest pytest-asyncio pytest-timeout
```

### 2. 环境变量配置

```bash
# Windows PowerShell
$env:MCP_WEB_PORT_RANGE = "8765-8864"
$env:DEBUG = "true"

# Linux/macOS Bash
export MCP_WEB_PORT_RANGE="8765-8864"
export DEBUG=true
```

### 3. 清理测试环境

```bash
# 清理端口锁文件
# Windows
Remove-Item -Recurse -Force "$env:TEMP\mcp-feedback-ports"

# Linux/macOS
rm -rf /tmp/mcp-feedback-ports
```

---

## 单元测试

### 测试结构

```
tests/
├── unit/                    # 单元测试
│   ├── test_port_manager.py      # 端口管理器测试
│   ├── test_feedback_session.py  # 会话模型测试
│   └── test_i18n.py              # 国际化测试
├── integration/             # 集成测试
│   └── test_multi_project.py    # 多项目集成测试
└── conftest.py             # pytest 配置
```

### 运行单元测试

#### 运行所有单元测试

```bash
# Windows
.venv\Scripts\python.exe -m pytest tests/unit/ -v

# Linux/macOS
python -m pytest tests/unit/ -v
```

**预期输出**:
```
====================================================
collected 8 items

tests/unit/test_port_manager.py::test_port_lock_creation PASSED        [ 12%]
tests/unit/test_port_manager.py::test_port_lock_prevents_reuse PASSED  [ 25%]
tests/unit/test_port_manager.py::test_zombie_lock_cleanup PASSED       [ 37%]
tests/unit/test_port_manager.py::test_port_range_configuration PASSED  [ 50%]
...
====================================================
7 passed, 1 skipped in 0.90s
====================================================
```

#### 运行特定测试文件

```bash
# 只测试端口管理器
pytest tests/unit/test_port_manager.py -v

# 只测试会话模型
pytest tests/unit/test_feedback_session.py -v
```

#### 运行特定测试用例

```bash
# 运行单个测试
pytest tests/unit/test_port_manager.py::test_port_lock_creation -v

# 运行包含关键字的测试
pytest -k "port_lock" -v
```

#### 详细输出模式

```bash
# 显示 print 输出
pytest tests/unit/ -v -s

# 显示详细日志
pytest tests/unit/ -v --log-cli-level=DEBUG
```

### 端口管理器测试详解

#### test_port_lock_creation
**测试目标**: 验证端口锁文件创建和清理机制

**测试步骤**:
1. 找到一个可用端口
2. 验证端口可用性
3. 创建端口锁文件
4. 验证锁文件包含正确的 PID
5. 释放端口锁
6. 验证锁文件被删除

**关键断言**:
```python
assert PortManager.is_port_available(port)
assert lock_file.exists()
assert str(os.getpid()) in content
assert not lock_file.exists()  # 释放后
```

#### test_port_lock_prevents_reuse
**测试目标**: 验证端口锁防止重复使用

**测试步骤**:
1. 占用端口 A
2. 尝试再次分配端口 A
3. 验证返回不同端口 B
4. 验证两个端口都不相同

**关键断言**:
```python
assert port1 != port2
assert port1 in allocated_ports
assert port2 in allocated_ports
```

#### test_zombie_lock_cleanup
**测试目标**: 验证僵尸锁文件自动清理（60秒超时）

**测试步骤**:
1. 创建模拟的旧锁文件（61秒前）
2. 调用端口可用性检查
3. 验证旧锁文件被清理
4. 验证可以分配该端口

**关键断言**:
```python
# 创建 61 秒前的锁文件
old_timestamp = time.time() - 61
assert not lock_file.exists()  # 应该被清理
```

#### test_port_range_configuration
**测试目标**: 验证通过环境变量配置端口范围

**测试步骤**:
1. 设置环境变量 `MCP_WEB_PORT_RANGE=9000-9010`
2. 分配多个端口
3. 验证所有端口在配置范围内

**关键断言**:
```python
assert 9000 <= port <= 9010
```

#### test_port_range_invalid_config
**测试目标**: 验证无效配置的错误处理

**测试步骤**:
1. 设置无效的环境变量值
2. 尝试分配端口
3. 验证回退到默认范围（8765-8864）

**测试用例**:
- `"invalid"` - 非数字格式
- `"9000"` - 缺少结束端口
- `"9010-9000"` - 范围倒置
- `"9000-9001"` - 范围过小

#### test_multiple_ports_allocation
**测试目标**: 验证同时分配多个端口

**测试步骤**:
1. 并发分配 3 个端口
2. 验证所有端口唯一
3. 验证所有端口都有锁文件
4. 释放所有端口
5. 验证锁文件被清理

**关键断言**:
```python
assert len(set(ports)) == 3  # 所有端口唯一
assert all(lock_exists(p) for p in ports)
```

#### test_release_wrong_process_lock
**测试目标**: 验证只释放当前进程的锁

**测试步骤**:
1. 创建模拟其他进程的锁文件（不同 PID）
2. 尝试释放该锁
3. 验证锁文件未被删除（保护其他进程）

**关键断言**:
```python
PortManager.release_port_lock(port)
assert lock_file.exists()  # 不应该被删除
```

#### test_find_free_port_stress
**测试目标**: 压力测试（默认跳过）

**测试步骤**:
1. 快速分配大量端口
2. 验证性能和稳定性
3. 释放所有端口

**运行方式**:
```bash
pytest tests/unit/test_port_manager.py::test_find_free_port_stress -v
```

---

## 集成测试

### 多项目并发测试

#### 准备测试项目

```bash
# 创建测试项目目录
mkdir -p test-projects/project-a
mkdir -p test-projects/project-b
mkdir -p test-projects/project-c

# 初始化简单项目
echo '{"name": "project-a"}' > test-projects/project-a/package.json
echo '{"name": "project-b"}' > test-projects/project-b/package.json
echo '{"name": "project-c"}' > test-projects/project-c/package.json
```

#### 集成测试脚本

创建 `tests/integration/test_multi_project.py`:

```python
import pytest
import asyncio
import subprocess
from pathlib import Path

@pytest.mark.asyncio
async def test_concurrent_projects():
    """测试多个项目同时启动 MCP 服务"""
    
    projects = [
        Path("test-projects/project-a"),
        Path("test-projects/project-b"),
        Path("test-projects/project-c"),
    ]
    
    processes = []
    ports = []
    
    try:
        # 启动所有项目的服务
        for project in projects:
            proc = subprocess.Popen(
                ["python", "-m", "mcp_feedback_enhanced"],
                cwd=project,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(proc)
            await asyncio.sleep(2)  # 等待服务启动
        
        # 验证每个项目获得不同端口
        # TODO: 实现端口检测逻辑
        
        # 验证 Web UI 可访问
        # TODO: 实现 HTTP 请求验证
        
    finally:
        # 清理所有进程
        for proc in processes:
            proc.terminate()
            proc.wait(timeout=5)
```

#### 运行集成测试

```bash
pytest tests/integration/ -v -s
```

---

## 手动测试场景

### 场景 1: 单项目基本功能

**目标**: 验证单个项目的基本 MCP 功能

**前置条件**:
- VS Code 已安装
- MCP 插件已配置
- 项目目录已准备

**测试步骤**:

1. **启动服务**
   ```bash
   cd your-project
   python -m mcp_feedback_enhanced
   ```
   
2. **验证启动信息**
   - [ ] 控制台显示端口号（例如: `Server started on port 8765`）
   - [ ] 显示项目名称和路径
   - [ ] 显示项目 ID（8字符 MD5）

3. **访问 Web UI**
   - 打开浏览器访问 `http://localhost:8765`
   - [ ] 页面正常加载
   - [ ] 顶部显示项目信息横幅（紫色渐变）
   - [ ] 横幅显示项目图标、名称、路径、ID
   - [ ] 复制按钮可用

4. **测试反馈功能**
   - [ ] 输入反馈内容
   - [ ] 点击提交
   - [ ] 验证反馈成功接收
   - [ ] WebSocket 连接正常

5. **关闭服务**
   - 按 `Ctrl+C` 停止服务
   - [ ] 服务正常关闭
   - [ ] 端口锁文件被删除

**预期结果**: ✅ 所有检查项通过

---

### 场景 2: 多项目并发（核心测试）

**目标**: 验证多个 VS Code 窗口同时使用 MCP 服务

**测试项目准备**:

```bash
# 准备 3 个不同的项目
D:\projects\frontend-app
D:\projects\backend-api
D:\projects\data-analysis
```

**测试步骤**:

#### Step 1: 打开多个 VS Code 窗口

1. 打开 VS Code 窗口 1，打开 `frontend-app` 项目
2. 打开 VS Code 窗口 2，打开 `backend-api` 项目
3. 打开 VS Code 窗口 3，打开 `data-analysis` 项目

#### Step 2: 配置 MCP 客户端

每个项目的 `.vscode/settings.json`:

```json
{
  "mcp.servers": {
    "feedback": {
      "command": "python",
      "args": ["-m", "mcp_feedback_enhanced"]
    }
  }
}
```

#### Step 3: 启动所有服务

1. 在窗口 1 中启动 MCP 服务
2. 在窗口 2 中启动 MCP 服务
3. 在窗口 3 中启动 MCP 服务

#### Step 4: 验证端口分配

检查每个窗口的控制台输出：

```
窗口 1: Server started on port 8765
        Project: frontend-app
        Project ID: a1b2c3d4

窗口 2: Server started on port 8766
        Project: backend-api
        Project ID: e5f6g7h8

窗口 3: Server started on port 8767
        Project: data-analysis
        Project ID: i9j0k1l2
```

**检查清单**:
- [ ] 三个项目获得不同端口（8765, 8766, 8767）
- [ ] 每个项目有唯一的 Project ID
- [ ] 所有项目显示正确的名称和路径

#### Step 5: 验证端口锁文件

检查临时目录：

```powershell
# Windows
Get-ChildItem "$env:TEMP\mcp-feedback-ports"

# 应该看到 3 个锁文件:
# port_8765.lock
# port_8766.lock
# port_8767.lock
```

**检查锁文件内容**:

```powershell
Get-Content "$env:TEMP\mcp-feedback-ports\port_8765.lock"
```

预期格式:
```
12345                    # PID
1735660800.123           # 时间戳
frontend-app             # 项目名称
```

**检查清单**:
- [ ] 存在 3 个锁文件
- [ ] 每个锁文件包含正确的 PID
- [ ] 每个锁文件包含项目名称

#### Step 6: 验证 Web UI 隔离

访问三个项目的 Web UI：

1. **项目 1**: `http://localhost:8765`
   - [ ] 横幅显示 "frontend-app"
   - [ ] 路径显示 "D:\projects\frontend-app"
   - [ ] ID 显示 "a1b2c3d4"

2. **项目 2**: `http://localhost:8766`
   - [ ] 横幅显示 "backend-api"
   - [ ] 路径显示 "D:\projects\backend-api"
   - [ ] ID 显示 "e5f6g7h8"

3. **项目 3**: `http://localhost:8767`
   - [ ] 横幅显示 "data-analysis"
   - [ ] 路径显示 "D:\projects\data-analysis"
   - [ ] ID 显示 "i9j0k1l2"

#### Step 7: 测试并发反馈提交

在每个 Web UI 中同时提交反馈：

1. 项目 1: 提交反馈 "前端需求 A"
2. 项目 2: 提交反馈 "后端优化 B"
3. 项目 3: 提交反馈 "数据分析 C"

**检查清单**:
- [ ] 所有反馈成功提交
- [ ] 反馈没有混淆到其他项目
- [ ] Session ID 包含正确的项目 ID

#### Step 8: 测试服务关闭和锁释放

1. 关闭项目 1 的服务（Ctrl+C）
   - [ ] 端口 8765 的锁文件被删除
   - [ ] 端口 8766、8767 的锁文件仍存在

2. 关闭项目 2 的服务
   - [ ] 端口 8766 的锁文件被删除
   - [ ] 端口 8767 的锁文件仍存在

3. 关闭项目 3 的服务
   - [ ] 端口 8767 的锁文件被删除
   - [ ] 临时目录为空或不存在

#### Step 9: 测试快速重启

1. 重新启动项目 1 的服务
   - [ ] 获得可用端口（可能是 8765 或其他）
   - [ ] 创建新的锁文件
   - [ ] Web UI 正常访问

**预期结果**: ✅ 所有检查项通过

---

### 场景 3: 端口耗尽处理

**目标**: 验证端口范围接近耗尽时的行为

**测试步骤**:

1. **设置小端口范围**
   ```powershell
   $env:MCP_WEB_PORT_RANGE = "9000-9003"  # 只有 4 个端口
   ```

2. **启动 4 个项目**
   - 启动项目 1 → 获得端口 9000
   - 启动项目 2 → 获得端口 9001
   - 启动项目 3 → 获得端口 9002
   - 启动项目 4 → 获得端口 9003

3. **尝试启动第 5 个项目**
   - [ ] 服务启动失败
   - [ ] 显示友好错误信息: "端口范围已耗尽"
   - [ ] 建议扩大端口范围

4. **关闭一个项目并重试**
   - 关闭项目 2（释放端口 9001）
   - 再次启动项目 5
   - [ ] 获得端口 9001
   - [ ] 服务正常启动

**预期结果**: ✅ 正确处理端口耗尽情况

---

### 场景 4: 僵尸锁清理

**目标**: 验证崩溃进程遗留的锁文件自动清理

**测试步骤**:

1. **模拟进程崩溃**
   - 启动一个 MCP 服务（端口 8765）
   - 使用任务管理器强制结束 Python 进程（不是正常关闭）
   - [ ] 锁文件仍然存在

2. **等待 60 秒**
   ```bash
   # 检查锁文件
   ls "$env:TEMP\mcp-feedback-ports\port_8765.lock"
   ```

3. **启动新服务**
   - 在任意项目中启动新的 MCP 服务
   - [ ] 系统检测到僵尸锁（超过 60 秒）
   - [ ] 自动清理僵尸锁文件
   - [ ] 成功占用端口 8765

**预期结果**: ✅ 僵尸锁自动清理

---

### 场景 5: 跨平台测试

**目标**: 验证在不同操作系统上的兼容性

#### Windows 测试

```powershell
# 设置环境变量
$env:MCP_WEB_PORT_RANGE = "8765-8864"

# 运行测试
pytest tests/unit/ -v

# 检查临时目录
Get-ChildItem "$env:TEMP\mcp-feedback-ports"
```

**检查清单**:
- [ ] 所有测试通过
- [ ] 文件锁处理正常（Windows 特有的 PermissionError）
- [ ] 路径分隔符正确处理

#### Linux 测试

```bash
# 设置环境变量
export MCP_WEB_PORT_RANGE="8765-8864"

# 运行测试
pytest tests/unit/ -v

# 检查临时目录
ls -la /tmp/mcp-feedback-ports
```

**检查清单**:
- [ ] 所有测试通过
- [ ] Unix 路径处理正确
- [ ] 进程检测正常（psutil）

#### macOS 测试

```bash
# 设置环境变量
export MCP_WEB_PORT_RANGE="8765-8864"

# 运行测试
pytest tests/unit/ -v

# 检查临时目录
ls -la /tmp/mcp-feedback-ports
```

**检查清单**:
- [ ] 所有测试通过
- [ ] macOS 权限处理正确
- [ ] 文件系统操作正常

---

## 性能测试

### 测试 1: 端口分配性能

**目标**: 验证端口分配速度

**测试脚本**:

```python
import time
from mcp_feedback_enhanced.web.utils.port_manager import PortManager

def test_port_allocation_performance():
    """测试端口分配性能"""
    
    start = time.time()
    ports = []
    
    # 分配 10 个端口
    for i in range(10):
        port = PortManager.find_free_port_enhanced()
        ports.append(port)
    
    elapsed = time.time() - start
    
    # 清理
    for port in ports:
        PortManager.release_port_lock(port)
    
    # 性能断言
    assert elapsed < 1.0  # 应该在 1 秒内完成
    print(f"分配 10 个端口耗时: {elapsed:.3f} 秒")
```

**运行**:
```bash
pytest -v -s -k "performance"
```

**预期结果**:
- ✅ 10 个端口分配 < 1 秒
- ✅ 单个端口分配 < 100ms

---

### 测试 2: 僵尸锁清理性能

**目标**: 验证清理大量僵尸锁的性能

**测试脚本**:

```python
import time
import os
from pathlib import Path
from mcp_feedback_enhanced.web.utils.port_manager import PORT_LOCK_DIR

def test_zombie_cleanup_performance():
    """测试僵尸锁清理性能"""
    
    # 创建 50 个僵尸锁文件
    old_timestamp = time.time() - 100  # 100 秒前
    
    for i in range(50):
        lock_file = PORT_LOCK_DIR / f"port_{8000 + i}.lock"
        with open(lock_file, "w") as f:
            f.write(f"99999\n{old_timestamp}\ntest-project")
    
    start = time.time()
    
    # 触发清理
    PortManager.find_free_port_enhanced()
    
    elapsed = time.time() - start
    
    # 性能断言
    assert elapsed < 2.0  # 应该在 2 秒内完成
    print(f"清理 50 个僵尸锁耗时: {elapsed:.3f} 秒")
```

**预期结果**:
- ✅ 清理 50 个僵尸锁 < 2 秒
- ✅ 内存使用稳定

---

### 测试 3: 并发压力测试

**目标**: 验证高并发场景下的稳定性

**测试脚本**:

```python
import asyncio
import concurrent.futures
from mcp_feedback_enhanced.web.utils.port_manager import PortManager

def test_concurrent_stress():
    """并发压力测试"""
    
    def allocate_port():
        port = PortManager.find_free_port_enhanced()
        return port
    
    # 使用线程池并发分配
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(allocate_port) for _ in range(20)]
        ports = [f.result() for f in futures]
    
    # 验证所有端口唯一
    assert len(set(ports)) == 20
    
    # 清理
    for port in ports:
        PortManager.release_port_lock(port)
```

**预期结果**:
- ✅ 所有端口唯一
- ✅ 无死锁或竞态条件
- ✅ 无内存泄漏

---

## 回归测试

### 回归测试检查清单

在每次代码修改后运行以下检查：

#### 1. 核心功能回归

```bash
# 运行所有单元测试
pytest tests/unit/ -v

# 运行集成测试
pytest tests/integration/ -v
```

**检查项**:
- [ ] 所有测试通过
- [ ] 无新增失败测试
- [ ] 测试覆盖率未降低

#### 2. 端口管理回归

```bash
pytest tests/unit/test_port_manager.py -v
```

**检查项**:
- [ ] 端口锁创建正常
- [ ] 僵尸锁清理正常
- [ ] 端口范围配置正常
- [ ] 多端口分配正常

#### 3. Web UI 回归

**手动检查**:
- [ ] 项目信息横幅正常显示
- [ ] 复制功能正常工作
- [ ] 响应式布局正常
- [ ] 国际化切换正常

#### 4. 性能回归

```bash
pytest -v -s -k "performance"
```

**检查项**:
- [ ] 端口分配性能未退化
- [ ] 内存使用正常
- [ ] 无明显性能下降

---

## 测试检查清单

### 发布前完整检查清单

#### 单元测试 ✅

- [ ] `test_port_lock_creation` 通过
- [ ] `test_port_lock_prevents_reuse` 通过
- [ ] `test_zombie_lock_cleanup` 通过
- [ ] `test_port_range_configuration` 通过
- [ ] `test_port_range_invalid_config` 通过
- [ ] `test_multiple_ports_allocation` 通过
- [ ] `test_release_wrong_process_lock` 通过
- [ ] 测试覆盖率 ≥ 85%

#### 集成测试 ✅

- [ ] 多项目并发启动测试通过
- [ ] 端口隔离测试通过
- [ ] Session 隔离测试通过

#### 手动测试 ✅

- [ ] 单项目基本功能正常
- [ ] 2-3 个项目并发正常
- [ ] 端口耗尽处理正常
- [ ] 僵尸锁清理正常
- [ ] Web UI 显示正确

#### 跨平台测试 ✅

- [ ] Windows 测试通过
- [ ] Linux 测试通过（如适用）
- [ ] macOS 测试通过（如适用）

#### 性能测试 ✅

- [ ] 端口分配性能达标
- [ ] 僵尸锁清理性能达标
- [ ] 并发压力测试通过
- [ ] 无内存泄漏

#### 文档检查 ✅

- [ ] README 更新
- [ ] 测试文档完整
- [ ] API 文档准确
- [ ] 示例代码有效

---

## 常见问题排查

### 问题 1: 测试失败 - PermissionError

**症状**:
```
PermissionError: [WinError 32] 另一个程序正在使用此文件
```

**原因**: Windows 文件锁定

**解决方案**:
1. 确保所有文件句柄正确关闭
2. 添加延迟和重试机制
3. 使用 `with` 语句管理文件

**验证**:
```python
# 确保文件关闭
with open(lock_file, "r") as f:
    content = f.read()
# 文件自动关闭

# 延迟后删除
time.sleep(0.1)
lock_file.unlink()
```

---

### 问题 2: 测试失败 - UnboundLocalError

**症状**:
```
UnboundLocalError: cannot access local variable 'psutil'
```

**原因**: 变量作用域问题

**解决方案**:
在函数开头导入 `psutil`

```python
def is_port_available(port: int) -> bool:
    import psutil  # ✅ 在函数开头
    # ... 其他代码
```

---

### 问题 3: 端口冲突

**症状**:
```
OSError: [Errno 48] Address already in use
```

**排查步骤**:

1. **检查端口占用**:
   ```bash
   # Windows
   netstat -ano | findstr :8765
   
   # Linux/macOS
   lsof -i :8765
   ```

2. **清理僵尸进程**:
   ```bash
   # Windows
   taskkill /F /PID <PID>
   
   # Linux/macOS
   kill -9 <PID>
   ```

3. **清理锁文件**:
   ```bash
   rm -rf /tmp/mcp-feedback-ports
   ```

---

### 问题 4: 测试超时

**症状**:
```
FAILED tests/unit/test_port_manager.py::test_zombie_lock_cleanup - Timeout
```

**解决方案**:

增加超时时间：

```python
@pytest.mark.timeout(120)  # 120 秒超时
def test_zombie_lock_cleanup():
    # ... 测试代码
```

或全局配置：

```ini
# pytest.ini
[pytest]
timeout = 120
```

---

### 问题 5: 测试环境不一致

**症状**: 本地测试通过，CI/CD 失败

**解决方案**:

1. **统一 Python 版本**:
   ```yaml
   # .github/workflows/test.yml
   python-version: '3.11'
   ```

2. **锁定依赖版本**:
   ```bash
   pip freeze > requirements-test.txt
   ```

3. **清理缓存**:
   ```bash
   pytest --cache-clear
   ```

---

## 测试最佳实践

### 1. 测试独立性

每个测试应该独立运行，不依赖其他测试：

```python
# ✅ 好的做法
def test_port_lock():
    port = find_free_port()  # 每个测试分配自己的端口
    # ... 测试逻辑
    release_port(port)  # 清理

# ❌ 不好的做法
port = 8765  # 全局变量

def test_1():
    use_port(port)  # 依赖全局状态

def test_2():
    use_port(port)  # 可能冲突
```

### 2. 清理资源

使用 fixture 确保资源清理：

```python
@pytest.fixture
def allocated_port():
    port = PortManager.find_free_port_enhanced()
    yield port
    PortManager.release_port_lock(port)  # 自动清理
```

### 3. 明确断言

使用清晰的断言消息：

```python
# ✅ 好的做法
assert port in range(8765, 8865), f"端口 {port} 不在预期范围内"

# ❌ 不好的做法
assert port > 8000  # 不够明确
```

### 4. 测试数据隔离

使用临时目录避免污染：

```python
@pytest.fixture
def temp_lock_dir(tmp_path):
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    # 使用 tmp_path 作为锁目录
    yield lock_dir
```

---

## 附录

### A. 测试快速参考

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/ -v

# 运行特定文件
pytest tests/unit/test_port_manager.py -v

# 运行特定测试
pytest -k "port_lock" -v

# 显示详细输出
pytest -v -s

# 显示覆盖率
pytest --cov=mcp_feedback_enhanced --cov-report=html

# 并行运行
pytest -n auto

# 只运行失败的测试
pytest --lf
```

### B. 环境变量参考

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `MCP_WEB_PORT_RANGE` | `8765-8864` | 端口范围配置 |
| `DEBUG` | `false` | 调试模式 |
| `PYTEST_TIMEOUT` | `60` | 测试超时（秒）|

### C. 相关文档

- [MAINTENANCE.md](../MAINTENANCE.md) - 项目维护文档
- [MULTI_PROJECT_SUPPORT.md](MULTI_PROJECT_SUPPORT.md) - 多项目支持架构
- [TESTING_REPORT.md](TESTING_REPORT.md) - 测试结果报告
- [README.md](../README.md) - 项目README

---

**文档版本**: 1.0
**最后更新**: 2025-12-31
**维护者**: MCP Feedback Enhanced Team
