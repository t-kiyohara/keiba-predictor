from __future__ import annotations

import re
from datetime import date, timedelta

from app.scrapers.base import BaseScraper
from app.scrapers.constants import GRADE_NORMALIZE, GRADE_PATTERN


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

    JRA_SCHEDULE_URL = "https://www.jra.go.jp/keiba/thisweek/"

    async def fetch_graded_races(self, target_dates: list[date]) -> list[dict]:
        """JRA公式の今週の重賞ページから対象日のレースを取得する。

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
        try:
            html = await self.fetch(self.JRA_SCHEDULE_URL, encoding="shift_jis")
        except Exception as e:
            self.logger.warning("JRAスケジュールページの取得に失敗: %s", e)
            return []

        soup = self.parse_html(html)
        results: list[dict] = []
        current_year = date.today().year

        # ページ全体のテキストを走査して日付・レース情報を抽出する
        # h3タグにレース名が含まれており、直前または親要素に日付・会場情報がある
        for h3 in soup.find_all("h3"):
            h3_text = h3.get_text(strip=True)

            # グレード判定
            grade_match = GRADE_PATTERN.search(h3_text)
            if not grade_match:
                continue
            grade_raw = grade_match.group(1)
            grade = GRADE_NORMALIZE.get(grade_raw, "")
            if not grade:
                continue

            # レース名（グレード括弧を除去）
            race_name = h3_text

            # 日付と会場・距離を隣接要素から探す
            race_date: date | None = None
            venue: str = ""
            distance: int = 0

            # h3の周辺（前後の兄弟・親）をたどって日付・会場・距離を探す
            # まず親要素全体のテキストから日付を探す
            parent = h3.parent
            if parent:
                parent_text = parent.get_text()
                date_match = re.search(r"(\d+)月(\d+)日", parent_text)
                if date_match:
                    month = int(date_match.group(1))
                    day = int(date_match.group(2))
                    race_date = date(current_year, month, day)

                # 会場は「〇〇競馬場」のパターン
                venue_match = re.search(r"([^\s　]+)競馬場", parent_text)
                if venue_match:
                    venue = venue_match.group(1)

                # 距離は「NNNNメートル」のパターン
                dist_match = re.search(r"(\d{3,4})メートル", parent_text)
                if dist_match:
                    distance = int(dist_match.group(1))

            # 親で見つからない場合はページ全体を走査（前後のp/h4タグ）
            if not race_date:
                # h3より前の要素から日付を探す
                for sibling in h3.find_all_previous(["p", "h4", "h2", "div", "dt"]):
                    sib_text = sibling.get_text()
                    date_match = re.search(r"(\d+)月(\d+)日", sib_text)
                    if date_match:
                        month = int(date_match.group(1))
                        day = int(date_match.group(2))
                        race_date = date(current_year, month, day)
                        break

            # h3の直後のp要素から会場・距離情報を取得
            next_sibling = h3.find_next_sibling("p")
            if next_sibling:
                sib_text = next_sibling.get_text()
                if not venue:
                    venue_match = re.search(r"([^\s　]+)競馬場", sib_text)
                    if venue_match:
                        venue = venue_match.group(1)
                if not distance:
                    dist_match = re.search(r"(\d{3,4})メートル", sib_text)
                    if dist_match:
                        distance = int(dist_match.group(1))
                if not race_date:
                    date_match = re.search(r"(\d+)月(\d+)日", sib_text)
                    if date_match:
                        month = int(date_match.group(1))
                        day = int(date_match.group(2))
                        race_date = date(current_year, month, day)

            # 日付フィルタ
            if race_date is None or race_date not in target_dates:
                continue

            results.append(
                {
                    "name": race_name,
                    "date": race_date,
                    "venue": venue,
                    "grade": grade,
                    "distance": distance,
                    # TODO: JRAページから実際のR番号を取得する（現在は重賞=11Rと仮定）
                    "race_number": 11,
                }
            )

        return results
