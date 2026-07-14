# 候选辩题前端接口合同

本文档用于前端 D 对接教师端“教学设计 -> 候选辩题 -> 建赛回填 -> 推荐分析看板”链路。

## 接口清单

### 1. 推荐历史
- `GET /api/teacher/classes/{class_id}/topic-recommendations`
- 用途：
  - 推荐历史列表
  - 时间筛选后的历史列表
  - 看板中的最近推荐回显
- 查询参数：
  - `limit`
  - `date_from`
  - `date_to`
- 示例：
  - [topic_recommendation_history.json](/D:/Afile/debate/docs/api_contract_examples/topic_recommendation_history.json)

### 2. 推荐详情
- `GET /api/teacher/topic-recommendations/{run_id}`
- 用途：
  - 单次推荐详情页
  - 候选题展开详情
  - 候选题采用统计明细
- 示例：
  - [topic_recommendation_detail.json](/D:/Afile/debate/docs/api_contract_examples/topic_recommendation_detail.json)

### 3. 班级聚合统计
- `GET /api/teacher/classes/{class_id}/topic-recommendations/analytics`
- 用途：
  - 班级维度推荐效果总览
  - 时间范围统计
  - 版本分布与版本对比摘要
- 查询参数：
  - `date_from`
  - `date_to`
- 示例：
  - [topic_recommendation_analytics.json](/D:/Afile/debate/docs/api_contract_examples/topic_recommendation_analytics.json)

### 4. 教师看板
- `GET /api/teacher/classes/{class_id}/topic-recommendations/dashboard`
- 用途：
  - 教师 dashboard 主接口
  - 汇总统计、质量统计、时间线、最近推荐、排行榜、观察名单
- 查询参数：
  - `recent_limit`
  - `leaderboard_limit`
  - `observation_limit`
  - `date_from`
  - `date_to`
- 示例：
  - [topic_recommendation_dashboard.json](/D:/Afile/debate/docs/api_contract_examples/topic_recommendation_dashboard.json)

### 5. 版本对比摘要
- `GET /api/teacher/classes/{class_id}/topic-recommendations/version-comparison`
- 用途：
  - 教学设计版本切换后的轻量对比摘要
  - 版本对比弹层
- 查询参数：
  - `current_version_id`
  - `previous_version_id`
  - `date_from`
  - `date_to`
- 示例：
  - [topic_recommendation_version_comparison.json](/D:/Afile/debate/docs/api_contract_examples/topic_recommendation_version_comparison.json)

## 字段稳定性说明

以下字段已视为前后端稳定合同：

### 历史项稳定字段
- `run_id`
- `status`
- `teaching_design_version_id`
- `mode`
- `generation_source`
- `generation_quality`
- `candidate_count`
- `candidate_topics`
- `adoption_summary`

### 详情页稳定字段
- `run_id`
- `status`
- `teaching_design_status`
- `teaching_design_version_id`
- `mode`
- `generation_source`
- `generation_quality`
- `retry_count`
- `warnings`
- `generated_at`
- `candidates[*].candidate_id`
- `candidates[*].topic_text`
- `candidates[*].mapped_course_objectives`
- `candidates[*].mapped_knowledge_points`
- `candidates[*].recommended_classroom_scene`
- `candidates[*].debatability_reason`
- `candidates[*].difficulty_level`
- `candidates[*].recommendation_reason`
- `candidates[*].evidence_basis`
- `candidates[*].adoption_stats`

### analytics 稳定字段
- `total_runs`
- `total_candidates`
- `adopted_run_count`
- `adopted_candidate_count`
- `total_adoptions`
- `direct_adoptions`
- `edited_adoptions`
- `debate_adoptions`
- `reservation_adoptions`
- `run_adoption_rate`
- `candidate_adoption_rate`
- `average_candidates_per_run`
- `quality_counts`
- `quality_rates`
- `provider_counts`
- `status_counts`
- `version_breakdown`
- `version_comparison_summary`

### dashboard 稳定字段
- `summary`
- `quality`
- `timeline`
- `leaderboards`
- `observations`
- `recent_runs`

### 版本对比稳定字段
- `current_version_id`
- `previous_version_id`
- `version_comparison_summary`
- `version_breakdown`

## 前端渲染建议

### dashboard
- `summary`：
  - 大数字卡片
- `quality`：
  - 质量状态分布
  - provider 分布
  - 版本分布表
- `timeline`：
  - 最近生成时间
  - 最近采用时间
  - 最近一次推荐
  - 最近一次被采用推荐
- `leaderboards.top_adopted_candidates`：
  - 热门候选题榜
- `leaderboards.top_edited_candidates`：
  - 高频编辑后采用榜
- `observations.high_quality_low_adoption_candidates`：
  - 高质量但未采用
- `observations.high_quality_edited_only_candidates`：
  - 高质量但只在编辑后采用

### 版本对比弹层
- `version_comparison_summary.current_version`
- `version_comparison_summary.previous_version`
- `version_comparison_summary.delta`

## 错误处理约定

- 参数非法：
  - 返回 `400`
- 无班级权限：
  - 返回 `403`
- 推荐记录不存在：
  - 详情接口返回 `404`

## 备注

- 本文档只约束字段合同，不约束前端具体 UI 结构。
- 若后端后续新增字段，优先走“只新增不改名”的方式，避免破坏 D 的联调。
