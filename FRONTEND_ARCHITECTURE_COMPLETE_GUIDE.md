# AI Debate 前端架构完整说明文档

> 本文基于当前代码实现整理，重点说明页面结构、按钮动作、页面跳转、后端接口、实时通信、组件分层和业务功能边界。  
> 当前前端是 React + Vite 单页应用，但没有使用 React Router，页面切换由 `AppRouter` 内部状态驱动。

## 1. 项目定位

本项目是一个“人机辩论教学平台”前端。系统支持三类用户：

- 学生：登录、注册、加入课堂辩论、完成能力评估、进入候场区、参与实时辩论、查看报告、查看回放、使用知识库备战助手、查看成长分析和成就。
- 教师：登录、注册、查看教师控制台、创建/发布辩论任务、选择班级和学生、查看智能分组、上传辩论支撑材料、查看报告和回放、查看学生列表、维护个人资料。
- 管理员：登录后台，管理班级、成员、知识库文档、AI 模型配置、ASR/TTS/向量模型、邮件服务和 Coze Bot 配置。

## 2. 技术栈与目录

前端目录：`web/`

核心技术：

- React 18
- TypeScript
- Vite
- Tailwind CSS
- Radix UI 组件封装，位于 `web/src/components/ui`
- lucide-react 图标
- axios 请求层
- WebSocket 实时辩论通信
- Vitest 单元测试

关键文件：

- `web/src/main.tsx`：React 入口。
- `web/src/App.tsx`：挂载 `AuthProvider`、`AppRouter`、全局 `Toaster`。
- `web/src/components/app-router.tsx`：页面状态路由中心。
- `web/src/store/auth.context.tsx`：全局认证上下文。
- `web/src/lib/api.ts`：axios 封装、Token 注入、401 自动刷新。
- `web/src/lib/websocket-client.ts`：WebSocket 客户端。
- `web/src/hooks/use-websocket.ts`：React WebSocket Hook。
- `web/src/services/auth.service.ts`：登录、注册、资料、密码接口。
- `web/src/services/student.service.ts`：学生端接口。
- `web/src/services/teacher.service.ts`：教师端接口。
- `web/src/services/admin.service.ts`：管理员端接口。

## 3. 全局前端架构

### 3.1 应用启动

启动链路：

1. `main.tsx` 渲染 `<App />`。
2. `App.tsx` 包裹：
   - `AuthProvider`
   - `AppRouter`
   - `Toaster`
3. `AuthProvider` 从本地 Token 存储恢复登录状态。
4. `AppRouter` 根据内部 `currentPage` 渲染当前页面。

### 3.2 页面路由实现

当前不是 URL 路由，而是状态路由：

```ts
currentPage:
  'login'
  'teacher'
  'admin'
  'command-center'
  'student'
  'match'
  'debate'
  'analytics'
  'student-analytics'
  'debate-report'
  'debate-replay'
  'preparation-assistant'
```

页面跳转通过组件 props 回调完成，例如：

- 登录后设置 `currentPage`
- 学生点击“分析中心”设置为 `student-analytics`
- 学生点击“报告”设置为 `debate-report`
- 学生点击“回放”设置为 `debate-replay`
- 教师历史记录点击“报告/回放”进入相同报告/回放页
- 匹配结果页点击“开始辩论”进入 `debate`

注意：刷新浏览器会丢失当前页面状态，回到初始状态。若要产品化，建议后续改成 React Router，并把 debateId/reportId/replayId 写入 URL。

### 3.3 全局请求层

文件：`web/src/lib/api.ts`

特性：

- baseURL 来自 `VITE_API_BASE_URL`，默认为空字符串。
- 每个请求自动带 `Authorization: Bearer <access_token>`。
- 响应自动解包 `{ code, message, data }` 结构里的 `data`。
- 401 时自动调用 `TokenManager.refreshToken()` 刷新 Token，再重试原请求。
- 支持 `get/post/put/delete`。

### 3.4 全局认证

文件：`web/src/store/auth.context.tsx`

提供：

- `isAuthenticated`
- `user`
- `loading`
- `login(params)`
- `logout()`
- `updateUser(user)`
- `checkAuth()`

登录成功后：

- 保存 access_token、refresh_token、用户信息。
- 根据角色进入不同页面。

登出：

- 清理 Token 和用户信息。
- 当前 `AuthService.logout()` 里会跳转 `/login`，但本项目实际没有 URL 路由，页面内也会通过 `onLogout` 回到登录页。

## 4. 前端页面总览

| 页面状态 | 组件 | 用户 | 功能 |
|---|---|---|---|
| `login` | `LoginPortal` | 全部 | 登录、学生注册、教师注册、管理员登录 |
| `command-center` | `StudentCommandCenter` | 学生 | 学生主控制台、加入课堂、知识库文档、历史报告入口 |
| `student` | `StudentOnboarding` | 学生 | 能力评估、候场、查看辩题、准备清单 |
| `match` | `DebateMatchResult` | 学生 | 展示匹配结果、人类队伍、AI 队伍、开始辩论 |
| `debate` | `DebateArena` | 学生/教师入口可复用 | 实时辩论房间、音频、转写、AI 播报、流程控制 |
| `analytics` | `EnhancedDebateAnalytics` | 学生/教师 | 单场赛后分析和历史切换 |
| `student-analytics` | `StudentAnalyticsCenter` | 学生 | 历史、成长趋势、班级对比、成就 |
| `debate-report` | `DebateReportPage` | 学生/教师 | 单场辩论报告、导出 PDF、详细分析 |
| `debate-replay` | `DebateReplayPage` | 学生/教师 | 辩论回放、发言记录、音频播放 |
| `preparation-assistant` | `PreparationAssistantPage` | 学生 | 知识库流式问答备战助手 |
| `teacher` | `TeacherDashboard` | 教师 | 创建辩论、历史、学生、个人中心 |
| `admin` | `AdminDashboard` | 管理员 | 班级、成员、知识库、模型和系统配置 |

## 5. 登录页：LoginPortal

文件：`web/src/components/login-portal.tsx`

### 5.1 页面结构

页面分为：

- 顶部品牌区：平台名称、英文名称、核心卖点。
- 登录/注册卡片。
- 角色 Tabs。
- 表单区。

### 5.2 顶部按钮与控件

登录/注册切换：

- “登录”按钮：切换到登录模式。
- “注册”按钮：切换到注册模式。

角色 Tabs：

- 登录模式：学生、老师、管理员。
- 注册模式：学生、老师。管理员不支持注册。

### 5.3 学生登录

字段：

- 账号
- 密码

按钮：

- “登录”

接口：

- `POST /api/auth/login`

请求：

```json
{
  "account": "账号",
  "password": "密码",
  "user_type": "student"
}
```

成功后：

1. 保存 Token。
2. 调用 `StudentService.getAssessment()` 判断是否需要能力评估。
3. 进入学生控制台 `command-center`。
4. 若未完成能力评估，默认打开个人中心能力评估 Tab。

### 5.4 学生注册

字段：

- 账号，必填。
- 密码，必填。
- 确认密码，必填。
- 姓名，必填。
- 邮箱，可选。
- 班级选择，下拉，来自公开班级列表。
- 学号，可选。

接口：

- `GET /api/auth/classes/public`
- `POST /api/auth/register/student`

注册成功后：

- 显示成功提示。
- 回到登录模式。

### 5.5 教师登录

字段：

- 邮箱/教工号
- 密码

接口：

- `POST /api/auth/login`

成功后进入 `teacher`。

### 5.6 教师注册

字段：

- 教工号
- 密码
- 确认密码
- 姓名
- 邮箱

接口：

- `POST /api/auth/register/teacher`

说明：

- 教师注册时不选择班级。
- 班级由管理员创建并分配。

### 5.7 管理员登录

字段：

- 管理员账号
- 密码

接口：

- `POST /api/auth/login`

成功后进入 `admin`。

## 6. 学生主控制台：StudentCommandCenter

文件：`web/src/components/student-command-center.tsx`

### 6.1 页面定位

这是学生登录后的主页面，承担：

- 加入课堂辩论。
- 查看个人数据概览。
- 查看最近历史记录。
- 查看课程知识库文档。
- 跳转备战助手、分析中心、个人中心。

### 6.2 顶部导航按钮

按钮：

- “备战辅助”：进入 `preparation-assistant`。
- “分析中心”：进入 `student-analytics`，默认 Tab 为历史。
- “个人中心/控制中心”：切换当前页面内 `UserProfile` 显示。
- “退出登录”：返回登录页。

### 6.3 加入课堂模块

控件：

- 6 位邀请码输入框。
- “进入候场区”按钮。

按钮状态：

- 邀请码长度不是 6 位时禁用。

接口：

- `POST /api/student/debates/join`

成功后：

- 保存加入的 debate。
- 设置 currentDebateId。
- 进入 `student` 候场/准备页。

### 6.4 数据概览模块

展示：

- 总场次
- 胜率，目前按 `completed_debates / total_debates` 计算
- MVP 次数，目前前端固定为 0
- 等级，按总场次粗略计算

接口：

- `GET /api/student/analytics`

### 6.5 历史战绩模块

组件：`DebateHistoryRecords`

展示：

- 最近完成的辩论记录，默认最多 4 条。
- 日期、题目、角色、时长、得分、胜负结果。

按钮：

- “查看全部”：进入 `student-analytics` 的历史 Tab。
- “报告”：进入 `debate-report`。
- “回放”：进入 `debate-replay`。

接口：

- `GET /api/student/history?limit=20&offset=0`

### 6.6 课程知识库模块

展示：

- 文档数量。
- 最近同步时间。
- 文档卡片：类型、状态、上传日期、文件名、大小。

控件：

- 搜索输入框：前端按文件名本地过滤。
- “刷新”按钮。
- 文档“预览”按钮。
- 文档“下载”按钮。

接口：

- `GET /api/student/kb/documents?page=1&page_size=100`
- `GET /api/student/kb/documents/{document_id}/download`

预览规则：

- PDF 支持在线预览，通过 Blob 打开新窗口。
- 非 PDF 提示使用下载查看。

自动轮询：

- 若文档处于 `pending` 或 `processing`，每 8 秒刷新一次。
- 页面重新聚焦或可见时也会刷新。

## 7. 个人中心：UserProfile

文件：`web/src/components/user-profile.tsx`

可从学生主控制台和教师控制台打开。

### 7.1 Tabs

学生有 3 个 Tab：

- 个人信息
- 修改密码
- 能力评估

教师有 2 个 Tab：

- 个人信息
- 修改密码

### 7.2 个人信息 Tab

字段：

- 账号，只读。
- 姓名。
- 邮箱。
- 手机号。
- 学生额外字段：学号、所属班级。

按钮：

- “保存修改”

接口：

- `GET /api/auth/profile`
- `PUT /api/auth/profile`
- 学生班级列表：`GET /api/auth/classes/public`

学生班级规则：

- 如果已经绑定班级，班级选择会锁定。
- 如果未绑定，可以选择一次并保存。

### 7.3 修改密码 Tab

字段：

- 当前密码。
- 新密码。
- 确认新密码。

校验：

- 两次新密码必须一致。
- 新密码至少 6 位。

按钮：

- “修改密码”

接口：

- `POST /api/auth/change-password`

### 7.4 能力评估 Tab

仅学生显示。

展示：

- 五维能力画像。
- 综合评分。
- 已完成辩论数量。
- 最近 7 场成长趋势。

接口：

- `GET /api/student/analytics`
- `GET /api/student/analytics/growth?limit=7`
- `GET /api/student/assessment`

能力画像显示规则：

- 若没有真实辩论数据或评估是默认数据，则显示空状态。
- 当前组件主要展示，不在这里编辑能力自评。

## 8. 学生准备页：StudentOnboarding

文件：`web/src/components/student-onboarding.tsx`

### 8.1 页面定位

学生输入邀请码并加入辩论后进入该页，用于：

- 完成能力自评。
- 查看智能分组分配角色。
- 查看当前辩题和背景资料。
- 候场等待匹配。
- 快速进入分析中心。

### 8.2 顶部按钮

- “退出”：返回登录页。

### 8.3 能力评估模块

若已经完成能力评估：

- 展示 `SkillsRadar`。

若未完成：

- 展示 `SkillsAssessmentEditor`。
- 五个维度都需要填写：
  - AI 核心知识运用
  - AI 伦理与科技素养
  - 批判性思维
  - 逻辑建构力
  - 语言表达力

控件：

- 每个维度有 range 滑块。
- 每个维度有数字输入框。

按钮：

- “保存评估结果”

接口：

- `GET /api/student/assessment`
- `POST /api/student/assessment`

### 8.4 角色展示

数据来源：

- 初始 joinedDebate。
- 或 `GET /api/student/debates` 找到当前已加入的辩论。

展示：

- 角色：`debater_1` 至 `debater_4`
- 角色中文名：一辩、二辩、三辩、四辩。
- 分配原因 `role_reason`。
- 当前辩题。

### 8.5 辩题卡片

组件：`DebateTopicCard`

展示：

- 辩题标题。
- 轮次/描述。
- 知识点。
- 时长。
- 参与人数。
- 难度。
- 背景资料折叠区。
- 关键论点。
- 推荐资源。

按钮：

- “背景资料”折叠/展开。

### 8.6 候场状态条

组件：`WaitingStatusBar`

展示：

- 连接中、系统分配中、等待参与者、准备就绪。
- 进度条。
- 准备提示。

按钮：

- “跳过等待，查看匹配结果”

跳转：

- 进入 `match` 页面。

注意：

- 当前候场状态是前端模拟状态，不是 WebSocket 真实房间人数。

### 8.7 快速操作

按钮：

- “查看能力分析报告”：进入 `student-analytics` 的成长趋势 Tab。
- “查看历史辩论记录”：进入 `student-analytics` 的历史 Tab。

## 9. 匹配结果页：DebateMatchResult

文件：`web/src/components/debate-match-result.tsx`

### 9.1 页面定位

展示人类队伍和 AI 队伍匹配结果，开始正式辩论前的确认页。

### 9.2 顶部按钮

- “返回”：返回学生控制台。
- “详情/简化”：切换队伍详情显示效果。
- 静音图标按钮：切换本地静音状态，仅前端状态。
- 全屏图标按钮：切换全屏样式状态。

### 9.3 主体内容

展示：

- 立场展示。
- 人类团队，来自 joinedDebate participants。
- AI 团队，前端静态构造四个 AI：
  - Alpha-Logic
  - Beta-Creative
  - Gamma-Strategic
  - Delta-Balance
- 人类团队均分。
- AI 团队均分。
- 匹配成功率。
- 对抗等级。
- 对战预告。

接口：

- 若没有 `initialDebate`，调用 `GET /api/student/debates` 找到已加入辩论。
- 若缺参与者，调用 `GET /api/student/debates/{debate_id}/participants`。

### 9.4 底部按钮

- “准备就绪，开始辩论”

跳转：

- 设置 currentDebateId。
- 进入 `debate`。

## 10. 实时辩论页：DebateArena

文件：

- `web/src/components/debate-arena.tsx`
- `web/src/components/debate-header.tsx`
- `web/src/components/debate-audio-control.tsx`
- `web/src/components/debate-controls.tsx`

### 10.1 页面定位

实时辩论房间。功能包括：

- WebSocket 连接辩论房间。
- 展示人类队伍和 AI 队伍。
- 展示辩论阶段和流程。
- 文字发言。
- 语音录制上传。
- ASR 转写。
- TTS 播报。
- AI 流式音频播放。
- 自由辩论抢麦。
- 一辩控制开始、下一阶段、结束辩论。
- 生成报告时显示遮罩。

### 10.2 WebSocket 连接

连接地址：

```text
ws(s)://<host>/ws/debate/{room_id}?token=<access_token>
```

如果配置了 `VITE_API_BASE_URL`：

- `http` 会转 `ws`
- `https` 会转 `wss`
- 末尾 `/api` 会去掉

后端：

- `WebSocket /ws/debate/{room_id}`

### 10.3 顶部 DebateHeader

展示：

- 辩题。
- 当前阶段。
- 当前流程段标题。
- 剩余时间。
- 4v4 对抗。
- 对抗等级、匹配度。
- 进度条。
- 阶段指示器：立论陈词、攻辩环节、自由辩论、总结陈词。

按钮：

- “开始辩论”：只有当前用户是一辩、房间已连接、阶段为 waiting 时显示。
- “强制下一阶段”：只有一辩且当前阶段不是 waiting/finished 且不是最后阶段时显示。
- “结束辩论”：只有一辩且满足结束条件时显示。
- 设置图标：打开设置弹窗。
- 全屏图标：进入/退出浏览器全屏。
- 音量图标：开启/关闭 AI 自动播放。

WebSocket 发送：

- `start_debate`
- `advance_segment`
- `end_debate`
- `speech_playback_started`
- `speech_playback_finished`
- `speech_playback_failed`
- `speech_playback_skipped`

### 10.4 设置弹窗

字段：

- AI 语音自动播放开关。
- 流式播放状态。

按钮/控件：

- Switch：开启/关闭 AI 语音自动播放。

关闭自动播放时：

- 当前流式 TTS 会停止。
- 新的 AI 流式音频会被跳过。

### 10.5 左侧 DebateAudioControl

顶部图标按钮：

- 麦克风开关：切换 `isMuted`。
- 摄像头开关：切换 `isVideoOff`。

状态区：

- 当前能否发言。
- 当前抢麦/持麦状态。
- 录音错误。

核心按钮：

- “抢麦发言”：自由辩论可抢麦时显示，发送 `grab_mic`。
- “点击录音/停止录音”：录制音频并发送。
- “结束发言”：发送 `end_turn`。

录音流程：

1. 前端检查浏览器是否支持录音。
2. 发送 `request_recording` 请求后端判断是否允许录音。
3. 后端返回 `recording_permission`。
4. 允许后开始录音。
5. 停止录音后转成 base64。
6. 发送 WebSocket `audio` 消息。

WebSocket 发送：

- `request_recording`
- `audio`
- `grab_mic`
- `end_turn`

### 10.6 主战场区域

展示：

- 当前流程段。
- 阶段列表。
- “选择我来回答”按钮。
- 当前发言者提示。
- AI 当前状态提示。
- 人类团队 4 个视频占位。
- AI 团队 4 个头像。
- 团队信号强度。
- AI 处理能力。
- 对战统计。

“选择我来回答”显示条件：

- WebSocket 已连接。
- 当前 speakerMode 为 `choice`。
- 当前用户角色在 `speakerOptions` 内。

点击后发送：

- `select_speaker`，payload `{ role: currentUserRole }`

### 10.7 底部 DebateControls

展示：

- 实时记录列表。
- 每条发言的发言者、位置、时间、文本。
- 如果有音频 URL，显示 audio 控件。
- 自动播放开关。
- AI 流式播报中 Badge。
- 文字输入框和发送按钮。

按钮：

- “自动播放：开/关”
- audio 控件播放/暂停
- 文本发送按钮

文本发送：

- 只有 `canSpeak` 为 true 时可用。
- 发送 WebSocket `speech`，payload `{ content: message }`。

音频播放事件：

- 手动播放音频时发送 `speech_playback_started`
- 播放结束发送 `speech_playback_finished`
- 播放失败发送 `speech_playback_failed`

### 10.8 前端监听的 WebSocket 事件

`DebateArena` 监听：

- `state_update`
- `user_joined`
- `user_left`
- `phase_change`
- `segment_change`
- `timer_update`
- `subtitle`
- `speech`
- `tts_stream_start`
- `tts_stream_chunk`
- `tts_stream_end`
- `recording_permission`
- `audio_processed`
- `permission_denied`
- `mic_grabbed`
- `mic_released`
- `speaker_selected`
- `debate_processing`
- `debate_ended`
- `error`

### 10.9 前端发送的 WebSocket 事件

`DebateArena` 发送：

- `speech`
- `audio`
- `request_recording`
- `grab_mic`
- `end_turn`
- `start_debate`
- `advance_segment`
- `select_speaker`
- `end_debate`
- `speech_playback_started`
- `speech_playback_finished`
- `speech_playback_failed`
- `speech_playback_skipped`

### 10.10 报告生成遮罩

当收到 `debate_processing`：

- 显示全屏遮罩。
- 提示 AI 裁判正在分析和评分。

当收到 `debate_ended`：

- 隐藏遮罩。
- 调用 `onEndDebate` 进入 `analytics` 页面。

## 11. 学生分析中心：StudentAnalyticsCenter

文件：`web/src/components/student-analytics-center.tsx`

### 11.1 页面结构

左侧菜单：

- 历史记录
- 成长趋势
- 对比分析
- 成就系统

顶部：

- 返回按钮。
- 当前学生姓名。

接口初始化：

- `GET /api/student/analytics`
- `GET /api/student/history?limit=20&offset=0`
- `GET /api/student/analytics/growth?limit=10`
- `GET /api/student/achievements/v2`

### 11.2 历史记录 Tab

组件：`DebateHistoryRecords`

按钮：

- “报告”：进入 `debate-report`
- “回放”：进入 `debate-replay`

接口：

- `GET /api/student/history`

### 11.3 成长趋势 Tab

展示：

- 平均得分。
- 完成场次。
- 总参与场次。
- 得分趋势条。

接口：

- `GET /api/student/analytics`
- `GET /api/student/analytics/growth`

### 11.4 对比分析 Tab

展示：

- 班级排名。
- 领先百分位。
- 我的当前指标。
- 班级平均指标。
- 五维能力雷达图，我 vs 班级平均。
- 班级排行榜。

控件：

- 指标下拉：
  - overall
  - logic
  - argument
  - response
  - persuasion
  - teamwork
- “刷新”按钮。

接口：

- `GET /api/student/comparison/class?metric={metric}&top=10`

异常状态：

- 若学生未加入班级，显示提示卡片。
- 若样本为 0，显示暂无可对比数据。

### 11.5 成就系统 Tab

展示：

- 已解锁成就。
- 待解锁成就。
- 进度条。
- 解锁提示。

按钮：

- “检查新成就”

接口：

- `GET /api/student/achievements/v2`
- `POST /api/student/achievements/check/v2`

自动行为：

- 首次进入成就 Tab 会自动检查一次成就。

## 12. 辩论报告页：DebateReportPage

文件：

- `web/src/components/debate-report-page.tsx`
- `web/src/components/debate-report-overview.tsx`
- `web/src/components/debate-report-detail.tsx`

### 12.1 页面定位

用于查看单场辩论报告。学生和教师都可以从历史记录进入。

### 12.2 顶部按钮

- “返回”：返回来源页面。
- “导出 PDF”：下载报告 PDF。

代码中 Excel 和发送邮件按钮存在但被注释。

接口：

- `GET /api/student/reports/{debate_id}`
- `GET /api/student/reports/{debate_id}/export/pdf`
- `GET /api/student/reports/{debate_id}/export/excel`，目前按钮注释。
- `POST /api/student/reports/{debate_id}/send-email`，目前按钮注释。

### 12.3 概览区 DebateReportOverview

展示：

- 结果卡片：人类胜、AI 胜、平局。
- 人类团队分数。
- AI 团队分数。
- 得分差异。
- 辩题、立场、时长、完成时间。

按钮：

- “查看详细分析”：进入 detail view。
- “下载完整报告”：导出 PDF。

Tabs：

- 总结
- 能力
- 发言
- 反馈

### 12.4 总结 Tab

展示：

- 综合得分。
- 辩论时长。
- 发言次数。
- 表现等级。
- 五维能力雷达图。
- 发言时间分布图。

数据：

- 从 `DebateReport.participants[].final_score` 和 `statistics` 推导。

### 12.5 能力 Tab

组件：`AbilityRadarChart`

展示：

- 逻辑建构力。
- AI 核心知识运用。
- 批判性思维。
- 语言表达力。
- AI 伦理与科技素养。
- 维度分数与等级。

### 12.6 发言 Tab

组件：`SpeakingTimeChart`

展示：

- 总发言时间。
- 人类/AI 发言占比。
- 饼图。
- 条形图。
- 发言活跃度排名。

### 12.7 反馈 Tab

组件：`AIMentorFeedback`

展示：

- AI 导师反馈。
- 总体评语。
- 胜负关键点。
- 行动建议。
- 推荐学习资源。

### 12.8 详细分析页 DebateReportDetail

按钮：

- “返回”：回到概览。
- “导出 PDF”。

展示：

- 辩题和基础信息。
- 正方/反方结果总览。
- 当前用户个人表现总览。
- 五维分数。
- 每条发言详情和单条评分。

接口：

- `GET /api/student/reports/{debate_id}`
- `GET /api/student/reports/{debate_id}/export/pdf`

## 13. 辩论回放页：DebateReplayPage

文件：`web/src/components/debate-replay-page.tsx`

### 13.1 页面定位

查看已经完成的辩论回放，包括：

- 人类队伍。
- AI 队伍。
- 发言记录。
- 发言音频。

### 13.2 顶部按钮

- “返回”：返回来源页面。

### 13.3 数据接口

进入页面时并行请求：

- `GET /api/student/history/{debate_id}`
- `GET /api/student/debates/{debate_id}/participants`

### 13.4 主体展示

展示：

- 辩题。
- 创建时间。
- 回放模式 Badge。
- 人类 4 个位置。
- AI 4 个位置。
- 发言记录数量。

底部复用 `DebateControls`：

- title 为“发言记录”。
- badgeText 为“回放”。
- `showInput=false`，不显示输入框。
- 支持播放发言音频。

## 14. 备战辅助页：PreparationAssistantPage

文件：`web/src/components/student/preparation-assistant-page.tsx`

### 14.1 页面定位

学生知识库问答助手，类似聊天界面。用于赛前查资料、构建论点、寻找反驳点。

### 14.2 左侧栏

按钮：

- “返回控制台”：返回 `command-center`。
- “开启新对话”：清空当前 session，准备新会话。

列表：

- 历史会话列表。
- 点击会话加载该会话历史。

接口：

- `GET /api/student/kb/sessions`
- `GET /api/student/kb/conversations/{session_id}?limit=20`

### 14.3 主聊天区

空状态：

- 展示欢迎语。
- 展示 4 个示例问题按钮。

示例问题按钮：

- 点击后只填入输入框，不自动发送。

消息展示：

- 右侧为用户问题。
- 左侧为 AI 回答。
- 回答下方显示参考资料。
- 参考资料包含文档名、相似度、摘录。

### 14.4 底部输入区

控件：

- Textarea。
- “发送”按钮。

快捷键：

- Enter 发送。
- Shift + Enter 换行。

接口：

- 流式问答：`POST /api/student/kb/ask/stream`
- 非流式问答：`POST /api/student/kb/ask`，service 中存在，当前页面主要使用 stream。

流式协议：

- 使用 `fetch` 读取 SSE。
- 事件类型：
  - `sources`：参考资料。
  - `answer`：回答文本增量。
  - `done`：完成，保存最终消息。
  - `error`：生成错误。

新会话逻辑：

- 如果没有 currentSessionId，前端生成 `session_${Date.now()}_${random}`。
- 第一次提问成功后重新加载 session 列表。

## 15. 教师控制台：TeacherDashboard

文件：`web/src/components/teacher-dashboard.tsx`

### 15.1 页面结构

左侧菜单：

- 新建辩论
- 历史记录
- 学生管理
- 个人中心

顶部/概览：

- 教师信息。
- 管理学生数。
- 参与学生数。
- 活跃辩论。
- 已完成辩论。
- 今日辩论等统计。

接口初始化：

- `GET /api/teacher/classes`
- `GET /api/teacher/debates`
- `GET /api/teacher/dashboard`

轮询：

- 每 15 秒刷新辩论列表和教师统计。
- 窗口聚焦或页面可见时刷新。

### 15.2 新建辩论 Tab

字段：

- 班级选择。
- 辩题。
- 时长。
- 轮次。
- 支撑知识点。
- 学生选择，最多 4 人。

接口：

- 班级：`GET /api/teacher/classes`
- 学生：`GET /api/teacher/students?class_id={class_id}`
- 创建辩论：`POST /api/teacher/debates`
- 更新辩论：`PUT /api/teacher/debates/{debate_id}`

按钮：

- “保存草稿”
- “发布辩论任务”
- 编辑已有辩论时：
  - “取消编辑”
  - “保存草稿”
  - “发布草稿”
  - “保存修改”

保存/发布逻辑：

- 草稿允许没有学生。
- 发布时必须选择至少一名学生。
- 创建或更新后刷新历史列表。

### 15.3 支撑材料上传

在编辑已有辩论时显示。

按钮：

- 上传支撑材料。
- 删除支撑材料。

约束：

- 仅支持 PDF。
- 最大 10MB。
- 必须先保存辩论草稿后才可上传。

接口：

- `GET /api/teacher/debates/{debate_id}/support-documents`
- `POST /api/teacher/debates/{debate_id}/support-documents`
- `DELETE /api/teacher/debates/{debate_id}/support-documents/{document_id}`

### 15.4 历史记录 Tab

展示：

- 辩论题目。
- 创建日期。
- 时长。
- 状态：草稿、已发布、进行中、已完成。
- 邀请码。
- 智能分组。

按钮：

- “智能分组”：展开/收起分组信息。
- “编辑”：进入新建辩论 Tab 并加载该辩论。
- “报告”：进入 `debate-report`，仅 completed 可点击。
- “回放”：进入 `debate-replay`，仅 completed 可点击。

接口：

- `GET /api/teacher/debates`
- 展开分组时：`GET /api/teacher/debates/{debate_id}`

### 15.5 学生管理 Tab

展示：

- 当前选中班级下学生列表。
- 头像首字。
- 姓名。
- 邮箱或账号。

接口：

- `GET /api/teacher/students?class_id={class_id}`

注意：

- 教师端当前没有新增学生按钮，虽然 service 里有 `addStudent`。

### 15.6 个人中心 Tab

复用 `UserProfile`。

接口同第 7 节。

### 15.7 教师退出

按钮：

- 退出登录。

跳转：

- 返回 `login`。

## 16. 管理员后台：AdminDashboard

文件：`web/src/components/admin-dashboard.tsx`

### 16.1 页面结构

左侧菜单：

- 班级管理
- 知识库管理
- 模型配置
- ASR 配置
- TTS 配置
- 向量配置
- 邮件配置
- Coze 配置
- 成员管理

底部按钮：

- 退出登录。

右侧内容根据 activeTab 渲染对应管理组件。

## 17. 管理员：班级管理

文件：`web/src/components/admin/class-management.tsx`

### 17.1 功能

- 查看所有班级。
- 创建班级。
- 编辑班级。
- 删除班级。
- 指定班级所属教师。

### 17.2 顶部按钮

- “创建班级”

接口：

- `GET /api/admin/classes`
- `GET /api/admin/users?role=teacher`

### 17.3 班级卡片

展示：

- 班级名称。
- 班级 code。
- 教师名。
- 学生人数。
- 创建日期。

按钮：

- “编辑”
- “删除”

### 17.4 创建/编辑弹窗

字段：

- 班级名称。
- 指定教师。

按钮：

- “取消”
- “保存”

接口：

- 创建：`POST /api/admin/classes`
- 编辑：`PUT /api/admin/classes/{class_id}`

### 17.5 删除确认弹窗

按钮：

- “取消”
- “确认删除”

接口：

- `DELETE /api/admin/classes/{class_id}`

删除影响：

- 后端会移除学生的班级注册关系。
- 前端提示该操作不可撤销。

## 18. 管理员：知识库管理

文件：`web/src/components/admin/document-management.tsx`

### 18.1 功能

- 查看知识库文档。
- 上传文档。
- 删除文档。
- 分页。
- 自动轮询处理状态。

### 18.2 顶部按钮

- “上传文档”

接口：

- `GET /api/admin/kb/documents?page={page}&page_size=20`

### 18.3 上传弹窗

交互：

- 点击上传区域选择文件。
- 拖拽文件到上传区域。

约束：

- 支持 PDF、DOCX。
- 最大 10MB。

接口：

- `POST /api/admin/kb/documents`

上传成功：

- Toast 提示。
- 刷新列表。
- 后端异步处理文档。

### 18.4 文档列表

列：

- 文件名。
- 文件类型。
- 文件大小。
- 上传状态。
- 上传时间。
- 操作。

状态：

- pending：等待中。
- processing：处理中。
- completed：已完成。
- failed：失败，显示错误 tooltip。

按钮：

- “删除”

接口：

- `DELETE /api/admin/kb/documents/{document_id}`

### 18.5 分页

按钮：

- 上一页。
- 页码。
- 下一页。

前端状态：

- page
- pageSize = 20
- total
- totalPages

### 18.6 自动轮询

如果存在 `pending` 或 `processing` 文档：

- 每 5 秒刷新一次。
- 页面可见时才刷新。

## 19. 管理员：成员管理

文件：`web/src/components/admin/user-management.tsx`

### 19.1 功能

- 查看所有用户统计。
- 按教师/学生切换管理。
- 搜索用户。
- 刷新数据。
- 编辑用户基本信息。
- 为教师分配负责班级。
- 为学生调整班级和学号。

接口：

- `GET /api/admin/users`
- `GET /api/admin/classes`
- `PUT /api/admin/users/{user_id}`

### 19.2 顶部统计卡片

展示：

- 总用户数。
- 教师数。
- 学生数。

### 19.3 筛选区按钮和控件

按钮：

- “教师管理”
- “学生管理”
- “刷新数据”

控件：

- 搜索输入框。

搜索字段：

- 账号。
- 姓名。
- 邮箱。
- 班级。
- 学号。
- 教师负责班级。

### 19.4 教师表格

列：

- 账号。
- 教师信息。
- 负责班级。
- 注册时间。
- 操作。

按钮：

- “编辑”

编辑弹窗字段：

- 账号。
- 姓名。
- 邮箱。
- 手机号。
- 角色，只读。
- 注册时间，只读。
- 负责班级复选列表。

教师负责班级规则：

- 已负责的班级会锁定。
- 勾选其他班级后保存，会将该班级改派给当前教师。

### 19.5 学生表格

列：

- 账号。
- 学生信息。
- 学号。
- 所属班级。
- 注册时间。
- 操作。

按钮：

- “编辑”

编辑弹窗字段：

- 账号。
- 姓名。
- 邮箱。
- 手机号。
- 角色，只读。
- 注册时间，只读。
- 学号。
- 所属班级。

## 20. 管理员：模型配置

文件：`web/src/components/admin/model-configuration.tsx`

功能：

- 查看和编辑通用 AI 模型配置。

字段：

- 模型名称。
- API 端点。
- API 密钥。
- Temperature。
- Max Tokens。
- 创建时间。
- 更新时间。

按钮：

- “编辑配置”
- 眼睛图标：显示/隐藏 API Key。
- “取消”
- “保存配置”

接口：

- `GET /api/admin/config/models`
- `POST /api/admin/config/models`

校验：

- 模型名称、API 端点、API Key 必填。
- Temperature 范围 0 到 2。
- Max Tokens 必须大于 0。

## 21. 管理员：ASR 配置

文件：`web/src/components/admin/asr-configuration.tsx`

功能：

- 配置语音识别模型。

字段：

- 模型名称。
- API 端点。
- API Key。
- 默认语言。
- 音频文件 URL 前缀，DashScope FileTrans 场景需要。
- 创建时间。
- 更新时间。

按钮：

- “编辑配置”
- 眼睛图标。
- “取消”
- “保存配置”

接口：

- `GET /api/admin/config/asr`
- `POST /api/admin/config/asr`

校验：

- 模型名称、API 端点、API Key 必填。
- 默认语言不能为空。
- 如果模型/端点判断为 DashScope FileTrans，需要填写文件 URL 前缀。

## 22. 管理员：TTS 配置

文件：`web/src/components/admin/tts-configuration.tsx`

功能：

- 配置语音合成模型。

字段：

- 模型名称。
- API 端点。
- API Key。
- 默认语音 ID。
- 默认语速。
- 创建时间。
- 更新时间。

按钮：

- “编辑配置”
- 眼睛图标。
- “取消”
- “保存配置”

接口：

- `GET /api/admin/config/tts`
- `POST /api/admin/config/tts`

校验：

- 模型名称、API 端点、API Key 必填。
- 语音 ID 不能为空。
- 语速范围 0.25 到 4.0。

## 23. 管理员：向量配置

文件：`web/src/components/admin/vector-configuration.tsx`

功能：

- 配置知识库 embedding 模型。

字段：

- 模型名称。
- API 端点。
- API Key。
- 向量维度。
- 创建时间。
- 更新时间。

按钮：

- “编辑配置”
- 眼睛图标。
- “取消”
- “保存配置”

接口：

- `GET /api/admin/config/vector`
- `POST /api/admin/config/vector`

校验：

- 模型名称、API 端点、API Key 必填。
- 向量维度必须大于 0。

说明：

- 新上传文档会使用新配置。
- 已有文档不一定自动重建向量。

## 24. 管理员：邮件配置

文件：`web/src/components/admin/email-configuration.tsx`

功能：

- 配置 SMTP 邮件服务。
- 测试连接。
- 设置是否自动发送报告。

字段：

- SMTP 服务器。
- 端口。
- 用户名/邮箱。
- 密码/授权码。
- 发件人邮箱。
- 自动发送报告开关。
- 创建时间。
- 更新时间。

按钮：

- “测试连接”
- “编辑配置”
- 眼睛图标。
- “取消”
- “保存配置”

接口：

- `GET /api/admin/config/email`
- `POST /api/admin/config/email`
- `POST /api/admin/config/email/test`

校验：

- SMTP host、port、user 必填。
- 如果后端尚未配置密码，则密码必填。
- 如果已配置密码，前端允许留空表示保留旧密码。

## 25. 管理员：Coze 配置

文件：`web/src/components/admin/coze-configuration.tsx`

功能：

- 配置 Coze Bot ID 和 API Token。

字段：

- 反方一辩 Bot ID。
- 反方二辩 Bot ID。
- 反方三辩 Bot ID。
- 反方四辩 Bot ID。
- 裁判 Bot ID。
- 辅助/导师 Bot ID。
- API Token。
- 其他参数 JSON。
- 创建时间。
- 更新时间。

按钮：

- “编辑配置”
- 眼睛图标。
- “取消”
- “保存配置”

接口：

- `GET /api/admin/config/coze`
- `POST /api/admin/config/coze`

校验：

- API Token 必填。
- 至少填写一个 Bot ID。
- 其他参数必须是合法 JSON。

## 26. 后端接口总表

### 26.1 Auth

| 方法 | 路径 | 用途 | 前端使用位置 |
|---|---|---|---|
| GET | `/api/auth/classes/public` | 获取公开班级列表 | 注册页、个人中心 |
| POST | `/api/auth/register/teacher` | 教师注册 | 登录页 |
| POST | `/api/auth/register/student` | 学生注册 | 登录页 |
| POST | `/api/auth/login` | 登录 | 登录页 |
| POST | `/api/auth/refresh` | 刷新 Token | TokenManager |
| POST | `/api/auth/change-password` | 修改密码 | 个人中心 |
| GET | `/api/auth/profile` | 获取个人信息 | 个人中心 |
| PUT | `/api/auth/profile` | 更新个人信息 | 个人中心 |
| POST | `/api/auth/delete-account` | 注销账户 | service 中存在，当前主要页面未暴露 |

### 26.2 Student

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/student/profile` | 获取学生资料 |
| PUT | `/api/student/profile` | 更新学生资料 |
| POST | `/api/student/assessment` | 提交能力评估 |
| GET | `/api/student/assessment` | 获取能力评估 |
| GET | `/api/student/debates` | 获取可参与辩论 |
| GET | `/api/student/debates/{debate_id}/participants` | 获取辩论参与者 |
| POST | `/api/student/debates/join` | 邀请码加入辩论 |
| GET | `/api/student/reports/{debate_id}` | 获取报告 |
| GET | `/api/student/reports/{debate_id}/export/pdf` | 导出 PDF |
| GET | `/api/student/reports/{debate_id}/export/excel` | 导出 Excel |
| POST | `/api/student/reports/{debate_id}/send-email` | 发送报告邮件 |
| GET | `/api/student/history` | 历史记录 |
| GET | `/api/student/history/filter` | 筛选历史 |
| GET | `/api/student/history/{debate_id}` | 辩论详情/回放数据 |
| GET | `/api/student/analytics` | 学生统计 |
| GET | `/api/student/analytics/growth` | 成长趋势 |
| GET | `/api/student/comparison/class` | 班级对比 |
| GET | `/api/student/achievements/v2` | 成就列表 |
| POST | `/api/student/achievements/check/v2` | 检查成就 |

### 26.3 Student KB

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/student/kb/sessions` | 获取会话列表 |
| POST | `/api/student/kb/ask/stream` | 流式知识库问答 |
| POST | `/api/student/kb/ask` | 非流式知识库问答 |
| GET | `/api/student/kb/conversations/{session_id}` | 获取会话历史 |
| GET | `/api/student/kb/documents` | 学生查看知识库文档 |
| GET | `/api/student/kb/documents/{document_id}/download` | 下载文档 |

### 26.4 Teacher

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/teacher/classes` | 创建班级，service 存在 |
| GET | `/api/teacher/classes` | 获取教师班级 |
| GET | `/api/teacher/dashboard` | 获取教师统计 |
| POST | `/api/teacher/students` | 添加学生，service 存在 |
| GET | `/api/teacher/students` | 获取学生列表 |
| POST | `/api/teacher/debates` | 创建辩论 |
| PUT | `/api/teacher/debates/{debate_id}` | 更新辩论 |
| GET | `/api/teacher/debates/{debate_id}` | 获取辩论详情 |
| GET | `/api/teacher/debates` | 获取辩论列表 |
| GET | `/api/teacher/debates/{debate_id}/support-documents` | 获取支撑材料 |
| POST | `/api/teacher/debates/{debate_id}/support-documents` | 上传支撑材料 |
| DELETE | `/api/teacher/debates/{debate_id}/support-documents/{document_id}` | 删除支撑材料 |

### 26.5 Admin

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/admin/classes` | 获取全部班级 |
| POST | `/api/admin/classes` | 创建班级 |
| PUT | `/api/admin/classes/{class_id}` | 更新班级 |
| DELETE | `/api/admin/classes/{class_id}` | 删除班级 |
| GET | `/api/admin/config/models` | 获取模型配置 |
| POST | `/api/admin/config/models` | 更新模型配置 |
| GET | `/api/admin/config/asr` | 获取 ASR 配置 |
| POST | `/api/admin/config/asr` | 更新 ASR 配置 |
| GET | `/api/admin/config/tts` | 获取 TTS 配置 |
| POST | `/api/admin/config/tts` | 更新 TTS 配置 |
| GET | `/api/admin/config/vector` | 获取向量配置 |
| POST | `/api/admin/config/vector` | 更新向量配置 |
| GET | `/api/admin/config/email` | 获取邮件配置 |
| POST | `/api/admin/config/email` | 更新邮件配置 |
| POST | `/api/admin/config/email/test` | 测试邮件连接 |
| GET | `/api/admin/config/coze` | 获取 Coze 配置 |
| POST | `/api/admin/config/coze` | 更新 Coze 配置 |
| GET | `/api/admin/users` | 获取用户列表 |
| GET | `/api/admin/users/{user_id}` | 获取用户详情 |
| PUT | `/api/admin/users/{user_id}` | 更新用户 |
| PUT | `/api/admin/password` | 修改管理员密码 |

### 26.6 Admin KB

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/admin/kb/documents` | 上传知识库文档 |
| GET | `/api/admin/kb/documents` | 获取知识库文档 |
| DELETE | `/api/admin/kb/documents/{document_id}` | 删除知识库文档 |

### 26.7 Voice

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/voice/asr/transcribe` | 上传音频文件 ASR |
| POST | `/api/voice/asr/transcribe/base64` | Base64 音频 ASR |
| POST | `/api/voice/tts/synthesize` | TTS 返回 Base64 |
| POST | `/api/voice/tts/synthesize/file` | TTS 返回音频文件 URL |

注意：实时辩论页主要通过 WebSocket 发送音频，不直接调用这些 HTTP voice 接口。

## 27. 组件分层说明

### 27.1 页面级组件

页面级组件直接由 `AppRouter` 渲染：

- `LoginPortal`
- `StudentCommandCenter`
- `StudentOnboarding`
- `DebateMatchResult`
- `DebateArena`
- `StudentAnalyticsCenter`
- `DebateReportPage`
- `DebateReplayPage`
- `PreparationAssistantPage`
- `TeacherDashboard`
- `AdminDashboard`

### 27.2 业务组件

学生相关：

- `UserProfile`
- `DebateHistoryRecords`
- `DebateTopicCard`
- `WaitingStatusBar`
- `SkillsAssessmentEditor`
- `SkillsRadar`
- `AchievementBadges`
- `AbilityRadarChart`
- `SpeakingTimeChart`

辩论相关：

- `DebateHeader`
- `DebateAudioControl`
- `DebateControls`
- `ParticipantVideo`
- `AIAvatar`
- `TeamDisplay`
- `TeamMember`
- `StanceDisplay`
- `DebateResultDisplay`
- `AIMentorFeedback`

管理员相关：

- `ClassManagement`
- `DocumentManagement`
- `UserManagement`
- `ModelConfiguration`
- `AsrConfiguration`
- `TtsConfiguration`
- `VectorConfiguration`
- `EmailConfiguration`
- `CozeConfiguration`

### 27.3 UI 基础组件

位于 `web/src/components/ui`：

- Button
- Card
- Input
- Tabs
- Dialog
- Alert
- Badge
- Select
- Checkbox
- Switch
- Progress
- Tooltip
- Toast 等

这些组件风格统一，页面尽量复用。

## 28. 数据状态和缓存

### 28.1 Auth 状态

由 `AuthProvider` 管理：

- 用户信息存在 React state。
- Token 和用户信息存在本地存储，由 `TokenManager` 管理。
- storage 事件会同步多标签页登录状态。

### 28.2 StudentService 缓存

`getAvailableDebates` 有短缓存：

- TTL 约 1000ms。
- 防止短时间重复请求。
- 支持 `force` 强制刷新。

### 28.3 AdminService 配置缓存

管理员配置接口有前端内存缓存：

- model_config
- asr_config
- tts_config
- vector_config
- email_config
- coze_config

更新后会写回缓存。

### 28.4 页面轮询

教师控制台：

- 每 15 秒刷新辩论和统计。

管理员知识库：

- 文档处理中时每 5 秒刷新。

学生知识库文档：

- 文档处理中时每 8 秒刷新。

## 29. 当前实现注意事项

1. 没有 URL 路由。所有页面状态存在内存，刷新后当前页面丢失。
2. 登录后角色跳转依赖 `LoginPortal` 的 `onLogin(role)` 回调。
3. 报告页和回放页复用学生端接口，即教师查看报告也使用 `/api/student/...` 相关报告接口。
4. 候场页 `WaitingStatusBar` 的状态是模拟流程，不是实时房间人数。
5. 教师端创建辩论支持草稿和发布；发布时要求至少选择一个学生。
6. 辩论支撑材料只支持 PDF，并且必须已有 debateId。
7. 管理员知识库支持 PDF/DOCX，教师支撑材料仅支持 PDF。
8. 实时辩论的主要业务不是 REST，而是 WebSocket 消息。
9. 前端代码中部分中文显示存在编码异常，但业务含义仍可从变量、接口和上下文判断。
10. 部分按钮已在代码中注释，例如报告页 Excel 导出、邮件发送。

## 30. 推荐给前端后续优化方向

1. 引入 React Router，把页面状态、debateId、reportId、replayId 写入 URL。
2. 增加路由守卫，根据 `user_type` 限制页面访问。
3. 将页面跳转回调抽象为统一 navigation service。
4. 统一接口错误展示，减少各页面重复 toast 逻辑。
5. 给 WebSocket 消息定义更严格的 TypeScript payload 类型。
6. 把教师端“候场/进入实时辩论”的入口重新产品化，目前教师历史里进入辩论按钮被注释。
7. 将模拟候场状态替换为真实房间人数和准备状态。
8. 对知识库文档、报告导出、音频播放等异步任务增加统一任务状态组件。
9. 统一中英文字段和 UI 文案，修复当前文件里的中文编码异常。
10. 将管理员配置页抽象为通用配置表单，减少重复代码。
