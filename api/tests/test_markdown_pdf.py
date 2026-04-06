"""
测试Markdown转PDF功能
"""
import asyncio
from pathlib import Path
from utils.markdown_to_pdf import markdown_to_pdf

# 测试Markdown内容
TEST_MARKDOWN = """
# ⚔️ 辩论对局深度复盘报告

> **📌 辩题**：人工智能的发展利大于弊
> **🕒 时间**：2026年2月9日
> **📢 裁判综述**：本场辩论双方表现精彩，正方在论证结构上更为严密，反方在数据引用上略显不足。

## 🤖 1. 反方：AI 辩手评估

| 维度 | 得分 | 评分原因 |
| :--- | :---: | :--- |
| **攻防压制力** (40分) | 32/40 | 在第二轮成功质疑了对方关于就业数据的引用，但在第三轮未能有效回应关于教育领域的反驳 |
| **论证严密性** (40分) | 35/40 | 整体逻辑自洽，引用了多项研究数据，但在隐私保护论点上存在轻微漏洞 |
| **辩风与规范** (20分) | 18/20 | 语言专业简练，符合辩论规范，偶有重复论述 |

> **🤖 AI 总分**：85 / 100

## 🧑 2. 正方：学生辩手评估

| 维度 | 得分 | 评分原因 |
| :--- | :---: | :--- |
| **逻辑构建** (30分) | 26/30 | 立论清晰，采用了Claim+Data+Warrant结构，但在医疗领域的论证略显单薄 |
| **临场反驳** (30分) | 24/30 | 正面回应了大部分质询，但在第四轮对于伦理问题的回应有所回避 |
| **知识运用** (20分) | 17/20 | 引用数据基本准确，但有一处关于失业率的数据存在时效性问题 |
| **表达感染力** (20分) | 18/20 | 语言流畅，富有感染力，能够有效传达观点 |

> **🧑 学生总分**：85 / 100

## 💡 3. 赛后复盘与建议

### 🌟 双方高光时刻

- **AI**："技术本身是中性的，关键在于我们如何使用它。就像火可以取暖也可以伤人，人工智能的价值取决于人类的选择。"
- **学生**："我们不能因为担心未来的风险而放弃当下的进步，历史告诉我们，每一次技术革命都伴随着阵痛，但最终都推动了人类文明的进步。"

### 🚀 改进建议

1. **加强数据时效性**：建议在引用统计数据时，注明数据来源和时间，确保数据的准确性和时效性
2. **深化论证层次**：在核心论点上可以进一步展开，提供更多层次的论证支撑
3. **提升反驳技巧**：面对对方质询时，避免回避问题，应正面回应并转化为己方优势
4. **优化时间分配**：合理分配各环节时间，避免在某些论点上过度展开而忽略其他重要论点

## 📊 4. 详细发言记录

### 立论阶段

**正方一辩（学生）**：
人工智能的发展为人类社会带来了前所未有的机遇。首先，在医疗领域，AI辅助诊断系统已经能够识别早期癌症，准确率超过95%...

**反方一辩（AI）**：
我方并不否认人工智能带来的便利，但我们必须正视其潜在风险。数据显示，到2030年，AI可能导致全球8亿个工作岗位消失...

### 代码示例

```python
# AI模型训练示例
import tensorflow as tf

model = tf.keras.Sequential([
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(10, activation='softmax')
])

model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)
```

### 关键数据对比

| 指标 | 2020年 | 2025年 | 增长率 |
|------|--------|--------|--------|
| AI市场规模（亿美元） | 500 | 1900 | 280% |
| AI相关就业岗位（万个） | 230 | 580 | 152% |
| AI专利申请数（万件） | 12 | 45 | 275% |

---

**报告生成时间**：2026年2月9日 14:30:00
**系统版本**：v2.0.0
"""


async def test_markdown_to_pdf():
    """测试Markdown转PDF转换"""
    print("开始测试Markdown转PDF转换...")
    
    try:
        # 测试1: 生成PDF文件
        output_path = Path("test_output/debate_report.pdf")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"\n测试1: 生成PDF文件到 {output_path}")
        pdf_bytes = await markdown_to_pdf(
            markdown_text=TEST_MARKDOWN,
            output_path=output_path,
            title="辩论报告测试",
            meta_info={
                "辩题": "人工智能的发展利大于弊",
                "开始时间": "2026-02-09 14:00:00",
                "结束时间": "2026-02-09 14:30:00",
                "持续时间": "30 分钟"
            },
            syntax_style="github"
        )
        
        print(f"✓ PDF生成成功！文件大小: {len(pdf_bytes)} 字节")
        print(f"✓ 文件已保存到: {output_path.absolute()}")
        
        # 测试2: 只返回字节流（不保存文件）
        print("\n测试2: 生成PDF字节流（不保存文件）")
        pdf_bytes2 = await markdown_to_pdf(
            markdown_text=TEST_MARKDOWN,
            title="辩论报告测试（字节流）",
            syntax_style="monokai"  # 测试不同的代码高亮风格
        )
        
        print(f"✓ PDF字节流生成成功！大小: {len(pdf_bytes2)} 字节")
        
        # 测试3: 简单的Markdown
        print("\n测试3: 简单Markdown内容")
        simple_md = """
# 简单测试

这是一个**简单**的测试文档。

## 列表测试

- 项目1
- 项目2
- 项目3

## 代码测试

```python
def hello():
    print("Hello, World!")
```

完成！
"""
        simple_output = Path("test_output/simple_report.pdf")
        await markdown_to_pdf(
            markdown_text=simple_md,
            output_path=simple_output,
            title="简单测试"
        )
        
        print(f"✓ 简单PDF生成成功！文件已保存到: {simple_output.absolute()}")
        
        print("\n" + "="*50)
        print("所有测试通过！✓")
        print("="*50)
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_markdown_to_pdf())
