# C5 报告读取与 Excel 审计限流补齐总结

## 本轮目标

- 按严格验收口径补齐报告读取和 Excel 导出路径。
- 让所有会触发报告生成/导出的报告接口都进入同一限流桶。
- 让普通报告读取和 Excel 导出成功后也产生可追踪审计事件。

## 修改文件

- `api/middleware/rate_limit.py`
- `api/routers/student.py`
- `api/tests/test_rate_limit.py`
- `api/tests/test_student_report_pdf_cache.py`

## 代码逻辑

- `report_regeneration` 限流正则从只匹配 `/reports/{id}/export/...` 和 `/send-email`，扩展为同时匹配裸路径 `/reports/{id}`。
- `get_student_report` 在 `ReportGenerator.generate_student_report` 成功后记录 `report_regeneration` 审计事件，动作为 `get_student_report`。
- `export_report_excel` 在 Excel bytes 生成成功后记录 `report_regeneration` 审计事件，动作为 `export_report_excel`，并记录 `export_format=excel`。
- 新增限流测试，确认高频调用 `/api/student/reports/{id}` 会被 `report_regeneration` 桶拦截。
- 新增路由级审计测试，确认普通报告读取和 Excel 导出都会写入成功审计。

## 对应功能

- 报告读取、PDF 导出、Excel 导出、邮件发送均具备限流或审计覆盖。
- C5 中“报告重算/关键操作可追踪”和“高频调用可被限流”的标准覆盖更完整。

## 验证结果

- `python -m pytest api\tests\test_rate_limit.py -q`：6 passed。
- `python -m pytest api\tests\test_student_report_pdf_cache.py -q`：5 passed。
- `python -m pytest api\tests\test_audit_service.py -q`：5 passed。

## 风险与说明

- `/api/student/reports/{id}` 现在也会按 `report_regeneration` 的 6 次/分钟策略限流；这是按严格安全验收口径选择的保护策略。
- 如果产品侧以后希望普通报告读取频率更高，可以单独拆一个更宽松的 `report_read` 限流桶。
