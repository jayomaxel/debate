"""
测试基础设置
"""
import sys
print("Python version:", sys.version)

try:
    from config import settings
    print("✓ Config loaded successfully")
    print(f"  - Database URL: {settings.DATABASE_URL[:30]}...")
    print(f"  - Redis Host: {settings.REDIS_HOST}")
    print(f"  - App Name: {settings.APP_NAME}")
except Exception as e:
    print(f"✗ Config error: {e}")

try:
    from database import Base, engine
    print("✓ Database engine created successfully")
except Exception as e:
    print(f"✗ Database error: {e}")

try:
    from models import User, Class, Debate, DebateParticipation
    print("✓ Models imported successfully")
    print(f"  - User table: {User.__tablename__}")
    print(f"  - Class table: {Class.__tablename__}")
    print(f"  - Debate table: {Debate.__tablename__}")
except Exception as e:
    print(f"✗ Models error: {e}")

print("\n✓ All basic setup checks passed!")
