import asyncio
import logging
import time

import httpx
from bs4 import BeautifulSoup


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

    async def fetch(self, url: str, encoding: str | None = None) -> str:
        """URLからHTMLを取得（リトライ付き）

        Args:
            url: 取得対象URL
            encoding: 文字エンコーディング（例: "euc-jp"）。Noneの場合は
                      レスポンスのcharset_encodingまたはutf-8を使用する。
        """
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
                    # encodingが指定された場合はそれを優先する
                    response.encoding = (
                        encoding or response.charset_encoding or "utf-8"
                    )
                    return response.text
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                self.logger.warning(
                    "Attempt %d/%d failed for %s: %s",
                    attempt + 1,
                    self.MAX_RETRIES,
                    url,
                    e,
                )
                if attempt == self.MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(2**attempt)  # exponential backoff
        return ""  # unreachable but for type checker

    def parse_html(self, html: str, encoding: str | None = None) -> BeautifulSoup:
        """HTMLをパース"""
        return BeautifulSoup(html, "lxml")
