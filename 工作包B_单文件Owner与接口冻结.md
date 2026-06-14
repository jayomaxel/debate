# 工作包B：教学业务编排、画像与辩位分配

## 1. 负责人定位
- 角色：教学业务后端工程师。
- 核心目标：负责教师/学生业务路由、建赛/预约主流程、候选辩题编排、学生画像、AI 辩位分配、报告/回放/教师复盘业务聚合。
- 不负责：AI 评分内核、安全认证、教学设计文件处理、资料摘要底层服务、前端页面。

## 2. 单文件 Owner

### B 可修改文件
- `api/routers/teacher.py`
- `api/routers/student.py`
- `api/services/debate_service.py`
- `api/services/assessment_service.py`
- `api/services/analytics_service.py`
- `api/models/assessment.py`
- `api/tests/test_debate_config_meta.py`
- `api/tests/test_topic_recommendation.py`
- `api/tests/test_assessment_profile.py`
- `api/tests/test_role_assignment.py`
- `api/tests/test_teacher_student_contracts.py`

### B 禁止修改文件
- `api/agents/*`
- `api/services/report_service.py`
- `api/services/scoring_service.py`
- `api/services/prompt_pack_service.py`
- `api/services/rubric_service.py`
- `api/services/score_validation_service.py`
- `api/services/teaching_design_service.py`
- `api/services/document_service.py`
- `api/services/knowledge_base.py`
- `api/models/class_teaching_design.py`
- `api/models/document.py`
- `api/routers/auth.py`
- `api/routers/websocket.py`
- `api/utils/security.py`
- `api/main.py`
- `web/src/**`
- `web/index.html`
- `web/package.json`

## 3. 什么需要等谁做完

### 可以立即开始
- `DebateConfigMeta` 结构设计。
- 学生画像标准字段和旧字段映射。
- 辩位能力模型、辩位适配分、重复辩位惩罚策略。
- 教师/学生路由中的接口壳和 mock 响应。

### 必须等 A 冻结后再接入
- `DebateReportSchema`
- `ReportMeta`
- `ParticipantScoreProfileSchema`
- `ScoreEvidenceSchema`

用途：
- B 的报告详情、教师复盘、报告重算接口需要透传 A 的报告结构。

### 必须等 E 冻结后再接入
- `TeachingDesignSchema`
- `TopicSourceContext`
- `SupportDocumentSummarySchema`
- `KnowledgeSnippetSchema`

用途：
- B 的候选辩题推荐需要读取教学设计抽取结果和资料摘要。
- B 不直接处理文档解析、摘要、标签底层逻辑。

### 必须等 C 冻结后再接入
- `AuthSessionContract`
- `UploadGuardErrorContract`
- `AuditLogEventContract`

用途：
- 教师创建、报告重算、上传类业务需要权限和审计。

### D 需要等待 B
- D 的教师端建赛、候选辩题、辩位确认、学生画像页面必须等待 B 的业务接口冻结。

## 4. 固定接口，冻结后不能随意改

### DebateConfigMeta
```json
{
  "mode": "competition | teaching",
  "role_assignment_mode": "strength_first | growth_first",
  "assignment_policy": "ai_auto_assign | ai_recommend_then_confirm",
  "rounds": 0,
  "knowledge_points": ["string"],
  "objective": ["string"],
  "evaluation_focus": ["string"],
  "forbidden_moves": ["string"],
  "support_document_ids": ["string"],
  "domain_pack_id": "string",
  "teaching_design_version_id": "string",
  "activity_focus": {
    "chapter_focus": "string",
    "training_focus": "string",
    "classroom_scene": "string"
  }
}
```

### TopicRecommendationResult
```json
{
  "teaching_design_version_id": "string",
  "activity_focus": {},
  "recommendations": [
    {
      "topic_id": "string",
      "topic_text": "string",
      "mapped_course_objectives": ["string"],
      "mapped_knowledge_points": ["string"],
      "recommended_classroom_scene": "string",
      "debatability_reason": "string",
      "difficulty_level": "foundation | standard | advanced",
      "recommendation_reason": "string",
      "source_basis": ["string"]
    }
  ]
}
```

### AssessmentResultSchema
```json
{
  "student_id": "string",
  "self_assessment_profile": {},
  "performance_profile": {},
  "participation_profile": {},
  "recommended_role": "debater_1 | debater_2 | debater_3 | debater_4",
  "role_assignment_basis": {
    "self_reported": [],
    "history_scores": [],
    "speech_stats": [],
    "analysis_basis": "self_assessment_only | self_assessment_plus_history | history_enhanced | fallback_rule_only"
  }
}
```

### RoleAssignmentResult
```json
{
  "assignment_id": "string",
  "mode": "competition | teaching",
  "role_assignment_mode": "strength_first | growth_first",
  "assignment_policy": "ai_auto_assign | ai_recommend_then_confirm",
  "results": [
    {
      "student_id": "string",
      "assigned_role": "debater_1 | debater_2 | debater_3 | debater_4",
      "assignment_source": "model | rule | fallback",
      "assignment_reason": "string",
      "dimension_contribution": {},
      "historical_role_distribution": {},
      "repeat_role_penalty_applied": true,
      "teacher_override": false,
      "data_basis": "self_assessment_only | self_assessment_plus_history | history_enhanced | fallback_rule_only"
    }
  ]
}
```

### TeachingSummaryResult
```json
{
  "debate_id": "string",
  "common_issues": [],
  "turning_points": [],
  "next_training_focus": [],
  "report_quality": "validated | repaired | fallback | partial",
  "generated_at": "ISO-8601 datetime"
}
```

## 5. 需要做的功能
- 教师创建/预约辩论时支持结构化配置。
- 候选辩题推荐由 B 编排：读取 E 的教学设计和资料摘要，再调用 A 或通用 LLM 生成候选结果。
- 学生画像统一为标准维度，同时兼容旧字段。
- AI 辩位分配支持 `strength_first` 和 `growth_first`。
- 辩位分配必须返回解释、适配分、数据依据和重复辩位惩罚。
- 教师可以确认或覆盖 AI 分配。
- 报告、回放、教师复盘接口聚合 A 的报告结果。
- 提供报告重算入口，但重算逻辑由 A 执行。

## 6. 架构推荐
- `teacher.py` 和 `student.py` 只做路由、鉴权上下文和响应组织。
- `debate_service.py` 做建赛、预约、候选辩题、辩位分配编排。
- `assessment_service.py` 做画像计算和旧字段映射。
- `analytics_service.py` 做历史表现、发言统计和成长趋势聚合。
- B 调用 E 的服务读取教学设计和资料摘要，不直接解析文件。
- B 调用 A 的服务读取报告和评分结果，不自行生成评分。
- B 不把 `description` 当主要业务结构，只用于兼容旧数据。

## 7. 测试要求
- 老版 `description` 可解析，新版结构化配置可序列化。
- 候选辩题接口在有/无教学设计时都可用。
- 画像在自评、历史成绩、发言统计缺失时能降级。
- 辩位分配不出现重复辩位，能体现重复辩位惩罚。
- 教师覆盖分配后 `teacher_override` 为 true。
- 报告重算和教师复盘接口权限正确。

## 8. 验收标准
- D 可以只消费 B 的结构化业务接口，不解析隐藏 description。
- A 可以消费 B 的画像、辩位和配置摘要。
- B 不修改 E 的教学设计/资料服务文件。
- B 不修改任何前端文件。
