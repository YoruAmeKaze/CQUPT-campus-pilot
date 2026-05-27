import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# 加载 .env 文件
load_dotenv()


class Settings(BaseSettings):
    """应用配置类 - 从环境变量读取所有配置"""

    # ===== 基础配置 =====
    student_id: str = ""
    deploy_mode: str = "laptop"  # laptop 或 server

    # ===== 学习通配置 =====
    chaoxing_username: str = ""  # 学习通账号（手机号）
    chaoxing_password: str = ""
    feishu_bark_callback: str = ""

    # ===== 数你最灵配置 =====
    smartestu_student_id: str = ""
    smartestu_password: str = ""
    smartestu_school_id: str = "cqupt"

    # ===== DeepSeek / LLM 配置 =====
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"

    # ===== 飞书应用配置 =====
    feishu_app_id: str = ""
    feishu_app_secret: str = ""

    # ===== 公网服务器（SSH隧道）=====
    tunnel_server_host: str = "SERVER_IP"
    tunnel_server_user: str = "root"
    tunnel_remote_port: str = "9997"
    tunnel_local_port: str = "8000"
    tunnel_key_path: str = ""

    # ===== 加密密钥 =====
    fernet_key: Optional[str] = None

    # ===== VPN（仅 server 模式）=====
    vpn_host: str = "vpn.cqupt.edu.cn"
    vpn_username: str = ""
    vpn_password: str = ""

    # ===== 应用配置 =====
    tz: str = "Asia/Shanghai"
    database_url: str = "sqlite+aiosqlite:///data/campus.db"
    frontend_url: str = "http://localhost:3000"

    # ===== 校历配置 =====
    term_start_date: str = "2026-03-02"

    # ===== Bark 推送配置 =====
    bark_key: str = ""

    # ===== 飞书机器人配置 =====
    feishu_webhook_url: str = ""

    # ===== 教室查询配置 =====
    campus: str = "main"  # main / xiantao
    enable_lab_query: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """确保 data 目录存在"""
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)

    @property
    def is_server_mode(self) -> bool:
        return self.deploy_mode.lower() == "server"


# 全局配置实例
settings = Settings()
