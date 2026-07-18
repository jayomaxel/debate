# 部署与回滚说明

## 发布前提

- 使用 Docker Engine 24+ 和 Docker Compose Plugin。
- `.env.deploy` 至少配置 `POSTGRES_PASSWORD`、`DATABASE_URL`、`SECRET_KEY`、`PUBLIC_BASE_URL`、`ALLOWED_ORIGINS`。
- `SECRET_KEY` 使用独立长随机值，`DEBUG=false`，生产来源域名必须显式列出。
- PostgreSQL 已备份并完成一次恢复演练。
- [发布验收清单](../docs/acceptance_checklist.md)中的 PR 与 Docker 门禁已经通过。

## 数据库升级

当前发布包含以下连续迁移：

- 020：持久化后台任务、唯一去重键、租约和失败状态。
- 021：知识文档发布状态。
- 022：权威辩论运行时状态及版本号。
- 023：评分来源、质量、重试、失败码和分析资格。

先在与生产同版本的备份库执行：

```bash
docker compose --env-file .env.deploy -f docker-compose.yml run --rm api alembic upgrade head
```

确认只有一个 head：

```bash
docker compose --env-file .env.deploy -f docker-compose.yml run --rm api alembic heads
```

023 会保守地将无法证明可信的历史评分标为 `legacy_unknown` 且排除分析；明确的降级评分标为 `fallback`。升级后必须抽查分类数量，不能直接把未知历史数据批量改成可信。

## 部署

```bash
docker compose --env-file .env.deploy -f docker-compose.yml up -d --build
docker compose --env-file .env.deploy -f docker-compose.yml ps
```

若部署多个 API 实例，所有实例必须连接同一 PostgreSQL 和 Redis，并设置：

```env
REALTIME_MULTI_INSTANCE=true
INSTANCE_ID=<每个实例唯一值>
```

报告、音频和教学材料目录需要共享持久存储；不能让不同实例使用各自的临时容器磁盘。

## 发布后检查

Linux/macOS：

```bash
SMOKE_BASE_URL=https://your-domain.example.com \
  bash scripts/run-production-smoke.sh
```

Windows：

```powershell
$env:SMOKE_BASE_URL = "https://your-domain.example.com"
./scripts/run-production-smoke.ps1
```

提供 `SMOKE_ACCOUNT`、`SMOKE_PASSWORD`、`SMOKE_USER_TYPE` 时脚本还会验证登录。三项必须同时设置。

真实供应商检查只在受控环境执行，同时提供 `PROVIDER_BASE_URL`、`PROVIDER_API_KEY`、`PROVIDER_MODEL`。脚本只输出通过/失败，不输出密钥或完整响应。

## 故障处理

- `/api/health` 显示数据库失败：停止放量，检查连接、迁移 head 和数据库锁。
- Redis 或 realtime bridge 未就绪：停止多实例流量，检查 Redis 连通性与各实例 `INSTANCE_ID`。
- 向量 readiness 为 mismatch：停止知识检索流量，执行受控重建，完成前不得绕过 readiness。
- 报告任务积压：检查 lease、dead-letter、Worker 日志和磁盘容量，不要直接删除任务行。
- fallback 突增：检查供应商可用性；fallback 只能展示，不能人工改为 analytics eligible。

## 回滚

代码回滚与数据库回滚分开决策。020～023 均包含新状态数据，优先采用向前修复：

1. 停止新流量和后台 Worker，保留数据库现场。
2. 记录当前 Alembic revision、队列状态、向量重建状态和评分分类数量。
3. 若旧镜像能兼容新增列，仅回滚镜像，不降级数据库。
4. 只有确认旧代码无法运行且已完成备份时，才按 `023 -> 022 -> 021 -> 020 -> 019` 顺序逐级降级。
5. 降级 023 会删除 provenance 字段，可能永久丢失 fallback 审计与分析资格信息；必须先导出相关列。
6. 降级 022 前必须停止全部 API 实例，避免运行时状态重新写入。
7. 降级 020 前必须处理运行中、重试中和 dead-letter 任务，否则任务恢复信息会丢失。

执行单级降级示例：

```bash
docker compose --env-file .env.deploy -f docker-compose.yml run --rm api alembic downgrade 022
```

回滚后重新执行健康检查、登录、报告读取、私有文件鉴权和 WebSocket 冒烟，并记录数据恢复结果。
