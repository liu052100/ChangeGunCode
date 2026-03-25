import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from models.database import ScrapeLog, get_session
from scraper.crafting import CraftingScraper
from scraper.weapons import WeaponScraper

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def run_full_scrape():
    session = get_session()
    log = ScrapeLog(task_name="full_scrape", status="running")
    session.add(log)
    session.commit()
    log_id = log.id
    session.close()

    total = 0
    try:
        with WeaponScraper(Config.BASE_URL) as ws:
            logger.info("=== Scraping weapon categories ===")
            total += ws.scrape_categories()
            logger.info("=== Scraping weapon list ===")
            total += ws.scrape_weapon_list()
            logger.info("=== Updating category mappings ===")
            ws.scrape_weapon_categories_mapping()
            logger.info("=== Scraping all gun codes ===")
            total += ws.scrape_all_gun_codes()

        with CraftingScraper(Config.BASE_URL) as cs:
            logger.info("=== Scraping crafting stations ===")
            total += cs.scrape_crafting()
            logger.info("=== Scraping events ===")
            total += cs.scrape_events()

        session = get_session()
        log = session.query(ScrapeLog).get(log_id)
        log.status = "success"
        log.items_scraped = total
        log.finished_at = datetime.now()
        session.commit()
        session.close()
        logger.info("=== Full scrape completed: %d items ===", total)

    except Exception as e:
        logger.exception("Full scrape failed")
        session = get_session()
        log = session.query(ScrapeLog).get(log_id)
        log.status = "failed"
        log.error_message = str(e)
        log.finished_at = datetime.now()
        session.commit()
        session.close()


def init_scheduler():
    scheduler.add_job(
        run_full_scrape,
        trigger="cron",
        hour=Config.SCRAPE_CRON_HOUR,
        minute=Config.SCRAPE_CRON_MINUTE,
        id="full_scrape",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Scheduler started: full scrape at %02d:%02d daily", Config.SCRAPE_CRON_HOUR, Config.SCRAPE_CRON_MINUTE)
