# P2-3 CI/CD

## 本轮目标

补齐最小自动化质量门禁，确保工作包 C 的关键后端能力和前端构建在合并前有基础校验。

## 修改文件

- `.github/workflows/ci.yml`

## 代码逻辑

- 新建 GitHub Actions 工作流 `ci.yml`。
- 拆成两个 job：
  - `backend-tests`
  - `frontend-build`
- 后端 job：
  - 安装 Python 3.11
  - 安装 `api/requirements.txt`
  - 运行工作包 C 相关测试集合：
    - `test_upload_guard.py`
    - `test_audit_service.py`
    - `test_rate_limit.py`
    - `test_auth_session.py`
    - `test_websocket_ticket.py`
    - `test_config_masking.py`
    - `test_health_check.py`
- 前端 job：
  - 安装 Node 20
  - 启用 pnpm
  - 运行 `pnpm install --frozen-lockfile`
  - 运行 `pnpm type-check`
  - 运行 `pnpm build`

## 对应功能

- 后端关键安全能力改坏时可以被 CI 及时拦住。
- 前端类型问题和构建问题能在合并前暴露。
- 本地验证命令与 CI 质量门禁保持一致，便于排障。

## 风险/未完成项

- 当前 CI 还是最小版，没有覆盖完整集成测试和镜像发布流程。
- 如果后续要引入自动部署，建议在当前 workflow 基础上拆分 build 与 deploy 阶段。
