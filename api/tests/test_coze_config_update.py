"""
测试 CozeConfig 模型更新
验证新的多 agent 字段是否正确
"""
import sys
sys.path.insert(0, '.')

from models.config import CozeConfig

def test_coze_config_fields():
    """测试 CozeConfig 模型字段"""
    print("测试 CozeConfig 模型...")
    
    # 创建默认配置
    config = CozeConfig.get_default()
    
    # 检查所有字段
    assert hasattr(config, 'debater_1_bot_id'), "缺少 debater_1_bot_id 字段"
    assert hasattr(config, 'debater_2_bot_id'), "缺少 debater_2_bot_id 字段"
    assert hasattr(config, 'debater_3_bot_id'), "缺少 debater_3_bot_id 字段"
    assert hasattr(config, 'debater_4_bot_id'), "缺少 debater_4_bot_id 字段"
    assert hasattr(config, 'judge_bot_id'), "缺少 judge_bot_id 字段"
    assert hasattr(config, 'mentor_bot_id'), "缺少 mentor_bot_id 字段"
    assert hasattr(config, 'api_token'), "缺少 api_token 字段"
    assert hasattr(config, 'parameters'), "缺少 parameters 字段"
    
    # 检查默认值
    assert config.debater_1_bot_id == "", "debater_1_bot_id 默认值应为空字符串"
    assert config.debater_2_bot_id == "", "debater_2_bot_id 默认值应为空字符串"
    assert config.debater_3_bot_id == "", "debater_3_bot_id 默认值应为空字符串"
    assert config.debater_4_bot_id == "", "debater_4_bot_id 默认值应为空字符串"
    assert config.judge_bot_id == "", "judge_bot_id 默认值应为空字符串"
    assert config.mentor_bot_id == "", "mentor_bot_id 默认值应为空字符串"
    assert config.api_token == "", "api_token 默认值应为空字符串"
    assert config.parameters == {}, "parameters 默认值应为空字典"
    
    print("✓ 所有字段检查通过")
    print(f"✓ CozeConfig 模型: {config}")
    
    # 测试设置值
    config.debater_1_bot_id = "7428000001"
    config.debater_2_bot_id = "7428000002"
    config.debater_3_bot_id = "7428000003"
    config.debater_4_bot_id = "7428000004"
    config.judge_bot_id = "7428000005"
    config.mentor_bot_id = "7428000006"
    config.api_token = "pat_test_token"
    
    assert config.debater_1_bot_id == "7428000001"
    assert config.debater_2_bot_id == "7428000002"
    assert config.debater_3_bot_id == "7428000003"
    assert config.debater_4_bot_id == "7428000004"
    assert config.judge_bot_id == "7428000005"
    assert config.mentor_bot_id == "7428000006"
    assert config.api_token == "pat_test_token"
    
    print("✓ 字段赋值测试通过")
    print("\n所有测试通过！CozeConfig 模型已正确更新。")

if __name__ == "__main__":
    test_coze_config_fields()
