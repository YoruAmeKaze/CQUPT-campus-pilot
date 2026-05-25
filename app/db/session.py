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
    # 1. 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
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


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
