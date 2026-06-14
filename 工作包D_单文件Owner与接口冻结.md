# 工作包D：全量前端实现与交互闭环

## 1. 负责人定位
- 角色：前端工程师。
- 核心目标：教师端、学生端、管理员端、公开站、认证接入、实时接入、报告/回放/复盘展示、前端 adapter 与前端测试。
- 不负责：任何 Python 后端文件、Nginx、Docker、CI/CD、AI prompt 和安全 ticket 签发。

## 2. 单文件 Owner

### D 可修改文件
- `web/src/**`
- `web/index.html`
- `web/package.json`

### D 禁止修改文件
- `api/**`
- `web/nginx.conf`
- `docker-compose*.yml`
- `Dockerfile.*`
- `.github/workflows/*`
- `ops/**`

## 3. 什么需要等谁做完

### 可以立即开始
- 前端 ViewModel 设计。
- 页面骨架。
- mock 数据。
- loading/empty/error/degraded 状态。
- 公开站、法务页、404、Error Boundary。

### 必须等 A 冻结后再接入
- `DebateReportSchema`
- `ReportMeta`
- `ParticipantScoreProfileSchema`
- `ScoreEvidenceSchema`

用途：
- 报告页、评分卡、质量提示、证据锚点、回放跳转。

### 必须等 B 冻结后再接入
- `DebateConfigMeta`
- `TopicRecommendationResult`
- `AssessmentResultSchema`
- `RoleAssignmentResult`
- `TeachingSummaryResult`

用途：
- 教师建赛、候选辩题、辩位确认、学生画像、教师复盘。

### 必须等 C 冻结后再接入
- `AuthSessionContract`
- `WsTicketContract`
- `MaskedConfigResponse`
- `UploadGuardErrorContract`

用途：
- 登录态、路由守卫、WebSocket、管理员配置、上传错误。

### 必须等 E 冻结后再接入
- `TeachingDesignSchema`
- `SupportDocumentSummarySchema`

用途：
- 教学设计中心、支持材料标签、摘要展示。

## 4. 固定接口，冻结后不能随意改

### FrontendTeachingDesignViewModel
```json
{
  "class_id": "string",
  "current_version_id": "string",
  "source_file_name": "string",
  "status": "extracting | ready | needs_review | failed",
  "extraction_sections": [],
  "topic_recommendations": []
}
```

### FrontendAssignmentViewModel
```json
{
  "assignment_id": "string",
  "mode": "competition | teaching",
  "role_assignment_mode": "strength_first | growth_first",
  "assignment_policy": "ai_auto_assign | ai_recommend_then_confirm",
  "can_teacher_override": true,
  "students": [],
  "warnings": []
}
```

### FrontendReportViewModel
```json
{
  "debate_id": "string",
  "mode": "competition | teaching",
  "title": "string",
  "report_meta": {},
  "quality_banner": {},
  "participant_scores": [],
  "team_scores": [],
  "turning_points": [],
  "evidence_anchors": [],
  "improvement_actions": [],
  "replay_anchor_map": {}
}
```

### FrontendAuthStateShape
```json
{
  "status": "initializing | authenticated | anonymous | expired | error",
  "user": {},
  "session_id": "string",
  "access_token_expires_at": "ISO-8601 datetime",
  "refresh_strategy": "http_only_cookie | server_session",
  "requires_reauth": false,
  "permissions": []
}
```

### FrontendUploadErrorMapper
```json
{
  "backend_code": "string",
  "ui_level": "info | warning | danger",
  "field": "file | form | global",
  "message": "string",
  "request_id": "string"
}
```

## 5. 需要做的功能
- 建立 `frontend-contracts.ts` 和 `frontend-adapters.ts`。
- 教学设计中心：上传、覆盖、抽取结果展示、在线校正。
- 候选辩题面板：生成、比较、选用、重生成。
- 结构化建赛/预约表单。
- AI 辩位分配确认面板：策略切换、理由展示、教师微调。
- 学生画像、辩位理由、赛前准备、成长反馈。
- 报告页：质量提示、分辩位评分、证据锚点、改进动作。
- 回放页：锚点跳转和高亮。
- 教师复盘：共性问题、下次训练重点、重算入口。
- 登录、会话过期、WebSocket ticket、配置脱敏、上传错误接入。
- 公开站、法务页、404、Error Boundary、a11y。

## 6. 架构推荐
- `services/*` 只负责请求。
- `lib/frontend-adapters.ts` 负责后端响应到 ViewModel 的转换。
- 页面组件只消费 ViewModel。
- 复杂交互拆组件：
  - `teaching-design-manager.tsx`
  - `topic-recommendation-panel.tsx`
  - `role-assignment-panel.tsx`
  - `teaching-summary-panel.tsx`
- 不把业务规则写死在 UI 组件里。
- 表单保留旧数据兼容，但新数据走结构化字段。

## 7. 测试要求
- ViewModel adapter 单测。
- 教学设计上传成功/失败/抽取中/需校正。
- 候选辩题生成和选用。
- 辩位分配策略切换和教师覆盖。
- 报告质量状态 `validated / repaired / fallback / partial`。
- WebSocket ticket 获取失败和重连。
- 配置脱敏展示。
- 404、Error Boundary、基础 a11y。

## 8. 验收标准
- D 不修改任何后端文件。
- D 不直接解析旧 `description` 隐藏结构。
- D 不长期保存 access/refresh token。
- D 能用 mock 数据独立开发，并在 A/B/C/E 接口冻结后替换真实接口。
