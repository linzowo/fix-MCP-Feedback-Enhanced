"""
端口管理工具模組

提供增強的端口管理功能，包括：
- 智能端口查找
- 進程檢測和清理
- 端口衝突解決
- 端口鎖文件機制（防止多項目競態條件）
- 端口範圍配置支持
"""

import os
import socket
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import psutil

from ...debug import debug_log

# 端口鎖文件目錄
PORT_LOCK_DIR = Path(tempfile.gettempdir()) / "mcp-feedback-ports"


class PortManager:
    """端口管理器 - 提供增強的端口管理功能"""

    @staticmethod
    def find_process_using_port(port: int) -> dict[str, Any] | None:
        """
        查找占用指定端口的進程

        Args:
            port: 要檢查的端口號

        Returns:
            Dict[str, Any]: 進程信息字典，包含 pid, name, cmdline 等
            None: 如果沒有進程占用該端口
        """
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                    try:
                        process = psutil.Process(conn.pid)
                        return {
                            "pid": conn.pid,
                            "name": process.name(),
                            "cmdline": " ".join(process.cmdline()),
                            "create_time": process.create_time(),
                            "status": process.status(),
                        }
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # 進程可能已經結束或無權限訪問
                        continue
        except Exception as e:
            debug_log(f"查找端口 {port} 占用進程時發生錯誤: {e}")

        return None

    @staticmethod
    def kill_process_on_port(port: int, force: bool = False) -> bool:
        """
        終止占用指定端口的進程

        Args:
            port: 要清理的端口號
            force: 是否強制終止進程

        Returns:
            bool: 是否成功終止進程
        """
        process_info = PortManager.find_process_using_port(port)
        if not process_info:
            debug_log(f"端口 {port} 沒有被任何進程占用")
            return True

        try:
            pid = process_info["pid"]
            process = psutil.Process(pid)
            process_name = process_info["name"]

            debug_log(f"發現進程 {process_name} (PID: {pid}) 占用端口 {port}")

            # 檢查是否是自己的進程（避免誤殺）
            if "mcp-feedback-enhanced" in process_info["cmdline"].lower():
                debug_log("檢測到 MCP Feedback Enhanced 相關進程，嘗試優雅終止")

            if force:
                debug_log(f"強制終止進程 {process_name} (PID: {pid})")
                process.kill()
            else:
                debug_log(f"優雅終止進程 {process_name} (PID: {pid})")
                process.terminate()

            # 等待進程結束
            try:
                process.wait(timeout=5)
                debug_log(f"成功終止進程 {process_name} (PID: {pid})")
                return True
            except psutil.TimeoutExpired:
                if not force:
                    debug_log(f"優雅終止超時，強制終止進程 {process_name} (PID: {pid})")
                    process.kill()
                    process.wait(timeout=3)
                    return True
                debug_log(f"強制終止進程 {process_name} (PID: {pid}) 失敗")
                return False

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            debug_log(f"無法終止進程 (PID: {process_info['pid']}): {e}")
            return False
        except Exception as e:
            debug_log(f"終止端口 {port} 占用進程時發生錯誤: {e}")
            return False

    @staticmethod
    def is_port_available(host: str, port: int) -> bool:
        """
        檢查端口是否可用（增強版：包含鎖文件檢查）

        Args:
            host: 主機地址
            port: 端口號

        Returns:
            bool: 端口是否可用
        """
        # 確保 psutil 在函數作用域內可用
        import psutil
        
        try:
            # 1. 傳統 socket 檢查
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((host, port))
        except OSError:
            # 如果綁定失敗，再檢查是否真的有進程在監聽
            # 使用 psutil 檢查是否有進程在監聽該端口
            try:
                for conn in psutil.net_connections(kind="inet"):
                    if (
                        conn.laddr.port == port
                        and conn.laddr.ip in [host, "0.0.0.0", "::"]
                        and conn.status == psutil.CONN_LISTEN
                    ):
                        return False
                # 沒有找到監聽的進程，可能是臨時占用，認為可用
            except Exception:
                # 如果 psutil 檢查失敗，保守地認為端口不可用
                return False

        # 2. 檢查鎖文件（避免多進程競態條件）
        try:
            PORT_LOCK_DIR.mkdir(parents=True, exist_ok=True)
            lock_file = PORT_LOCK_DIR / f"port_{port}.lock"

            if lock_file.exists():
                # 檢查鎖文件是否過期（進程可能已死）
                try:
                    lock_age = time.time() - lock_file.stat().st_mtime
                    if lock_age > 60:  # 鎖文件超過 60 秒視為僵尸鎖
                        debug_log(f"清理端口 {port} 的僵尸鎖文件（年齡: {lock_age:.1f}秒）")
                        try:
                            lock_file.unlink()
                        except Exception:
                            pass  # 忽略刪除錯誤
                    else:
                        # 讀取鎖文件內容檢查進程是否存活
                        try:
                            with open(lock_file, "r") as f:
                                content = f.read().strip()
                        except Exception:
                            content = ""
                        
                        if content:
                            try:
                                lock_pid = int(content.split("\n")[0])
                                # 檢查進程是否存在
                                if not psutil.pid_exists(lock_pid):
                                    debug_log(
                                        f"清理端口 {port} 的過期鎖文件（進程 {lock_pid} 已不存在）"
                                    )
                                    try:
                                        lock_file.unlink()
                                    except Exception:
                                        pass  # 忽略刪除錯誤
                                else:
                                    debug_log(f"端口 {port} 被進程 {lock_pid} 鎖定")
                                    return False
                            except (ValueError, IndexError):
                                # 鎖文件格式錯誤，刪除
                                debug_log(f"清理端口 {port} 的損壞鎖文件")
                                try:
                                    lock_file.unlink()
                                except Exception:
                                    pass  # 忽略刪除錯誤
                except Exception as e:
                    debug_log(f"檢查端口 {port} 鎖文件時發生錯誤: {e}")
                    # 繼續嘗試創建鎖文件，而不是直接返回 False

            # 3. 嘗試創建鎖文件
            try:
                with open(lock_file, "w") as f:
                    f.write(f"{os.getpid()}\n{time.time():.0f}\n{host}")
                debug_log(f"為端口 {port} 創建鎖文件（PID: {os.getpid()}）")
                return True
            except Exception as e:
                debug_log(f"為端口 {port} 創建鎖文件失敗: {e}")
                return False

        except Exception as e:
            debug_log(f"端口 {port} 鎖文件操作失敗: {e}")
            # 鎖文件機制失敗時，回退到 socket 檢查結果
            return True

    @staticmethod
    def release_port_lock(port: int):
        """
        釋放端口鎖（在服務器關閉時調用）

        Args:
            port: 要釋放鎖的端口號
        """
        try:
            lock_file = PORT_LOCK_DIR / f"port_{port}.lock"
            if lock_file.exists():
                # 驗證是否是當前進程創建的鎖
                try:
                    with open(lock_file, "r") as f:
                        content = f.read().strip()
                except Exception:
                    content = ""
                
                if content:
                    try:
                        lock_pid = int(content.split("\n")[0])
                        if lock_pid == os.getpid():
                            # 延遲一下確保文件句柄關閉
                            time.sleep(0.1)
                            try:
                                lock_file.unlink()
                                debug_log(f"成功釋放端口 {port} 的鎖文件")
                            except PermissionError:
                                # Windows 上可能需要多次嘗試
                                for i in range(3):
                                    time.sleep(0.2)
                                    try:
                                        lock_file.unlink()
                                        debug_log(f"成功釋放端口 {port} 的鎖文件（第 {i+2} 次嘗試）")
                                        break
                                    except:
                                        if i == 2:
                                            debug_log(f"無法釋放端口 {port} 的鎖文件（文件被鎖定）")
                        else:
                            debug_log(
                                f"端口 {port} 的鎖文件屬於其他進程（PID: {lock_pid}），跳過釋放"
                            )
                    except (ValueError, IndexError):
                        # 格式錯誤，直接刪除
                        try:
                            lock_file.unlink()
                            debug_log(f"清理端口 {port} 的損壞鎖文件")
                        except Exception:
                            pass
        except Exception as e:
            debug_log(f"釋放端口 {port} 鎖文件時發生錯誤: {e}")

    @staticmethod
    def find_free_port_enhanced(
        preferred_port: int = 8765,
        auto_cleanup: bool = True,
        host: str = "127.0.0.1",
        max_attempts: int = 100,
    ) -> int:
        """
        增強的端口查找功能（支持端口範圍配置）

        Args:
            preferred_port: 偏好端口號
            auto_cleanup: 是否自動清理占用端口的進程
            host: 主機地址
            max_attempts: 最大嘗試次數

        Returns:
            int: 可用的端口號

        Raises:
            RuntimeError: 如果找不到可用端口
        """
        # 解析環境變數端口範圍
        port_range_str = os.getenv("MCP_WEB_PORT_RANGE", "")
        if port_range_str and "-" in port_range_str:
            try:
                start_port, end_port = map(int, port_range_str.split("-"))
                if start_port >= 1024 and end_port <= 65535 and start_port < end_port:
                    debug_log(
                        f"使用環境變數配置的端口範圍: {start_port}-{end_port}"
                    )
                    port_range = range(start_port, end_port + 1)
                else:
                    debug_log(
                        f"MCP_WEB_PORT_RANGE 值無效 ({port_range_str})，使用默認範圍"
                    )
                    port_range = range(preferred_port, preferred_port + max_attempts)
            except ValueError:
                debug_log(
                    f"MCP_WEB_PORT_RANGE 格式錯誤 ({port_range_str})，使用默認範圍"
                )
                port_range = range(preferred_port, preferred_port + max_attempts)
        else:
            port_range = range(preferred_port, preferred_port + max_attempts)

        # 首先嘗試偏好端口
        if PortManager.is_port_available(host, preferred_port):
            debug_log(f"✅ 偏好端口 {preferred_port} 可用")
            return preferred_port

        # 如果偏好端口被占用且啟用自動清理
        if auto_cleanup:
            debug_log(f"偏好端口 {preferred_port} 被占用，嘗試清理占用進程")
            process_info = PortManager.find_process_using_port(preferred_port)

            if process_info:
                debug_log(
                    f"端口 {preferred_port} 被進程 {process_info['name']} (PID: {process_info['pid']}) 占用"
                )

                # 詢問用戶是否清理（在實際使用中可能需要配置選項）
                if PortManager._should_cleanup_process(process_info):
                    if PortManager.kill_process_on_port(preferred_port):
                        # 等待一下讓端口釋放
                        time.sleep(1)
                        # 釋放舊的鎖文件
                        PortManager.release_port_lock(preferred_port)
                        if PortManager.is_port_available(host, preferred_port):
                            debug_log(f"✅ 成功清理端口 {preferred_port}，現在可用")
                            return preferred_port

        # 如果偏好端口仍不可用，在端口範圍內尋找
        debug_log(
            f"偏好端口 {preferred_port} 不可用，在範圍 {port_range.start}-{port_range.stop-1} 內查找"
        )

        for port in port_range:
            if port == preferred_port:
                continue  # 已經檢查過
            if PortManager.is_port_available(host, port):
                debug_log(f"✅ 找到可用端口: {port}")
                return port

        # 如果端口範圍查找失敗，拋出異常
        raise RuntimeError(
            f"無法在範圍 {port_range.start}-{port_range.stop-1} 內找到可用端口。\n"
            f"請檢查是否有過多 MCP 實例運行，或配置 MCP_WEB_PORT_RANGE 環境變數擴大範圍。\n"
            f"示例: export MCP_WEB_PORT_RANGE=\"8765-8874\"  # 支持 110 個並發項目"
        )

    @staticmethod
    def _should_cleanup_process(process_info: dict[str, Any]) -> bool:
        """
        判斷是否應該清理指定進程

        Args:
            process_info: 進程信息字典

        Returns:
            bool: 是否應該清理該進程
        """
        # 檢查是否是 MCP Feedback Enhanced 相關進程
        cmdline = process_info.get("cmdline", "").lower()
        process_name = process_info.get("name", "").lower()

        # 如果是自己的進程，允許清理
        if any(
            keyword in cmdline
            for keyword in ["mcp-feedback-enhanced", "mcp_feedback_enhanced"]
        ):
            return True

        # 如果是 Python 進程且命令行包含相關關鍵字
        if "python" in process_name and any(
            keyword in cmdline for keyword in ["uvicorn", "fastapi"]
        ):
            return True

        # 其他情況下，為了安全起見，不自動清理
        debug_log(
            f"進程 {process_info['name']} (PID: {process_info['pid']}) 不是 MCP 相關進程，跳過自動清理"
        )
        return False

    @staticmethod
    def get_port_status(port: int, host: str = "127.0.0.1") -> dict[str, Any]:
        """
        獲取端口狀態信息

        Args:
            port: 端口號
            host: 主機地址

        Returns:
            Dict[str, Any]: 端口狀態信息
        """
        status = {
            "port": port,
            "host": host,
            "available": False,
            "process": None,
            "error": None,
        }

        try:
            # 檢查端口是否可用
            status["available"] = PortManager.is_port_available(host, port)

            # 如果不可用，查找占用進程
            if not status["available"]:
                status["process"] = PortManager.find_process_using_port(port)

        except Exception as e:
            status["error"] = str(e)
            debug_log(f"獲取端口 {port} 狀態時發生錯誤: {e}")

        return status

    @staticmethod
    def list_listening_ports(
        start_port: int = 8000, end_port: int = 9000
    ) -> list[dict[str, Any]]:
        """
        列出指定範圍內正在監聽的端口

        Args:
            start_port: 起始端口
            end_port: 結束端口

        Returns:
            List[Dict[str, Any]]: 監聽端口列表
        """
        listening_ports = []

        try:
            for conn in psutil.net_connections(kind="inet"):
                if (
                    conn.status == psutil.CONN_LISTEN
                    and start_port <= conn.laddr.port <= end_port
                ):
                    try:
                        process = psutil.Process(conn.pid)
                        port_info = {
                            "port": conn.laddr.port,
                            "host": conn.laddr.ip,
                            "pid": conn.pid,
                            "process_name": process.name(),
                            "cmdline": " ".join(process.cmdline()),
                        }
                        listening_ports.append(port_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

        except Exception as e:
            debug_log(f"列出監聽端口時發生錯誤: {e}")

        return listening_ports
