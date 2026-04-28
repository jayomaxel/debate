"""
Markdown转PDF工具
使用WeasyPrint实现高质量的PDF生成，支持中文、代码高亮、表格等
"""
import asyncio
from pathlib import Path
from typing import Optional
from io import BytesIO

from markdown import markdown
from pygments.formatters import HtmlFormatter

from logging_config import get_logger

logger = get_logger(__name__)


class MarkdownToPdfConverter:
    """Markdown转PDF转换器"""
    
    # 默认CSS样式
    DEFAULT_CSS = """
    @page {
        size: A4;
        margin: 2.5cm 2cm;
        
        @top-center {
            content: "辩论报告";
            font-size: 10pt;
            color: #666;
        }
        
        @bottom-right {
            content: "第 " counter(page) " 页";
            font-size: 10pt;
            color: #666;
        }
    }
    
    body {
        font-family: 'Noto Sans CJK SC', 'Source Han Sans SC', 'Microsoft YaHei', 
                     'PingFang SC', 'Hiragino Sans GB', 'WenQuanYi Micro Hei', sans-serif;
        font-size: 11pt;
        line-height: 1.8;
        color: #333;
        text-align: justify;
    }
    
    /* 标题样式 */
    h1 {
        color: #2c3e50;
        font-size: 24pt;
        font-weight: bold;
        border-bottom: 3px solid #3498db;
        padding-bottom: 0.4em;
        margin-top: 1.5em;
        margin-bottom: 0.8em;
        page-break-after: avoid;
    }
    
    h2 {
        color: #34495e;
        font-size: 20pt;
        font-weight: bold;
        border-bottom: 2px solid #95a5a6;
        padding-bottom: 0.3em;
        margin-top: 1.2em;
        margin-bottom: 0.6em;
        page-break-after: avoid;
    }
    
    h3 {
        color: #555;
        font-size: 16pt;
        font-weight: bold;
        margin-top: 1em;
        margin-bottom: 0.5em;
        page-break-after: avoid;
    }
    
    h4 {
        color: #666;
        font-size: 14pt;
        font-weight: bold;
        margin-top: 0.8em;
        margin-bottom: 0.4em;
    }
    
    h5, h6 {
        color: #777;
        font-size: 12pt;
        font-weight: bold;
        margin-top: 0.6em;
        margin-bottom: 0.3em;
    }
    
    /* 段落 */
    p {
        margin: 0.6em 0;
        text-indent: 0;
    }
    
    /* 引用块 */
    blockquote {
        border-left: 4px solid #3498db;
        padding-left: 1.2em;
        margin: 1em 0;
        color: #555;
        font-style: italic;
        background-color: #f8f9fa;
        padding: 0.8em 1.2em;
        border-radius: 4px;
    }
    
    blockquote p {
        margin: 0.3em 0;
    }
    
    /* 列表 */
    ul, ol {
        margin: 0.8em 0;
        padding-left: 2em;
    }
    
    li {
        margin: 0.4em 0;
        line-height: 1.6;
    }
    
    /* 代码块 */
    code {
        font-family: 'Noto Sans Mono CJK SC', 'Source Code Pro', 'Consolas', 
                     'Monaco', 'Courier New', monospace;
        background-color: #f4f4f4;
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 10pt;
        color: #c7254e;
    }
    
    pre {
        background-color: #f8f8f8;
        border: 1px solid #ddd;
        border-left: 4px solid #3498db;
        border-radius: 4px;
        padding: 1em;
        overflow-x: auto;
        margin: 1em 0;
        page-break-inside: avoid;
    }
    
    pre code {
        background: none;
        padding: 0;
        color: inherit;
        font-size: 9.5pt;
        line-height: 1.5;
    }
    
    /* 表格样式 */
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 1.2em 0;
        font-size: 10pt;
        page-break-inside: avoid;
    }
    
    thead {
        background-color: #3498db;
        color: white;
    }
    
    th {
        border: 1px solid #2980b9;
        padding: 10px 12px;
        text-align: left;
        font-weight: bold;
    }
    
    td {
        border: 1px solid #ddd;
        padding: 8px 12px;
        text-align: left;
    }
    
    tbody tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    
    tbody tr:hover {
        background-color: #f5f5f5;
    }
    
    /* 水平线 */
    hr {
        border: none;
        border-top: 2px solid #e0e0e0;
        margin: 1.5em 0;
    }
    
    /* 链接 */
    a {
        color: #3498db;
        text-decoration: none;
    }
    
    a:hover {
        text-decoration: underline;
    }
    
    /* 图片 */
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 1em auto;
        page-break-inside: avoid;
    }
    
    /* 强调 */
    strong, b {
        font-weight: bold;
        color: #2c3e50;
    }
    
    em, i {
        font-style: italic;
    }
    
    /* 删除线 */
    del, s {
        text-decoration: line-through;
        color: #999;
    }
    
    /* 分页控制 */
    .page-break {
        page-break-after: always;
    }
    
    /* 避免孤行 */
    h1, h2, h3, h4, h5, h6 {
        page-break-after: avoid;
    }
    
    /* 报告容器 */
    .report-container {
        max-width: 100%;
    }
    
    /* 元信息样式 */
    .meta-info {
        background-color: #ecf0f1;
        padding: 1em;
        border-radius: 6px;
        margin: 1em 0;
        font-size: 10pt;
    }
    
    .meta-info p {
        margin: 0.3em 0;
    }
    
    /* 评分表格特殊样式 */
    .score-table {
        margin: 1.5em 0;
    }
    
    .score-table th {
        background-color: #2ecc71;
    }
    
    /* 高亮框 */
    .highlight-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1em;
        margin: 1em 0;
        border-radius: 4px;
    }
    
    /* 警告框 */
    .warning-box {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 1em;
        margin: 1em 0;
        border-radius: 4px;
    }
    
    /* 信息框 */
    .info-box {
        background-color: #d1ecf1;
        border-left: 4px solid #17a2b8;
        padding: 1em;
        margin: 1em 0;
        border-radius: 4px;
    }
    """
    
    def __init__(self, custom_css: Optional[str] = None):
        """
        初始化转换器
        
        Args:
            custom_css: 自定义CSS样式（可选）
        """
        self.custom_css = custom_css
        try:
            from weasyprint.text.fonts import FontConfiguration
            self.font_config = FontConfiguration()
        except Exception:
            self.font_config = None
    
    def _get_syntax_highlight_css(self, style: str = "github") -> str:
        """
        获取代码语法高亮CSS
        
        Args:
            style: Pygments样式名称（github, monokai, solarized-light等）
            
        Returns:
            CSS字符串
        """
        try:
            formatter = HtmlFormatter(style=style)
            return formatter.get_style_defs('.codehilite')
        except Exception as e:
            logger.warning(f"获取语法高亮CSS失败: {e}")
            return ""
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        将Markdown转换为HTML
        
        Args:
            markdown_text: Markdown文本
            
        Returns:
            HTML字符串
        """
        try:
            # 使用markdown扩展
            html_body = markdown(
                markdown_text,
                extensions=[
                    'extra',          # 表格、脚注、定义列表等
                    'codehilite',     # 代码高亮
                    'toc',            # 目录
                    'nl2br',          # 换行转<br>
                    'sane_lists',     # 更好的列表支持
                    'smarty',         # 智能标点
                    'attr_list',      # 属性列表
                    'def_list',       # 定义列表
                    'tables',         # 表格
                    'fenced_code',    # 围栏代码块
                ],
                extension_configs={
                    'codehilite': {
                        'linenums': False,
                        'guess_lang': True,
                    }
                }
            )
            
            return html_body
        except Exception as e:
            logger.error(f"Markdown转HTML失败: {e}", exc_info=True)
            # 返回原始文本的HTML转义版本
            return f"<pre>{markdown_text}</pre>"
    
    def _build_full_html(
        self,
        html_body: str,
        title: str = "辩论报告",
        meta_info: Optional[dict] = None
    ) -> str:
        """
        构建完整的HTML文档
        
        Args:
            html_body: HTML正文
            title: 文档标题
            meta_info: 元信息（可选）
            
        Returns:
            完整HTML字符串
        """
        # 构建元信息HTML
        meta_html = ""
        if meta_info:
            meta_items = []
            for key, value in meta_info.items():
                meta_items.append(f"<p><strong>{key}:</strong> {value}</p>")
            meta_html = f'<div class="meta-info">{"".join(meta_items)}</div>'
        
        full_html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body>
    <div class="report-container">
        <h1 style="text-align: center; border-bottom: none;">{title}</h1>
        {meta_html}
        {html_body}
    </div>
</body>
</html>
"""
        return full_html
    
    def convert_to_pdf(
        self,
        markdown_text: str,
        output_path: Optional[Path] = None,
        title: str = "辩论报告",
        meta_info: Optional[dict] = None,
        syntax_style: str = "github"
    ) -> bytes:
        """
        将Markdown转换为PDF
        
        Args:
            markdown_text: Markdown文本
            output_path: 输出文件路径（可选，如果不提供则只返回字节流）
            title: 文档标题
            meta_info: 元信息字典（可选）
            syntax_style: 代码高亮样式
            
        Returns:
            PDF字节流
        """
        try:
            # 转换Markdown到HTML
            html_body = self._markdown_to_html(markdown_text)
            
            # 构建完整HTML
            full_html = self._build_full_html(html_body, title, meta_info)
            
            # 获取语法高亮CSS
            highlight_css = self._get_syntax_highlight_css(syntax_style)
            
            # 组合所有CSS
            combined_css = self.DEFAULT_CSS + "\n" + highlight_css
            if self.custom_css:
                combined_css += "\n" + self.custom_css
            
            # 创建HTML和CSS对象
            try:
                from weasyprint import HTML, CSS
            except Exception as e:
                raise RuntimeError("WeasyPrint 未可用或依赖缺失") from e
            html_obj = HTML(string=full_html)
            if self.font_config is not None:
                css_obj = CSS(string=combined_css, font_config=self.font_config)
            else:
                css_obj = CSS(string=combined_css)
            
            # 生成PDF
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                html_obj.write_pdf(
                    str(output_path),
                    stylesheets=[css_obj],
                    font_config=self.font_config if self.font_config is not None else None
                )
                logger.info(f"PDF已保存到: {output_path}")
                return output_path.read_bytes()
            else:
                # 返回字节流
                pdf_bytes = html_obj.write_pdf(
                    stylesheets=[css_obj],
                    font_config=self.font_config if self.font_config is not None else None
                )
                return pdf_bytes
        
        except Exception as e:
            logger.error(f"转换PDF失败: {e}", exc_info=True)
            raise
    
    async def convert_to_pdf_async(
        self,
        markdown_text: str,
        output_path: Optional[Path] = None,
        title: str = "辩论报告",
        meta_info: Optional[dict] = None,
        syntax_style: str = "github"
    ) -> bytes:
        """
        异步将Markdown转换为PDF
        
        Args:
            markdown_text: Markdown文本
            output_path: 输出文件路径（可选）
            title: 文档标题
            meta_info: 元信息字典（可选）
            syntax_style: 代码高亮样式
            
        Returns:
            PDF字节流
        """
        return await asyncio.to_thread(
            self.convert_to_pdf,
            markdown_text,
            output_path,
            title,
            meta_info,
            syntax_style
        )


# 便捷函数
async def markdown_to_pdf(
    markdown_text: str,
    output_path: Optional[Path] = None,
    title: str = "辩论报告",
    meta_info: Optional[dict] = None,
    custom_css: Optional[str] = None,
    syntax_style: str = "github"
) -> bytes:
    """
    便捷函数：将Markdown转换为PDF
    
    Args:
        markdown_text: Markdown文本
        output_path: 输出文件路径（可选）
        title: 文档标题
        meta_info: 元信息字典（可选）
        custom_css: 自定义CSS（可选）
        syntax_style: 代码高亮样式
        
    Returns:
        PDF字节流
    """
    converter = MarkdownToPdfConverter(custom_css=custom_css)
    return await converter.convert_to_pdf_async(
        markdown_text,
        output_path,
        title,
        meta_info,
        syntax_style
    )
