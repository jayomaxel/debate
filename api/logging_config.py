"""
集中式日志配置
所有日志统一写入 api/logs/app.log
"""
import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging():
    """
    配置应用日志
    - 所有日志写入 api/logs/app.log
    - 控制台输出INFO级别以上日志
    - 文件记录DEBUG级别以上日志
    - 日志文件自动轮转（最大10MB，保留5个备份）
    """
    # 获取当前文件所在目录（api目录）
    current_dir = Path(__file__).parent
    log_dir = current_dir / "logs"
    
    # 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 日志文件路径
    log_file = log_dir / "app.log"
    
    # 日志格式
    log_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # 清除现有的处理器
    root_logger.handlers.clear()
    
    # 文件处理器（带轮转）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=2 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # 记录启动信息
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info(f"日志系统初始化完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"日志文件路径: {log_file.absolute()}")
    logger.info("=" * 80)
    
    return log_file


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称（通常使用 __name__）
    
    Returns:
        配置好的日志记录器
    """
    return logging.getLogger(name)
