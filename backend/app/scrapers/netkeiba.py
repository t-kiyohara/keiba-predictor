from __future__ import annotations

from app.scrapers.base import BaseScraper


class NetkeibaScraper(BaseScraper):
    """netkeiba.com から競馬データを取得するスクレイパー。"""

    BASE_URL = "https://race.netkeiba.com"
    DB_URL = "https://db.netkeiba.com"

    async def fetch_race_entries(self, race_id: str) -> dict:
        """レース出馬表ページから出走馬情報を取得する。

        Args:
            race_id: netkeibaのレースID（例: "202405050811"）

        Returns:
            レース情報と出走馬リストを含む辞書。形式:
            {
                "race_info": {
                    "race_id": "202405050811",
                    "name": "天皇賞(春)",
                    "date": "2024-04-28",
                    "venue": "京都",
                    "grade": "G1",
                    "distance": 3200,
                    "course_type": "芝",
                },
                "entries": [
                    {
                        "horse_id": "2019105943",
                        "horse_name": "ドウデュース",
                        "jockey_id": "01167",
                        "jockey_name": "武豊",
                        "trainer_id": "01234",
                        "trainer_name": "友道康夫",
                        "post_position": 3,
                        "horse_number": 5,
                        "weight": 58.0,
                    }
                ],
            }

        URL例:
            https://race.netkeiba.com/race/shutuba.html?race_id={race_id}
        """
        # TODO: Implement actual HTML parsing for JRA schedule page
        return {}

    async def fetch_horse_results(self, horse_id: str, limit: int = 10) -> list[dict]:
        """馬の過去成績を取得する。

        Args:
            horse_id: netkeibaの馬ID（例: "2019105943"）
            limit: 取得する過去成績の最大件数

        Returns:
            過去成績のリスト。各要素は以下の形式:
            {
                "race_id": "202405050811",
                "race_name": "天皇賞(春)",
                "date": "2024-04-28",
                "venue": "京都",
                "distance": 3200,
                "course_type": "芝",
                "track_condition": "良",
                "finish_position": 1,
                "time": "3:14.2",
                "last_3f": 35.4,
                "jockey_name": "武豊",
            }

        URL例:
            https://db.netkeiba.com/horse/{horse_id}
        """
        # TODO: Implement actual HTML parsing for JRA schedule page
        return []

    async def fetch_horse_profile(self, horse_id: str) -> dict:
        """馬の血統・プロフィールを取得する。

        Args:
            horse_id: netkeibaの馬ID（例: "2019105943"）

        Returns:
            馬のプロフィール情報。形式:
            {
                "id": "2019105943",
                "name": "ドウデュース",
                "sex": "牡",
                "birthday": "2019-03-01",
                "sire": "ハーツクライ",
                "dam": "ダストアンドダイヤモンズ",
                "dam_sire": "Motivator",
            }

        URL例:
            https://db.netkeiba.com/horse/{horse_id}
        """
        # TODO: Implement actual HTML parsing for JRA schedule page
        return {}

    async def fetch_race_results_history(self, race_name: str, limit: int = 5) -> list[dict]:
        """同名レースの過去結果を取得する。

        Args:
            race_name: レース名（例: "天皇賞(春)"）
            limit: 取得する過去年度の最大件数

        Returns:
            過去レース結果のリスト。各要素は以下の形式:
            {
                "year": 2023,
                "race_id": "202305050811",
                "results": [
                    {
                        "finish_position": 1,
                        "horse_name": "ジャスティンパレス",
                        "horse_id": "2019105123",
                        "jockey_name": "C.ルメール",
                        "time": "3:15.0",
                        "last_3f": 34.8,
                    }
                ],
            }
        """
        # TODO: Implement actual HTML parsing for JRA schedule page
        return []
