"""
SSH 反向隧道管理

用于将本地服务暴露到公网服务器，供飞书应用回调
自动在应用启动时建立，关闭时断开
"""

import asyncio
import logging
import os
import signal
import subprocess
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

TUNNEL_PID_FILE = Path("data/tunnel.pid")


def _get_key_path() -> Optional[str]:
    """获取 SSH 密钥路径（可选）"""
    key = settings.tunnel_key_path
    if key and os.path.exists(key):
        return key
    return None


def _build_ssh_command() -> Optional[list]:
    """构建 SSH 隧道命令"""
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        logger.info("飞书应用未配置，跳过隧道启动")
        return None

    host = settings.tunnel_server_host
    user = settings.tunnel_server_user
    remote_port = settings.tunnel_remote_port
    local_port = settings.tunnel_local_port

    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ConnectTimeout=10",
        "-N",  # 不执行远程命令
        "-R", f"{remote_port}:localhost:{local_port}",
        f"{user}@{host}",
    ]

    key_path = _get_key_path()
    if key_path:
        cmd.insert(2, "-i")
        cmd.insert(3, key_path)

    return cmd


def start_tunnel() -> Optional[int]:
    """
    启动 SSH 隧道（后台进程）

    Returns:
        PID 或 None（失败时）
    """
    cmd = _build_ssh_command()
    if not cmd:
        return None

    logger.info(f"🔌 启动 SSH 隧道: {settings.tunnel_server_host}:{settings.tunnel_remote_port}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        pid = proc.pid
        TUNNEL_PID_FILE.write_text(str(pid))
        logger.info(f"✅ SSH 隧道已启动 (PID: {pid})")
        return pid
    except Exception as e:
        logger.error(f"❌ 启动 SSH 隧道失败: {e}")
        return None


def stop_tunnel():
    """停止 SSH 隧道"""
    pid = None
    if TUNNEL_PID_FILE.exists():
        try:
            pid = int(TUNNEL_PID_FILE.read_text().strip())
        except (ValueError, OSError):
            pass

    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info(f"🛑 SSH 隧道已停止 (PID: {pid})")
        except ProcessLookupError:
            logger.info("SSH 隧道进程已不存在")
        except Exception as e:
            logger.warning(f"停止隧道失败: {e}")
        finally:
            TUNNEL_PID_FILE.unlink(missing_ok=True)


def is_tunnel_running() -> bool:
    """检查隧道是否运行中"""
    if not TUNNEL_PID_FILE.exists():
        return False
    try:
        pid = int(TUNNEL_PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, OSError):
        TUNNEL_PID_FILE.unlink(missing_ok=True)
        return False


async def ensure_tunnel():
    """确保隧道运行，未运行则启动"""
    if is_tunnel_running():
        logger.debug("SSH 隧道已在运行")
        return True

    pid = start_tunnel()
    if pid:
        await asyncio.sleep(2)
        if is_tunnel_running():
            return True
        logger.error("SSH 隧道启动后未检测到进程")
        return False

    return False
