"""
模型配置独立诊断脚本。

作用：
1. 直接读取数据库中的 model_config 配置。
2. 复用项目正式链路的模型地址拼装逻辑。
3. 主动发送一次最小化 LLM 请求，方便排查模型配置是否可用。

使用示例：
    conda run -n python_311_venv python api/debug_model_from_db.py
    conda run -n python_311_venv python api/debug_model_from_db.py --prompt "请只回复：ok"
"""

import argparse
import asyncio
import json
import traceback

import database
from config import settings
from services.config_service import ConfigService
from services.model_test_service import ModelTestService


def print_section(title: str) -> None:
    """统一打印分段标题，方便阅读调试输出。"""
    print(f"\n{'=' * 18} {title} {'=' * 18}")


async def run_debug(args: argparse.Namespace) -> int:
    """执行模型配置诊断主流程。"""
    print_section("运行环境")
    print(f"数据库地址: {settings.DATABASE_URL}")
    print(f"默认模型基地址: {settings.OPENAI_BASE_URL}")

    # 初始化数据库引擎，保证脚本独立执行时也能读取正式配置。
    database.init_engine()
    if database.SessionLocal is None:
        print("数据库会话初始化失败。")
        return 1

    db = database.SessionLocal()
    try:
        config_service = ConfigService(db)
        model_config = await config_service.get_model_config()
        tester = ModelTestService(db)

        print_section("模型配置")
        print(
            json.dumps(
                {
                    "model_name": model_config.model_name,
                    "api_endpoint": model_config.api_endpoint,
                    "api_key_masked": tester.mask_secret(model_config.api_key or ""),
                    "temperature": model_config.temperature,
                    "max_tokens": model_config.max_tokens,
                    "parameters": model_config.parameters or {},
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        print_section("模型调用测试")
        success, error_msg, result = await tester.test_model_connection(
            prompt=args.prompt,
            timeout_seconds=args.timeout,
        )

        print(
            json.dumps(
                {
                    "success": success,
                    "error": error_msg,
                    "result": result,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        if success:
            print("\n诊断结论：模型配置可用。")
            return 0

        print("\n诊断结论：模型配置调用失败，请根据 error 和 result 排查。")
        return 2

    except Exception as exc:
        print_section("脚本异常")
        print(f"异常信息: {exc}")
        print(traceback.format_exc())
        return 9
    finally:
        # 关闭数据库会话，避免脚本残留连接。
        db.close()


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="读取数据库 model_config 并执行一次实际模型调用测试"
    )
    parser.add_argument(
        "--prompt",
        default="请只回复：模型连接测试成功",
        help="测试时发送给模型的简短提示词",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="请求超时时间，单位秒，默认 30 秒",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    raise SystemExit(asyncio.run(run_debug(arguments)))
