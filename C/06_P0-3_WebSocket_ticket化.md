# P0-3 WebSocket ticket 化

## 本轮目标

完成工作包 C 的 `P0-3`：

- 提供真实的 WebSocket ticket 签发接口
- WebSocket 连接改为使用 `ticket`
- 不再接受 `?token=` 直接进入 WebSocket
- ticket 绑定 `room_id`
- ticket 短时有效且单次消费
- 修复旧 access token 登出“假成功”问题

## 修改文件

- `api/utils/security.py`
- `api/services/auth_service.py`
- `api/routers/auth.py`
- `api/routers/websocket.py`
- `api/tests/test_websocket_ticket.py`
- `api/tests/test_auth_session.py`

## 代码逻辑

### 1. 新增真实 ws ticket 存储与消费能力

在 `api/utils/security.py` 中新增：

- `persist_ws_ticket`
- `get_ws_ticket`
- `consume_ws_ticket`
- `revoke_ws_ticket`

实现策略：

- Redis 优先
- Redis 不可用时降级为进程内内存
- ticket 默认 5 分钟过期
- ticket 默认单次使用

ticket 中绑定了：

- `ticket`
- `room_id`
- `user_id`
- `user_type`
- `session_id`
- `auth_iat`
- `expires_at`

### 2. 真实签发接口接入登录态

在 `api/routers/auth.py` 中新增：

- `GET /api/auth/ws-ticket`

它依赖当前登录态，通过 `verify_token_middleware` 取得：

- 当前用户
- 当前 `session_id`
- 当前 token 的 `iat`

然后调用 `AuthService.issue_ws_ticket()` 生成短时 ticket，返回冻结的 `WsTicketContract`。

### 3. WebSocket 改为只认 ticket

在 `api/routers/websocket.py` 中：

- 新增 `/ws/{room_id}` 路由
- 保留 `/ws/debate/{room_id}` 作为兼容别名
- 连接鉴权从 `token` 改成 `ticket`

现在的规则是：

- 没有 `ticket`：拒绝连接
- 只有 `token`：明确拒绝连接
- ticket 无效、过期、错房间：拒绝连接
- ticket 验证通过后才允许继续进入 join room 流程

### 4. ticket 与会话状态联动

`consume_ws_ticket()` 在消费时会继续校验：

- 如果 ticket 绑定了 `session_id`，则该服务端 session 必须仍然有效
- 如果是旧 token 签发的 ticket，则会检查该用户的 legacy token 是否已被登出失效

这样可以避免：

- 登录后拿到 ticket，但会话已经被登出，仍然继续进 WebSocket

### 5. 顺手修复旧 token 登出假成功

此前旧 access token 没有 `session_id`，调用 `/logout` 会出现：

- 返回成功
- 但 token 实际不失效

本轮新增了 legacy access token 撤销时间标记：

- `revoke_legacy_access_tokens`
- `get_legacy_access_revoked_at`
- `is_legacy_access_token_valid`

现在：

- 旧 token 调 `/logout` 后会被真正判定为失效
- 旧 token 调 `/logout-all` 后也会失效

## 对应功能

本轮完成后，工作包 C 现在已经具备：

- 真实 ws ticket 签发
- WebSocket 不再暴露 access token query
- ticket 单次消费
- ticket 过期控制
- ticket 房间绑定
- 旧 token 登出失效修复

## 验证结果

执行：

```bash
cd api
python -m pytest tests/test_websocket_ticket.py tests/test_auth_session.py -q
```

结果：

- `18 passed`

覆盖验证：

- mock ticket 合同仍可访问
- 真实 `GET /api/auth/ws-ticket` 返回冻结结构
- 缺少 ticket 不能连
- `?token=` 不能连
- 有效 ticket 可以连
- 同一 ticket 第二次不能再连
- 错房间 ticket 不能连
- 过期 ticket 不能连
- 旧 access token 登出后真正变为 `401`

## 当前状态

- `P0-1` 已完成
- `P0-2` 已完成
- `P0-3` 已完成

## 下一步建议

进入 `P1-1`：

- 把真实管理员配置接口切到“非明文 secret 返回”
- 同时尽量保留现有前端兼容行为，避免直接把页面表单打挂
