"""简报内容生成器"""
from __future__ import annotations

import json
import logging
from .ai_client import AIGatewayClient

logger = logging.getLogger(__name__)


class DigestGenerator:
    """按分类生成每日简报的 Markdown 内容"""

    def __init__(self, client: AIGatewayClient, prompt_template: str):
        self.client = client
        self.prompt_template = prompt_template

    def group_by_category(self, articles: list[dict]) -> dict[str, list[dict]]:
        """按分类分组文章"""
        grouped = {}
        for article in articles:
            cat = article.get("category") or "其他"
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(article)
        return grouped

    async def generate(
        self,
        articles: list[dict],
        date_str: str = "",
    ) -> str:
        """生成完整的 Markdown 简报"""
        grouped = self.group_by_category(articles)

        sections_md = []
        for category, items in grouped.items():
            items_text = json.dumps(
                [
                    {
                        "title": a["title"],
                        "url": a.get("url", ""),
                        "summary": a.get("summary", ""),
                        "source": a.get("source", ""),
                        "image_url": a.get("image_url", ""),
                    }
                    for a in items
                ],
                ensure_ascii=False,
                indent=2,
            )

            try:
                prompt = self.prompt_template.format(
                    category_name=category,
                    articles=items_text,
                )
                section_md = await self.client.chat(prompt)
                sections_md.append(section_md)
            except Exception as e:
                logger.error(f"生成 {category} 失败: {e}")
                # 降级方案：手动格式化
                fallback = f"## {category}\n\n"
                for i, a in enumerate(items, 1):
                    fallback += f"**{a['title']}**\n\n"
                    if a.get("image_url"):
                        fallback += f"![]({a['image_url']})\n\n"
                    fallback += f"{a.get('summary', '')}\n\n"
                    if a.get("url"):
                        fallback += f"[原文链接]({a['url']})\n\n"
                sections_md.append(fallback)

        # 组装完整简报
        header = f"# AI 早报\n\n"
        if date_str:
            header += f"**{date_str}**\n\n"
        header += "---\n\n"

        return header + "\n---\n\n".join(sections_md)
