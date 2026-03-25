import logging
import re

from models.database import CraftingStation, Event, get_session
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)


class CraftingScraper(BaseScraper):
    def scrape_crafting(self):
        soup = self.fetch("/")
        if not soup:
            return 0
        session = get_session()
        count = 0
        try:
            session.query(CraftingStation).delete()
            station_names = ["技术中心", "工作台", "制药台", "防具台"]
            for station_name in station_names:
                item = self._extract_station_data(soup, station_name)
                if item:
                    session.add(CraftingStation(
                        station_name=station_name,
                        item_name=item["item_name"],
                        hourly_profit=item["hourly_profit"],
                        item_image_url=item.get("image_url"),
                    ))
                    count += 1
            session.commit()
            logger.info("Scraped %d crafting stations", count)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return count

    def scrape_events(self):
        soup = self.fetch("/")
        if not soup:
            return 0
        session = get_session()
        try:
            event_data = self._extract_event_data(soup)
            if event_data:
                session.add(Event(
                    title=event_data.get("title", "研发部门活动"),
                    items=event_data.get("items"),
                    countdown_hours=event_data.get("countdown_hours"),
                ))
                session.commit()
                logger.info("Scraped event: %s", event_data.get("title"))
                return 1
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return 0

    def _extract_station_data(self, soup, station_name):
        text_elements = soup.find_all(string=re.compile(re.escape(station_name)))
        for el in text_elements:
            container = el.parent
            for _ in range(8):
                if container is None:
                    break
                container_text = container.get_text()
                profit_match = re.search(r"小时利润[:\s]*([\d,]+)", container_text)
                if profit_match:
                    profit = int(profit_match.group(1).replace(",", ""))
                    item_name = self._extract_item_name(container_text, station_name)
                    if item_name:
                        img = container.select_one("img")
                        image_url = img.get("src") if img else None
                        return {"item_name": item_name, "hourly_profit": profit, "image_url": image_url}
                container = container.parent
        return None

    @staticmethod
    def _extract_item_name(text, station_name):
        pattern = re.escape(station_name) + r"\s*(.+?)\s*小时利润"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            name = re.sub(r"\s+", " ", match.group(1).strip())
            if name:
                return name
        return None

    def _extract_event_data(self, soup):
        event_text = soup.find(string=re.compile("研发部门活动"))
        if not event_text:
            event_text = soup.find(string=re.compile("活动倒计时"))
        if not event_text:
            return None
        container = event_text.parent
        for _ in range(5):
            if container is None:
                break
            container = container.parent
        if not container:
            return None
        full_text = container.get_text()
        countdown_match = re.search(r"(\d+)天(\d+)时", full_text)
        countdown_hours = None
        if countdown_match:
            countdown_hours = int(countdown_match.group(1)) * 24 + int(countdown_match.group(2))
        items = []
        imgs = container.select("img[alt]")
        for img in imgs:
            alt = img.get("alt", "").strip()
            if alt and alt not in ("", "Modal Image"):
                items.append(alt)
        if not items:
            for child in container.children:
                text = child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
                if text and len(text) < 20 and "活动" not in text and "倒计时" not in text and "研发" not in text:
                    items.append(text)
        return {"title": "研发部门活动物品", "items": items if items else None, "countdown_hours": countdown_hours}
