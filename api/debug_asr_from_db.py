"""
ASR 独立诊断脚本。

作用：
1. 直接读取数据库中的 asr_config 配置。
2. 复用正式环境的 VoiceProcessor.transcribe_audio 调用链。
3. 输出 ASR 配置、音频校验结果、DashScope 文件 URL 诊断信息、最终识别结果。

使用示例：
    conda run -n python_311_venv python api/debug_asr_from_db.py --audio "E:\\test\\demo.webm"
    conda run -n python_311_venv python api/debug_asr_from_db.py --audio "E:\\test\\demo.mp3" --language zh --check-file-url
"""

import argparse
import asyncio
import json
import traceback
from pathlib import Path
from typing import Any, Dict

import httpx

import database
from config import settings
from services.config_service import ConfigService
from utils.voice_processor import voice_processor


def mask_secret(secret: str) -> str:
    """对敏感信息做脱敏显示，避免脚本日志泄露密钥。"""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}***{secret[-4:]}"


def infer_audio_format(audio_path: Path, audio_format: str | None) -> str:
    """优先使用命令行传入格式，否则根据文件后缀推断格式。"""
    if audio_format and audio_format.strip():
        return audio_format.strip().lower()

    suffix = audio_path.suffix.lower().lstrip(".")
    return suffix or "webm"


def need_dashscope_file_url(provider: str, model_name: str, api_endpoint: str) -> bool:
    """判断当前 ASR 配置是否走 DashScope 文件转写模式。"""
    return (
        provider == "dashscope"
        or model_name.startswith("qwen")
        or "dashscope" in api_endpoint
    )


def print_section(title: str) -> None:
    """统一打印分段标题，方便阅读诊断输出。"""
    print(f"\n{'=' * 18} {title} {'=' * 18}")


def build_config_snapshot(asr_config: Any) -> Dict[str, Any]:
    """整理一份适合打印的 ASR 配置快照。"""
    parameters = asr_config.parameters or {}
    return {
        "model_name": asr_config.model_name,
        "api_endpoint": asr_config.api_endpoint,
        "api_key_masked": mask_secret(asr_config.api_key or ""),
        "provider": parameters.get("provider"),
        "file_url_prefix": parameters.get("file_url_prefix")
        or parameters.get("fileUrlPrefix")
        or "",
        "task_base_url": parameters.get("task_base_url") or "",
        "poll_interval_seconds": parameters.get("poll_interval_seconds"),
        "poll_timeout_seconds": parameters.get("poll_timeout_seconds"),
        "parameters": parameters,
    }


async def diagnose_dashscope_file_url(
    audio_data: bytes,
    audio_format: str,
    parameters: Dict[str, Any],
    check_file_url: bool,
) -> None:
    """诊断 DashScope 文件转写依赖的公开音频 URL 是否可用。"""
    print_section("DashScope 文件 URL 诊断")

    # 调用正式逻辑中的持久化函数，确保诊断路径与线上一致。
    generated_url = await voice_processor._persist_audio_for_dashscope(
        audio_data=audio_data,
        audio_format=audio_format,
        parameters=parameters,
    )

    if not generated_url:
        print("生成文件 URL 失败。")
        print("可能原因：")
        print("1. 管理端 ASR 配置里没有配置 file_url_prefix。")
        print("2. 环境变量 PUBLIC_BASE_URL 没有配置。")
        print("3. 当前配置不是对外可访问的公网地址。")
        return

    print(f"生成的文件 URL: {generated_url}")
    print(f"本地上传目录: {Path(settings.UPLOAD_DIR) / 'asr'}")

    if not check_file_url:
        print("未启用 URL 可访问性检查。如需继续检查，请增加 --check-file-url 参数。")
        return

    if not generated_url.startswith(("http://", "https://")):
        print("生成的文件 URL 不是 http/https 地址，外部 ASR 服务无法直接访问。")
        return

    try:
        # 主动请求一次生成的文件 URL，先排除本机侧的静态文件访问问题。
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(generated_url)

        print(f"URL 检查状态码: {response.status_code}")
        if response.status_code == 200:
            print(f"URL 返回内容长度: {len(response.content)} bytes")
            print("本机访问该 URL 成功。若云端 ASR 仍失败，需要继续检查公网映射、域名解析或防火墙。")
        else:
            print("本机访问该 URL 失败。重点检查：")
            print("1. 后端服务是否已启动并挂载 /uploads。")
            print("2. file_url_prefix 是否写成了前端地址、内网地址或错误端口。")
            print("3. Nginx/反向代理是否放行了 uploads 目录。")
    except Exception as exc:
        print(f"URL 可访问性检查异常: {exc}")
        print("这通常意味着生成的地址当前不可访问，DashScope 文件转写大概率也会失败。")


async def run_debug(args: argparse.Namespace) -> int:
    """执行 ASR 诊断主流程。"""
    # audio_path = Path(args.audio).expanduser().resolve()
    audio_path = Path(r"E:\my_project\基于聊天室的实时辩论教学系统\AIDebate\dev_docs\1.wav")
    if not audio_path.exists():
        print(f"音频文件不存在: {audio_path}")
        return 1

    audio_format = infer_audio_format(audio_path, args.audio_format)
    audio_data = audio_path.read_bytes()

    print_section("运行环境")
    print(f"音频文件: {audio_path}")
    print(f"音频格式: {audio_format}")
    print(f"音频大小: {len(audio_data)} bytes")
    print(f"数据库地址: {settings.DATABASE_URL}")
    print(f"上传目录: {Path(settings.UPLOAD_DIR).resolve()}")

    # 初始化数据库引擎，保证脚本直接运行时也能拿到 SessionLocal。
    database.init_engine()
    if database.SessionLocal is None:
        print("数据库会话初始化失败。")
        return 1

    db = database.SessionLocal()
    try:
        config_service = ConfigService(db)

        # 调用配置服务，读取管理端保存的 ASR 配置。
        asr_config = await config_service.get_asr_config()
        config_snapshot = build_config_snapshot(asr_config)

        print_section("ASR 配置")
        print(json.dumps(config_snapshot, ensure_ascii=False, indent=2))

        # 调用正式音频校验逻辑，先排除录音文件本身的问题。
        is_valid, message = await voice_processor.validate_audio_quality(audio_data)
        print_section("音频校验")
        print(
            json.dumps(
                {"is_valid": is_valid, "message": message or ""},
                ensure_ascii=False,
                indent=2,
            )
        )
        if not is_valid:
            print("音频文件未通过基础校验，正式 ASR 流程也会在这里失败。")
            return 2

        parameters = asr_config.parameters or {}
        provider = (parameters.get("provider") or "").strip()
        model_name = (asr_config.model_name or "").strip()
        api_endpoint = (asr_config.api_endpoint or "").strip()

        # 如果是 DashScope 文件转写，额外诊断文件 URL 问题。
        if need_dashscope_file_url(provider, model_name, api_endpoint):
            await diagnose_dashscope_file_url(
                audio_data=audio_data,
                audio_format=audio_format,
                parameters=parameters,
                check_file_url=args.check_file_url,
            )

        print_section("ASR 调用结果")

        # 直接复用正式 ASR 识别逻辑，确保与线上行为一致。
        result = await voice_processor.transcribe_audio(
            audio_data=audio_data,
            audio_format=audio_format,
            language=args.language,
            db=db,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if result.get("error"):
            print("\n诊断结论：ASR 调用失败，请优先根据 error 字段和上面的配置诊断输出排查。")
            return 3

        print("\n诊断结论：ASR 调用成功，核心转写链路可用。")
        return 0
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
        description="读取数据库 asr_config 并复用正式逻辑执行 ASR 诊断"
    )
    parser.add_argument(
        "--audio",
        default=None,
        help="待测试的音频文件路径，例如 E:\\test\\demo.webm",
    )
    parser.add_argument(
        "--audio-format",
        default=None,
        help="可选，显式指定音频格式，例如 webm/mp3/wav；默认按文件后缀推断",
    )
    parser.add_argument(
        "--language",
        default="zh",
        help="识别语言，默认 zh",
    )
    parser.add_argument(
        "--check-file-url",
        action="store_true",
        help="当 ASR 走 DashScope 文件转写时，额外检查生成的文件 URL 是否可访问",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # 解析参数后执行主流程，便于通过退出码判断成功失败。
    arguments = parse_args()
    raise SystemExit(asyncio.run(run_debug(arguments)))
