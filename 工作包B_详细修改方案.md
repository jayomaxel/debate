# 工作包B：详细修改方案

## 1. B 要解决什么

B 是教学业务编排负责人。它不负责底层 AI 评分，不负责文件抽取，也不负责前端页面，而是把 A、C、E 的能力组织成教师和学生可用的业务接口。

B 的最终交付：
- 结构化建赛/预约接口。
- 候选辩题推荐编排接口。
- 学生画像与角色推荐接口。
- AI 辩位分配和教师确认接口。
- 报告、回放、教师复盘、报告重算业务接口。

## 2. B 不做什么

B 不处理：
- prompt 和评分算法。
- 教学设计文件抽取和资料摘要底层服务。
- 安全会话和 WebSocket ticket。
- 前端组件。

教学设计和资料服务由 E 做，B 只调用 E。报告和评分由 A 做，B 只聚合。安全和审计由 C 做，B 只接入。

## 3. 修改阶段

### B0：路由与业务接口骨架

涉及文件：
- `api/routers/teacher.py`
- `api/routers/student.py`
- `api/services/debate_service.py`

怎么改：
- 梳理教师端接口：
  - 建赛/预约。
  - 候选辩题推荐。
  - 辩位分配预览。
  - 辩位分配确认。
  - 教师复盘摘要。
  - 报告重算。
- 梳理学生端接口：
  - 学生画像。
  - 当前辩位理由。
  - 准备建议。
  - 报告和回放入口。
- 接口先返回 mock，字段必须和冻结合同一致。

验收：
- D 可以不等真实逻辑，先用 B mock 接页面。

### B1：结构化建赛/预约配置

涉及文件：
- `api/services/debate_service.py`
- `api/routers/teacher.py`
- `api/tests/test_debate_config_meta.py`

怎么改：
- 新增 `DebateConfigMeta` 读写逻辑。
- 老数据继续兼容 `description`。
- 新数据不再把所有配置塞进 description。
- 建赛/预约支持：
  - `mode`
  - `role_assignment_mode`
  - `assignment_policy`
  - `rounds`
  - `knowledge_points`
  - `objective`
  - `evaluation_focus`
  - `forbidden_moves`
  - `support_document_ids`
  - `teaching_design_version_id`
  - `activity_focus`

验收：
- 老版 description 能解析。
- 新版结构化配置能序列化。
- D 不需要解析隐藏字符串。

### B2：候选辩题推荐编排

涉及文件：
- `api/services/debate_service.py`
- `api/routers/teacher.py`
- `api/tests/test_topic_recommendation.py`

怎么改：
- B 不直接做文件抽取，调用 E：
  - 当前班级教学设计版本。
  - 抽取出的课程目标、知识点、章节主题。
  - 支持材料摘要和标签。
- B 组织 prompt 或调用 A/LLM 生成候选辩题。
- 每个候选辩题必须包含：
  - 辩题文本。
  - 适配课程目标。
  - 对应知识点。
  - 课堂场景。
  - 可辩性说明。
  - 难度等级。
  - 推荐原因。
  - 来源依据。

验收：
- 没有教学设计时，接口降级为手动建赛提示。
- 有教学设计时，至少返回 3 个候选辩题。
- 推荐结果不声称“自动最优”，只作为教师选择建议。

### B3：学生画像与角色推荐

涉及文件：
- `api/models/assessment.py`
- `api/services/assessment_service.py`
- `api/services/analytics_service.py`
- `api/routers/student.py`
- `api/tests/test_assessment_profile.py`

怎么改：
- 标准画像维度：
  - `expression`
  - `logic`
  - `critical`
  - `knowledge_primary`
  - `knowledge_secondary`
- 兼容旧字段：
  - `expression_willingness`
  - `logical_thinking`
  - `stablecoin_knowledge`
  - `financial_knowledge`
  - `critical_thinking`
- 融合来源：
  - 自评。
  - 历史成绩。
  - 发言统计。
- 数据不足时返回 `analysis_basis`。

验收：
- 不接入 LMS 时不能写“学情大数据”。
- 画像必须说明数据依据。
- D 能展示低置信度提示。

### B4：AI 辩位分配

涉及文件：
- `api/services/debate_service.py`
- `api/services/assessment_service.py`
- `api/tests/test_role_assignment.py`

怎么改：
- 建立四辩位能力模型：
  - 一辩：定义框架、立论搭建、概念界定。
  - 二辩：盘问推进、证据追问、漏洞识别。
  - 三辩：反驳整合、攻防转换、临场回应。
  - 四辩：总结陈词、价值权衡、胜负归因。
- 支持两种模式：
  - `strength_first`：发挥优势。
  - `growth_first`：补齐短板。
- 加入重复辩位惩罚：
  - 查询学生历史辩位分布。
  - 长期重复同一辩位时降低匹配分。
- 输出解释：
  - 分配理由。
  - 维度贡献。
  - 数据来源。
  - 历史辩位分布。
  - 是否教师覆盖。

验收：
- 不再按进入顺序分配一辩二辩。
- 教师能确认或覆盖。
- 学生能看到简化版分配理由。

### B5：报告、回放、教师复盘接口

涉及文件：
- `api/routers/teacher.py`
- `api/routers/student.py`
- `api/services/debate_service.py`
- `api/services/analytics_service.py`

怎么改：
- 调用 A 的报告结构。
- 给 D 提供：
  - 报告详情。
  - 回放锚点。
  - 教师复盘摘要。
  - 报告重算入口。
- 学生端隐藏技术细节，教师端显示报告质量和降级信息。

验收：
- `fallback / partial` 报告教师端可见。
- 报告重算有权限限制。
- 回放锚点和报告证据能对应。

## 4. B 的架构建议

- `teacher.py` 只做教师路由和响应组织。
- `student.py` 只做学生路由和响应组织。
- `debate_service.py` 做业务编排。
- `assessment_service.py` 做画像和辩位适配。
- `analytics_service.py` 做历史统计和成长分析。
- B 调 E，不复制 E 的教学设计逻辑。
- B 调 A，不复制 A 的评分逻辑。

## 5. B 的联调顺序

1. 先和 E 联调教学设计/资料摘要。
2. 再和 A 联调报告和评分字段。
3. 再和 D 联调教师端和学生端页面。
4. 最后和 C 联调权限、审计、上传错误。

## 6. B 的最终验收

- 建赛/预约结构化。
- 候选辩题可生成。
- 学生画像可解释。
- 辩位分配可解释、可确认、可覆盖。
- 报告/回放/复盘接口稳定。
- B 不修改 E 的服务文件和 D 的前端文件。
