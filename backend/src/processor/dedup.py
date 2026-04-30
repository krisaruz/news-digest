"""去重检测"""
from __future__ import annotations

import logging
from .ai_client import AIGatewayClient

logger = logging.getLogger(__name__)


class DedupChecker:
    """检测文章是否与已有内容重复"""

    def __init__(self, client: AIGatewayClient, prompt_template: str):
        self.client = client
        self.prompt_template = prompt_template

    async def check_duplicate(
        self,
        new_title: str,
        new_summary: str,
        existing_articles: list[dict],
    ) -> bool:
        """检查是否重复，返回 True 表示重复"""
        if not existing_articles:
            return False

        # 先用简单的标题相似度做初筛
        for article in existing_articles:
            if self._title_similar(new_title, article["title"]):
                return True

        # 再用 AI 做深度判断
        existing_text = "\n".join(
            f"- {a['title']}: {a.get('summary', '')}"
            for a in existing_articles[:10]  # 最多对比10篇
        )

        prompt = self.prompt_template.format(
            new_title=new_title,
            new_summary=new_summary,
            existing_articles=existing_text,
        )

        try:
            result = await self.client.chat(prompt)
            return "DUPLICATE" in result.upper()
        except Exception as e:
            logger.error(f"去重检测失败: {e}")
            return False

    def _title_similar(self, title1: str, title2: str) -> bool:
        """简单的标题相似度判断"""
        # 去除标点、空格后完全相同
        import re
        def normalize(t):
            return re.sub(r'[^\w\u4e00-\u9fff]', '', t).lower()
        return normalize(title1) == normalize(title2) and len(normalize(title1)) > 5

    async def check_batch(
        self, articles: list[dict], existing_articles: list[dict]
    ) -> list[dict]:
        """批量去重检测"""
        import asyncio

        tasks = []
        for article in articles:
            tasks.append(self.check_duplicate(
                article["title"],
                article.get("summary", ""),
                existing_articles,
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        filtered = []
        for i, article in enumerate(articles):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"文章 {article['id']} 去重检测失败: {result}")
                filtered.append(article)  # 保留
            elif result:
                logger.info(f"文章 {article['id']} 被去重: {article['title']}")
            else:
                filtered.append(article)

        return filtered
