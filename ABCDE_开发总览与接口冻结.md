# ABCDE 开发总览与接口冻结

## 1. 五人分工总览

| 工作包 | 负责人定位 | 核心边界 | 复杂度 |
| --- | --- | --- | --- |
| A | AI 内核工程师 | Prompt、评分、报告、降级链 | 高，边界集中 |
| B | 教学业务后端工程师 | 教师/学生路由、建赛、画像、辩位分配、业务编排 | 中高，集成最强 |
| C | 平台安全工程师 | 认证、WebSocket、安全、审计、运维 | 高风险，边界清楚 |
| D | 前端工程师 | 所有前端页面、ViewModel、交互、前端测试 | 高工作量 |
| E | 教学设计与资料支撑工程师 | 教学设计、支持材料、摘要、知识片段、fixture | 低到中，最适合简单任务 |

## 2. 单文件 Owner 总规则
- 任一文件只能由一个工作包修改。
- 跨工作包只通过冻结接口协作。
- 若字段不够用，提出接口变更，不直接改对方文件。
- D 独占 `web/src/**`、`web/index.html`、`web/package.json`。
- B 独占 `teacher.py / student.py / debate_service.py`。
- E 独占 `teaching_design_service.py / document_service.py / knowledge_base.py`。

## 3. 谁需要等谁

| 等待方 | 必须等待 | 原因 |
| --- | --- | --- |
| A | B 的 `DebateConfigMeta / AssessmentResultSchema / RoleAssignmentResult` | prompt 和评分报告需要业务上下文 |
| A | E 的 `SupportDocumentSummarySchema / KnowledgeSnippetSchema` | 资料注入需要稳定摘要结构 |
| B | A 的 `DebateReportSchema / ReportMeta` | 报告、教师复盘、重算接口需要报告结构 |
| B | E 的 `TeachingDesignSchema / SupportDocumentSummarySchema` | 候选辩题、结构化建赛需要教学设计和资料 |
| B | C 的审计和上传安全合同 | 上传、重算、敏感操作需要权限和审计 |
| C | B/E 的业务对象语义 | 审计和上传安全需要知道对象类型 |
| D | A/B/C/E 的冻结接口 | 前端不能写死未冻结字段 |
| E | C 的上传安全合同 | 文件业务服务需要统一上传错误结构 |

## 4. 固定接口清单

### A 冻结
- `PromptBuildContext`
- `ReportMeta`
- `ScoringPolicy`
- `DebateReportSchema`
- `ScoreEvidenceSchema`

### B 冻结
- `DebateConfigMeta`
- `TopicRecommendationResult`
- `AssessmentResultSchema`
- `RoleAssignmentResult`
- `TeachingSummaryResult`

### C 冻结
- `AuthSessionContract`
- `WsTicketContract`
- `MaskedConfigResponse`
- `UploadGuardErrorContract`
- `AuditLogEventContract`

### D 冻结
- `FrontendTeachingDesignViewModel`
- `FrontendAssignmentViewModel`
- `FrontendReportViewModel`
- `FrontendAuthStateShape`
- `FrontendUploadErrorMapper`

### E 冻结
- `TeachingDesignSchema`
- `TeachingDesignExtractionResult`
- `SupportDocumentSummarySchema`
- `KnowledgeSnippetSchema`
- `ContractFixtureSchema`

## 5. 推荐架构

### 后端
- A 做 AI 内核，不直接接教师/学生路由。
- B 做业务编排，不直接解析文件、不直接生成评分。
- C 做安全平台，不进入教学业务判断。
- E 做教学设计与资料支撑，不直接暴露教师主路由。

### 前端
- D 使用 `services + adapters + ViewModel`。
- 页面不直接消费后端原始响应。
- 所有 degraded/fallback 状态必须可视化。

### 数据流
1. E 抽取教学设计和支持材料摘要。
2. B 读取 E 的结构化结果，生成候选辩题和建赛配置。
3. A 读取 B/E 的上下文，生成 prompt、评分和报告。
4. B 聚合 A 的报告结果给教师/学生业务接口。
5. D 通过 ViewModel 展示教师端、学生端、管理员端和公开站。
6. C 横向提供认证、上传安全、审计、限流和运维。

## 6. 联调顺序
1. 第 1 天：五方冻结接口，不写业务实现。
2. 第 2 天：A 做 prompt/report skeleton；B 做业务接口 skeleton；C 做安全合同；E 做教学设计/资料 fixture；D 做页面 skeleton。
3. 第 3-4 天：A/B/E 联调候选辩题、资料注入、报告上下文。
4. 第 5 天：B/D/E 联调教学设计中心、候选辩题、建赛表单。
5. 第 6 天：A/B/D 联调报告、评分、回放、教师复盘。
6. 第 7 天：C/D 联调登录、WebSocket ticket、配置脱敏、上传错误。
7. 第 8 天：全链路回归。

## 7. 风险与处理
- 风险：B 和 E 同时改教学设计服务。处理：`teaching_design_service.py` 只归 E。
- 风险：D 在接口未冻结前写死字段。处理：D 只写 mock adapter。
- 风险：A 的评分字段漂移。处理：A 先冻结 `DebateReportSchema`。
- 风险：C 的安全改造影响上传。处理：C 只做中间件和错误合同，E 做业务文档服务。
- 风险：E 被分到太难任务。处理：E 不做辩位算法、不做评分、不做安全，只做教学设计和资料支撑。

## 8. 最终验收
- 五份工作包文档与本总览一致。
- 没有两个工作包修改同一文件。
- 所有冻结接口有 mock 示例。
- D 可以用 mock 数据独立开发。
- A/B/C/E 可以各自单测。
- 全链路通过：登录、教学设计、候选辩题、建赛、辩位分配、比赛、报告、回放、教师复盘、管理员配置。
