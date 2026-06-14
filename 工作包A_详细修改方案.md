# 工作包A：详细修改方案

## 1. A 要解决什么

A 负责 AI 内核。重点不是增加更多 prompt，而是把平台里散落的 prompt、评分、报告和降级逻辑收成一个稳定内核。

A 的最终交付：
- Prompt Pack V1。
- 比赛/教学双模式策略。
- Judge JSON 修复与 fallback 链路。
- 分辩位三层评分 rubric。
- DebateReport V2。
- ReportMeta 与评分质量标记。
- 评分校准和异常样本回流。

## 2. A 不做什么

A 不做教师页面、学生页面、安全登录、教学设计上传、资料文件处理、教师/学生路由。

如果 A 需要教学设计、候选辩题、学生画像、资料摘要，只消费 B/E 冻结后的结构，不直接读业务表或前端参数。

## 3. 修改阶段

### A0：建立 AI 内核数据合同

涉及文件：
- `api/services/prompt_pack_service.py`
- `api/services/mode_policy_service.py`
- `api/services/domain_pack_service.py`
- `api/services/rubric_service.py`
- `api/services/report_service.py`

怎么改：
- 新增 `PromptBuildContext` 数据结构。
- 新增 `ReportMeta` 数据结构。
- 新增 `ScoringPolicy` 数据结构。
- 新增 `DebateReportSchema` 数据结构。
- 新增 `ScoreEvidenceSchema` 数据结构。
- 先写纯函数和 schema，不接真实 agent。

产出：
- A 给 B/D/E 一份固定报告和评分字段。
- D 可以基于 mock 报告先做页面。

验收：
- 所有合同字段有默认值、枚举值、示例数据。
- `report_meta.scoring_quality` 可以表达 `validated / repaired / fallback / partial`。

### A1：重构 Prompt Pack

涉及文件：
- `api/services/prompt_pack_service.py`
- `api/services/mode_policy_service.py`
- `api/services/domain_pack_service.py`
- `api/agents/debater_agent.py`
- `api/agents/judge_agent.py`
- `api/agents/mentor_agent.py`
- `api/services/flow_controller.py`

怎么改：
- 平台统一构建 prompt，不再在 agent 文件里散写大段 prompt。
- Prompt Pack 固定 7 层：
  - `global_rules`
  - `mode_policy`
  - `task_contract`
  - `phase_objective`
  - `context_block`
  - `output_contract`
  - `domain_pack`
- Coze 只保留人设、语气和少量身份设定。
- 平台负责任务要求、阶段目标、输出格式、评分维度、资料注入和模式切换。

架构建议：
- `build_prompt(context: PromptBuildContext) -> PromptPack`
- agent 只调用 `prompt_pack_service`，不再拼接业务 prompt。

验收：
- 同一 agent 在 `competition / teaching` 下输出 prompt 不同。
- 同一阶段 prompt 注入字段稳定。
- 不再出现 agent 内部自行解释 mode 的逻辑。

### A2：比赛/教学双模式策略

涉及文件：
- `api/services/mode_policy_service.py`
- `api/services/prompt_pack_service.py`
- `api/agents/judge_agent.py`
- `api/agents/mentor_agent.py`

怎么改：
- `competition` 模式：
  - Judge 重点看论证强度、回应有效性、回合控制、关键失误。
  - Mentor 输出 80-120 字战术建议。
  - Report 强调关键转折和决胜原因。
- `teaching` 模式：
  - Judge 可强调知识迁移、课程目标、反思。
  - Mentor 输出 120-180 字改进建议。
  - Report 强调学习目标、共性问题和改进动作。

验收：
- mode 切换不需要改 agent 代码。
- 默认仍为 `competition`。
- 金融稳定币不进入默认 AI 通识比赛口径，只作为后续 domain pack。

### A3：Judge JSON 修复与 fallback 链路

涉及文件：
- `api/agents/judge_agent.py`
- `api/services/scoring_service.py`
- `api/services/score_validation_service.py`
- `api/services/report_service.py`

怎么改：
- Judge 首次输出后先做 JSON schema 校验。
- 非法 JSON 时走一次修复重试。
- 修复仍失败才 fallback。
- fallback 必须写入：
  - `scoring_source: fallback`
  - `scoring_quality: fallback | partial`
  - `retry_count`
  - `provider`
  - `prompt_pack_version`
  - `rubric_version`

验收：
- 非法 JSON 不会导致报告生成失败。
- fallback 报告不会被伪装成正常评分。
- D 可以直接根据 `report_meta` 显示质量提示。

### A4：分辩位三层评分 rubric

涉及文件：
- `api/services/rubric_service.py`
- `api/services/scoring_service.py`
- `api/tests/test_role_weight_matrix.py`
- `api/tests/test_scoring_semantics.py`

怎么改：
- 评分分成三层：
  - 通用论证能力。
  - 辩位职责履行。
  - 团队过程表现。
- 四个辩位分别定义职责：
  - 一辩：概念界定、框架搭建、主论点建立。
  - 二辩：盘问设计、证据追问、漏洞识别。
  - 三辩：反驳整合、攻防转换、临场回应。
  - 四辩：总结陈词、价值权衡、胜负归因。
- 分数保留标准维度：
  - `logic`
  - `argument`
  - `response`
  - `persuasion`
  - `teamwork`

验收：
- 每个辩手都有个人评分和辩位职责评分。
- 团队分和个人分不混用。
- 评分维度在报告、历史、成长中心口径一致。

### A5：报告语义增强

涉及文件：
- `api/services/report_service.py`
- `api/services/scoring_service.py`
- `api/tests/test_report_score_readiness.py`
- `api/tests/test_report_pdf_export.py`
- `api/tests/test_markdown_pdf.py`

怎么改：
- 报告新增：
  - `turning_points`
  - `evidence_anchors`
  - `improvement_actions`
  - `participant_scores`
  - `team_summary`
  - `teaching_summary`
- evidence anchor 必须可被 D 映射到回放。
- 报告分比赛版和教学版骨架。

验收：
- D 能从报告跳转到回放片段。
- 教师端可以展示报告质量和重算入口。
- 学生端不暴露过多技术细节。

### A6：评分校准与异常样本回流

涉及文件：
- `api/services/score_validation_service.py`
- `api/tests/test_score_validation_service.py`

怎么改：
- 记录异常样本：
  - JSON 修复失败。
  - fallback 触发。
  - 分数极端。
  - 证据锚点缺失。
- 生成最小校准摘要：
  - 样本数量。
  - 相邻一致率。
  - 分辩位异常分布。
  - fairness check 结果。

验收：
- 不能把平台评分写成已被严格验证的科学评分系统。
- 可以写成“具备评分校准和异常样本回流机制”。

## 4. A 的联调顺序

1. 先给 D 报告 mock。
2. 再给 B 报告/评分 schema。
3. 等 B 给画像和辩位字段。
4. 等 E 给资料摘要和 knowledge snippet。
5. 接入真实 judge/mentor/debater。
6. 跑报告和回放锚点联调。

## 5. A 的最终验收

- Prompt Pack 不散落在 agent 文件里。
- Judge 非法 JSON 可以修复或降级。
- 报告有质量标记。
- 分辩位评分可解释。
- 证据锚点可被前端使用。
- A 不修改 B/C/D/E 文件。
