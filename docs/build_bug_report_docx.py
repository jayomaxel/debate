from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


BASE = Path(__file__).resolve().parent
ASSET_DIR = BASE / "bug-report-assets"
OUT = BASE / "辩论平台_Bug汇总与修复优先级_2026-07-17.docx"

NAVY = RGBColor(15, 30, 54)
BLUE = RGBColor(37, 99, 235)
MUTED = RGBColor(91, 107, 129)
LIGHT = "F2F4F7"
PALE_BLUE = "EEF4FF"
PALE_RED = "FEF2F2"
PALE_GOLD = "FFF7E6"
RED = RGBColor(185, 28, 28)
GOLD = RGBColor(146, 92, 18)
WHITE = RGBColor(255, 255, 255)


def set_font(run, size=10.5, bold=False, color=NAVY, name="Microsoft YaHei"):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Arial")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Arial")
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = color
    return run


def set_cell_shading(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=90, start=120, bottom=90, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for key, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{key}"))
        if node is None:
            node = OxmlElement(f"w:{key}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_widths(table, widths: Iterable[float]):
    table.autofit = False
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = Inches(width)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(int(width * 1440)))
            tc_w.set(qn("w:type"), "dxa")


def border_bottom(paragraph, color="D8DEE9", size="8"):
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)


def paragraph(doc, text="", size=10.5, bold=False, color=NAVY, after=5, before=0, align=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.12
    if align is not None:
        p.alignment = align
    set_font(p.add_run(text), size=size, bold=bold, color=color)
    return p


def bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.25 + level * 0.25)
    p.paragraph_format.first_line_indent = Inches(-0.18)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.12
    set_font(p.add_run(text), size=10.2)
    return p


def heading(doc, text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(6 if level == 1 else 4)
    sizes = {1: 15.5, 2: 12.5, 3: 11}
    run = p.add_run(text)
    set_font(run, size=sizes[level], bold=True, color=BLUE if level < 3 else NAVY)
    return p


def callout(doc, title, body, fill=PALE_BLUE, title_color=BLUE):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_widths(table, [6.5])
    cell = table.cell(0, 0)
    set_cell_shading(cell, fill)
    set_cell_margins(cell, top=150, start=180, bottom=150, end=180)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(4)
    set_font(p.add_run(title), size=11, bold=True, color=title_color)
    p2 = cell.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    p2.paragraph_format.line_spacing = 1.12
    set_font(p2.add_run(body), size=10.2)
    paragraph(doc, "", after=2)


def summary_table(doc):
    rows = [
        ("P0", "8", "报告/AI/安全/实时状态阻断", "修复前不得发布"),
        ("P1", "8", "可靠性、评分可信度、数据口径", "P0 后立即关闭"),
        ("P2", "2", "错误提示、文件治理", "纳入近期迭代"),
    ]
    table = doc.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    headers = ["级别", "数量", "主要影响", "处理要求"]
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        set_cell_shading(cell, LIGHT)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_font(cell.paragraphs[0].add_run(h), size=9.5, bold=True)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for level, count, impact, requirement in rows:
        cells = table.add_row().cells
        vals = [level, count, impact, requirement]
        for i, (cell, val) in enumerate(zip(cells, vals)):
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_font(cell.paragraphs[0].add_run(val), size=9.2, bold=i == 0, color=RED if level == "P0" and i == 0 else NAVY)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i < 2 else WD_ALIGN_PARAGRAPH.LEFT
    set_table_widths(table, [0.7, 0.65, 3.0, 2.15])


def bug_block(doc, bug_id, title, priority, status, symptom, impact, cause, acceptance):
    h = heading(doc, f"{bug_id}  {title}", 2)
    h.paragraph_format.keep_with_next = True
    meta = doc.add_table(rows=1, cols=3)
    meta.style = "Table Grid"
    meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    values = [("优先级", priority), ("状态", status), ("模块", bug_id.split("-")[1] if "-" in bug_id else "")]
    for cell, (label, value) in zip(meta.rows[0].cells, values):
        set_cell_shading(cell, PALE_RED if priority == "P0" else PALE_GOLD if priority == "P1" else LIGHT)
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.add_run(f"{label}："), size=9, bold=True, color=RED if priority == "P0" else GOLD if priority == "P1" else MUTED)
        set_font(p.add_run(value), size=9, bold=True)
    set_table_widths(meta, [2.0, 2.1, 2.4])
    for label, value in (("问题现象", symptom), ("业务影响", impact), ("根因/判断", cause), ("验收标准", acceptance)):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.12
        set_font(p.add_run(f"{label}："), size=10, bold=True, color=BLUE)
        set_font(p.add_run(value), size=10)


def crop_evidence():
    sources = {
        "evidence-vector-dimension.png": ASSET_DIR / "联想截图_20260717184520.png",
        "evidence-report-load.png": ASSET_DIR / "联想截图_20260717184552.png",
    }
    for name, src in sources.items():
        if not src.exists():
            continue
        with Image.open(src).convert("RGB") as im:
            if "vector" in name:
                crop = im.crop((0, 0, im.width, min(im.height, 275)))
            else:
                crop = im
            crop.save(ASSET_DIR / name, optimize=True)


def add_figure(doc, filename, caption):
    path = ASSET_DIR / filename
    if not path.exists():
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(7)
    p.paragraph_format.space_after = Pt(3)
    p.add_run().add_picture(str(path), width=Inches(6.15))
    c = paragraph(doc, caption, size=9, color=MUTED, after=7, align=WD_ALIGN_PARAGRAPH.CENTER)
    c.paragraph_format.keep_with_next = False


def audit_table(doc, rows):
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["编号", "级别", "问题摘要", "建议责任人"]
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        set_cell_shading(cell, LIGHT)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_font(cell.paragraphs[0].add_run(h), size=9.2, bold=True)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for bug_id, level, summary, owner in rows:
        cells = table.add_row().cells
        for i, (cell, value) in enumerate(zip(cells, [bug_id, level, summary, owner])):
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_font(cell.paragraphs[0].add_run(value), size=8.8, bold=i < 2, color=RED if level == "P0" and i == 1 else NAVY)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i in (0, 1, 3) else WD_ALIGN_PARAGRAPH.LEFT
    set_table_widths(table, [1.12, 0.52, 3.86, 1.0])
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))


def build():
    crop_evidence()
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.72)
    section.left_margin = Inches(0.82)
    section.right_margin = Inches(0.82)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)

    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = NAVY
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.12

    for level, size in ((1, 15.5), (2, 12.5), (3, 11)):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = BLUE if level < 3 else NAVY

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_font(header.add_run("碳硅之辩｜缺陷与风险报告"), size=8.5, bold=True, color=MUTED)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_font(footer.add_run("内部交付材料｜2026-07-17"), size=8, color=MUTED)

    paragraph(doc, "技术质量报告", size=10, bold=True, color=BLUE, after=4)
    title = paragraph(doc, "辩论平台 Bug 汇总与修复优先级", size=24, bold=True, color=NAVY, after=6)
    subtitle = paragraph(doc, "基于端到端测试截图与当前代码静态审计", size=12.5, color=MUTED, after=12)
    meta = doc.add_table(rows=4, cols=2)
    meta.style = "Table Grid"
    meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_rows = [
        ("报告日期", "2026-07-17"),
        ("代码基线", "main / d6fb6c5e（本地工作区含未提交修改）"),
        ("证据来源", "需求方端到端截图、运行现象、代码审计"),
        ("交付结论", "当前版本不具备稳定交付条件，应先关闭 P0 阻断项"),
    ]
    for row, (label, value) in zip(meta.rows, meta_rows):
        set_cell_shading(row.cells[0], LIGHT)
        for cell in row.cells:
            set_cell_margins(cell, top=100, bottom=100)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_font(row.cells[0].paragraphs[0].add_run(label), size=9.5, bold=True)
        set_font(row.cells[1].paragraphs[0].add_run(value), size=9.5, bold=label == "交付结论", color=RED if label == "交付结论" else NAVY)
    set_table_widths(meta, [1.25, 5.25])
    paragraph(doc, "", after=2)
    callout(doc, "管理层结论", "本轮共整理 18 项缺陷/风险：P0 级 8 项、P1 级 8 项、P2 级 2 项。报告读取、PDF 导出和备赛助手已在真实界面复现失败。单元测试通过不等于端到端链路可用。", fill=PALE_RED, title_color=RED)

    heading(doc, "1. 缺陷总览", 1)
    summary_table(doc)
    paragraph(doc, "核心链路风险：辩论结束 → 进程内后台评分 → 报告数据 → Markdown → PDF。任一环节失败都会造成“辩论已结束但报告不可用”，而当前前端只显示裸 500。", size=10.3, after=7)

    heading(doc, "2. 需求方已复现问题", 1)
    bug_block(doc, "BUG-UI-001", "右上角用户卡片与校验提示重叠", "P1", "已复现（附件图1）", "教师端创建辩论页面右上角，用户信息卡片与“请输入辩论主题”等提示重叠。", "提示不可读，在不同分辨率/缩放比例下可能遮挡操作入口。", "高概率为固定定位元素共用右上角锚点，z-index、安全间距和响应式断点未统一。", "1280/1440/1920 宽度及 100%/125% 缩放下无重叠，提示完整可读。")
    bug_block(doc, "BUG-RPT-001", "完整报告/PDF 导出返回 500", "P0", "已复现（附件图2、图3）", "点击“下载完整报告/导出 PDF”后提示导出失败，HTTP 500。", "核心交付物无法归档、下载或提交。", "导出依赖评分、报告、Markdown、PDF 渲染和文件缓存。确切失败点需结合容器日志确认；重点排查空 Markdown、渲染器依赖、目录权限和缓存哈希不一致。", "同一已完成辩论连续导出 3 次均返回 200；文件可打开且内容一致；缓存命中正确；失败返回结构化错误码。")
    bug_block(doc, "BUG-RAG-001", "备赛区 AI 助手向量维度不一致", "P0", "已复现（证据图 A）", "问答时报“期望1536，实际1024”，机器人回复为空。", "知识库检索和备赛问答不可用。", "嵌入模型输出维度、配置维度和数据库向量列维度不一致。", "启动预检三者一致；完成向量列迁移与全量重建；新旧文档均可检索，连续 20 次问答无空回复。")
    add_figure(doc, "evidence-vector-dimension.png", "证据图 A｜备赛区提示“查询嵌入向量维度错误：期望1536，实际1024”")
    bug_block(doc, "BUG-RPT-002", "分析报告读取/生成失败", "P0", "已复现（证据图 B、附件图5）", "打开已完成辩论的分析报告后返回 500，页面显示“报告加载失败”。", "复盘、能力分析、教师反馈与成长数据无法使用。", "与 PDF 导出共享评分/报告前置链路，但读取接口不应依赖 PDF；应独立排查评分缺失、报告生成异常和数据库数据状态。", "报告状态可追踪；ready 时稳定返回 200；failed 时提供错误码和可重试入口。")
    add_figure(doc, "evidence-report-load.png", "证据图 B｜报告读取返回 500，页面无法加载")

    heading(doc, "3. 代码审计发现的问题", 1)
    paragraph(doc, "以下问题来自当前工作区静态审计。P0 为发布阻断；P1 为核心稳定性/可信度问题；P2 为治理和体验问题。", size=10.2)
    rows = [
        ("BUG-SEC-001", "P0", "多组密钥/密码曾明文暴露，必须全部轮换", "后端/运维"),
        ("BUG-CFG-001", "P0", "数据库旧 AI 配置可能覆盖环境变量新值，且存在缓存", "后端"),
        ("BUG-RT-001", "P0", "抢麦异常分支静默返回，检查与占用不是原子操作", "后端"),
        ("BUG-RT-002", "P0", "实时房间状态主要在单进程内存，多实例/重启会失真", "后端/运维"),
        ("BUG-TASK-001", "P0", "评分/报告使用进程内 create_task，失败不可恢复", "后端/运维"),
        ("BUG-RPT-003", "P0", "辩论结束与评分/报告就绪状态混用", "后端/前端"),
        ("BUG-UPL-001", "P0", "上传目录静态暴露，缺少对象级下载授权", "后端"),
        ("BUG-AI-001", "P0", "语音→人类文本→AI回应全链路缺少生产健康门禁", "后端/测试"),
        ("BUG-SCORE-001", "P1", "批量评分以字数/关键词启发式为主，不是语义评分", "算法/后端"),
        ("BUG-SCORE-002", "P1", "模型异常仍落库固定70分，故障被伪装为正常分", "后端"),
        ("BUG-SCORE-003", "P1", "评分缺少来源、量表版本、证据与回退标识", "算法/后端"),
        ("BUG-ANL-001", "P1", "班级平均按评分行加权，与学生等权平均不一致", "后端/产品"),
        ("BUG-ANL-002", "P1", "领先百分位命名与公式容易误导", "产品/前端"),
        ("BUG-DATA-001", "P1", "演示/种子数据可能污染能力图和班级排行", "后端/数据"),
        ("BUG-JDG-001", "P1", "裁判JSON二次修复失败路径存在异常变量作用域风险", "后端"),
        ("BUG-TST-001", "P1", "测试多为局部/mock，未覆盖真实端到端链路", "测试/全栈"),
        ("BUG-UX-001", "P2", "前端直接展示Axios英文500，无请求编号", "前端/后端"),
        ("BUG-FILE-001", "P2", "报告文件路径可预测且依赖本地文件系统", "后端/运维"),
    ]
    audit_table(doc, rows)

    heading(doc, "4. 关键技术证据", 1)
    evidence = [
        ("AI 配置注入", "ConfigService 优先返回缓存/数据库第一条模型配置；只有数据库无记录时才用环境变量创建默认配置。"),
        ("向量维度", "DocumentService 对查询向量按配置维度校验；当前运行时已复现 1536 与 1024 不一致。"),
        ("后台任务", "辩论结束后用 asyncio.create_task 启动评分/报告；异常只写日志，finally 仍广播 debate_ended。"),
        ("实时状态", "DebateRoomManager.rooms 为进程内字典；仅候场清单等部分元数据持久化。"),
        ("抢麦", "grab_mic 在房间/角色缺失时直接返回；占用检查和状态更新之间没有可见的原子锁。"),
        ("文件访问", "UploadGuard 负责上传校验，但整个上传目录仍通过 /uploads 静态挂载。"),
        ("评分来源", "batch_score_debate 使用字数、关键词、阶段和标记词计算五维分数；单条评分异常会落库固定70分。"),
        ("班级平均", "学生排名先按学生聚合；班级平均直接对全部 Score 行求均值，发言更多者权重更高。"),
    ]
    for label, text in evidence:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.12
        set_font(p.add_run(f"{label}｜"), size=10, bold=True, color=BLUE)
        set_font(p.add_run(text), size=10)

    heading(doc, "5. 推荐修复顺序", 1)
    phases = [
        ("第一批｜当天止血", "轮换全部已暴露凭据；收口配置来源；完成模型/语音/向量启动预检；修复向量维度并重建索引。"),
        ("第二批｜恢复核心闭环", "报告/评分/导出拆分状态；后台任务持久化和重试；修复报告 GET 与 PDF 500；跑通真实人类发言到 AI 回应。"),
        ("第三批｜实时可靠性", "统一录音/抢麦协议；房间级锁与状态版本；共享状态和重启恢复；上传下载改鉴权路由。"),
        ("第四批｜分析可信度", "标记评分来源和回退；补量表/证据字段；隔离演示数据；统一班级平均和百分位口径。"),
        ("第五批｜UI与门禁", "修复右上角重叠；统一结构化错误；建立从注册到报告导出的 E2E 发布门禁。"),
    ]
    for title_text, body in phases:
        callout(doc, title_text, body, fill=PALE_BLUE if "第一" not in title_text else PALE_RED, title_color=BLUE if "第一" not in title_text else RED)

    heading(doc, "6. 发布验收清单", 1)
    checks = [
        "所有已暴露凭据均已吊销并轮换，仓库/压缩包/日志中无真实密钥。",
        "启动健康页显示脱敏后的最终配置来源、模型名、向量维度及外部服务状态。",
        "备赛助手连续20次问答无空白回复、无维度错误。",
        "人类语音能转写，AI能引用人类刚才观点进行针对性回应。",
        "两客户端并发抢麦仅一个成功，失败方立即收到带请求编号的明确结果。",
        "API重启后关键房间状态可恢复，不能跳阶段或丢失当前发言人。",
        "评分/报告任务状态可追踪、可幂等重试、不重复写分。",
        "报告GET稳定200；PDF连续导出3次成功，文件可打开且缓存正确。",
        "不同学生无法通过猜URL下载他人材料或报告。",
        "能力图只统计正式有效且非回退评分，并显示样本量、统计周期和评分来源。",
        "1280/1440/1920宽度及100%/125%缩放下顶部控件无重叠。",
    ]
    for item in checks:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.left_indent = Inches(0.28)
        p.paragraph_format.first_line_indent = Inches(-0.18)
        p.paragraph_format.space_after = Pt(4)
        set_font(p.add_run("□  " + item), size=10.1)

    heading(doc, "7. 工期与责任人建议", 1)
    owner_rows = [
        ("密钥轮换与配置收口", "后端/运维", "0.5–1天", "第三方控制台权限"),
        ("向量维度迁移与重建", "后端/数据", "1–2天", "嵌入模型冻结"),
        ("报告读取与PDF导出", "后端", "2–4天", "模型/渲染器/存储可用"),
        ("后台任务持久化", "后端/运维", "2–4天", "任务队列方案"),
        ("实时状态与并发锁", "后端", "3–5天", "共享状态方案"),
        ("上传下载鉴权", "后端/前端", "1–3天", "文件存储方案"),
        ("AI全链路E2E", "后端/测试", "2–3天", "测试账号与额度"),
        ("评分与能力图治理", "算法/后端/产品", "3–6天", "评分量表冻结"),
        ("页面重叠与错误提示", "前端", "0.5–1.5天", "统一错误合同"),
    ]
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(["模块", "责任人", "工作量", "前置依赖"]):
        set_cell_shading(table.rows[0].cells[i], LIGHT)
        set_cell_margins(table.rows[0].cells[i])
        set_font(table.rows[0].cells[i].paragraphs[0].add_run(h), size=9.2, bold=True)
        table.rows[0].cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for vals in owner_rows:
        cells = table.add_row().cells
        for i, (cell, val) in enumerate(zip(cells, vals)):
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_font(cell.paragraphs[0].add_run(val), size=8.8)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i in (1, 2) else WD_ALIGN_PARAGRAPH.LEFT
    set_table_widths(table, [2.0, 1.15, 1.0, 2.35])

    heading(doc, "8. 证据说明与限制", 1)
    bullet(doc, "截图现象来自需求方2026-07-17端到端测试；原始图1—图5应与本报告一并归档。")
    bullet(doc, "向量维度问题已获得明确错误信息；报告读取/导出500的最终根因仍需结合API容器日志、数据库报告状态和文件权限确认。")
    bullet(doc, "本报告未修改业务代码，仅整理缺陷、风险、优先级和验收标准。")
    bullet(doc, "代码基线存在未提交修改，正式修复前应冻结版本并记录部署对应的commit或镜像digest。")

    doc.core_properties.title = "辩论平台 Bug 汇总与修复优先级报告"
    doc.core_properties.subject = "端到端缺陷、代码审计风险与修复优先级"
    doc.core_properties.author = "项目质量审计"
    doc.core_properties.keywords = "辩论平台,Bug,P0,报告导出,AI,向量维度"
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
