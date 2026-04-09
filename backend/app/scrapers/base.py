import asyncio
import httpx
from bs4 import BeautifulSoup
import logging
import time


class BaseScraper:
    """共通スクレイピング基盤"""

    MIN_INTERVAL = 2.0  # 最低リクエスト間隔（秒）
    MAX_RETRIES = 3
    TIMEOUT = 30.0
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def __init__(self):
        self._last_request_time = 0.0
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _wait_interval(self):
        """リクエスト間隔を制御"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_INTERVAL:
            await asyncio.sleep(self.MIN_INTERVAL - elapsed)

    async def fetch(self, url: str) -> str:
        """URLからHTMLを取得（リトライ付き）"""
        for attempt in range(self.MAX_RETRIES):
            try:
                await self._wait_interval()
                async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                    response = await client.get(
                        url,
                        headers={"User-Agent": self.USER_AGENT},
                        follow_redirects=True,
                    )
                    self._last_request_time = time.time()
                    response.raise_for_status()
                    # netkeibaはEUC-JPの場合がある
                    response.encoding = response.charset_encoding or "utf-8"
                    return response.text
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                self.logger.warning(f"Attempt {attempt + 1}/{self.MAX_RETRIES} failed for {url}: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # exponential backoff
        return ""  # unreachable but for type checker

    def parse_html(self, html: str, encoding: str | None = None) -> BeautifulSoup:
        """HTMLをパース"""
        return BeautifulSoup(html, "lxml")
