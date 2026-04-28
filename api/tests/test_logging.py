"""
测试日志系统
验证日志配置是否正常工作
"""
from logging_config import setup_logging, get_logger

# 初始化日志系统
log_file = setup_logging()

# 获取日志记录器
logger = get_logger(__name__)

def test_logging():
    """测试各个日志级别"""
    print("\n开始测试日志系统...")
    print(f"日志文件位置: {log_file}\n")
    
    logger.debug("这是一条 DEBUG 级别的日志")
    logger.info("这是一条 INFO 级别的日志")
    logger.warning("这是一条 WARNING 级别的日志")
    logger.error("这是一条 ERROR 级别的日志")
    
    # 测试异常日志
    try:
        result = 1 / 0
    except Exception as e:
        logger.exception("捕获到异常（会自动记录堆栈信息）")
    
    # 测试不同模块的日志
    test_module_logging()
    
    print("\n日志测试完成！")
    print(f"请查看日志文件: {log_file}")
    print("\n提示: 使用以下命令查看日志内容:")
    print(f"  type {log_file}")
    print(f"  或使用文本编辑器打开")


def test_module_logging():
    """测试模块化日志"""
    module_logger = get_logger("test_module")
    module_logger.info("来自测试模块的日志")
    
    # 模拟 WebSocket 日志
    ws_logger = get_logger("api.routers.websocket")
    ws_logger.info("模拟 WebSocket 连接: User test_user connected to room test_room")
    ws_logger.debug("模拟 WebSocket 调试信息: Received message type=speech")
    
    # 模拟服务日志
    service_logger = get_logger("api.services.room_manager")
    service_logger.info("模拟房间管理: Room test_room created")
    service_logger.warning("模拟警告: Room test_room has no participants")


if __name__ == "__main__":
    test_logging()
