from __future__ import annotations

from datetime import date, timedelta

from app.scrapers.base import BaseScraper


def get_target_race_dates(today: date) -> list[date]:
    """実行日に応じてスクレイピング対象日を返す。

    - 土曜実行 → 当日(土) + 翌日(日)
    - 日曜実行 → 当日(日)のみ
    - 平日実行 → 次の土曜 + 日曜

    Args:
        today: 基準日

    Returns:
        対象日のリスト（昇順）
    """
    weekday = today.weekday()  # 0=月, 1=火, 2=水, 3=木, 4=金, 5=土, 6=日

    if weekday == 5:  # 土曜
        return [today, today + timedelta(days=1)]
    elif weekday == 6:  # 日曜
        return [today]
    else:  # 平日（月〜金）
        days_until_saturday = 5 - weekday
        next_saturday = today + timedelta(days=days_until_saturday)
        next_sunday = next_saturday + timedelta(days=1)
        return [next_saturday, next_sunday]


class JraScraper(BaseScraper):
    """JRA公式サイトから重賞スケジュールを取得するスクレイパー。"""

    JRA_SCHEDULE_URL = "https://www.jra.go.jp/keiba/schedule/"

    async def fetch_graded_races(self, target_dates: list[date]) -> list[dict]:
        """JRA公式の重賞スケジュールページから対象日のレースを取得する。

        Args:
            target_dates: 取得対象日のリスト

        Returns:
            重賞レース情報のリスト。各要素は以下の形式:
            {
                "name": "天皇賞(春)",
                "date": date(2024, 4, 28),
                "venue": "京都",
                "grade": "G1",
                "race_number": 11,
            }
        """
        # TODO: Implement actual HTML parsing for JRA schedule page
        return []
