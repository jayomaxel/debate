# 工作包A的开发文档

## 1. 结论

工作包 A 当前已经完成 A0：AI 内核数据合同、Prompt Pack V1 骨架、比赛/教学模式策略、默认领域包、三层评分 rubric、Judge JSON 校验/fallback 纯函数层和对应单测。

当前所处阶段：A0 已完成，下一步应进入 A1/A2，把现有 `debater_agent.py`、`judge_agent.py`、`mentor_agent.py` 中散落的 prompt 逐步切换到 `PromptPackService`，并保持旧方法签名兼容。

已经完成的内容：
- 已新增 AI 内核服务文件：`prompt_pack_service.py`、`mode_policy_service.py`、`domain_pack_service.py`、`rubric_service.py`、`score_validation_service.py`。
- 已冻结 `PromptBuildContext`、`ReportMeta`、`ScoringPolicy`、`DebateReportSchema`、`ScoreEvidenceSchema` 的默认字段、枚举值和 mock 示例。
- 已把比赛/教学模式策略、Prompt Pack 7 层结构、分辩位 rubric、Judge JSON 校验与 fallback 规则做成纯函数和可单测模块。
- 已补齐 A 第一阶段测试：`test_prompt_pack.py`、`test_score_validation_service.py`、`test_role_weight_matrix.py`、`test_judge_fallback.py`、`test_scoring_semantics.py`。

仍然不要做的内容：
- 不要修改教师/学生路由、前端页面、认证安全、教学设计和知识库业务文件。
- 不要依赖 B/E 未冻结的真实字段直接接入业务表。
- 不要一次性替换所有 agent prompt，应逐个 agent 接入并用测试保护。

当前 A 新增单测已通过，命令是：

```powershell
python -m pytest api\tests\test_prompt_pack.py api\tests\test_score_validation_service.py api\tests\test_role_weight_matrix.py api\tests\test_judge_fallback.py api\tests\test_scoring_semantics.py -q -p no:cacheprovider
```

结果：21 passed。

如果新环境缺依赖，先安装：

```powershell
cd "D:\白玉京\辩论开发\api"
python -m pip install -r requirements.txt
```

## 2. 当前项目状态

项目代码已经完整落在目录中，但当前目录不是 Git 仓库形态，属于源码快照。这不影响本地开发和测试，但如果后续要提交或拉取，需要重新初始化或重新克隆。

### A 文档要求的新文件现状

以下 5 个 A 内核服务文件当前已经新增：

| 文件 | 当前状态 | 用途 |
| --- | --- | --- |
| `api/services/prompt_pack_service.py` | 已新增 | 统一构建 Prompt Pack，定义 `PromptBuildContext`、`PromptPack`、`DebateReportSchema`、`ScoreEvidenceSchema` |
| `api/services/mode_policy_service.py` | 已新增 | 管理 competition / teaching 策略 |
| `api/services/domain_pack_service.py` | 已新增 | 管理领域资料注入，默认不注入金融稳定币 |
| `api/services/rubric_service.py` | 已新增 | 管理三层 rubric、辩位权重和 `ScoringPolicy` |
| `api/services/score_validation_service.py` | 已新增 | JSON 校验、修复、fallback、`ReportMeta`、异常样本摘要 |

### 现有 A 相关文件状态

| 文件 | 现状判断 |
| --- | --- |
| `api/agents/debater_agent.py` | 已有大量内联 prompt，生成立论、盘问、回应、反驳、结辩、自由辩论等内容，是 A1 重构重点。 |
| `api/agents/judge_agent.py` | 已有评分、违规检测、反馈、整场批量复盘；评分 prompt 和 JSON 解析/fallback 混在 agent 内，是 A3 重点。 |
| `api/agents/mentor_agent.py` | 已有导师建议 prompt，但未区分比赛/教学模式策略，是 A2 重点。 |
| `api/services/scoring_service.py` | 已有本地规则评分和批量评分，使用旧五维分数；可作为 fallback 基础，但缺少 `ReportMeta` 和 rubric 版本标记。 |
| `api/services/report_service.py` | 已有 `Report` 类、学生报告、班级报告、Markdown/PDF/Excel 导出；输出仍是旧结构，缺少 DebateReport V2 字段。 |
| `api/services/flow_controller.py` | 负责辩论流程和 AI 发言调度；A 可以接入 prompt 构建，但要非常小心，避免影响实时流程。 |
| `api/services/history_service.py` | 历史查询可以后置适配报告质量字段，不应第一阶段改。 |
| `api/services/coze_client.py` | Coze 封装较独立，A 一般只需要保持调用兼容。 |

### 数据模型状态

- `api/models/debate.py` 里 `Debate.report` 是 JSON 字段，可以承载 `DebateReportSchema` 与 `report_meta`。
- `api/models/score.py` 里 `Score` 只有旧五维分数、总分和反馈，没有 `scoring_quality`、`rubric_version`、`prompt_pack_version` 等字段。
- 所以第一阶段建议把新元信息放进报告 JSON 和服务返回结构，不急着改数据库表。

### 测试状态

已有相关测试：
- `api/tests/test_report_score_readiness.py`
- `api/tests/test_report_pdf_export.py`
- `api/tests/test_markdown_pdf.py`
- `api/tests/test_student_report_pdf_cache.py`

A 第一阶段已经补齐的测试：
- `api/tests/test_prompt_pack.py`
- `api/tests/test_judge_fallback.py`
- `api/tests/test_scoring_semantics.py`
- `api/tests/test_role_weight_matrix.py`
- `api/tests/test_score_validation_service.py`

当前 A 新增单测结果：21 passed。

## 3. 开发边界

### A 可以修改

- `api/agents/debater_agent.py`
- `api/agents/judge_agent.py`
- `api/agents/mentor_agent.py`
- `api/services/coze_client.py`
- `api/services/flow_controller.py`
- `api/services/report_service.py`
- `api/services/scoring_service.py`
- `api/services/history_service.py`
- `api/services/prompt_pack_service.py`
- `api/services/mode_policy_service.py`
- `api/services/domain_pack_service.py`
- `api/services/rubric_service.py`
- `api/services/score_validation_service.py`
- A 自己负责的测试文件

### A 禁止修改

- `api/routers/teacher.py`
- `api/routers/student.py`
- `api/routers/auth.py`
- `api/routers/websocket.py`
- `api/services/debate_service.py`
- `api/services/assessment_service.py`
- `api/services/analytics_service.py`
- `api/services/teaching_design_service.py`
- `api/services/document_service.py`
- `api/services/knowledge_base.py`
- `api/utils/security.py`
- `api/services/auth_service.py`
- `api/services/config_service.py`
- `api/main.py`
- `web/src/**`
- `web/index.html`
- `web/package.json`

边界原则：A 只输出 AI 内核、评分语义和报告合同；B/D/E 只能消费 A 冻结后的结构，A 也不能越界读取或解释 B/E 的业务对象。

## 4. 推荐开发顺序

### A0：先做合同和纯函数

新增文件：
- `api/services/mode_policy_service.py`
- `api/services/domain_pack_service.py`
- `api/services/rubric_service.py`
- `api/services/prompt_pack_service.py`
- `api/services/score_validation_service.py`
- `api/tests/test_prompt_pack.py`
- `api/tests/test_role_weight_matrix.py`
- `api/tests/test_score_validation_service.py`

目标：
- 用 Pydantic 或 dataclass 定义 A 合同。因为 `api/schemas/**` 不在 A owner 列表里，建议先把模型放在 A 自己的 service 文件中。
- 所有字段要有默认值和枚举值。
- 先不调用真实模型，不接 Coze，不接数据库。

验收：
- `PromptBuildContext` 默认 `mode=competition`。
- `ReportMeta.scoring_quality` 支持 `validated / repaired / fallback / partial`。
- `ScoringPolicy` 支持三层权重，权重和可被测试。
- 生成一份 DebateReport V2 mock，D 可以直接看字段。

### A1：Prompt Pack 统一入口

目标：
- 固定 7 层结构：`global_rules / mode_policy / task_contract / phase_objective / context_block / output_contract / domain_pack`。
- agent 不再自行解释 mode，不再散写完整业务 prompt。
- 第一阶段保留旧 agent 方法签名，只在内部通过 `prompt_pack_service.build_prompt()` 生成 prompt。

推荐方式：
- `PromptPackService.build_prompt(context) -> PromptPack`
- `PromptPack.render() -> str`
- `AIDebaterAgent`、`JudgeAgent`、`MentorAgent` 只负责调用模型和解析结果。

验收：
- 同一个 agent 在 `competition` 和 `teaching` 下输出 prompt 内容不同，但结构稳定。
- 同一阶段的 prompt 字段顺序稳定。
- Prompt Pack 测试不依赖数据库和外部模型。

### A2：比赛/教学模式策略

目标：
- `competition`：强调论证强度、回应有效性、关键失误、回合控制；mentor 输出 80-120 字战术建议。
- `teaching`：强调知识迁移、课程目标、反思动作；mentor 输出 120-180 字改进建议。
- 默认仍为 `competition`。

建议实现：
- `ModePolicyService.get_policy(mode, agent, phase)` 返回稳定字典。
- `PromptPackService` 消费 policy，不让 agent 判断模式。

验收：
- 切换 mode 不改 agent 代码。
- teaching 模式不影响旧 competition 默认行为。

### A3：Judge JSON 校验、修复与 fallback

目标：
- Judge 首次输出后先 schema 校验。
- 非法 JSON 走一次修复。
- 修复失败才 fallback。
- fallback 不伪装正常评分，必须写入 `ReportMeta`。

推荐实现：
- `ScoreValidationService.extract_json(text)`：支持去除代码块和前后解释文本。
- `ScoreValidationService.validate_speech_score(payload)`：校验五维分数、总分、feedback。
- `ScoreValidationService.build_repair_prompt(raw_text, contract)`：构造修复 prompt。
- `ScoreValidationService.build_fallback_score(reason, policy)`：返回 fallback 分数和 meta。

验收：
- 非法 JSON 不会导致报告生成失败。
- `retry_count`、`provider`、`prompt_pack_version`、`rubric_version` 有默认值。
- `scoring_quality` 能区分 `validated / repaired / fallback / partial`。

### A4：分辩位三层 rubric

目标：
- 评分层次分为：通用论证能力、辩位职责履行、团队过程表现。
- 保留旧五维输出：`logic / argument / response / persuasion / teamwork`，避免 D/B 旧字段断裂。
- 为四个辩位提供职责权重：
  - 一辩：概念界定、框架搭建、主论点建立。
  - 二辩：盘问设计、证据追问、漏洞识别。
  - 三辩：反驳整合、攻防转换、临场回应。
  - 四辩：总结陈词、价值权衡、胜负归因。

验收：
- 每个辩手都有个人评分和辩位职责评分。
- 团队分和个人分不混用。
- `api/tests/test_role_weight_matrix.py` 覆盖权重和版本。

### A5：DebateReport V2

目标：
- 在现有报告基础上新增：
  - `report_meta`
  - `turning_points`
  - `evidence_anchors`
  - `improvement_actions`
  - `participant_scores`
  - `team_summary`
  - `teaching_summary`
- 保留旧字段：`participants / speeches / statistics / winner`，避免现有 PDF、历史和前端调用直接断裂。

建议：
- `Report.to_dict()` 保持旧字段，同时增加 V2 字段。
- `ReportGenerator.generate_student_report()` 可以先补默认空数组/空对象。
- `export_to_pdf_async()` 和 Markdown 导出先做到“新增字段不报错”，再逐步美化内容。

验收：
- D 能从 `evidence_anchors[].turn_id` 映射回放片段。
- PDF/Markdown 导出不因新增字段失败。
- `report_meta` 可直接给前端显示质量提示。

### A6：评分校准与异常样本回流

目标：
- 记录异常样本类型：JSON 修复失败、fallback 触发、极端分数、证据锚点缺失。
- 生成最小校准摘要：样本数量、相邻一致率、分辩位异常分布、fairness check 结果。

建议：
- 第一版只做内存/报告级摘要，不新增数据库表。
- 对外表述为“具备评分校准和异常样本回流机制”，不要宣称科学评分已经严格验证。

## 5. 冻结合同建议

### PromptBuildContext

```json
{
  "agent": "debater | judge | mentor | report",
  "mode": "competition | teaching",
  "phase": "opening | questioning | free_debate | closing | report",
  "topic": "string",
  "role": "affirmative | negative | judge | mentor",
  "speaker_role": "debater_1 | debater_2 | debater_3 | debater_4 | judge | mentor",
  "stance": "pro | con | neutral",
  "history": [],
  "knowledge_snippets": [],
  "assessment_summary": {},
  "role_assignment_summary": {},
  "output_contract": {}
}
```

### ReportMeta

```json
{
  "scoring_source": "judge_model | fallback",
  "scoring_quality": "validated | repaired | fallback | partial",
  "provider": "coze | llm | local",
  "prompt_pack_version": "a.prompt_pack.v1",
  "rubric_version": "a.rubric.v1",
  "calibration_version": "a.calibration.v1",
  "mode": "competition | teaching",
  "retry_count": 0,
  "generated_at": "ISO-8601 datetime"
}
```

### DebateReportSchema

```json
{
  "mode": "competition",
  "domain_pack_id": "default",
  "report_meta": {},
  "turning_points": [],
  "evidence_anchors": [],
  "improvement_actions": [],
  "participant_scores": [],
  "participants": [],
  "speeches": [],
  "team_summary": {},
  "teaching_summary": {}
}
```

## 6. 兼容性策略

1. 保留旧五维分数字段，不重命名：`logic_score / argument_score / response_score / persuasion_score / teamwork_score / overall_score`。
2. 新增字段只追加，不删除旧字段。
3. `ReportMeta` 优先放在 `Debate.report` JSON 中，暂不强行改 `scores` 表。
4. agent 方法签名第一阶段不改，避免 `flow_controller.py` 调用链大面积变动。
5. Prompt Pack 先作为内部构建器上线，逐个替换内联 prompt。

## 7. 推荐本地开发命令

安装后端依赖：

```powershell
cd "D:\白玉京\辩论开发\api"
python -m pip install -r requirements.txt
```

运行 A 相关单测：

```powershell
cd "D:\白玉京\辩论开发"
python -m pytest api\tests\test_prompt_pack.py api\tests\test_score_validation_service.py api\tests\test_role_weight_matrix.py -q
```

运行报告兼容测试：

```powershell
cd "D:\白玉京\辩论开发"
python -m pytest api\tests\test_report_score_readiness.py api\tests\test_report_pdf_export.py api\tests\test_markdown_pdf.py -q
```

启动本地开发环境：

```powershell
cd "D:\白玉京\辩论开发"
.\start-dev.ps1
```

## 8. 风险清单

| 风险 | 等级 | 处理方式 |
| --- | --- | --- |
| Prompt 目前散落在 agent 内，直接替换容易破坏实时流程 | 高 | 先新增 Prompt Pack 服务和测试，再逐个 agent 接入 |
| B/E 接口未冻结，真实画像和资料摘要字段不可依赖 | 中 | A0-A2 使用默认 mock 和空对象，集成阶段再接入 |
| `Score` 表没有质量元字段 | 中 | 第一阶段把 meta 放进报告 JSON，后续再评估迁移 |
| 现有 PDF/Markdown 导出依赖旧报告结构 | 中 | 追加字段，保留旧字段，先跑导出兼容测试 |
| 当前本地依赖未安装完整 | 低 | 安装 `api/requirements.txt` 后再跑测试 |
| 目录不是 Git 仓库 | 低 | 不影响开发；需要版本管理时重新 clone 或初始化仓库 |

## 9. 第一阶段交付清单

最小可交付版本建议包括：

- `api/services/mode_policy_service.py`
- `api/services/domain_pack_service.py`
- `api/services/rubric_service.py`
- `api/services/prompt_pack_service.py`
- `api/services/score_validation_service.py`
- `api/tests/test_prompt_pack.py`
- `api/tests/test_score_validation_service.py`
- `api/tests/test_role_weight_matrix.py`
- `api/tests/test_judge_fallback.py`
- `api/tests/test_scoring_semantics.py`

第一阶段验收标准：
- Prompt Pack V1 能生成稳定 7 层 prompt。
- competition / teaching 策略可测试。
- Judge 非法 JSON 能修复或 fallback。
- fallback 结果带完整 `ReportMeta`。
- rubric 有版本号和辩位权重。
- 现有报告/PDF/Markdown 测试保持通过。

## 10. 是否能开始开发

已经开始，并完成 A0。

下一步推荐任务是 A1/A2：把 agent prompt 接入 `PromptPackService` 和 `ModePolicyService`。这个阶段仍然不依赖 B/E，不需要前端，不需要数据库迁移，也不应触碰禁改文件。

需要等 B/E 的部分是真实业务上下文接入，例如学生画像、辩位分配、教学设计摘要、知识片段等。A 可以先用空对象和 mock 数据完成内核，再在接口冻结后接入。
