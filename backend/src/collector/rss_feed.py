"""RSS 采集模块 - 仅采集当天文章，提取图像"""
from __future__ import annotations

import feedparser
import httpx
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import yaml

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """采集到的原始文章"""
    id: str
    title: str
    url: str
    source: str
    content: str = ""
    author: str = ""
    published: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    image_url: str = ""


def load_sources(config_path: str = "backend/src/collector/sources.yaml") -> list[dict]:
    """加载 RSS 源配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("sources", [])


def extract_images(html: str) -> tuple[str, str]:
    """从 HTML 内容中提取第一张图片和纯文本内容

    返回: (image_url, clean_text)
    """
    # 提取第一张图片
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html)
    image_url = img_match.group(1) if img_match else ""

    # 清理 HTML 标签
    text = re.sub(r'<[^>]+>', '', html)
    text = re.sub(r'\s+', ' ', text).strip()

    return image_url, text


def is_today(pub_date: Optional[datetime], max_age_hours: int = 48) -> bool:
    """判断文章是否在指定时间范围内

    Args:
        pub_date: 文章发布时间
        max_age_hours: 最大允许的小时数（默认48小时）
    """
    if pub_date is None:
        return True  # 没有日期信息也保留
    cutoff = datetime.now() - __import__('datetime', fromlist=['timedelta']).timedelta(hours=max_age_hours)
    return pub_date >= cutoff


async def fetch_rss(url: str, timeout: int = 30) -> feedparser.FeedParserDict:
    """异步获取 RSS 源"""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return feedparser.parse(resp.text)


async def collect_source(source: dict, max_articles: int = 10, max_age_hours: int = 48) -> list[Article]:
    """采集单个 RSS 源，仅保留指定时间范围内的文章"""
    name = source["name"]
    url = source["url"]
    category = source.get("category", "tech")

    logger.info(f"采集 RSS: {name} ({url})")

    try:
        feed = await fetch_rss(url)
    except Exception as e:
        logger.error(f"RSS 采集失败 {name}: {e}")
        return []

    articles = []
    for i, entry in enumerate(feed.entries[:max_articles]):
        article_id = entry.get("id") or entry.get("link") or f"{name}-{i}"

        pub_date = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                pub_date = datetime(*entry.published_parsed[:6])
            except (TypeError, ValueError):
                pass

        # 仅保留当天文章
        if not is_today(pub_date, max_age_hours):
            continue

        raw_content = entry.get("summary", "") or entry.get("description", "") or ""
        image_url, clean_content = extract_images(raw_content)

        articles.append(Article(
            id=article_id,
            title=entry.get("title", ""),
            url=entry.get("link", ""),
            source=name,
            content=clean_content,
            author=entry.get("author", ""),
            published=pub_date,
            tags=list(entry.get("tags", [])),
            image_url=image_url,
        ))

    logger.info(f"  -> 当天文章: {len(articles)} 篇来自 {name}")
    return articles


async def collect_all(sources: list[dict], max_articles: int = 10, max_age_hours: int = 48) -> list[Article]:
    """并发采集所有 RSS 源"""
    import asyncio

    tasks = [collect_source(s, max_articles, max_age_hours) for s in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"采集异常: {result}")
        elif isinstance(result, list):
            all_articles.extend(result)

    logger.info(f"当天总计采集到 {len(all_articles)} 篇文章")
    return all_articles
