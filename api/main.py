"""
FastAPI应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from pathlib import Path
from config import settings

# 导入路由
from routers import auth, teacher, student, websocket, admin, voice, admin_kb, student_kb

# 导入数据库初始化
from database import init_db, init_engine, init_redis

# 配置集中式日志
from logging_config import setup_logging, get_logger
from utils.http_client_pool import async_http_client_pool

# 初始化日志系统
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="辩论教学系统API",
    description="基于聊天室的实时辩论教学系统后端API",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该配置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
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
    """应用启动时执行"""
    logger.info("正在启动辩论教学系统API...")
    
    try:
        # 初始化数据库引擎
        logger.info("初始化数据库引擎...")
        init_engine()
        
        # 初始化数据库表（如果不存在则创建）
        logger.info("初始化数据库表...")
        init_db()
        logger.info("✓ 数据库表初始化完成")
        
        # 初始化默认配置
        logger.info("初始化默认配置...")
        from database import SessionLocal
        from models.config import ModelConfig, CozeConfig
        from sqlalchemy import select
        
        db = SessionLocal()
        try:
            # 检查并创建默认模型配置
            model_config = db.execute(select(ModelConfig).limit(1)).scalar_one_or_none()
            if not model_config:
                default_model_config = ModelConfig(
                    model_name="gpt-3.5-turbo",
                    api_endpoint="https://api.openai.com/v1/chat/completions",
                    api_key="",
                    temperature=0.7,
                    max_tokens=2000,
                    parameters={}
                )
                db.add(default_model_config)
                logger.info("✓ 默认模型配置已创建")
            
            # 检查并创建默认Coze配置
            coze_config = db.execute(select(CozeConfig).limit(1)).scalar_one_or_none()
            if not coze_config:
                default_coze_config = CozeConfig(
                    debater_1_bot_id="",
                    debater_2_bot_id="",
                    debater_3_bot_id="",
                    debater_4_bot_id="",
                    judge_bot_id="",
                    mentor_bot_id="",
                    api_token="",
                    parameters={}
                )
                db.add(default_coze_config)
                logger.info("✓ 默认Coze配置已创建")
            
            db.commit()
            logger.info("✓ 配置初始化完成")
        except Exception as e:
            logger.error(f"配置初始化失败: {e}")
            db.rollback()
        finally:
            db.close()
        
        # 初始化Redis连接
        logger.info("初始化Redis连接...")
        init_redis()
        logger.info("✓ Redis连接初始化完成")
        
        logger.info("✓ 辩论教学系统API启动成功！")
    except Exception as e:
        logger.error(f"✗ 启动失败: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info("正在关闭辩论教学系统API...")

    # 应用关闭时统一释放复用池中的长连接，避免遗留未关闭的 HTTP 连接。
    await async_http_client_pool.aclose_all()

    await async_http_client_pool.aclose_all()

@app.get("/")
async def root():
    return {"message": "辩论教学系统API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7860)
