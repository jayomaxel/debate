# 部署说明

## 目标

本文档说明如何基于仓库根目录的 `docker-compose.yml` 部署工作包 C 依赖的后端安全能力、前端网关和基础运维组件。

## 前提条件

- 已安装 Docker Engine 24+ 和 Docker Compose Plugin
- 目标主机可以拉取 PostgreSQL、Python、Node、Redis 相关镜像
- 已准备部署环境变量：
  - `POSTGRES_PASSWORD`
  - `DATABASE_URL`
  - `SECRET_KEY`
  - `PUBLIC_BASE_URL`
  - `ALLOWED_ORIGINS`

## 持久化目录

- PostgreSQL 数据保存在 `pgdata` volume
- Redis AOF 数据保存在 `redisdata` volume
- API 日志目录为 `./api/logs`
- 上传与隔离目录为 `./api/uploads`

## 首次部署

1. 在仓库根目录准备 `.env.deploy`
2. 可先复制 `.env.deploy.example` 为 `.env.deploy`
3. 至少写入以下内容：

```env
POSTGRES_PASSWORD=replace-with-strong-password
DATABASE_URL=postgresql://pgvector:replace-with-strong-password@db:5432/debate_system
SECRET_KEY=replace-with-long-random-secret
PUBLIC_BASE_URL=https://your-domain.example.com
ALLOWED_ORIGINS=https://your-domain.example.com
```

4. 主 `docker-compose.yml` 已开启必填变量校验；如果不带 `--env-file .env.deploy` 直接执行，会在 Compose 解析阶段被拦截。这是为了避免占位密码或本机旧数据卷状态导致的假故障。
5. 启动服务：

```bash
docker compose --env-file .env.deploy -f docker-compose.yml up -d --build
```

6. 检查容器状态：

```bash
docker compose --env-file .env.deploy -f docker-compose.yml ps
```

## 部署后校验

- API 健康检查：

```bash
docker compose --env-file .env.deploy -f docker-compose.yml exec api curl -fsS http://localhost:7860/health
```

- 网关健康检查：

```bash
curl -fsS http://127.0.0.1:8860/healthz
```

- 同域 API 代理检查：

```bash
curl -fsS http://127.0.0.1:8860/api/health
```

- Metrics 检查：
  - `GET /metrics` 应可返回 Prometheus 指标
  - 默认仅允许本机或 RFC1918 私网访问

## 升级发布

1. 拉取新代码
2. 先执行本地或 CI 校验
3. 重建并滚动拉起：

```bash
docker compose --env-file .env.deploy -f docker-compose.yml up -d --build
```

4. 再次执行健康检查，并补做登录、上传、安全审计、WebSocket ticket 等关键路径冒烟验证

## 回滚

1. 回退到上一版代码或镜像标签
2. 使用同一份 `.env.deploy` 重新拉起：

```bash
docker compose --env-file .env.deploy -f docker-compose.yml up -d --build
```

3. 如果数据库结构发生变化，先确认 Alembic 迁移是否可逆
4. 回滚后至少验证：
  - `/health`
  - `/api/health`
  - `/healthz`
  - 登录刷新链路
  - 上传安全拦截

## 开发环境

本地联调请优先使用 `docker-compose.dev.yml`：

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

默认访问地址：

- API: `http://127.0.0.1:7860`
- Web: `http://127.0.0.1:8860`
- PostgreSQL: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`
