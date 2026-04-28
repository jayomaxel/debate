"""
检查配置状态
快速检查数据库中的配置和用户数据
"""
import sys
import logging
from sqlalchemy import select

sys.path.insert(0, '.')

from database import get_db, init_engine, init_db
from models.config import ModelConfig, CozeConfig
from models.user import User
from models.class_model import Class

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_config_status():
    """检查配置状态"""
    # 初始化数据库
    init_engine()
    init_db()
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        print("\n" + "="*60)
        print("配置和数据状态检查")
        print("="*60 + "\n")
        
        # 检查模型配置
        print("【模型配置】")
        model_config = db.execute(
            select(ModelConfig).limit(1)
        ).scalar_one_or_none()
        
        if model_config:
            print(f"✓ 模型配置已存在")
            print(f"  - ID: {model_config.id}")
            print(f"  - 模型名称: {model_config.model_name}")
            print(f"  - API端点: {model_config.api_endpoint}")
            print(f"  - API密钥: {'已设置' if model_config.api_key else '未设置'}")
            print(f"  - 温度: {model_config.temperature}")
            print(f"  - 最大令牌数: {model_config.max_tokens}")
            print(f"  - 创建时间: {model_config.created_at}")
        else:
            print("✗ 模型配置不存在")
            print("  建议：重启后端服务或运行 python api/init_config.py")
        
        print()
        
        # 检查Coze配置
        print("【Coze配置】")
        coze_config = db.execute(
            select(CozeConfig).limit(1)
        ).scalar_one_or_none()
        
        if coze_config:
            print(f"✓ Coze配置已存在")
            print(f"  - ID: {coze_config.id}")
            print(f"  - 代理ID: {coze_config.agent_id if coze_config.agent_id else '未设置'}")
            print(f"  - API令牌: {'已设置' if coze_config.api_token else '未设置'}")
            print(f"  - 创建时间: {coze_config.created_at}")
        else:
            print("✗ Coze配置不存在")
            print("  建议：重启后端服务或运行 python api/init_config.py")
        
        print()
        
        # 检查用户
        print("【用户统计】")
        
        # 管理员
        admin_count = db.execute(
            select(User).where(User.user_type == "administrator")
        ).scalars().all()
        print(f"管理员: {len(admin_count)} 个")
        
        # 教师
        teachers = db.execute(
            select(User).where(User.user_type == "teacher")
        ).scalars().all()
        print(f"教师: {len(teachers)} 个")
        if teachers:
            for teacher in teachers:
                print(f"  - {teacher.name} ({teacher.email})")
        else:
            print("  ⚠ 没有教师用户")
            print("  建议：通过注册流程创建教师账号")
        
        # 学生
        student_count = db.execute(
            select(User).where(User.user_type == "student")
        ).scalars().all()
        print(f"学生: {len(student_count)} 个")
        
        print()
        
        # 检查班级
        print("【班级统计】")
        classes = db.execute(select(Class)).scalars().all()
        print(f"班级总数: {len(classes)} 个")
        if classes:
            for cls in classes:
                teacher = db.execute(
                    select(User).where(User.id == cls.teacher_id)
                ).scalar_one_or_none()
                teacher_name = teacher.name if teacher else "未知"
                print(f"  - {cls.name} (代码: {cls.code}, 教师: {teacher_name})")
        
        print()
        print("="*60)
        print("检查完成")
        print("="*60 + "\n")
        
        # 给出建议
        if not model_config or not coze_config:
            print("⚠ 建议操作：")
            print("  1. 重启后端服务（会自动初始化配置）")
            print("  2. 或运行：python api/init_config.py")
            print()
        
        if len(teachers) == 0:
            print("⚠ 建议操作：")
            print("  1. 退出管理员账号")
            print("  2. 在登录页面选择教师注册")
            print("  3. 完成注册后重新使用管理员账号登录")
            print()
        
    except Exception as e:
        logger.error(f"检查失败: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    check_config_status()
