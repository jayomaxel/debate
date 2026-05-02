# 辩论链路无 API 日志与连接失败详细解决方案

## 1. 问题背景

当前辩论功能存在两个表象问题：

1. 进入辩论页面后，前后端表现为“能进入页面，但无法正常发言、抢麦、开始辩论或推进环节”。
2. 后端日志中“看不到对应 API 的调用记录”，导致难以判断究竟是前端未发起请求，还是请求/连接已失败但未被日志体系捕获。

本方案基于当前代码实际链路进行梳理，给出：

- 真实调用路径说明
- 当前最可能断点分析
- 为什么后端会出现“看不到 API 调用”的现象
- 推荐的修复与增强方案
- 实施顺序与验收标准

---

## 2. 结论先行

本次问题**不是单一“某个 API 没写好”**，而是以下几类问题叠加后形成的：

### 2.1 辩论页核心交互并不主要依赖 HTTP API

辩论页面只有少量初始化 HTTP 请求，后续真正的核心操作主要依赖 WebSocket：

- 发言
- 语音上传
- 抢麦
- 申请录音
- 开始辩论
- 推进环节
- 结束当前轮次
- 结束辩论

以上操作都不是普通 REST API，而是 WebSocket 消息。

因此，如果后端侧只在盯 HTTP 接口日志，就很容易误判为“根本没有调用”。

### 2.2 当前后端没有统一的请求级访问日志

后端当前有应用日志，但没有显式的 HTTP 请求访问日志中间件，也没有针对 WebSocket 握手与异常关闭的增强日志。因此以下情况都可能让人误以为“没有请求”：

- 前端请求实际发出了，但被 401/403 拦截
- WebSocket 握手失败，直接关闭
- 请求发到了错误的前端/代理入口，而不是实际 API 服务
- 页面进入了辩论路由，但 `roomId` 为空，导致前端根本未发初始化请求

### 2.3 当前最值得优先排查的是三条主线

1. 页面是否通过正确的前端开发入口打开  
   即是否从 `http://127.0.0.1:8860` 或对应代理域名访问。

2. 进入 `DebateArena` 时 `roomId` 是否真实存在  
   如果为空，参与者接口和 WebSocket 都不会发出。

3. WebSocket 是否连上并成功收到 `room_joined` / `state_update`  
   因为当前前端大部分操作都被 `isConnected && roomJoined` 双条件拦住。

---

## 3. 当前代码中的真实辩论链路

下面是老师端进入辩论页后的实际调用链。

### 3.1 页面跳转链路

老师在辩论列表点击“进入”按钮：

- `web/src/components/teacher-dashboard.tsx`
  - 调用 `onNavigate('debate', debate.id)`

路由层接收后：

- `web/src/components/app-router.tsx`
  - `setCurrentDebateId(debateId)`
  - `setCurrentPage('debate')`

最终渲染：

- `web/src/components/app-router.tsx`
  - `<DebateArena roomId={currentDebateId} ... />`

### 3.2 DebateArena 初始化链路

进入辩论页后，`DebateArena` 会并行做两件事：

#### A. 拉取参与者列表

文件：

- `web/src/components/debate-arena.tsx`
- `web/src/services/student.service.ts`

调用逻辑：

- `DebateArena` 中 `useEffect` 检查 `roomId`
- 若 `roomId` 存在，则调用：

```ts
StudentService.getDebateParticipants(roomId)
```

实际 HTTP 请求：

```text
GET /api/student/debates/{debateId}/participants
```

后端对应路由：

- `api/routers/student.py`

说明：

- 该接口支持 `student` 与 `teacher` 访问
- 内部会根据用户类型区分教师视角和学生视角返回参与者信息

#### B. 建立 WebSocket 连接

文件：

- `web/src/hooks/use-websocket.ts`
- `web/src/lib/websocket-client.ts`

逻辑：

- 只要 `roomId` 有值，就会尝试自动连接

实际连接地址：

```text
ws://当前页面host/ws/debate/{roomId}?token={access_token}
```

后端对应入口：

- `api/routers/websocket.py`
- 路由：`/ws/debate/{room_id}`

### 3.3 辩论操作链路

页面进入后，大部分操作不是 HTTP，而是 WebSocket 消息：

| 功能 | 前端消息类型 | 后端处理位置 |
| --- | --- | --- |
| 文本发言 | `speech` | `api/routers/websocket.py` |
| 音频发言 | `audio` | `api/routers/websocket.py` |
| 抢麦 | `grab_mic` | `api/routers/websocket.py` |
| 请求录音 | `request_recording` | `api/routers/websocket.py` |
| 选择发言人 | `select_speaker` | `api/routers/websocket.py` |
| 开始辩论 | `start_debate` | `api/routers/websocket.py` |
| 推进环节 | `advance_segment` | `api/routers/websocket.py` |
| 结束本轮 | `end_turn` | `api/routers/websocket.py` |
| 结束辩论 | `end_debate` | `api/routers/websocket.py` |

因此：

> “进入辩论后无法发言、无法操作”首先要看的是 WebSocket 是否建立、房间是否真正加入，而不是只看 REST API 是否成功。

---

## 4. 为什么后端会出现“看不到 API 调用记录”

### 4.1 后端当前没有专门的 HTTP 请求访问日志

当前后端入口：

- `api/main.py`

当前日志配置：

- `api/logging_config.py`

现状：

- 有应用级 logger
- 没有统一 request logging middleware
- 没有在每个请求进入/结束时输出 method、path、status、耗时

所以如果你盯的是 `app.log`，可能只能看到：

- 某些业务代码内部的 `logger.info`
- 某些异常日志

而看不到：

- `GET /api/student/debates/{id}/participants` 的访问记录
- 401/403 拦截的统一请求记录

### 4.2 WebSocket 不是普通接口日志

辩论的主交互通过 WebSocket 完成，WebSocket 连接失败时，常见情况是：

- token 无效
- room 不存在
- join room 失败
- 页面连接到了错误 host

这些失败多数不会像 REST API 那样，在你习惯看的位置留下“完整访问日志 + 响应结果”。

### 4.3 可能看错了服务入口

前端 Vite 配置中：

- `web/vite.config.ts`

当前开发端口与代理规则：

- 前端端口：`8860`
- `/api -> http://localhost:7860`
- `/ws -> ws://localhost:7860`

如果页面不是从 `8860` 这个前端入口进入，而是从其他 origin 打开：

- API 请求会发往当前页面 origin
- WS 也会连向当前页面 host

此时后端 `7860` 上看不到预期请求，是完全可能的。

---

## 5. 当前最可能的断点分析

## 5.1 断点一：`roomId` 为空，导致初始化请求根本没发

这是最典型的“后端没有任何记录”的一种情况。

前端代码中：

- `web/src/components/debate-arena.tsx`

参与者请求前有显式判断：

```ts
if (!roomId) return;
```

WebSocket 自动连接同样依赖 `roomId`。

一旦 `roomId` 为空：

- 不会请求参与者接口
- 不会建立 WebSocket
- 页面仍可能被渲染出来
- 用户看到的是“进来了，但什么都不能做”

### 现阶段判断

从静态代码看，老师端按钮 -> `onNavigate` -> `setCurrentDebateId` -> `DebateArena roomId` 这条链是接通的。  
但仍需在运行时验证 `currentDebateId` 是否真的有值。

---

## 5.2 断点二：页面未从正确前端入口打开

由于前端默认 `VITE_API_BASE_URL` 为空：

- `web/src/lib/api.ts`
- `web/src/lib/websocket-client.ts`

当前逻辑依赖：

- 页面当前 origin
- Vite 代理

这意味着：

如果浏览器访问的不是前端代理入口，API/WS 都会指向错误位置。

### 典型表现

- 页面能打开
- 部分纯前端 UI 正常显示
- 后端 7860 没有对应请求
- WebSocket 也可能根本没连到正确服务

---

## 5.3 断点三：鉴权失败，但日志不显性

参与者接口需要登录态，前端会自动带 `Authorization`：

- `web/src/lib/api.ts`

如果 token 失效：

- 会先收到 401
- 然后触发 refresh token 逻辑
- refresh 失败后清空 token

文件：

- `web/src/lib/token-manager.ts`

如果你后端没有 request access log，就很容易出现下面的认知偏差：

- 前端其实请求过
- 后端其实返回过 401 或 403
- 但业务日志里没有明显记录
- 最终观察结果被误解为“根本没调”

---

## 5.4 断点四：WebSocket 已连接失败，但前端没有足够可见的定位信息

当前前端很多行为被下列条件拦住：

```ts
isConnected && roomJoined
```

也就是说，即使 WebSocket 只差最后一步没成功：

- 页面能渲染
- 按钮可能存在
- 用户操作无效或被禁用

而当前页面对这几种状态的显式诊断不够充分：

- `roomId` 是否存在
- 当前连接的 WS URL 是什么
- token 是否存在
- 是否收到了 `room_joined`
- 是否收到了首个 `state_update`

### 5.5 当前已确认的真实阻塞点

根据最新日志，当前真正阻塞 AI 链路的不是“没发请求”，而是数据库写入失败：

- WebSocket 已经收到 `start_debate`、`audio`、`end_turn`、`ping`
- AI 回合已经进入 `thinking`
- 但在写入 `speeches` 时失败
- 核心报错是：
  - `column speeches.transcription_status does not exist`
  - `column "transcription_status" of relation "speeches" does not exist`

这说明：

1. HTTP / WebSocket 基础链路是通的
2. AI 回合也确实被触发了
3. 失败点在旧数据库结构，而不是前端没调用
4. 这类错误会让后端看起来“很安静”，因为任务卡在写库前后，没有你期望的业务日志继续往下走

---

## 6. 已确认的现有能力与现状

## 6.1 老师主持权限主链已基本具备

当前代码已具备以下能力：

1. 老师可作为主持进入辩论房间
2. 老师主持身份具有 `can_moderate = true`
3. 老师主持身份具有 `can_speak = false`
4. 老师可以控制辩论流程，但不能发言

对应位置：

- `api/services/room_manager.py`
- `api/routers/websocket.py`
- `web/src/components/debate-arena.tsx`

这说明：  
“老师不能进入辩论”不再是主要结构性问题，当前更像是链路可观测性和连接可靠性问题。

## 6.2 辩论页操作已全面受 `roomJoined` 保护

当前前端修正后，很多操作必须满足：

- WebSocket 已连接
- 已成功加入房间

这本身是对的，但副作用是：  
一旦连接链路某处失败，页面看起来就像“全部操作失效”。

---

## 7. 推荐解决方案总览

建议分为四层处理：

1. **可观测性增强**
2. **前端运行态链路校验**
3. **后端请求与 WebSocket 入口日志增强**
4. **用户体验与错误提示增强**

---

## 8. 方案一：补齐前端运行态调试日志

这是当前最快、最有效的定位手段。

## 8.1 目标

让前端能清楚打印出以下关键信息：

- 点击“进入辩论”时使用的 debateId
- 路由切换时设置的 `currentDebateId`
- `DebateArena` 挂载时收到的 `roomId`
- 当前页面 `window.location.origin`
- 参与者接口最终请求路径
- WebSocket 最终连接 URL
- WebSocket `open / close / error`
- 是否收到 `room_joined`
- 是否收到 `state_update`

## 8.2 建议加日志的位置

### A. 老师端进入按钮

- `web/src/components/teacher-dashboard.tsx`

记录：

- 当前辩论 ID
- 当前辩论状态
- 点击进入的时间点

### B. 路由层

- `web/src/components/app-router.tsx`

记录：

- `onNavigate` 的 page / debateId
- `setCurrentDebateId` 前后的值

### C. DebateArena 初始化

- `web/src/components/debate-arena.tsx`

记录：

- `roomId`
- `window.location.origin`
- 当前用户类型
- 当前 access token 是否存在

### D. 参与者请求

- `web/src/services/student.service.ts`

记录：

- `debateId`
- 实际请求路径

### E. WebSocket 连接

- `web/src/lib/websocket-client.ts`

记录：

- 最终生成的 ws URL
- `onopen`
- `onclose`
- `onerror`

## 8.3 预期收益

加入这些日志后，基本可以在 1 次浏览器调试里直接区分：

- 是没进入链路
- 是 `roomId` 丢了
- 是请求发错地方
- 是 token 问题
- 是 WS 没连上
- 是 WS 连上了但没成功 join room

---

## 9. 方案二：后端增加 HTTP 请求访问日志中间件

## 9.1 目标

让所有 HTTP 请求至少输出：

- method
- path
- query
- status_code
- elapsed_ms
- user_id（可选）

## 9.2 建议输出格式

示例：

```text
[HTTP] GET /api/student/debates/xxx/participants 200 18ms user=teacher_xxx
```

401/403 也必须可见，例如：

```text
[HTTP] GET /api/student/debates/xxx/participants 401 6ms user=anonymous
```

## 9.3 建议实现位置

- `api/main.py`

通过 FastAPI middleware 增加统一请求日志。

## 9.4 预期收益

一旦上线这个中间件，就不会再出现：

> “前端到底有没有调过接口，后端完全看不出来”

这种排查黑箱。

---

## 10. 方案三：后端增强 WebSocket 握手与 join room 日志

## 10.1 目标

对于 `/ws/debate/{room_id}`，至少把以下阶段打全：

1. 握手开始
2. token 校验成功/失败
3. user 查询成功/失败
4. room 是否存在
5. create_room 是否成功
6. join_room 是否成功
7. 首次 `room_joined` 是否已发送
8. 首次 `state_update` 是否已发送
9. 连接关闭原因

## 10.2 当前存在的不足

虽然 `api/routers/websocket.py` 中已有一些日志，但不够系统，不足以快速定位所有分支问题，尤其是：

- 连接压根没来到这个入口
- token 验证失败
- 房间创建失败
- `join_room` 返回 false
- 页面建连 host 错误

## 10.3 推荐日志示例

```text
[WS] connect start room=xxx
[WS] token verified room=xxx user=xxx
[WS] room missing, try create room=xxx
[WS] join_room success room=xxx user=xxx role=teacher_moderator
[WS] initial payload sent room=xxx user=xxx
[WS] disconnect room=xxx user=xxx code=...
```

---

## 11. 方案四：前端增强错误态展示

## 11.1 当前不足

当前用户看到的主要只是：

- 连接失败
- 不能发言
- 操作无响应

但不知道具体是：

- 未获取到辩论 ID
- 未登录
- 参与者接口失败
- WebSocket 未连接
- 已连接但未加入房间
- 权限不足

## 11.2 建议补充的错误提示

辩论页顶部增加调试/状态面板，仅开发环境展示：

- 当前 debateId
- 当前用户身份
- HTTP 参与者接口状态
- WS 连接状态
- roomJoined 状态
- 当前页面 origin
- 当前 WS URL

以及给用户态更明确的提示：

- “未获取到辩论房间 ID，无法连接”
- “当前登录态已失效，请重新登录”
- “已连接服务器，但尚未完成房间加入”
- “当前账号无发言权限”

---

## 12. 针对本问题的排查顺序建议

建议按以下顺序排查，效率最高。

## 第一步：确认访问入口

确认当前页面是否来自：

```text
http://127.0.0.1:8860
```

或对应 cpolar/LAN 前端地址。

如果不是，先修正访问方式，再继续排查。

## 第二步：查看浏览器 Network

进入辩论页后必须检查：

1. 是否发起  
   `GET /api/student/debates/{id}/participants`

2. 是否发起  
   `WS /ws/debate/{id}`

### 判断规则

- 如果 1 和 2 都没有  
  大概率是 `roomId` 为空

- 如果 1 有，2 没有  
  说明 WS 连接链路有问题

- 如果 1 有 401/403  
  说明是鉴权/权限问题，不是“没调”

- 如果 2 发起了但握手失败  
  说明问题在 token、host、room、join_room 其中之一

## 第三步：查看浏览器 Console

配合前端调试日志确认：

- `onNavigate` 是否触发
- `currentDebateId` 是否设置成功
- `roomId` 是否存在
- 实际 ws URL 是什么
- 是否收到 `room_joined`

## 第四步：查看后端 access log / WS 日志

如果已经补了日志，可以直接判断：

- 请求有没有到
- 到的是哪个 path
- 返回了什么状态
- WebSocket 在哪一步失败

---

## 13. 建议的最终修改项清单

以下为建议落地的正式修改项。

## A. 前端

1. 在老师进入辩论按钮处增加调试日志
2. 在 `AppRouter` 中增加 `currentDebateId` 设置日志
3. 在 `DebateArena` 挂载时输出：
   - `roomId`
   - `origin`
   - token 是否存在
4. 在参与者请求前后输出请求信息与结果
5. 在 `WebSocketClient` 中输出最终 ws URL、open、close、error
6. 在辩论页开发环境增加连接状态面板
7. 在初始化失败时增加更明确的用户提示

## B. 后端

1. 增加统一 HTTP 请求日志中间件
2. 增强 WebSocket 握手日志
3. 增强 `join_room` 成功/失败日志
4. 增强 token 校验失败日志
5. 增强房间创建失败日志
6. 为 WebSocket close reason 输出统一格式

## C. 配置与环境

1. 明确开发环境统一入口为 `8860`
2. 团队约定不得绕过前端代理直接打开不正确页面入口
3. 如果后续有多环境需求，可考虑显式配置 `VITE_API_BASE_URL`

---

## 14. 验收标准

完成方案后，至少满足以下验收条件。

## 14.1 功能验收

1. 老师点击“进入”后能稳定进入辩论页
2. 老师身份可成功建立辩论房间连接
3. 老师可看到辩论态势、报告入口等信息
4. 老师无发言按钮或发言能力被明确禁用
5. 学生进入辩论页后可正常连接并执行允许的发言操作

## 14.2 日志验收

1. 每次进入辩论页时，后端可看到参与者接口请求日志
2. 每次建立辩论 WebSocket 时，后端可看到握手与 join room 日志
3. 每次连接失败时，可明确区分：
   - token 失败
   - roomId 缺失
   - 房间不存在
   - join_room 失败
   - 权限不足

## 14.3 排查效率验收

对于任一“进入辩论后不可操作”的问题，开发人员应能在：

- 1 次浏览器 Network 检查
- 1 次浏览器 Console 检查
- 1 次后端日志查看

内快速判断根因。

---

## 15. 推荐实施顺序

建议分三批完成。

## 第一批：定位能力补齐

优先做：

1. 前端运行态调试日志
2. 后端 HTTP 请求日志
3. 后端 WebSocket 握手日志

理由：

- 不先补观察能力，后续问题会反复陷入“看起来没调”的困境

## 第二批：连接失败体验优化

再做：

1. 辩论页连接状态可视化
2. 更细的错误提示
3. 开发环境状态面板

## 第三批：环境规范与收口

最后做：

1. 统一开发访问入口说明
2. 如有必要，补充显式环境变量配置
3. 更新团队排查手册

---

## 16. 最终判断

结合当前代码现状，本次问题最有可能的真实根因排序如下：

1. **WebSocket 连接链路异常，而非发言 REST API 异常**
2. **页面访问入口不正确，导致请求/WS 未打到目标后端**
3. **运行时 `roomId` 丢失，导致前端根本未发初始化请求**
4. **鉴权失败存在，但后端缺少访问日志，造成“没有调用记录”的错觉**

因此，本问题的最佳解决思路不是继续盲查某一个“死 API”，而是：

> 先补足链路可观测性，再基于真实请求与真实 WebSocket 状态定位最终故障点。

---

## 17. 附：本次排查对应的关键代码位置

### 前端

- `web/src/components/teacher-dashboard.tsx`
- `web/src/components/app-router.tsx`
- `web/src/components/debate-arena.tsx`
- `web/src/hooks/use-websocket.ts`
- `web/src/lib/websocket-client.ts`
- `web/src/lib/api.ts`
- `web/src/lib/token-manager.ts`
- `web/src/services/student.service.ts`
- `web/vite.config.ts`

### 后端

- `api/main.py`
- `api/logging_config.py`
- `api/routers/student.py`
- `api/routers/websocket.py`
- `api/services/room_manager.py`
- `api/middleware/auth_middleware.py`

---

## 18. 建议的下一步

如果要继续推进，建议下一步直接进入实施：

1. 先补前端/后端调试日志
2. 复现一次老师进入辩论流程
3. 根据日志确定究竟是：
   - `roomId` 问题
   - host/origin 问题
   - token 问题
   - WebSocket 握手问题
   - join_room 问题

这样能在最短时间内把“无日志、无法发言、无法操作”的问题彻底收敛。

---

## 19. 本次落地勾选

- [x] 前端补充 `room_joined` / `state_update` 可见提示
- [x] 前端补充参与者加载失败提示
- [x] 前端补充 AI `thinking` 超时展示
- [x] 修复 `debate-arena.tsx` 重复 `debateReady` 定义
- [x] 后端补充 AI 回合入口日志
- [x] 后端补充 AI 草稿与 Speech 持久化日志
- [x] 数据库启动时补 `speeches.transcription_status` 兼容兜底

## 20. 我自己的解决方案

我建议把这条链路拆成“先让它不黑盒，再让它不炸库，再让老师角色独立”三步：

1. 先确保 `room_joined` 和 `state_update` 都能被前端明确收到
2. 先修数据库迁移或启动兼容，让 `Speech` 写入不再因旧库字段缺失失败
3. 再继续收敛老师主持模式，保证老师只拿流程控制和报告权限，不再占用发言位
