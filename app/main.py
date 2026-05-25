import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import close_db, init_db
from app.scheduler import TaskScheduler, register_tasks

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局调度器实例
scheduler = TaskScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 CampusPilot 启动中...")

    # 启动时：初始化数据库
    await init_db()
    logger.info("✅ 数据库初始化完成")

    # 迁移 .env 中的业务配置到数据库（仅首次运行）
    try:
        from app.services.config_store import ConfigStoreService
        from app.db.session import async_session
        async with async_session() as db:
            store = ConfigStoreService(db, settings.fernet_key)
            migrated = await store.migrate_from_env(settings.model_dump())
            if migrated:
                logger.info(f"✅ 已迁移 {migrated} 项配置从 .env 到数据库")
    except Exception as e:
        logger.warning(f"⚠️ 配置迁移跳过: {e}")

    # 注册并启动定时任务
    register_tasks(scheduler)
    scheduler.start()
    logger.info("✅ 定时任务调度器已启动")

    yield  # 应用运行中...

    # 关闭时：清理资源
    scheduler.shutdown()
    logger.info("✅ 定时任务调度器已停止")
    
    await close_db()
    logger.info("👋 CampusPilot 已关闭")


# 创建 FastAPI 实例
app = FastAPI(
    title="CampusPilot",
    description="重庆邮电大学个人学业智能助理 API",
    version="2.0.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://localhost:3001",  # Vite 备用端口
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "service": "CampusPilot",
        "version": "2.0.0",
        "mode": settings.deploy_mode,
    }


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用 CampusPilot - 重庆邮电大学个人学业智能助理",
        "docs": "/docs",
        "health": "/health",
    }


# 注册路由
from app.api.courses import router as courses_router
from app.api.todos import router as todos_router
from app.api.assignments import router as assignments_router
from app.api.config import router as config_router
from app.api.notification import router as notification_router
from app.api.data_sources import router as data_sources_router

app.include_router(courses_router)
app.include_router(todos_router)
app.include_router(assignments_router)
app.include_router(config_router)
app.include_router(notification_router)
app.include_router(data_sources_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
