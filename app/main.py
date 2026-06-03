import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from cryptography.fernet import Fernet

from app.config import settings
from app.db.session import close_db, init_db
from app.scheduler import TaskScheduler, register_tasks
from app.services.tunnel import ensure_tunnel, stop_tunnel

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

    # 确保 FERNET_KEY 存在（未设置时自动生成）
    if not settings.fernet_key:
        try:
            new_key = Fernet.generate_key().decode()
            settings.fernet_key = new_key
            logger.info("🔑 已自动生成 FERNET_KEY（运行时内存）")

            # 尝试写入 .env 文件供下次使用（不阻塞启动）
            env_path = Path(".env")
            try:
                if env_path.is_file():
                    content = env_path.read_text(encoding="utf-8")
                    if "FERNET_KEY=" in content:
                        new_content = content.replace("FERNET_KEY=", f"FERNET_KEY={new_key}")
                        env_path.write_text(new_content, encoding="utf-8")
                        logger.info("📝 FERNET_KEY 已写入 .env")
                    else:
                        env_path.write_text(
                            f"FERNET_KEY={new_key}\n{content}", encoding="utf-8"
                        )
                        logger.info("📝 FERNET_KEY 已追加到 .env")
                elif not env_path.exists():
                    env_path.write_text(
                        f"FERNET_KEY={new_key}\n"
                        "TZ=Asia/Shanghai\n"
                        "DATABASE_URL=sqlite+aiosqlite:///data/campus.db\n"
                        "FRONTEND_URL=http://localhost:3000\n",
                        encoding="utf-8",
                    )
                    logger.info("📝 已创建 .env 文件")
            except OSError:
                logger.info("📝 FERNET_KEY 保持运行时内存中（.env 不可写，如 Docker volume 挂载）")
        except Exception as e:
            logger.warning(f"⚠️ FERNET_KEY 生成失败: {e}")

    # 启动时：初始化数据库
    await init_db()
    logger.info("✅ 数据库初始化完成")

    # 迁移 .env 中的业务配置到数据库（仅首次运行）并加载数据库配置覆盖 settings
    try:
        from app.services.config_store import ConfigStoreService
        from app.db.session import async_session
        async with async_session() as db:
            store = ConfigStoreService(db, settings.fernet_key)
            migrated = await store.migrate_from_env(settings.model_dump())
            if migrated:
                logger.info(f"✅ 已迁移 {migrated} 项配置从 .env 到数据库")
            # 从数据库加载配置覆盖运行时 settings（数据库优先）
            loaded = await store.load_all_into_settings(settings)
            if loaded:
                logger.info(f"✅ 已从数据库加载 {loaded} 项配置覆盖 runtime settings")
    except Exception as e:
        logger.warning(f"⚠️ 配置加载跳过: {e}")

    # 注册并启动定时任务
    register_tasks(scheduler)
    scheduler.start()
    logger.info("✅ 定时任务调度器已启动")

    # 启动 SSH 隧道（如果配置了飞书应用）
    if settings.feishu_app_id and settings.feishu_app_secret:
        logger.info("🔌 检测到飞书应用配置，启动 SSH 隧道...")
        await ensure_tunnel()
    else:
        logger.info("🔌 飞书应用未配置，跳过 SSH 隧道")

    yield  # 应用运行中...

    # 关闭时：清理资源
    stop_tunnel()
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


@app.get("/api/health/detailed")
async def detailed_health():
    """详细服务状态检测（机器人连接情况）"""
    from app.llm.client import check_api_key
    from app.services.feishu_app_service import FeishuAppService
    from app.services.tunnel import is_tunnel_running, get_tunnel_pid

    # DeepSeek AI
    deepseek_ok = await check_api_key()

    # 飞书应用
    feishu_app = FeishuAppService()

    # SSH 隧道
    tunnel_running = is_tunnel_running()
    tunnel_pid = get_tunnel_pid()
    tunnel_info = f"PID:{tunnel_pid} -> :{settings.tunnel_remote_port}" if tunnel_running else "未连接"

    # 定时任务调度器
    scheduler_running = scheduler and scheduler.running

    # 飞书 Webhook
    webhook_configured = bool(settings.feishu_webhook_url)

    # Bark
    bark_configured = bool(settings.bark_key)

    # 数据库
    db_ok = True
    try:
        from app.db.session import async_session
        from sqlalchemy import text
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    services = {
        "server": {"status": "ok", "label": "后端服务", "icon": "server"},
        "database": {"status": "ok" if db_ok else "error", "label": "数据库", "icon": "database"},
        "deepseek": {"status": "ok" if deepseek_ok else "error", "label": "AI 服务", "icon": "brain"},
        "feishu_app": {"status": "ok" if feishu_app.is_configured else "warning", "label": "飞书应用机器人", "icon": "bot"},
        "feishu_webhook": {"status": "ok" if webhook_configured else "warning", "label": "飞书 Webhook 推送", "icon": "webhook"},
        "bark": {"status": "ok" if bark_configured else "warning", "label": "Bark 推送", "icon": "bell"},
        "tunnel": {"status": "ok" if tunnel_running else "warning", "label": "SSH 隧道", "icon": "tunnel"},
        "scheduler": {"status": "ok" if scheduler_running else "error", "label": "定时任务", "icon": "clock"},
    }

    all_ok = all(s["status"] == "ok" for s in services.values())

    return {
        "overall": "ok" if all_ok else "degraded",
        "message": "所有服务正常运行" if all_ok else "部分服务异常",
        "services": services,
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
from app.api.feishu_app import router as feishu_app_router
from app.api.llm import router as llm_router
from app.api.custom_reminders import router as custom_reminders_router
from app.api.rooms import router as rooms_router
from app.api.ai_providers import router as ai_providers_router

app.include_router(courses_router)
app.include_router(todos_router)
app.include_router(assignments_router)
app.include_router(config_router)
app.include_router(notification_router)
app.include_router(data_sources_router)
app.include_router(feishu_app_router)
app.include_router(llm_router)
app.include_router(custom_reminders_router)
app.include_router(rooms_router)
app.include_router(ai_providers_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
