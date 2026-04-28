"""
测试所有API路由
"""
from main import app

print("=" * 60)
print("辩论教学系统 - API路由列表")
print("=" * 60)

routes_by_tag = {}

for route in app.routes:
    if hasattr(route, 'methods') and hasattr(route, 'path'):
        methods = ', '.join(route.methods)
        path = route.path
        tags = getattr(route, 'tags', ['未分类'])
        
        for tag in tags:
            if tag not in routes_by_tag:
                routes_by_tag[tag] = []
            routes_by_tag[tag].append((methods, path))

for tag, routes in sorted(routes_by_tag.items()):
    print(f"\n【{tag}】")
    for methods, path in sorted(routes, key=lambda x: x[1]):
        print(f"  {methods:20} {path}")

print("\n" + "=" * 60)
print(f"总计: {len([r for r in app.routes if hasattr(r, 'methods')])} 个API端点")
print("=" * 60)
