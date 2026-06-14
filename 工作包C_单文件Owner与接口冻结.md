# 工作包C：安全、会话、平台底座与运维

## 1. 负责人定位
- 角色：平台安全工程师。
- 核心目标：认证会话、WebSocket ticket、配置密钥脱敏、上传安全网关、审计日志、限流、健康检查、CI/CD 和部署基线。
- 不负责：AI prompt、评分、教学业务规则、教学设计抽取、前端页面。

## 2. 单文件 Owner

### C 可修改文件
- `api/utils/security.py`
- `api/services/auth_service.py`
- `api/routers/auth.py`
- `api/middleware/auth_middleware.py`
- `api/routers/websocket.py`
- `api/models/config.py`
- `api/services/config_service.py`
- `api/schemas/config.py`
- `api/routers/admin.py`
- `api/main.py`
- `api/middleware/upload_guard.py`
- `api/utils/upload_security.py`
- `api/services/audit_service.py`
- `api/middleware/rate_limit.py`
- `web/nginx.conf`
- `docker-compose.yml`
- `docker-compose.dev.yml`
- `Dockerfile.api`
- `Dockerfile.web`
- `.github/workflows/ci.yml`
- `ops/deploy.md`
- `ops/backup_restore.md`
- `ops/security_baseline.md`
- `api/tests/test_auth_session.py`
- `api/tests/test_websocket_ticket.py`
- `api/tests/test_config_masking.py`
- `api/tests/test_upload_guard.py`
- `api/tests/test_audit_service.py`
- `api/tests/test_rate_limit.py`

### C 禁止修改文件
- `api/agents/*`
- `api/services/report_service.py`
- `api/services/scoring_service.py`
- `api/services/debate_service.py`
- `api/services/assessment_service.py`
- `api/services/analytics_service.py`
- `api/services/teaching_design_service.py`
- `api/services/document_service.py`
- `api/services/knowledge_base.py`
- `api/routers/teacher.py`
- `api/routers/student.py`
- `web/src/**`
- `web/index.html`
- `web/package.json`

## 3. 什么需要等谁做完

### 可以立即开始
- 会话合同。
- WebSocket ticket 合同。
- 配置脱敏合同。
- 上传安全错误合同。
- 审计事件合同。
- 限流和健康检查基础结构。

### 必须等 B/E 明确业务对象后再完善
- 教学设计上传对象。
- 支持材料上传对象。
- 报告重算对象。

用途：
- 审计日志需要知道 `target_type / target_id`。
- 上传安全需要知道业务对象和允许文件类型。

### D 必须等 C 冻结后再接入
- 登录态。
- WebSocket ticket。
- 管理员配置脱敏。
- 上传安全错误提示。

### A 与 C 的依赖
- A 不等待 C。
- C 只要求 A 的 `report_meta` 时间字段和 provider 字段可审计。

## 4. 固定接口，冻结后不能随意改

### AuthSessionContract
```json
{
  "access_token": "string",
  "access_token_expires_in": 0,
  "session_id": "string",
  "user": {
    "id": "string",
    "username": "string",
    "role": "student | teacher | admin"
  },
  "refresh_strategy": "http_only_cookie | server_session",
  "requires_reauth": false
}
```

### WsTicketContract
```json
{
  "ticket": "string",
  "room_id": "string",
  "expires_at": "ISO-8601 datetime",
  "connection_url": "string"
}
```

### MaskedConfigResponse
```json
{
  "configured": true,
  "masked": "sk-****",
  "updated_at": "ISO-8601 datetime",
  "updated_by": "string"
}
```

### UploadGuardErrorContract
```json
{
  "code": "upload_blocked | mime_invalid | extension_invalid | magic_number_invalid | file_too_large | scan_failed",
  "message": "string",
  "request_id": "string"
}
```

### AuditLogEventContract
```json
{
  "event_id": "string",
  "event_type": "auth | config | upload | admin_action | report_regeneration",
  "actor_id": "string",
  "actor_role": "student | teacher | admin | system",
  "target_type": "string",
  "target_id": "string",
  "result": "success | denied | failed",
  "created_at": "ISO-8601 datetime",
  "metadata": {}
}
```

## 5. 需要做的功能
- refresh token 改为服务端可吊销会话。
- 前端不再长期保存 access/refresh token，D 负责接入。
- WebSocket 使用短时 ticket。
- 管理员配置接口禁止回传明文密钥。
- 上传安全支持扩展名、MIME、魔数、大小限制和隔离。
- 审计覆盖登录、上传、配置、管理员操作、报告重算。
- 基础限流和健康检查。
- metrics、CI/CD、部署说明、备份恢复说明。

## 6. 架构推荐
- `auth_service.py` 管理会话生命周期。
- `auth_middleware.py` 只做认证上下文注入。
- `websocket.py` 只接受 ticket，不接受 access token query。
- `config_service.py` 统一做密钥脱敏和保存。
- `upload_guard.py` 在路由前统一做文件安全检查。
- `audit_service.py` 统一记录安全事件。
- `rate_limit.py` 做基础 IP/用户限流。
- `main.py` 只注册中间件、路由、健康检查和 metrics。

## 7. 测试要求
- 登录、刷新、登出当前设备、登出所有设备。
- WebSocket ticket 过期和非法 ticket。
- 配置接口无明文密钥回传。
- 上传非法扩展名、非法 MIME、魔数不符、超大文件。
- 审计事件生成。
- 限流命中。

## 8. 验收标准
- C 冻结接口后，D 可以独立完成安全前端接入。
- B/E 上传业务不自行实现安全检查。
- C 不修改任何业务服务和前端文件。
