import logging
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.fernet import Fernet

from app.db.models import SystemConfig, DataSource

logger = logging.getLogger(__name__)


# 系统级配置键（不含 user_id）
SYSTEM_KEYS = {
    "term_start_date": "学期开始日期，格式 YYYY-MM-DD",
    "bark_key": "Bark iOS 推送 Key",
    "deploy_mode": "部署模式: laptop / server",
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
