"""
调度器模块 —— 基于 APScheduler AsyncIOScheduler

设计约定（P0 基础设施）：
- 显式使用 Asia/Shanghai 时区，避免容器/系统时区不一致导致提醒跑偏。
- 挂在 FastAPI lifespan 中启动/停止，见 app/main.py。
- uvicorn --reload 下可能重复实例化应用，这里有双重防护：
  1) 模块级单例，start_scheduler() 幂等（已在运行则直接返回）；
  2) 环境变量 HAMSTER_SCHEDULER_ENABLED=0 可整体关掉（调试/多实例场景）。
- P1 早报、P2 提醒扫描等任务在 register_jobs() 中注册。
"""

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# 显式指定业务时区：所有 cron 触发时间按上海时间解释
BUSINESS_TIMEZONE = "Asia/Shanghai"

# 模块级单例（uvicorn --reload 同进程重复导入时复用同一实例）
_scheduler: AsyncIOScheduler | None = None


def is_scheduler_enabled() -> bool:
    """环境变量开关：HAMSTER_SCHEDULER_ENABLED=0 时整体关闭调度器"""
    return os.environ.get("HAMSTER_SCHEDULER_ENABLED", "1").strip().lower() not in (
        "0", "false", "no",
    )


# ============================================================
# Job 定义
# ============================================================

async def _heartbeat() -> None:
    """心跳任务：每 6 小时打一条日志，证明调度器活着（P0 验证用）"""
    logger.info("⏰ 调度器心跳：运行中")


def register_jobs(scheduler: AsyncIOScheduler) -> None:
    """
    注册不依赖数据库配置的固定任务。
    早报任务依赖 DB 设置，由 configure_morning_report_job() 单独挂载。
    """
    scheduler.add_job(_heartbeat, IntervalTrigger(hours=6), id="heartbeat",
                      replace_existing=True)
    # 提醒扫描：同步库存事件 + 推送到点提醒（每 30 分钟）
    scheduler.add_job(_run_reminder_scan, IntervalTrigger(minutes=30),
                      id="reminder_scan", replace_existing=True)


async def _run_reminder_scan() -> None:
    """提醒扫描 job 入口（异常兜底，不让调度器挂掉）"""
    try:
        from app.services.event_service import scan_due_reminders, sync_inventory_events
        await sync_inventory_events()
        await scan_due_reminders()
    except Exception as e:
        logger.error(f"提醒扫描执行异常: {e}")


async def configure_morning_report_job(scheduler: AsyncIOScheduler) -> None:
    """
    按 app_settings 中的早报配置挂载/移除每日早报任务。
    - enabled=True：CronTrigger(hour, minute, Asia/Shanghai)，默认 8:00
    - enabled=False：移除任务（早报功能整体可关闭）
    """
    from app.services.morning_report import load_settings

    settings = await load_settings()
    job_id = "morning_report"

    if settings.get("enabled"):
        scheduler.add_job(
            _run_morning_report,
            CronTrigger(hour=settings["hour"], minute=settings["minute"],
                        timezone=BUSINESS_TIMEZONE),
            id=job_id,
            replace_existing=True,
        )
        logger.info(
            f"📮 每日早报任务已挂载：每天 {settings['hour']:02d}:{settings['minute']:02d}（{BUSINESS_TIMEZONE}）"
        )
    else:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        logger.info("🔕 每日早报已关闭，未挂载定时任务")


async def _run_morning_report() -> None:
    """早报 job 入口：先同步事件（保证早报事件数据新鲜），再生成发送（异常兜底）"""
    try:
        from app.services.event_service import sync_inventory_events
        await sync_inventory_events()
    except Exception as e:
        logger.error(f"早报前事件同步失败（继续生成早报）: {e}")
    try:
        from app.services.morning_report import scheduled_morning_report
        await scheduled_morning_report()
    except Exception as e:
        logger.error(f"每日早报执行异常: {e}")


async def reschedule_morning_report() -> None:
    """早报配置变更后重新挂载定时任务（供配置接口调用）"""
    scheduler = get_scheduler()
    if scheduler is None or not scheduler.running:
        logger.info("调度器未运行，早报配置将在下次启动时生效")
        return
    await configure_morning_report_job(scheduler)


# ============================================================
# 启动 / 停止（供 lifespan 调用）
# ============================================================

async def start_scheduler() -> AsyncIOScheduler | None:
    """
    启动调度器（幂等）。
    返回调度器实例；被环境变量关闭时返回 None。
    """
    global _scheduler

    if not is_scheduler_enabled():
        logger.info("🔕 调度器已通过环境变量 HAMSTER_SCHEDULER_ENABLED=0 关闭")
        return None

    if _scheduler is not None and _scheduler.running:
        # uvicorn --reload / 多次 lifespan 启动防护
        logger.info("调度器已在运行，跳过重复启动")
        return _scheduler

    scheduler = AsyncIOScheduler(timezone=BUSINESS_TIMEZONE)
    register_jobs(scheduler)
    scheduler.start()
    _scheduler = scheduler

    # 早报任务依赖数据库配置，启动后单独挂载（失败不影响调度器本身）
    try:
        await configure_morning_report_job(scheduler)
    except Exception as e:
        logger.error(f"挂载每日早报任务失败（下次启动重试）: {e}")
    logger.info(f"📅 调度器已启动（时区: {BUSINESS_TIMEZONE}，任务数: {len(scheduler.get_jobs())}）")
    return scheduler


async def stop_scheduler() -> None:
    """停止调度器（lifespan 关闭时调用），等待正在执行的任务收尾"""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("📅 调度器已停止")
    _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    """获取当前调度器实例（未启动返回 None）"""
    return _scheduler
