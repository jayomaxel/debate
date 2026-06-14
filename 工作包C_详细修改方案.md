# 工作包C：详细修改方案

## 1. C 要解决什么

C 负责平台安全和上线底座。它不参与教学业务判断，但要保证登录、会话、WebSocket、上传、配置、审计和运维可上线。

C 的最终交付：
- 服务端可吊销会话。
- WebSocket ticket。
- 管理员配置脱敏。
- 上传安全中间件。
- 审计日志。
- 基础限流。
- 健康检查、metrics、CI/CD、部署与备份文档。

## 2. C 不做什么

C 不写 AI prompt，不写辩位算法，不写教学设计抽取，不写前端页面。

如果 B/E 需要上传能力，C 只提供安全网关和错误结构，不定义教学业务字段。

## 3. 修改阶段

### C0：安全合同先落地

涉及文件：
- `api/schemas/config.py`
- `api/utils/security.py`
- `api/services/auth_service.py`
- `api/routers/auth.py`

怎么改：
- 固定：
  - `AuthSessionContract`
  - `WsTicketContract`
  - `MaskedConfigResponse`
  - `UploadGuardErrorContract`
  - `AuditLogEventContract`
- 提供 mock 响应给 D。

验收：
- D 能按合同先改前端状态。

### C1：认证与会话重构

涉及文件：
- `api/utils/security.py`
- `api/services/auth_service.py`
- `api/routers/auth.py`
- `api/middleware/auth_middleware.py`

怎么改：
- refresh token 改为服务端可吊销会话。
- 支持：
  - 当前设备登出。
  - 全设备登出。
  - 会话过期。
  - 重新认证。
- access token 生命周期缩短。
- 前端不再长期保存 refresh token。

验收：
- 旧 token 失效后不能继续刷新。
- 会话可被服务端主动吊销。

### C2：WebSocket ticket 化

涉及文件：
- `api/routers/websocket.py`
- `api/routers/auth.py`
- `api/middleware/auth_middleware.py`
- `api/tests/test_websocket_ticket.py`

怎么改：
- 新增获取 ws ticket 的 HTTP 接口。
- ticket 包含：
  - `ticket`
  - `room_id`
  - `expires_at`
  - `connection_url`
- WebSocket 连接改为 `/ws/{room_id}?ticket=...`。
- 禁止 access token 直接进入 query string。

验收：
- 无 ticket 不能连接。
- 过期 ticket 不能连接。
- ticket 只能用于指定 room。

### C3：管理员配置密钥脱敏

涉及文件：
- `api/models/config.py`
- `api/services/config_service.py`
- `api/schemas/config.py`
- `api/routers/admin.py`
- `api/tests/test_config_masking.py`

怎么改：
- 配置接口不返回明文 API key。
- 返回：
  - `configured`
  - `masked`
  - `updated_at`
  - `updated_by`
- 修改配置只能提交新值，不能查看旧值。

验收：
- OpenAI、Coze、ASR、TTS、Vector、Email 配置均不回传明文密钥。

### C4：上传安全中间件

涉及文件：
- `api/middleware/upload_guard.py`
- `api/utils/upload_security.py`
- `api/main.py`
- `api/tests/test_upload_guard.py`

怎么改：
- 统一检查：
  - 文件大小。
  - 扩展名。
  - MIME。
  - 魔数。
  - 临时隔离路径。
- 统一返回 `UploadGuardErrorContract`。
- B/E 不自行拼上传安全错误。

验收：
- 非法 PDF/DOCX 被拦截。
- 错误结构可被 D 映射。

### C5：审计日志与限流

涉及文件：
- `api/services/audit_service.py`
- `api/middleware/rate_limit.py`
- `api/main.py`
- `api/tests/test_audit_service.py`
- `api/tests/test_rate_limit.py`

怎么改：
- 审计事件覆盖：
  - 登录。
  - 上传。
  - 配置修改。
  - 管理员操作。
  - 报告重算。
- 限流至少覆盖：
  - 登录。
  - 上传。
  - 报告重算。
  - 生成候选辩题。

验收：
- 关键操作可追踪。
- 高频调用能被限流。

### C6：运维交付

涉及文件：
- `api/main.py`
- `web/nginx.conf`
- `docker-compose.yml`
- `docker-compose.dev.yml`
- `Dockerfile.api`
- `Dockerfile.web`
- `.github/workflows/ci.yml`
- `ops/deploy.md`
- `ops/backup_restore.md`
- `ops/security_baseline.md`

怎么改：
- 增加健康检查。
- 增加 metrics 最小入口。
- CI 至少跑：
  - 后端测试。
  - 前端类型检查。
  - 前端构建。
- 写清部署步骤、回滚步骤、备份恢复。

验收：
- 能按文档部署。
- CI 失败能阻断合并。

## 4. C 的架构建议

- 安全能力做横切，不侵入 B/E 业务逻辑。
- token、ticket、secret、upload error 都由 C 统一规范。
- 审计日志不要散落在业务服务里，业务只传事件语义。
- 配置服务统一脱敏，不让各配置页自己处理。

## 5. C 的联调顺序

1. 先和 D 联调登录态。
2. 再和 D 联调 WebSocket ticket。
3. 再和 D 联调管理员配置脱敏。
4. 再和 B/E 联调上传安全和审计。
5. 最后跑部署和 CI/CD。

## 6. C 的最终验收

- 会话可吊销。
- WebSocket 不泄漏 access token。
- 配置不回传明文密钥。
- 上传安全错误统一。
- 审计可查。
- CI/CD 和部署文档可用。
