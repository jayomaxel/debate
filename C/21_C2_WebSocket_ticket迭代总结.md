# C2 WebSocket Ticket 迭代总结

## 本轮目标

补齐截图反馈中的 C2：新增真实 `/api/auth/ws-ticket`，WebSocket 连接改为 `?ticket=`，并拒绝旧的 `?token=`。

## 修改逻辑

- `api/routers/auth.py`
  - 新增 `GET /api/auth/ws-ticket`，依赖当前登录态签发短时 ticket。
  - 返回冻结后的 `WsTicketContract`，包含 `ticket`、`room_id`、`expires_at`、`connection_url`。
- `api/routers/websocket.py`
  - WebSocket 入口只接受 `ticket` 查询参数。
  - 如果缺少 ticket、传入旧 `token`、ticket 过期、房间不匹配或重复消费，全部拒绝连接。
- `api/services/auth_service.py` 和 `api/utils/security.py`
  - ticket 绑定 `room_id`、`user_id`、`session_id`。
  - ticket 默认短时有效、单次消费。
  - 消费 ticket 时会继续检查服务端 session 是否仍有效。
- `web/src/lib/websocket-client.ts`
  - 前端建连前先调用 `/api/auth/ws-ticket`。
  - WebSocket URL 改为 `?ticket=`。
  - 重连时重新签发 ticket，不复用旧 ticket。
- `web/src/hooks/use-websocket.ts`
  - 保留登录态检查，但不再把 access token 传给 WebSocket URL 构造。

## 对应功能

- access token 不再暴露在 WebSocket query string 中。
- 单个 ticket 只能连接一次，降低 URL 泄露后的复用风险。
- ticket 绑定房间，不能拿 A 房间 ticket 连接 B 房间。
- 已登出的 session 即使持有旧 ticket，也不能继续进入 WebSocket。
- 前端真实接入已同步，不会因为后端拒绝 `?token=` 而连不上。

## 验证结果

已执行 C 包专项测试：

```bash
python -m pytest api/tests/test_auth_session.py api/tests/test_websocket_ticket.py api/tests/test_config_masking.py api/tests/test_upload_guard.py api/tests/test_audit_service.py api/tests/test_rate_limit.py api/tests/test_health_check.py -q
```

结果：`43 passed`。

额外检查：

```bash
rg "\?token=|token=\$|token=\{|buildDebateWebSocketUrl\([^\)]*," web\src api\routers\websocket.py api\tests\test_websocket_ticket.py -n
```

结果：运行时代码无 `?token=` 建连残留，仅保留测试用例验证旧 token query 会被拒绝。

前端类型检查：

```bash
cd web
npx tsc --noEmit
```

结果：通过。
