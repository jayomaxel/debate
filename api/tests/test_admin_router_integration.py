"""
管理员路由集成测试
测试管理员班级管理端点的功能（需要运行的API服务器）
"""
import requests
import uuid
import json

# API基础URL（根据实际部署调整）
BASE_URL = "http://localhost:7860/api"

# 测试配置
ADMIN_CREDENTIALS = {
    "account": "admin",
    "password": "Admin123!",
    "user_type": "administrator"
}

TEACHER_CREDENTIALS = {
    "account": "teacher001",
    "password": "password123",
    "user_type": "teacher"
}


def login(credentials):
    """登录并获取令牌"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json=credentials
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("data", {}).get("token")
    return None


def test_admin_get_all_classes():
    """测试管理员获取所有班级"""
    print("\n=== 测试：管理员获取所有班级 ===")
    
    # 登录管理员
    admin_token = login(ADMIN_CREDENTIALS)
    if not admin_token:
        print("❌ 管理员登录失败")
        return False
    
    print("✓ 管理员登录成功")
    
    # 获取所有班级
    response = requests.get(
        f"{BASE_URL}/admin/classes",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if response.status_code == 200:
        classes = response.json()
        print(f"✓ 成功获取 {len(classes)} 个班级")
        
        # 验证响应格式
        if classes:
            first_class = classes[0]
            required_fields = ["id", "name", "code", "teacher_id", "teacher_name", "student_count", "created_at"]
            missing_fields = [f for f in required_fields if f not in first_class]
            
            if missing_fields:
                print(f"❌ 缺少必需字段: {missing_fields}")
                return False
            
            print(f"✓ 班级响应包含所有必需字段")
            print(f"  示例班级: {first_class['name']} (教师: {first_class['teacher_name']}, 学生数: {first_class['student_count']})")
        
        return True
    else:
        print(f"❌ 获取班级失败: {response.status_code} - {response.text}")
        return False


def test_teacher_cannot_access_admin_endpoint():
    """测试教师无法访问管理员端点"""
    print("\n=== 测试：教师无法访问管理员端点 ===")
    
    # 登录教师
    teacher_token = login(TEACHER_CREDENTIALS)
    if not teacher_token:
        print("⚠ 教师账号不存在，跳过测试")
        return True
    
    print("✓ 教师登录成功")
    
    # 尝试访问管理员端点
    response = requests.get(
        f"{BASE_URL}/admin/classes",
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    
    if response.status_code == 403:
        print("✓ 教师访问被正确拒绝 (403 Forbidden)")
        return True
    else:
        print(f"❌ 预期403，实际得到: {response.status_code}")
        return False


def test_admin_create_class():
    """测试管理员创建班级"""
    print("\n=== 测试：管理员创建班级 ===")
    
    # 登录管理员
    admin_token = login(ADMIN_CREDENTIALS)
    if not admin_token:
        print("❌ 管理员登录失败")
        return False
    
    # 首先获取一个教师ID
    response = requests.get(
        f"{BASE_URL}/admin/classes",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if response.status_code != 200 or not response.json():
        print("⚠ 没有现有班级，无法获取教师ID，跳过测试")
        return True
    
    teacher_id = response.json()[0]["teacher_id"]
    
    # 创建新班级
    new_class_data = {
        "name": f"测试班级_{uuid.uuid4().hex[:6]}",
        "teacher_id": teacher_id
    }
    
    response = requests.post(
        f"{BASE_URL}/admin/classes",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=new_class_data
    )
    
    if response.status_code == 200:
        created_class = response.json()
        print(f"✓ 成功创建班级: {created_class['name']}")
        print(f"  班级代码: {created_class['code']}")
        print(f"  教师ID: {created_class['teacher_id']}")
        return created_class
    else:
        print(f"❌ 创建班级失败: {response.status_code} - {response.text}")
        return False


def test_admin_update_class(class_data):
    """测试管理员更新班级"""
    print("\n=== 测试：管理员更新班级 ===")
    
    if not class_data:
        print("⚠ 没有班级数据，跳过测试")
        return True
    
    # 登录管理员
    admin_token = login(ADMIN_CREDENTIALS)
    if not admin_token:
        print("❌ 管理员登录失败")
        return False
    
    class_id = class_data["id"]
    new_name = f"更新后的班级_{uuid.uuid4().hex[:6]}"
    
    # 更新班级
    response = requests.put(
        f"{BASE_URL}/admin/classes/{class_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": new_name}
    )
    
    if response.status_code == 200:
        updated_class = response.json()
        if updated_class["name"] == new_name:
            print(f"✓ 成功更新班级名称: {new_name}")
            return updated_class
        else:
            print(f"❌ 班级名称未更新")
            return False
    else:
        print(f"❌ 更新班级失败: {response.status_code} - {response.text}")
        return False


def test_admin_delete_class(class_data):
    """测试管理员删除班级"""
    print("\n=== 测试：管理员删除班级 ===")
    
    if not class_data:
        print("⚠ 没有班级数据，跳过测试")
        return True
    
    # 登录管理员
    admin_token = login(ADMIN_CREDENTIALS)
    if not admin_token:
        print("❌ 管理员登录失败")
        return False
    
    class_id = class_data["id"]
    
    # 删除班级
    response = requests.delete(
        f"{BASE_URL}/admin/classes/{class_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if response.status_code == 200:
        print(f"✓ 成功删除班级: {class_data['name']}")
        
        # 验证班级已删除
        response = requests.get(
            f"{BASE_URL}/admin/classes",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            classes = response.json()
            class_ids = [c["id"] for c in classes]
            if class_id not in class_ids:
                print("✓ 确认班级已从列表中删除")
                return True
            else:
                print("❌ 班级仍在列表中")
                return False
    else:
        print(f"❌ 删除班级失败: {response.status_code} - {response.text}")
        return False


def test_unauthorized_access():
    """测试未认证访问"""
    print("\n=== 测试：未认证访问被拒绝 ===")
    
    response = requests.get(f"{BASE_URL}/admin/classes")
    
    if response.status_code in [401, 403]:
        print(f"✓ 未认证访问被正确拒绝 ({response.status_code})")
        return True
    else:
        print(f"❌ 预期401或403，实际得到: {response.status_code}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("管理员路由集成测试")
    print("=" * 60)
    print(f"API URL: {BASE_URL}")
    print("=" * 60)
    
    results = []
    
    # 测试1: 未认证访问
    results.append(("未认证访问被拒绝", test_unauthorized_access()))
    
    # 测试2: 管理员获取所有班级
    results.append(("管理员获取所有班级", test_admin_get_all_classes()))
    
    # 测试3: 教师无法访问管理员端点
    results.append(("教师访问被拒绝", test_teacher_cannot_access_admin_endpoint()))
    
    # 测试4: 管理员创建班级
    created_class = test_admin_create_class()
    results.append(("管理员创建班级", bool(created_class)))
    
    # 测试5: 管理员更新班级
    if created_class:
        updated_class = test_admin_update_class(created_class)
        results.append(("管理员更新班级", bool(updated_class)))
        
        # 测试6: 管理员删除班级
        results.append(("管理员删除班级", test_admin_delete_class(updated_class or created_class)))
    
    # 打印测试结果摘要
    print("\n" + "=" * 60)
    print("测试结果摘要")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "❌ 失败"
        print(f"{status} - {test_name}")
    
    print("=" * 60)
    print(f"总计: {passed}/{total} 测试通过")
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    try:
        success = run_all_tests()
        exit(0 if success else 1)
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到API服务器")
        print(f"请确保API服务器正在运行: {BASE_URL}")
        exit(1)
    except Exception as e:
        print(f"\n❌ 测试执行出错: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
