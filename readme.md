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

#### 后端开发

```bash
cd api

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（创建 .env 文件）

# 运行数据库迁移
alembic upgrade head

# 进入后端项目目录
cd api

# 启动开发服务器
uvicorn main:app --host 0.0.0.0 --port 7860
```

#### 前端开发

```bash
cd web

# 安装依赖
pnpm install

# 配置环境变量（编辑 .env 文件）

# 启动开发服务器
pnpm dev
```

## coze agent
- TOKEN: pat_m06sDcbsp0YoOFrCtEurlIhTlXvEqq4KilKS6p4OqNDuqICOOTLLdv4zIH19UROQ

## bot id
- 反方一辩：7602097016784879631
- 反方二辩：7602097411951525931
- 反方三辩：7602097357069221938
- 反向四辩：7602097537914765358
- 裁判：7602097627471413248


## 🐳 Docker 部署

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+ (可选)
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
# 使用 docker-compose 构建

- docker compose build

## 运行容器
docker compose up -d

docker-compose -p aidebate up -d  --推荐，运行容器
docker-compose -p aidebate down -- 停止容器

# 或者分别构建
docker-compose build api
docker-compose build web
```

### 3. 访问系统

- **前端界面**: http://localhost:5173
- **后端API**: http://localhost:7860
- **API文档**: http://localhost:7860/docs

### 4. 默认管理员账号

```
用户名: admin
密码: Admin123!
```

**⚠️ 重要：首次登录后请立即修改密码！**


### 5、前端配置
.env.development # 开发环境配置文件
.env.production # 生产环境配置文件

注意：开发环境可以不动，已经配置好。但是如果发布到服务器，则一定需要改.env.production文件中的后端地址，因为是通过https访问的。
