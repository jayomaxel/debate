# 工作包D：前端详细修改方案

## 1. 文档用途

本文档给前端负责人 D 使用，回答三个问题：
- D 具体要改哪些前端文件。
- 每个页面和前端模块要改成什么样。
- D 如何消费 A/B/C 冻结后的接口，避免前端反复返工。

本文档不替代 `工作包D_单文件Owner与接口冻结.md`。  
`工作包D_单文件Owner与接口冻结.md` 负责文件 owner 和接口边界；本文档负责具体前端实施路径。

## 2. 前端总目标

当前前端已经具备教师端、学生端、管理员端、公开入口、报告页、回放页、预约辩论和实时赛场等基础能力，但仍存在四个问题：
- 教学设计没有独立管理入口，建赛时无法自动读取班级教学设计生成候选辩题。
- 辩位分配仍偏向学生选择或进入顺序，缺少 AI 推荐、解释、确认和教师微调链路。
- 报告、评分、回放、教师复盘的展示没有完全适配新版 `report_meta`、分辩位评分和证据锚点。
- 认证、WebSocket、上传错误、配置脱敏等安全改造需要前端同步接入。

D 的目标是把前端从“页面直接消费接口”改成“服务层适配 + ViewModel 消费 + 页面状态完整”的结构。

## 3. D 的总体改造原则

### 3.1 文件边界
- D 可以修改所有 `web/src/**` 文件、`web/index.html`、`web/package.json`。
- D 不修改任何 `api/**`、`web/nginx.conf`、`Dockerfile.*`、`docker-compose*.yml`。
- 如果后端字段不够用，D 只提出接口变更，不直接改后端。

### 3.2 前端架构
- 组件不直接解析后端原始响应。
- 所有后端响应先进入 `services` 层，再经 `lib` 中的 adapter 转成页面 ViewModel。
- 页面只消费 ViewModel，不直接依赖后端字段细节。
- 新增状态必须覆盖 `loading / empty / error / success / degraded`。

### 3.3 交互风格
- 教师端是工作台，不做营销式大屏，优先信息密度、可扫描、可比较。
- 候选辩题、辩位分配、报告质量提示要做成可操作面板，不做一次性弹窗。
- 重要 AI 结果必须可解释、可重试、可人工覆盖。
- 学生端展示要简化技术细节，只展示对学习和比赛有用的信息。

## 4. 阶段 D0：前端合同与 adapter 先冻结

### 当前状态
- `teacher.service.ts`、`student.service.ts`、`auth.service.ts` 已有基础接口类型。
- 组件中仍存在不少直接依赖服务返回结构的情况。

### 目标状态
- 先冻结 5 个前端 ViewModel，再开始页面改造：
  - `FrontendTeachingDesignViewModel`
  - `FrontendAssignmentViewModel`
  - `FrontendReportViewModel`
  - `FrontendAuthStateShape`
  - `FrontendUploadErrorMapper`

### 涉及文件
- 新增 `web/src/lib/frontend-contracts.ts`
- 新增 `web/src/lib/frontend-adapters.ts`
- 新增 `web/src/lib/upload-error-mapper.ts`
- 修改 `web/src/services/teacher.service.ts`
- 修改 `web/src/services/student.service.ts`
- 修改 `web/src/services/auth.service.ts`
- 修改 `web/src/lib/api.ts`

### 怎么改
- 在 `frontend-contracts.ts` 中集中定义前端 ViewModel 类型。
- 在 `frontend-adapters.ts` 中写纯函数 adapter：
  - `toTeachingDesignViewModel`
  - `toAssignmentViewModel`
  - `toReportViewModel`
  - `toAuthStateShape`
- 在 `upload-error-mapper.ts` 中把 C 的 `UploadGuardErrorContract` 映射成前端提示。
- 组件只能 import ViewModel 和 adapter，不直接写后端字段解析逻辑。

### 验收标准
- 页面组件中不再散落 `report_meta.scoring_quality` 之外的原始报告解析逻辑。
- 上传错误都通过统一 mapper 展示。
- mock 数据可以在没有后端联调时驱动页面渲染。

## 5. 阶段 D1：教学设计中心

### 当前状态
- 教师端有 `teacher-dashboard.tsx`、`teacher-reservation-form.tsx`、`teacher-reservation-management.tsx`。
- 教学设计上传和结构化抽取尚未形成独立页面。
- 当前建赛/预约仍以辩题和 description 为中心。

### 目标状态
- 教学设计成为班级级独立入口。
- 教师可以对每个班级上传、替换、查看抽取结果、在线修改抽取结果。
- 创建辩论时只选择已有教学设计版本，不要求每次重复上传。

### 涉及文件
- 新增 `web/src/components/teaching-design-manager.tsx`
- 修改 `web/src/components/teacher-dashboard.tsx`
- 修改 `web/src/components/layouts/teacher-layout.tsx`
- 修改 `web/src/services/teacher.service.ts`
- 修改 `web/src/lib/frontend-contracts.ts`
- 修改 `web/src/lib/frontend-adapters.ts`
- 新增 `web/src/components/teaching-design-manager.test.tsx`

### 怎么改
- 在教师端导航或 tab 中新增“教学设计”入口。
- `teaching-design-manager.tsx` 分为四块：
  - 班级选择区：选择当前班级。
  - 文件区：上传/覆盖 PDF 或 DOCX，显示当前版本。
  - 抽取结果区：按课程目标、知识点、章节主题、重点难点、能力目标等结构展示。
  - 校正区：允许教师编辑抽取后的结构化字段。
- 对于抽取缺失或低置信度字段，用提示标记，不强行填满。
- 在线修改只改结构化结果，不提供原始文档编辑器。

### 交互要求
- 上传后显示 `extracting` 状态。
- 抽取完成显示 `ready`。
- 字段缺失显示 `needs_review`。
- 抽取失败显示失败原因和重新上传入口。
- 保存修改时要有保存中、保存成功、保存失败状态。

### 验收标准
- 教师可以不进入创建辩论表单，就完成教学设计上传和校正。
- 同一个班级可以看到当前教学设计版本。
- 创建辩论时能读取当前班级教学设计版本。

## 6. 阶段 D2：候选辩题推荐面板

### 当前状态
- `teacher-reservation-form.tsx` 里直接填写辩题。
- 没有候选辩题推荐、比较、选用和重生成机制。

### 目标状态
- 教师在创建/预约辩论时，先选择班级和教学设计版本。
- 前端调用 B 的候选辩题编排接口，并消费 E 冻结的教学设计/资料摘要结构，展示多个可选辩题。
- 教师可以比较候选辩题、选用其中一个，也可以手动修改。

### 涉及文件
- 新增 `web/src/components/topic-recommendation-panel.tsx`
- 修改 `web/src/components/teacher-reservation-form.tsx`
- 修改 `web/src/components/teacher-dashboard.tsx`
- 修改 `web/src/services/teacher.service.ts`
- 修改 `web/src/lib/debate-description.ts`
- 新增 `web/src/components/topic-recommendation-panel.test.tsx`

### 怎么改
- 在 `teacher-reservation-form.tsx` 中新增“教学设计与辩题推荐”区域。
- 该区域不是弹窗，建议做成表单内的独立面板，放在辩题输入框上方。
- 面板内容：
  - 当前班级教学设计版本。
  - 活动聚焦字段：章节重点、训练目标、课堂场景。
  - “生成候选辩题”按钮。
  - 候选辩题列表。
- 每个候选辩题卡片展示：
  - 辩题文本。
  - 适配课程目标。
  - 对应知识点。
  - 适合课堂场景。
  - 可辩性说明。
  - 难度等级。
  - 推荐使用原因。
  - “选用”按钮。
- 选用后自动填入 `topic`，同时把 `teaching_design_version_id`、`activity_focus`、`topic_id` 写入结构化配置。

### 交互要求
- 生成候选辩题时显示 loading。
- 没有教学设计时提示先去“教学设计中心”上传。
- 生成失败时保留教师已填写内容。
- 教师仍可手动覆盖辩题文本。

### 验收标准
- 教师可以从候选辩题一键填入辩题。
- 候选辩题能显示推荐依据。
- 没有教学设计时不会阻塞手动建赛，但会提示推荐能力不可用。

## 7. 阶段 D3：建赛/预约表单结构化改造

### 当前状态
- `teacher-reservation-form.tsx` 主要字段是 topic、description、duration、time、visibility、students。
- `description` 仍承担太多隐性业务信息。

### 目标状态
- 表单显式支持结构化配置：
  - `mode`
  - `rounds`
  - `knowledge_points`
  - `objective`
  - `evaluation_focus`
  - `forbidden_moves`
  - `support_document_ids`
  - `teaching_design_version_id`
  - `role_assignment_mode`
  - `assignment_policy`

### 涉及文件
- 修改 `web/src/components/teacher-reservation-form.tsx`
- 修改 `web/src/components/teacher-reservation-management.tsx`
- 修改 `web/src/lib/debate-description.ts`
- 修改 `web/src/lib/debate-description.test.ts`
- 修改 `web/src/services/teacher.service.ts`

### 怎么改
- 保留 `description` 的兼容能力，但页面上不再让教师把所有配置写进一段说明。
- 增加分区：
  - 基础信息：班级、时间、时长、公开性。
  - 辩题来源：手动输入或 AI 推荐。
  - 教学目标：知识点、目标、评价重点。
  - 资料配置：支持材料、资料标签。
  - 辩位分配：发挥优势/补齐短板、自动分配/推荐后确认。
- `buildDebateDescription` 只作为兼容序列化工具，不作为页面主要编辑入口。

### 验收标准
- 表单提交的结构化字段完整。
- 老数据仍能通过 `parseDebateDescription` 展示。
- 新建数据不再依赖教师手写复杂 description。

## 8. 阶段 D4：AI 辩位分配确认面板

### 当前状态
- 已有 `DebateGroupingItem` 和部分 grouping 展示。
- 角色分配解释不足，教师缺少策略选择和确认微调入口。

### 目标状态
- 停止把进入顺序或学生选择作为主要辩位分配方式。
- 前端展示 AI 推荐的辩位分配、推荐理由、数据依据、重复辩位惩罚。
- 教师可以确认 AI 分配，也可以手动微调。

### 涉及文件
- 新增 `web/src/components/role-assignment-panel.tsx`
- 修改 `web/src/components/teacher-reservation-form.tsx`
- 修改 `web/src/components/teacher-reservation-management.tsx`
- 修改 `web/src/components/teacher-dashboard.tsx`
- 修改 `web/src/services/teacher.service.ts`
- 修改 `web/src/lib/ability-profile.ts`
- 新增 `web/src/components/role-assignment-panel.test.tsx`

### 怎么改
- 在建赛/预约流程中，选择学生后出现“AI 辩位分配”区域。
- 提供两个策略选项：
  - 发挥优势：优先把学生分到适配度最高的辩位。
  - 补齐短板：优先让学生承担需要训练的辩位，但不能完全失配。
- 提供两个执行策略：
  - AI 自动分配。
  - AI 推荐后教师确认。
- 分配结果按四个辩位展示：
  - 一辩：定义框架、立论搭建、概念界定。
  - 二辩：盘问推进、证据追问、漏洞识别。
  - 三辩：反驳整合、攻防转换、临场回应。
  - 四辩：总结陈词、价值权衡、胜负归因。
- 每个学生展示：
  - 分配辩位。
  - 分配理由。
  - 四个辩位适配分。
  - 维度贡献。
  - 历史辩位分布。
  - 是否触发重复辩位惩罚。
  - 数据依据是否充分。
- 教师微调后标记 `teacher_override: true`。

### 交互要求
- 数据不足时显示低置信度提示。
- 学生不足 4 人时显示不可完整分配提示。
- 手动调整不能出现同队同辩位重复。
- 调整后需要重新校验角色完整性。

### 验收标准
- 教师可以看到 AI 为什么这样分配。
- 教师可以切换“发挥优势/补齐短板”。
- 教师可以确认或覆盖分配结果。
- 最终提交的数据包含辩位、理由、数据依据和 override 标记。

## 9. 阶段 D5：学生画像、准备页和成长反馈

### 当前状态
- 已有 `skills-assessment-editor.tsx`、`skills-radar.tsx`、`student-onboarding.tsx`、`student-command-center.tsx`、`student-analytics-center.tsx`。
- 学生画像主要来自自评和既有展示，辩位推荐理由还不完整。

### 目标状态
- 学生可以看到自己的能力画像、辩位适配、当前被分配辩位和训练目标。
- 赛前准备助手能根据辩位和弱项展示更有针对性的建议。
- 赛后成长反馈能体现前后对比和下一次训练重点。

### 涉及文件
- 修改 `web/src/components/skills-assessment-editor.tsx`
- 修改 `web/src/components/skills-radar.tsx`
- 修改 `web/src/components/student-onboarding.tsx`
- 修改 `web/src/components/student-command-center.tsx`
- 修改 `web/src/components/student-analytics-center.tsx`
- 修改 `web/src/components/student/preparation-assistant-page.tsx`
- 修改 `web/src/hooks/use-student-assessment.ts`
- 修改 `web/src/lib/ability-profile.ts`
- 修改 `web/src/services/student.service.ts`

### 怎么改
- `skills-radar.tsx` 统一使用标准画像维度：
  - `expression`
  - `logic`
  - `critical`
  - `knowledge_primary`
  - `knowledge_secondary`
- 在学生首页或比赛准备页展示：
  - 当前能力画像。
  - 被分配辩位。
  - 分配理由。
  - 本场训练目标。
  - 需要重点避免的问题。
- 准备助手按辩位展示建议：
  - 一辩：定义、框架、主论点。
  - 二辩：问题设计、证据追问。
  - 三辩：反驳、归纳、攻防转换。
  - 四辩：总结、权衡、价值升维。

### 验收标准
- 学生端不展示复杂算法细节。
- 学生可以理解“我为什么被分到这个辩位”。
- 赛前准备建议和辩位一致。
- 赛后成长反馈能展示下一次训练重点。

## 10. 阶段 D6：报告、回放与教师复盘

### 当前状态
- 已有 `debate-report-page.tsx`、`debate-report-overview.tsx`、`debate-report-detail.tsx`、`debate-replay-page.tsx`。
- 报告质量标记、分辩位评分、证据锚点和教师复盘仍需增强。

### 目标状态
- 报告页支持 `report_meta`。
- 报告能展示分辩位评分、证据锚点、关键转折点、改进动作。
- 教师端能看到更完整的复盘摘要和报告重算入口。

### 涉及文件
- 修改 `web/src/components/debate-report-page.tsx`
- 修改 `web/src/components/debate-report-overview.tsx`
- 修改 `web/src/components/debate-report-detail.tsx`
- 修改 `web/src/components/debate-replay-page.tsx`
- 新增 `web/src/components/teaching-summary-panel.tsx`
- 修改 `web/src/components/student-analytics-center.tsx`
- 修改 `web/src/components/teacher-dashboard.tsx`
- 修改 `web/src/services/student.service.ts`
- 修改 `web/src/services/teacher.service.ts`
- 新增 `web/src/components/debate-report-quality-banner.test.tsx`

### 怎么改
- 新增报告质量提示组件：
  - `validated`：不显示或显示普通说明。
  - `repaired`：教师端显示“评分经过结构修复”，学生端不强调技术细节。
  - `fallback`：教师端显示明显降级提示和重算入口。
  - `partial`：教师端显示部分评分不可用，学生端显示简化提示。
- 报告详情增加：
  - 分辩位评分。
  - 三层评分结构：通用论证、辩位职责、团队过程。
  - 证据锚点。
  - 关键转折点。
  - 下次改进行动。
- 回放页支持从报告锚点跳转：
  - URL query 可用 `?anchor=xxx` 或内部状态定位。
  - 高亮对应发言片段。
- 教师复盘展示：
  - 本场共性问题。
  - 关键转折点。
  - 建议下次训练重点。
  - 报告重算按钮。

### 验收标准
- `fallback / partial` 状态在教师端明显可见。
- 学生端不暴露过多技术细节。
- 点击证据锚点能跳到回放对应位置。
- 教师可以触发一次报告重算。

## 11. 阶段 D7：认证、WebSocket、管理员配置安全

### 当前状态
- 已有 `token-manager.ts`、`auth.context.tsx`、`auth.service.ts`、`api.ts`、`websocket-client.ts`、`use-websocket.ts`。
- 需要适配 C 的会话、ticket 和密钥脱敏方案。

### 目标状态
- 前端不长期保存 access/refresh token。
- WebSocket 使用短时 ticket。
- 管理员配置页只显示 `configured / masked`，不显示明文密钥。

### 涉及文件
- 修改 `web/src/lib/token-manager.ts`
- 修改 `web/src/store/auth.context.tsx`
- 修改 `web/src/services/auth.service.ts`
- 修改 `web/src/lib/api.ts`
- 修改 `web/src/lib/websocket-client.ts`
- 修改 `web/src/hooks/use-websocket.ts`
- 修改 `web/src/components/debate-arena.tsx`
- 修改 `web/src/services/admin.service.ts`
- 修改 `web/src/components/admin/model-configuration.tsx`
- 修改 `web/src/components/admin/coze-configuration.tsx`
- 修改 `web/src/components/admin/asr-configuration.tsx`
- 修改 `web/src/components/admin/tts-configuration.tsx`
- 修改 `web/src/components/admin/vector-configuration.tsx`
- 修改 `web/src/components/admin/email-configuration.tsx`

### 怎么改
- `token-manager.ts`：
  - 移除长期 refresh token 持久化。
  - 只保留内存态或短生命周期 access token 管理。
- `auth.context.tsx`：
  - 使用 `FrontendAuthStateShape`。
  - 明确 `initializing / authenticated / anonymous / expired / error` 状态。
- `api.ts`：
  - 统一 401、403、会话过期、重认证处理。
- `websocket-client.ts`：
  - 连接前先调用 C 的 ticket 接口。
  - 使用 `/ws/{room_id}?ticket=...`。
  - ticket 过期时进入重新获取和重连流程。
- 管理员配置页：
  - 只展示是否已配置和脱敏值。
  - 提交新密钥时不允许“查看原密钥”。

### 验收标准
- localStorage 中没有长期 access/refresh token。
- WebSocket query 中不出现 access token。
- 配置页不回显明文 API key。
- 会话过期时路由能回到登录或重认证状态。

## 12. 阶段 D8：公开站、法务页、404、Error Boundary、a11y

### 当前状态
- 已有 `public-entry.tsx`、`public-layout.tsx`、`app-router.tsx`。
- 公开站、法务、404、错误边界和 a11y 仍需补齐。

### 目标状态
- 平台具备最小可上线网站能力。
- 公开页面能说明平台用途，但不要喧宾夺主。
- 应用异常不会导致白屏。

### 涉及文件
- 修改 `web/src/components/app-router.tsx`
- 修改 `web/src/components/public-entry.tsx`
- 修改 `web/src/components/layouts/public-layout.tsx`
- 新增 `web/src/components/public/home-page.tsx`
- 新增 `web/src/components/public/features-page.tsx`
- 新增 `web/src/components/public/contact-page.tsx`
- 新增 `web/src/components/legal/privacy-page.tsx`
- 新增 `web/src/components/legal/terms-page.tsx`
- 新增 `web/src/components/error-boundary.tsx`
- 修改 `web/index.html`

### 怎么改
- `app-router.tsx` 增加：
  - `/privacy`
  - `/terms`
  - `/404`
  - fallback not found route。
- `error-boundary.tsx` 包裹主要路由区域。
- 公开站保持简洁，重点展示：
  - AI 辩论式学习平台。
  - 教师建赛、学生参赛、赛后报告。
  - 登录入口。
- `web/index.html` 补基础 title、description、favicon、viewport 和 open graph 最小信息。
- a11y 基线：
  - 表单控件有 label。
  - 关键按钮有明确文本或 tooltip。
  - 错误提示和 loading 状态可被读屏理解。
  - 键盘可操作主要弹层、菜单、表单。

### 验收标准
- 访问未知路径显示 404，不白屏。
- 组件异常进入 Error Boundary。
- 公开页、隐私页、服务条款页可访问。
- 基础 SEO 信息存在。

## 13. 阶段 D9：测试与联调

### 当前状态
- 项目已有 Vitest、Testing Library 和部分组件/服务测试。

### 目标状态
- D 至少覆盖关键 adapter、核心页面状态和安全接入逻辑。

### 涉及文件
- 新增或修改 `web/src/lib/*.test.ts`
- 新增或修改 `web/src/services/*.test.ts`
- 新增或修改 `web/src/components/*.test.tsx`

### 必测用例
- 教学设计：
  - 上传成功。
  - 抽取中。
  - 抽取失败。
  - 字段缺失需要教师校正。
- 候选辩题：
  - 有推荐结果。
  - 无教学设计。
  - 推荐生成失败。
  - 选用候选辩题。
- 辩位分配：
  - 发挥优势模式。
  - 补齐短板模式。
  - 重复辩位惩罚提示。
  - 教师手动覆盖。
- 报告：
  - `validated`。
  - `repaired`。
  - `fallback`。
  - `partial`。
  - 锚点跳转回放。
- 安全：
  - 会话过期。
  - WebSocket ticket 获取失败。
  - 上传被拦截。
  - 配置脱敏展示。

### 验收命令
```bash
cd web
pnpm test:run
pnpm type-check
pnpm build
```

## 14. D 与 A/B/C/E 的接口等待顺序

### 第一步：等 A
- `DebateReportSchema`
- `ReportMeta`
- `ParticipantScoreProfileSchema`
- `ScoreEvidenceSchema`
- `ScoreCalibrationSummarySchema`

D 在这些字段冻结前，只能做报告页 mock，不要写死字段名。

### 第二步：等 B
- `TopicRecommendationResult`
- `DebateConfigMeta`
- `AssessmentResultSchema`
- `RoleFitScoreSchema`
- `RoleAssignmentPolicySchema`
- `RoleAssignmentResult`

B 负责教师/学生业务接口和候选辩题编排。D 在这些字段冻结前，可以先完成页面骨架和 mock adapter。

### 第三步：等 C
- `AuthSessionContract`
- `WsTicketContract`
- `MaskedConfigResponse`
- `UploadGuardErrorContract`

D 在这些字段冻结前，不要大改 token 和 WebSocket 的最终实现，只先封装替换点。

### 第四步：等 E
- `TeachingDesignSchema`
- `SupportDocumentSummarySchema`
- `KnowledgeSnippetSchema`

E 负责教学设计、支持材料和资源摘要的底层结构。D 在这些字段冻结前，只能用 fixture 做教学设计中心和资料展示。

## 15. 推荐开发顺序

1. 先做 `frontend-contracts.ts` 和 `frontend-adapters.ts`。
2. 再做教学设计中心，因为候选辩题依赖它。
3. 再改建赛/预约表单和候选辩题面板。
4. 再做 AI 辩位分配确认面板。
5. 再做学生画像、准备页和成长反馈。
6. 再做报告、回放、教师复盘。
7. 再做认证、WebSocket、管理员配置安全接入。
8. 最后补公开站、Error Boundary、a11y 和测试。

## 16. D 最终交付物

- 前端 ViewModel 与 adapter 层。
- 教学设计中心。
- 候选辩题推荐面板。
- 结构化建赛/预约表单。
- AI 辩位分配确认与教师微调面板。
- 学生画像、辩位理由、赛前准备和成长反馈。
- 报告质量提示、分辩位评分、回放锚点和教师复盘。
- 会话安全、WebSocket ticket、配置脱敏、上传错误接入。
- 公开站、法务页、404、Error Boundary、a11y 基线。
- 前端测试、类型检查和构建通过。
