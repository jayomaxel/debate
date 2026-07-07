# C0 mock 响应示例

## AuthSessionContract

接口：

- `GET /api/auth/contracts/session/mock?user_type=teacher`

示例：

```json
{
  "access_token": "string",
  "access_token_expires_in": 3600,
  "session_id": "string",
  "user": {
    "id": "string",
    "username": "teacher_demo",
    "role": "teacher"
  },
  "refresh_strategy": "server_session",
  "requires_reauth": false
}
```

## WsTicketContract

接口：

- `GET /api/auth/ws-ticket/mock?room_id=room_demo_001`

示例：

```json
{
  "ticket": "string",
  "room_id": "room_demo_001",
  "expires_at": "2026-06-20T08:30:00Z",
  "connection_url": "/ws/room_demo_001?ticket=string"
}
```

## UploadGuardErrorContract

接口：

- `GET /api/auth/contracts/upload-error/mock`

示例：

```json
{
  "code": "mime_invalid",
  "message": "Only PDF and DOCX uploads are allowed for this object.",
  "request_id": "req_contract_upload_demo"
}
```

## AuditLogEventContract

接口：

- `GET /api/auth/contracts/audit-event/mock`

示例：

```json
{
  "event_id": "audit_contract_demo",
  "event_type": "auth",
  "actor_id": "teacher_demo_id",
  "actor_role": "teacher",
  "target_type": "session",
  "target_id": "session_demo_id",
  "result": "success",
  "created_at": "2026-06-20T08:30:00Z",
  "metadata": {
    "action": "login"
  }
}
```

## MaskedConfigResponse

接口：

- `GET /api/admin/config/contracts/masked/mock`

示例：

```json
{
  "model": {
    "configured": true,
    "masked": "sk-****1234",
    "updated_at": "2026-06-20T08:30:00Z",
    "updated_by": "system"
  },
  "coze": {
    "configured": true,
    "masked": "pat****1234",
    "updated_at": "2026-06-20T08:30:00Z",
    "updated_by": "system"
  }
}
```
