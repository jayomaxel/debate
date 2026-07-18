# 项目交付检查清单

本清单用于每次合并、演示部署或正式上线前确认项目不是“功能能跑一次”，而是具备可复现、可回滚、可排错的交付状态。

## 1. 代码与依赖

- [ ] 后端依赖通过 `api/requirements.txt` 安装成功。
- [ ] 后端依赖有锁定策略，避免不同机器解析到不兼容版本。
- [ ] 前端依赖通过 `web/pnpm-lock.yaml` 和 `pnpm install --frozen-lockfile` 安装成功。
- [ ] 前端生产构建必须执行 `pnpm run build`，包含 TypeScript 检查。
- [ ] 本地无需要提交的 `.env`、数据库、日志、上传文件和临时缓存。

## 2. 数据库

- [ ] 所有新增模型都有对应 Alembic migration。
- [ ] `alembic upgrade head` 能从空库成功执行。
- [ ] migration 链只有一个 head。
- [ ] 生产库升级前已备份。
- [ ] 涉及字段删除、表删除或数据重写时，有回滚说明。

## 3. 后端质量门禁

- [ ] `python -m compileall -q api` 通过。
- [ ] `python -m pytest api/tests -m "not integration"` 通过。
- [ ] 外部服务相关测试使用 mock 或显式标记。
- [ ] WebSocket ticket 合同测试通过。
- [ ] 上传、鉴权、配置脱敏、报告生成等关键路径有覆盖。

## 4. 前端质量门禁

- [ ] `pnpm run type-check` 通过。
- [ ] `pnpm run test:run` 通过。
- [ ] `pnpm run build` 通过。
- [ ] 前端 WebSocket 不再拼接 access token query。
- [ ] 前端配置页面不展示真实 API key/token。

## 5. 安全与配置

- [ ] 生产环境 `SECRET_KEY` 已显式配置，且不是默认值。
- [ ] 生产环境 `DEBUG=false`。
- [ ] 生产环境 `ALLOWED_ORIGINS` 只包含明确域名，不包含 `*`。
- [ ] 管理端配置读取接口不返回明文 `api_key`、`api_token`、`smtp_password`。
- [ ] 数据库存储的第三方密钥已有加密或密钥管理方案。
- [ ] WebSocket 使用短时单次 ticket，不接受 access token query。
- [ ] 文件上传有大小限制、类型白名单和错误响应。

## 6. 部署与运行

- [ ] `docker compose -f docker-compose.local.yml up --build` 能启动完整本地栈。
- [ ] `docker-compose.yml` 的使用场景已明确：外部数据库还是完整栈。
- [ ] `/health` 或 `/api/health` 能正确反映数据库和 Redis 状态。
- [ ] 生产镜像启动命令、端口、卷挂载和健康检查已确认。
- [ ] 上传目录、日志目录、报告目录有持久化策略。

## 7. 数据与隐私

- [ ] `/uploads` 中的资源已区分公开资源和受保护资源。
- [ ] 学生报告、音频、教学材料不通过可猜 URL 暴露敏感内容。
- [ ] 日志不打印完整 token、API key、密码、学生隐私字段。
- [ ] 本地 `api/.env` 和生产密钥已做提交前清点。

## 8. 发布后检查

- [ ] 登录、刷新、登出、全设备登出通过。
- [ ] 教师建赛、学生入赛、WebSocket 连接、发言、结束比赛通过。
- [ ] 报告读取、报告重算、教师摘要通过。
- [ ] 管理端模型、Coze、ASR、TTS、向量、邮件配置保存与读取通过。
- [ ] 失败场景可定位：日志、健康检查、错误响应足够明确。

## 9. Work Package E

- [ ] The class teaching-design endpoint returns `TeachingDesignSchema` with an active version and version history.
- [ ] Each version uses the frozen extraction fields and one of: `extracting`, `ready`, `needs_review`, `failed`.
- [ ] Corrected teaching designs preserve the source version and make the correction the active version.
- [ ] Support documents retain a purpose label, summary result, summary quality, and failure state.
- [ ] Knowledge snippets are filtered by debate phase and are present in AI debate prompts.
- [ ] Published API examples and test fixtures use the same fields and values.
