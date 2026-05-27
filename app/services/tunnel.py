"""
SSH 反向隧道管理

用于将本地服务暴露到公网服务器，供飞书应用回调
自动在应用启动时建立，关闭时断开

策略：使用独立端口建立隧道，通过 nginx 按路径分流。
nginx 将 /api/feishu/app/* 的请求转发到隧道端口，其余请求转发到生产服务端口。
"""

import asyncio
import logging
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

TUNNEL_PID_FILE = Path("data/tunnel.pid")
TUNNEL_LOG_FILE = Path("data/tunnel.log")

# 固定端口配置（勿修改）
# 远程端口 9997：公网服务器 nginx 转发飞书回调到此端口
# 本地端口 8000：隧道映射到本地开发服务器
TUNNEL_REMOTE_PORT = "9997"
TUNNEL_LOCAL_PORT = "8000"


def _get_key_path() -> Optional[str]:
    key = settings.tunnel_key_path
    if key and os.path.exists(key):
        return key
    return None


def _build_ssh_command() -> Optional[list]:
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        logger.info("飞书应用未配置，跳过隧道启动")
        return None

    host = settings.tunnel_server_host
    user = settings.tunnel_server_user
    remote_port = TUNNEL_REMOTE_PORT
    local_port = TUNNEL_LOCAL_PORT

    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ConnectTimeout=10",
        "-N",
        "-R", f"{remote_port}:localhost:{local_port}",
        f"{user}@{host}",
    ]

    key_path = _get_key_path()
    if key_path:
        cmd.insert(2, "-i")
        cmd.insert(3, key_path)

    return cmd


def start_tunnel() -> Optional[int]:
    cmd = _build_ssh_command()
    if not cmd:
        return None

    logger.info(f"🔌 启动 SSH 隧道: {settings.tunnel_server_host}:{settings.tunnel_remote_port}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        pid = proc.pid

        # 等待一小段时间检查进程是否存活
        try:
            proc.wait(timeout=3)
            # 进程已退出，说明连接失败
            stderr_out = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            logger.error(f"❌ SSH 隧道启动失败 (PID: {pid}): {stderr_out[:500]}")
            TUNNEL_LOG_FILE.write_text(stderr_out)
            if TUNNEL_PID_FILE.exists():
                TUNNEL_PID_FILE.unlink()
            return None
        except subprocess.TimeoutExpired:
            # 进程还在运行，连接成功
            TUNNEL_PID_FILE.write_text(str(pid))
            logger.info(f"✅ SSH 隧道已启动 (PID: {pid}) - {settings.tunnel_server_host}:{settings.tunnel_remote_port} -> localhost:{settings.tunnel_local_port}")
            return pid

    except Exception as e:
        logger.error(f"❌ 启动 SSH 隧道异常: {e}")
        return None


def stop_tunnel():
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
    if not TUNNEL_PID_FILE.exists():
        return False
    try:
        pid = int(TUNNEL_PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, OSError):
        TUNNEL_PID_FILE.unlink(missing_ok=True)
        return False


def get_tunnel_pid() -> Optional[int]:
    """获取隧道 PID"""
    if not TUNNEL_PID_FILE.exists():
        return None
    try:
        return int(TUNNEL_PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


async def ensure_tunnel():
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
