"""
FastAPI application entrypoint.
"""

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db, init_engine, init_redis
from logging_config import get_logger, setup_logging
from routers import admin, admin_kb, auth, student, student_kb, teacher, voice, websocket
from services.kb_seed_service import KBSeedService
from services.kb_vector_schema_service import KBVectorSchemaService
from utils.http_client_pool import async_http_client_pool


setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="AIDebate API",
    description="Realtime debate-teaching backend API.",
    version="1.0.0",
)

# CORS：生产环境不建议 allow_origins=["*"] 与 allow_credentials=True 同时出现
_cors_origins = settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else ["*"]
if settings.IS_PRODUCTION and "*" in _cors_origins:
    logger.warning(
        "生产环境 CORS allow_origins 包含 '*'，建议显式配置 ALLOWED_ORIGINS 环境变量"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(teacher.router)
app.include_router(student.router)
app.include_router(websocket.router)
app.include_router(admin.router)
app.include_router(admin_kb.router)
app.include_router(student_kb.router)
app.include_router(voice.router)

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.on_event("startup")
async def startup_event():
    """Initialize services and default records during startup."""
    logger.info("Starting AIDebate API...")

    try:
        logger.info("Initializing database engine...")
        init_engine()

        logger.info("Ensuring database schema...")
        init_db()
        logger.info("Database schema ready.")

        logger.info("Ensuring default configuration...")
        from sqlalchemy import select

        from database import SessionLocal
        from models.config import CozeConfig, ModelConfig

        db = SessionLocal()
        try:
            model_config = db.execute(select(ModelConfig).limit(1)).scalar_one_or_none()
            if not model_config:
                db.add(
                    ModelConfig(
                        model_name="gpt-3.5-turbo",
                        api_endpoint="https://api.openai.com/v1/chat/completions",
                        api_key="",
                        temperature=0.7,
                        max_tokens=2000,
                        parameters={},
                    )
                )
                logger.info("Created default model config.")

            coze_config = db.execute(select(CozeConfig).limit(1)).scalar_one_or_none()
            if not coze_config:
                db.add(
                    CozeConfig(
                        debater_1_bot_id="",
                        debater_2_bot_id="",
                        debater_3_bot_id="",
                        debater_4_bot_id="",
                        judge_bot_id="",
                        mentor_bot_id="",
                        api_token="",
                        parameters={},
                    )
                )
                logger.info("Created default Coze config.")

            db.commit()
            logger.info("Default configuration ready.")

            try:
                schema_changed = await KBVectorSchemaService.ensure_schema_matches_vector_config(
                    db
                )
                if schema_changed:
                    logger.info("Knowledge base vector schema aligned with vector config.")
            except Exception:
                db.rollback()
                logger.exception("Failed to align knowledge base vector schema.")

            try:
                repo_root = Path(__file__).resolve().parent.parent
                imported_seed_documents = await KBSeedService.import_repo_root_docx_files(
                    db=db,
                    repo_root=repo_root,
                )
                if imported_seed_documents:
                    logger.info(
                        "Imported %s repo-root knowledge documents into the KB.",
                        len(imported_seed_documents),
                    )
            except Exception:
                logger.exception("Failed to import repo-root knowledge documents.")
        except Exception:
            db.rollback()
            logger.exception("Failed to initialize default configuration.")
        finally:
            db.close()

        logger.info("Initializing Redis...")
        redis_client = init_redis()
        if redis_client is None:
            logger.warning("Redis is disabled for this process; cache-backed features will run in degraded mode.")
        else:
            logger.info("Redis connection initialized.")

        logger.info("AIDebate API started successfully.")
    except Exception:
        logger.exception("Application startup failed.")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Close shared resources during shutdown."""
    logger.info("Shutting down AIDebate API...")
    await async_http_client_pool.aclose_all()


@app.get("/")
async def root():
    return {"message": "AIDebate API", "status": "running"}


@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7860)
