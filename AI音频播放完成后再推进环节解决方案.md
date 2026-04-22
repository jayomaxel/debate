# AI音频播放完成后再推进环节解决方案

## 1. 问题现象

当前系统在固定 AI 环节中存在以下体验问题：

- 第一个 AI 的音频还没播放完，环节已经推进到下一个 AI 发言。
- 第二个 AI 的音频还没播放完，环节已经推进到人类发言。
- 前端还在播上一条 AI 语音时，房间状态、当前发言人和可操作按钮已经切到下一环节，导致用户感知错乱。

这个问题本质上不是“AI 生成太快”，而是“环节推进依据错了”。

当前推进依据是：

- 后端认为 TTS 已经生成完成。

但业务真正需要的推进依据是：

- 前端已经把当前 AI 的语音播放完成，或者至少达到了可接受的播放结束判定。

## 2. 结合当前项目的根因定位

### 2.1 后端在 TTS 完成后立即推进环节

当前 `api/services/flow_controller.py` 的 `run_ai_turn(...)` 在 `release_ai_speech(...)` 返回成功后，会直接调用 `advance_segment(...)`。

也就是说，当前链路等的是：

- 文本已生成。
- 音频已合成。
- 音频文件已保存。
- WebSocket 已经把 `speech` 和 `tts_stream_end` 广播出去。

它没有等的是：

- 某个前端页面实际把这段音频播完。

这就是“后端状态已经进入下一环节，但前端耳朵里还在听上一环节”的直接原因。

### 2.2 `release_ai_speech(...)` 的成功语义是“可播放”，不是“已播完”

当前 `release_ai_speech(...)` 做的事情是：

1. 创建 `Speech`。
2. 广播文本。
3. 流式推送 PCM chunk。
4. 生成最终音频文件并广播 `audio_url`。
5. 更新 `turn_processing_status="succeeded"`。

这里的 `succeeded` 语义是：

- 这段 AI 语音已经准备好了，前端现在可以播。

不是：

- 这段 AI 语音已经被前端播完。

### 2.3 前端播放器只做本地播放，没有回传“播放结束确认”

当前前端有两条播放链路：

- `web/src/components/debate-arena.tsx` + `web/src/lib/pcm-stream-player.ts`
  负责流式 PCM 播放。
- `web/src/components/debate-controls.tsx`
  负责最终 `audio_url` 的整段自动播放和手动播放。

这两条链路当前都只更新本地 UI 状态，没有给后端发送任何“开始播放 / 播放完成”的回执。

也就是说：

- 前端知道它什么时候播完了。
- 后端完全不知道。

### 2.4 当前 `RoomState` 没有“播放栅栏”概念

当前 `api/services/room_manager.py` 的 `RoomState` 已有：

- `turn_processing_status`
- `turn_processing_kind`
- `pending_advance_reason`
- `ai_turn_status`

这些字段主要覆盖：

- ASR 是否完成。
- TTS 是否完成。
- AI 当前在 thinking / ready / speaking 哪个阶段。

但没有任何字段表示：

- 当前 AI 发言是否还在前端播放中。
- 当前环节是否必须等待播放结束后才能推进。
- 哪个前端客户端是“播放完成确认”的基准客户端。

因此当前系统只能做到“生成完成即推进”，做不到“播放完成再推进”。

## 3. 目标

本轮方案目标不是重做整套辩论流程，而是在当前架构上补上“AI音频播放栅栏”。

改造后要达到的行为是：

1. 固定 AI 环节中，当前 AI 音频未播完前，不进入下一个 segment。
2. AI 对 AI 的连续环节之间，必须严格串行播放。
3. AI 到人类的切换，必须以当前 AI 音频结束为边界。
4. 自由辩中，如果 AI 持麦发言，也应在音频播完后再释放麦克风。
5. 系统必须保留超时兜底，避免因为前端没回执而卡死整场辩论。

## 4. 可选方案对比

### 方案 A：后端按音频时长直接 `sleep` 后再推进

做法：

- AI 发言完成后，后端根据 `Speech.duration` 或音频时长估算，`sleep(duration + buffer)` 后再 `advance_segment(...)`。

优点：

- 改动最小。
- 基本不用改前端协议。
- 能快速止住“秒切下个环节”的问题。

缺点：

- 只能等“估计时长”，不能等“真实播放结束”。
- 浏览器自动播放失败、页面卡顿、流式播放队列堆积时，后端仍会提前推进。
- 无法区分“流式 PCM 已播完”与“最终音频 URL 还没播完”。

适用性判断：

- 可以作为止血补丁。
- 不适合作为最终方案。

### 方案 B：前端播放确认 + 后端超时兜底

做法：

- 后端在 AI 语音生成完成后进入“等待播放结束”状态，不立即推进。
- 前端在实际播放开始 / 结束时回传 WebSocket 事件。
- 后端收到“播放结束”后再推进。
- 若前端迟迟未回传，则按超时兜底推进。

优点：

- 语义正确。
- 能覆盖流式播放和整段音频播放两条链路。
- 能解释和解决“AI 还在说，环节已经变了”的核心问题。

缺点：

- 需要改前后端协议。
- 需要定义一个“谁来回传播放完成”的基准客户端。

适用性判断：

- 这是最适合当前项目的推荐方案。

### 方案 C：等待所有客户端都确认播放完成

做法：

- 后端收集所有在线客户端的播放完成确认，全部到齐后再推进。

缺点非常明显：

- 有人切后台、关自动播放、网慢、掉线，整场就卡住。
- 多人设备的实际播放时刻天然不一致。

适用性判断：

- 不推荐。

## 5. 推荐方案

推荐采用：

- 方案 B 作为正式方案。
- 如需快速止血，可先临时叠加方案 A 的短期延迟推进。

## 6. 推荐方案的核心设计

### 6.1 增加“AI播放栅栏”
状态：已完成

建议在 `RoomState` 中新增一组独立字段，不要复用 `turn_processing_status`。

建议新增字段：

- ~~`playback_gate_status`~~
  可取值：`idle` / `waiting` / `playing` / `completed` / `timeout` / `skipped`
- ~~`playback_gate_speech_id`~~
  当前等待播放完成的 AI `speech_id`
- ~~`playback_gate_segment_id`~~
  当前等待释放的 segment
- ~~`playback_gate_speaker_role`~~
  当前等待释放的 AI 角色
- ~~`playback_gate_controller_user_id`~~
  当前被指定为“播放确认基准”的客户端用户 ID
- ~~`playback_gate_started_at`~~
  播放栅栏开始时间
- ~~`playback_gate_deadline_at`~~
  后端兜底超时时间
- ~~`pending_post_playback_action`~~
  播放结束后要执行的动作，建议取值：`advance_segment` / `release_mic` / `none`

这样做的原因是：

- `turn_processing_status` 当前承担的是 ASR / TTS 处理语义。
- 如果把“播放中”也塞进去，会干扰已有的 `end_turn`、`timeout`、`advance_deferred` 逻辑。

### 6.2 明确“谁的播放结束”作为推进依据
状态：已完成

后端不能等所有客户端都播完，必须只认一个“基准客户端”。

建议策略：

1. ~~优先使用 `debater_1` 对应的在线客户端。~~
2. ~~若 `debater_1` 不在线，则选择第一个在线且处于辩论页的客户端。~~
3. ~~若当前基准客户端断线，则自动重选。~~

这样设计的原因是：

- 目前项目里 `debater_1` 本身就具备推进环节权限，天然更接近“主持控制端”。
- 只认一个基准客户端，能避免多人设备播放时差导致的无限等待。

### 6.3 后端固定环节的新流程
状态：已完成

固定 AI 环节建议改成如下时序：

1. ~~`run_ai_turn(...)` 正常完成草稿准备。~~
2. ~~`release_ai_speech(...)` 正常创建 `Speech`、广播文本、推送流式音频、生成最终音频地址。~~
3. ~~不再在 `run_ai_turn(...)` 末尾直接 `advance_segment(...)`。~~
4. ~~改为进入 `playback_gate_status="waiting"`。~~
5. ~~后端记录：~~
   - 当前 `speech_id`
   - 当前 `segment_id`
   - 当前 `speaker_role`
   - 当前 `controller_user_id`
   - `deadline_at`
6. ~~当前端回传“播放开始”时，将状态改为 `playing`。~~
7. ~~当前端回传“播放结束”时，校验：~~
   - `speech_id` 一致
   - `segment_id` 仍一致
   - 回执用户是当前 `controller_user_id`
8. ~~校验通过后再执行 `advance_segment(...)`。~~

### 6.4 自由辩的新流程
状态：已完成

自由辩不应在 AI 文本和音频一准备好就立即释放麦克风。

建议改成：

1. ~~AI 进入 `speaking` 状态并推送文本 / 音频。~~
2. ~~同时建立 `playback_gate`，`pending_post_playback_action="release_mic"`。~~
3. ~~当前端确认播放结束后，再：~~
   - `mic_owner_user_id=None`
   - `mic_owner_role=None`
   - `current_speaker=None`
   - `free_debate_next_side="human"`

否则会出现：

- 前端仍在播 AI 的语音。
- 房间状态却已经允许人类抢麦。

## 7. 前端配合方案

### 7.1 流式 PCM 播放链路回传
状态：已完成

涉及文件：

- `web/src/components/debate-arena.tsx`
- `web/src/lib/pcm-stream-player.ts`

当前 `PcmStreamPlayer` 已经能够知道：

- 某条流何时真正开始播放。
- 某条流何时尾音播放完成。

建议扩展为：

- ~~在流真正开始播放时，前端发送 `speech_playback_started`~~
- ~~在流真正播放完成时，前端发送 `speech_playback_finished`~~

消息体建议至少包含：

- `speech_id`
- `segment_id`
- `speaker_role`
- `playback_source`
  建议取值：`stream`

### 7.2 整段音频自动播放链路回传
状态：已完成

涉及文件：

- `web/src/components/debate-controls.tsx`
- `web/src/lib/debate-transcript.ts`

当前隐藏 `audio` 播放器已经有：

- `onPlay`
- `onEnded`
- `onError`

建议在这几个节点回传：

- ~~`onPlay` -> `speech_playback_started`~~
- ~~`onEnded` -> `speech_playback_finished`~~
- ~~`onError` -> `speech_playback_failed`~~

消息体建议至少包含：

- `speech_id`
- `segment_id`
- `speaker_role`
- `playback_source`
  建议取值：`audio_element`

### 7.3 前端需要显式保存 `speech_id`
状态：已完成

当前 `TranscriptEntry.id` 虽然通常能稳定映射为 `speech-{speech_id}`，但这是一个间接约定。

为了降低后续维护成本，建议：

- ~~在 `TranscriptEntry` 中显式增加 `speechId` 字段。~~

这样前端在回传播放确认时，不需要再从 `entry.id` 反推真实 `speech_id`。

## 8. 后端协议建议
状态：已完成

建议在 `api/routers/websocket.py` 中新增以下消息类型：

- ~~`speech_playback_started`~~
- ~~`speech_playback_finished`~~
- ~~`speech_playback_failed`~~
- ~~`playback_controller_appointed`~~
  用于广播当前哪个用户是播放确认基准

对应新增处理入口：

- ~~`handle_speech_playback_started_message(...)`~~
- ~~`handle_speech_playback_finished_message(...)`~~
- ~~`handle_speech_playback_failed_message(...)`~~

后端处理原则：

1. 只接受当前 `playback_gate_controller_user_id` 的回执。
2. 只处理与当前 `playback_gate_speech_id` 匹配的回执。
3. 若 segment 已切换，则丢弃旧回执。
4. 若同一条语音收到重复完成回执，只处理第一次。

## 9. 超时与兜底策略
状态：已完成

这是整套方案能否稳定落地的关键。

如果没有兜底，以下情况都会卡死：

- 浏览器自动播放被禁。
- 基准客户端关闭了自动播放。
- 用户切后台。
- 页面断网。
- 前端收到 `speech`，但根本没实际播放成功。

因此推荐双保险：

### 9.1 正常路径

- ~~以前端 `speech_playback_finished` 为准，立即推进。~~

### 9.2 兜底路径

- ~~后端在建立 `playback_gate` 时，同时生成 `deadline_at`。~~
- ~~如果 `deadline_at` 到了还没收到完成回执，则按超时推进。~~

`deadline_at` 建议计算方式：

- `音频时长`
- 加 `2~4 秒`缓冲
- 再加 `流式播放起播等待`缓冲

如果一开始拿不到准确音频时长，则退化为：

- `Speech.duration`
- 加 `2~4 秒`

### 9.3 特殊失败路径

若收到 `speech_playback_failed`：

- ~~后端应记录日志和状态。~~
- ~~可以直接按兜底推进。~~
- ~~不建议要求用户必须手动恢复，否则课堂场景会非常卡。~~

## 10. 为什么不建议直接复用现有 `turn_processing_status`

当前系统里：

- 人类音频上传时，`turn_processing_status="processing"` 表示 ASR 处理中。
- AI 发言时，`turn_processing_status="processing"` 表示 TTS 处理中。
- `end_turn`、`timeout`、`force_advance_segment(...)` 已经依赖这套语义。

如果再把“音频播放中”也塞进同一字段，会出现三个问题：

1. `end_turn` 的语义会被污染。
2. `timeout` 无法区分“还在转写”还是“已经转好但还在播”。
3. 人类发言链路和 AI 播放链路会互相干扰。

因此建议：

- 处理状态仍归 `turn_processing_status`
- 播放状态单独归 `playback_gate_status`

## 11. 与现有定时器和手动推进的关系

### 11.1 定时器超时
状态：已完成

当前 `handle_segment_timeout(...)` 只知道“处理是否完成”，不知道“播放是否完成”。

改造后建议：

- ~~若当前处于 `playback_gate_status="waiting"` 或 `playing`，不要直接切下一个 segment。~~
- ~~应先判断是否已到 `playback_gate_deadline_at`。~~
- ~~若未到，则继续等待播放结束。~~
- ~~若已到，则按播放超时推进。~~

### 11.2 主持人手动推进
状态：已完成

当前 `host_advance` 应保留最高优先级。

建议策略：

- ~~主持人手动推进时，可以直接打断当前播放栅栏并切段。~~
- ~~但要同时清理当前 `playback_gate`，避免旧回执污染新环节。~~

### 11.3 结束辩论
状态：已完成

结束辩论时应：

- ~~取消当前 AI 播放等待任务。~~
- ~~清空 `playback_gate`。~~
- ~~忽略后续迟到的播放完成回执。~~

## 12. 涉及文件建议

本方案预计主要影响以下文件：

- `api/services/flow_controller.py`
  核心改造点，取消“AI 发完即推进”，改为“等待播放栅栏释放”
- `api/services/room_manager.py`
  增加 `RoomState` 播放栅栏字段
- `api/routers/websocket.py`
  增加播放开始 / 结束 / 失败的消息处理
- `web/src/components/debate-arena.tsx`
  从流式 PCM 播放链路回传播放事件
- `web/src/lib/pcm-stream-player.ts`
  提供更细粒度的流播放开始 / 完成回调
- `web/src/components/debate-controls.tsx`
  从隐藏音频播放器回传播放事件
- `web/src/lib/debate-transcript.ts`
  显式保留 `speech_id`

## 13. 推荐实施顺序

### 第一阶段：快速止血
状态：已完成

- ~~在后端先按音频时长增加一个短期延迟推进。~~
- ~~目标是先解决“AI 语音刚出来就切段”的最明显问题。~~

### 第二阶段：正式方案落地
状态：已完成

1. ~~扩展 `RoomState` 播放栅栏字段。~~
2. ~~后端新增 `speech_playback_*` 协议。~~
3. ~~前端流式播放链路回传播放开始 / 结束。~~
4. ~~前端整段音频播放链路回传播放开始 / 结束。~~
5. ~~后端改为收到完成回执后再推进 segment。~~
6. ~~为所有播放确认增加超时兜底。~~

### 第三阶段：自由辩补齐
状态：已完成

- ~~将同样的播放栅栏逻辑应用到 AI 自由辩持麦链路。~~
- ~~保证“音频播完再释放麦克风”。~~

## 14. 验收标准

改造完成后，至少应满足以下结果：

1. AI 固定环节中，前一条 AI 音频未播完，绝不进入下一固定环节。
2. AI 到人类切换时，必须等当前 AI 音频播完或超时兜底后才开放人类发言。
3. 自由辩中，AI 持麦后必须等音频播完再释放麦克风。
4. 自动播放关闭、页面切后台、网络抖动时，不会把整场辩论卡死。
5. 主持人手动推进和结束辩论仍然可用。

## 15. 结论

这次问题的根因不是模型、不是真人操作，也不是音频生成慢，而是：

- 当前系统把“TTS 已准备好”误当成了“用户已经听完”。

对当前项目来说，最合适的方向不是继续调提示词，也不是只拉长 `response_delay_sec`，而是补上一层独立的：

- AI 播放完成栅栏

推荐最终路线是：

- 前端播放确认
- 后端等待确认
- 超时自动兜底

如果只想先快速止血，可以先做：

- 后端按音频时长延迟推进

但这只能作为过渡方案，最终还是应该落到“播放完成再推进”的协议化设计上。
