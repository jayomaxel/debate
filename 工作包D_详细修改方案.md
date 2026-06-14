# 工作包D：详细修改方案

## 1. D 要解决什么

D 负责所有前端实现。详细交互方案见 `工作包D_前端详细修改方案.md`，本文是 ABCDE 五人版下的标准详细修改方案。

D 的最终交付：
- 前端 ViewModel 与 adapter。
- 教学设计中心。
- 候选辩题推荐面板。
- 结构化建赛/预约表单。
- AI 辩位分配确认面板。
- 学生画像、准备页、成长反馈。
- 报告、回放、教师复盘。
- 认证、WebSocket、配置脱敏、上传错误接入。
- 公开站、法务页、404、Error Boundary、a11y。

## 2. D 不做什么

D 不修改后端文件，不设计后端算法，不签发 ticket，不处理文件安全扫描。

## 3. 修改阶段

### D0：前端 ViewModel 与 adapter

涉及文件：
- `web/src/lib/frontend-contracts.ts`
- `web/src/lib/frontend-adapters.ts`
- `web/src/lib/upload-error-mapper.ts`
- `web/src/services/*.ts`

怎么改：
- 后端响应先进入 service。
- service 响应再经过 adapter。
- 页面只消费 ViewModel。
- 先用 A/B/C/E 的 mock fixture 开发。

验收：
- 组件不直接解析后端复杂字段。

### D1：教学设计中心

涉及文件：
- `web/src/components/teaching-design-manager.tsx`
- `web/src/components/teacher-dashboard.tsx`
- `web/src/components/layouts/teacher-layout.tsx`
- `web/src/services/teacher.service.ts`

怎么改：
- 教学设计独立成教师端入口。
- 按班级上传/覆盖教学设计。
- 展示 E 的抽取结果、置信度、缺失字段和来源片段。
- 支持教师在线校正结构化结果。

验收：
- 不要求每次创建辩论都重新上传教学设计。

### D2：候选辩题推荐面板

涉及文件：
- `web/src/components/topic-recommendation-panel.tsx`
- `web/src/components/teacher-reservation-form.tsx`
- `web/src/services/teacher.service.ts`

怎么改：
- 表单中增加候选辩题面板，不做一次性弹窗。
- 调 B 的候选辩题接口。
- 展示辩题文本、课程目标、知识点、课堂场景、可辩性、难度、推荐原因。
- 选用后写入建赛表单。

验收：
- 教师可以比较、选用、重生成候选辩题。

### D3：建赛/预约表单结构化

涉及文件：
- `web/src/components/teacher-reservation-form.tsx`
- `web/src/components/teacher-reservation-management.tsx`
- `web/src/lib/debate-description.ts`

怎么改：
- 新增结构化字段：
  - mode。
  - rounds。
  - knowledge points。
  - objective。
  - evaluation focus。
  - forbidden moves。
  - support document ids。
  - role assignment mode。
  - assignment policy。
- `description` 只做兼容，不作为主编辑入口。

验收：
- 老数据能展示，新数据结构化提交。

### D4：AI 辩位分配确认

涉及文件：
- `web/src/components/role-assignment-panel.tsx`
- `web/src/components/teacher-reservation-form.tsx`
- `web/src/components/teacher-reservation-management.tsx`

怎么改：
- 展示发挥优势/补齐短板。
- 展示四个辩位适配分。
- 展示推荐理由、历史辩位分布、重复辩位惩罚。
- 支持教师确认和手动覆盖。

验收：
- 不再给教师一个黑盒分组结果。

### D5：学生端画像与准备

涉及文件：
- `web/src/components/skills-radar.tsx`
- `web/src/components/student-command-center.tsx`
- `web/src/components/student/preparation-assistant-page.tsx`
- `web/src/services/student.service.ts`

怎么改：
- 展示标准画像维度。
- 展示被分配辩位和简化理由。
- 准备页按辩位给建议。
- 成长中心展示前后对比和下次训练重点。

验收：
- 学生能理解“为什么我是这个辩位”和“下一步练什么”。

### D6：报告、回放、教师复盘

涉及文件：
- `web/src/components/debate-report-page.tsx`
- `web/src/components/debate-report-overview.tsx`
- `web/src/components/debate-report-detail.tsx`
- `web/src/components/debate-replay-page.tsx`
- `web/src/components/teaching-summary-panel.tsx`

怎么改：
- 展示 `report_meta`。
- 展示 fallback/partial/repaired/validated 状态。
- 展示分辩位评分。
- 证据锚点跳转回放。
- 教师端显示重算入口。

验收：
- 报告降级不再隐藏。

### D7：认证、实时、管理端、安全接入

涉及文件：
- `web/src/lib/token-manager.ts`
- `web/src/store/auth.context.tsx`
- `web/src/lib/websocket-client.ts`
- `web/src/hooks/use-websocket.ts`
- `web/src/components/admin/*.tsx`

怎么改：
- 不长期保存 access/refresh token。
- WebSocket 使用 ticket。
- 管理端配置只显示 masked。
- 上传错误走统一 mapper。

验收：
- localStorage 不保留长期 token。
- WebSocket query 不带 access token。
- 配置页不显示明文密钥。

### D8：公开站与质量收口

涉及文件：
- `web/src/components/public/*.tsx`
- `web/src/components/legal/*.tsx`
- `web/src/components/error-boundary.tsx`
- `web/src/components/app-router.tsx`
- `web/index.html`

怎么改：
- 补公开首页、功能页、联系页。
- 补隐私协议、服务条款。
- 补 404。
- 补 Error Boundary。
- 补基础 SEO 和 a11y。

验收：
- 未知路径不白屏。
- 应用异常进入错误边界。

## 4. D 的联调顺序

1. 用 mock 做页面骨架。
2. 接 E 的教学设计和资料结构。
3. 接 B 的建赛、候选辩题、辩位分配。
4. 接 A 的报告和评分。
5. 接 C 的登录、WebSocket、安全错误。
6. 做全链路回归。

## 5. D 的最终验收

- 前端页面闭环完整。
- 所有状态都有 loading/empty/error。
- 降级报告可见。
- 教师和学生看到的信息层级不同。
- D 不修改后端。
