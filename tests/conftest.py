import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.models import Base
from app.db.session import get_db


# 测试用数据库 URL（使用内存 SQLite）
TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理：删除所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine):
    """创建测试数据库会话"""
    async_session = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


@pytest.fixture(scope="function")
async def client(db_session):
    """创建测试客户端，覆盖数据库依赖"""
    async def override_get_db():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data():
    """示例用户数据"""
    return {
        "wxwork_userid": "test_user_001",
        "student_id": "STUDENT_ID",
    }


@pytest.fixture
def sample_course_data():
    """示例课程数据"""
    return {
        "name": "高等数学",
        "teacher": "张老师",
        "location": "A201",
        "day_of_week": 1,
        "start_week": 1,
        "end_week": 16,
        "start_slot": 1,
        "end_slot": 2,
        "start_time": "08:30",
        "end_time": "10:05",
    }


@pytest.fixture
def sample_assignment_data():
    """示例作业数据"""
    from datetime import datetime
    return {
        "title": "高等数学作业3",
        "description": "完成教材P58-60习题",
        "course_name": "高等数学",
        "due_time": datetime(2024, 12, 25, 23, 59, 0),
        "is_completed": False,
    }
