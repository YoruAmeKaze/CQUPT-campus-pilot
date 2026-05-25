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

    # ===== 企业微信配置 =====
    wxwork_corp_id: str = ""
    wxwork_agent_id: str = ""
    wxwork_agent_secret: str = ""
    wxwork_token: str = ""
    wxwork_encoding_aes_key: str = ""

    # ===== 学习通配置 =====
    chaoxing_username: str = ""  # 学习通账号（手机号）
    chaoxing_password: str = ""
    feishu_bark_callback: str = ""

    # ===== 数你最灵配置 =====
    smartestu_student_id: str = ""
    smartestu_password: str = ""
    smartestu_school_id: str = ""

    # ===== DeepSeek 配置 =====
    deepseek_api_key: str = ""

    # ===== 加密密钥 =====
    fernet_key: Optional[str] = None

    # ===== iCloud 日历（可选）=====
    caldav_url: Optional[str] = None
    caldav_username: Optional[str] = None
    caldav_password: Optional[str] = None

    # ===== VPN（仅 server 模式）=====
    vpn_host: str = "vpn.cqupt.edu.cn"
    vpn_username: str = ""
    vpn_password: str = ""

    # ===== 应用配置 =====
    tz: str = "Asia/Shanghai"
    database_url: str = "sqlite+aiosqlite:///data/campus.db"
    frontend_url: str = "http://localhost:3000"
    
    # ===== 校历配置 =====
    term_start_date: str = "2026-03-02"  # 第一周周一的日期

    # ===== Bark 推送配置 =====
    bark_key: str = ""  # Bark Key，用于 iOS 推送通知

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

    @property
    def is_wxwork_configured(self) -> bool:
        """检查企业微信是否已配置"""
        return all([
            self.wxwork_corp_id,
            self.wxwork_agent_id,
            self.wxwork_agent_secret,
        ])


# 全局配置实例
settings = Settings()
