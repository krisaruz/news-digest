"""智能打分"""
from __future__ import annotations

import logging
from .ai_client import AIGatewayClient

logger = logging.getLogger(__name__)


class Scorer:
    """对文章的信息价值进行打分"""

    def __init__(self, client: AIGatewayClient, prompt_template: str):
        self.client = client
        self.prompt_template = prompt_template

    async def score(self, title: str, summary: str) -> float:
        prompt = self.prompt_template.format(
            title=title,
            summary=summary,
        )
        try:
            result = await self.client.chat(prompt)
            # 提取数字
            import re
            match = re.search(r'[\d.]+', result)
            if match:
                score = float(match.group())
                return max(0.0, min(1.0, score))
            return 0.5  # 默认中间值
        except Exception as e:
            logger.error(f"打分失败: {e}")
            return 0.5

    async def score_batch(self, articles: list[dict]) -> list[dict]:
        """批量打分"""
        import asyncio

        tasks = []
        for article in articles:
            tasks.append(self.score(
                article["title"],
                article.get("summary", ""),
            ))

        scores = await asyncio.gather(*tasks, return_exceptions=True)

        for i, article in enumerate(articles):
            result = scores[i]
            if isinstance(result, Exception):
                logger.error(f"文章 {article['id']} 打分失败: {result}")
                article["score"] = 0.5
            else:
                article["score"] = result

        return articles

    def filter_by_score(self, articles: list[dict], threshold: float = 0.5) -> list[dict]:
        """过滤低于阈值的文章"""
        filtered = [a for a in articles if a.get("score", 0) >= threshold]
        removed = len(articles) - len(filtered)
        if removed > 0:
            logger.info(f"打分过滤: {removed} 篇文章被排除（低于 {threshold}）")
        return filtered
