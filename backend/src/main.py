"""每日 AI 科技简报 - FastAPI 应用"""
from __future__ import annotations

import logging
import uuid
import yaml
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from storage import DigestDB
from collector import collect_all, collect_source, load_sources
from processor import (
    AIGatewayClient,
    Summarizer,
    DedupChecker,
    Scorer,
    KeywordExtractor,
    DigestGenerator,
    categorize_article,
    TTSClient,
    VideoPipeline,
)
from publisher import MultiPlatformExporter

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
PROMPTS_PATH = Path(__file__).parent / "processor" / "prompts.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
    PROMPTS = yaml.safe_load(f)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- Global state ----
db: DigestDB
ai_client: AIGatewayClient
summarizer: Summarizer
dedup_checker: DedupChecker
scorer: Scorer
keyword_extractor: KeywordExtractor
digest_generator: DigestGenerator
md_exporter: MultiPlatformExporter
video_pipeline: Optional[VideoPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, ai_client, summarizer, dedup_checker, scorer
    global keyword_extractor, digest_generator, md_exporter, video_pipeline

    logger.info("Initializing services...")

    db = DigestDB(
        db_path=str(PROJECT_ROOT / CONFIG["storage"]["db_path"])
    )
    await db.init()

    ai_client = AIGatewayClient(CONFIG["ai_gateway"])

    summarizer = Summarizer(ai_client, PROMPTS["summarize"])
    dedup_checker = DedupChecker(ai_client, PROMPTS["dedup"])
    scorer = Scorer(ai_client, PROMPTS["scoring"])
    keyword_extractor = KeywordExtractor(ai_client, PROMPTS["keywords"])
    digest_generator = DigestGenerator(ai_client, PROMPTS["generate_digest"])

    md_exporter = MultiPlatformExporter(
        markdown_dir=str(PROJECT_ROOT / CONFIG["output"]["markdown_dir"]),
        html_dir=str(PROJECT_ROOT / CONFIG["output"]["html_dir"]),
    )

    if CONFIG.get("tts_gateway"):
        video_pipeline = VideoPipeline(
            tts_config=CONFIG["tts_gateway"],
            ai_client=ai_client,
            prompts=PROMPTS,
            output_dir=str(PROJECT_ROOT / "data/output/video"),
        )
        logger.info("视频流水线已初始化（含口播稿生成）")
    else:
        logger.warning("TTS Gateway 未配置，视频功能不可用")

    logger.info("Services initialized.")
    yield


app = FastAPI(title="AI 科技简报", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Models ----
class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    content: Optional[str] = None


class IssueRequest(BaseModel):
    title: str = ""


# ---- Collector API ----
@app.post("/api/collect/trigger")
async def trigger_collect():
    sources = load_sources(str(PROJECT_ROOT / "backend/src/collector/sources.yaml"))
    max_articles = CONFIG["collector"].get("max_articles_per_source", 10)
    max_age_hours = CONFIG["collector"].get("max_age_hours", 48)
    articles = await collect_all(sources, max_articles, max_age_hours)

    inserted = 0
    skipped = 0
    for article in articles:
        article_id = article.id if article.id else str(uuid.uuid4())
        row = {
            "id": article_id,
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "content": article.content,
            "image_url": article.image_url if hasattr(article, 'image_url') else "",
        }
        result = await db.insert_article(row)
        if result:
            inserted += 1
        else:
            skipped += 1

    return {
        "status": "ok",
        "total": len(articles),
        "inserted": inserted,
        "skipped": skipped,
    }


@app.post("/api/collect/clipper")
async def receive_clipper(data: dict):
    article_id = str(uuid.uuid4())
    row = {
        "id": article_id,
        "title": data.get("title", ""),
        "url": data.get("url", ""),
        "source": data.get("source", "clipper"),
        "content": data.get("content", ""),
    }
    await db.insert_article(row)
    return {"status": "ok", "id": article_id}


@app.get("/api/collect/stats")
async def collect_stats():
    pending = await db.get_pending_articles()
    recent = await db.get_recent_articles(hours=24)
    return {"pending": len(pending), "last_24h": len(recent)}


# ---- Processor API ----
@app.post("/api/process/run")
async def run_pipeline():
    pending = await db.get_pending_articles()
    if not pending:
        return {"status": "ok", "message": "没有待处理的文章"}

    logger.info(f"开始处理 {len(pending)} 篇文章")

    recent = await db.get_recent_articles(
        hours=CONFIG["processor"]["dedup_window_hours"]
    )
    existing_keywords = await db.get_all_keywords()

    import asyncio
    results = await asyncio.gather(
        summarizer.summarize_batch(pending),
        keyword_extractor.extract_batch(pending, existing_keywords),
        return_exceptions=True,
    )
    if isinstance(results[0], Exception):
        logger.error(f"摘要生成失败: {results[0]}")
    if isinstance(results[1], Exception):
        logger.error(f"关键词提取失败: {results[1]}")

    filtered = await dedup_checker.check_batch(pending, recent)
    scored = await scorer.score_batch(filtered)

    threshold = CONFIG["processor"].get("score_threshold", 0.5)
    final = scorer.filter_by_score(scored, threshold)

    for article in final:
        article["category"] = categorize_article(article)

    updated = 0
    for article in final:
        updates = {
            "summary": article.get("summary", ""),
            "keywords": article.get("keywords_json", "[]"),
            "score": article.get("score", 0.5),
            "category": article.get("category", ""),
            "status": "screened",
        }
        await db.update_article(article["id"], updates)
        updated += 1

    final_ids = {a["id"] for a in final}
    for article in pending:
        if article["id"] not in final_ids:
            await db.update_article(article["id"], {"status": "rejected"})

    return {
        "status": "ok",
        "total_processed": len(pending),
        "passed": len(final),
        "rejected": len(pending) - len(final),
    }


# ---- Articles API ----
@app.get("/api/articles/pending")
async def get_pending():
    return await db.get_pending_articles()


@app.get("/api/articles/{article_id}")
async def get_article(article_id: str):
    article = await db.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@app.put("/api/articles/{article_id}")
async def update_article(article_id: str, update: ArticleUpdate):
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    await db.update_article(article_id, updates)
    return {"status": "ok"}


# ---- Issue API ----
@app.post("/api/issue/generate")
async def generate_issue(req: IssueRequest = IssueRequest()):
    approved = await db.get_approved_articles()
    if not approved:
        approved = await db.get_pending_articles()
        for a in approved:
            await db.update_article(a["id"], {"status": "approved"})

    if not approved:
        raise HTTPException(status_code=404, detail="No articles available")

    approved.sort(key=lambda a: a.get("score", 0), reverse=True)
    max_items = CONFIG["processor"].get("max_items_per_issue", 10)
    approved = approved[:max_items]

    logger.info(f"精选 {len(approved)} 篇文章生成简报")

    sections = md_exporter.group_articles(approved)
    date_str = datetime.now().strftime("%Y年%m月%d日")
    issue_title = req.title or f"第 {datetime.now().strftime('%Y%m%d')} 期"

    issue_id = await db.create_issue(
        title=issue_title,
        content={
            "date": date_str,
            "articles": [
                {"id": a["id"], "title": a["title"], "category": a.get("category")}
                for a in approved
            ],
            "sections": {
                k: [{"id": a["id"]} for a in v]
                for k, v in sections.items()
            },
        },
    )

    return {
        "status": "ok",
        "issue_id": issue_id,
        "total_articles": len(approved),
        "sections": list(sections.keys()),
    }


@app.get("/api/issue/{issue_id}")
async def get_issue(issue_id: int):
    issue = await db.get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@app.get("/api/issues")
async def list_issues():
    return await db.list_issues()


@app.post("/api/issue/{issue_id}/export")
async def export_issue(issue_id: int, platform: str = "wechat"):
    issue = await db.get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    import json
    content = json.loads(issue["content"]) if issue["content"] else {}

    article_ids = [
        a["id"]
        for section in content.get("sections", {}).values()
        for a in section
    ]

    articles = []
    for aid in article_ids:
        article = await db.get_article(aid)
        if article:
            articles.append(article)

    sections = md_exporter.group_articles(articles)
    date_str = content.get("date", datetime.now().strftime("%Y年%m月%d日"))

    if platform == "wechat":
        html = md_exporter.export_wechat_html(issue_id, date_str, sections)
        return {"platform": "wechat", "content": html}
    elif platform == "zhihu":
        md = md_exporter.export_zhihu(issue_id, date_str, sections)
        return {"platform": "zhihu", "content": md}
    else:
        md = md_exporter.export_markdown(issue_id, date_str, sections)
        return {"platform": "markdown", "content": md}


@app.post("/api/issue/{issue_id}/publish")
async def publish_issue(issue_id: int):
    issue = await db.get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    await db.update_issue(issue_id, {
        "status": "published",
        "published_at": datetime.now().isoformat(),
    })
    return {"status": "ok", "message": "Issue marked as published"}


# ---- Video API ----
@app.post("/api/issue/{issue_id}/video")
async def generate_video(issue_id: int):
    """生成视频（V2: 口播稿 + 句级 TTS + SRT 字幕 + 转场）"""
    if not video_pipeline:
        raise HTTPException(status_code=503, detail="视频功能未启用")

    issue = await db.get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    import json
    content = json.loads(issue["content"]) if issue["content"] else {}

    article_ids = [
        a["id"]
        for section in content.get("sections", {}).values()
        for a in section
    ]

    articles = []
    for aid in article_ids:
        article = await db.get_article(aid)
        if article:
            articles.append(article)

    if not articles:
        raise HTTPException(status_code=404, detail="No articles for this issue")

    date_str = content.get("date", datetime.now().strftime("%Y年%m月%d日"))

    video_path = await video_pipeline.generate_video(
        issue_number=issue_id,
        date_str=date_str,
        articles=articles,
    )

    if video_path:
        return {
            "status": "ok",
            "video_path": video_path,
            "article_count": len(articles),
        }
    else:
        raise HTTPException(status_code=500, detail="视频生成失败")


# ---- Pipeline (full flow) ----
@app.post("/api/pipeline/run")
async def run_full_pipeline():
    collect_result = await trigger_collect()
    process_result = await run_pipeline()
    issue_result = await generate_issue()
    return {
        "status": "ok",
        "collect": collect_result,
        "process": process_result,
        "issue": issue_result,
    }
