"""
语音处理器测试
"""

import asyncio
import os
from utils.voice_processor import voice_processor


async def test_audio_validation():
    """测试音频质量验证"""
    print("=== 测试音频质量验证 ===")

    # 测试空数据
    is_valid, message = await voice_processor.validate_audio_quality(b"")
    print(f"空数据: valid={is_valid}, message={message}")
    assert not is_valid

    # 测试太小的数据
    is_valid, message = await voice_processor.validate_audio_quality(b"abc")
    print(f"太小数据: valid={is_valid}, message={message}")
    assert not is_valid

    # 测试正常大小的数据
    test_data = b"x" * 2048
    is_valid, message = await voice_processor.validate_audio_quality(test_data)
    print(f"正常数据: valid={is_valid}, message={message}")
    assert is_valid

    print("✅ 音频质量验证测试通过\n")


async def test_base64_encoding():
    """测试Base64编码/解码"""
    print("=== 测试Base64编码/解码 ===")

    original_data = b"Hello, World! This is test audio data."

    # 编码
    encoded = voice_processor.encode_audio_base64(original_data)
    print(f"编码后: {encoded[:50]}...")

    # 解码
    decoded = voice_processor.decode_audio_base64(encoded)
    print(f"解码后: {decoded[:50]}...")

    # 验证
    assert original_data == decoded
    print("✅ Base64编码/解码测试通过\n")


async def test_tts_synthesis():
    """测试TTS语音合成（需要配置OpenAI API密钥）"""
    print("=== 测试TTS语音合成 ===")

    # 检查是否配置了API密钥
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  未配置OPENAI_API_KEY，跳过TTS测试")
        return

    text = "你好，我是AI辩手一号。"

    print(f"合成文字: {text}")
    audio_data = await voice_processor.synthesize_speech(
        text, voice_id="alloy", speed=1.0
    )

    if audio_data:
        print(f"✅ TTS合成成功，音频大小: {len(audio_data)} bytes")

        # 保存测试音频
        test_file = "test_tts_output.mp3"
        with open(test_file, "wb") as f:
            f.write(audio_data)
        print(f"✅ 测试音频已保存: {test_file}")
    else:
        print("❌ TTS合成失败")


async def test_asr_transcription():
    """测试ASR语音识别（需要配置OpenAI API密钥和测试音频文件）"""
    print("=== 测试ASR语音识别 ===")

    # 检查是否配置了API密钥
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  未配置OPENAI_API_KEY，跳过ASR测试")
        return

    # 检查是否有测试音频文件
    test_audio_file = "test_audio.mp3"
    if not os.path.exists(test_audio_file):
        print(f"⚠️  未找到测试音频文件 {test_audio_file}，跳过ASR测试")
        return

    # 读取音频文件
    with open(test_audio_file, "rb") as f:
        audio_data = f.read()

    print(f"音频文件大小: {len(audio_data)} bytes")

    # 调用ASR
    result = await voice_processor.transcribe_audio(
        audio_data, audio_format="mp3", language="zh"
    )

    if "error" in result:
        print(f"❌ ASR识别失败: {result['error']}")
    else:
        print("✅ ASR识别成功")
        print(f"识别文字: {result['text']}")
        print(f"音频时长: {result['duration']}秒")
        print(f"置信度: {result['confidence']}")


async def main():
    """运行所有测试"""
    print("开始测试语音处理器...\n")

    try:
        await test_audio_validation()
        await test_base64_encoding()
        await test_tts_synthesis()
        await test_asr_transcription()

        print("\n=== 所有测试完成 ===")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
