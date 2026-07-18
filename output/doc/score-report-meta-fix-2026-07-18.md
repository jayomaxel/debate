# 评分报告元数据与证据来源补齐修复说明

日期：2026-07-18

## 一、问题背景

本次修复对应评分报告链路中“后端已有部分评分元数据，但教师端未完整透出、前端未展示”的问题。此前系统已经在底层评分合同中生成了 `report_meta`、`evidence_anchors`、`quality_flags`、`calibration_summary` 等结构，但在教师端编排层与报告页上存在明显缺口，导致老师查看报告时无法直接确认以下关键信息：

- 当前评分结果来自评分模型还是降级补全
- 当前报告使用的是哪一版评分量表
- Prompt Pack 与校准版本是什么
- 证据锚点来自哪里，前端页面缺少明确来源说明
- 老报告数据在未补全 `evidence_anchors` 时，元数据统计与页面锚点展示口径不一致

## 二、根因分析

本次问题的根因不是“底层完全没有数据”，而是“数据已经存在，但合同链路没有完整透出”：

1. `ScoreValidationService` 已经能够生成带版本信息的 `report_meta`
2. `ReportGenerator` 和本地评分补丁也已经能产出 `evidence_anchors`
3. 但 `ReportOrchestrationService` 在构建教师端 `report_meta` 时，没有把底层 `report_meta` 中的版本和来源字段继续暴露出来
4. 教师端前端类型定义中缺少对应字段，导致即使接口有数据，页面也没有接
5. 报告页只展示了 `report_quality`、缓存状态等浅层信息，没有把评分来源、量表版本、证据来源口径展示给老师
6. 对旧报告兼容不足：历史报告如果尚未写入 `evidence_anchors`，教师端元数据里会显示证据锚点数为 0，但页面右侧仍可能根据发言渲染锚点，形成口径割裂

## 三、后端修复内容

### 1. 补齐教师端报告元数据编排

在 `api/services/report_orchestration_service.py` 中补齐了对底层评分合同元数据的透传与归并，新增/明确输出以下字段：

- `scoring_source`
- `scoring_quality`
- `provider`
- `prompt_pack_version`
- `rubric_version`
- `calibration_version`
- `mode`
- `retry_count`
- `evidence_anchor_count`
- `evidence_source_types`
- `evidence_sources`

同时增加了 `_score_contract_meta`、`_evidence_source_info`、`_summarize_evidence_sources` 等辅助方法，用于：

- 从底层 `report_meta` 中提取评分版本与来源
- 对证据锚点来源做统一归一化
- 给教师端输出可直接展示的“证据来源摘要”

### 2. 统一证据锚点来源字段

在以下两个位置统一补齐了证据锚点来源字段：

- `api/services/report_service.py`
- `api/services/scoring_service.py`

为每个锚点补充：

- `source_location`
- `evidence_source`
- `source_type`
- `source_kind`
- `source_label`

当前默认的发言证据来源被明确标记为：

- `evidence_source = debate_speech`
- `source_label = Debate speech transcript`

这样前端和后端不再需要依赖隐式推断。

### 3. 补齐教师端 speech anchor 的来源信息

在 `build_speech_anchors` 中增加了对 `evidence_anchors` 的映射逻辑，使教师端返回的 `speech_anchors` 不再只是“发言摘要 + 是否有分数”，还会附带：

- `evidence_source`
- `source_label`

这样教师报告页右侧的锚点卡片可以直接展示“该锚点证据来自什么来源”。

### 4. 兼容历史报告数据

考虑到历史报告中可能只有发言和评分，没有显式写入 `evidence_anchors`，本次在编排层增加了兼容回推逻辑：

- 当报告里没有 `evidence_anchors`
- 但当前辩论存在有效发言时

系统会按有效发言数推断出：

- `evidence_anchor_count`
- `evidence_sources = [{ source_type: "debate_speech", label: "Debate speech transcript", count: N }]`

这样可以保证旧数据不会出现“元数据说没有证据锚点，但页面实际有可查看发言锚点”的矛盾。

## 四、前端修复内容

### 1. 补齐教师端类型定义

在 `web/src/services/teacher.service.ts` 中补充了教师报告元数据与发言锚点的类型定义，包括：

- `TeacherReportMeta.scoring_source`
- `TeacherReportMeta.scoring_quality`
- `TeacherReportMeta.provider`
- `TeacherReportMeta.prompt_pack_version`
- `TeacherReportMeta.rubric_version`
- `TeacherReportMeta.calibration_version`
- `TeacherReportMeta.mode`
- `TeacherReportMeta.retry_count`
- `TeacherReportMeta.evidence_anchor_count`
- `TeacherReportMeta.evidence_source_types`
- `TeacherReportMeta.evidence_sources`
- `TeacherSpeechAnchor.evidence_source`
- `TeacherSpeechAnchor.source_label`

同时新增 `TeacherEvidenceSourceSummary` 类型，保证接口契约在前端可被完整消费。

### 2. 补齐教师报告页展示

在 `web/src/components/debate-report-page.tsx` 中补充了教师报告质量区块和锚点卡片展示。

新增展示内容：

- 评分来源
- 量表版本
- Prompt Pack 版本
- 校准版本
- 证据锚点数量
- 证据来源摘要

同时在每条发言锚点卡片底部增加了“证据来源”显示，避免老师只能看到摘要，却不知道该锚点来自哪里。

## 五、测试与验证

本次修复补充并通过了以下验证：

### 后端回归测试

执行命令：

```bash
python -m pytest api/tests/test_report_score_readiness.py api/tests/test_teacher_student_contracts.py -q --tb=short -p no:cacheprovider --basetemp .pytest_tmp_codex
```

结果：

- `11 passed`

覆盖验证点包括：

- `report_meta` 是否透出 `rubric_version`
- `report_meta` 是否透出 `scoring_source`
- `report_meta` 是否能统计 `evidence_anchor_count`
- `report_meta.evidence_sources` 是否正确返回 `debate_speech`
- `speech_anchors` 是否补充 `source_label`
- 旧报告兼容场景下是否仍能给出默认版本和证据来源摘要

### 前端类型检查

执行命令：

```bash
web/node_modules/.bin/tsc.cmd --noEmit
```

结果：

- 通过

说明新增字段未破坏现有前端类型系统。

## 六、影响范围

本次修改影响的是“评分报告合同的透传完整性”和“教师端报告页的可解释性”，不会改变已有评分计算逻辑本身，也不会改变报告生成主流程的业务入口。

直接收益包括：

- 老师能在页面上直接看到评分来源与版本口径
- 评分结果更可解释，便于排查评分异常与版本差异
- 前后端对证据锚点的来源口径统一
- 历史报告兼容性更好，不会因为旧结构缺字段而导致展示割裂

## 七、本次提交包含文件

- `api/services/report_orchestration_service.py`
- `api/services/report_service.py`
- `api/services/scoring_service.py`
- `api/tests/test_report_score_readiness.py`
- `api/tests/test_teacher_student_contracts.py`
- `web/src/services/teacher.service.ts`
- `web/src/components/debate-report-page.tsx`
- `output/doc/score-report-meta-fix-2026-07-18.md`

## 八、说明

当前工作区中还存在其他与本次修复无关的本地变更与临时目录，例如测试临时文件、历史文档和本地配置文件。本次提交将仅包含上述与“评分报告元数据和证据来源补齐”直接相关的文件，不会把无关改动一并推送到 GitHub。
