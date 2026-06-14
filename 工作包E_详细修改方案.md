# 工作包E：详细修改方案

## 1. E 要解决什么

E 从 B 中拆出教学设计与资料支撑。E 的任务相对简单，但很关键：它要让平台能读懂教师上传的教学设计和支持材料，并把这些内容变成 A/B/D 都能消费的结构化数据。

E 的最终交付：
- 教学设计 schema。
- 教学设计版本管理。
- 教学设计结构化抽取结果存储。
- 教师校正结果保存。
- 支持材料标签。
- 支持材料摘要。
- KnowledgeSnippet。
- mock fixture 和接口示例。

## 2. E 不做什么

E 不做：
- 教师/学生主路由。
- 候选辩题最终编排。
- AI 辩位分配。
- 评分报告。
- 登录安全。
- 前端页面。

E 只做资料基础能力，B 负责业务编排，D 负责展示，A 负责 AI 使用。

## 3. 修改阶段

### E0：教学设计数据结构

涉及文件：
- `api/models/class_teaching_design.py`
- `api/tests/test_teaching_design_service.py`

怎么改：
- 建立班级级教学设计模型。
- 支持多版本。
- 每个版本包含：
  - 文件名。
  - 文件类型。
  - 上传时间。
  - 抽取状态。
  - 抽取结果。
  - 置信度。
  - 缺失字段。
  - 来源片段映射。

验收：
- 一个班级可以有当前教学设计版本。
- 历史版本可追踪。

### E1：结构化抽取结果服务

涉及文件：
- `api/services/teaching_design_service.py`

怎么改：
- 不假设教师文件一定按固定模板写。
- 抽取结果统一为：
  - 课程目标。
  - 知识点。
  - 章节主题。
  - 重点难点。
  - 能力培养目标。
  - 适用年级。
  - 课时约束。
  - 教师备注。
- 抽取不到就写入 `missing_fields`。
- 不确定就写入 `confidence`。
- 保留 `source_excerpt_map`。

验收：
- 非标准教学设计也能保存部分抽取结果。
- 不能把缺失字段伪造成完整字段。

### E2：教师校正结果保存

涉及文件：
- `api/services/teaching_design_service.py`
- `api/tests/test_teaching_design_service.py`

怎么改：
- 支持教师修改抽取后的结构化字段。
- 修改后保存为当前版本的校正结果。
- 保留原始抽取结果和教师校正结果的区别。

验收：
- D 在线修改后，刷新页面仍能看到修改后的结构。

### E3：支持材料模型与标签

涉及文件：
- `api/models/document.py`
- `api/services/document_service.py`

怎么改：
- 支持资料标签：
  - `background`
  - `evidence`
  - `case`
  - `optional`
- 记录文件类型、上传时间、处理状态、摘要状态。
- 上传安全错误由 C 处理，E 只管业务记录。

验收：
- 同一份资料能被标注用途。
- 资料处理失败有状态。

### E4：支持材料摘要

涉及文件：
- `api/services/document_service.py`
- `api/tests/test_support_document_summary.py`

怎么改：
- 生成或保存：
  - summary。
  - key_points。
  - evidence_candidates。
  - case_candidates。
  - usable_phases。
  - summary_quality。
- 摘要失败时允许 fallback。
- 不直接把全文塞给 A。

验收：
- A 能按阶段拿摘要片段。
- B 能用摘要做候选辩题来源依据。
- D 能展示资料摘要质量。

### E5：KnowledgeSnippet 输出

涉及文件：
- `api/services/knowledge_base.py`

怎么改：
- 按标签和阶段筛选片段。
- 输出：
  - `snippet_id`
  - `document_id`
  - `source_type`
  - `content`
  - `usage_goal`
  - `source_location`
- 给 A 的 prompt 只注入摘要片段和使用目标。

验收：
- 开篇、盘问、自由辩、总结能拿到不同资料片段。

### E6：fixture 和契约示例

涉及文件：
- `api/tests/fixtures/*.json`
- `docs/api_contract_examples/*.json`
- `docs/acceptance_checklist.md`

怎么改：
- 给 D 提供教学设计 mock。
- 给 B 提供候选辩题来源 mock。
- 给 A 提供 knowledge snippet mock。
- 给 C 提供上传对象类型示例。

验收：
- D 不等真实后端也能做教学设计中心。
- A/B 能用 fixture 写单测。

## 4. E 的架构建议

- `class_teaching_design.py` 只放教学设计模型。
- `document.py` 只放支持材料模型。
- `teaching_design_service.py` 只处理教学设计版本和抽取结果。
- `document_service.py` 只处理资料业务记录和摘要结果。
- `knowledge_base.py` 只负责片段检索和输出。
- 不新增教师主路由，由 B 调 E 服务后对外输出。

## 5. E 的联调顺序

1. 先给 D 教学设计 fixture。
2. 再给 B 教学设计服务方法。
3. 再给 B 支持材料摘要。
4. 再给 A knowledge snippet。
5. 最后和 C 对上传安全错误。

## 6. E 的最终验收

- 教学设计可以按班级和版本管理。
- 非标准文档也能部分抽取。
- 支持材料能打标签、出摘要。
- A/B/D 都能消费 E 的数据。
- E 不修改 B 的路由和 D 的前端。
