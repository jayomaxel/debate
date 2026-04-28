"""
测试API启动
"""
import sys
print("Testing API setup...")

try:
    from main import app
    print("✓ FastAPI app imported successfully")
    
    # 检查路由
    routes = [route.path for route in app.routes]
    print(f"✓ Registered routes: {len(routes)}")
    
    auth_routes = [r for r in routes if r.startswith("/api/auth")]
    print(f"✓ Auth routes: {len(auth_routes)}")
    for route in auth_routes:
        print(f"  - {route}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n✓ API setup test completed!")
