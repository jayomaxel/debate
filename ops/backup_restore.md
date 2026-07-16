# 备份与恢复说明

## 备份范围

工作包 C 上线后，至少需要覆盖以下数据面：

- PostgreSQL 业务库
- `./api/uploads` 上传与隔离目录
- `redisdata` volume 中的 Redis AOF

说明：

- Redis 主要承载会话、限流计数、审计事件缓存和降级数据，属于可恢复但建议保留的数据层。
- `api/logs` 建议按日志平台策略单独收集，不作为恢复主数据源。

## PostgreSQL 备份

### 在线逻辑备份

```bash
docker compose --env-file .env.deploy -f docker-compose.yml exec -T db \
  pg_dump -U "${POSTGRES_USER:-pgvector}" "${POSTGRES_DB:-debate_system}" > backup.sql
```

### 备份频率建议

- 每日全量逻辑备份 1 次
- 重要配置变更前追加一次手工备份
- 保留最近 7 天可快速恢复版本

## 上传目录备份

```bash
tar -czf uploads-backup.tar.gz api/uploads
```

建议和数据库备份使用同一时间点命名，以便恢复时对齐。

## Redis 数据备份

### 导出 volume

```bash
docker run --rm -v debate_redisdata:/data -v "${PWD}:/backup" alpine \
  tar -czf /backup/redis-backup.tar.gz -C /data .
```

说明：

- volume 名称可能因 Compose project name 不同而变化，执行前先用 `docker volume ls` 确认。
- Redis 不是唯一真源，但会话、限流和审计的短期状态保留后可减少恢复期抖动。

## 恢复流程

### 1. 停止写流量

- 暂停外部入口或先停止 `web` 与 `api` 容器。

### 2. 恢复数据库

```bash
cat backup.sql | docker compose --env-file .env.deploy -f docker-compose.yml exec -T db \
  psql -U "${POSTGRES_USER:-pgvector}" "${POSTGRES_DB:-debate_system}"
```

### 3. 恢复上传目录

```bash
tar -xzf uploads-backup.tar.gz
```

确认恢复后的目录至少包含：

- `api/uploads/audio`
- `api/uploads/asr_tmp`
- `api/uploads/reports`
- `api/uploads/quarantine`

### 4. 恢复 Redis

```bash
docker run --rm -v debate_redisdata:/data -v "${PWD}:/backup" alpine \
  sh -c "rm -rf /data/* && tar -xzf /backup/redis-backup.tar.gz -C /data"
```

### 5. 重新启动服务

```bash
docker compose --env-file .env.deploy -f docker-compose.yml up -d
```

## 恢复后检查

- `/health` 返回 healthy 或 degraded，而不是 unhealthy。
- `/metrics` 可读取 `debate_database_up`、`debate_redis_up`。
- 登录后 refresh 正常。
- 上传安全网关能放行合法文件、拦截非法文件。
- `/api/admin/audit/events` 可查询恢复后的审计记录或降级缓存记录。
