# P2-1 健康检查与 Metrics

## 本轮目标

在现有健康检查基础上补齐最小 metrics 入口，便于部署后快速判断数据库、Redis 和服务启动状态。

## 修改文件

- `api/main.py`
- `api/tests/test_health_check.py`

## 代码逻辑

- 保留 `/health` 和 `/api/health` 两个健康检查入口。
- 在 `api/main.py` 补充运行态探测函数：
  - 数据库连通性
  - Redis 可用性
- 暴露 `/metrics`，输出最小 Prometheus 指标：
  - `debate_database_up`
  - `debate_redis_up`
  - `debate_redis_enabled`
  - `debate_service_start_time_seconds`
  - `debate_service_info`
- 上传安全、审计、限流模块各自的计数器也统一注册到同一监控面。
- 在测试里补充健康检查与 metrics 的最小验证。

## 对应功能

- 运维可以快速区分 healthy、degraded 和 unhealthy。
- Prometheus 或手工排障可以直接读取服务基本状态。
- 工作包 C 的安全中间件和审计能力都有了统一观测入口。

## 风险/未完成项

- 当前没有对 `/metrics` 做应用层鉴权，默认依赖网关与网络隔离。
- 由于仓库的数据库初始化约束，完整应用启动测试仍需依赖特定数据库环境。
