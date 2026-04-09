"""Tests for scraping utilities: date targeting, HTML parsing, weather client."""

from __future__ import annotations

from datetime import date

import pytest

from app.scrapers.base import BaseScraper
from app.scrapers.jra import get_target_race_dates
from app.scrapers.weather import VENUE_COORDINATES, WEATHER_JP, WeatherClient


# ---------------------------------------------------------------------------
# get_target_race_dates
# ---------------------------------------------------------------------------


class TestGetTargetRaceDates:
    def test_get_target_race_dates_saturday(self):
        """土曜日 → 当日(土) + 翌日(日) の2日分を返す。"""
        saturday = date(2024, 4, 27)  # weekday() == 5
        assert saturday.weekday() == 5, "fixture is not a Saturday"
        result = get_target_race_dates(saturday)
        assert result == [date(2024, 4, 27), date(2024, 4, 28)]

    def test_get_target_race_dates_sunday(self):
        """日曜日 → 当日(日)のみ返す。"""
        sunday = date(2024, 4, 28)  # weekday() == 6
        assert sunday.weekday() == 6, "fixture is not a Sunday"
        result = get_target_race_dates(sunday)
        assert result == [date(2024, 4, 28)]

    def test_get_target_race_dates_weekday(self):
        """平日(水曜) → 次の土曜 + 日曜を返す。"""
        wednesday = date(2024, 4, 24)  # weekday() == 2
        assert wednesday.weekday() == 2, "fixture is not a Wednesday"
        result = get_target_race_dates(wednesday)
        # 2024-04-24(水) の次の土曜は 2024-04-27
        assert result == [date(2024, 4, 27), date(2024, 4, 28)]

    def test_get_target_race_dates_monday(self):
        """月曜 → 次の土曜 + 日曜を返す。"""
        monday = date(2024, 4, 22)  # weekday() == 0
        assert monday.weekday() == 0, "fixture is not a Monday"
        result = get_target_race_dates(monday)
        # 2024-04-22(月) の次の土曜は 2024-04-27
        assert result == [date(2024, 4, 27), date(2024, 4, 28)]

    def test_get_target_race_dates_friday(self):
        """金曜 → 翌日の土曜 + 日曜を返す。"""
        friday = date(2024, 4, 26)  # weekday() == 4
        assert friday.weekday() == 4, "fixture is not a Friday"
        result = get_target_race_dates(friday)
        # 2024-04-26(金) の次の日が土曜 2024-04-27
        assert result == [date(2024, 4, 27), date(2024, 4, 28)]


# ---------------------------------------------------------------------------
# BaseScraper.parse_html
# ---------------------------------------------------------------------------


class TestBaseScraperParseHtml:
    def test_base_scraper_parse_html(self):
        """HTMLパースが正しく動作するか確認する。"""
        scraper = BaseScraper()
        html = "<html><body><h1>テスト</h1><p class='info'>情報</p></body></html>"
        soup = scraper.parse_html(html)

        assert soup.find("h1") is not None
        assert soup.find("h1").text == "テスト"
        assert soup.find("p", class_="info") is not None
        assert soup.find("p", class_="info").text == "情報"

    def test_base_scraper_parse_html_returns_beautifulsoup(self):
        """parse_html が BeautifulSoup インスタンスを返すことを確認する。"""
        from bs4 import BeautifulSoup

        scraper = BaseScraper()
        soup = scraper.parse_html("<html></html>")
        assert isinstance(soup, BeautifulSoup)


# ---------------------------------------------------------------------------
# WeatherClient — venue coordinates
# ---------------------------------------------------------------------------


class TestWeatherVenueCoordinates:
    EXPECTED_VENUES = [
        "東京",
        "中山",
        "阪神",
        "京都",
        "中京",
        "小倉",
        "新潟",
        "札幌",
        "函館",
        "福島",
    ]

    def test_weather_venue_coordinates(self):
        """全10競馬場の座標が VENUE_COORDINATES に定義されているか確認する。"""
        assert len(VENUE_COORDINATES) == 10

        for venue in self.EXPECTED_VENUES:
            assert venue in VENUE_COORDINATES, f"{venue} が VENUE_COORDINATES に未定義"
            lat, lon = VENUE_COORDINATES[venue]
            assert isinstance(lat, float), f"{venue} の緯度が float ではない"
            assert isinstance(lon, float), f"{venue} の経度が float ではない"
            # 日本の緯度経度範囲チェック
            assert 24.0 <= lat <= 46.0, f"{venue} の緯度が日本の範囲外: {lat}"
            assert 122.0 <= lon <= 154.0, f"{venue} の経度が日本の範囲外: {lon}"


# ---------------------------------------------------------------------------
# WeatherClient — Japanese weather mapping
# ---------------------------------------------------------------------------


class TestWeatherJapaneseMapping:
    def test_weather_japanese_mapping(self):
        """天気の日本語変換が正しいか確認する。"""
        assert WEATHER_JP["Clear"] == "晴れ"
        assert WEATHER_JP["Clouds"] == "曇り"
        assert WEATHER_JP["Rain"] == "雨"
        assert WEATHER_JP["Snow"] == "雪"

    def test_weather_japanese_mapping_drizzle(self):
        """小雨が正しくマッピングされているか確認する。"""
        assert WEATHER_JP["Drizzle"] == "小雨"

    def test_weather_japanese_mapping_thunderstorm(self):
        """雷雨が正しくマッピングされているか確認する。"""
        assert WEATHER_JP["Thunderstorm"] == "雷雨"

    def test_weather_japanese_mapping_completeness(self):
        """主要な天気種別が全てマッピングされているか確認する。"""
        required_keys = ["Clear", "Clouds", "Rain", "Drizzle", "Thunderstorm", "Snow"]
        for key in required_keys:
            assert key in WEATHER_JP, f"'{key}' が WEATHER_JP に未定義"
            assert WEATHER_JP[key], f"'{key}' のマッピングが空"


# ---------------------------------------------------------------------------
# WeatherClient — no API key fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weather_client_no_api_key_returns_default():
    """APIキーが空の場合はデフォルト値を返すことを確認する。"""
    client = WeatherClient(api_key="")
    result = await client.get_weather("東京")
    assert isinstance(result, dict)
    assert "weather" in result
    assert "temp" in result
    assert "humidity" in result
    assert "description" in result


@pytest.mark.asyncio
async def test_weather_client_unknown_venue_returns_default():
    """未定義の競馬場名を渡した場合はデフォルト値を返すことを確認する。"""
    client = WeatherClient(api_key="dummy_key")
    result = await client.get_weather("未定義競馬場")
    assert isinstance(result, dict)
    assert result["weather"] == "不明"
