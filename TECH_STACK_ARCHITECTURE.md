# 辩论智能体技术栈与技术架构文档

## 1. 文档定位

本文档用于说明“AI 辩论智能体教学平台”的核心技术栈、系统分层、智能体架构、实时辩论链路、语音链路、知识库增强链路以及部署运行方式。它面向开发、交付、运维和后续二次开发人员，帮助快速理解系统由哪些技术组成，以及这些技术如何共同支撑“多人实时辩论 + AI 智能体陪练 + 赛后评价分析”的完整业务闭环。

## 2. 系统总体架构

系统采用前后端分离架构：

- 前端位于 `web/`，负责学生端、教师端、管理员端和实时辩论房间的交互体验。
- 后端位于 `api/`，负责认证鉴权、业务编排、WebSocket 实时通信、AI 智能体调用、语音能力、知识库检索和数据持久化。
- 数据层以 PostgreSQL 为核心，配合 pgvector 支持知识库向量检索，Redis 作为缓存和实时能力辅助组件。
- AI 能力层由自定义 Agent、Coze Bot、OpenAI 兼容大模型、DashScope 语音服务、LangChain/LangGraph 与 RAG 服务共同组成。
- 部署层提供 Dockerfile 与 Docker Compose，支持 API、Web、PostgreSQL、Redis 的容器化运行。

典型调用链路如下：

```text
浏览器前端
  -> REST API / WebSocket
  -> FastAPI 路由层
  -> 业务服务层 / 实时流程控制层
  -> Agent / ASR / TTS / RAG / 数据库
  -> WebSocket 广播或 REST 响应
  -> 前端刷新辩论状态、语音播放、报告展示
```

## 3. 前端技术栈

| 技术 | 用途 |
| --- | --- |
| React 18 | 构建学生、教师、管理员和辩论房间页面 |
| TypeScript | 提升前端类型约束和可维护性 |
| Vite | 前端开发服务器与构建工具 |
| Tailwind CSS | 原子化样式和响应式布局 |
| Radix UI | 对话框、下拉框、Tabs、Tooltip 等基础交互组件 |
| lucide-react | 图标库 |
| Axios | REST API 请求封装 |
| WebSocket | 实时辩论状态、发言、抢麦、阶段推进等消息传输 |
| Vitest / Testing Library / fast-check | 单元测试、组件测试和属性测试 |

前端主要承担以下职责：

- 按角色组织页面：学生端、教师端、管理员端。
- 展示实时辩论房间状态：当前阶段、发言人、倒计时、抢麦状态、发言记录。
- 接入文本发言、语音发言、音频播放和 AI 发言展示。
- 调用报告、分析、知识库问答、班级和用户管理等 REST API。
- 通过服务层文件，如 `web/src/services/*.ts`，隔离页面组件与接口细节。

## 4. 后端技术栈

| 技术 | 用途 |
| --- | --- |
| FastAPI | 后端 Web 框架，提供 REST API 和 WebSocket |
| Uvicorn | ASGI 运行服务器 |
| SQLAlchemy 2.x | ORM 与数据库访问 |
| Alembic | 数据库迁移管理 |
| PostgreSQL | 主业务数据库 |
| pgvector | 知识库向量存储与相似度检索 |
| Redis | 缓存、实时能力和运行期辅助组件 |
| Pydantic / pydantic-settings | 请求响应模型与配置管理 |
| python-jose | JWT 令牌签发与校验 |
| passlib / bcrypt | 密码哈希与账号安全 |
| httpx | 异步 HTTP 调用外部 AI、语音和模型服务 |
| pytest / pytest-asyncio / hypothesis | 后端测试体系 |

后端入口为 `api/main.py`，启动时会完成：

- 初始化数据库引擎和表结构。
- 加载默认模型配置与 Coze 配置。
- 对齐知识库向量表结构。
- 初始化 Redis。
- 注册认证、教师、学生、管理员、知识库、语音和 WebSocket 路由。
- 挂载上传目录 `/uploads`。

## 5. 后端分层设计

后端采用“路由层 + 服务层 + 智能体层 + 数据层 + 工具层”的组织方式。

### 5.1 路由层

路由位于 `api/routers/`：

| 路由文件 | 职责 |
| --- | --- |
| `auth.py` | 登录、注册、用户资料、密码修改等认证相关接口 |
| `student.py` | 学生端能力评估、参赛、报告、历史、分析、成就等接口 |
| `teacher.py` | 教师端班级、学生、辩论任务创建和管理接口 |
| `admin.py` | 管理员端用户、班级、系统配置等接口 |
| `admin_kb.py` | 管理员知识库文档上传、解析、向量化和管理 |
| `student_kb.py` | 学生知识库问答与会话历史 |
| `voice.py` | ASR 语音识别与 TTS 语音合成 |
| `websocket.py` | 实时辩论房间通信 |

### 5.2 服务层

服务位于 `api/services/`，负责封装核心业务逻辑：

| 服务 | 职责 |
| --- | --- |
| `room_manager.py` | 辩论房间、参与者、阶段状态、麦克风状态管理 |
| `flow_controller.py` | 辩论流程编排、阶段切换、倒计时、AI 发言触发 |
| `debate_service.py` | 辩论任务与业务数据管理 |
| `scoring_service.py` | 评分与赛后评价 |
| `report_service.py` | 报告生成与导出 |
| `analytics_service.py` | 学生表现、班级对比和成长分析 |
| `assessment_service.py` | 能力评估 |
| `rag_service.py` | 知识库增强问答 |
| `document_service.py` | 文档解析、切片和处理 |
| `knowledge_base.py` | 知识库检索与管理能力 |
| `kb_vector_schema_service.py` | pgvector 字段与索引结构对齐 |
| `config_service.py` | 模型、语音、向量、Coze、邮件等配置读取 |
| `coze_client.py` | Coze Bot API 调用封装 |

### 5.3 数据模型层

模型位于 `api/models/`，核心实体包括：

- `User`：教师、学生、管理员统一用户模型。
- `Class`：班级信息。
- `Debate`：辩论任务、辩题、状态、阶段配置等信息。
- `DebateParticipation`：学生与辩论任务的参与关系。
- `Speech`：实时发言文本、音频地址、发言时长和角色信息。
- `Score`：评分结果和反馈。
- `AbilityAssessment`：能力评估结果。
- `Achievement`：成就与成长激励。
- `KBDocument` / `KBDocumentChunk`：知识库文档与向量切片。
- `KBConversation`：知识库问答会话历史。
- `ModelConfig` / `AsrConfig` / `TtsConfig` / `VectorConfig` / `CozeConfig` / `EmailConfig`：平台能力配置。

## 6. AI 智能体技术栈

| 技术 / 模块 | 用途 |
| --- | --- |
| 自定义 Agent | 封装辩手、裁判、导师等角色行为 |
| CozePy / Coze API | 接入外部 Bot，支持多角色智能体配置 |
| OpenAI 兼容接口 | 通用 LLM 生成、评分、推理与兜底调用 |
| DashScope | ASR/TTS 语音识别与语音合成 |
| LangChain | 文档处理、文本切分、RAG 基础能力 |
| LangGraph | 可扩展的智能体流程编排能力 |
| Cohere | 可扩展的嵌入、重排或外部模型能力 |
| tiktoken | Token 估算与上下文控制 |

智能体代码位于 `api/agents/`：

- `debater_agent.py`：AI 辩手 Agent，负责根据辩题、阶段、上下文生成发言内容，并支持 Coze Bot 或通用 LLM 调用。
- `judge_agent.py`：裁判 Agent，负责评分、违规检测、反馈生成等。
- `mentor_agent.py`：导师 Agent，负责教学点评、指导建议和学习辅助。

智能体配置优先从数据库配置表读取，环境变量作为 fallback。这样可以让管理员在后台维护模型名称、API 地址、API Key、Bot ID、语音模型和向量模型等参数，而不需要修改代码。

## 7. 实时辩论架构

实时辩论由 WebSocket、房间管理器和流程控制器共同实现。

### 7.1 WebSocket 接入

WebSocket 端点为：

```text
/ws/debate/{room_id}?token={jwt}
```

连接建立时，后端会：

- 校验 JWT。
- 查询用户身份。
- 创建或加入辩论房间。
- 推送当前房间状态。
- 持续接收并处理前端消息。

支持的典型消息类型包括：

- `speech`：文本发言。
- `audio`：语音发言。
- `grab_mic`：自由辩论抢麦。
- `select_speaker`：可选回答阶段选择发言人。
- `start_debate`：开始辩论。
- `advance_segment`：推进到下一阶段。
- `end_turn`：结束当前发言回合。
- `end_debate`：结束整场辩论。
- `speech_playback_started` / `speech_playback_finished`：前端音频播放状态回传。

### 7.2 流程控制

`flow_controller.py` 内置默认辩论流程，覆盖：

- 立论阶段。
- 盘问阶段。
- 自由辩论阶段。
- 总结陈词阶段。

每个阶段包含：

- 阶段 ID。
- 展示标题。
- 阶段类型。
- 持续时间。
- 发言模式：固定发言、可选回答、自由抢麦。
- 允许发言的角色列表。

当轮到 AI 角色发言时，流程控制器会调用 `AIDebaterAgent` 生成内容，并通过 WebSocket 广播给房间内所有前端客户端。发言结果会沉淀到 `Speech` 表，便于报告、回放、评分和分析。

## 8. 语音链路架构

系统同时支持学生语音发言和 AI 语音输出。

### 8.1 ASR 语音识别

语音识别主要由 `voice.py` 和 `utils/voice_processor.py` 封装，默认可接入 DashScope ASR：

- 前端上传或发送音频。
- 后端调用 ASR 服务识别文本。
- 统一解析不同 ASR 返回格式。
- 保存识别文本、音频地址和发言时长。
- 将发言作为辩论上下文继续推进。

### 8.2 TTS 语音合成

AI 发言可通过 TTS 合成为音频：

- AI Agent 生成文本。
- 后端调用 TTS 服务生成音频。
- 音频文件写入上传目录。
- 前端播放 AI 发言音频。
- 前端回传播放开始和播放完成事件，用于控制“音频播放完成后再推进环节”的时序。

## 9. 知识库与 RAG 架构

知识库能力用于学生备赛问答和资料检索。

核心链路：

```text
管理员上传 PDF / DOCX
  -> 文档解析
  -> 文本切片
  -> 向量化
  -> PostgreSQL + pgvector 存储
  -> 学生提问
  -> 向量检索
  -> 组装上下文
  -> LLM 生成答案
  -> 返回答案、引用来源、命中状态和置信度
```

相关模块：

- `document_service.py`：文档解析与切片。
- `rag_service.py`：检索增强问答。
- `knowledge_base.py`：知识库核心管理逻辑。
- `kb_vector_schema_service.py`：向量列和索引结构维护。
- `admin_kb.py`：管理员文档管理接口。
- `student_kb.py`：学生问答接口。

## 10. 报告与分析技术栈

报告和分析能力围绕“发言记录 + 评分结果 + 历史表现”构建。

| 技术 | 用途 |
| --- | --- |
| ReportLab | PDF 或报告文档生成 |
| WeasyPrint | HTML/CSS 到 PDF 的报告渲染 |
| markdown / pygments | Markdown 内容处理与代码高亮能力 |
| openpyxl | Excel 导出 |
| python-docx | Word 文档解析或生成 |
| aiosmtplib | 异步邮件发送 |

相关服务包括：

- `report_service.py`：单场辩论报告生成和导出。
- `scoring_service.py`：评分与评价。
- `analytics_service.py`：成长趋势、班级对比、表现分析。
- `comparison_service.py`：对比分析。
- `achievement_service.py`：成就检测和激励。

## 11. 配置管理

系统配置采用“数据库配置优先，环境变量兜底”的策略。

主要配置来源：

- `api/config.py`：基础环境变量和默认值。
- 数据库配置表：模型、Coze、ASR、TTS、向量、邮件等后台可维护配置。
- Docker Compose 环境变量：数据库、Redis、API 地址、密钥等部署参数。

关键环境变量包括：

- `DATABASE_URL`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `REDIS_PASSWORD`
- `SECRET_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL_NAME`
- `ASR_API_KEY`
- `TTS_API_KEY`
- `COZE_API_KEY`
- `COZE_BASE_URL`
- `PUBLIC_BASE_URL`

生产环境建议：

- 将密钥全部放入环境变量或密钥管理系统。
- 避免在代码中保留真实数据库地址、Redis 密码和模型 API Key。
- 管理员后台只保存必要配置，敏感字段应考虑加密存储或脱敏展示。

## 12. 部署与运行技术栈

项目提供以下部署文件：

- `Dockerfile.api`：后端 API 镜像。
- `Dockerfile.web`：前端 Web 镜像。
- `Dockerfile.db.local`：本地 PostgreSQL + pgvector 数据库镜像。
- `docker-compose.yml`：API 与 Web 基础编排。
- `docker-compose.local.yml`：本地完整编排，包含 PostgreSQL、Redis、API、Web。

本地容器化运行结构：

```text
web container
  -> Nginx 静态资源服务 / API 反向代理

api container
  -> Uvicorn + FastAPI
  -> PostgreSQL
  -> Redis
  -> 外部 AI / ASR / TTS 服务

db container
  -> PostgreSQL + pgvector

redis container
  -> Redis 7
```

端口约定：

- Web：`8860`
- API：`7860`
- PostgreSQL：`5432`
- Redis：`6379`

## 13. 测试与质量保障

前端测试：

- `vitest`
- `@testing-library/react`
- `fast-check`
- `jsdom`

后端测试：

- `pytest`
- `pytest-asyncio`
- `pytest-cov`
- `hypothesis`
- `faker`

代码质量工具：

- 前端：ESLint、Prettier、TypeScript type-check、Biome 配置。
- 后端：Black、Flake8、Mypy。

建议重点覆盖：

- WebSocket 消息状态机。
- AI 发言失败兜底。
- ASR/TTS 异常处理。
- 报告生成边界情况。
- RAG 检索命中和未命中场景。
- 权限隔离：学生、教师、管理员接口访问控制。

## 14. 架构优势

- 前后端分离，便于独立开发、构建和部署。
- 实时辩论流程由服务层统一编排，前端只需消费状态和事件。
- AI 智能体与业务流程解耦，可切换 Coze Bot 或 OpenAI 兼容模型。
- 配置表驱动模型、语音和向量能力，适合教学平台后续运营维护。
- PostgreSQL 同时承载业务数据和向量数据，降低部署复杂度。
- WebSocket 支撑低延迟课堂互动，REST API 支撑管理、报告和分析场景。
- 报告、知识库、语音、评分和成长分析形成完整教学闭环。

## 15. 后续演进建议

- 引入统一任务队列处理耗时任务，如文档向量化、报告生成、批量评分和邮件发送。
- 将房间状态从进程内存逐步迁移到 Redis，支持多 API 实例横向扩展。
- 为智能体调用增加统一熔断、重试、限流和模型用量统计。
- 对 Coze、OpenAI 兼容模型、DashScope 等外部服务建立统一 Provider 接口。
- 增强观测能力，补充结构化日志、Prometheus 指标和链路追踪。
- 对敏感配置进行加密存储，后台展示时进行脱敏。
- 完善 WebSocket 协议文档，固定消息类型、字段结构和状态转换规则。

