"""
批量更新日志导入的辅助脚本
将所有使用 logging.getLogger(__name__) 的文件更新为使用集中式日志配置
"""

import re
from pathlib import Path


def update_file_logging(file_path: Path) -> bool:
    """
    更新单个文件的日志导入

    Returns:
        是否进行了修改
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # 替换 import logging
        if (
            "import logging" in content
            and "from logging_config import get_logger" not in content
        ):
            # 移除 import logging
            content = re.sub(r"^import logging\n", "", content, flags=re.MULTILINE)

            # 在合适的位置添加 from logging_config import get_logger
            # 通常在其他导入之后
            if "from config import settings" in content:
                content = content.replace(
                    "from config import settings",
                    "from config import settings\nfrom logging_config import get_logger",
                )
            elif "from database import" in content:
                content = content.replace(
                    "from database import",
                    "from logging_config import get_logger\nfrom database import",
                )
            else:
                # 在第一个 from 导入之前添加
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if line.startswith("from "):
                        lines.insert(i, "from logging_config import get_logger")
                        break
                content = "\n".join(lines)

        # 替换 logger = logging.getLogger(__name__)
        content = re.sub(
            r"logger = logging\.getLogger\(__name__\)",
            "logger = get_logger(__name__)",
            content,
        )

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✓ 已更新: {file_path}")
            return True
        else:
            return False

    except Exception as e:
        print(f"✗ 更新失败 {file_path}: {e}")
        return False


def main():
    """主函数"""
    api_dir = Path(__file__).parent

    # 需要更新的文件模式
    patterns = [
        "routers/**/*.py",
        "services/**/*.py",
        "agents/**/*.py",
        "utils/**/*.py",
        "middleware/**/*.py",
    ]

    updated_count = 0

    for pattern in patterns:
        for file_path in api_dir.glob(pattern):
            if file_path.name == "__pycache__":
                continue
            if update_file_logging(file_path):
                updated_count += 1

    print(f"\n总计更新了 {updated_count} 个文件")
    print(f"所有日志将写入: {api_dir / 'logs' / 'app.log'}")


if __name__ == "__main__":
    main()
