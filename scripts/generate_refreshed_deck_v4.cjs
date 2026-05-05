const fs = require("fs");
const os = require("os");
const path = require("path");

const runtimeNodeModules = path.join(
  os.homedir(),
  ".cache",
  "codex-runtimes",
  "codex-primary-runtime",
  "dependencies",
  "node",
  "node_modules"
);

const pptxgen = require(path.join(runtimeNodeModules, "pptxgenjs"));
const sharp = require(path.join(runtimeNodeModules, "sharp"));
const JSZip = require(path.join(runtimeNodeModules, "jszip"));

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "碳硅之辩_答辩PPT_v4_美化版.pptx");
const PREVIEW_DIR = path.join(ROOT, "ppt_preview_v4");
const QA_REPORT = path.join(ROOT, "ppt_refresh_quality_v4.json");

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "西南财经大学";
pptx.company = "西南财经大学";
pptx.subject = "碳硅之辩：大模型驱动的人机辩论辅助教学平台";
pptx.title = "碳硅之辩答辩PPT美化版";
pptx.lang = "zh-CN";
pptx.theme = {
  headFontFace: "Microsoft YaHei",
  bodyFontFace: "Microsoft YaHei",
  lang: "zh-CN",
};
pptx.defineLayout({ name: "CUSTOM_WIDE", width: 13.333333, height: 7.5 });
pptx.layout = "CUSTOM_WIDE";
pptx.margin = 0;

const C = {
  bg: "061821",
  bg2: "0B2230",
  ink: "F4FBFF",
  text: "DCECF2",
  muted: "96B6C5",
  dim: "5E7C8A",
  cyan: "36E0C2",
  cyan2: "9FFFEA",
  blue: "4DA3FF",
  blue2: "8CC8FF",
  orange: "FFB15C",
  orange2: "FFE0B8",
  green: "79E38E",
  line: "234556",
  panel: "0E2A36",
  panel2: "123746",
  white: "FFFFFF",
  red: "FF756B",
};

const FONT = "Microsoft YaHei";
const W = 13.333333;
const H = 7.5;
const S = 144; // 13.333 x 7.5 inches -> 1920 x 1080 preview.
const ST = pptx.ShapeType;

function hex(c) {
  return `#${c}`;
}

function esc(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function isCjk(ch) {
  return /[\u3400-\u9fff\uff00-\uffef]/.test(ch);
}

function textUnits(str) {
  let units = 0;
  for (const ch of String(str)) units += isCjk(ch) ? 1 : 0.55;
  return units;
}

function wrapLine(str, maxUnits) {
  const out = [];
  let line = "";
  let units = 0;
  for (const ch of String(str)) {
    const u = isCjk(ch) ? 1 : 0.55;
    if (units + u > maxUnits && line) {
      out.push(line);
      line = ch;
      units = u;
    } else {
      line += ch;
      units += u;
    }
  }
  if (line) out.push(line);
  return out;
}

function previewTextLines(value, wIn, fontSizePt) {
  const maxUnits = Math.max(4, (wIn * 72) / Math.max(10, fontSizePt));
  const raw = String(value).split(/\n|\s\|\s/g);
  return raw.flatMap((line) => wrapLine(line.trim(), maxUnits)).filter(Boolean);
}

class DeckSlide {
  constructor(pageNo, title, subtitle, opts = {}) {
    this.slide = pptx.addSlide();
    this.slide.background = { color: opts.bg || C.bg };
    this.ops = [];
    this.pageNo = pageNo;
    this.title = title;
    this.subtitle = subtitle;
    this.bg = opts.bg || C.bg;

    this.rect(0, 0, W, H, { fill: this.bg, line: this.bg });
    this.rect(0, 0, W, 0.12, { fill: C.cyan, line: C.cyan, transparency: 12 });
    this.rect(0, H - 0.08, W, 0.08, { fill: C.cyan, line: C.cyan, transparency: 30 });
    this.line(0.55, H - 0.28, W - 0.55, H - 0.28, { color: C.line, width: 1 });
    this.text("碳硅之辩  ·  微课与人工智能辅助教学", 0.55, H - 0.22, 5.5, 0.16, {
      fontSize: 6.8,
      color: C.dim,
      bold: false,
    });
    this.text(String(pageNo).padStart(2, "0"), W - 0.98, H - 0.25, 0.45, 0.18, {
      fontSize: 7.5,
      color: C.dim,
      bold: true,
      align: "right",
    });

    if (title) {
      this.text(title, 0.58, 0.36, 4.45, 0.38, {
        fontSize: 14,
        color: C.cyan2,
        bold: true,
      });
    }
    if (subtitle) {
      this.text(subtitle, 0.58, 0.76, 8.6, 0.45, {
        fontSize: 22,
        color: C.ink,
        bold: true,
        breakLine: false,
      });
    }
  }

  rect(x, y, w, h, opts = {}) {
    const shapeType = opts.round ? ST.roundRect || ST.rect : ST.rect;
    const fill = opts.fill ? { color: opts.fill, transparency: opts.transparency ?? 0 } : { color: C.bg, transparency: 100 };
    const line = opts.line === false ? { color: opts.fill || C.bg, transparency: 100 } : {
      color: opts.line || opts.fill || C.line,
      transparency: opts.lineTransparency ?? 0,
      width: opts.lineWidth ?? 0.8,
    };
    this.slide.addShape(shapeType, { x, y, w, h, fill, line, rotate: opts.rotate || 0 });
    this.ops.push({ type: "rect", x, y, w, h, fill: opts.fill || C.bg, line: line.color, opacity: 1 - (fill.transparency || 0) / 100, round: !!opts.round, rotate: opts.rotate || 0 });
  }

  circle(x, y, w, h, opts = {}) {
    const fill = opts.fill ? { color: opts.fill, transparency: opts.transparency ?? 0 } : { color: C.bg, transparency: 100 };
    const line = opts.line === false ? { color: opts.fill || C.bg, transparency: 100 } : {
      color: opts.line || opts.fill || C.line,
      transparency: opts.lineTransparency ?? 0,
      width: opts.lineWidth ?? 0.8,
    };
    this.slide.addShape(ST.ellipse, { x, y, w, h, fill, line });
    this.ops.push({ type: "ellipse", x, y, w, h, fill: opts.fill || C.bg, line: line.color, opacity: 1 - (fill.transparency || 0) / 100 });
  }

  line(x1, y1, x2, y2, opts = {}) {
    this.slide.addShape(ST.line, {
      x: x1,
      y: y1,
      w: x2 - x1,
      h: y2 - y1,
      line: {
        color: opts.color || C.line,
        width: opts.width || 1,
        transparency: opts.transparency ?? 0,
        beginArrowType: opts.beginArrowType,
        endArrowType: opts.endArrowType,
      },
    });
    this.ops.push({ type: "line", x1, y1, x2, y2, color: opts.color || C.line, width: opts.width || 1, opacity: 1 - (opts.transparency || 0) / 100 });
  }

  text(value, x, y, w, h, opts = {}) {
    this.slide.addText(value, {
      x,
      y,
      w,
      h,
      fontFace: opts.fontFace || FONT,
      fontSize: opts.fontSize || 16,
      bold: !!opts.bold,
      color: opts.color || C.text,
      align: opts.align || "left",
      valign: opts.valign || "top",
      margin: opts.margin ?? 0.03,
      breakLine: opts.breakLine,
      fit: opts.fit || "shrink",
      paraSpaceAfterPt: opts.paraSpaceAfterPt ?? 0,
      lineSpacingMultiple: opts.lineSpacingMultiple || 0.92,
    });
    this.ops.push({ type: "text", value, x, y, w, h, opts });
  }

  pill(value, x, y, w, h, opts = {}) {
    this.rect(x, y, w, h, {
      fill: opts.fill || C.panel,
      line: opts.line || C.line,
      lineWidth: 0.7,
      transparency: opts.transparency ?? 0,
      round: true,
    });
    this.text(value, x + 0.08, y + h * 0.19, w - 0.16, h * 0.58, {
      fontSize: opts.fontSize || 8.5,
      color: opts.color || C.text,
      bold: opts.bold ?? true,
      align: opts.align || "center",
      valign: "mid",
    });
  }

  metric(percent, label, x, y, w, color = C.cyan) {
    this.text(percent, x, y, 1.05, 0.33, { fontSize: 21, bold: true, color });
    this.text(label, x + 1.1, y + 0.04, 1.45, 0.2, { fontSize: 8.5, color: C.text, bold: true });
    this.rect(x + 2.55, y + 0.11, w - 2.55, 0.08, { fill: C.line, line: false, transparency: 15 });
    const pct = parseFloat(percent) / 100;
    this.rect(x + 2.55, y + 0.11, (w - 2.55) * pct, 0.08, { fill: color, line: false, transparency: 0 });
  }

  previewSvg() {
    const svg = [
      `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">`,
      `<rect width="1920" height="1080" fill="${hex(this.bg)}"/>`,
    ];
    for (const op of this.ops) {
      if (op.type === "rect") {
        const x = op.x * S, y = op.y * S, w = op.w * S, h = op.h * S;
        const rx = op.round ? Math.min(22, h / 2) : 0;
        svg.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${hex(op.fill)}" opacity="${op.opacity}" stroke="${hex(op.line)}" stroke-width="${Math.max(0.5, 1.2)}"/>`);
      } else if (op.type === "ellipse") {
        const x = op.x * S, y = op.y * S, w = op.w * S, h = op.h * S;
        svg.push(`<ellipse cx="${x + w / 2}" cy="${y + h / 2}" rx="${w / 2}" ry="${h / 2}" fill="${hex(op.fill)}" opacity="${op.opacity}" stroke="${hex(op.line)}" stroke-width="1.2"/>`);
      } else if (op.type === "line") {
        svg.push(`<line x1="${op.x1 * S}" y1="${op.y1 * S}" x2="${op.x2 * S}" y2="${op.y2 * S}" stroke="${hex(op.color)}" stroke-width="${Math.max(1, op.width * 2)}" opacity="${op.opacity}" stroke-linecap="round"/>`);
      } else if (op.type === "text") {
        const { value, x, y, w, h, opts } = op;
        const size = (opts.fontSize || 16) * 2;
        const color = hex(opts.color || C.text);
        const weight = opts.bold ? 700 : 400;
        const align = opts.align || "left";
        const anchor = align === "center" ? "middle" : align === "right" ? "end" : "start";
        const x0 = align === "center" ? (x + w / 2) * S : align === "right" ? (x + w) * S : x * S;
        let y0 = y * S + size * 0.92;
        const lines = previewTextLines(value, w, opts.fontSize || 16);
        const lineHeight = size * 1.18;
        svg.push(`<text x="${x0}" y="${y0}" font-family="'Microsoft YaHei','Noto Sans CJK SC',Arial,sans-serif" font-size="${size}" fill="${color}" font-weight="${weight}" text-anchor="${anchor}">`);
        lines.slice(0, Math.max(1, Math.floor((h * S) / lineHeight) + 1)).forEach((line, idx) => {
          svg.push(`<tspan x="${x0}" dy="${idx === 0 ? 0 : lineHeight}">${esc(line)}</tspan>`);
        });
        svg.push(`</text>`);
      }
    }
    svg.push(`</svg>`);
    return svg.join("");
  }
}

const slides = [];
function newSlide(pageNo, title, subtitle, opts) {
  const d = new DeckSlide(pageNo, title, subtitle, opts);
  slides.push(d);
  return d;
}

function addSoftGrid(d) {
  for (let x = 0.8; x < W; x += 1.0) d.line(x, 1.3, x, H - 0.45, { color: C.line, width: 0.4, transparency: 78 });
  for (let y = 1.45; y < H - 0.7; y += 0.65) d.line(0.55, y, W - 0.55, y, { color: C.line, width: 0.4, transparency: 82 });
}

function sectionLabel(d, label, x, y, color = C.cyan) {
  d.rect(x, y + 0.03, 0.06, 0.28, { fill: color, line: false });
  d.text(label, x + 0.14, y, 2.5, 0.24, { fontSize: 10.2, color, bold: true });
}

function bullet(d, textValue, x, y, w, color = C.cyan) {
  d.circle(x, y + 0.05, 0.06, 0.06, { fill: color, line: false });
  d.text(textValue, x + 0.13, y, w - 0.13, 0.18, { fontSize: 8.3, color: C.text });
}

function smallCard(d, title, body, x, y, w, h, opts = {}) {
  d.rect(x, y, w, h, { fill: opts.fill || C.panel, line: opts.line || C.line, transparency: opts.transparency ?? 3, round: true });
  d.text(title, x + 0.18, y + 0.15, w - 0.36, 0.22, { fontSize: opts.titleSize || 10.5, color: opts.color || C.cyan2, bold: true });
  d.text(body, x + 0.18, y + 0.48, w - 0.36, h - 0.6, { fontSize: opts.bodySize || 7.7, color: C.text });
}

function phaseNode(d, no, title, lines, x, y, w, accent) {
  d.text(no, x, y, 0.35, 0.24, { fontSize: 9, color: accent, bold: true });
  d.line(x, y + 0.35, x + w, y + 0.35, { color: accent, width: 1.1, transparency: 5 });
  d.text(title, x, y + 0.46, w, 0.22, { fontSize: 11.2, color: C.ink, bold: true });
  d.text(lines.join("\n"), x, y + 0.82, w, 0.72, { fontSize: 7.4, color: C.muted });
}

function slide1() {
  const d = newSlide(1, "", "", { bg: C.bg });
  addSoftGrid(d);
  d.rect(7.95, 0.45, 4.9, 6.0, { fill: C.panel, line: C.line, transparency: 0, round: true });
  d.rect(8.15, 0.67, 4.48, 5.56, { fill: C.bg2, line: C.line, transparency: 6, round: true });
  d.line(8.45, 3.47, 12.25, 3.47, { color: C.line, width: 1, transparency: 20 });
  d.circle(8.75, 1.18, 0.56, 0.56, { fill: C.cyan, line: false, transparency: 12 });
  d.circle(11.3, 5.25, 0.56, 0.56, { fill: C.blue, line: false, transparency: 10 });
  d.text("HUMAN", 8.45, 1.85, 1.25, 0.18, { fontSize: 7.6, color: C.muted, bold: true });
  d.text("CARBON", 8.45, 2.1, 1.65, 0.32, { fontSize: 16, color: C.ink, bold: true });
  d.text("SILICON", 10.7, 4.25, 1.75, 0.32, { fontSize: 16, color: C.ink, bold: true, align: "right" });
  d.text("AI AGENT", 10.95, 4.65, 1.35, 0.18, { fontSize: 7.6, color: C.muted, bold: true, align: "right" });
  d.text("VS", 9.9, 3.04, 0.78, 0.34, { fontSize: 18, color: C.orange, bold: true, align: "center" });
  for (let i = 0; i < 8; i++) {
    d.circle(9.2 + i * 0.32, 2.78 + (i % 2) * 0.22, 0.05, 0.05, { fill: i % 2 ? C.blue : C.cyan, line: false, transparency: 0 });
  }

  d.text("中国大学生计算机设计大赛 2026  ·  微课与人工智能辅助教学", 0.65, 0.48, 6.6, 0.24, {
    fontSize: 9.5,
    color: C.cyan2,
    bold: true,
  });
  d.text("碳硅之辩", 0.63, 1.48, 5.9, 0.72, { fontSize: 43, color: C.ink, bold: true });
  d.rect(0.68, 2.36, 1.2, 0.07, { fill: C.orange, line: false });
  d.text("大模型驱动的人机辩论辅助教学平台", 0.65, 2.62, 6.6, 0.34, {
    fontSize: 20,
    color: C.text,
    bold: true,
  });
  d.text("面向人工智能通识课与计算机基础课程的 AI 辩论式教学实践", 0.66, 3.08, 6.3, 0.3, {
    fontSize: 12.5,
    color: C.muted,
  });

  const metas = [
    ["参赛单位", "西南财经大学"],
    ["答辩时长", "10分钟  |  视频3分钟"],
    ["参赛赛道", "微课与AI辅助教学"],
  ];
  metas.forEach((m, i) => {
    d.text(m[0], 0.68 + i * 2.02, 4.22, 1.0, 0.16, { fontSize: 7.3, color: C.dim, bold: true });
    d.text(m[1], 0.68 + i * 2.02, 4.52, 1.74, 0.26, { fontSize: 10.4, color: C.ink, bold: true });
  });
  ["AI 辩手对抗", "语音实时交互", "知识库备赛", "赛后报告分析", "成长趋势追踪", "三端协同运营"].forEach((v, i) => {
    d.pill(v, 0.66 + (i % 3) * 2.03, 5.36 + Math.floor(i / 3) * 0.5, 1.72, 0.28, {
      fill: i % 2 ? C.panel2 : C.panel,
      color: i % 3 === 0 ? C.cyan2 : C.text,
      fontSize: 7.6,
    });
  });
}

function slide2() {
  const d = newSlide(2, "教学痛点", "辩论式教学有价值，但难组织、难反馈、难沉淀");
  d.text("前期用户调研数据", 0.72, 1.48, 2.5, 0.24, { fontSize: 11, color: C.cyan2, bold: true });
  [
    ["84.7%", "希望提升表达能力", C.cyan],
    ["86.1%", "希望获得具体反馈", C.blue],
    ["62.5%", "愿意尝试 AI 陪练", C.green],
    ["37.5%", "接受 AI 直接评分", C.orange],
    ["31.9%", "不愿使用复杂系统", C.red],
  ].forEach((m, i) => d.metric(m[0], m[1], 0.74, 1.9 + i * 0.56, 4.3, m[2]));

  d.rect(0.72, 4.88, 4.55, 0.78, { fill: "1A2B22", line: C.orange, lineWidth: 0.9, transparency: 0, round: true });
  d.text("设计约束", 0.94, 5.03, 0.9, 0.18, { fontSize: 8.8, color: C.orange2, bold: true });
  d.text("AI 必须辅助教师，而非取代教师；低操作门槛必须成为明确设计原则。", 1.82, 4.98, 3.18, 0.38, {
    fontSize: 8.6,
    color: C.text,
  });

  sectionLabel(d, "三类核心痛点", 5.85, 1.48, C.blue2);
  const cards = [
    ["学生端", "缺少稳定练习对手，难以高频训练；备赛资料分散，论据准备效率低；赛后缺少具体改进建议。", C.cyan],
    ["教师端", "分组、控场、计时、记录都依赖人工；课后点评耗时，班级表现缺乏系统追踪。", C.blue],
    ["教学端", "辩论过程难沉淀，长期能力数据不足；AI 伦理等议题缺少实践教学载体。", C.orange],
  ];
  cards.forEach((c, i) => {
    const y = 2.0 + i * 0.9;
    d.rect(5.85, y, 0.06, 0.62, { fill: c[2], line: false });
    d.text(c[0], 6.08, y - 0.02, 1.05, 0.24, { fontSize: 12.3, color: C.ink, bold: true });
    d.text(c[1], 7.18, y + 0.02, 4.9, 0.38, { fontSize: 8.2, color: C.text });
    d.line(6.08, y + 0.74, 12.18, y + 0.74, { color: C.line, width: 0.9, transparency: 12 });
  });
  d.text("结论", 5.85, 5.2, 0.55, 0.22, { fontSize: 9, color: C.cyan2, bold: true });
  d.text("平台机会不在“替老师评分”，而在降低辩论教学组织成本，并把练习过程转化为可复盘的数据。", 6.45, 5.16, 5.7, 0.38, {
    fontSize: 10.2,
    color: C.ink,
    bold: true,
  });
}

function slide3() {
  const d = newSlide(3, "解决方案", "构建课前 · 课中 · 课后 · 长期成长的 AI 辩论教学闭环");
  d.text("碳硅之辩通过 AI 辩手、流程控制、语音交互、知识库和赛后分析，让每一次课堂辩论可组织、可记录、可评价、可成长。", 0.72, 1.38, 11.65, 0.36, {
    fontSize: 12.3,
    color: C.text,
  });

  const phases = [
    ["01", "课前备赛", ["课程知识库文档", "备赛问答助手", "论点论据准备"], C.cyan],
    ["02", "课中辩论", ["AI 辩手实时陪练", "语音发言与识别", "结构化阶段推进"], C.blue],
    ["03", "课后复盘", ["发言全程自动记录", "AI 评分与报告", "PDF / Excel 导出"], C.orange],
    ["04", "长期成长", ["能力趋势图表", "班级横向对比", "成就激励体系"], C.green],
  ];
  phases.forEach((p, i) => {
    const x = 0.82 + i * 3.05;
    d.circle(x + 0.98, 2.35, 0.82, 0.82, { fill: p[3], line: false, transparency: 8 });
    d.text(p[0], x + 1.11, 2.55, 0.55, 0.22, { fontSize: 11.5, color: C.bg, bold: true, align: "center" });
    d.text(p[1], x, 3.34, 2.78, 0.26, { fontSize: 15, color: C.ink, bold: true, align: "center" });
    d.text(p[2].join("\n"), x + 0.2, 3.83, 2.38, 0.68, { fontSize: 8.2, color: C.text, align: "center" });
    if (i < phases.length - 1) d.line(x + 2.42, 2.76, x + 3.02, 2.76, { color: C.line, width: 1.4, endArrowType: "triangle" });
  });

  const insights = [
    ["课前", "基于知识库准备论点，告别散乱资料"],
    ["课中", "AI 辩手稳定陪练，完整流程有记录"],
    ["课后", "系统自动生成报告，教师无需整理"],
    ["长期", "多场数据沉淀为能力成长档案"],
  ];
  insights.forEach((it, i) => {
    d.text(it[0], 0.9 + i * 3.05, 5.18, 0.55, 0.2, { fontSize: 8.5, color: phases[i][3], bold: true });
    d.text(it[1], 1.48 + i * 3.05, 5.16, 2.0, 0.34, { fontSize: 8.6, color: C.muted });
  });
}

function slide4() {
  const d = newSlide(4, "三端协同", "学生训练端 · 教师组织端 · 管理员配置端，围绕实时辩论场协同运转");
  d.circle(5.55, 2.1, 2.25, 2.25, { fill: C.panel2, line: C.cyan, lineWidth: 1.4, transparency: 0 });
  d.text("实时辩论场", 5.88, 2.76, 1.58, 0.28, { fontSize: 15, color: C.ink, bold: true, align: "center" });
  d.text("流程推进 · 倒计时 · 抢麦\nAI 发言 · 语音播放 · 记录入库", 5.78, 3.18, 1.8, 0.5, { fontSize: 7.9, color: C.muted, align: "center" });
  d.line(4.95, 3.1, 3.95, 3.1, { color: C.cyan, width: 1.2 });
  d.line(8.15, 3.1, 9.15, 3.1, { color: C.blue, width: 1.2 });
  d.line(6.67, 4.7, 6.67, 5.4, { color: C.orange, width: 1.2 });

  smallCard(d, "学生端 · 训练参与者", "个人控制台：任务入口、历史记录、成长数据\n能力评估：五维画像、角色分配建议\n备赛助手：RAG 知识库、论据引用追溯\n成长分析：趋势图、班级对比、成就徽章", 0.78, 1.85, 3.65, 2.95, { color: C.cyan2, line: C.cyan });
  smallCard(d, "教师端 · 教学组织者", "班级管理：创建班级、学生信息管理\n辩论创建：辩题、时长、轮次、知识点配置\n预约管理：邀请签到、提前安排课程计划\n报告回放：发言记录、评分、课堂讲评依据", 8.9, 1.85, 3.65, 2.95, { color: C.blue2, line: C.blue });
  smallCard(d, "管理员端 · 平台维护者", "用户与班级治理\n知识库文档上传、解析、向量化\n模型、Coze、ASR、TTS、向量、邮件配置\n保障平台稳定接入不同 AI 与语音服务", 4.35, 5.18, 4.65, 1.08, { color: C.orange2, line: C.orange, bodySize: 7.4 });
}

function slide5() {
  const d = newSlide(5, "实时辩论场", "一场完整的人机辩论如何发生");
  sectionLabel(d, "辩论结构化流程", 0.72, 1.44, C.cyan);
  const steps = [
    ["01", "正方一辩立论", "学生发言"],
    ["02", "反方一辩立论", "AI 辩手生成回应"],
    ["03", "多轮盘问回答", "双方交替"],
    ["04", "攻辩小结", "各方陈述立场"],
    ["05", "自由辩论抢麦", "即时竞争发言权"],
    ["06", "双方总结陈词", "辩论完整结束"],
  ];
  steps.forEach((s, i) => {
    const y = 1.9 + i * 0.58;
    d.text(s[0], 0.82, y, 0.42, 0.18, { fontSize: 8, color: i % 2 ? C.blue : C.cyan, bold: true });
    d.line(1.35, y + 0.1, 1.7, y + 0.1, { color: C.line, width: 1 });
    d.text(s[1], 1.85, y - 0.02, 1.65, 0.2, { fontSize: 10.8, color: C.ink, bold: true });
    d.text(s[2], 3.48, y, 1.5, 0.18, { fontSize: 8.2, color: C.muted });
  });
  d.rect(5.24, 1.64, 0.04, 3.58, { fill: C.line, line: false });

  sectionLabel(d, "技术支撑", 5.75, 1.44, C.blue2);
  const tech = [
    ["WebSocket 实时同步", "房间状态、当前发言人、倒计时毫秒级推送"],
    ["AI 辩手智能体", "辩题 + 立场 + 上下文 → Coze/OpenAI → 对抗性发言"],
    ["TTS 语音合成", "AI 发言文字转语音，营造真实对抗感"],
    ["ASR 语音识别", "学生发言语音转文本，自动入档计时"],
    ["抢麦机制", "自由辩论阶段即时抢权，还原真实辩论场景"],
  ];
  tech.forEach((t, i) => {
    const y = 1.88 + i * 0.62;
    d.circle(5.82, y + 0.07, 0.12, 0.12, { fill: i % 2 ? C.blue : C.cyan, line: false });
    d.text(t[0], 6.04, y - 0.02, 2.3, 0.2, { fontSize: 10.5, color: C.ink, bold: true });
    d.text(t[1], 8.42, y - 0.02, 3.7, 0.2, { fontSize: 8.3, color: C.muted });
  });

  d.rect(0.72, 5.62, 11.88, 0.56, { fill: "102A23", line: C.cyan, lineWidth: 0.8, transparency: 0, round: true });
  d.text("语音时序闭环", 0.94, 5.8, 1.2, 0.18, { fontSize: 8.8, color: C.cyan2, bold: true });
  d.text("AI生成发言 → TTS合成 → 前端播放 → 回传完成事件 → 系统推进下一环节，保证流程与语音同步。", 2.1, 5.78, 9.8, 0.2, { fontSize: 9.2, color: C.ink, bold: true });
}

function slide6() {
  const d = newSlide(6, "赛后报告与成长分析", "从一场辩论到长期能力档案的完整数据链路");
  const blocks = [
    ["即时分析", "单场多维度评分概览\n表现优势识别与不足标记\nAI 导师个性化改进建议\n辩论结束后立刻呈现", C.cyan],
    ["正式报告", "完整发言记录（文本 + 音频 + 时长）\n能力维度深度分析报告\nPDF / Excel 格式导出\n可复盘、可导出、可分享", C.blue],
    ["成长追踪", "历史辩论趋势图与能力变化曲线\n班级横向对比分析\n成就激励体系与徽章系统\n跨场次长期数据沉淀", C.orange],
  ];
  blocks.forEach((b, i) => {
    const x = 0.82 + i * 4.05;
    d.rect(x, 1.82, 3.32, 3.65, { fill: C.panel, line: b[2], lineWidth: 1.1, transparency: 0, round: true });
    d.text(`0${i + 1}`, x + 0.22, 2.05, 0.45, 0.22, { fontSize: 9, color: b[2], bold: true });
    d.text(b[0], x + 0.22, 2.48, 2.2, 0.3, { fontSize: 17, color: C.ink, bold: true });
    d.text(b[1], x + 0.26, 3.1, 2.78, 1.26, { fontSize: 8.4, color: C.text });
    d.line(x + 0.22, 4.72, x + 2.88, 4.72, { color: b[2], width: 1 });
    if (i < 2) d.line(x + 3.42, 3.65, x + 3.86, 3.65, { color: C.line, width: 1.2, endArrowType: "triangle" });
  });
  d.text("单场数据", 1.05, 5.96, 1.0, 0.18, { fontSize: 8.5, color: C.muted, bold: true });
  d.line(2.0, 6.06, 11.3, 6.06, { color: C.line, width: 1.1 });
  d.text("长期能力档案", 11.1, 5.96, 1.25, 0.18, { fontSize: 8.5, color: C.cyan2, bold: true, align: "right" });
  d.circle(7.55, 5.73, 0.2, 0.2, { fill: C.cyan, line: false });
  d.circle(8.28, 5.48, 0.2, 0.2, { fill: C.blue, line: false });
  d.circle(9.05, 5.25, 0.2, 0.2, { fill: C.orange, line: false });
  d.line(7.65, 5.83, 8.38, 5.58, { color: C.cyan, width: 1.1 });
  d.line(8.38, 5.58, 9.15, 5.35, { color: C.blue, width: 1.1 });
}

function slide7() {
  const d = newSlide(7, "AI 角色设计", "辅助教师，而不是替代教师");
  const roles = [
    ["AI 辩手", "课中辩论", "根据辩题、立场、阶段上下文生成对抗性发言，支持 Coze / OpenAI 兼容接口", C.cyan],
    ["AI 评委", "辩论结束", "对发言进行多维度评分、规则判断和表现点评", C.blue],
    ["AI 导师", "报告页面", "生成个性化改进建议和下一步学习方向指导", C.orange],
    ["RAG 助教", "课前备赛", "基于课程文档检索增强回答，引用来源可追溯", C.green],
    ["语音助手", "辩论全程", "ASR 转写学生语音 + TTS 合成 AI 发言语音", C.blue2],
  ];
  roles.forEach((r, i) => {
    const y = 1.55 + i * 0.72;
    d.text(String(i + 1).padStart(2, "0"), 0.8, y, 0.38, 0.2, { fontSize: 8.5, color: r[3], bold: true });
    d.line(1.32, y + 0.1, 2.05, y + 0.1, { color: r[3], width: 1.1 });
    d.text(r[0], 2.25, y - 0.07, 1.3, 0.25, { fontSize: 13, color: C.ink, bold: true });
    d.pill(r[1], 3.72, y - 0.08, 1.18, 0.26, { fill: C.panel2, line: C.line, color: C.cyan2, fontSize: 7.2 });
    d.text(r[2], 5.15, y - 0.05, 6.5, 0.28, { fontSize: 9.2, color: C.text });
  });
  d.rect(0.78, 5.72, 11.78, 0.56, { fill: "231E13", line: C.orange, lineWidth: 0.9, transparency: 0, round: true });
  d.text("AI 使用边界", 1.0, 5.91, 1.2, 0.18, { fontSize: 8.8, color: C.orange2, bold: true });
  d.text("AI 提供陪练和初步分析；教师保留最终评价和教学解释权；报告辅助复盘，不作为唯一评分依据。", 2.28, 5.88, 9.45, 0.22, {
    fontSize: 9.4,
    color: C.ink,
    bold: true,
  });
}

function slide8() {
  const d = newSlide(8, "平台架构与技术栈", "五层分离架构，前后端解耦，多智能体协同");
  const layers = [
    ["前端层", "React 18 · TypeScript · Vite · Tailwind CSS · Radix UI", "学生端 / 教师端 / 管理员端 / 实时辩论场", C.cyan],
    ["接口层", "FastAPI · REST API · WebSocket · JWT 鉴权", "认证 / 路由 / 实时通信 / 角色权限隔离", C.blue],
    ["编排层", "RoomManager · FlowController", "房间状态 / 阶段推进 / 发言权控制 / AI 触发", C.orange],
    ["AI能力层", "Debater / Judge / Mentor Agent · Coze · OpenAI兼容", "ASR / TTS / RAG，多智能体协作与语音、知识库能力", C.green],
    ["数据层", "PostgreSQL · pgvector · Redis", "用户 / 辩论 / 发言 / 评分 / 报告 / 知识库", C.blue2],
  ];
  layers.forEach((l, i) => {
    const y = 1.45 + i * 0.7;
    d.rect(0.78, y, 6.2, 0.48, { fill: i % 2 ? C.panel2 : C.panel, line: l[3], lineWidth: 0.8, transparency: 0, round: true });
    d.text(l[0], 1.02, y + 0.12, 1.0, 0.18, { fontSize: 9, color: l[3], bold: true });
    d.text(l[1], 2.0, y + 0.08, 4.55, 0.18, { fontSize: 9.5, color: C.ink, bold: true });
    d.text(l[2], 2.0, y + 0.29, 4.6, 0.16, { fontSize: 6.9, color: C.muted });
    if (i < layers.length - 1) d.line(3.85, y + 0.5, 3.85, y + 0.68, { color: C.line, width: 1 });
  });

  sectionLabel(d, "核心调用链", 7.45, 1.46, C.cyan2);
  const chain = ["学生发言", "WebSocket 接入", "FlowController 编排", "AI Agent 生成回应", "TTS 合成语音播放", "Speech 记录入库", "报告与分析生成"];
  chain.forEach((c, i) => {
    const y = 1.95 + i * 0.43;
    d.text(c, 7.55, y, 2.28, 0.18, { fontSize: 8.5, color: i === 0 ? C.ink : C.text, bold: i === 0 });
    if (i < chain.length - 1) d.line(9.62, y + 0.09, 10.18, y + 0.09, { color: C.line, width: 1, endArrowType: "triangle" });
  });

  sectionLabel(d, "工程质量", 7.45, 5.15, C.orange2);
  ["Docker Compose 一键部署", "SQLAlchemy + Alembic 迁移", "Vitest + pytest 测试覆盖", "模型 / 语音 / 向量后台可配置"].forEach((b, i) => {
    bullet(d, b, 7.52 + (i % 2) * 2.55, 5.55 + Math.floor(i / 2) * 0.34, 2.36, i % 2 ? C.blue : C.cyan);
  });
}

function slide9() {
  const d = newSlide(9, "创新点与教学价值", "把大模型嵌入真实教学流程的五项核心创新");
  const innovations = [
    ["01", "教学模式创新", "AI 作为辩手进入完整辩论流程，实现对抗式教学，而非普通问答工具"],
    ["02", "多智能体协作", "辩手 / 裁判 / 导师三类 Agent 分工，覆盖训练、评价、指导全链路"],
    ["03", "语音交互融合", "ASR/TTS 支持真实口语训练，发言自动沉淀为可回放记录与分析数据"],
    ["04", "知识库增强备赛", "回答基于课程文档检索生成，来源可追溯，降低幻觉风险"],
    ["05", "赛后成长沉淀", "每场辩论数据自动转化为能力成长曲线与学习档案，支持班级对比"],
  ];
  innovations.forEach((it, i) => {
    const y = 1.45 + i * 0.62;
    d.text(it[0], 0.8, y, 0.45, 0.2, { fontSize: 8.6, color: i % 2 ? C.blue : C.cyan, bold: true });
    d.text(it[1], 1.38, y - 0.05, 1.7, 0.22, { fontSize: 11.2, color: C.ink, bold: true });
    d.text(it[2], 3.2, y - 0.04, 5.85, 0.24, { fontSize: 8.4, color: C.text });
  });
  d.rect(9.6, 1.45, 2.72, 3.52, { fill: C.panel, line: C.line, transparency: 0, round: true });
  d.text("教学价值", 9.92, 1.78, 1.3, 0.26, { fontSize: 15.5, color: C.orange2, bold: true });
  const value = [
    ["对学生", "低压力高频训练\n提升表达与逻辑辩证能力", C.cyan],
    ["对教师", "低成本组织课堂\n获得可复盘的量化材料", C.blue],
    ["对课程", "AI伦理、算法影响、数据隐私\n有了高参与度实践载体", C.green],
  ];
  value.forEach((v, i) => {
    const y = 2.34 + i * 0.78;
    d.rect(9.92, y, 0.05, 0.45, { fill: v[2], line: false });
    d.text(v[0], 10.12, y - 0.02, 0.8, 0.18, { fontSize: 8.3, color: v[2], bold: true });
    d.text(v[1], 10.12, y + 0.22, 1.82, 0.3, { fontSize: 7.4, color: C.text });
  });
}

function slide10() {
  const d = newSlide(10, "平台演示", "用一场完整辩论展示教学闭环");
  const timeline = [
    ["0:00", "角色登录"],
    ["0:15", "教师建赛"],
    ["0:40", "学生备赛"],
    ["1:05", "实时辩论"],
    ["2:05", "赛后报告"],
    ["2:35", "成长分析"],
    ["2:50", "管理配置"],
  ];
  d.line(0.9, 2.15, 7.35, 2.15, { color: C.line, width: 1.4 });
  timeline.forEach((t, i) => {
    const x = 0.9 + i * 1.07;
    d.circle(x - 0.05, 2.04, 0.22, 0.22, { fill: i === 3 ? C.orange : C.cyan, line: false });
    d.text(t[0], x - 0.35, 1.58, 0.7, 0.18, { fontSize: 8.6, color: i === 3 ? C.orange2 : C.cyan2, bold: true, align: "center" });
    d.text(t[1], x - 0.46, 2.44, 0.9, 0.18, { fontSize: 8.4, color: C.text, bold: true, align: "center" });
  });

  d.rect(8.3, 1.45, 3.8, 2.3, { fill: C.panel, line: C.cyan, lineWidth: 1.1, transparency: 0, round: true });
  d.circle(9.82, 2.12, 0.92, 0.92, { fill: C.cyan, line: false, transparency: 12 });
  d.slide.addShape(ST.triangle, {
    x: 10.16,
    y: 2.39,
    w: 0.32,
    h: 0.32,
    rotate: 90,
    fill: { color: C.bg },
    line: { color: C.bg, transparency: 100 },
  });
  d.ops.push({ type: "text", value: "▶", x: 10.06, y: 2.26, w: 0.45, h: 0.32, opts: { fontSize: 18, color: C.bg, bold: true, align: "center" } });
  d.text("3 分钟演示视频", 8.75, 3.02, 2.95, 0.26, { fontSize: 15, color: C.ink, bold: true, align: "center" });

  d.text("演示视频重点", 0.88, 3.65, 1.4, 0.22, { fontSize: 10.5, color: C.cyan2, bold: true });
  ["教师创建辩论任务", "学生备赛与知识库问答", "人机实时辩论（核心片段）", "赛后报告与成长分析"].forEach((b, i) => {
    bullet(d, b, 1.0 + (i % 2) * 3.0, 4.12 + Math.floor(i / 2) * 0.45, 2.6, i % 2 ? C.blue : C.cyan);
  });

  d.rect(0.86, 5.35, 11.42, 0.78, { fill: "0E2A23", line: C.cyan, lineWidth: 0.8, transparency: 0, round: true });
  d.text("碳硅之辩希望让每一次课堂辩论都可组织、可记录、可评价、可成长。", 1.1, 5.52, 10.95, 0.24, {
    fontSize: 13,
    color: C.ink,
    bold: true,
    align: "center",
  });
  d.text("让大模型真正成为教师和学生的辅助伙伴，而不只是一个对话框。", 1.38, 5.86, 10.3, 0.2, {
    fontSize: 9.5,
    color: C.muted,
    align: "center",
  });
}

slide1();
slide2();
slide3();
slide4();
slide5();
slide6();
slide7();
slide8();
slide9();
slide10();

async function renderPreviews() {
  fs.mkdirSync(PREVIEW_DIR, { recursive: true });
  await Promise.all(
    slides.map(async (d, idx) => {
      const svg = d.previewSvg();
      const out = path.join(PREVIEW_DIR, `slide-${String(idx + 1).padStart(2, "0")}.png`);
      await sharp(Buffer.from(svg)).png().toFile(out);
    })
  );
}

async function inspectPptx(filePath) {
  const data = fs.readFileSync(filePath);
  const zip = await JSZip.loadAsync(data);
  const names = Object.keys(zip.files);
  const slideNames = names
    .filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name))
    .sort((a, b) => Number(a.match(/slide(\d+)/)[1]) - Number(b.match(/slide(\d+)/)[1]));
  const mediaNames = names.filter((name) => name.startsWith("ppt/media/") && !zip.files[name].dir);
  const placeholder = [];
  for (let i = 0; i < slideNames.length; i++) {
    const xml = await zip.file(slideNames[i]).async("string");
    if (/\b(Slide Number|Click to add|Lorem ipsum|Replace with|TODO|TBD)\b/i.test(xml)) {
      placeholder.push(i + 1);
    }
  }
  const zeroMedia = [];
  for (const name of mediaNames) {
    const buf = await zip.file(name).async("nodebuffer");
    if (buf.length === 0) zeroMedia.push(name);
  }
  return {
    pptx: filePath,
    slide_count: slideNames.length,
    media_count: mediaNames.length,
    placeholder_slides: placeholder,
    zero_byte_media: zeroMedia,
    checks: {
      expected_slide_count: slideNames.length === 10,
      no_placeholder_text: placeholder.length === 0,
      no_zero_byte_media: zeroMedia.length === 0,
    },
  };
}

(async () => {
  await pptx.writeFile({ fileName: OUT });
  await renderPreviews();
  const report = await inspectPptx(OUT);
  report.preview_dir = PREVIEW_DIR;
  report.preview_files = fs.readdirSync(PREVIEW_DIR).filter((f) => f.endsWith(".png")).sort();
  fs.writeFileSync(QA_REPORT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ output: OUT, previewDir: PREVIEW_DIR, qaReport: QA_REPORT, report }, null, 2));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
