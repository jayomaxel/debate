# 辩论教学系统 (Debate Teaching System)

一个基于 AI 的智能辩论教学平台，支持实时辩论、智能评分、语音交互等功能。

## 🏗️ 系统架构

```
辩论教学系统
├── web/          # 前端 (React + TypeScript + Vite)
├── api/          # 后端 (FastAPI + Python)
├── Dockerfile.api   # 后端Docker镜像
├── Dockerfile.web   # 前端Docker镜像
└── docker-compose.yml # 容器编排文件
```

## 🛠️ 技术栈

### 前端
- React 18 + TypeScript
- Vite 构建工具
- TailwindCSS + Radix UI
- Axios + WebSocket

### 后端
- FastAPI (Python 3.11+)
- SQLAlchemy + Alembic
- PostgreSQL 15 (外部)
- Redis 7 (外部)
- LangChain + OpenAI/Coze
- DashScope (阿里云语音服务)


## 💻 开发环境

### 本地开发（不使用Docker）

#### 一键安装依赖（推荐）

在项目根目录运行：

```powershell
.\install-deps.ps1
```

也可以直接双击运行：

```bat
install-deps.bat
```

在 macOS / Linux 上运行：

```bash
chmod +x ./install-deps.sh
./install-deps.sh
```

这个脚本会自动完成以下步骤：

- 创建 `api\venv` 虚拟环境并安装 `api/requirements.txt`
- 安装前端依赖 `web/node_modules`
- 按当前系统尽量自动安装 WeasyPrint 所需的系统依赖

可选参数：

```powershell
.\install-deps.ps1 -SkipBackend
.\install-deps.ps1 -SkipFrontend
.\install-deps.ps1 -SkipWeasyPrintSystem
```

```bash
./install-deps.sh --skip-backend
./install-deps.sh --skip-frontend
./install-deps.sh --skip-weasyprint-system
```

如果你在 Windows 上开发，依赖安装完成后可以直接在根目录启动前后端开发服务：

```powershell
.\start-dev.ps1
```

或：

```bat
start-dev.bat
```

#### 手动安装

##### 后端开发

```bash
cd api

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 安装依赖
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 配置环境变量（创建 .env 文件）

# 运行数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn main:app --host 0.0.0.0 --port 7860 --reload
```

##### 前端开发

```bash
cd web

# 安装依赖
pnpm install

# 如果本机没有 pnpm，可先执行
corepack enable
corepack prepare pnpm@10.11.0 --activate

# 配置环境变量（编辑 .env 文件）

# 启动开发服务器
pnpm dev --host 0.0.0.0
```

## 测试

后端测试现在分为两层：

- 默认单元测试使用 SQLite，通过统一的测试建表 helper 自动避开 PostgreSQL 专属 `ARRAY` 列，避免知识库向量表影响无关测试。
- 依赖 PostgreSQL + `pgvector` 的测试统一使用 `pytest` 标记 `pgvector`，未配置 `TEST_PGVECTOR_DATABASE_URL` 时会自动跳过。

常用命令：

```powershell
cd api
.\venv\Scripts\python.exe -m pytest
```

```powershell
$env:TEST_PGVECTOR_DATABASE_URL = "postgresql://user:password@localhost:5432/aidebate_test"
cd api
.\venv\Scripts\python.exe -m pytest -m pgvector
```

更详细说明见 `api/tests/README.md`。

## coze agent
- TOKEN: pat_m06sDcbsp0YoOFrCtEurlIhTlXvEqq4KilKS6p4OqNDuqICOOTLLdv4zIH19UROQ

## bot id
- 反方一辩：7602097016784879631
- 反方二辩：7602097411951525931
- 反方三辩：7602097357069221938
- 反向四辩：7602097537914765358
- 裁判：7602097627471413248


## 🐳 Docker 部署

### Docker 在本项目中的作用

- 仓库已经提供 `Dockerfile.api`、`Dockerfile.web` 和 `docker-compose.yml`，说明项目支持容器化部署。
- **默认本地开发流程不使用 Docker**。日常开发、联调、改功能时，优先使用 `install-deps.ps1` 和 `start-dev.ps1`。
- Docker 更适合以下场景：部署到服务器、演示环境快速复现、减少不同机器上的环境差异。
- 当前 `docker-compose.yml` **只编排前端和后端** 两个服务，不包含数据库和 Redis。
- PostgreSQL 15+ 与 Redis 7+ 需要提前在外部准备好，并通过环境变量或配置文件指向可用实例。

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- PostgreSQL 15+ (已安装)
- Redis 7+ (已安装)

### 1. 构建镜像

#### 构建后端镜像

```bash
# 构建后端镜像
docker build -f Dockerfile.api -t debate-api:latest .

# 查看镜像
docker images | grep debate-api
```

#### 构建前端镜像

```bash
# 构建前端镜像
docker build -f Dockerfile.web -t debate-web:latest .

# 查看镜像
docker images | grep debate-web
```

#### 一键构建所有镜像（建议该方式）

```bash
# 构建并启动
docker compose up -d --build

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f

# 停止并删除容器
docker compose down
```

如果你更习惯旧命令，也可以使用：

```bash
docker-compose -p aidebate up -d --build
docker-compose -p aidebate down
```

### 2. 访问系统

#### Docker 部署端口

- **前端界面**: http://localhost:8860
- **后端 API**: http://localhost:7860
- **API 文档**: http://localhost:7860/docs

#### 本地开发端口（非 Docker）

- **前端界面**: http://localhost:5173
- **后端 API**: http://localhost:7860
- **API 文档**: http://localhost:7860/docs

### 3. 默认管理员账号

```
用户名: admin
密码: Admin123!
```

**⚠️ 重要：首次登录后请立即修改密码！**


### 4. 前端配置
.env.development # 开发环境配置文件
.env.production # 生产环境配置文件

注意：开发环境可以不动，已经配置好。但是如果发布到服务器，则一定需要改.env.production文件中的后端地址，因为是通过https访问的。
