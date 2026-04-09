from __future__ import annotations

import httpx


VENUE_COORDINATES: dict[str, tuple[float, float]] = {
    "東京": (35.6644, 139.4815),    # 府中
    "中山": (35.7297, 139.9582),
    "阪神": (34.7881, 135.3594),
    "京都": (34.9101, 135.7178),
    "中京": (35.0784, 136.9678),
    "小倉": (33.8636, 130.7986),
    "新潟": (37.8647, 139.0511),
    "札幌": (43.0472, 141.4036),
    "函館": (41.7757, 140.6927),
    "福島": (37.7571, 140.4386),
}

# OpenWeatherMap の main.weather → 日本語マッピング
WEATHER_JP: dict[str, str] = {
    "Clear": "晴れ",
    "Clouds": "曇り",
    "Rain": "雨",
    "Drizzle": "小雨",
    "Thunderstorm": "雷雨",
    "Snow": "雪",
    "Mist": "霧",
    "Fog": "霧",
    "Haze": "霞",
    "Smoke": "煙霧",
    "Dust": "砂塵",
    "Sand": "砂嵐",
    "Ash": "火山灰",
    "Squall": "スコール",
    "Tornado": "竜巻",
}

_DEFAULT_WEATHER = {"weather": "不明", "temp": 0.0, "humidity": 0, "description": ""}


class WeatherClient:
    """OpenWeatherMap API から天気情報を取得するクライアント。"""

    API_URL = "https://api.openweathermap.org/data/2.5/weather"
    TIMEOUT = 10.0

    def __init__(self, api_key: str) -> None:
        """初期化。

        Args:
            api_key: OpenWeatherMap の API キー。空文字の場合はデフォルト値を返す。
        """
        self.api_key = api_key

    async def get_weather(self, venue: str) -> dict:
        """競馬場名から現在の天気情報を取得する。

        Args:
            venue: 競馬場名（例: "東京", "阪神"）。VENUE_COORDINATES に定義された
                   名前を指定すること。

        Returns:
            天気情報の辞書。形式:
            {
                "weather": "晴れ",       # 日本語天気
                "temp": 20.5,            # 気温（℃）
                "humidity": 45,          # 湿度（%）
                "description": "clear sky",  # 英語詳細説明
            }
            APIキーが無い場合や競馬場が未定義の場合はデフォルト値を返す。
        """
        if not self.api_key:
            return dict(_DEFAULT_WEATHER)

        coords = VENUE_COORDINATES.get(venue)
        if coords is None:
            return dict(_DEFAULT_WEATHER)

        lat, lon = coords
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
        }

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                response = await client.get(self.API_URL, params=params)
                response.raise_for_status()
                data = response.json()

            main_weather = data.get("weather", [{}])[0].get("main", "")
            description = data.get("weather", [{}])[0].get("description", "")
            temp = data.get("main", {}).get("temp", 0.0)
            humidity = data.get("main", {}).get("humidity", 0)

            weather_jp = WEATHER_JP.get(main_weather, main_weather)

            return {
                "weather": weather_jp,
                "temp": temp,
                "humidity": humidity,
                "description": description,
            }
        except (httpx.HTTPError, httpx.TimeoutException, KeyError, ValueError):
            return dict(_DEFAULT_WEATHER)
