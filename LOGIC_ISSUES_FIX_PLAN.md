# 辩论流程类似逻辑问题整改方案

## 背景

本次巡检聚焦于辩论房间的状态机、阶段推进、AI 发言任务、语音识别、音频播放闸门和前端控制逻辑。此前已发现并修复“人类提问方无发言时，AI 回答方持续思考且强制下一阶段无响应”的问题。该问题本质是：异步任务依赖前置输入，但流程状态没有统一的跳过、超时、失败恢复策略。

本文档整理同类风险点，并给出后续详细修改方案。当前文档仅作为方案记录，暂不修改业务代码。

## 总体原则

1. 状态推进必须有单一可信出口。
   - 阶段自然结束、强制推进、播放完成、AI 发言完成，都应收敛到同一类推进函数。
   - 不应在多个位置分别维护“结束辩论”“推进阶段”“释放麦克风”的业务副作用。

2. 异步结果必须带阶段校验。
   - ASR、TTS、LLM、播放回执等异步结果返回时，应验证当前房间仍处于发起该任务时的 `segment_id`、`speaker_role` 和处理状态。
   - 过期结果只能更新对应历史记录，不能污染当前房间状态。

3. 失败态必须有明确恢复路径。
   - 失败可分为可重试、可跳过、必须阻断三类。
   - 用户可见按钮与后端处理应一致，例如“强制下一阶段”应能跳出非致命失败。

4. 前后端流程定义应避免硬编码副本。
   - 前端展示、最后一段判断、结束按钮展示，应优先来自后端状态或后端提供的 segments。

## 问题一：末段自然推进不会走正式结辩流程

### 现象

当最后一个 segment 结束后，`flow_controller._apply_current_segment()` 在 `index >= len(segments)` 时只会把房间内存状态设置为 `FINISHED`，并广播 `phase_change`。但正式结辩逻辑位于 `room_manager.end_debate()`，其中包含：

- 数据库 debate 状态更新为 `completed`
- 写入 `end_time`
- 清理流程控制器
- 广播 `debate_processing`
- 自动评分与报告生成
- 广播 `debate_ended`

### 影响

如果最后一段靠计时器自然结束，或主持人继续强制推进到最后之后，可能出现：

- 前端显示已结束，但报告不生成
- 数据库状态仍为 `in_progress`
- 教师/学生端无法查看完整结果
- 房间资源清理不完整

### 修改方案

推荐新增统一的结束入口：

```python
async def finish_debate_flow(room_id: str, reason: str = "flow_completed") -> bool:
    ...
```

该入口由 `flow_controller` 负责调用 `room_manager.end_debate()`，而不是自己只改内存状态。

#### 具体改动点

1. 在 `DebateFlowController._apply_current_segment()` 中，当 `index >= len(segments)` 时：
   - 不再直接设置 `current_phase=FINISHED`
   - 调用统一结束方法
   - 若 DB session 不可用，至少记录错误并广播明确错误事件

2. 在 `DebateRoomManager.end_debate()` 中：
   - 保持当前正式结辩逻辑
   - 确保重复调用幂等：如果已经 `FINISHED/completed`，不重复评分，但可返回成功

3. 在 WebSocket `handle_end_debate_message()` 中：
   - 仍可直接调用 `room_manager.end_debate()`
   - 或改为调用 `flow_controller.finish_debate_flow()`，使主持人手动结束和自然结束走同一逻辑

### 测试建议

新增后端测试：

- 最后一段 `advance_segment()` 后，DB debate 状态变为 `completed`
- 会广播 `debate_processing` 和 `debate_ended`
- 重复调用结束方法不会重复评分
- 评分失败时，房间仍能进入 finished，并保留错误日志

## 问题二：ASR 异步完成后可能污染下一阶段状态

### 现象

音频发言开始时，后端会记录当时的 `segment_id`，并将房间状态设置为：

- `turn_processing_status="processing"`
- `turn_processing_kind="asr"`
- `turn_speech_user_id=user_id`
- `turn_speech_role=user_role`

但 ASR 成功或失败后，会无条件更新当前房间的处理状态。若主持人在 ASR 期间强制下一阶段，旧 ASR 结果可能在下一阶段回写：

- `turn_processing_status="succeeded"` 或 `"failed"`
- `turn_speech_committed=True`
- `turn_speech_role=旧发言人`
- `pending_advance_reason` 被错误消费

### 影响

- 新阶段可能被标记为已经发言
- 结束回合按钮可能异常可用或不可用
- 旧阶段失败态阻塞新阶段
- 旧阶段成功态触发新阶段自动推进

### 修改方案

引入“回合处理令牌”或至少使用阶段快照校验。

推荐轻量方案：在 ASR 开始时保存快照：

- `segment_id`
- `current_phase`
- `current_speaker`
- `user_id`
- `user_role`
- 可选 `turn_processing_token`

ASR 结束回写前检查：

```python
latest = room_manager.get_room_state(room_id)
if (
    not latest
    or latest.segment_id != started_segment_id
    or latest.current_speaker != started_user_role
    or latest.turn_processing_kind != "asr"
    or latest.turn_speech_user_id != user_id
):
    # 只更新 speech 数据库记录和广播 transcript，不更新房间 turn 状态
    return
```

#### 具体改动点

1. `handle_audio_message()`：
   - 在进入 ASR 前创建本地 `turn_snapshot`
   - ASR 成功后，先更新 speech 内容
   - 只有快照仍匹配时，才更新 `turn_processing_status` 和 `turn_speech_committed`

2. ASR 失败路径：
   - 如果快照已经过期，不再把当前房间置为 failed
   - 可广播旧 speech 的 `transcription_status="failed"`，让前端展示该条音频识别失败

3. pending advance 消费：
   - 只有快照仍匹配且 `latest_state.segment_id == started_segment_id` 时才消费

### 测试建议

新增后端测试：

- ASR processing 时强制推进，随后 ASR 成功，不应修改新阶段 `turn_speech_committed`
- ASR processing 时强制推进，随后 ASR 失败，不应把新阶段置为 failed
- ASR 在原阶段成功，仍可正常消费 `pending_advance_reason`

## 问题三：自由辩论抢麦超时后不会自动交给 AI

### 现象

自由辩论中，人类抢麦后如果没有点击结束发言，也没有提交有效内容，计时器到 `mic_expires_at` 后仅清理：

- `mic_owner_user_id`
- `mic_owner_role`
- `mic_expires_at`
- `current_speaker`

没有设置：

- `free_debate_next_side="ai"`

也没有触发：

- `trigger_free_debate_ai_turn(room_id)`

### 影响

人类可以反复抢麦并沉默，AI 永远不会自然接话。自由辩论节奏可能停在人类侧。

### 修改方案

将“人类自由辩论麦克风过期”视为一次人类回合结束，交给 AI。

#### 具体改动点

1. 在 `_timer_loop()` 麦克风过期分支中：
   - 如果 `mic_owner_role` 是 `debater_*`
   - 清理麦克风后设置 `free_debate_last_side="human"`、`free_debate_next_side="ai"`
   - 广播 `mic_released reason="expired"`
   - 创建任务 `trigger_free_debate_ai_turn(room_id)`

2. 如果 `mic_owner_role` 是 `ai_*`：
   - 过期可视为 AI 超时结束
   - 设置 `free_debate_last_side="ai"`、`free_debate_next_side="human"`
   - 清理 `ai_turn_status`

3. 防抖：
   - 触发 AI 前检查 `free_debate_next_side=="ai"` 且没有活跃 AI task

### 测试建议

新增后端测试：

- 人类持麦过期后，状态切到 `free_debate_next_side="ai"`
- 会触发一次 AI 自由辩论任务
- AI 持麦过期后，状态切回 human
- 重复 timer tick 不会重复触发多个 AI 任务

## 问题四：choice 模式前端没有选择发言人入口

### 现象

后端支持 `select_speaker` 消息，但前端没有发送该消息。choice 段进入时，后端默认选择 `speaker_options[0]` 作为当前发言人。

### 影响

配置上允许多个候选发言人的阶段，实际只有第一个候选人能发言。例：

- `questioning_1_pos_answer`: `debater_2` 或 `debater_3`
- `questioning_3_pos_answer`: `debater_1` 或 `debater_4`

### 修改方案

在前端当前阶段区域增加候选发言人选择控件。

#### 具体改动点

1. `DebateArena`：
   - 当 `speakerMode === "choice"` 且当前用户角色在 `speakerOptions` 中时，显示“选择我来回答”按钮
   - 点击发送 `send("select_speaker", { role: currentUserRole })`

2. 后端 `handle_select_speaker_message()`：
   - 保留现有权限校验
   - 可补充：若本段已经 `turn_speech_committed=True`，不允许切换

3. 前端收到 `speaker_selected`：
   - 更新 `currentSpeakerRole`
   - 可 toast 提示“已切换发言人”

### 测试建议

新增前端测试：

- choice 阶段候选用户可看到选择按钮
- 非候选用户不可见
- 点击后发送 `select_speaker`
- 收到 `speaker_selected` 后 UI 更新当前发言人

新增后端测试：

- 候选发言人可选择自己
- 非候选发言人不可选择
- 已发言后不能切换

## 问题五：ASR 失败会留下空 speech 记录

### 现象

音频消息处理时，后端先创建一条空内容 speech 占位记录。若 ASR 失败，该记录不会删除，也没有明确失败字段。

### 影响

- 回放记录中可能出现空文本
- 报告/评分可能读到空发言
- 后续 AI 上下文可能包含无效 speech

### 修改方案

推荐保留原始音频记录，但明确标记其转写失败，避免评分和 AI 上下文使用。

#### 具体改动点

1. 数据模型层：
   - 如果已有字段可用，使用现有字段表示失败
   - 如果没有，考虑给 `Speech` 增加：
     - `transcription_status`
     - `transcription_error`
     - `is_valid_for_scoring`

2. 查询层：
   - `_load_recent_speeches()` 过滤空内容或 `is_valid_for_scoring=False` 的记录
   - 评分服务过滤无效 speech

3. WebSocket 广播：
   - ASR 失败时广播同一 `speech_id` 的 `transcription_status="failed"`
   - 前端在 transcript 中显示“语音识别失败，可重试”

### 测试建议

- ASR 失败后 speech 不参与 AI 上下文
- ASR 失败后报告评分不包含该空内容
- 前端能合并同一 `speech_id` 并显示失败态

## 问题六：文本发言接口缺少后端空内容校验

### 现象

前端输入框禁用了空文本提交，但后端 `handle_speech_message()` 没有拒绝空字符串。直接发送 WS `speech` 可提交空内容，并标记回合已发言。

### 影响

- 可绕过发言要求
- 盘问阶段可能出现“空问题”
- AI 依赖空输入时仍可能进入异常路径

### 修改方案

在后端 `handle_speech_message()` 增加空内容校验。

#### 具体改动点

1. 读取 content 后：

```python
content = str(data.get("content") or "").strip()
if not content:
    send error to user
    return
```

2. 若业务允许“跳过发言”：
   - 不应通过空 speech 表示
   - 应新增明确消息类型，如 `skip_turn`
   - skip 后由流程控制器决定是否推进或触发 AI

### 测试建议

- 空文本 speech 被拒绝
- 空白字符串 speech 被拒绝
- 正常文本仍可提交并标记 `turn_speech_committed=True`

## 问题七：关闭自动播放时播放闸门只能等待超时

### 现象

前端关闭自动播放后，会忽略 TTS stream start/chunk/end，不向后端发送播放完成回执。后端最终依赖播放闸门 deadline 自动释放。

### 影响

不构成死锁，但会带来固定延迟：

- 固定发言阶段延迟推进
- 自由辩论中 AI 麦克风延迟释放
- 用户感觉 AI 已经说完但界面仍等待

### 修改方案

关闭自动播放时，前端应明确告诉后端“本客户端跳过播放”。

#### 具体改动点

1. `handleTtsStreamStart()` 中，如果 `autoPlayEnabledRef.current` 为 false：
   - 发送 `speech_playback_failed` 或新增 `speech_playback_skipped`
   - 带上 `speech_id`、`speaker_role`、`segment_id`

2. 后端：
   - 当前已有 `handle_speech_playback_failed()`，可复用为 skipped
   - 更清晰方案是新增 `speech_playback_skipped` 消息类型

3. 注意 controller 权限：
   - 只有 playback controller 的 skipped 才能释放闸门
   - 非 controller 客户端关闭自动播放不应影响全局推进

### 测试建议

- controller 关闭自动播放时，AI 发言后立即释放播放闸门
- 非 controller 关闭自动播放时，不影响 playback gate
- 没有任何 controller 在线时，仍走 deadline 兜底

## 问题八：前端阶段列表是硬编码副本

### 现象

`DebateArena` 内维护了一份固定 `flowSegments`。后端也有一份默认 segments。如果后端流程调整，前端进度条、最后一段判断和结束按钮可能不同步。

### 影响

- 进度显示错误
- “强制下一阶段”或“结束辩论”按钮显示条件错误
- 自定义赛制无法正确展示

### 修改方案

由后端在 `state_update` 或 `segment_change` 中下发完整 segments 元数据，前端不再硬编码。

#### 具体改动点

1. 后端：
   - `RoomState.to_dict()` 可附加 `segments` 或新增 `flow_segments`
   - 至少包含 `id`、`title`、`phase`、`duration`、`mode`

2. 前端：
   - 优先使用后端下发 segments
   - 仅在未收到时使用本地 fallback
   - `isLastSegment` 基于后端 segments 计算

3. 如果 segments 较大：
   - 可只在 `debate_started` 或首次 `state_update` 下发

### 测试建议

- 后端下发自定义 segments 时，前端进度按自定义列表展示
- 最后一段判断跟随后端 segments
- 未下发 segments 时 fallback 仍可工作

## 建议实施顺序

### 第一阶段：状态机止血

1. 修复末段自然结束不走正式结辩流程。
2. 修复 ASR 异步回写污染新阶段。
3. 增加文本 speech 后端空内容校验。

这三项优先级最高，直接影响流程是否结束、报告是否生成、状态是否被旧异步任务污染。

### 第二阶段：自由辩论节奏

1. 人类持麦超时后自动交给 AI。
2. AI 持麦超时后自动释放给 human。
3. 增加重复触发 AI task 的防抖测试。

### 第三阶段：用户体验和一致性

1. choice 模式增加前端选择发言人入口。
2. 自动播放关闭时显式发送 skipped 回执。
3. 前端流程列表改为后端下发。

### 第四阶段：数据质量

1. ASR 失败 speech 标记无效。
2. AI 上下文和评分过滤无效 speech。
3. 回放页显示转写失败状态。

## 回归测试清单

后端：

- `pytest api/tests/test_websocket.py`
- 覆盖自然结束、强制结束、ASR 成功/失败、AI 思考超时、播放闸门释放

前端：

- `pnpm test`
- 覆盖 choice 选择发言人、自动播放关闭、AI 播放回执、自由辩论抢麦状态

手工联调：

1. 正常完整辩论直到最后一段自然结束，确认报告生成。
2. 人类音频发言 ASR 中途强制下一阶段，确认新阶段不被旧 ASR 污染。
3. 自由辩论人类抢麦后不说话，等待 30 秒，确认 AI 自动接话。
4. 关闭自动播放后进入 AI 发言，确认流程不等待过长 deadline。
5. 盘问 choice 阶段，候选辩手可以选择自己回答。

## 风险提示

- 结束流程统一到 `room_manager.end_debate()` 后，要确认评分生成时间较长时前端遮罩和 WebSocket 连接不会被误判为卡死。
- ASR 过期结果仍应更新 speech 本身，否则回放记录会缺失用户音频内容。
- 自动播放 skipped 需要保持 controller 机制，避免任意旁观客户端释放全局播放闸门。
- 前端 segments 改为后端下发时，要保留 fallback，避免旧房间或异常连接下页面空白。
