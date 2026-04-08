#!/bin/bash
# WeasyPrint安装脚本（Linux/macOS）

echo "================================"
echo "WeasyPrint 安装脚本"
echo "================================"
echo ""

# 检测操作系统
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

echo "检测到操作系统: ${MACHINE}"
echo ""

# 安装系统依赖
if [ "${MACHINE}" = "Linux" ]; then
    echo "正在安装Linux系统依赖..."
    
    # 检测Linux发行版
    if [ -f /etc/debian_version ]; then
        echo "检测到Debian/Ubuntu系统"
        sudo apt-get update
        sudo apt-get install -y \
            libpango-1.0-0 \
            libpangocairo-1.0-0 \
            libgdk-pixbuf2.0-0 \
            libffi-dev \
            shared-mime-info \
            fonts-noto-cjk \
            fonts-wqy-microhei
        echo "✓ 系统依赖安装完成"
    elif [ -f /etc/redhat-release ]; then
        echo "检测到CentOS/RHEL系统"
        sudo yum install -y \
            pango \
            gdk-pixbuf2 \
            libffi-devel \
            wqy-microhei-fonts
        echo "✓ 系统依赖安装完成"
    else
        echo "⚠ 未识别的Linux发行版，请手动安装依赖"
        echo "参考: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
    fi
    
elif [ "${MACHINE}" = "Mac" ]; then
    echo "正在安装macOS系统依赖..."
    
    # 检查是否安装了Homebrew
    if ! command -v brew &> /dev/null; then
        echo "❌ 未检测到Homebrew，请先安装Homebrew"
        echo "访问: https://brew.sh/"
        exit 1
    fi
    
    brew install pango gdk-pixbuf libffi
    echo "✓ 系统依赖安装完成"
    
else
    echo "❌ 不支持的操作系统: ${MACHINE}"
    exit 1
fi

echo ""
echo "正在安装Python依赖..."

# 安装Python包
pip install weasyprint>=68.1 markdown>=3.5.0 pygments>=2.17.0

if [ $? -eq 0 ]; then
    echo "✓ Python依赖安装完成"
else
    echo "❌ Python依赖安装失败"
    exit 1
fi

echo ""
echo "正在验证安装..."

# 验证安装
python3 -c "import weasyprint; print('WeasyPrint版本:', weasyprint.__version__)"
python3 -c "import markdown; print('Markdown版本:', markdown.__version__)"
python3 -c "import pygments; print('Pygments版本:', pygments.__version__)"

if [ $? -eq 0 ]; then
    echo ""
    echo "================================"
    echo "✓ 安装成功！"
    echo "================================"
    echo ""
    echo "下一步："
    echo "1. 运行测试: python test_markdown_pdf.py"
    echo "2. 查看文档: docs/WeasyPrint使用说明.md"
    echo ""
else
    echo ""
    echo "❌ 验证失败，请检查错误信息"
    exit 1
fi
