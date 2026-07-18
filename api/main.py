"""
FastAPI application entrypoint.
"""

from pathlib import Path
from time import time
from hmac import compare_digest

import uvicorn
import database as database_module
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, Info, generate_latest
from sqlalchemy import text

from config import settings
from database import get_redis, init_db, init_engine, init_redis
from logging_config import get_logger, setup_logging
from middleware.rate_limit import RateLimitMiddleware
from middleware.upload_guard import UploadGuardMiddleware
from routers import admin, admin_kb, auth, student, student_kb, teacher, voice, websocket
from services.kb_seed_service import KBSeedService
from services.kb_vector_schema_service import KBVectorSchemaService
from services.e2e_health_probe_service import (
    e2e_health_probe_service,
    get_last_probe_state,
)
from utils.http_client_pool import async_http_client_pool


setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="AIDebate API",
    description="Realtime debate-teaching backend API.",
    version="1.0.0",
)

SERVICE_INFO = Info("debate_service", "Static service metadata.")
SERVICE_INFO.info(
    {
        "app_name": app.title,
        "version": app.version,
        "environment": settings.ENVIRONMENT,
    }
)
SERVICE_START_TIME = Gauge(
    "debate_service_start_time_seconds",
    "Unix timestamp when the API process started.",
)
SERVICE_START_TIME.set(time())
DATABASE_UP = Gauge("debate_database_up", "Database connectivity status.")
REDIS_UP = Gauge("debate_redis_up", "Redis connectivity status.")
REDIS_ENABLED = Gauge("debate_redis_enabled", "Whether Redis is configured for use.")

# CORS：生产环境不建议 allow_origins=["*"] 与 allow_credentials=True 同时出现
_cors_origins = settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else ["*"]
if settings.IS_PRODUCTION and "*" in _cors_origins:
    raise RuntimeError(
        "Production CORS cannot include '*' while credentials are enabled. "
        "Set ALLOWED_ORIGINS to explicit HTTPS origins."
    )

app.add_middleware(UploadGuardMiddleware)
app.add_middleware(RateLimitMiddleware)
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

upload_root = Path(settings.UPLOAD_DIR)
upload_root.mkdir(parents=True, exist_ok=True)
for public_media_dir in ("audio", "asr"):
    media_path = upload_root / public_media_dir
    media_path.mkdir(parents=True, exist_ok=True)
    app.mount(
        f"/uploads/{public_media_dir}",
        StaticFiles(directory=media_path),
        name=f"uploads-{public_media_dir}",
    )


def _database_health() -> tuple[bool, str | None]:
    """Run a lightweight query to verify database connectivity."""
    if database_module.SessionLocal is None:
        database_module.init_engine()

    if database_module.SessionLocal is None:
        return False, "database session factory is not initialized"

    db = database_module.SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # pragma: no cover - depends on runtime services
        return False, str(exc)
    finally:
        db.close()


def _redis_health() -> tuple[str, str | None]:
    """Return Redis status: connected, disabled, or disconnected."""
    try:
        redis_client = get_redis()
        if redis_client is None:
            return "disabled", None
        redis_client.ping()
        return "connected", None
    except Exception as exc:  # pragma: no cover - depends on runtime services
        return "disconnected", str(exc)


def _update_operational_metrics() -> None:
    database_connected, _ = _database_health()
    redis_status, _ = _redis_health()

    DATABASE_UP.set(1 if database_connected else 0)
    REDIS_UP.set(1 if redis_status == "connected" else 0)
    REDIS_ENABLED.set(0 if redis_status == "disabled" else 1)


async def _ai_runtime_health() -> dict:
    """Load effective AI configuration without returning any secret values."""
    if database_module.SessionLocal is None:
        return {"status": "unavailable", "services": {}}

    from services.config_service import ConfigService

    db = database_module.SessionLocal()
    try:
        services = await ConfigService(db).get_runtime_readiness()
        required_names = {"model", "asr", "tts", "vector"}
        missing = sorted(
            name
            for name in required_names
            if not services.get(name, {}).get("configured")
        )
        return {
            "status": "ready" if not missing else "degraded",
            "missing": missing,
            "services": services,
        }
    except Exception as exc:
        logger.exception("Failed to evaluate AI runtime readiness")
        return {"status": "error", "error": str(exc), "services": {}}
    finally:
        db.close()


def _e2e_health_snapshot() -> dict:
    """Expose the last probe result without running an expensive probe."""
    return {
        "enabled": bool(settings.E2E_HEALTH_PROBE_ENABLED),
        "release_gate_required": bool(settings.RELEASE_GATE_REQUIRE_E2E_HEALTH),
        "last": get_last_probe_state(),
    }


def _authorize_e2e_probe(request: Request) -> None:
    expected_token = (settings.E2E_HEALTH_PROBE_TOKEN or "").strip()
    if not expected_token:
        return
    supplied_token = request.headers.get("X-E2E-Probe-Token", "")
    if not supplied_token or not compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=403, detail="Invalid E2E probe token")

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

            from services.config_service import ConfigService

            ai_services = await ConfigService(db).get_runtime_readiness()
            missing_ai_services = sorted(
                name
                for name in ("model", "asr", "tts", "vector")
                if not ai_services.get(name, {}).get("configured")
            )
            if missing_ai_services:
                logger.warning(
                    "AI runtime configuration is incomplete: %s",
                    ", ".join(missing_ai_services),
                )

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

            try:
                from services.room_manager import room_manager

                recovered_jobs = await room_manager.recover_pending_report_jobs(db)
                if recovered_jobs:
                    logger.info("Recovered %s pending report jobs.", recovered_jobs)
            except Exception:
                db.rollback()
                logger.exception("Failed to recover pending report jobs.")
        except Exception:
            db.rollback()
            logger.exception("Failed to initialize default configuration.")
        finally:
            db.close()

        logger.info("Initializing Redis...")
        init_redis()
        redis_status, redis_error = _redis_health()
        if redis_status == "disabled":
            logger.warning("Redis is disabled for this process; cache-backed features will run in degraded mode.")
        elif redis_status == "connected":
            logger.info("Redis connection initialized.")
        else:
            logger.warning("Redis connection failed during startup: %s", redis_error)

        _update_operational_metrics()
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
    database_connected, database_error = _database_health()
    redis_status, redis_error = _redis_health()
    ai_runtime = (
        await _ai_runtime_health()
        if database_connected
        else {"status": "unavailable", "services": {}}
    )
    _update_operational_metrics()

    status = "healthy"
    status_code = 200

    if not database_connected:
        status = "unhealthy"
        status_code = 503
    elif redis_status == "disconnected":
        status = "degraded"

    elif ai_runtime.get("status") != "ready":
        status = "degraded"

    payload = {
        "status": status,
        "database": {
            "status": "connected" if database_connected else "disconnected",
            "url_configured": bool(settings.DATABASE_URL),
        },
        "redis": {
            "status": redis_status,
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
        },
        "ai": ai_runtime,
        "e2e": _e2e_health_snapshot(),
    }

    if database_error:
        payload["database"]["error"] = database_error

    if redis_error:
        payload["redis"]["error"] = redis_error

    return JSONResponse(status_code=status_code, content=payload)


@app.get("/health/e2e")
@app.get("/api/health/e2e")
@app.get("/health/readiness")
@app.get("/api/health/readiness")
async def e2e_health_check(request: Request):
    """Run the production speech -> transcript -> AI response health probe."""
    _authorize_e2e_probe(request)

    if database_module.SessionLocal is None:
        payload = {
            "status": "unavailable",
            "error": "database session factory is not initialized",
            "release_gate": {
                "required": bool(settings.RELEASE_GATE_REQUIRE_E2E_HEALTH),
                "eligible": False,
            },
        }
        return JSONResponse(status_code=503, content=payload)

    db = database_module.SessionLocal()
    try:
        payload = await e2e_health_probe_service.run(db)
    finally:
        db.close()

    status_code = 200 if payload.get("status") == "passed" else 503
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/metrics", include_in_schema=False)
async def metrics():
    _update_operational_metrics()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7860)
