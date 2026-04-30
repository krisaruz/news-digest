"""关键词提取"""
from __future__ import annotations

import json
import logging
from .ai_client import AIGatewayClient

logger = logging.getLogger(__name__)


class KeywordExtractor:
    """从文章中提取关键词"""

    def __init__(self, client: AIGatewayClient, prompt_template: str):
        self.client = client
        self.prompt_template = prompt_template

    async def extract(self, title: str, content: str, existing_keywords: list[str]) -> list[str]:
        prompt = self.prompt_template.format(
            title=title,
            content=content[:2000],
            existing_keywords=", ".join(existing_keywords[-30:]),  # 最近的30个
        )
        try:
            result = await self.client.chat_json(prompt)
            if isinstance(result, list):
                return [kw for kw in result if isinstance(kw, str)]
            return []
        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return []

    async def extract_batch(self, articles: list[dict], existing_keywords: list[str]) -> list[dict]:
        """批量提取关键词"""
        import asyncio

        tasks = []
        for article in articles:
            tasks.append(self.extract(
                article["title"], article["content"], existing_keywords
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, article in enumerate(articles):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"文章 {article['id']} 关键词提取失败: {result}")
                article["keywords"] = []
            else:
                article["keywords"] = result
                article["keywords_json"] = json.dumps(result, ensure_ascii=False)

        return articles
