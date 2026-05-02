# 全局逻辑问题完善方案

## 1. 文档目标

本文档用于统一记录当前全局逻辑问题的修复状态、剩余风险、完善步骤和回归验收标准。覆盖范围包括：

- 权限与敏感配置安全
- WebSocket 协议与状态机一致性
- 文本/语音/ASR/TTS/AI 发言链路
- 自由辩论抢麦与播放闸门
- 报告、评分、AI 上下文的数据质量
- 前后端流程定义一致性
- 测试、联调和上线前验收

核心原则：

1. 已修复项必须能用测试或明确自检证明。
2. 异步任务结果不得污染新的阶段状态。
3. 用户可见状态必须和后端状态一致。
4. 敏感字段只允许写入，不允许读出明文。
5. 失败态必须有可重试、可跳过或可强制推进的明确路径。

## 2. 当前验证结果

最近一次本地验证：

```powershell
api\venv\Scripts\python.exe -m pytest api\tests\test_websocket.py -q
```

结果：

- 47 passed
- 存在若干 `datetime.utcnow()` 和 pytest cache 权限类 warning，不是业务断言失败。

补充后端回归：

```powershell
api\venv\Scripts\python.exe -m pytest api\tests\test_admin_router.py api\tests\test_security.py api\tests\test_scoring.py -q
```

结果：

- 28 passed
- 存在 Pydantic/FastAPI/datetime/pytest cache warning，不是业务断言失败。

```powershell
cmd /c npm run type-check
```

结果：

- 通过。

前端组件测试：

```powershell
cmd /c npx vitest run src/components/debate-arena.test.tsx
```

结果：

- 当前机器被 `esbuild spawn EPERM` 阻断，未进入业务断言阶段。
- 新增前端测试已通过 `cmd /c npm run type-check` 类型校验。

生产日志扫描：

```powershell
rg -n "console\.log" web/src
```

结果：

- 真实运行代码无裸 `console.log`。
- 当前仅剩 `web/src/hooks/use-websocket.ts` 注释示例命中。

注意：

- `GLOBAL_LOGIC_ISSUES_SOLUTION.md` 当前是新文档，需要纳入 Git 跟踪后才能出现在 diff 中。
- 工作区还有较多非本文档相关修改，提交前应按主题拆分。

### 2.1 本轮修改执行记录

- ~~自动评分/报告过滤无效 speech~~ ✅ 已完成。
  - 代码逻辑：`api/services/room_manager.py` 的 `_auto_score_and_generate_report(...)` 查询 speeches 时新增 `Speech.is_valid_for_scoring.is_(True)`，并保留空内容过滤作为双保险。ASR 失败但仍有 content 的历史 speech 可以继续用于回放排查，但不会进入 `ScoringService.batch_score_debate(...)` 的 speeches/context。
  - 自检：`api\venv\Scripts\python.exe -m pytest api\tests\test_websocket.py -q -k "auto_score_filters_invalid_speeches"` 通过，1 passed。
- ~~文本空发言后端回归测试~~ ✅ 已完成。
  - 代码逻辑：现有 `api/routers/websocket.py` 会在 `handle_speech_message(...)` 中 `strip()` 文本内容，空字符串或纯空白直接向用户返回 `error: 发言内容不能为空`，不调用 `db.add/db.commit`，不广播 `speech`，不设置 `turn_speech_committed=True`。
  - 自检：`api\venv\Scripts\python.exe -m pytest api\tests\test_websocket.py -q -k "empty_text_speech or blank_text_speech"` 通过，2 passed。
- ~~TTS/LLM 旧异步结果防污染~~ ✅ 已完成。
  - 代码逻辑：`api/services/flow_controller.py` 新增 `_is_ai_turn_still_current(...)`，校验当前房间仍处于原 `segment_id/current_phase/current_speaker/ai_turn_speaker_role`。`release_ai_speech(...)` 在 TTS 长耗时后的 audio 回填、播放闸门创建、completed speech 广播、`tts_stream_end`、draft released 标记和 `notify_speech_committed(...)` 前重新校验；过期结果最多保留历史 speech/audio，不再修改当前阶段 turn 状态、释放麦克风或推进流程。播放回执处理同时补充 `segment_id + speaker_role` 匹配，旧回执不能释放新闸门。
  - 自检：`api\venv\Scripts\python.exe -m pytest api\tests\test_websocket.py -q -k "stale_ai_tts_result or playback_finished_with_stale_segment"` 通过，2 passed。
- ~~生产 console.log 扫尾~~ ✅ 已完成。
  - 代码逻辑：`web/src/components/teacher-dashboard.tsx` 中真实运行路径的 `console.log` 改为 `debateDebug(...)`，且只输出 `debateId/status/studentCount` 等摘要字段，避免生产输出完整对象或潜在敏感内容。
  - 自检：`rg -n "console\.log" web/src` 仅剩 `web/src/hooks/use-websocket.ts` 注释示例；`cmd /c npm run type-check` 通过。

## 3. 状态总览

| 模块 | 当前状态 | 说明 |
| --- | --- | --- |
| 邮件配置后端鉴权与脱敏 | 已完成 | 后端不再返回 `smtp_password` 明文 |
| ~~邮件配置前端适配脱敏字段~~ | ✅ 已完成 | 前端不再读取明文密码，空密码表示保留旧值 |
| 生产默认配置 fail-fast | 已完成 | 已移除公网/硬编码敏感默认值 |
| 人类语音录制入口 | 已完成 | 支持性检查、错误提示、音频先于 `end_turn` 发送已修复 |
| 文本/语音发言持久化失败处理 | 已完成 | commit 失败不广播、不标记成功、不推进 |
| `end_turn` processing gate | 已完成 | 普通 `end_turn` 不再绕过 ASR/处理状态 |
| ~~文本空发言后端校验~~ | ✅ 已完成 | 空文本/空白文本不落库、不广播、不标记发言成功 |
| ~~WebSocket speech payload 统一~~ | ✅ 已完成 | 文本、语音、AI 发言走统一 helper，并补字段测试 |
| AI 缓存草稿响应延迟 | 已完成 | 以 `segment_start_time + response_delay_sec` 为准 |
| ~~自动播放关闭播放闸门~~ | ✅ 已完成 | 新增 `speech_playback_skipped`，并修复非 controller 释放漏洞 |
| ~~生产 `console.log` 清理~~ | ✅ 已完成 | 真实运行代码已清理，剩余命中仅为注释示例 |
| ~~ASR 失败 speech 无效标记与评分过滤~~ | ✅ 已完成 | 新增字段与迁移，AI 上下文、报告、评分、自动结辩评分均过滤 |
| ~~自然结束正式结辩流程~~ | ✅ 已完成 | 代码走 `finish_debate_flow`，并补充回归测试 |
| ~~ASR 异步结果防污染~~ | ✅ 已完成 | 旧 ASR 成功/失败不会污染新阶段，并补测试 |
| ~~TTS/LLM 异步结果防污染~~ | ✅ 已完成 | 旧 AI/TTS 结果最多更新历史 speech，不再污染当前阶段 |
| ~~自由辩论持麦超时交给 AI~~ | ✅ 已完成 | 人类持麦超时立即切到 AI side，并补测试 |
| ~~choice 模式选择发言人入口~~ | ✅ 已完成 | 前后端入口已实现，并补回归测试 |
| ~~前端流程列表后端下发~~ | ✅ 已完成 | 已支持 `flow_segments` 优先渲染，并补测试 |
| 乱码文案清理 | 待分批处理 | 不应混入状态机修复 PR |
| 长记忆增强 | 设计中 | 应异步、可降级，不阻塞实时 AI |

## 4. P0 安全与配置

### 4.1 邮件配置接口鉴权与脱敏

后端已完成：

- `GET /api/admin/config/email` 恢复管理员鉴权。
- 未登录返回 401，非管理员返回 403。
- 响应不再包含 `smtp_password` 明文。
- 响应改为：
  - `smtp_password_configured: boolean`
  - `smtp_password_masked: string | null`
- 删除调试 `print`。

仍需修复前端：

- `web/src/services/admin.service.ts` 中 `EmailConfig` 仍定义 `smtp_password: string`。
- `web/src/components/admin/email-configuration.tsx` 仍从 `data.smtp_password` 初始化表单。
- 保存校验仍要求 `smtp_password` 必填。

完善方案：

1. 更新前端类型：

```ts
export interface EmailConfig {
  id: string;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password_configured: boolean;
  smtp_password_masked?: string | null;
  from_email: string;
  auto_send_enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

2. 表单初始化时密码字段置空：

```ts
smtp_password: ''
```

3. 编辑页展示：

- 已配置：显示 `smtp_password_masked` 或“已配置”。
- 未配置：显示“未配置”。
- 密码输入框 placeholder 为“留空表示保留旧密码”。

4. 保存逻辑：

- 如果已有密码且输入框为空，不发送 `smtp_password` 字段。
- 如果未配置密码，则保存时要求输入新密码。
- 用户显式输入新密码时才提交 `smtp_password`。

验收标准：

- 管理员打开邮件配置页不会看到明文密码。
- 已配置密码时，直接修改 host/user/from_email 并保存不会清空旧密码。
- 未配置密码时，保存会要求填写密码。
- `cmd /c npm run type-check` 通过。

执行记录：

- ✅ 已完成前端脱敏适配。
- 代码逻辑：`web/src/services/admin.service.ts` 中 `EmailConfig` 改为接收 `smtp_password_configured` 和 `smtp_password_masked`；`web/src/components/admin/email-configuration.tsx` 初始化表单时不再读取 `smtp_password`，密码框始终置空。保存时如果旧密码已配置且输入为空，则提交 payload 中省略 `smtp_password`，后端保留旧密码；如果旧密码未配置，则要求输入新密码。
- 自检：`cmd /c npm run type-check` 通过。

### 4.2 生产环境默认配置风险

已完成：

- `DATABASE_URL` 不再使用公网默认值。
- `REDIS_HOST` 默认改为 `localhost`。
- `REDIS_PASSWORD` 不再硬编码。
- 新增 `ENVIRONMENT`、`IS_PRODUCTION`、`ALLOWED_ORIGINS`。
- 生产环境下默认 `SECRET_KEY`、空 `DATABASE_URL`、`DEBUG=true` 会 fail-fast。

建议补充：

- 在部署文档中明确生产必填环境变量。
- CI 增加一个最小生产配置检查脚本。

## 5. P0 状态一致性

### 5.1 发言持久化失败后仍广播并标记成功

已完成：

- 文本发言 `db.commit()` 失败后立即 `rollback`、发送错误并返回。
- 不广播 `speech`。
- 不设置 `turn_speech_committed=True`。
- 语音初始 `Speech` 创建失败时停止 ASR。
- ASR 成功但回填落库失败时标记 failed，不广播 completed speech，不推进。

验收标准：

- mock 文本 `db.commit()` 抛异常，不广播 speech。
- mock 语音初始 speech 创建失败，不启动 ASR。
- mock ASR 回填失败，不推进流程。

当前测试：

- `api\tests\test_websocket.py` 已覆盖主要路径。

### 5.2 普通 `end_turn` 绕过 processing gate

已完成：

- `force_advance_segment(...)` 仅允许 `host_advance` 和 `timeout` 绕过 processing/failed gate。
- 普通 `end_turn` 在 `processing` 时只设置 `pending_advance_reason="end_turn"`，并广播 `advance_deferred`。
- 普通 `end_turn` 在 `failed` 时广播 `advance_blocked` 并返回 `False`。
- ASR 成功后消费 pending 并推进。

仍需注意：

- 产品语义需保持清晰：普通用户“结束发言”不是强制跳过处理；主持人“强制下一阶段”才是。

## 6. P1 异步任务与阶段状态

### 6.1 ASR 异步完成后污染下一阶段

当前代码已实现快照校验：

- ASR 开始时记录：
  - `segment_id`
  - `current_phase`
  - `current_speaker`
  - `user_role`
  - `turn_speech_user_id`
  - `turn_speech_role`
- ASR 回写前通过 `asr_turn_still_current()` 校验。
- 快照不匹配时只更新/广播 speech 结果，不更新当前房间 turn 状态。

缺口：

- 缺少专门测试覆盖“ASR 中途主持人强制推进，旧 ASR 成功/失败不污染新阶段”。

完善测试：

```python
def test_stale_asr_success_does_not_mark_new_segment_committed():
    ...

def test_stale_asr_failure_does_not_mark_new_segment_failed:
    ...

def test_current_asr_success_consumes_pending_end_turn():
    ...
```

验收标准：

- 旧 ASR 成功不会设置新阶段 `turn_speech_committed=True`。
- 旧 ASR 失败不会设置新阶段 `turn_processing_status="failed"`。
- 原阶段 ASR 成功仍能消费 pending `end_turn`。

执行记录：

- ✅ 已完成 ASR 过期结果回归测试补强。
- 代码逻辑：`api/routers/websocket.py` 在 ASR 开始时保存阶段快照，并通过 `asr_turn_still_current()` 校验 `segment_id/current_phase/current_speaker/turn_processing_kind/turn_speech_user_id/turn_speech_role`。ASR 成功或失败时，如果快照已过期，只广播对应 speech 的 completed/failed 回填，不更新当前房间的 turn 状态，也不消费 pending advance。
- 自检：`api\venv\Scripts\python.exe -m pytest api\tests\test_websocket.py -q -k "stale_asr or flow_completion or finish_debate_flow"` 通过。

### 6.2 自然结束流程走正式结辩

当前代码已实现：

- `flow_controller._apply_current_segment()` 在 `index >= len(segments)` 时调用 `finish_debate_flow(...)`。
- `finish_debate_flow(...)` 调用 `room_manager.end_debate(...)`。
- `room_manager.end_debate(...)` 更新 DB debate 状态、广播 processing/ended，并清理流程状态。

补强结果：

- 已补充 `advance_segment()` 触发正式结辩入口和已结束房间幂等返回测试。

完善测试：

```python
def test_flow_completion_calls_room_manager_end_debate():
    ...

def test_end_debate_is_idempotent():
    ...

def test_report_generation_failure_still_broadcasts_debate_ended():
    ...
```

验收标准：

- 最后一段自然结束后 DB debate 为 `completed`。
- 广播 `debate_processing` 和 `debate_ended`。
- 重复结束不重复生成报告/评分。
- 报告或评分失败时，辩论仍进入 finished，并有错误日志。

执行记录：

- ✅ 已完成自然结束正式结辩回归测试补强。
- 代码逻辑：`api/services/flow_controller.py` 在 `advance_segment()` 推进到 segments 尾部之后，由 `_apply_current_segment()` 调用 `finish_debate_flow(room_id, reason="segments_completed")`；`finish_debate_flow(...)` 创建 DB session 并调用 `room_manager.end_debate(...)`，而不是只修改内存阶段。若房间已经是 `FINISHED`，直接返回成功，避免重复结辩。
- 自检：同上子集测试通过，覆盖 `advance_segment()` 触发 `end_debate` 和已结束房间幂等返回。

## 7. P1 WebSocket 协议统一

### 7.1 speech payload 统一

已完成：

- 新增 `api/utils/speech_payload.py`。
- 文本、语音 processing/completed/failed、AI speech 使用统一结构。
- 关键字段：
  - `speech_id`
  - `message_id`
  - `user_id`
  - `role`
  - `name`
  - `stance`
  - `speaker_type`
  - `content`
  - `audio_url`
  - `audio_format`
  - `duration`
  - `timestamp`
  - `is_audio`
  - `transcription_status`
  - `phase`
  - `segment_id`
  - `segment_title`

建议补充：

- 为 `build_speech_payload(...)` 增加单元测试，锁定字段完整性。
- 前端 transcript 合并逻辑优先使用 `speech_id`。

执行记录：

- ✅ 已完成 speech payload 字段完整性测试。
- 代码逻辑：`api/utils/speech_payload.py` 统一生成 `speech_id/message_id/user_id/role/name/stance/speaker_type/content/audio_url/audio_format/duration/timestamp/is_audio/transcription_status/phase/segment_id/segment_title`，避免文本、语音和 AI 发言字段漂移。
- 自检：`api\venv\Scripts\python.exe -m pytest api\tests\test_websocket.py -q -k "choice_ or playback_skipped or speech_payload or segment_flow"` 通过。

### 7.2 后端新增消息类型前端兼容

已完成/已适配：

- `audio_processed`
- `advance_deferred`
- `advance_blocked`
- `advance_forced`
- `speech_playback_skipped`
- `speaker_selected`

建议补充：

- 前端 `websocket-client.ts` 增加类型测试或编译保护。
- 对未知消息类型保持容错日志，不阻塞主流程。

## 8. P1 AI 发言、TTS 与播放闸门

### 8.1 缓存 AI 草稿响应延迟

已完成：

- 释放时间以 `segment_start_time + response_delay_sec` 为准。
- 缓存草稿提前生成时仍等待目标释放时间。
- 已更新相关测试。

验收标准：

- draft 提前生成不提前广播。
- 超过目标时间时立即释放。

### 8.2 自动播放关闭时播放闸门延迟

已完成：

- 新增 `speech_playback_skipped`。
- 前端自动播放关闭且收到 `tts_stream_start` 时发送 skipped。
- 后端只接受 playback controller 的 completed/skipped/failed。
- skipped 释放播放 gate。

建议补充测试：

```python
def test_playback_skipped_from_controller_releases_gate():
    ...

def test_playback_skipped_from_non_controller_is_ignored:
    ...

def test_no_controller_still_uses_deadline():
    ...
```

执行记录：

- ✅ 已完成 playback skipped controller 权限补强。
- 代码逻辑：`api/services/flow_controller.py` 的 `_refresh_playback_controller_if_needed(...)` 在找不到新的在线 controller 时不再清空 `playback_gate_controller_user_id`，而是保留原 controller 并等待 deadline；非 controller 客户端发送 `speech_playback_skipped` 不会释放全局播放闸门。
- 自检：后端子集测试通过；前端 `cmd /c npm run type-check` 通过。`cmd /c npx vitest run src/components/debate-arena.test.tsx` 当前仍被本机 `esbuild spawn EPERM` 阻断。

### 8.3 TTS/LLM 异步结果防污染

原风险：

- ASR 已加快照校验，但 TTS、LLM、播放回执等异步结果也应持续使用 `segment_id + speaker_role + speech_id` 校验。

完善方案：

1. 所有异步完成回调携带：
   - `segment_id`
   - `speaker_role`
   - `speech_id`
   - `task_token` 可选
2. 回写房间状态前校验当前状态仍匹配。
3. 过期结果只能更新历史 speech，不得推进当前流程。

验收标准：

- AI 发言生成期间被强制推进，旧 AI 完成后不会释放新阶段麦克风。
- 旧 TTS 播放完成不会推进新阶段。

执行记录：

- ✅ 已完成 TTS/LLM 旧异步结果防污染补强。
- 代码逻辑：`api/services/flow_controller.py` 新增 `_is_ai_turn_still_current(...)`，在 `release_ai_speech(...)` 进入 TTS、流式 chunk、音频保存后状态回写、completed speech 广播、`tts_stream_end`、draft released 标记和 `notify_speech_committed(...)` 前重复校验当前阶段与当前 AI 发言人仍匹配。`run_ai_turn(...)` 和自由辩论 AI 接话在释放麦克风或推进前也会重新确认旧任务仍是当前任务。播放 completed/skipped/failed 回执补充校验 `segment_id` 和 `speaker_role`，避免旧回执释放新阶段闸门。
- 自检：`api\venv\Scripts\python.exe -m pytest api\tests\test_websocket.py -q -k "stale_ai_tts_result or playback_finished_with_stale_segment"` 通过，2 passed。

## 9. P1 自由辩论节奏

### 9.1 人类持麦超时后自动交给 AI

当前问题：

- 人类持麦过期时会触发 `schedule_free_debate_ai_turn(room_id)`。
- 但过期瞬间 `free_debate_next_side` 被设置为 `"human"`，然后延迟任务再改为 `"ai"`。
- 这会产生短暂 human 窗口，前端可能允许再次抢麦，导致节奏不确定。

修复方案：

1. 人类持麦过期时立即设置：

```python
free_debate_last_side = "human"
free_debate_next_side = "ai"
```

2. 广播：

```json
{
  "type": "mic_released",
  "data": {
    "reason": "expired",
    "next_side": "ai"
  }
}
```

3. 调用 `schedule_free_debate_ai_turn(room_id)` 前检查：

- 当前仍是 free_debate。
- 没有持麦人。
- 没有活跃 AI task。
- `free_debate_next_side == "ai"`。

4. AI 持麦过期时设置：

```python
free_debate_last_side = "ai"
free_debate_next_side = "human"
```

测试：

```python
def test_human_mic_expire_sets_next_side_ai_immediately():
    ...

def test_human_mic_expire_schedules_one_ai_turn():
    ...

def test_ai_mic_expire_returns_next_side_human:
    ...

def test_repeated_timer_tick_does_not_schedule_duplicate_ai_tasks:
    ...
```

验收标准：

- 人类超时后 UI 立即显示 AI 回合。
- 超时后不能在 AI 接话前再次抢麦。
- 重复 timer tick 不会启动多个 AI task。

执行记录：

- ✅ 已完成自由辩论持麦超时状态修复。
- 代码逻辑：`api/services/flow_controller.py` 新增 `_release_expired_free_debate_mic(...)`，统一处理过期麦克风释放。人类 `debater_*` 持麦超时后立即设置 `free_debate_last_side="human"`、`free_debate_next_side="ai"`，广播 `mic_released` 时附带 `next_side="ai"`，并调度 AI 接话；AI `ai_*` 持麦超时后设置 `free_debate_last_side="ai"`、`free_debate_next_side="human"`，并清理对应 AI turn 状态。
- 自检：`api\venv\Scripts\python.exe -m pytest api\tests\test_websocket.py -q -k "mic_expire or free_debate_ai_speaker"` 通过，3 passed。

## 10. P1 choice 模式发言人选择

当前状态：

- 后端支持 `select_speaker`。
- 前端已有 `canSelectCurrentUserSpeaker` 与发送 `select_speaker` 的逻辑。

仍需完善：

- 补前端测试。
- 补后端“已发言后不能切换”的测试。
- 确认后端 `handle_select_speaker_message()` 已阻止非候选人选择。

测试：

```ts
it('shows select speaker button for candidate user', ...)
it('does not show select speaker button for non-candidate user', ...)
it('sends select_speaker when clicked', ...)
it('updates current speaker after speaker_selected', ...)
```

```python
def test_candidate_can_select_speaker():
    ...

def test_non_candidate_cannot_select_speaker():
    ...

def test_cannot_switch_speaker_after_committed_speech():
    ...
```

执行记录：

- ✅ 已完成 choice 模式前后端回归测试补强。
- 代码逻辑：后端 `set_current_speaker(...)` 只允许 `speaker_options` 中的候选角色被选择，且本段已提交发言后拒绝切换；前端 `DebateArena` 在 `speaker_mode="choice"` 且当前用户角色属于候选列表时展示“选择我来回答”，点击发送 `select_speaker`。
- 自检：后端 choice 子集测试通过；前端 type-check 通过，Vitest 受 EPERM 阻断。

## 11. P1 前后端流程定义一致性

当前状态：

- `RoomState.to_dict()` 已包含 `flow_segments`。
- `flow_controller.start_flow(...)` 会写入序列化 segments。
- 前端 `DebateArena` 已优先使用 `backendFlowSegments`，未收到时 fallback 到本地 `flowSegments`。

仍需完善：

- 补测试覆盖自定义 segments。
- 确认 `debate_started`、`state_update`、`segment_change` 都能让前端拿到一致的 segments。
- 本地 fallback 应只作为兼容旧状态，不应作为主逻辑来源。

验收标准：

- 后端下发自定义 segments 时，前端进度条、最后一段判断、结束按钮都跟随后端。
- 后端未下发时 fallback 仍可工作。
- 修改后端默认流程后，不需要同步改前端硬编码列表。

执行记录：

- ✅ 已完成 `flow_segments` 下发与前端优先渲染测试补强。
- 代码逻辑：`RoomState.to_dict()` 输出 `flow_segments`，`flow_controller.start_flow(...)` 将当前 segments 序列化写入房间状态；前端 `DebateArena` 收到 `state_update.flow_segments` 后使用 `backendFlowSegments` 作为主进度列表，本地 `flowSegments` 仅作为 fallback。
- 自检：后端 `test_flow_controller_segment_flow` 已断言 `room_state.flow_segments`；前端新增渲染自定义 segments 的测试，type-check 通过。

## 12. P2 数据质量

### 12.1 ASR 失败 speech 无效标记

已完成：

- `Speech` 新增：
  - `transcription_status`
  - `transcription_error`
  - `is_valid_for_scoring`
- 新增迁移：
  - `api/alembic/versions/013_add_speech_transcription_status.py`
- 历史空 content 且有 audio_url 的记录回填为：
  - `transcription_status="failed"`
  - `is_valid_for_scoring=false`
- ASR processing：
  - `is_valid_for_scoring=false`
- ASR completed：
  - `is_valid_for_scoring=true`
- ASR failed/empty：
  - `is_valid_for_scoring=false`
- AI 上下文、报告生成、评分查询、自动结辩评分入口过滤 `is_valid_for_scoring=True`。

执行记录：

- ✅ 已完成自动结辩评分入口过滤补漏。
- 代码逻辑：`api/services/room_manager.py` 的 `_auto_score_and_generate_report(...)` 查询 speeches 时加入 `Speech.is_valid_for_scoring.is_(True)`，再过滤空内容，确保 ASR failed/empty 的 speech 不进入评分和报告上下文。
- 自检：`api\venv\Scripts\python.exe -m pytest api\tests\test_websocket.py -q -k "auto_score_filters_invalid_speeches"` 通过，1 passed。

建议补充：

- 报告页/回放页展示“语音识别失败”，而不是静默隐藏所有失败语音。
- 对历史数据迁移做一次 staging 演练。

### 12.2 迁移链检查

当前迁移链：

- `012_add_email_config_table.py`
- `013_add_speech_transcription_status.py`

建议：

- 执行一次 `alembic history` 和 `alembic upgrade head` 验证链路。
- 确认所有部署环境都能从当前版本升级到 `013`。

## 13. P2 前端体验与维护性

### 13.1 生产 console.log 清理

已完成：

- `web/src/lib/utils.ts` 新增 `debateDebug(...)`。
- 点名文件中的 `console.log` 已改为开发环境 debug。

扫尾结果：

```powershell
rg -n "console\.log" web/src
```

- ✅ 已完成真实运行代码扫尾；当前命中仅剩 `web/src/hooks/use-websocket.ts` 中的注释示例。
- 代码逻辑：`web/src/components/teacher-dashboard.tsx` 的编辑辩论调试输出改为 `debateDebug(...)`，只输出摘要字段，不输出完整 debate 对象。
- 自检：`cmd /c npm run type-check` 通过。

处理原则：

- 生产必要日志用统一 logger。
- 调试日志用 `import.meta.env.DEV` 包裹。
- 不输出用户发言全文、token、敏感配置。

### 13.2 乱码文案清理

当前问题：

- 仓库中存在中文文案乱码风险。
- 这类修改 diff 大，容易和业务逻辑混在一起。

处理原则：

1. 单独开文案编码修复 PR。
2. 只改用户可见文案和注释，不改业务逻辑。
3. 优先修复：
   - 辩论页按钮/toast
   - 权限错误提示
   - 管理端配置页
   - 报告生成提示

验收标准：

- 源文件统一 UTF-8。
- UI 关键路径无乱码。
- type-check 和相关测试通过。

## 14. P2 长记忆增强方案

当前状态：

- 系统已有数据库历史发言和最近上下文读取。
- 尚不是完整长记忆系统。

设计原则：

- 长记忆不能阻塞实时 AI 发言。
- 摘要、画像、向量索引应异步计算。
- 检索失败或超时时降级到最近发言。

推荐上下文结构：

```text
系统角色与辩论规则
当前阶段与当前任务
最近 6-20 条原始发言
相关阶段摘要 1-3 条
相关关键记忆 3-5 条
短用户画像 1 条
当前 AI 具体生成要求
```

落地步骤：

1. 新增 `MemoryService`。
2. 新增 `debate_memory_summaries` 表。
3. 发言 commit 成功后后台更新阶段摘要、关键词、索引。
4. AI 生成入口读取：
   - `recent_speeches`
   - `phase_summary`
   - `retrieved_memories`
   - `student_profile_hint`
5. 检索超时保护，例如 200ms。
6. prompt token 设硬上限，优先裁剪低相关记忆。

验收标准：

- 长记忆服务正常时 prompt 包含摘要/相关记忆。
- 长记忆超时或异常时 AI 仍能生成。
- prompt 长度不随整场发言无限增长。
- 后台摘要失败不影响 WebSocket 流程推进。

## 15. 建议实施顺序

### 阶段一：立即修复

1. 邮件配置前端适配脱敏字段。
2. 自由辩论人类持麦超时立即切到 AI。
3. 补 ASR 过期结果不污染新阶段测试。
4. 补自然结束正式结辩测试。

### 阶段二：一致性补强

1. 补 choice 模式前后端测试。
2. 补后端 `flow_segments` 下发与前端使用测试。
3. 补播放 skipped controller 权限测试。
4. 为 `build_speech_payload(...)` 加字段完整性测试。

### 阶段三：数据与体验收尾

1. staging 验证 Alembic 013 迁移。
2. 回放页/报告页展示 ASR failed 状态。
3. 全局清理生产 `console.log`。
4. 单独处理乱码文案。

### 阶段四：长记忆

1. 先做阶段摘要表和服务接口。
2. 再接入 AI prompt 组装。
3. 最后做向量检索和用户画像注入。

## 16. 回归测试清单

### 后端

```powershell
api\venv\Scripts\python.exe -m pytest api\tests\test_websocket.py -q
api\venv\Scripts\python.exe -m pytest api\tests\test_admin_router.py -q
api\venv\Scripts\python.exe -m pytest api\tests\test_security.py -q
api\venv\Scripts\python.exe -m pytest api\tests\test_report_pdf_export.py -q
api\venv\Scripts\python.exe -m pytest api\tests\test_scoring.py -q
```

重点新增/确认：

- 未登录无法读取邮件配置。
- 邮件配置不返回明文密码。
- 不传密码不会清空旧密码。
- 文本 speech commit 失败不广播、不推进。
- 音频 speech commit 失败不启动 ASR、不推进。
- `end_turn` 在 ASR processing 时只设置 pending。
- ASR 成功后消费 pending。
- ASR 失败后普通 `end_turn` 被阻断。
- 旧 ASR 成功/失败不污染新阶段。
- 最后一段自然结束调用正式 end debate。
- 自动评分失败仍广播 `debate_ended`。
- 人类持麦过期后立即进入 AI side。
- AI 持麦过期后回到 human side。
- controller skipped 释放 playback gate，非 controller 无效。

### 前端

```powershell
cmd /c npm run type-check
cmd /c npx vitest run src/components/debate-arena.test.tsx src/components/debate-controls.test.tsx
```

重点新增/确认：

- 邮件配置页显示脱敏密码状态。
- 已配置密码时保存不强制输入密码。
- 未配置密码时要求输入密码。
- 停止录音后先发送 `audio`，再发送 `end_turn`。
- 录音权限拒绝显示明确错误。
- `audio_processed` 能回填同一条 transcript。
- ASR failed 同一 `speech_id` 合并为失败状态。
- choice 候选发言人可看到选择按钮。
- 点击选择按钮发送 `select_speaker`。
- 后端下发自定义 `flow_segments` 时进度条跟随更新。
- 自动播放关闭时发送 `speech_playback_skipped`。

### 手工联调

1. 管理员打开邮件配置，确认看不到明文旧密码。
2. 已配置密码时修改 SMTP host 后保存，确认旧密码未被清空。
3. 非管理员访问 `/api/admin/config/email` 返回 403。
4. 学生录音，确认音频先提交，`end_turn` 不抢跑。
5. ASR 失败时页面显示识别失败，流程不误推进。
6. ASR 处理中主持人强制下一阶段，旧 ASR 完成后不污染新阶段。
7. 自由辩论人类抢麦后沉默至超时，确认 AI 自动接话。
8. AI 自由辩论播放完成或 skipped 后，麦克风释放给 human。
9. choice 阶段候选辩手能选择自己回答。
10. 完整辩论自然结束后，DB debate 为 `completed`，报告生成。

## 17. 上线前检查

上线前必须确认：

- 后端核心测试通过。
- 前端 type-check 通过。
- Alembic 可升级到 head。
- 生产环境配置不使用默认 `SECRET_KEY`。
- CORS 生产环境不使用不受控 `*`。
- 管理端敏感配置接口不返回明文 secret/password/token。
- WebSocket 新消息类型前端不报类型错误。
- 报告和评分不读取 `is_valid_for_scoring=False` 的 speech。
- 旧异步任务不会修改新阶段状态。

## 18. 风险提示

1. 不要把乱码文案大修和状态机修复放在同一个提交里。
2. 不要把所有全局逻辑问题一次性混成一个大 PR。
3. 状态机相关修复必须配套测试，否则后续很难判断行为是否回退。
4. 对 ASR/TTS/LLM 这类异步链路，必须优先考虑“结果回来时房间是否还是原来的阶段”。
5. 工作区当前有多处非本文档修改，提交前应按安全、状态机、前端体验、数据迁移分组。
