"""定时任务调度"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_collect_job():
    """定时采集任务"""
    from collector import collect_all, load_sources
    from pathlib import Path

    sources = load_sources(
        str(Path(__file__).parent.parent.parent / "backend/src/collector/sources.yaml")
    )
    articles = await collect_all(sources)
    logger.info(f"定时采集完成: {len(articles)} 篇文章")


async def run_process_job():
    """定时处理任务"""
    logger.info("定时处理任务触发")


def setup_scheduler(config: dict, db, ai_client, summarizer, dedup_checker, scorer):
    """配置定时任务"""
    schedule_str = config.get("collector", {}).get("schedule", "0 8 * * *")
    parts = schedule_str.split()

    trigger = CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
        timezone="Asia/Shanghai",
    )

    scheduler.add_job(
        run_collect_job,
        trigger,
        id="collect_rss",
        name="RSS 采集",
        replace_existing=True,
    )

    # 处理后运行：采集后30分钟
    process_parts = parts.copy()
    process_hour = (int(parts[1]) + 1) % 24
    process_parts[1] = str(process_hour)

    scheduler.add_job(
        run_process_job,
        CronTrigger(
            minute=process_parts[0],
            hour=process_parts[1],
            day=process_parts[2],
            month=process_parts[3],
            day_of_week=process_parts[4],
            timezone="Asia/Shanghai",
        ),
        id="process_articles",
        name="AI 处理",
        replace_existing=True,
    )

    logger.info(f"定时任务已配置: 采集 {schedule_str}, 处理 {':'.join(process_parts[:2])}")


def start_scheduler():
    """启动调度器"""
    if not scheduler.running:
        scheduler.start()
        logger.info("调度器已启动")


def stop_scheduler():
    """停止调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("调度器已停止")
