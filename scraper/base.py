import logging
import random
import time

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


class BaseScraper:
    def __init__(self, base_url, min_delay=1.0, max_delay=3.0, max_retries=3):
        self.base_url = base_url.rstrip("/")
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
            },
        )

    def _random_ua(self):
        return random.choice(USER_AGENTS)

    def _delay(self):
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def fetch(self, url):
        if not url.startswith("http"):
            url = f"{self.base_url}{url}"

        for attempt in range(1, self.max_retries + 1):
            try:
                self.client.headers["User-Agent"] = self._random_ua()
                self.client.headers["Referer"] = self.base_url
                resp = self.client.get(url)
                resp.raise_for_status()
                self._delay()
                return BeautifulSoup(resp.text, "lxml")
            except httpx.HTTPStatusError as e:
                logger.warning("HTTP %d for %s (attempt %d/%d)", e.response.status_code, url, attempt, self.max_retries)
            except httpx.RequestError as e:
                logger.warning("Request error for %s: %s (attempt %d/%d)", url, e, attempt, self.max_retries)

            backoff = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(backoff)

        logger.error("Failed to fetch %s after %d attempts", url, self.max_retries)
        return None

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
