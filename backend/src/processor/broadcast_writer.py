"""口播稿生成器 - 为视频生成结构化的播报脚本"""
from __future__ import annotations

import json
import logging
from typing import Optional

from .ai_client import AIGatewayClient

logger = logging.getLogger(__name__)


class BroadcastWriter:
    """根据文章列表生成视频口播稿

    输出结构:
    {
        "opening":  str,          # 开场白 100-150字
        "items": [
            {"title": str, "script": str},  # 每条新闻 2-3 句
        ],
        "closing":  str,          # 结尾总结 50-80字
    }
    """

    def __init__(
        self,
        client: AIGatewayClient,
        broadcast_prompt: str,
        item_prompt: str,
    ):
        self.client = client
        self.broadcast_prompt = broadcast_prompt
        self.item_prompt = item_prompt

    async def generate_full_script(
        self,
        articles: list[dict],
        date_str: str = "",
    ) -> dict:
        """生成完整口播稿（开场 + 逐条 + 结尾）"""
        articles_text = json.dumps(
            [
                {
                    "title": a.get("title", ""),
                    "summary": a.get("summary", ""),
                    "category": a.get("category", ""),
                    "source": a.get("source", ""),
                    "keywords": a.get("keywords", "[]"),
                }
                for a in articles
            ],
            ensure_ascii=False,
            indent=2,
        )

        try:
            prompt = self.broadcast_prompt.format(articles=articles_text)
            raw = await self.client.chat(prompt)
            segments = self._parse_json_array(raw)

            if segments and len(segments) >= 3:
                opening = segments[0]
                closing = segments[-1]
                item_scripts = segments[1:-1]

                items = []
                for i, script in enumerate(item_scripts):
                    title = articles[i]["title"] if i < len(articles) else ""
                    items.append({"title": title, "script": script})

                return {
                    "opening": opening,
                    "items": items,
                    "closing": closing,
                }
        except Exception as e:
            logger.warning(f"完整口播稿生成失败，回退到逐条生成: {e}")

        return await self._generate_fallback(articles, date_str)

    async def generate_item_script(self, article: dict) -> str:
        """为单条文章生成播报脚本"""
        try:
            prompt = self.item_prompt.format(
                title=article.get("title", ""),
                summary=article.get("summary", ""),
                keywords=article.get("keywords", ""),
            )
            return await self.client.chat(prompt)
        except Exception as e:
            logger.error(f"条目口播稿生成失败: {e}")
            return article.get("summary", article.get("title", ""))

    async def _generate_fallback(
        self,
        articles: list[dict],
        date_str: str,
    ) -> dict:
        """逐条生成口播稿（作为整体生成失败的后备方案）"""
        import asyncio

        opening = f"大家好，欢迎收看今天的AI早报。今天是{date_str}，我们为大家精选了{len(articles)}条AI科技领域的最新资讯，一起来看看吧。"
        closing = "以上就是今天的全部内容。感谢大家的观看，如果觉得有用的话请点个关注，我们明天再见！"

        tasks = [self.generate_item_script(a) for a in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        items = []
        for i, result in enumerate(results):
            title = articles[i].get("title", "")
            if isinstance(result, Exception):
                script = articles[i].get("summary", title)
            else:
                script = result
            items.append({"title": title, "script": script})

        return {"opening": opening, "items": items, "closing": closing}

    @staticmethod
    def _parse_json_array(text: str) -> Optional[list]:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
