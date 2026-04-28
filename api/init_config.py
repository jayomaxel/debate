"""
初始化配置数据
确保数据库中有默认的模型配置和Coze配置
"""
import sys
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select

# 添加当前目录到Python路径
sys.path.insert(0, '.')

from database import SessionLocal, init_db
from models.config import ModelConfig, CozeConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_default_configs():
    """初始化默认配置"""
    db: Session = SessionLocal()
    
    try:
        # 检查并创建默认模型配置
        model_config = db.execute(
            select(ModelConfig).limit(1)
        ).scalar_one_or_none()
        
        if not model_config:
            logger.info("创建默认模型配置...")
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
        else:
            logger.info("✓ 模型配置已存在")
        
        # 检查并创建默认Coze配置
        coze_config = db.execute(
            select(CozeConfig).limit(1)
        ).scalar_one_or_none()
        
        if not coze_config:
            logger.info("创建默认Coze配置...")
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
        else:
            logger.info("✓ Coze配置已存在")
        
        # 提交更改
        db.commit()
        logger.info("✓ 配置初始化完成")
        
    except Exception as e:
        logger.error(f"✗ 配置初始化失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("开始初始化配置数据...")
    
    # 确保数据库表已创建
    logger.info("检查数据库表...")
    init_db()
    
    # 初始化默认配置
    init_default_configs()
    
    logger.info("配置初始化完成！")
