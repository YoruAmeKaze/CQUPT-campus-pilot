from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=False,  # 设置为 True 可以查看 SQL 日志
    future=True,
)

# 创建异步会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库，创建所有表并添加默认用户"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await _migrate_missing_columns()
    
    # 2. 检查并创建默认用户
    from sqlalchemy import select
    from app.db.models import User
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == 1))
        existing_user = result.scalar_one_or_none()
        
        if not existing_user:
            default_user = User(
                id=1,
                student_id="default_user",
            )
            session.add(default_user)
            await session.commit()


async def _migrate_missing_columns():
    """迁移：给已有表添加缺失的新列"""
    from sqlalchemy import text, inspect
    
    async with engine.begin() as conn:
        
        def _get_columns(connection):
            inspector = inspect(connection)
            return {col["name"] for col in inspector.get_columns("todos")}
        
        existing_column_names = await conn.run_sync(_get_columns)
        
        migrations = [
            ("reminder_enabled", "INTEGER DEFAULT 0"),
            ("reminder_sent", "INTEGER DEFAULT 0"),
        ]
        
        for col_name, col_def in migrations:
            if col_name not in existing_column_names:
                await conn.execute(
                    text(f"ALTER TABLE todos ADD COLUMN {col_name} {col_def}")
                )


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
