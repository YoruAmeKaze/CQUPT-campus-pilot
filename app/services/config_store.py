import logging
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.fernet import Fernet

from app.db.models import SystemConfig, DataSource

logger = logging.getLogger(__name__)


SYSTEM_KEYS = {
    # ===== 已有数据库配置 =====
    "term_start_date": "学期开始日期，格式 YYYY-MM-DD",
    "bark_key": "Bark iOS 推送 Key",
    "deploy_mode": "部署模式: laptop / server",
    "feishu_webhook_url": "飞书群机器人 Webhook URL",
    "auto_cleanup_enabled": "自动清理过时数据开关",
    "auto_cleanup_days": "数据保留天数",
    # ===== 从 .env 迁移到数据库的配置 =====
    "student_id": "学号",
    "chaoxing_username": "学习通账号（手机号）",
    "chaoxing_password": "学习通密码",
    "smartestu_student_id": "数你最灵学号",
    "smartestu_password": "数你最灵密码",
    "deepseek_api_key": "DeepSeek API Key",
    "deepseek_model": "DeepSeek 模型 (deepseek-chat / deepseek-reasoner)",
    "llm_base_url": "LLM API 地址 (默认 https://api.deepseek.com，Ollama 用 http://localhost:11434/v1)",
    "feishu_app_id": "飞书应用 App ID",
    "feishu_app_secret": "飞书应用 App Secret",
    "tunnel_server_host": "公网服务器 IP",
    "tunnel_server_user": "公网服务器用户名",
    "tunnel_remote_port": "公网服务器监听端口",
    "tunnel_local_port": "本地服务端口",
    "tunnel_key_path": "SSH 密钥路径",
    "vpn_host": "VPN 地址",
    "vpn_username": "VPN 用户名",
    "vpn_password": "VPN 密码",
}


class ConfigStoreService:
    """
    配置存储服务
    所有业务配置统一存储在数据库 system_configs 表中
    """

    def __init__(self, db: AsyncSession, fernet_key: Optional[str] = None):
        self.db = db
        self._fernet = Fernet(fernet_key) if fernet_key else None

    # ─── 系统配置（无 user_id）───

    async def get(self, key: str, default: str = "") -> str:
        result = await self.db.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        row = result.scalar_one_or_none()
        return row.value if row and row.value is not None else default

    async def set(self, key: str, value: str, description: str = "") -> None:
        result = await self.db.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
            row.updated_at = datetime.now()
        else:
            self.db.add(SystemConfig(key=key, value=value, description=description))
        await self.db.commit()

    async def get_all(self) -> Dict[str, str]:
        result = await self.db.execute(select(SystemConfig))
        return {row.key: row.value or "" for row in result.scalars().all()}

    async def load_all_into_settings(self, settings_obj: Any) -> int:
        """
        从数据库加载所有配置并覆盖到 settings 对象
        返回覆盖的配置数量
        """
        db_configs = await self.get_all()
        count = 0
        for key, value in db_configs.items():
            if value and hasattr(settings_obj, key):
                old = getattr(settings_obj, key)
                if str(old) != value:
                    setattr(settings_obj, key, value)
                    count += 1
        return count

    async def migrate_from_env(self, env_values: Dict[str, str]) -> int:
        """将 .env 中的业务配置迁移到数据库"""
        count = 0
        for key, desc in SYSTEM_KEYS.items():
            existing = await self.get(key)
            if not existing and key in env_values and env_values[key]:
                await self.set(key, env_values[key], desc)
                count += 1
                logger.info(f"  📥 迁移配置 {key} → 数据库")
        await self.db.commit()
        return count

    # ─── 数据源凭证（带 user_id + Fernet 加密）───

    async def get_data_source(self, user_id: int, source_type: str) -> Optional[dict]:
        result = await self.db.execute(
            select(DataSource).where(
                DataSource.user_id == user_id,
                DataSource.type == source_type,
            )
        )
        ds = result.scalar_one_or_none()
        if not ds or not ds.credentials:
            return None
        return self._decrypt_credentials(ds.credentials)

    async def save_data_source(
        self, user_id: int, source_type: str, name: str, credentials: dict
    ) -> DataSource:
        result = await self.db.execute(
            select(DataSource).where(
                DataSource.user_id == user_id,
                DataSource.type == source_type,
            )
        )
        ds = result.scalar_one_or_none()
        enc = self._encrypt_credentials(credentials)
        if ds:
            ds.name = name
            ds.credentials = enc
        else:
            ds = DataSource(
                user_id=user_id,
                type=source_type,
                name=name,
                credentials=enc,
            )
            self.db.add(ds)
        await self.db.commit()
        await self.db.refresh(ds)
        return ds

    def _encrypt_credentials(self, data: dict) -> str:
        import json
        raw = json.dumps(data)
        if self._fernet:
            return self._fernet.encrypt(raw.encode()).decode()
        return raw

    def _decrypt_credentials(self, raw: str) -> dict:
        import json
        try:
            if self._fernet:
                return json.loads(self._fernet.decrypt(raw.encode()).decode())
            return json.loads(raw)
        except Exception:
            return {}
