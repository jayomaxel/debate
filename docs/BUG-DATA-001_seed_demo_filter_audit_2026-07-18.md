# BUG-DATA-001：能力图与排行 seed/demo 数据过滤专项核对

- 核对日期：2026-07-18
- 优先级：P1
- 归属：后端 / 数据
- 核对范围：学生能力图、成长趋势、同班排行、班级平均值，以及相关数据模型、种子脚本和测试
- 最终结论：**问题已确认。当前不存在可证明“能力图/排行统一排除 seed/demo 数据”的模型字段、公共过滤器或接口级过滤条件。只要演示脚本与正式系统共用数据库，演示评分就会进入能力图、成长趋势、班级平均和排行。**

## 1. 用户可见链路

学生端“成长 / 同班对比”页面直接调用以下接口：

| 页面数据 | 前端调用 | 后端入口 | 服务实现 |
| --- | --- | --- | --- |
| 个人统计及五维能力 | `StudentService.getAnalytics()` | `GET /api/student/analytics` | `AnalyticsService.get_student_statistics()` |
| 成长趋势 | `StudentService.getGrowthTrend()` | `GET /api/student/analytics/growth` | `AnalyticsService.get_growth_trend()` |
| 能力雷达、班级平均、排行 | `StudentService.getClassComparison()` | `GET /api/student/comparison/class` | `ComparisonService.get_class_comparison()` |

页面上的“五维能力对比（我 vs 班级平均）”、班级排名、领先百分位、当前指标和 Top 排行均直接使用 `/api/student/comparison/class` 返回的数据，不存在前端二次排除逻辑。

## 2. 查询条件专项核对

### 2.1 个人能力图：未排除 seed/demo，且未限制正式完成辩论

`AnalyticsService.get_student_statistics()` 的平均分和五维能力查询只连接 `Score -> DebateParticipation`，过滤条件只有：

```python
DebateParticipation.user_id == student_id
```

查询没有连接 `Debate`，因此没有 `completed`、正式数据来源、非演示数据、有效评分或非回退评分等限制。学生名下任何 `Score` 行都会进入个人平均分与能力图。

### 2.2 成长趋势：未排除 seed/demo

`AnalyticsService.get_growth_trend()` 连接了 `Debate`、`DebateParticipation` 和 `Score`，但唯一业务过滤条件仍是学生 ID，没有限制辩论状态或数据来源。种子脚本产生的评分会出现在成长曲线中。

### 2.3 班级排行与雷达图：仅过滤 completed，无法排除演示数据

`ComparisonService.get_class_comparison()` 的有效条件为：

```python
User.user_type == "student"
User.class_id == student.class_id
Debate.status == "completed"
```

这里没有 seed/demo 排除条件。`completed` 只表示辩论状态，不表示数据真实性；三个演示脚本都会创建或覆盖 `completed` 辩论，因此演示数据满足当前排行条件。

### 2.4 班级平均服务：同样未排除 seed/demo

`AnalyticsService.get_average_score()` 只按 `User.class_id` 过滤，没有连接 `Debate`，也没有正式数据来源条件。因此如果该服务后续重新暴露或被内部调用，也会受到同样污染。

## 3. 数据模型核对

核对 `User`、`Debate`、`DebateParticipation`、`Score` 及 Alembic 迁移后确认：

- `Debate` 没有 `is_demo`、`is_seed`、`environment` 或等价来源字段。
- `Score` 没有数据来源、有效性、是否回退或演示标记。
- `User` 没有演示账号标记。
- `DebateParticipation.role_reason` 虽被部分脚本写入 `portrait_seed`、`fake_report_seed`、`full_flow_demo`，但它是辩位分配原因，不是稳定的数据治理字段，查询也未使用它。
- 其他模型中的 `source/sample_source` 属于辩位学习或教学设计，不适用于能力统计查询。

结论：**当前数据库结构本身无法提供可靠、统一、可索引的数据排除条件。** 依赖标题、描述、账号名或 `role_reason` 做模糊过滤不具备完整性，也不应作为正式修复方案。

## 4. 演示脚本进入统计的证据

### `seed_fake_debate_report.py`

- 将辩论写成 `status="completed"`。
- 写入真实的 `DebateParticipation`、`Speech` 和 `Score` 表。
- 仅在描述中写“演示链路用假数据”，并将 `role_reason` 写成 `fake_report_seed`。

### `seed_student_ability_portrait.py`

- 将辩论写成 `status="completed"`。
- 直接为学生写入 `Score`。
- 仅通过描述和 `role_reason="portrait_seed"` 表示测试用途。

### `seed_full_flow_demo.py`

- 先创建完整流程数据，再调用 `seed_fake_bundle()` 为 completed 辩论写入评分。
- `role_reason="full_flow_demo"`，但统计查询不读取该字段。

只要这些脚本指向正式数据库或与正式班级、学生共用数据库，模拟分数就会被当作正常分数统计。

## 5. 测试覆盖核对

现有 `api/tests/test_comparison_service.py` 测试通过，但它：

- 使用 `MagicMock` 模拟查询结果；
- 只验证班级平均按学生等权计算；
- 没有写入正式与 demo 两组数据；
- 没有断言 SQL 查询包含统一来源过滤；
- 没有覆盖 `/api/student/analytics` 和 `/api/student/analytics/growth` 的 seed/demo 排除。

`api/tests/test_analytics.py` 主要验证服务可以导入并打印接口清单，不执行真实统计查询。

本次复跑 `python -m pytest api/tests/test_comparison_service.py -q` 的结果为 `1 passed`。该结果只能证明原有等权平均逻辑未报错，**不能作为演示数据已排除的证据**。

## 6. 风险判定

| 风险对象 | 当前风险 | 结果 |
| --- | --- | --- |
| 个人五维能力图 | 高 | 演示评分直接改变五维均值 |
| 成长趋势 | 高 | 演示辩论作为真实历史节点展示 |
| 班级排行 | 高 | 演示高分或低分改变名次与百分位 |
| 班级平均 | 高 | 演示数据改变对比基线 |
| 教学解释与报告可信度 | 高 | 页面无法说明统计样本是否为正式数据 |

该问题符合 P1：不一定阻断系统运行，但会直接破坏能力分析和排行的可信度。

## 7. 建议修复方案

### 7.1 建立数据库级来源标记

优先在 `Debate` 增加非空、可索引字段：

```text
data_origin = official | demo | seed | test
```

默认值为 `official`，所有种子脚本必须显式写 `demo/seed/test`。如需更细评分治理，再为 `Score` 增加 `is_valid/is_fallback/source`。

### 7.2 建立统一查询作用域

提供公共过滤器或查询构造函数，例如 `apply_official_scoring_scope(query)`，至少统一约束：

- `Debate.status == "completed"`
- `Debate.data_origin == "official"`
- 有效且非回退评分（字段补齐后）
- 明确每个学生、每场辩论采用哪一条汇总评分，避免发言行与汇总行重复加权

必须接入：

1. `get_student_statistics()`
2. `get_growth_trend()`
3. `get_class_comparison()`
4. `get_average_score()`
5. 后续所有能力图、排行、成长、成就和教师统计入口

### 7.3 历史数据治理

- 迁移不能盲目把所有旧数据标成 `official`。
- 先按已知脚本产生的辩论 ID、描述、`role_reason` 和测试账号生成待确认清单。
- 经人工确认后批量回填 `data_origin`。
- 生产库与开发/演示库分离，种子脚本默认拒绝连接生产环境。

## 8. 验收标准

- 模型和迁移中存在明确的来源字段及索引。
- 三个种子脚本显式写入非正式来源。
- 能力图、成长趋势、班级平均和排行共享同一个正式评分过滤器。
- 集成测试同时插入一场 `official` 和一场 `demo/seed` 辩论，断言所有相关接口只统计 `official`。
- 测试覆盖 demo 分数高于和低于正式分数两种情况，确保名次、平均值、样本量、五维分数均不受影响。
- 接口返回有效样本量，页面能够说明统计口径。
- 对现有数据库执行审计 SQL 后，能够列出并隔离历史演示数据。

## 9. 汇报摘要

> BUG-DATA-001 经专项核对已确认。能力图、成长趋势和班级排行均直接聚合 `scores`；现有数据模型没有统一的 demo/seed 来源字段，排行接口虽然过滤 `completed`，但种子脚本同样把演示辩论写成 `completed`，所以无法排除。现有测试只验证等权平均，没有验证数据来源隔离。建议以 `Debate.data_origin` 加统一 official scoring scope 的方式修复，并补真实数据库集成测试及历史数据清理。
