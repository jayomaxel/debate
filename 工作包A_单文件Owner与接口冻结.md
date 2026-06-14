# 工作包A：AI内核、评分语义与报告合同

## 1. 负责人定位
- 角色：后端 AI 内核工程师。
- 核心目标：统一 Prompt Pack、评分 rubric、报告合同、Judge 降级链、评分校准和报告质量标记。
- 不负责：教师/学生业务路由、教学设计文件处理、安全认证、前端页面、运维交付。

## 2. 单文件 Owner

### A 可修改文件
- `api/agents/debater_agent.py`
- `api/agents/judge_agent.py`
- `api/agents/mentor_agent.py`
- `api/services/coze_client.py`
- `api/services/flow_controller.py`
- `api/services/report_service.py`
- `api/services/scoring_service.py`
- `api/services/history_service.py`
- `api/services/prompt_pack_service.py`
- `api/services/mode_policy_service.py`
- `api/services/domain_pack_service.py`
- `api/services/rubric_service.py`
- `api/services/score_validation_service.py`
- `api/tests/test_prompt_pack.py`
- `api/tests/test_judge_fallback.py`
- `api/tests/test_report_score_readiness.py`
- `api/tests/test_report_pdf_export.py`
- `api/tests/test_markdown_pdf.py`
- `api/tests/test_scoring_semantics.py`
- `api/tests/test_role_weight_matrix.py`
- `api/tests/test_score_validation_service.py`

### A 禁止修改文件
- `api/routers/teacher.py`
- `api/routers/student.py`
- `api/routers/auth.py`
- `api/routers/websocket.py`
- `api/services/debate_service.py`
- `api/services/assessment_service.py`
- `api/services/analytics_service.py`
- `api/services/teaching_design_service.py`
- `api/services/document_service.py`
- `api/services/knowledge_base.py`
- `api/utils/security.py`
- `api/services/auth_service.py`
- `api/services/config_service.py`
- `api/main.py`
- `web/src/**`
- `web/index.html`
- `web/package.json`

## 3. 什么需要等谁做完

### 可以立即开始
- Prompt Pack 架构。
- mode policy 架构。
- Judge JSON 校验与修复链。
- ReportMeta 与 DebateReportSchema 草案。
- 通用评分 rubric 与分辩位评分权重。

### 必须等 B 冻结后再接入
- `DebateConfigMeta`
- `AssessmentResultSchema`
- `RoleAssignmentResult`
- `TopicRecommendationResult`

用途：
- A 的 prompt 需要消费 mode、辩题、评价重点、辩位分配、画像摘要。
- A 不直接读取教师/学生路由，不直接读前端传参。

### 必须等 E 冻结后再接入
- `TeachingDesignSchema`
- `SupportDocumentSummarySchema`
- `KnowledgeSnippetSchema`

用途：
- A 的 `context_block` 和 `knowledge_snippets` 需要消费教学设计抽取结果、支持材料摘要和资料标签。

### 与 C 的依赖
- A 不等待 C 才能开发。
- A 输出的 `provider / generated_at / report_meta` 字段不得与 C 的审计字段冲突。

### 与 D 的依赖
- A 不等待 D。
- D 只能消费 A 冻结后的报告和评分字段，不能自行解释评分含义。

## 4. 固定接口，冻结后不能随意改

### PromptBuildContext
```json
{
  "agent": "debater | judge | mentor | report",
  "mode": "competition | teaching",
  "phase": "opening | questioning | free_debate | closing | report",
  "topic": "string",
  "role": "affirmative | negative | judge | mentor",
  "speaker_role": "debater_1 | debater_2 | debater_3 | debater_4 | judge | mentor",
  "stance": "pro | con | neutral",
  "history": [],
  "knowledge_snippets": [],
  "assessment_summary": {},
  "role_assignment_summary": {},
  "output_contract": {}
}
```

### ReportMeta
```json
{
  "scoring_source": "judge_model | fallback",
  "scoring_quality": "validated | repaired | fallback | partial",
  "provider": "coze | llm | local",
  "prompt_pack_version": "string",
  "rubric_version": "string",
  "calibration_version": "string",
  "mode": "competition | teaching",
  "retry_count": 0,
  "generated_at": "ISO-8601 datetime"
}
```

### ScoringPolicy
```json
{
  "mode": "competition | teaching",
  "scale": "ordinal_1_4",
  "final_score_mapping": "percent",
  "score_layers": {
    "common_argument_weight": 0.55,
    "role_fulfillment_weight": 0.30,
    "team_process_weight": 0.15
  },
  "fallback_policy": {
    "judge_retry_limit": 1,
    "repair_retry_limit": 1,
    "allow_partial": true
  },
  "role_dimension_weights": {
    "debater_1": {},
    "debater_2": {},
    "debater_3": {},
    "debater_4": {}
  }
}
```

### DebateReportSchema
```json
{
  "mode": "competition | teaching",
  "domain_pack_id": "string",
  "report_meta": {},
  "turning_points": [],
  "evidence_anchors": [],
  "improvement_actions": [],
  "participants": [],
  "team_summary": {},
  "teaching_summary": {}
}
```

### ScoreEvidenceSchema
```json
{
  "anchor_id": "string",
  "anchor_type": "turn | opponent_turn | document_snippet | teacher_note | peer_review | self_reflection",
  "turn_id": "string",
  "speaker_role": "string",
  "excerpt": "string",
  "source_document_id": "string",
  "source_location": "string",
  "evidence_relation": "support | rebuttal | weighing | process"
}
```

## 5. 需要做的功能
- 建立统一 Prompt Pack：`global_rules / mode_policy / task_contract / phase_objective / context_block / output_contract / domain_pack`。
- `competition` 和 `teaching` 两种模式输出策略分层。
- Judge 降级链固定为：正常生成、JSON 修复、fallback。
- fallback 结果必须写入 `report_meta`，不能伪装成正常评分。
- Mentor 在比赛模式输出短战术建议，在教学模式输出反思性改进建议。
- Debater 按阶段切换策略，资料注入只注入摘要片段和使用目标。
- 报告生成补齐 `turning_points / evidence_anchors / improvement_actions`。
- 评分标准改成分辩位、三层 rubric、证据锚点、可复核。
- 建立最小评分校准与异常样本回流。

## 6. 架构推荐
- 新增 `prompt_pack_service.py` 作为唯一 prompt 构建入口。
- 新增 `mode_policy_service.py` 管理比赛/教学策略。
- 新增 `domain_pack_service.py` 管理领域包，默认不注入金融稳定币内容。
- 新增 `rubric_service.py` 管理评分 rubric、辩位权重和版本。
- 新增 `score_validation_service.py` 管理 JSON 校验、修复、fallback 标记和校准摘要。
- `agents/*` 只负责调用与解析，不再散落业务 prompt。
- `report_service.py` 只输出冻结后的报告 schema。

## 7. 测试要求
- Prompt Pack 在 `competition / teaching` 下结构不同但格式稳定。
- Judge 非法 JSON 先修复再 fallback。
- fallback / partial 必须带完整 `report_meta`。
- 分辩位评分权重可测试。
- 报告锚点、证据片段、改进动作字段稳定。
- PDF/Markdown 导出不因新增字段失败。

## 8. 验收标准
- A 的接口冻结后，B/D 不需要再猜报告字段。
- 同一评分在历史、报告、成长中心含义一致。
- 报告质量状态可被 D 直接识别。
- A 不修改任何 B/C/D/E 文件。
