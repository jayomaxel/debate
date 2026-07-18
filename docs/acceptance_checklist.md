# 发布验收清单

每一项必须留下命令输出或 CI 链接。任何一项失败都应停止发布，不得用“其他测试通过”替代。

## 1. PR 快速门禁

- [ ] `python -m compileall -q api` 通过。
- [ ] `python -m pytest -q api/tests -m "not integration and not pgvector and not e2e"` 通过。
- [ ] `pnpm --dir web run lint` 通过。
- [ ] `pnpm --dir web run type-check` 通过。
- [ ] `pnpm --dir web run test:run` 全量通过。
- [ ] `pnpm --dir web run build` 通过。
- [ ] 仓库中没有 `.env`、密钥、测试数据库、上传文件或本地修复方案文档。

## 2. PR 真实依赖门禁

- [ ] 使用 PostgreSQL 16 + pgvector、Redis 7 和空数据库执行 `alembic upgrade head`。
- [ ] Alembic 只有一个 head，020、021、022、023 迁移测试全部通过。
- [ ] PostgreSQL 队列并发、租约恢复和幂等测试通过。
- [ ] Redis 双实例事件转发、presence 和去重测试通过。
- [ ] pgvector 维度不一致会阻断 readiness，重建后检索恢复。
- [ ] 真实文件系统权限测试通过，越权访问统一返回不可枚举的拒绝结果。
- [ ] WeasyPrint 真实 PDF 渲染、缓存、写盘失败和重试测试通过。

## 3. main/release Docker 端到端门禁

执行：

```bash
docker compose -f docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from e2e e2e
```

必须验证以下八条链路：

- [ ] 辩论结束后任务入队，评分完成，报告进入 ready。
- [ ] Worker 中断后租约过期，任务被新 Worker 恢复且只完成一次。
- [ ] 报告可读取，连续三次导出 PDF 只渲染一次且没有临时文件残留。
- [ ] PDF 渲染或写盘失败返回稳定错误码，后续重试可成功。
- [ ] 向量维度不一致时 readiness 失败，重建后 1024/1536 检索均恢复。
- [ ] 两个实例之间麦克风互斥、事件广播、presence 和故障转移正常。
- [ ] 非所有者下载报告、教学材料或音频均被拒绝。
- [ ] fallback 分数可在报告中标识，但不进入画像、均分、排名和训练数据。

然后启动双 API 实例和网关并冒烟：

```bash
docker compose -f docker-compose.test.yml --profile stack up -d --build --wait web
bash scripts/run-production-smoke.sh http://127.0.0.1:18860
docker compose -f docker-compose.test.yml --profile stack down --volumes --remove-orphans
```

## 4. 受控真实供应商门禁

仅允许在 GitHub `workflow_dispatch` 或受控发布环境运行。密钥只能由 CI Secret 注入，不能写入命令、日志或仓库。

- [ ] `PRODUCTION_SMOKE_BASE_URL` 指向待发布环境。
- [ ] 可选登录凭据三项同时提供：账号、密码、用户类型。
- [ ] `PROVIDER_BASE_URL`、`PROVIDER_API_KEY`、`PROVIDER_MODEL` 三项同时提供。
- [ ] 应用健康检查、可选登录、真实模型最小 completion 全部通过。
- [ ] 输出中不包含 access token、API key 或完整供应商响应。

## 5. 数据与回滚确认

- [ ] 升级前已完成数据库备份并验证可恢复。
- [ ] 020～023 的迁移耗时、锁等待和表大小已评估。
- [ ] 023 升级后抽查 fallback、legacy_unknown、validated 分类及分析资格。
- [ ] 回滚镜像、数据库回滚决策人和维护窗口已明确。
- [ ] 发布后检查 `/healthz`、`/api/health`、登录、报告、文件权限和 WebSocket。

## 6. 发布后业务检查

- [ ] 登录、刷新、登出、全设备登出通过。
- [ ] 教师建赛、学生入赛、WebSocket 连接、发言、结束比赛通过。
- [ ] 报告读取、报告重算、教师摘要通过。
- [ ] 管理端模型、Coze、ASR、TTS、向量、邮件配置保存与读取通过。
- [ ] 失败场景可定位：日志、健康检查、错误响应足够明确。

## 7. Work Package E

- [ ] The class teaching-design endpoint returns `TeachingDesignSchema` with an active version and version history.
- [ ] Each version uses the frozen extraction fields and one of: `extracting`, `ready`, `needs_review`, `failed`.
- [ ] Corrected teaching designs preserve the source version and make the correction the active version.
- [ ] Support documents retain a purpose label, summary result, summary quality, and failure state.
- [ ] Knowledge snippets are filtered by debate phase and are present in AI debate prompts.
- [ ] Published API examples and test fixtures use the same fields and values.

## 8. 验收记录

| 项目 | 结果 | CI/日志链接 | 验收人 | 时间 |
| --- | --- | --- | --- | --- |
| PR 快速门禁 |  |  |  |  |
| PR 真实依赖门禁 |  |  |  |  |
| Docker E2E |  |  |  |  |
| 真实供应商冒烟 |  |  |  |  |
| 生产发布后检查 |  |  |  |  |
