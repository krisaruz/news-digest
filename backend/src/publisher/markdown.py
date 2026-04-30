"""多平台输出生成器"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


class MultiPlatformExporter:
    """支持多平台格式导出：微信公众号、知乎、通用 Markdown"""

    def __init__(
        self,
        markdown_dir: str = "data/output/markdown",
        html_dir: str = "data/output/html",
    ):
        self.markdown_dir = Path(markdown_dir)
        self.html_dir = Path(html_dir)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.html_dir.mkdir(parents=True, exist_ok=True)

    def group_articles(self, articles: list[dict]) -> dict[str, list[dict]]:
        """按 category 分组文章"""
        grouped = {}
        for article in articles:
            cat = article.get("category") or "其他"
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(article)
        return grouped

    def _render_sections(self, sections: dict[str, list[dict]], platform: str) -> str:
        """渲染所有 section"""
        lines = []
        for section_name, items in sections.items():
            if not items:
                continue

            if platform == "wechat":
                lines.append(f'<h2 style="color:#07C160;border-left:4px solid #07C160;padding-left:12px;font-size:18px;">{section_name}</h2>')
            elif platform == "zhihu":
                lines.append(f"## {section_name}")
            else:
                lines.append(f"## {section_name}")

            for i, item in enumerate(items, 1):
                title = self._escape(item["title"]) if platform == "wechat" else item["title"]

                if platform == "wechat":
                    lines.append(f'<p style="font-weight:bold;font-size:16px;margin-top:16px;">{i}、{title}</p>')
                else:
                    lines.append(f"**{i}、{title}**")
                    lines.append("")

                if item.get("image_url"):
                    if platform == "wechat":
                        lines.append(
                            f'<p><img src="{item["image_url"]}" style="max-width:100%;"></p>'
                        )
                    else:
                        lines.append(f"![]({item['image_url']})")
                        lines.append("")

                if item.get("summary"):
                    summary = self._escape(item["summary"]) if platform == "wechat" else item["summary"]
                    if platform == "wechat":
                        lines.append(f'<p style="color:#666;font-size:14px;line-height:1.8;">{summary}</p>')
                    else:
                        lines.append(summary)
                        lines.append("")

                if item.get("url"):
                    if platform == "wechat":
                        lines.append(
                            f'<p style="font-size:12px;color:#576b95;">原文链接：<a href="{item["url"]}">{item["url"]}</a></p>'
                        )
                    elif platform == "zhihu":
                        lines.append(f"[原文链接]({item['url']})")
                        lines.append("")
                    else:
                        lines.append(f"[原文链接]({item['url']})")
                        lines.append("")

                lines.append("")

        return "\n".join(lines)

    def export_markdown(
        self,
        issue_number: int,
        date_str: str,
        sections: dict[str, list[dict]],
        title: str = "AI 早报",
    ) -> str:
        """通用 Markdown 格式"""
        lines = [f"# {title}（第 {issue_number} 期）", "", f"**{date_str}**", "", "---", ""]
        lines.append(self._render_sections(sections, "markdown"))
        lines.extend(["", "---", "", f"*第 {issue_number} 期 | {date_str}*", ""])

        content = "\n".join(lines)
        self._save(issue_number, "md", content)
        return content

    def export_wechat_html(
        self,
        issue_number: int,
        date_str: str,
        sections: dict[str, list[dict]],
        title: str = "AI 早报",
    ) -> str:
        """微信公众号 HTML 格式（带自定义样式）"""
        style = """
<style>
.digest-body {
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
    line-height: 1.8;
    color: #333;
    padding: 16px;
    max-width: 677px;
    margin: 0 auto;
}
.digest-header {
    font-size: 22px;
    font-weight: bold;
    text-align: center;
    color: #1a1a1a;
    border-bottom: 2px solid #07C160;
    padding-bottom: 12px;
    margin-bottom: 20px;
}
.digest-footer {
    font-size: 12px;
    color: #999;
    text-align: center;
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid #eee;
}
</style>
"""
        body_lines = [f'<div class="digest-body">']
        body_lines.append(f'<div class="digest-header">{title}（第 {issue_number} 期）</div>')
        body_lines.append(f'<p style="text-align:center;color:#999;font-size:14px;">{date_str}</p>')
        body_lines.append(self._render_sections(sections, "wechat"))
        body_lines.append(f'<div class="digest-footer">第 {issue_number} 期 | {date_str}</div>')
        body_lines.append("</div>")

        html = style + "\n".join(body_lines)
        self._save(issue_number, "wechat.html", html)
        return html

    def export_zhihu(
        self,
        issue_number: int,
        date_str: str,
        sections: dict[str, list[dict]],
        title: str = "AI 早报",
    ) -> str:
        """知乎格式（Markdown + 目录）"""
        lines = [f"# {title}（第 {issue_number} 期）", "", f"**{date_str}**", ""]

        # 目录
        lines.append("## 目录\n")
        for section_name in sections.keys():
            lines.append(f"- [{section_name}](#{section_name})")
        lines.append("")

        lines.append(self._render_sections(sections, "zhihu"))
        lines.extend(["", "---", "", f"*第 {issue_number} 期 | {date_str}*", ""])

        content = "\n".join(lines)
        self._save(issue_number, "zhihu.md", content)
        return content

    def _save(self, issue_number: int, suffix: str, content: str):
        filename = f"issue-{issue_number}.{suffix}"
        if suffix == "md":
            filepath = self.markdown_dir / filename
        else:
            filepath = self.html_dir / filename
        filepath.write_text(content, encoding="utf-8")

    @staticmethod
    def _escape(text: str) -> str:
        """转义 HTML 特殊字符"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
