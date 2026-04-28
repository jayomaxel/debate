# 前端遗留问题详细解决方案

## 1. 文档目标

本文档用于承接 `FRONTEND_ARCHITECTURE_FULL_SUMMARY.md` 中第 8、9 节提到的前端遗留问题，输出一份可以直接用于开发排期、任务拆分和实施落地的解决方案。

文档范围包括：

- 当前前端主流程中的无行为按钮、遗留入口、占位页、未挂载组件
- 前端内部结构收敛方案
- 需要前后端联动的接口补齐方案
- 建议的实施顺序、验收标准和风险点

本文档基于当前已挂载的主流程代码进行制定，不讨论未接入的历史分支作为主实现方向。

---

## 2. 解决原则

### 2.1 先修真实可见问题，再做结构升级

优先修复用户已经能看到、能点到、但没有实际行为的控件，例如：

- 学生控制中心 `查看全部`
- 学生准备中心两个快捷按钮
- 赛后分析页分享按钮
- 实时辩论页顶部设置 / 全屏 / 音量

### 2.2 不继续并行维护两套相似功能

当前 `EnhancedDebateAnalytics` 和 `StudentAnalyticsCenter` 在“分析中心”职责上存在明显重叠。后续应当收敛职责边界，避免长期维护两套分析页。

### 2.3 能复用现有状态与现有服务，就不要重复造轮子

例如：

- `DebateControls` 已经有 `autoPlayEnabled` 状态，就不应该为辩论页顶部音量按钮再新造一套音频开关逻辑
- `StudentAnalyticsCenter` 已经有 `history / growth / comparison / achievements` 四类长期数据，就不应该再把这套长期分析重复塞进 `EnhancedDebateAnalytics`

### 2.4 前端单独无法完成的项，要明确标记为前后端联动任务

典型代表是学生知识库文档卡片。目前学生端只有文档列表接口，没有预览/下载接口，因此这一项不能伪装成单纯前端修复。

---

## 3. 优先级与实施阶段

## 3.1 P0：立即修复，直接影响可用性

1. 学生控制中心历史模块 `查看全部`
2. 学生准备中心 `查看能力分析报告` / `查看历史辩论记录`
3. 赛后即时分析页分享按钮
4. 实时辩论页顶部设置 / 全屏 / 音量按钮
5. 管理员邮件配置重新挂载

## 3.2 P1：结构收敛，降低维护成本

1. 删除 `report-detail` 遗留路由入口
2. 清理或迁移旧版 `preparation-assistant.tsx` / `debate-hall.tsx`
3. 收敛 `EnhancedDebateAnalytics` 与 `StudentAnalyticsCenter` 的职责边界
4. 处理 `TeacherDashboard -> 数据分析` 占位页
5. 删除 `EnhancedDebateAnalytics` 中导入但未渲染的高级组件

## 3.3 P2：需要前后端联动或较大改造

1. 教师端辩论设置“支撑知识点”文件上传能力
2. 学生知识库文档预览 / 下载能力与状态同步刷新
3. `AppRouter` 迁移到真正的 URL 路由

---

## 4. 问题逐项解决方案

## 4.1 `report-detail` 路由级遗留

**状态：✅ 已完成**

完成标注：

- ~~删除 `app-router.tsx` 中 `currentPage` 联合类型里的 `'report-detail'`~~
- ~~删除 `app-router.tsx` 中的 `case 'report-detail'`~~
- ~~删除 `app-router.tsx` 对 `DebateReportDetail` 的直接 import~~
- ~~保留 `DebateReportPage` 内部 `overview/detail` 视图切换作为唯一报告详情入口~~

### 当前问题

- `AppRouter` 仍保留 `'report-detail'` 页面状态
- 同时正式报告流程已经通过 `DebateReportPage` 内部 `overview/detail` 状态完成
- 造成“同一个报告详情存在两套入口”的结构冗余

### 目标状态

- 全站报告详情统一收敛到 `DebateReportPage`
- `AppRouter` 不再直接维护 `report-detail` 页面
- 报告详情只保留“页面内部视图切换”这一种方式

### 涉及文件

- `web/src/components/app-router.tsx`
- `web/src/components/debate-report-page.tsx`
- `web/src/components/debate-report-detail.tsx`

### 具体修改方案

1. 在 `app-router.tsx` 中删除：
   - `currentPage` 联合类型中的 `'report-detail'`
   - `case 'report-detail'`
   - 对 `DebateReportDetail` 的直接 import

2. 保持报告详情的展示方式为：
   - `DebateReportPage` 内部 `view: 'overview' | 'detail'`
   - 从概览页点“查看详情”进入 detail
   - 从 detail 返回回到 overview

3. 检查是否还有其他组件试图直接跳转 `report-detail`
   - 如果有，全部改为跳 `debate-report`

### 验收标准

- 全项目不再存在可达的 `report-detail` 路由状态
- 任意查看报告行为统一进入 `DebateReportPage`
- 报告详情仍可正常进入和返回

### 风险说明

风险较低，属于结构删冗余，不涉及新增功能。

---

## 4.2 旧版 `preparation-assistant.tsx` 与 `debate-hall.tsx`

**状态：✅ 已完成**

完成标注：

- ~~新建 `web/src/components/legacy/` 目录~~
- ~~迁移 `student/preparation-assistant.tsx` 到 `web/src/components/legacy/preparation-assistant.tsx`~~
- ~~迁移 `debate-hall.tsx` 到 `web/src/components/legacy/debate-hall.tsx`~~
- ~~修正 legacy 内部旧版备战辅助 import 路径~~
- ~~删除 `student-command-center.tsx` 中旧版弹窗式备战辅助的注释痕迹~~

### 当前问题

- `student/preparation-assistant.tsx` 是旧版弹窗式备战辅助
- `debate-hall.tsx` 不在主流程中，但内部还引用旧版 `PreparationAssistant`
- 这两份代码容易让后续维护者误以为仍在主用

### 目标状态

二选一：

- 要么彻底清理
- 要么统一迁入 `legacy/` 目录，明确为历史代码

### 涉及文件

- `web/src/components/student/preparation-assistant.tsx`
- `web/src/components/debate-hall.tsx`
- `web/src/components/student-command-center.tsx`

### 推荐方案

推荐直接迁入 `web/src/components/legacy/`，而不是立即删除，理由是：

- 当前项目可能还处于频繁调整期
- 旧版组件可能被拿来参考交互或文案
- 迁移比硬删更稳

### 具体修改方案

1. 新建目录：
   - `web/src/components/legacy/`

2. 迁移文件：
   - `student/preparation-assistant.tsx`
   - `debate-hall.tsx`

3. 清理主流程残留注释：
   - 删除 `student-command-center.tsx` 中旧版弹窗式备战辅助的注释痕迹

4. 如后续确认完全无用，再第二阶段删除

### 验收标准

- 主目录下不再混放旧版未使用组件
- 主流程文件不再出现旧版组件的误导性注释

### 风险说明

如果直接删除，需要确认没有外部文档、测试、临时分支仍依赖这些文件。

---

## 4.3 学生控制中心历史模块 `查看全部`

**状态：✅ 已完成**

完成标注：

- ~~`StudentAnalyticsCenter` 新增 `defaultTab` 入参~~
- ~~`StudentAnalyticsCenter` 的 `activeTab` 初始值改为 `defaultTab ?? 'history'`~~
- ~~`defaultTab` 变化时同步更新 `activeTab`~~
- ~~`AppRouter` 新增 `studentAnalyticsTab` 状态并传给 `StudentAnalyticsCenter`~~
- ~~`StudentCommandCenter` 的 `onNavigateToAnalytics` 支持指定目标 tab~~
- ~~`DebateHistoryRecords` 的 `查看全部` 接线为 `onNavigateToAnalytics?.('history')`~~

### 当前问题

- `DebateHistoryRecords` 组件支持 `onClickAll`
- `StudentCommandCenter` 渲染时没有传入该回调
- 用户可以看到按钮，但点击无行为

### 目标状态

- 点击 `查看全部` 后进入 `StudentAnalyticsCenter`
- 默认落在 `history` 视图

### 涉及文件

- `web/src/components/student-command-center.tsx`
- `web/src/components/student-analytics-center.tsx`
- `web/src/components/app-router.tsx`

### 推荐实现方式

不要做“单纯跳到分析中心首页”，而要做“带默认 tab 的定向进入”。

### 具体修改方案

1. `StudentAnalyticsCenter` 新增 props：

```tsx
interface StudentAnalyticsCenterProps {
  onBack?: () => void;
  onViewReport?: (debateId: string) => void;
  onViewReplay?: (debateId: string) => void;
  defaultTab?: 'history' | 'growth' | 'comparison' | 'achievements';
}
```

2. `StudentAnalyticsCenter` 内部：
   - `activeTab` 初始值改为 `defaultTab ?? 'history'`
   - 当 `defaultTab` 改变时同步更新一次 `activeTab`

3. `AppRouter` 新增状态：

```tsx
const [studentAnalyticsTab, setStudentAnalyticsTab] =
  useState<'history' | 'growth' | 'comparison' | 'achievements'>('history');
```

4. `StudentCommandCenter` 增加 props：

```tsx
onNavigateToAnalytics?: (tab?: 'history' | 'growth' | 'comparison' | 'achievements') => void;
```

5. `查看全部` 接线：
   - 在 `StudentCommandCenter` 里给 `DebateHistoryRecords` 传 `onClickAll`
   - 行为为 `onNavigateToAnalytics?.('history')`

6. `AppRouter` 中：
   - 接到该回调后先 `setStudentAnalyticsTab('history')`
   - 再 `setCurrentPage('student-analytics')`

### 验收标准

- 点击 `查看全部` 可进入长期分析中心
- 默认落在历史记录页
- 历史记录中的报告、回放按钮仍然正常

### 风险说明

风险较低，是标准接线任务。

---

## 4.4 学生准备中心两个快捷按钮

**状态：✅ 已完成**

完成标注：

- ~~`StudentOnboardingProps` 新增 `onNavigateToAnalytics?: (tab: 'history' | 'growth') => void`~~
- ~~`查看能力分析报告` 点击后进入 `StudentAnalyticsCenter` 的 `growth`~~
- ~~`查看历史辩论记录` 点击后进入 `StudentAnalyticsCenter` 的 `history`~~
- ~~`AppRouter` 在 `case 'student'` 中透传分析中心跳转回调~~
- ~~保留 `查看能力分析报告` 的 `assessmentComplete` 禁用逻辑~~

### 当前问题

- `查看能力分析报告` 仅在评估完成后可点击，但没有行为
- `查看历史辩论记录` 显示可点，但没有行为

### 目标状态

- `查看能力分析报告` -> 进入 `StudentAnalyticsCenter` 的 `growth`
- `查看历史辩论记录` -> 进入 `StudentAnalyticsCenter` 的 `history`

### 涉及文件

- `web/src/components/student-onboarding.tsx`
- `web/src/components/app-router.tsx`
- `web/src/components/student-analytics-center.tsx`

### 具体修改方案

1. `StudentOnboardingProps` 新增：

```tsx
onNavigateToAnalytics?: (tab: 'history' | 'growth') => void;
```

2. 两个按钮分别绑定：

- `查看能力分析报告` -> `onNavigateToAnalytics?.('growth')`
- `查看历史辩论记录` -> `onNavigateToAnalytics?.('history')`

3. `AppRouter` 在 `case 'student'` 中透传该回调：
   - 设置 `studentAnalyticsTab`
   - 跳转到 `student-analytics`

4. 保持现有禁用逻辑：
   - `查看能力分析报告` 仍然要求 `assessmentComplete === true`
   - `查看历史辩论记录` 可直接进入

### 验收标准

- 两个按钮点击后都能跳到真实页面
- 页面落点正确
- 不会中断当前学生候场主流程

### 风险说明

风险较低。

---

## 4.5 教师端辩论设置“支撑知识点”文件上传

**状态：🟡 部分完成**

完成标注：

- ~~`TeacherDashboard` 新增支撑材料状态、隐藏文件输入框、上传/刷新/删除交互~~
- ~~“支撑知识点”区域扩展为“文本知识点 + 支撑材料上传区 + 文件列表”~~
- ~~未保存草稿时显示“请先保存草稿后再上传支撑材料”，并提供“先保存草稿”按钮~~
- ~~新建草稿保存后不再清空表单，保留编辑态并设置 `editingDebateId` / `editingDebateStatus`~~
- ~~编辑已有辩论时调用 `TeacherService.listDebateSupportDocuments(debateId)` 加载材料列表~~
- ~~`teacher.service.ts` 新增 `TeacherDebateSupportDocument` 和列表/上传/删除接口~~
- ~~`api/routers/teacher.py` 新增 `GET/POST/DELETE /api/teacher/debates/{debate_id}/support-documents`~~
- ~~教师支撑材料接口增加辩论归属权限校验，并校验文档属于当前辩论~~
- ~~复用现有 `Document` 模型与 `KnowledgeBase` 服务，不新增数据库迁移~~

暂未完成：

- [ ] 将 `KnowledgeBase.upload_document()` 拆成“保存记录 + 后台处理”两步，目前仍复用现有同步处理流程。
- [ ] 下载接口属于可选项，本轮暂未新增。

### 当前问题

- 教师端 `TeacherDashboard` 的“支撑知识点”当前只有一个 `Textarea`
- 前端 `debateConfig.knowledgePoints` 只是纯文本字符串
- `buildDebateDescription()` 只会把轮次和文本知识点拼进 `description`
- `TeacherService` 没有任何“按辩论上传支撑材料”的接口
- `api/routers/teacher.py` 当前也没有对应的上传 / 列表 / 删除路由

但后端并不是完全没有基础能力：

- `api/models/document.py` 里已经有挂在 `debates` 上的 `Document` 表
- `api/services/knowledge_base.py` 已经提供了按 `debate_id` 上传、查询、删除辩论文档的能力

也就是说，当前缺的不是底层存储模型，而是“教师端表单 + 教师路由 + 前端服务”的接线层。

### 目标状态

- 教师可以在“支撑知识点”区域上传 PDF / DOCX 支撑材料
- 上传的文件与某一场辩论任务一一绑定，而不是进入全局管理员知识库
- 教师既可以继续手工填写文本知识点，也可以补充上传文件
- 文件上传后可以看到列表、状态、删除入口
- 这些文档后续可以被辩论过程中的检索 / 辅助分析能力复用

### 总体设计建议

#### 方案原则

推荐直接复用现有的辩论级 `Document` 模型和 `KnowledgeBase` 服务，不新建第二套“教师支撑材料表”。

这样做的理由是：

- `documents.debate_id` 已经天然表达“文件属于某场辩论”
- 后端已经有提取文本、生成 embedding、按 `debate_id` 查询的基础逻辑
- 可以避免和管理员知识库 `kb_documents` 混淆

#### 推荐交互：先保存草稿，再上传文件

因为上传文件必须绑定到 `debate_id`，而新建辩论在未保存前还没有真实主键，所以推荐采用：

1. 教师先填写基础信息
2. 先点“保存草稿”
3. 草稿创建成功后，页面保持在当前编辑态
4. 这时才解锁“上传支撑材料”

这是第一阶段最稳的做法。  
不推荐第一版就做“未保存状态下先传临时文件”，因为那会引入临时表、垃圾文件回收、草稿放弃清理等一整套额外复杂度。

### 涉及文件

- `web/src/components/teacher-dashboard.tsx`
- `web/src/services/teacher.service.ts`
- `web/src/lib/debate-description.ts`
- `api/routers/teacher.py`
- `api/services/knowledge_base.py`
- `api/models/document.py`

### 前端详细修改方案

#### 4.5.1 `TeacherDashboard` 交互改造

当前“支撑知识点”区域只有文本框。建议改成“文本 + 文件上传 + 文件列表”的组合区域。

建议在 `teacher-dashboard.tsx` 中新增状态：

```tsx
const [supportDocuments, setSupportDocuments] = useState<TeacherDebateSupportDocument[]>([]);
const [supportDocumentsLoading, setSupportDocumentsLoading] = useState(false);
const [supportUploading, setSupportUploading] = useState(false);
const [deletingSupportDocumentId, setDeletingSupportDocumentId] = useState<string | null>(null);
```

并新增一个隐藏的文件输入框：

```tsx
const supportFileInputRef = useRef<HTMLInputElement>(null);
```

#### 4.5.2 UI 结构建议

在“支撑知识点”文本框下新增一块“支撑材料上传区”，包含：

1. 一个上传按钮
2. 一段说明文案
3. 文件类型 / 大小限制提示
4. 已上传文件列表
5. 每个文件的状态 badge
6. 删除按钮

建议显示状态：

- `pending`
- `processing`
- `completed`
- `failed`

这些状态可以直接复用后端 `Document.embedding_status`。

#### 4.5.3 未保存草稿时的交互

如果当前没有 `editingDebateId`，上传区不要直接可用，而应显示：

- 一个 `Alert`
- 提示“请先保存草稿后再上传支撑材料”
- 一个快捷按钮：`先保存草稿`

这个按钮可以直接调用现有 `handleSubmit('draft')`。

#### 4.5.4 新建草稿后的行为必须调整

当前 `TeacherDashboard` 的 `handleSubmit()` 在新建成功后会调用 `resetDebateEditor()`，这会把表单直接清空。  
这与“保存草稿后继续上传材料”的目标是冲突的。

因此必须修改为：

- 当 `targetStatus === 'draft'` 且是“新建草稿”时：
  - 不要立刻 `resetDebateEditor()`
  - 保留当前表单
  - 设置 `editingDebateId = newDebate.id`
  - 设置 `editingDebateStatus = 'draft'`
  - 保持停留在当前 `new` tab
  - toast 提示“草稿已保存，可继续上传支撑材料”

这是这一功能能否顺畅使用的关键改动。

#### 4.5.5 编辑已有草稿 / 辩论时的行为

当教师点“编辑辩论”进入表单时：

1. 除了加载原有 `topic / rounds / knowledgePoints / student_ids`
2. 还要额外调用一次：

```ts
TeacherService.listDebateSupportDocuments(debateId)
```

并把结果填进 `supportDocuments`。

#### 4.5.6 前端服务层新增接口

在 `web/src/services/teacher.service.ts` 中新增类型：

```ts
export interface TeacherDebateSupportDocument {
  id: string;
  filename: string;
  file_type: string;
  embedding_status: 'pending' | 'processing' | 'completed' | 'failed';
  uploaded_at: string;
}
```

新增方法：

```ts
static async listDebateSupportDocuments(debateId: string): Promise<TeacherDebateSupportDocument[]>
static async uploadDebateSupportDocument(debateId: string, file: File): Promise<TeacherDebateSupportDocument>
static async deleteDebateSupportDocument(debateId: string, documentId: string): Promise<void>
```

如需下载，再加：

```ts
static getDebateSupportDocumentDownloadUrl(debateId: string, documentId: string): string
```

#### 4.5.7 前端校验建议

前端校验建议与后端保持一致：

- 仅支持 `.pdf`、`.docx`
- 文件大小不超过 `10MB`

第一阶段不建议自动把上传文件解析出的内容反写到 `knowledgePoints` 文本框里。  
文本知识点和上传材料先并行存在，后续如要加“自动提取知识点”，再做第二阶段增强。

### 后端详细修改方案

#### 4.5.8 教师路由新增接口

在 `api/routers/teacher.py` 中新增以下接口：

1. 获取某场辩论的支撑材料列表

```text
GET /api/teacher/debates/{debate_id}/support-documents
```

2. 上传某场辩论的支撑材料

```text
POST /api/teacher/debates/{debate_id}/support-documents
Content-Type: multipart/form-data
body: file
```

3. 删除某场辩论的支撑材料

```text
DELETE /api/teacher/debates/{debate_id}/support-documents/{document_id}
```

4. 可选：下载某个支撑材料

```text
GET /api/teacher/debates/{debate_id}/support-documents/{document_id}/download
```

这里建议路由名用 `support-documents`，而不是直接叫 `documents`，这样语义更清楚，也更不容易和报告、回放音频等其他“文件型资源”混淆。

#### 4.5.9 权限校验

每个接口都必须校验：

1. 该 `debate_id` 存在
2. 该辩论属于当前教师
3. 该文档确实属于这个 `debate_id`

推荐封装一个教师侧 helper，例如：

```py
def ensure_teacher_can_access_debate(db: Session, current_user: User, debate_id: str) -> Dict[str, Any]:
```

避免每个路由重复写一遍权限逻辑。

#### 4.5.10 复用 `KnowledgeBase`，但建议拆分上传流程

当前 `KnowledgeBase.upload_document()` 会做：

1. 保存文件
2. 提取文本
3. 生成 embedding
4. 更新状态

这意味着上传请求会同步阻塞到处理完成，教师端表单体验可能比较卡。

因此推荐把 `KnowledgeBase` 拆成两步：

1. `save_document_record(...)`
   - 只负责校验、存文件、写入 `Document`
   - 初始状态设为 `pending`

2. `process_document(document_id)`
   - 后台完成文本提取和 embedding 生成
   - 状态流转为 `processing -> completed / failed`

然后教师上传接口改成：

- 路由里接收文件
- 先创建 `Document`
- 再用 `BackgroundTasks` 异步触发 `process_document(document_id)`

这样能和管理员知识库上传的处理模式保持一致，也能提升教师端交互体验。

#### 4.5.11 数据库层是否需要迁移

第一阶段推荐 **不新增表，不新增迁移**。

原因：

- `documents` 表已经存在
- `debate_id` 已经存在
- `filename / file_path / file_type / content / embedding_status / uploaded_at` 已满足基础需求

如果后续要增强展示，可在第二阶段考虑新增：

- `file_size`
- `uploaded_by`
- `display_order`

但这不是第一阶段必需项。

### 推荐返回结构

列表接口返回示例：

```json
[
  {
    "id": "uuid",
    "filename": "support-material-1.pdf",
    "file_type": "application/pdf",
    "embedding_status": "completed",
    "uploaded_at": "2026-04-28T12:00:00Z"
  }
]
```

上传接口返回示例：

```json
{
  "id": "uuid",
  "filename": "support-material-1.pdf",
  "file_type": "application/pdf",
  "embedding_status": "pending",
  "uploaded_at": "2026-04-28T12:00:00Z"
}
```

### 与当前“支撑知识点”文本框的关系

这一块要特别说明：

- `knowledgePoints` 文本框继续保留
- 上传文件不是替代文本知识点，而是补充支撑材料
- 第一阶段不要求自动抽取文件内容回填文本框

也就是说，最终发布辩论时：

- `description` 仍由 `buildDebateDescription(rounds, knowledgePoints)` 生成
- 支撑文件则通过独立的辩论文档接口单独管理

这样能最大程度减少对现有辩论创建主链路的侵入。

### 验收标准

- 教师在“新建辩论”页保存草稿后，上传区解锁
- 教师可以上传 PDF / DOCX 文件
- 上传后能看到文件列表和状态
- 教师刷新后再次编辑该草稿，仍能看到已上传文件
- 教师可以删除自己辩论下的支撑材料
- 非该辩论所属教师无法访问或删除这些文件
- 发布辩论后，支撑材料仍然保留并继续关联到该辩论

### 风险说明

1. 当前 `KnowledgeBase.upload_document()` 是同步处理，直接复用会让上传接口偏慢
2. `handleSubmit('draft')` 当前会重置表单，这一行为如果不改，上传区无法自然接入
3. 如果未来要让这些支撑材料直接参与赛中检索，还需要再核对使用这些文档的调用链

---

## 4.6 学生知识库文档卡片

**状态：✅ 已完成**

完成标注：

- ~~`student.service.ts` 新增 `downloadKBDocument()`~~
- ~~`student.service.ts` 新增 `getKBDocumentPreviewUrl()`~~
- ~~`student_kb.py` 新增 `GET /api/student/kb/documents/{documentId}/download`~~
- ~~`StudentCommandCenter` 文档卡片取消整卡 `console.log` 点击~~
- ~~文档卡片新增显式 `预览` / `下载` 按钮~~
- ~~PDF 文档可通过新窗口预览，非 PDF 提示使用下载查看~~
- ~~下载失败时通过 toast 给出错误提示~~

### 当前问题

- 学生控制中心文档卡片点击只做 `console.log`
- 学生前端服务只有文档列表接口，没有预览 / 下载接口
- 这一项不是纯前端问题

### 目标状态

文档卡片应支持以下至少一种能力：

1. 在线预览
2. 文件下载
3. 预览与下载同时具备

### 涉及文件

- `web/src/components/student-command-center.tsx`
- `web/src/services/student.service.ts`
- `api/routers/student.py`
- 如有必要：后端文档服务层

### 推荐接口设计

#### 方案 A：最小可用

- `GET /api/student/kb/documents/{documentId}/download`
  - 返回 blob

#### 方案 B：完整可用

- `GET /api/student/kb/documents/{documentId}/preview`
  - 返回可访问的预览 URL 或直接返回流
- `GET /api/student/kb/documents/{documentId}/download`
  - 返回 blob

推荐采用方案 B。

### 前端具体修改方案

1. 在 `student.service.ts` 中新增：

```ts
static async downloadKBDocument(documentId: string): Promise<void>
static getKBDocumentPreviewUrl(documentId: string): string
```

2. `StudentCommandCenter` 中：
   - 不再把整张卡片作为单一 `onClick`
   - 改成显式按钮：
     - `预览`
     - `下载`

3. 对不支持预览的文件类型：
   - `预览` 按钮置灰，或点击后 toast 提示仅支持下载

4. 加入加载态：
   - `downloadingDocumentId`
   - `previewingDocumentId`

### 后端具体修改方案

1. `student.py` 新增学生可访问的文档下载接口
2. 权限校验必须保证：
   - 只能访问学生可见的知识库文档
3. 若用文件流返回，前端按 blob 下载

### 验收标准

- 学生可以真实打开或下载知识库文档
- 权限正确
- 失败时有 toast 提示

### 风险说明

这是前后端联动项，不能只改前端。

---

### 4.6.1 管理员上传知识库后的学生端同步与刷新

**状态：✅ 已完成**

完成标注：

- ~~`DocumentManagement` 增加处理中状态轮询，存在 `pending/processing` 文档时每 5 秒自动刷新~~
- ~~管理员知识库页在页面不可见时暂停轮询~~
- ~~学生知识库列表抽出独立刷新方法 `loadKnowledgeBaseDocuments()`~~
- ~~学生知识库模块新增刷新按钮和最近同步时间~~
- ~~学生端页面 focus / visibilitychange 时自动补拉知识库列表~~
- ~~学生端存在 `pending/processing` 文档时每 8 秒轮询刷新知识库模块~~
- ~~学生知识库卡片显示 `pending/processing/completed/failed` 状态~~
- ~~管理员与学生知识库列表接口增加禁缓存响应头~~

### 当前问题

现在管理员上传知识库文档后，学生端虽然理论上读取的是同一套全局知识库数据，但实际体验并不是“实时同步”：

1. 管理员端上传页当前没有 WebSocket，也没有状态轮询  
2. 学生端 `StudentCommandCenter` 中的知识库列表只在页面初次进入时拉取一次  
3. 管理员上传后，学生端如果不手动刷新页面，通常不会看到最新文档  
4. 即使学生端列表看到了新文档，问答检索也要等文档处理状态变成 `completed` 后才能真正被 RAG 使用

也就是说，当前的问题不是“数据不同步”，而是：

- 前端没有自动刷新机制
- 后端文档处理是异步的，但页面没有把状态变化持续展示出来

### 本节范围

本节只处理：

- 管理员上传全局知识库后，学生端如何看到最新列表和状态
- 管理员端上传页如何自动看到 `pending / processing / completed / failed` 的状态变化

本节 **不处理教师端知识库接入**。

### 目标状态

达到以下体验：

1. 管理员上传后，管理员页能自动看到文档状态从 `pending -> processing -> completed/failed`
2. 学生端进入知识库列表时，能看到最新文档
3. 学生端在页面停留期间，如果存在正在处理的知识库文档，列表可以自动刷新状态
4. 学生端从后台切回前台时，会自动补拉一次最新列表
5. 学生端可以手动点击“刷新知识库”按钮做即时刷新

### 涉及文件

- `web/src/components/admin/document-management.tsx`
- `web/src/components/student-command-center.tsx`
- `web/src/services/admin.service.ts`
- `web/src/services/student.service.ts`
- `api/routers/admin_kb.py`
- `api/routers/student_kb.py`

### 具体修改方案

#### 前端：管理员知识库页自动刷新状态

在 `DocumentManagement` 中新增一套“处理中轮询”机制：

1. 每次 `loadDocuments()` 后检查当前列表中是否存在：
   - `pending`
   - `processing`

2. 如果存在，则启动轮询：
   - 推荐间隔：`5s`
   - 页面不可见时暂停
   - 全部文档进入终态后停止轮询

3. 建议新增状态：

```tsx
const [isPollingDocuments, setIsPollingDocuments] = useState(false);
const pollTimerRef = useRef<number | null>(null);
```

4. 上传成功后：
   - 立即 `loadDocuments()`
   - 如果新文件状态是 `pending`，自动进入轮询

这样管理员不需要手动刷新页面去看文档处理完成没有。

#### 前端：学生知识库列表自动刷新

当前 `StudentCommandCenter` 把知识库数据和其他首页数据绑在一个初始化 `useEffect` 里。建议拆开：

1. 保留首页整体初始化加载
2. 额外抽出一个独立方法：

```tsx
const loadKnowledgeBaseDocuments = async () => { ... }
```

3. 为知识库增加独立状态：

```tsx
const [kbLoading, setKbLoading] = useState(false);
const [kbRefreshing, setKbRefreshing] = useState(false);
const [lastKbSyncAt, setLastKbSyncAt] = useState<string | null>(null);
```

4. 在知识库模块标题区增加：
   - `刷新` 按钮
   - `最近同步时间`

5. 当页面重新获得焦点时，自动调用一次 `loadKnowledgeBaseDocuments()`
   - 监听 `window.focus`
   - 监听 `visibilitychange`

6. 如果学生端拿到的知识库列表里有文档状态是：
   - `pending`
   - `processing`

   则对知识库模块启动短轮询，直到没有处理中项为止。

推荐规则：

- 仅轮询知识库模块，不重拉整个学生首页
- 轮询间隔：`8s`
- 页面隐藏时暂停
- 页面卸载时清理 timer

#### 前端：学生知识库列表与问答状态提示

为减少“看得到但问不到”的困惑，建议在学生知识库模块加一条轻提示：

- 当存在 `pending` 或 `processing` 文档时，显示：
  - “部分知识库文档仍在处理中，智能问答暂时不会使用这些文档”

这样用户能理解为什么新文档已经在列表里，但问答暂时还没命中。

#### 后端：接口缓存策略补强

虽然当前接口本身每次都会查数据库，但为了避免浏览器或中间层缓存带来的旧数据问题，建议在以下接口响应上增加禁缓存头：

- `/api/admin/kb/documents`
- `/api/student/kb/documents`

推荐响应头：

```text
Cache-Control: no-store, no-cache, must-revalidate
Pragma: no-cache
Expires: 0
```

这样能避免上传后用户看到旧列表。

#### 后端：不需要新增 WebSocket

这一项当前**不建议**为了知识库状态同步专门上 WebSocket。

原因：

1. 现在上传处理是后台任务型，不是高频实时事件
2. 前后端目前都没有知识库专用实时通道
3. 用“可见时轮询 + 焦点恢复补拉 + 手动刷新”就足够覆盖这个场景

因此本节推荐的方案是：

- **先用轮询和前台激活刷新解决**
- 暂不把知识库刷新改造成 WebSocket

### 验收标准

- 管理员上传知识库后，管理员页不需要手动刷新即可看到处理状态变化
- 学生重新进入控制中心时能看到最新知识库文档
- 学生停留在控制中心时，如文档仍在处理中，状态能自动刷新到完成或失败
- 学生端可见“处理中提示”，避免误以为问答会立刻用到所有新文档
- 刷新逻辑仅作用于知识库模块，不影响其他首页区域性能

### 风险说明

1. 如果轮询间隔过短，会增加不必要的请求量  
2. 如果轮询和首页整体加载耦合在一起，会让学生首页频繁整页 loading  
3. 如果不补缓存头，某些环境下可能会出现“数据库已更新但列表仍旧”的假象

---

## 4.7 赛后即时分析页分享按钮

**状态：✅ 已完成**

完成标注：

- ~~`handleShareReport` 优先调用 `navigator.share`~~
- ~~不支持系统分享时降级为 `navigator.clipboard.writeText`~~
- ~~分享内容包含辩题、最终得分、对局 ID 和简短总结~~
- ~~分享成功/失败均有 toast 提示~~

### 当前问题

- `handleShareReport` 为空实现
- 用户可以看到分享图标，但无法使用

### 目标状态

分享按钮至少具备一个真实可用的降级链路：

1. 优先系统分享
2. 不支持系统分享时复制摘要文本

### 涉及文件

- `web/src/components/enhanced-debate-analytics.tsx`

### 具体修改方案

1. `handleShareReport` 改为：

```ts
if (navigator.share) {
  await navigator.share({ title, text });
} else {
  await navigator.clipboard.writeText(text);
  toast(...);
}
```

2. 分享内容建议使用：
   - 辩题
   - 最终得分
   - 对局 ID
   - 简短总结

3. 暂不建议做“复制链接”
   - 因为当前项目还没有真正的 URL 路由

### 验收标准

- 点击分享图标会触发系统分享或复制成功提示
- 失败时有错误提示

### 风险说明

低风险。

---

## 4.8 实时辩论页顶部设置 / 全屏 / 音量

**状态：✅ 已完成**

完成标注：

- ~~`DebateArena` 新增 `isSettingsOpen` 并通过顶部设置按钮打开真实设置面板~~
- ~~设置面板仅放真实可控项：AI 语音自动播放开关和流式播放状态~~
- ~~`DebateArena` 新增 `arenaRootRef` / `isFullscreen`~~
- ~~全屏按钮调用浏览器 Fullscreen API 进入 / 退出全屏~~
- ~~监听 `fullscreenchange` 同步全屏状态~~
- ~~`DebateHeader` 新增 `isFullscreen` 并切换全屏图标/提示~~
- ~~`DebateHeader` 新增 `autoPlayEnabled` / `onToggleAutoPlay`~~
- ~~顶部音量按钮切换现有 `autoPlayEnabled`，与底部 `DebateControls` 共用同一状态~~

### 当前问题

- `设置` 只有日志
- `全屏` 只有日志
- `音量` 只有 UI，没有行为

### 目标状态

- `设置` 打开真实设置面板
- `全屏` 调用浏览器 Fullscreen API
- `音量` 与现有自动播放状态绑定

### 涉及文件

- `web/src/components/debate-arena.tsx`
- `web/src/components/debate-header.tsx`
- `web/src/components/debate-controls.tsx`

### 具体修改方案

#### 4.7.1 设置按钮

在 `DebateArena` 中新增状态：

```tsx
const [isSettingsOpen, setIsSettingsOpen] = useState(false);
```

通过 `DebateHeader` 的 `onSettings` 打开 `Dialog`。

建议第一版设置面板只放已经真实可控的项：

- 自动播放开关
- 是否允许自动滚动转录区
- 是否展示额外调试信息（仅开发环境）

不要在第一版面板里继续放假按钮或未来占位项。

#### 4.7.2 全屏按钮

在 `DebateArena` 中新增：

- `arenaRootRef`
- `isFullscreen`

实现方式：

- `arenaRootRef.current?.requestFullscreen()`
- `document.exitFullscreen()`
- 监听 `fullscreenchange` 同步状态

同时 `DebateHeader` 需要新增：

```tsx
isFullscreen?: boolean;
```

用于切换图标或按钮提示。

#### 4.7.3 音量按钮

这里不应该去控制麦克风静音状态，因为：

- 麦克风是输入设备状态
- 顶部音量更像“播放输出 / 自动播报”控制

项目里已经存在现成状态：

- `DebateArena` 的 `autoPlayEnabled`
- `DebateControls` 的 `onAutoPlayEnabledChange`

因此推荐改法是：

1. `DebateHeader` 新增 props：

```tsx
autoPlayEnabled?: boolean;
onToggleAutoPlay?: () => void;
```

2. 顶部音量按钮点击后：
   - 切换 `autoPlayEnabled`

3. `DebateArena` 里把这个状态继续透传给 `DebateControls`

### 验收标准

- 点击设置按钮可以打开真实面板
- 点击全屏按钮会真正进入 / 退出全屏
- 点击音量按钮会切换自动播放状态，并影响转录区音频自动播放

### 风险说明

中等风险，主要在全屏状态同步和辩论页复杂状态共存。

---

## 4.9 `EnhancedDebateAnalytics` 占位页与职责重叠

**状态：✅ 已完成**

完成标注：

- ~~`EnhancedDebateAnalytics` 导航收敛为 `overview` / `history`~~
- ~~删除 `trends` / `comparison` / `achievements` / `teacher` 占位渲染分支~~
- ~~即时分析页聚焦本场报告与历史报告入口~~
- ~~长期成长、对比、成就职责保留在 `StudentAnalyticsCenter`~~

### 当前问题

当前 `EnhancedDebateAnalytics` 中存在：

- `成长趋势`：固定空数组
- `对比分析`：直接空文案
- `成就系统`：直接空文案
- `学生管理`：直接空文案

同时项目里已经有 `StudentAnalyticsCenter`，并且该页面已经真实接入：

- `getGrowthTrend`
- `getAchievements`
- `getClassComparison`

### 目标状态

明确两者职责：

- `EnhancedDebateAnalytics`：本场辩论的即时分析 / 报告容器
- `StudentAnalyticsCenter`：长期成长分析中心

### 涉及文件

- `web/src/components/enhanced-debate-analytics.tsx`
- `web/src/components/student-analytics-center.tsx`
- `web/src/components/app-router.tsx`

### 推荐职责划分

#### `EnhancedDebateAnalytics`

保留：

- `overview`
- `history`
- 导出
- 发送邮件
- 分享

删除或移出：

- `trends`
- `comparison`
- `achievements`
- `teacher` 占位型学生管理视图

#### `StudentAnalyticsCenter`

继续承担：

- `history`
- `growth`
- `comparison`
- `achievements`

### 具体修改方案

1. `EnhancedDebateAnalytics` 精简导航项
2. 删除对应空数据渲染分支
3. 增加从即时分析页进入长期分析中心的入口按钮：
   - 学生：`进入成长分析中心`
   - 教师：可暂不提供，或后续再设计教师长期分析页

### 验收标准

- 不再存在两套职责重叠的分析导航
- `EnhancedDebateAnalytics` 更聚焦“本场分析”
- `StudentAnalyticsCenter` 更聚焦“长期分析”

### 风险说明

中等风险，涉及产品结构调整，但长期收益很高。

---

## 4.10 `TeacherSearchFilter` / `ComparisonMode` / `AchievementBadges`

**状态：✅ 已完成**

完成标注：

- ~~移除 `EnhancedDebateAnalytics` 中未使用的 `TeacherSearchFilter` import~~
- ~~移除 `EnhancedDebateAnalytics` 中未使用的 `ComparisonMode` import~~
- ~~移除 `EnhancedDebateAnalytics` 中未使用的 `AchievementBadges` import~~
- ~~移除随占位分支一起遗留的 `GrowthTrendChart` import~~

### 当前问题

三者都已在 `EnhancedDebateAnalytics` 中 import，但并未渲染。

### 目标状态

根据上一节职责收敛结果处理：

- 若当前不启用，删除 import
- 若未来需要，等真实挂载点确定后再重新接入

### 涉及文件

- `web/src/components/enhanced-debate-analytics.tsx`

### 具体修改方案

1. 移除未使用 import
2. 如果未来要启用：
   - 应接到 `StudentAnalyticsCenter`
   - 或接到未来独立的教师分析页

### 验收标准

- `EnhancedDebateAnalytics` 文件内不再出现导入未使用的高级组件

---

## 4.11 `TeacherDashboard -> 数据分析`

**状态：✅ 已完成**

完成标注：

- ~~从 `TeacherDashboard` 侧边菜单中隐藏 `analytics` 数据分析 tab~~
- ~~保留内部占位实现代码，后续接入真实教师分析能力时再恢复入口~~

### 当前问题

教师控制台里有一个 `数据分析` tab，但目前只显示“暂无分析数据”。

### 目标状态

二选一：

- 短期内隐藏该 tab
- 中期补真实教师分析能力

### 涉及文件

- `web/src/components/teacher-dashboard.tsx`

### 推荐方案

短期先隐藏。

原因：

- 占位页会降低用户信任感
- 当前教师主流程核心是发任务、看分组、看历史、看报告回放
- 数据分析并不是当前刚需链路

### 具体修改方案

1. 从左侧 tab / 菜单数组中移除 `analytics`
2. 保留内部实现代码，后续再接

### 验收标准

- 教师端不再暴露纯占位分析页

---

## 4.12 `EmailConfiguration` 重新挂载

**状态：✅ 已完成**

完成标注：

- ~~恢复 `EmailConfiguration` import~~
- ~~恢复管理员侧边栏“邮件配置”菜单项~~
- ~~恢复邮件配置说明文字~~
- ~~恢复 `activeTab === 'email'` 的实际渲染分支~~

### 当前问题

- 邮件配置组件已存在
- 管理员服务层已存在
- 后端接口已存在
- 但 `AdminDashboard` 中菜单和渲染分支被注释掉

### 目标状态

管理员能直接在控制台使用邮件配置功能。

### 涉及文件

- `web/src/components/admin-dashboard.tsx`
- `web/src/components/admin/email-configuration.tsx`
- `web/src/services/admin.service.ts`

### 具体修改方案

1. 取消 `EmailConfiguration` import 注释
2. 在 `TabType` 中保留 `email`
3. 取消左侧菜单项注释
4. 取消说明文字注释
5. 取消实际渲染分支注释

### 验收标准

- 管理员菜单中能看到邮件配置
- 页面可正常加载、保存、测试连接

### 风险说明

低风险，属于恢复已完成能力。

---

## 4.13 `AppRouter` 迁移到真正的 URL 路由

**状态：⏸️ 暂缓**

暂缓说明：

- 该项需要引入 `react-router-dom`、改造 `App.tsx`、拆分 `AppRouter`，并迁移所有 `setCurrentPage` 导航调用。
- 文档风险说明已明确该项属于结构性改造，不建议与 P0 小修混做。
- 本轮保留为独立后续任务，避免影响当前已完成的主流程修复。

### 当前问题

- 当前页面跳转完全依赖本地状态 `currentPage`
- 无法深链接
- 无法刷新保持页面
- 无法自然分享地址

### 目标状态

迁移到真正的 URL 路由，至少具备：

- 可刷新的页面访问
- 可直接打开报告 / 回放链接
- 可用 query / params 表达 tab 与 back source

### 涉及文件

- `web/package.json`
- `web/src/App.tsx`
- `web/src/components/app-router.tsx`
- 所有依赖 `setCurrentPage` 的组件

### 推荐路由设计

```text
/login
/student/command-center
/student/onboarding
/student/match
/student/debate/:debateId
/student/analytics?tab=history
/student/reports/:debateId
/student/replay/:debateId
/student/preparation
/teacher
/teacher/reports/:debateId
/teacher/replay/:debateId
/admin
```

### 具体修改方案

1. 安装：
   - `react-router-dom`

2. `App.tsx` 改为：
   - `BrowserRouter`
   - `Routes`
   - `Route`

3. `AppRouter` 逐步拆分：
   - 从“状态分发器”变成“路由配置层”

4. 页面参数改为通过 URL 表达：
   - `debateId`
   - `reportBackPage`
   - `replayBackPage`
   - `studentAnalyticsTab`

5. 对需要权限保护的路由，补 `AuthGuard`

### 验收标准

- 刷新报告页不会丢失页面
- 直接访问回放地址可以打开页面
- 学生分析页的 tab 可通过 URL 保持

### 风险说明

这是结构性改造，应该放到单独阶段实施，不建议与 P0 小修混做。

---

## 5. 推荐实施顺序

## 第一阶段：修可见问题

1. `查看全部`
2. 学生准备中心两个按钮
3. 分享按钮
4. 辩论页顶部三按钮
5. 恢复邮件配置

## 第二阶段：做结构收敛

1. 删除 `report-detail`
2. 迁移旧版组件到 `legacy`
3. 精简 `EnhancedDebateAnalytics`
4. 隐藏教师占位分析页
5. 清理未使用高级组件 import

## 第三阶段：做联动与升级

1. 教师端“支撑知识点”文件上传
2. 学生知识库预览 / 下载与自动同步刷新
3. URL 路由迁移

---

## 6. 验收清单

- [x] ~~学生控制中心 `查看全部` 可进入长期分析中心历史页~~
- [x] ~~学生准备中心两个按钮均有真实跳转~~
- [x] ~~教师端“支撑知识点”区域支持按辩论上传 PDF / DOCX 支撑材料~~
- [x] ~~新建草稿保存后仍保留当前编辑态，可继续上传支撑材料~~
- [x] ~~管理员上传知识库后，管理员页能自动看到文档处理状态变化~~
- [x] ~~管理员上传知识库后，学生端知识库列表可通过自动刷新或前台恢复刷新看到最新状态~~
- [x] ~~分享按钮至少支持系统分享或复制摘要~~
- [x] ~~辩论页顶部设置按钮有真实面板~~
- [x] ~~辩论页全屏按钮可真实进入 / 退出全屏~~
- [x] ~~辩论页音量按钮与自动播放状态绑定~~
- [x] ~~管理员邮件配置重新出现在菜单中~~
- [x] ~~`report-detail` 不再作为独立页面入口存在~~
- [x] ~~旧版未接入组件不再混在主流程目录中~~
- [x] ~~`EnhancedDebateAnalytics` 不再承载长期成长分析占位页~~
- [x] ~~学生知识库文档具备真实预览或下载能力~~
- [ ] URL 路由迁移后核心页面可刷新保持

---

## 7. 结论

当前最需要的不是继续补“描述文档”，而是把已经暴露在用户面前的假按钮、空按钮、重复入口先修成真实可用的链路。

从投入产出比来看，最值得先做的是：

1. 补齐学生端无行为按钮
2. 修辩论页顶部控制按钮
3. 恢复管理员邮件配置
4. 为教师端“支撑知识点”补上文件上传链路
5. 收敛分析页职责
6. 最后再做知识库接口与 URL 路由升级

如果后续继续推进开发，建议直接按本文档的三个阶段拆任务，而不是一次性混合改造。
