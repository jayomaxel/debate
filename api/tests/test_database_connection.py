"""
测试数据库连接
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("="*60)
print("数据库连接测试")
print("="*60)
print()

# 步骤1: 检查.env文件
print("步骤1: 检查.env文件...")
env_file = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_file):
    print("  ✓ .env文件存在")
else:
    print("  ✗ .env文件不存在")
    print("  请从.env.example复制并配置")
    sys.exit(1)

# 步骤2: 加载配置
print("\n步骤2: 加载配置...")
try:
    from config import settings
    print(f"  ✓ 配置加载成功")
    print(f"  数据库URL: {settings.DATABASE_URL[:30]}...")
except Exception as e:
    print(f"  ✗ 配置加载失败: {e}")
    sys.exit(1)

# 步骤3: 初始化数据库引擎
print("\n步骤3: 初始化数据库引擎...")
try:
    import database
    database.init_engine()
    
    if database.SessionLocal is None:
        print("  ✗ SessionLocal未初始化")
        sys.exit(1)
    
    print("  ✓ 数据库引擎初始化成功")
except Exception as e:
    print(f"  ✗ 数据库引擎初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤4: 测试数据库连接
print("\n步骤4: 测试数据库连接...")
try:
    db = database.SessionLocal()
    
    # 执行简单查询
    from sqlalchemy import text
    result = db.execute(text("SELECT 1")).scalar()
    
    if result == 1:
        print("  ✓ 数据库连接成功")
    else:
        print("  ✗ 数据库查询返回异常结果")
    
    db.close()
except Exception as e:
    print(f"  ✗ 数据库连接失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤5: 检查表是否存在
print("\n步骤5: 检查数据库表...")
try:
    from sqlalchemy import inspect
    
    inspector = inspect(database.engine)
    tables = inspector.get_table_names()
    
    required_tables = ['debates', 'speeches', 'scores', 'debate_participations', 'users']
    
    for table in required_tables:
        if table in tables:
            print(f"  ✓ 表 '{table}' 存在")
        else:
            print(f"  ✗ 表 '{table}' 不存在")
    
except Exception as e:
    print(f"  ✗ 检查表失败: {e}")

# 步骤6: 统计数据
print("\n步骤6: 统计数据...")
try:
    db = database.SessionLocal()
    
    from sqlalchemy import select, func
    from models.debate import Debate
    from models.speech import Speech
    from models.score import Score
    
    debate_count = db.execute(select(func.count(Debate.id))).scalar()
    speech_count = db.execute(select(func.count(Speech.id))).scalar()
    score_count = db.execute(select(func.count(Score.id))).scalar()
    
    print(f"  辩论数: {debate_count}")
    print(f"  发言数: {speech_count}")
    print(f"  评分数: {score_count}")
    
    db.close()
except Exception as e:
    print(f"  ✗ 统计数据失败: {e}")

print()
print("="*60)
print("测试完成！")
print("="*60)
print()
print("如果所有步骤都显示 ✓，说明数据库配置正确。")
print("现在可以运行评分工具:")
print("  python quick_check_scoring_v2.py")
print()
