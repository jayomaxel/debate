# 安全基线

## 基线目标

工作包 C 负责的安全基线覆盖认证、会话、WebSocket ticket、上传安全、配置脱敏、审计、限流、健康检查和发布底座。

## 环境变量与密钥

- 生产环境必须显式设置 `SECRET_KEY`，禁止使用默认值。
- `DATABASE_URL`、第三方模型密钥、邮箱密码等敏感值不得写入仓库。
- `PUBLIC_BASE_URL` 必须与实际访问域名一致。
- `ALLOWED_ORIGINS` 必须显式列出可信前端来源，避免生产环境继续使用宽泛值。

## 认证与会话

- 登录与刷新统一返回冻结后的 `AuthSessionContract`。
- refresh 必须依赖服务端仍然有效的 session。
- 支持单设备登出与全设备登出。
- WebSocket 连接只接受短期 ticket，不再接受 query string access token。

## 上传安全

- 上传入口统一经过 `UploadGuardMiddleware`。
- 至少校验扩展名、MIME、魔数和文件大小。
- 非法文件统一返回冻结合同 `UploadGuardErrorContract`。
- 隔离目录 `api/uploads/quarantine` 必须存在，并纳入备份范围。

## 配置与密钥展示

- 管理端 GET 配置接口只返回 `configured`、`masked`、`updated_at`、`updated_by`。
- 配置更新成功后不回显明文密钥。
- 配置变更应写入审计日志。

## 审计与限流

- 登录、刷新、登出、ws ticket 签发、配置修改、上传拦截、限流命中必须产出审计事件。
- 登录、上传和高频报告接口必须启用基础限流。
- 限流命中返回 `429`，并带 `Retry-After` 与 `X-RateLimit-*` 头。

## 网关与暴露面

- 对外仅暴露 `web` 网关端口。
- `api` 建议只在容器内部网络暴露，由 Nginx 反向代理访问。
- `/metrics` 仅允许本机或内网采集器访问，不应对公网开放。
- Nginx 需启用基本安全头和上传体积上限。

## 运维要求

- 每次发布前运行工作包 C 的后端测试、前端类型检查和前端构建。
- 每日执行数据库备份，上传目录与 Redis AOF 至少保留最近 7 天。
- 安全事件排查优先查看：
  - `/api/admin/audit/events`
  - API 日志
  - Nginx 访问日志
  - Metrics 指标趋势
