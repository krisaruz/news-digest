"""自动分类器 - 根据关键词和来源自动归类文章"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 分类规则：关键词 -> 分类
CATEGORY_KEYWORDS = {
    "AI 相关": [
        "模型", "LLM", "AI", "智能体", "GPT", "Claude", "Gemini", "Qwen",
        "大模型", "训练", "推理", "开源", "Agent", "RAG",
        "OpenAI", "Anthropic", "DeepSeek", "Kimi", "智谱",
    ],
    "工具": [
        "工具", "软件", "开源", "发布", "上线", "工具", "CLI",
        "平台", "API", "SDK", "Browser", "Extension",
    ],
    "科技动态": [
        "公司", "投资", "融资", "收购", "裁员", "发布", "产品",
        "融资", "估值", "IPO", "上市",
    ],
    "文章推荐": [
        "文章", "博客", "研究", "论文", "博客", "教程", "指南",
    ],
    "资源": [
        "数据集", "数据集", "教程", "指南", "文档", "课程",
    ],
}

# 来源到分类的映射
SOURCE_CATEGORY = {
    "GitHub Trending": "工具",
    "Product Hunt": "工具",
}


def categorize_article(article: dict) -> str:
    """根据关键词和来源自动分类文章"""
    keywords = article.get("keywords", [])
    source = article.get("source", "")
    title = article.get("title", "")

    # 先检查来源映射
    for source_pattern, category in SOURCE_CATEGORY.items():
        if source_pattern in source:
            return category

    # 根据关键词分类
    all_text = " ".join(keywords) + " " + title
    for category, kw_list in CATEGORY_KEYWORDS.items():
        for kw in kw_list:
            if kw.lower() in all_text.lower():
                return category

    return "科技动态"
