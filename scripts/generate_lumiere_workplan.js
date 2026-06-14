const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  Table,
  TableRow,
  TableCell,
  AlignmentType,
  HeadingLevel,
  LevelFormat,
  BorderStyle,
  WidthType,
  ShadingType,
  VerticalAlign,
} = require("docx");
const fs = require("fs");
const path = require("path");

const BLUE = "1E4D8C";
const LIGHT_BLUE = "D6E4F7";
const MID_BLUE = "4A7FC1";
const GREY_BG = "F5F6F8";
const BORDER_COLOR = "C5D5EA";

const border = { style: BorderStyle.SINGLE, size: 1, color: BORDER_COLOR };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = {
  top: noBorder,
  bottom: noBorder,
  left: noBorder,
  right: noBorder,
};

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 160 },
    children: [new TextRun({ text, bold: true, size: 32, color: BLUE, font: "Arial" })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 120 },
    children: [new TextRun({ text, bold: true, size: 26, color: MID_BLUE, font: "Arial" })],
  });
}

function h3(text) {
  return new Paragraph({
    spacing: { before: 200, after: 80 },
    children: [new TextRun({ text, bold: true, size: 23, color: "333333", font: "Arial" })],
  });
}

function body(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    children: [new TextRun({ text, size: 22, font: "Arial", color: "333333", ...opts })],
  });
}

function bullet(text, boldPrefix = null) {
  const children = [];
  if (boldPrefix) {
    children.push(
      new TextRun({
        text: `${boldPrefix} `,
        bold: true,
        size: 22,
        font: "Arial",
        color: "333333",
      }),
    );
    children.push(new TextRun({ text, size: 22, font: "Arial", color: "333333" }));
  } else {
    children.push(new TextRun({ text, size: 22, font: "Arial", color: "333333" }));
  }
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { before: 40, after: 40 },
    children,
  });
}

function subbullet(text) {
  return new Paragraph({
    numbering: { reference: "subbullets", level: 0 },
    spacing: { before: 30, after: 30 },
    children: [new TextRun({ text, size: 21, font: "Arial", color: "555555" })],
  });
}

function spacer(size = 120) {
  return new Paragraph({
    spacing: { before: size, after: 0 },
    children: [new TextRun("")],
  });
}

function divider() {
  return new Paragraph({
    spacing: { before: 160, after: 160 },
    border: {
      bottom: { style: BorderStyle.SINGLE, size: 4, color: BORDER_COLOR },
    },
    children: [new TextRun("")],
  });
}

function infoBox(lines) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            borders,
            shading: { fill: GREY_BG, type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 200, right: 200 },
            width: { size: 9360, type: WidthType.DXA },
            children: lines.map(
              (line) =>
                new Paragraph({
                  spacing: { before: 40, after: 40 },
                  children: [
                    new TextRun({ text: line, size: 21, font: "Arial", color: "444444" }),
                  ],
                }),
            ),
          }),
        ],
      }),
    ],
  });
}

function statusTable(rows) {
  const headerCell = (text, width) =>
    new TableCell({
      borders,
      shading: { fill: BLUE, type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      width: { size: width, type: WidthType.DXA },
      children: [
        new Paragraph({
          children: [new TextRun({ text, bold: true, size: 21, color: "FFFFFF", font: "Arial" })],
        }),
      ],
    });

  const headerRow = new TableRow({
    children: [
      headerCell("任务模块", 2400),
      headerCell("具体内容", 4200),
      headerCell("优先级", 1560),
      headerCell("状态", 1200),
    ],
  });

  const dataRows = rows.map(([module, content, priority, status], i) => {
    const fill = i % 2 === 0 ? "FFFFFF" : GREY_BG;
    const priorityColor =
      priority === "🔴 高" ? "C0392B" : priority === "🟡 中" ? "D68910" : "27AE60";

    return new TableRow({
      children: [
        new TableCell({
          borders,
          shading: { fill, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          width: { size: 2400, type: WidthType.DXA },
          children: [
            new Paragraph({
              children: [new TextRun({ text: module, bold: true, size: 20, font: "Arial", color: "222222" })],
            }),
          ],
        }),
        new TableCell({
          borders,
          shading: { fill, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          width: { size: 4200, type: WidthType.DXA },
          children: [
            new Paragraph({
              children: [new TextRun({ text: content, size: 20, font: "Arial", color: "444444" })],
            }),
          ],
        }),
        new TableCell({
          borders,
          shading: { fill, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          width: { size: 1560, type: WidthType.DXA },
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [new TextRun({ text: priority, size: 20, font: "Arial", color: priorityColor, bold: true })],
            }),
          ],
        }),
        new TableCell({
          borders,
          shading: { fill, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          width: { size: 1200, type: WidthType.DXA },
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [new TextRun({ text: status, size: 20, font: "Arial", color: "666666" })],
            }),
          ],
        }),
      ],
    });
  });

  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2400, 4200, 1560, 1200],
    rows: [headerRow, ...dataRows],
  });
}

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 480, hanging: 240 } } },
          },
        ],
      },
      {
        reference: "subbullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "–",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 800, hanging: 240 } } },
          },
        ],
      },
      {
        reference: "numbers",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 480, hanging: 300 } } },
          },
        ],
      },
    ],
  },
  styles: {
    default: {
      document: {
        run: { font: "Arial", size: 22 },
      },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: BLUE },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: MID_BLUE },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      children: [
        spacer(400),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 80 },
          children: [new TextRun({ text: "Lumiere Australia", size: 52, bold: true, color: BLUE, font: "Arial" })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 200 },
          children: [new TextRun({ text: "运营工作体系 · 1-2个月执行计划", size: 30, color: MID_BLUE, font: "Arial" })],
        }),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [3120, 3120, 3120],
          rows: [
            new TableRow({
              children: [
                new TableCell({
                  borders: noBorders,
                  shading: { fill: LIGHT_BLUE, type: ShadingType.CLEAR },
                  margins: { top: 120, bottom: 120, left: 120, right: 120 },
                  width: { size: 3120, type: WidthType.DXA },
                  children: [
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      children: [new TextRun({ text: "执行人", size: 20, color: "666666", font: "Arial" })],
                    }),
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      children: [new TextRun({ text: "运营实习生（独立执行）", bold: true, size: 22, color: BLUE, font: "Arial" })],
                    }),
                  ],
                }),
                new TableCell({
                  borders: noBorders,
                  shading: { fill: LIGHT_BLUE, type: ShadingType.CLEAR },
                  margins: { top: 120, bottom: 120, left: 120, right: 120 },
                  width: { size: 3120, type: WidthType.DXA },
                  children: [
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      children: [new TextRun({ text: "核心目标", size: 20, color: "666666", font: "Arial" })],
                    }),
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      children: [new TextRun({ text: "次账号0→1 + 主账号持续运营", bold: true, size: 22, color: BLUE, font: "Arial" })],
                    }),
                  ],
                }),
                new TableCell({
                  borders: noBorders,
                  shading: { fill: LIGHT_BLUE, type: ShadingType.CLEAR },
                  margins: { top: 120, bottom: 120, left: 120, right: 120 },
                  width: { size: 3120, type: WidthType.DXA },
                  children: [
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      children: [new TextRun({ text: "变现漏斗", size: 20, color: "666666", font: "Arial" })],
                    }),
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      children: [new TextRun({ text: "课件引流 → 咨询转化", bold: true, size: 22, color: BLUE, font: "Arial" })],
                    }),
                  ],
                }),
              ],
            }),
          ],
        }),
        spacer(200),
        divider(),
        h1("一、整体业务逻辑与账号定位"),
        body("在开始所有执行之前，需要先厘清这两个账号在整体变现漏斗中各自的角色，避免做了大量内容却没有方向感。"),
        spacer(80),
        h3("变现漏斗全链路"),
        infoBox([
          "【内容曝光】主账号（小红书图文+视频）· 次账号（小红书橱窗）",
          "       ↓",
          "【兴趣筛选】品牌自测产品（1元） · 低价引流课件（29.9-49.9）",
          "       ↓",
          "【深度转化】高价课件（199-299）· 咨询Call（500-600/h）",
          "       ↓",
          "【长期服务】品牌长期孵化（年度合作）",
        ]),
        spacer(80),
        h3("两个账号的分工"),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [1600, 3880, 3880],
          rows: [
            new TableRow({
              children: [
                new TableCell({
                  borders,
                  shading: { fill: BLUE, type: ShadingType.CLEAR },
                  margins: { top: 80, bottom: 80, left: 120, right: 120 },
                  width: { size: 1600, type: WidthType.DXA },
                  children: [new Paragraph({ children: [new TextRun({ text: "", size: 20, font: "Arial" })] })],
                }),
                new TableCell({
                  borders,
                  shading: { fill: BLUE, type: ShadingType.CLEAR },
                  margins: { top: 80, bottom: 80, left: 120, right: 120 },
                  width: { size: 3880, type: WidthType.DXA },
                  children: [
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      children: [new TextRun({ text: "主账号 · Lumiere Australia", bold: true, size: 21, color: "FFFFFF", font: "Arial" })],
                    }),
                  ],
                }),
                new TableCell({
                  borders,
                  shading: { fill: BLUE, type: ShadingType.CLEAR },
                  margins: { top: 80, bottom: 80, left: 120, right: 120 },
                  width: { size: 3880, type: WidthType.DXA },
                  children: [
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      children: [new TextRun({ text: "次账号 · 小红书橱窗", bold: true, size: 21, color: "FFFFFF", font: "Arial" })],
                    }),
                  ],
                }),
              ],
            }),
            ...[
              ["平台", "小红书（已有2k+粉丝）", "小红书（从0新建）"],
              ["内容方向", "方法论/商业判断/行业洞察（What & Why）", "课件产品挂链接 + 商品引流转化"],
              ["核心作用", "品牌曝光 + 专业度建立 + 吸引潜在客户", "直接变现 + 客户资产沉淀"],
              ["内容形式", "图文为主 + 视频（系列化）", "产品主图/介绍内容 + 引导私信"],
              ["转化路径", "评论/私信 → 咨询Call / 高价课件", "橱窗购买 → 低价课件 → 升级咨询"],
            ].map(([label, left, right], i) => {
              const fill = i % 2 === 0 ? GREY_BG : "FFFFFF";
              return new TableRow({
                children: [
                  new TableCell({
                    borders,
                    shading: { fill, type: ShadingType.CLEAR },
                    margins: { top: 80, bottom: 80, left: 120, right: 120 },
                    width: { size: 1600, type: WidthType.DXA },
                    children: [new Paragraph({ children: [new TextRun({ text: label, bold: true, size: 20, font: "Arial", color: "333333" })] })],
                  }),
                  new TableCell({
                    borders,
                    shading: { fill, type: ShadingType.CLEAR },
                    margins: { top: 80, bottom: 80, left: 120, right: 120 },
                    width: { size: 3880, type: WidthType.DXA },
                    children: [new Paragraph({ children: [new TextRun({ text: left, size: 20, font: "Arial", color: "444444" })] })],
                  }),
                  new TableCell({
                    borders,
                    shading: { fill, type: ShadingType.CLEAR },
                    margins: { top: 80, bottom: 80, left: 120, right: 120 },
                    width: { size: 3880, type: WidthType.DXA },
                    children: [new Paragraph({ children: [new TextRun({ text: right, size: 20, font: "Arial", color: "444444" })] })],
                  }),
                ],
              });
            }),
          ],
        }),
        spacer(100),
        divider(),
        h1("二、执行阶段拆解"),
        h2("第一阶段（第1-2周）：调研分析 & 框架搭建"),
        body("这是整个计划的地基。不要急于出内容，先把账号框架、选题逻辑、产品方向想清楚，后续所有执行才有依据。"),
        spacer(60),
        h3("1.1 竞品/参考账号分析（Mentor发来的参考账号）"),
        bullet("系统分析3个品牌咨询类账号的视觉风格、内容结构、爆款选题逻辑"),
        bullet("重点提炼：这些账号在讲What & Why，而不是在教How——记录它们的切入角度"),
        bullet("分析维度：账号定位 / 内容形式分布（图文:视频） / 爆款笔记特征 / 评论区高频问题"),
        bullet("输出物：一份竞品分析表（可直接作为次账号框架搭建的参考依据）"),
        spacer(60),
        h3("1.2 次账号框架搭建（基于1.1的分析结果）"),
        bullet("确定账号名称、简介、头像风格方向"),
        bullet("确定内容矩阵：橱窗课件主图风格 / 引流笔记内容方向 / 选题框架"),
        bullet("确定账号主页视觉调性（参考主账号风格保持一致性，建立品牌关联感）"),
        bullet("输出物：次账号完整框架文档（账号定位 / 内容框架 / 视觉规范 / 发布节奏）"),
        spacer(60),
        h3("1.3 主账号内容方向梳理"),
        bullet("回顾主账号已有40篇内容，整理出高赞（200+）内容的共同特征"),
        bullet("结合公司定位（What & Why导向），确定未来1-2个月的选题库（建议储备10-15个题目）"),
        bullet("选题原则：能体现商业判断力 / 对目标客户（初创品牌方）有决策参考价值 / 与咨询服务形成关联"),
        spacer(60),
        h3("1.4 YouTube参考内容研究（视频系列方向）"),
        bullet("筛选YouTube上已验证的、与品牌出海/初创相关的内容方向"),
        bullet("提炼可迁移的选题逻辑（不是搬运，是以此为选题灵感基础）"),
        bullet("为每个视频系列准备：内容脚本框架 + 画面脚本框架（两份独立脚本）"),
        spacer(60),
        divider(),
        h2("第二阶段（第3-4周）：课件产品 & 品牌自测产品开发"),
        body("先把产品开发出来，橱窗才有东西可卖。低价引流课件是次账号冷启动的核心钩子，不能拖。"),
        spacer(60),
        h3("2.1 低价引流课件（29.9-49.9元）"),
        bullet("选题建议方向（可从中选1-2个作为首批）："),
        subbullet("「澳洲品牌冷启动避坑指南」——针对初创品牌方最高频踩坑"),
        subbullet("「出海澳洲前，你必须想清楚的5个问题」——决策前置型选题"),
        subbullet("「小众品牌如何找到第一批精准客户」——冷启动核心问题"),
        bullet("课件制作要求：结构清晰、有框架感、体现方法论，不要流水账"),
        bullet("注意：低价课件是筛客器，内容质量决定后续高价转化率；宁可少而精"),
        bullet("上架小红书橱窗，配套写1-2篇引流笔记"),
        spacer(60),
        h3("2.2 高价课件（199-299元）"),
        bullet("内容来源：从公司已有咨询Call记录中，提炼真实建议和会议思考"),
        bullet("定位：面向已有一定认知基础的品牌方，内容深度是低价课件的3-5倍"),
        bullet("制作节奏：不急于第一个月上架，可以在第二个月完成；先把低价课件跑通"),
        bullet("高价课件不挂橱窗链接，通过主账号内容引导私信咨询"),
        spacer(60),
        h3("2.3 品牌自测产品（搭建阶段）"),
        bullet("核心逻辑：用低门槛测试（1元）筛选有潜力的品牌客户，同时收集品牌信息建立数据库"),
        bullet("功能需求拆解："),
        subbullet("测试题目设计（反映品牌定位/市场潜力/创始人认知的维度）"),
        subbullet("逻辑分支设计：测试结果与测题之间的逻辑对应"),
        subbullet("结果输出页面：给用户一个有参考价值的品牌诊断报告（不是随机结果）"),
        subbullet("后台数据库：记录用户填写的品牌信息 + 联系方式"),
        subbullet("网站部署（需要技术支持确认）"),
        bullet("分发形式三选一（待决策）："),
        subbullet("方案A · 1元收费：通过小红书引导付款，适合直接变现，但操作链路较长"),
        subbullet("方案B · 评论区链接：零门槛，适合快速引流，但客户筛选质量较低"),
        subbullet("方案C · 私信获取链接：需要互动，天然筛选了愿意主动沟通的客户，推荐优先考虑"),
        bullet("决策建议：先确定分发形式，再开发，避免后期改动影响数据库逻辑"),
        spacer(60),
        divider(),
        h2("第三阶段（第3-8周，持续进行）：内容持续生产"),
        body("内容是账号的生命线，需要在框架搭建完成后立刻进入持续生产节奏。建议主账号图文和视频并行推进，不要互相等待。"),
        spacer(60),
        h3("3.1 主账号图文内容"),
        bullet("建议发布节奏：每周2-3篇图文（可根据实际精力调整，但不建议低于每周1篇）"),
        bullet("选题来自1.3中整理的选题库，优先发「What & Why」类深度内容"),
        bullet("图文制作流程：选题确认 → 核心观点提炼 → 配图/排版 → 发布"),
        bullet("每篇发布后：记录数据（点赞/收藏/评论），评估哪类选题反响更好，动态调整选题库"),
        spacer(60),
        h3("3.2 主账号视频内容（系列化）"),
        bullet("视频形式：口播为主 + 画面配合（参考YouTube已验证内容的结构）"),
        bullet("每个视频需要两份脚本：①内容脚本（说什么）②画面脚本（配什么画面/字幕）"),
        bullet("制作流程：内容脚本（你写）→ 画面脚本（你写）→ 剪辑（外包）→ 审核 → 发布"),
        bullet("建议第一个月先出1-2个视频，验证内容方向，再批量生产"),
        bullet("视频选题优先与已有高赞图文关联，降低从0验证的风险"),
        spacer(60),
        h3("3.3 次账号内容（橱窗引流）"),
        bullet("在课件上架后开始发布，不要提前开号发空内容"),
        bullet("每周1-2篇引流笔记，直接指向橱窗产品"),
        bullet("内容逻辑：用一个具体痛点/场景 → 引出课件能解决的问题 → 引导进橱窗"),
        bullet("不要在次账号发方法论内容，那是主账号的事；次账号聚焦「这个产品能帮你解决什么」"),
        spacer(60),
        divider(),
        h1("三、任务优先级总览"),
        body("按照执行紧急程度排列，红色代表必须先做，否则后续工作无法展开。"),
        spacer(80),
        statusTable([
          ["竞品分析", "分析Mentor参考账号 + 输出分析报告", "🔴 高", "待开始"],
          ["次账号框架", "基于竞品分析搭建账号定位/内容框架", "🔴 高", "待开始"],
          ["主账号选题库", "整理高赞内容规律 + 储备10-15个选题", "🔴 高", "待开始"],
          ["低价课件开发", "完成1-2个引流课件并上架橱窗", "🔴 高", "待开始"],
          ["品牌自测·决策", "确定分发形式（三选一）", "🟡 中", "待决策"],
          ["主账号图文", "按节奏持续发布（每周2-3篇）", "🟡 中", "持续进行"],
          ["视频脚本", "内容脚本+画面脚本（系列化）", "🟡 中", "待开始"],
          ["品牌自测·搭建", "题目设计+逻辑+数据库+部署", "🟡 中", "待开始"],
          ["高价课件开发", "从咨询记录提炼，第2个月完成", "🟢 低", "待开始"],
          ["咨询Call链接", "确认挂链接的形式与位置", "🟢 低", "待确认"],
        ]),
        spacer(100),
        divider(),
        h1("四、执行注意事项"),
        spacer(40),
        h3("关于内容方向"),
        bullet("始终坚持 What & Why 原则：内容的价值在于帮客户做商业判断，而不是教具体操作方法"),
        bullet("账号是吸引和转化客户的工具，不是课程平台；内容要让人「看完想咨询」，而不是「看完学会了」"),
        bullet("聚焦小而美、有调性的初创品牌——内容选题和案例要与目标客户画像保持一致"),
        spacer(60),
        h3("关于节奏管理"),
        bullet("作为独立执行的实习生，精力有限；优先把关键动作做深，不要贪多"),
        bullet("视频脚本写完后立刻交剪辑，不要因为等剪辑而卡住其他工作"),
        bullet("图文和视频不要互相等待，可以并行推进"),
        spacer(60),
        h3("关于品牌自测产品"),
        bullet("一定要先拍板分发形式，再开始搭建数据库和题目逻辑，不要边做边改"),
        bullet("数据库的核心价值是沉淀品牌信息+联系方式，字段设计要提前想清楚"),
        bullet("测试结果逻辑要有说服力，否则用户会觉得是在收集信息而非提供价值"),
        spacer(60),
        h3("关于两个账号的协同"),
        bullet("主账号内容可以为次账号引流：在高赞图文的评论区自然引导「课件已上架橱窗」"),
        bullet("次账号不要发与主账号完全重复的内容，要形成互补而不是稀释"),
        spacer(200),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Lumiere Australia · 内部工作文档", size: 18, color: "999999", font: "Arial" })],
        }),
      ],
    },
  ],
});

const outputDir = path.resolve(__dirname, "..", "output", "doc");
const outputFile = path.join(outputDir, "Lumiere_Australia_运营工作体系_1-2个月执行计划.docx");

fs.mkdirSync(outputDir, { recursive: true });

Packer.toBuffer(doc)
  .then((buffer) => {
    fs.writeFileSync(outputFile, buffer);
    console.log(outputFile);
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
