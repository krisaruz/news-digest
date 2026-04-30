"""AI 科技简报 - SQLite 存储层"""
from __future__ import annotations

import aiosqlite
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class DigestDB:
    """SQLite 数据库操作封装"""

    def __init__(self, db_path: str = "data/digest.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path

    async def init(self):
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE,
                    source TEXT,
                    content TEXT,
                    summary TEXT,
                    keywords TEXT DEFAULT '[]',
                    score REAL DEFAULT 0,
                    category TEXT,
                    status TEXT DEFAULT 'new',
                    image_url TEXT DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    published_at DATETIME,
                    status TEXT DEFAULT 'draft',
                    content TEXT
                )
            """)
            await db.commit()

    # ---- Articles CRUD ----

    async def insert_article(self, article: dict) -> str:
        """插入一篇文章，如果 url 已存在则跳过"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """INSERT INTO articles
                       (id, title, url, source, content, status)
                       VALUES (?, ?, ?, ?, ?, 'new')""",
                    (
                        article["id"],
                        article["title"],
                        article.get("url", ""),
                        article.get("source", ""),
                        article.get("content", ""),
                    ),
                )
                await db.commit()
                return article["id"]
            except aiosqlite.IntegrityError:
                return ""  # URL 已存在，跳过

    async def get_article(self, article_id: str) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM articles WHERE id = ?", (article_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_article(self, article_id: str, updates: dict) -> bool:
        """更新文章字段"""
        fields = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [article_id]
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                f"UPDATE articles SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values,
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_pending_articles(self) -> list[dict]:
        """获取待审核文章 (status = 'new' or 'screened')"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM articles WHERE status IN ('new', 'screened') ORDER BY created_at DESC"
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def get_approved_articles(self) -> list[dict]:
        """获取已通过审核的文章"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM articles WHERE status = 'approved' ORDER BY score DESC"
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def get_recent_articles(self, hours: int = 72) -> list[dict]:
        """获取最近 N 小时的文章（用于去重）"""
        cutoff = datetime.now() - timedelta(hours=hours)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM articles WHERE created_at >= ? ORDER BY created_at DESC",
                (cutoff.isoformat(),),
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def get_all_keywords(self) -> list[str]:
        """从已分类文章中提取所有关键词"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT DISTINCT keywords FROM articles WHERE keywords IS NOT NULL AND keywords != '[]'"
            ) as cursor:
                rows = await cursor.fetchall()
                keywords = set()
                for (kw_json,) in rows:
                    try:
                        keywords.update(json.loads(kw_json))
                    except (json.JSONDecodeError, TypeError):
                        pass
                return sorted(keywords)

    # ---- Issues CRUD ----

    async def create_issue(self, title: str, content: dict) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO issues (title, content) VALUES (?, ?)",
                (title, json.dumps(content, ensure_ascii=False)),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_issue(self, issue_id: int) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM issues WHERE id = ?", (issue_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_issue(self, issue_id: int, updates: dict) -> bool:
        fields = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [issue_id]
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"UPDATE issues SET {fields} WHERE id = ?", values)
            await db.commit()
            return cursor.rowcount > 0

    async def list_issues(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM issues ORDER BY created_at DESC"
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]
