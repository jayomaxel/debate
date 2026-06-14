# 工作包E：教学设计、资料资源与契约测试支撑

## 1. 负责人定位
- 角色：教学设计与资源材料后端工程师。
- 核心目标：从 B 中拆出教学设计、文档材料、资源摘要、知识片段和契约测试支撑，给 B/A/D 提供稳定的资料基础能力。
- 不负责：教师/学生主路由、AI 评分、辩位分配核心策略、安全认证、前端页面。

## 2. 单文件 Owner

### E 可修改文件
- `api/models/class_teaching_design.py`
- `api/models/document.py`
- `api/services/teaching_design_service.py`
- `api/services/document_service.py`
- `api/services/knowledge_base.py`
- `api/tests/test_teaching_design_service.py`
- `api/tests/test_support_document_summary.py`
- `api/tests/test_contract_fixtures.py`
- `api/tests/fixtures/*.json`
- `docs/api_contract_examples/*.json`
- `docs/acceptance_checklist.md`

### E 禁止修改文件
- `api/routers/teacher.py`
- `api/routers/student.py`
- `api/services/debate_service.py`
- `api/services/assessment_service.py`
- `api/services/analytics_service.py`
- `api/agents/*`
- `api/services/report_service.py`
- `api/services/scoring_service.py`
- `api/routers/auth.py`
- `api/routers/websocket.py`
- `api/main.py`
- `web/src/**`
- `web/index.html`
- `web/package.json`

## 3. 什么需要等谁做完

### 可以立即开始
- 教学设计 schema。
- 教学设计版本结构。
- 抽取结果字段、置信度、缺失字段、来源片段映射。
- 支持材料标签和摘要结构。
- mock fixture 和示例响应。

### 必须等 C 冻结后再接入
- `UploadGuardErrorContract`
- 上传安全策略。

用途：
- E 处理业务文档服务，但上传安全由 C 统一拦截。

### B 必须等待 E
- B 的候选辩题推荐、结构化建赛、资料注入编排要等 E 的教学设计与资料摘要接口稳定。

### A 必须等待 E
- A 的 `knowledge_snippets`、资料摘要注入、source basis 要等 E 的摘要和知识片段字段稳定。

### D 必须等待 E
- D 的教学设计中心、资料标签、摘要展示要等 E 的 schema 和 mock 数据。

## 4. 固定接口，冻结后不能随意改

### TeachingDesignSchema
```json
{
  "design_id": "string",
  "class_id": "string",
  "current_version_id": "string",
  "versions": [
    {
      "version_id": "string",
      "uploaded_at": "ISO-8601 datetime",
      "source_file_type": "pdf | docx",
      "source_file_name": "string",
      "extraction_result": {},
      "confidence": {},
      "missing_fields": [],
      "source_excerpt_map": {},
      "status": "extracting | ready | needs_review | failed"
    }
  ]
}
```

### TeachingDesignExtractionResult
```json
{
  "course_objectives": [],
  "knowledge_points": [],
  "chapter_topics": [],
  "key_and_difficult_points": [],
  "competency_goals": [],
  "applicable_grade": [],
  "class_hour_constraints": [],
  "teacher_notes": []
}
```

### SupportDocumentSummarySchema
```json
{
  "document_id": "string",
  "label": "background | evidence | case | optional",
  "summary": "string",
  "key_points": ["string"],
  "evidence_candidates": ["string"],
  "case_candidates": ["string"],
  "usable_phases": ["opening", "questioning", "free_debate", "closing"],
  "summary_quality": "validated | fallback"
}
```

### KnowledgeSnippetSchema
```json
{
  "snippet_id": "string",
  "document_id": "string",
  "source_type": "background | evidence | case | optional",
  "content": "string",
  "usage_goal": "string",
  "source_location": "string"
}
```

### ContractFixtureSchema
```json
{
  "name": "string",
  "owner": "A | B | C | D | E",
  "contract": "string",
  "example": {},
  "updated_at": "ISO-8601 datetime"
}
```

## 5. 需要做的功能
- 支持教学设计按班级独立管理。
- 支持教学设计多版本。
- 支持 PDF/DOCX 的业务文件记录，安全检查由 C 完成。
- 支持教学设计结构化抽取结果存储。
- 支持教师在线校正后的结构化结果保存。
- 支持抽取置信度、缺失字段、来源片段映射。
- 支持资料用途标签：`background / evidence / case / optional`。
- 支持支持材料摘要、证据候选、案例候选、可用阶段。
- 支持向 A 提供 `knowledge_snippets`。
- 支持向 B 提供候选辩题生成所需上下文。
- 提供 mock fixture 和接口示例给 D。

## 6. 架构推荐
- `class_teaching_design.py` 定义教学设计版本、抽取结果和状态。
- `document.py` 定义支持材料、标签、摘要状态和来源信息。
- `teaching_design_service.py` 负责教学设计版本、抽取结果保存、校正结果保存。
- `document_service.py` 负责业务文档记录、标签、摘要结果。
- `knowledge_base.py` 负责摘要片段检索和 `KnowledgeSnippetSchema` 输出。
- E 不直接建新教师路由，由 B 在 `teacher.py` 中调用 E 的服务。
- E 的服务方法必须可被单测独立调用。

## 7. 测试要求
- 教学设计无固定模板时也能保存抽取结果。
- 缺失字段能返回 `missing_fields`。
- 低置信度字段能返回 `confidence`。
- 教师校正后版本可追踪。
- 支持材料标签和摘要可保存。
- `KnowledgeSnippetSchema` 可按阶段和标签筛选。
- fixture JSON 能被 D 直接用于 mock。

## 8. 验收标准
- E 不修改 B 的路由和主业务服务。
- B 可以调用 E 服务完成候选辩题和建赛编排。
- A 可以消费 E 的知识片段和资料摘要。
- D 可以用 E 的 fixture 独立开发教学设计中心和资料展示。
