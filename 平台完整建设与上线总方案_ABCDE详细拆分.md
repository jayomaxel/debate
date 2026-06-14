# 平台完整建设与上线总方案：ABCDE 详细拆分执行版

## 1. 文档定位

本文档专门拆分 `平台完整建设与上线总方案.md`。  
它不是接口冻结文档，也不是高层概括，而是把总方案中的平台内核、画像分配、报告闭环、教师出题、完整网站、安全、运维、测试逐项分给 A/B/C/D/E。

阅读顺序：
1. 先看本文档，知道总方案拆给谁。
2. 再看对应的 `工作包X_详细修改方案.md`，知道怎么改。
3. 最后看 `工作包X_单文件Owner与接口冻结.md`，确认不能改哪些文件。

## 2. 总方案章节拆分总表

| 总方案章节 | 主责 | 协作 | 拆分说明 |
| --- | --- | --- | --- |
| 默认产品边界与总原则 | B | A,D,E | B 负责产品默认口径，A/D/E 按该口径落实现有功能 |
| 当前平台基线判断 | B | A,C,D,E | B 统筹真实实现口径，其他人补充本模块状态 |
| 平台内核改造总线 | A | B,E,D | A 主责 Prompt、mode、domain、judge、report、scoring |
| 评估、画像、AI 辩位分配与智能分组 | B | A,D,E | B 主责画像和辩位分配，A 提供 scoring，D 展示，E 提供教学资料上下文 |
| 报告、回放与教师复盘闭环 | A/B | D | A 负责报告结构和评分，B 负责业务聚合，D 负责展示 |
| 教师端结构化出题与资料配置 | B/E | D,A | E 负责教学设计和资料支撑，B 负责编排，D 展示，A 消费资料 |
| 完整网站能力补齐 | D | C | D 负责前端页面，C 负责部署、安全头和运维支撑 |
| 安全整改 | C | D,B,E | C 主责，D 接入，B/E 提供业务对象语义 |
| 运维交付与工程闭环 | C | A,B,D,E | C 主责 CI/CD、部署、备份，其他人提供测试命令和依赖 |
| 测试与验收矩阵 | 全员 | E 汇总 fixture | 各工作包负责本模块测试，E 提供 mock 和验收清单 |

## 3. A：AI 内核、评分与报告详细拆分

### 来源章节
- `平台内核改造总线`
- `报告、回放与教师复盘闭环`
- `测试与验收矩阵 - 平台内核验收`
- `平台建设参考文献与可借鉴标准 - 评分机制参考文献`

### A 要做的功能
- Prompt Pack 平台主控。
- 比赛/教学双模式策略。
- Domain Pack 能力，但默认不启用金融稳定币口径。
- Judge 降级透明化。
- 评分机制科学化重构。
- 三层评分结构。
- 分辩位 rubric。
- 评分证据来源与禁止推断边界。
- 评分输出合同。
- 自动评分实现路径。
- 信度、效度与公平性校准。
- DebateReportSchema。
- report_meta。
- 评分解释层。

### A 具体怎么改

#### A1 Prompt Pack 平台主控
涉及文件：
- `api/services/prompt_pack_service.py`
- `api/services/mode_policy_service.py`
- `api/services/domain_pack_service.py`
- `api/agents/debater_agent.py`
- `api/agents/judge_agent.py`
- `api/agents/mentor_agent.py`
- `api/services/flow_controller.py`

改法：
- 新增统一 prompt 构建入口。
- 固定 prompt 分层：`global_rules / mode_policy / task_contract / phase_objective / context_block / output_contract / domain_pack`。
- 从 `debater_agent / judge_agent / mentor_agent` 中移除散落的任务性 prompt。
- agent 只负责传入上下文、调用模型、解析结果。

验收：
- 同一 agent 在 `competition / teaching` 下生成不同策略。
- 不再由 Coze bot 决定任务格式和评分维度。

#### A2 Judge 降级链
涉及文件：
- `api/agents/judge_agent.py`
- `api/services/score_validation_service.py`
- `api/services/scoring_service.py`
- `api/services/report_service.py`

改法：
- Judge 输出先校验 JSON。
- 非法 JSON 先走修复重试。
- 再失败进入 fallback。
- fallback 必须写 `report_meta`。

验收：
- 非法 JSON 不会导致报告生成中断。
- D 可以识别 `validated / repaired / fallback / partial`。

#### A3 分辩位评分
涉及文件：
- `api/services/rubric_service.py`
- `api/services/scoring_service.py`
- `api/tests/test_role_weight_matrix.py`

改法：
- 共通论证质量 rubric。
- 辩位履职 rubric。
- 团队过程 rubric。
- 四个辩位分别设置权重。
- 分数统一映射到标准维度：`logic / argument / response / persuasion / teamwork`。

验收：
- 一辩、二辩、三辩、四辩评分侧重点不同。
- 同一分数在报告、历史、成长中心含义一致。

#### A4 报告结构
涉及文件：
- `api/services/report_service.py`
- `api/tests/test_report_score_readiness.py`
- `api/tests/test_report_pdf_export.py`

改法：
- 输出 `turning_points`。
- 输出 `evidence_anchors`。
- 输出 `improvement_actions`。
- 输出 participant 级评分。
- 输出 team summary。
- 输出 teaching summary 所需字段。

验收：
- 报告能跳转回放。
- 报告可解释评分依据。
- 教师端可显示重算和降级信息。

### A 需要等谁
- 等 B：画像、辩位、建赛配置、候选辩题上下文。
- 等 E：教学设计摘要、支持材料摘要、knowledge snippets。
- 不等 C/D 才能开始，但输出要给 D 使用。

### A 架构建议
- 所有 prompt 构造集中在 `prompt_pack_service.py`。
- 所有评分规则集中在 `rubric_service.py`。
- 所有降级和校验集中在 `score_validation_service.py`。
- 报告 schema 不由多个服务拼字段。

## 4. B：教学业务编排、画像与辩位分配详细拆分

### 来源章节
- `默认产品边界与总原则`
- `当前平台基线判断`
- `评估、画像、AI 辩位分配与智能分组`
- `报告、回放与教师复盘闭环`
- `教师端结构化出题与资料配置`

### B 要做的功能
- 当前平台真实口径梳理。
- 教师/学生业务接口。
- DebateConfigMeta。
- 候选辩题推荐编排。
- 当前评估口径固化。
- 初步融合画像。
- 画像治理与学习分析边界。
- 辩位能力模型。
- AI 辩位分配模式。
- AI 辩位分配算法与约束。
- AI 辩位分配解释化。
- 动态成长反馈与轮岗机制。
- 画像驱动 Mentor 提示词所需摘要。
- 报告/回放/教师复盘业务聚合。

### B 具体怎么改

#### B1 业务路由整理
涉及文件：
- `api/routers/teacher.py`
- `api/routers/student.py`

改法：
- 教师端接口集中提供：
  - 教学设计版本选择结果读取。
  - 候选辩题推荐。
  - 建赛/预约。
  - 辩位分配预览。
  - 辩位分配确认。
  - 教师复盘摘要。
  - 报告重算。
- 学生端接口集中提供：
  - 画像。
  - 当前辩位。
  - 赛前准备。
  - 报告。
  - 回放。
  - 成长反馈。

验收：
- D 不直接调多个底层服务拼页面。

#### B2 DebateConfigMeta
涉及文件：
- `api/services/debate_service.py`
- `api/tests/test_debate_config_meta.py`

改法：
- 结构化保存：
  - mode。
  - rounds。
  - objective。
  - knowledge_points。
  - evaluation_focus。
  - forbidden_moves。
  - support_document_ids。
  - teaching_design_version_id。
  - role_assignment_mode。
  - assignment_policy。
- 老 description 保留兼容。

验收：
- 老数据不坏，新数据不依赖自由文本。

#### B3 候选辩题推荐编排
涉及文件：
- `api/services/debate_service.py`
- `api/tests/test_topic_recommendation.py`

改法：
- 调 E 读取教学设计和资料摘要。
- 组织 activity focus。
- 调 A/LLM 生成候选辩题。
- 返回 `TopicRecommendationResult`。

验收：
- 每个候选辩题包含课程目标、知识点、课堂场景、可辩性、难度、推荐原因。

#### B4 学生画像
涉及文件：
- `api/models/assessment.py`
- `api/services/assessment_service.py`
- `api/services/analytics_service.py`

改法：
- 固化 5 维画像。
- 兼容旧字段。
- 融合自评、历史成绩、发言统计。
- 数据不足时写明 `analysis_basis`。

验收：
- 不声称接入 LMS 或完整学情大数据。

#### B5 AI 辩位分配
涉及文件：
- `api/services/debate_service.py`
- `api/services/assessment_service.py`

改法：
- 建立一辩、二辩、三辩、四辩能力要求。
- 支持发挥优势和补齐短板。
- 加入重复辩位惩罚。
- 输出解释、维度贡献、历史辩位分布、教师覆盖标记。

验收：
- 不再按进入顺序分配。
- 教师可确认和微调。

#### B6 教师复盘与成长反馈
涉及文件：
- `api/services/analytics_service.py`
- `api/routers/teacher.py`
- `api/routers/student.py`

改法：
- 聚合 A 的报告字段。
- 聚合学生画像和辩位表现。
- 输出共性问题、关键转折点、下次训练重点。

验收：
- 教师端能看共性问题。
- 学生端能看下一次训练重点。

### B 需要等谁
- 等 A：报告、评分、证据锚点。
- 等 E：教学设计和资料摘要。
- 等 C：权限、上传错误、审计。
- D 等 B：所有业务页面接口。

### B 架构建议
- B 是编排层，不是底层能力层。
- 不复制 A 的评分逻辑。
- 不复制 E 的文档逻辑。
- 不复制 C 的安全逻辑。

## 5. C：安全整改与运维交付详细拆分

### 来源章节
- `安全整改`
- `运维交付与工程闭环`
- `完整网站能力补齐` 中部署和稳定性支撑部分
- `测试与验收矩阵 - 安全验收 / 运维验收`

### C 要做的功能
- 会话重构。
- WebSocket ticket 化。
- 配置密钥安全。
- 上传与审计。
- 安全基线。
- metrics 与告警。
- 异步任务预留。
- CI/CD。
- 备份恢复。

### C 具体怎么改

#### C1 会话重构
涉及文件：
- `api/utils/security.py`
- `api/services/auth_service.py`
- `api/routers/auth.py`
- `api/middleware/auth_middleware.py`

改法：
- refresh token 改成服务端可吊销。
- 支持登出当前设备和全部设备。
- 统一 401/403/过期状态。

验收：
- D 不再长期保存 refresh token。

#### C2 WebSocket ticket
涉及文件：
- `api/routers/websocket.py`
- `api/routers/auth.py`

改法：
- 新增 ticket 获取接口。
- WebSocket 只接受 ticket。
- ticket 有 room、过期时间和一次性/短期限制。

验收：
- query string 不出现 access token。

#### C3 配置密钥脱敏
涉及文件：
- `api/models/config.py`
- `api/services/config_service.py`
- `api/schemas/config.py`
- `api/routers/admin.py`

改法：
- 配置接口只返回 configured/masked。
- 不提供查看明文密钥能力。

验收：
- 管理端不显示明文 API key。

#### C4 上传安全与审计
涉及文件：
- `api/middleware/upload_guard.py`
- `api/utils/upload_security.py`
- `api/services/audit_service.py`
- `api/main.py`

改法：
- 上传检查扩展名、MIME、魔数、大小。
- 统一上传错误结构。
- 审计上传、配置、报告重算、管理员操作。

验收：
- B/E 不各自实现上传安全。

#### C5 运维交付
涉及文件：
- `docker-compose.yml`
- `Dockerfile.api`
- `Dockerfile.web`
- `.github/workflows/ci.yml`
- `ops/deploy.md`
- `ops/backup_restore.md`

改法：
- CI 执行后端测试、前端类型检查、前端构建。
- 写部署、回滚、备份恢复。
- 提供健康检查和 metrics。

验收：
- 平台具备最小上线交付能力。

## 6. D：前端详细拆分

### 来源章节
- `评估、画像、AI 辩位分配与智能分组` 的展示部分
- `报告、回放与教师复盘闭环` 的前端展示规则
- `教师端结构化出题与资料配置` 的教师端交互
- `完整网站能力补齐`
- `安全整改` 的前端接入部分
- `测试与验收矩阵 - 前端展示验收`

### D 要做的功能
- 前端 ViewModel。
- 教学设计中心。
- 候选辩题面板。
- 建赛/预约表单。
- AI 辩位分配确认面板。
- 学生画像和准备页。
- 报告、回放、教师复盘。
- 认证和 WebSocket 接入。
- 管理员配置脱敏展示。
- 公开站、法务页、404、Error Boundary、a11y。

### D 具体怎么改

#### D1 ViewModel 与 adapter
涉及文件：
- `web/src/lib/frontend-contracts.ts`
- `web/src/lib/frontend-adapters.ts`
- `web/src/services/*.ts`

改法：
- 后端响应不直接进页面。
- 页面只消费 ViewModel。
- 对 A/B/C/E 的 mock 都走 adapter。

#### D2 教学设计中心
涉及文件：
- `web/src/components/teaching-design-manager.tsx`
- `web/src/components/teacher-dashboard.tsx`

改法：
- 教学设计独立页面。
- 上传、覆盖、查看抽取结果、在线校正。
- 显示缺失字段和低置信度。

#### D3 候选辩题和建赛表单
涉及文件：
- `web/src/components/topic-recommendation-panel.tsx`
- `web/src/components/teacher-reservation-form.tsx`

改法：
- 候选辩题作为页内面板。
- 建赛表单结构化。
- 选用候选辩题后写入表单。

#### D4 辩位分配
涉及文件：
- `web/src/components/role-assignment-panel.tsx`

改法：
- 展示发挥优势/补齐短板。
- 展示分配理由、适配分、历史辩位分布。
- 支持教师覆盖。

#### D5 报告回放复盘
涉及文件：
- `web/src/components/debate-report-*.tsx`
- `web/src/components/debate-replay-page.tsx`
- `web/src/components/teaching-summary-panel.tsx`

改法：
- 报告质量提示。
- 分辩位评分。
- 证据锚点跳转回放。
- 教师端重算入口。

#### D6 安全接入和公开站
涉及文件：
- `web/src/lib/token-manager.ts`
- `web/src/lib/websocket-client.ts`
- `web/src/components/admin/*.tsx`
- `web/src/components/public/*.tsx`
- `web/src/components/error-boundary.tsx`

改法：
- 接入 C 的会话和 ticket。
- 配置页只显示 masked。
- 补公开站、法务、404、错误边界。

## 7. E：教学设计与资料支撑详细拆分

### 来源章节
- `教师端结构化出题与资料配置`
- `评估、画像、AI 辩位分配与智能分组` 中学习分析边界的数据来源说明
- `测试与验收矩阵` 中 fixture 和资料类验收

### E 要做的功能
- 班级级教学设计中心的底层数据结构。
- 非标准化教学设计抽取结果。
- 教学设计与资源元数据标准化提炼。
- 资料标签。
- 支持材料自动摘要。
- 按环节注入资料所需片段。
- 资源包自动整理基础结构。
- mock fixture。

### E 具体怎么改

#### E1 教学设计版本模型
涉及文件：
- `api/models/class_teaching_design.py`

改法：
- 班级级设计。
- 多版本。
- 当前版本。
- 原始文件信息。
- 抽取状态。

#### E2 非标准教学设计抽取结果
涉及文件：
- `api/services/teaching_design_service.py`

改法：
- 不要求教师文件按固定模板。
- 抽取课程目标、知识点、章节主题、重点难点、能力目标、年级、课时、教师备注。
- 标记缺失字段和置信度。

#### E3 资料标签与摘要
涉及文件：
- `api/models/document.py`
- `api/services/document_service.py`

改法：
- 支持 `background / evidence / case / optional`。
- 生成 summary、key points、evidence candidates、case candidates。
- 标记 usable phases。

#### E4 KnowledgeSnippet
涉及文件：
- `api/services/knowledge_base.py`

改法：
- 按阶段和标签输出给 A。
- 不把全文直接塞进 prompt。

#### E5 fixture 与示例
涉及文件：
- `api/tests/fixtures/*.json`
- `docs/api_contract_examples/*.json`

改法：
- 提供 D 可用的教学设计 mock。
- 提供 B 可用的候选辩题来源 mock。
- 提供 A 可用的 knowledge snippet mock。

## 8. 按人交付清单

### A 交付
- Prompt Pack。
- mode/domain policy。
- Judge 降级链。
- 分辩位评分。
- ReportMeta。
- DebateReportSchema。

### B 交付
- 教师/学生业务接口。
- DebateConfigMeta。
- TopicRecommendationResult。
- AssessmentResultSchema。
- RoleAssignmentResult。
- TeachingSummaryResult。

### C 交付
- AuthSessionContract。
- WsTicketContract。
- MaskedConfigResponse。
- UploadGuardErrorContract。
- AuditLogEventContract。
- 运维交付。

### D 交付
- 前端 ViewModel。
- 教师端、学生端、管理端、公开站。
- 报告、回放、复盘展示。
- 安全前端接入。

### E 交付
- TeachingDesignSchema。
- TeachingDesignExtractionResult。
- SupportDocumentSummarySchema。
- KnowledgeSnippetSchema。
- fixture 和示例。

## 9. 最短联调顺序

1. E 先给教学设计和资料 mock。
2. A 先给报告和评分 mock。
3. B 先给教师/学生接口 skeleton。
4. D 用 mock 做页面。
5. C 给登录、ticket、上传错误合同。
6. B + E 联调候选辩题。
7. A + B 联调报告和评分。
8. B + D 联调教师端/学生端。
9. C + D 联调安全接入。
10. 全员跑 E2E。
