# 碳硅之辩 AI 辩论教学平台

一个面向课堂与训练场景的 AI 辩论教学系统，覆盖教师组织、学生参赛、实时辩论、语音交互、赛后报告、成长分析与知识库辅助备赛等完整链路。

项目采用前后端分离架构：

- `web/`：React + TypeScript + Vite 前端
- `api/`：FastAPI 后端服务
- `PostgreSQL + pgvector`：业务数据与向量检索
- `Redis`：缓存与实时能力辅助

## 核心能力

- 学生端
  - 登录、加入课堂/比赛、参与实时辩论
  - 文本与语音发言
  - 查看个人报告、历史记录、成长趋势、能力画像
  - 使用知识库问答助手完成备赛准备
- 教师端
  - 班级管理、学生管理
  - 创建和组织辩论活动
  - 查看课堂数据、比赛记录、复盘内容
- 管理端
  - 用户与班级治理
  - 模型、ASR、TTS、向量、邮件等系统配置
  - 知识库文档上传、解析、切片、向量化
- 实时辩论引擎
  - 基于 WebSocket 的房间通信
  - 多阶段流程控制，如立论、盘问、自由辩论、总结陈词
  - AI 辩手、评委、导师等角色化能力接入

## 架构概览

### 前端

前端位于 `web/`，主要面向学生、教师、管理员三类角色，包含：

- 学生指挥中心、比赛大厅、实时辩论页
- 教师控制台、预约/组织页面
- 管理后台配置页
- 数据分析、报告、回放等页面

技术栈以 React 18、TypeScript、Vite、TailwindCSS、Radix UI 为主，测试使用 Vitest。

### 后端

后端位于 `api/`，入口为 `api/main.py`，按业务拆分为多个路由和服务模块：

- `routers/auth.py`：认证、注册、资料相关接口
- `routers/student.py`：学生侧业务
- `routers/teacher.py`：教师侧业务
- `routers/admin.py`：后台管理接口
- `routers/admin_kb.py` / `routers/student_kb.py`：知识库管理与问答
- `routers/voice.py`：ASR / TTS
- `routers/websocket.py`：实时辩论 WebSocket

核心业务主要集中在：

- `services/room_manager.py`：房间状态与参赛者管理
- `services/flow_controller.py`：辩论流程编排
- `services/debate_service.py`：辩论业务处理
- `services/report_service.py`：报告与导出
- `services/rag_service.py`：知识库检索增强问答

## 技术栈

### 前端

- React 18
- TypeScript
- Vite
- TailwindCSS
- Radix UI
- Axios
- Vitest + Testing Library

### 后端

- FastAPI
- Uvicorn
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis
- Pydantic / pydantic-settings

### AI 与多模态

- OpenAI
- CozePy
- Cohere
- LangChain / LangGraph
- DashScope

### 文档与报告

- python-docx
- ReportLab
- openpyxl
- WeasyPrint
- markdown

## 目录结构

```text
debate/
├─ api/                      后端服务
│  ├─ agents/                AI 智能体
│  ├─ alembic/               数据库迁移
│  ├─ models/                数据模型
│  ├─ routers/               API 路由
│  ├─ schemas/               请求/响应模型
│  ├─ services/              核心业务服务
│  ├─ tests/                 后端测试
│  └─ utils/                 工具模块
├─ web/                      前端应用
│  ├─ src/components/        页面与业务组件
│  ├─ src/hooks/             自定义 Hooks
│  ├─ src/lib/               工具与运行时封装
│  ├─ src/services/          前端接口层
│  └─ src/store/             状态与上下文
├─ scripts/                  本地启动辅助脚本
├─ output/                   生成产物
└─ readme.md
```

## 快速开始

### 方式一：本地 Docker 启动整套服务

这是最省心的方式，适合首次运行。

```powershell
docker compose -f docker-compose.local.yml up --build
```

默认端口：

- 前端：`http://localhost:8860`
- 后端：`http://localhost:7860`
- PostgreSQL：`127.0.0.1:5432`
- Redis：`127.0.0.1:6380`

### 方式二：本地开发模式

适合前后端分别调试。

#### 1. 准备环境

- Node.js `>= 18`
- pnpm `>= 10`
- Python `>= 3.10`
- PostgreSQL（建议启用 `pgvector`）
- Redis 7

#### 2. 安装前端依赖

```powershell
cd web
pnpm install
```

#### 3. 安装后端依赖

```powershell
cd api
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
```

#### 4. 启动前后端

仓库根目录提供了 Windows 开发脚本：

```powershell
.\start-dev.ps1
```

该脚本默认会：

- 启动 API：`http://localhost:7861`
- 启动 Web：`http://localhost:8860`
- 连接本地 PostgreSQL：`127.0.0.1:5432/debate_system`
- 连接本地 Redis：`127.0.0.1:6380`

如果你已经通过 Docker 单独启动了数据库和 Redis，这个脚本会很方便。

## 配置说明

后端主要配置位于 `api/config.py`，环境变量支持：

- `DATABASE_URL`
- `REDIS_HOST`
- `REDIS_PORT`
- `SECRET_KEY`
- `PUBLIC_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `ASR_API_KEY`
- `TTS_API_KEY`
- `COZE_API_KEY`

生产环境下需要显式配置数据库、密钥和跨域来源，避免直接使用默认值。

## 测试

### 前端测试

```powershell
cd web
pnpm test:run
```

### 后端测试

```powershell
cd api
.\venv\Scripts\python.exe -m pytest
```

说明：

- 默认后端测试以 SQLite 为主
- 依赖 `pgvector` 的测试需要额外设置 `TEST_PGVECTOR_DATABASE_URL`
- 详情可参考 `api/tests/README.md`

## 部署相关

仓库内提供了多套容器与启动文件：

- `docker-compose.yml`：基础容器编排
- `docker-compose.local.yml`：本地完整联调
- `docker-compose.dev.yml`：开发环境扩展配置
- `Dockerfile.api`：后端镜像
- `Dockerfile.web`：前端镜像
- `Dockerfile.pgvector`：向量数据库相关镜像

## 推荐阅读

如果你需要继续了解项目设计，可以优先查看这些文档：

- `碳硅之辩_完整功能说明.md`
- `碳硅之辩_完整架构说明.md`
- `项目核心代码文档.md`
- `TECH_STACK_ARCHITECTURE.md`
- `web/当前前端逻辑说明.md`

## 当前项目定位

这个仓库不只是一个“在线辩论房间”，而是一套把辩论教学流程产品化的系统：从教师发布任务、学生准备与参赛，到 AI 辅助、数据沉淀、报告生成和成长分析，尽量把教学闭环放进同一套平台中。
