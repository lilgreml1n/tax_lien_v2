import asyncio
import random
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import httpx


class HumanBehavior:
    """Simulate human-like browsing patterns."""

    REQUEST_DELAY_MIN = 2
    REQUEST_DELAY_MAX = 8
    PAGE_DELAY_MIN = 10
    PAGE_DELAY_MAX = 30

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    ]

    @staticmethod
    async def request_delay():
        delay = random.uniform(HumanBehavior.REQUEST_DELAY_MIN, HumanBehavior.REQUEST_DELAY_MAX)
        await asyncio.sleep(delay)

    @staticmethod
    async def page_delay():
        delay = random.uniform(HumanBehavior.PAGE_DELAY_MIN, HumanBehavior.PAGE_DELAY_MAX)
        await asyncio.sleep(delay)

    @staticmethod
    def get_headers() -> Dict[str, str]:
        return {
            "User-Agent": random.choice(HumanBehavior.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
        }


class CountyScraper(ABC):
    """Base class for all county scrapers."""

    def __init__(self, state: str, county: str):
        self.state = state
        self.county = county
        self.session = None

    @abstractmethod
    async def scrape(self, limit: int = 0) -> List[Dict[str, Any]]:
        pass

    async def close(self):
        if self.session:
            await self.session.aclose()
