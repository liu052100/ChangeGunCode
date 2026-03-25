import logging
import re
from urllib.parse import unquote, urlparse

from models.database import GunCode, Weapon, WeaponCategory, get_session
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)


class WeaponScraper(BaseScraper):
    def scrape_categories(self):
        soup = self.fetch("/weapons")
        if not soup:
            return 0
        session = get_session()
        count = 0
        try:
            category_links = soup.select('a[href*="/weapon_category/"]')
            for i, link in enumerate(category_links):
                name = link.get_text(strip=True)
                href = link.get("href", "")
                path = urlparse(href).path.rstrip("/")
                slug = unquote(path.split("/")[-1]) if path else name
                existing = session.query(WeaponCategory).filter_by(slug=slug).first()
                if existing:
                    existing.name = name
                    existing.sort_order = i
                else:
                    session.add(WeaponCategory(name=name, slug=slug, sort_order=i))
                count += 1
            session.commit()
            logger.info("Scraped %d weapon categories", count)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return count

    def scrape_weapon_list(self):
        soup = self.fetch("/weapons")
        if not soup:
            return 0
        session = get_session()
        count = 0
        try:
            categories = {c.name: c.id for c in session.query(WeaponCategory).all()}
            weapon_links = soup.select('a[href*="/weapons/"]')
            seen_slugs = set()
            for link in weapon_links:
                href = link.get("href", "")
                path = urlparse(href).path.rstrip("/")
                parts = path.split("/")
                if len(parts) < 2 or parts[-2] != "weapons":
                    continue
                slug = parts[-1]
                if slug in seen_slugs or not slug:
                    continue
                seen_slugs.add(slug)
                name = link.get_text(strip=True)
                if not name:
                    continue
                category_id = self._guess_category(name, categories)
                source_url = f"{self.base_url}/weapons/{slug}"
                existing = session.query(Weapon).filter_by(slug=slug).first()
                if existing:
                    existing.name = name
                    existing.source_url = source_url
                    if category_id:
                        existing.category_id = category_id
                else:
                    session.add(Weapon(name=name, slug=slug, category_id=category_id, source_url=source_url))
                count += 1
            session.commit()
            logger.info("Scraped %d weapons", count)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return count

    def scrape_weapon_categories_mapping(self):
        session = get_session()
        updated = 0
        try:
            categories = session.query(WeaponCategory).all()
            for cat in categories:
                soup = self.fetch(f"/weapon_category/{cat.slug}")
                if not soup:
                    continue
                weapon_links = soup.select('a[href*="/weapons/"]')
                for link in weapon_links:
                    href = link.get("href", "")
                    path = urlparse(href).path.rstrip("/")
                    parts = path.split("/")
                    if len(parts) < 2 or parts[-2] != "weapons":
                        continue
                    slug = parts[-1]
                    weapon = session.query(Weapon).filter_by(slug=slug).first()
                    if weapon and weapon.category_id != cat.id:
                        weapon.category_id = cat.id
                        updated += 1
            session.commit()
            logger.info("Updated %d weapon-category mappings", updated)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return updated

    def scrape_gun_codes(self, weapon_slug):
        soup = self.fetch(f"/weapons/{weapon_slug}")
        if not soup:
            return 0
        session = get_session()
        count = 0
        try:
            weapon = session.query(Weapon).filter_by(slug=weapon_slug).first()
            if not weapon:
                logger.warning("Weapon not found in DB: %s", weapon_slug)
                return 0
            code_elements = self._extract_codes_from_page(soup)
            for item in code_elements:
                code = item["code"]
                existing = session.query(GunCode).filter_by(code=code).first()
                if existing:
                    existing.description = item.get("description") or existing.description
                    existing.value = item.get("value") or existing.value
                    existing.copy_count = item.get("copy_count", existing.copy_count)
                    existing.likes = item.get("likes", existing.likes)
                    existing.is_hot = item.get("is_hot", existing.is_hot)
                    existing.image_url = item.get("image_url") or existing.image_url
                    existing.game_mode = item.get("game_mode") or existing.game_mode
                else:
                    session.add(GunCode(
                        weapon_id=weapon.id, code=code,
                        description=item.get("description"), value=item.get("value"),
                        copy_count=item.get("copy_count", 0), likes=item.get("likes", 0),
                        is_hot=item.get("is_hot", False), image_url=item.get("image_url"),
                        game_mode=item.get("game_mode", "烽火地带"),
                    ))
                count += 1
            weapon.code_count = session.query(GunCode).filter_by(weapon_id=weapon.id).count()
            session.commit()
            logger.info("Scraped %d gun codes for %s", count, weapon_slug)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return count

    def scrape_all_gun_codes(self):
        session = get_session()
        weapons = session.query(Weapon).all()
        slugs = [w.slug for w in weapons]
        session.close()
        total = 0
        for slug in slugs:
            total += self.scrape_gun_codes(slug)
        return total

    def _extract_codes_from_page(self, soup):
        results = []
        rows = soup.select("tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue
            code_text = self._find_code_in_element(cells[0])
            if not code_text:
                code_text = self._find_code_in_element(row)
            if not code_text:
                continue
            item = {"code": code_text, "is_hot": False}
            desc_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            if desc_text and desc_text != code_text:
                item["description"] = desc_text
            for cell in cells:
                text = cell.get_text(strip=True)
                if re.search(r"\d+[Ww万]", text):
                    item["value"] = text
                    break
            for cell in cells:
                text = cell.get_text(strip=True)
                match = re.search(r"([\d,]+)\s*次", text)
                if match:
                    item["copy_count"] = int(match.group(1).replace(",", ""))
                    break
            if row.select(".hot, .fire") or "热门" in row.get_text():
                item["is_hot"] = True
            full_text = row.get_text()
            if "全面战场" in full_text:
                item["game_mode"] = "全面战场"
            results.append(item)
        if not results:
            results = self._extract_codes_from_cards(soup)
        return results

    def _extract_codes_from_cards(self, soup):
        results = []
        code_pattern = re.compile(r"[A-Z0-9]{15,}")
        for el in soup.find_all(string=code_pattern):
            parent = el.parent
            if not parent:
                continue
            code_text = el.strip()
            code_match = re.search(r"([A-Za-z0-9\-\u4e00-\u9fff]+烽火地带[A-Za-z0-9\-]+|[A-Z0-9]{15,})", code_text)
            if not code_match:
                continue
            code = code_match.group(1).strip()
            item = {"code": code}
            container = parent
            for _ in range(5):
                if container.parent:
                    container = container.parent
                else:
                    break
            container_text = container.get_text()
            value_match = re.search(r"(\d+)[Ww万]", container_text)
            if value_match:
                item["value"] = f"{value_match.group(1)}W"
            copy_match = re.search(r"已?复制\s*([\d,]+)\s*次", container_text)
            if copy_match:
                item["copy_count"] = int(copy_match.group(1).replace(",", ""))
            results.append(item)
        return results

    def _find_code_in_element(self, element):
        text = element.get_text(strip=True)
        patterns = [
            r"([A-Za-z0-9\u4e00-\u9fff]+[--]烽火地带[--][A-Za-z0-9]+)",
            r"([A-Za-z0-9\u4e00-\u9fff]+[--]全面战场[--][A-Za-z0-9]+)",
            r"\b([A-Z0-9]{15,})\b",
        ]
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def _guess_category(weapon_name, categories):
        keywords = {
            "冲锋枪": ["冲锋枪", "MP", "UZI", "Vector", "P90", "SMG", "QCQ"],
            "手枪": ["手枪", "左轮", "G17", "G18", "M1911", "QSZ", "93R"],
            "步枪": ["突击步枪", "战斗步枪", "M4A1", "AK", "K416", "QBZ", "AUG", "SCAR", "SG552"],
            "狙击步枪": ["狙击", "AWM", "R93", "SV-98", "M700"],
            "精确射手步枪": ["射手步枪", "SR-25", "M14", "SVD", "PSG", "Mini-14", "SKS"],
            "轻机枪": ["轻机枪", "PKM", "M249", "M250", "QJB"],
            "霰弹枪": ["霰弹枪", "M870", "M1014", "S12K", "FS-12", "725"],
            "特殊武器": ["复合弓", "Marlin", "杠杆"],
        }
        for cat_name, kws in keywords.items():
            for kw in kws:
                if kw in weapon_name:
                    return categories.get(cat_name)
        return None
