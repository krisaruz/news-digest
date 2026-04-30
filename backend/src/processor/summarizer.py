"""摘要生成"""
from __future__ import annotations

import logging
from .ai_client import AIGatewayClient

logger = logging.getLogger(__name__)


class Summarizer:
    """为文章生成50字以内的中文摘要"""

    def __init__(self, client: AIGatewayClient, prompt_template: str):
        self.client = client
        self.prompt_template = prompt_template

    async def summarize(self, title: str, content: str) -> str:
        prompt = self.prompt_template.format(
            title=title,
            content=content[:2000],  # 截断过长内容
        )
        try:
            summary = await self.client.chat(prompt)
            return summary[:50]
        except Exception as e:
            logger.error(f"摘要生成失败: {e}")
            return ""

    async def summarize_batch(self, articles: list[dict]) -> list[dict]:
        """批量生成摘要"""
        import asyncio

        tasks = []
        for article in articles:
            tasks.append(self.summarize(article["title"], article["content"]))

        summaries = await asyncio.gather(*tasks, return_exceptions=True)

        for i, article in enumerate(articles):
            result = summaries[i]
            if isinstance(result, Exception):
                logger.error(f"文章 {article['id']} 摘要失败: {result}")
                article["summary"] = ""
            else:
                article["summary"] = result

        return articles
