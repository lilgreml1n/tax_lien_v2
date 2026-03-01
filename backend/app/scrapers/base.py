import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable, Optional
import httpx


NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
    OSError,  # catches [Errno -3] name resolution failures
)


async def with_retry(coro_func, label: str = "", max_wait: int = 300, retry_delay: int = 30):
    """
    Retry a coroutine on network errors with a hard timeout.

    Args:
        coro_func: Zero-argument async callable, e.g. lambda: scraper._get_total_billed(pid)
        label:     Human-readable description for log messages
        max_wait:  Give up after this many seconds (default 5 minutes)
        retry_delay: Seconds to wait between retries (default 30)
    """
    start = time.monotonic()
    attempt = 0
    while True:
        try:
            return await coro_func()
        except NETWORK_ERRORS as e:
            elapsed = time.monotonic() - start
            remaining = max_wait - elapsed
            if remaining <= 0:
                print(f"[retry] {label} - giving up after {int(elapsed)}s: {e}", flush=True)
                raise
            attempt += 1
            wait = min(retry_delay, remaining)
            print(f"[retry] {label} - network error (attempt {attempt}), retrying in {int(wait)}s ({int(remaining)}s left): {e}", flush=True)
            await asyncio.sleep(wait)


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
        self.total_parcels_available = 0  # Set by scraper before/after loop; written to checkpoint on completion

    @abstractmethod
    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        pass

    async def close(self):
        if self.session:
            await self.session.aclose()
