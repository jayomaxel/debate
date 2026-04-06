#!/bin/bash

# 辩论评分检查和修复示例脚本
# 使用方法: ./example_check_and_fix.sh [debate_id]

echo "========================================="
echo "辩论评分检查和修复工具"
echo "========================================="
echo ""

# 检查是否提供了debate_id参数
if [ -z "$1" ]; then
    echo "未提供辩论ID，将检查最近的辩论..."
    echo ""
    python quick_check_scoring.py
    echo ""
    echo "如果发现问题，请使用以下命令修复:"
    echo "  ./example_check_and_fix.sh <debate_id>"
    exit 0
fi

DEBATE_ID=$1

echo "辩论ID: $DEBATE_ID"
echo ""

# 步骤1: 快速检查
echo "步骤1: 快速检查评分状态..."
echo "========================================="
python quick_check_scoring.py $DEBATE_ID
echo ""

# 询问是否继续
read -p "是否需要详细诊断? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 步骤2: 详细诊断
    echo ""
    echo "步骤2: 详细诊断..."
    echo "========================================="
    python test_scoring_debug.py $DEBATE_ID
    echo ""
fi

# 询问是否修复
read -p "是否需要修复评分? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 询问是否强制重新评分
    read -p "是否强制重新评分（删除现有评分）? (y/n): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 步骤3: 强制重新评分
        echo ""
        echo "步骤3: 强制重新评分..."
        echo "========================================="
        python fix_scoring_issue.py $DEBATE_ID --force
    else
        # 步骤3: 修复评分
        echo ""
        echo "步骤3: 修复评分（只评分未评分的发言）..."
        echo "========================================="
        python fix_scoring_issue.py $DEBATE_ID
    fi
    
    echo ""
    echo "步骤4: 验证修复结果..."
    echo "========================================="
    python quick_check_scoring.py $DEBATE_ID
fi

echo ""
echo "========================================="
echo "完成！"
echo "========================================="
