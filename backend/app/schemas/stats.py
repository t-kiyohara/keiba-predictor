from datetime import date

from pydantic import BaseModel


class StatsSummaryOut(BaseModel):
    """答え合わせサマリ（的中率・回収率は0〜1のレート）"""

    races: int
    win_hit_rate: float
    win_roi: float
    place_hit_rate: float
    place_roi: float
    top3_in_top_picks: float


class StatsCumulativeOut(BaseModel):
    """券種別の累計収支（円）"""

    date: date
    race_id: str
    balance_win: int
    balance_place: int


class StatsRowOut(BaseModel):
    """レース1件分の答え合わせ結果"""

    date: date
    race_id: str
    race_name: str
    grade: str
    venue: str
    pick_horse_name: str
    pick_odds: float | None
    finish_position: int
    win_payout: int
    place_payout: int
    net: int


class StatsOut(BaseModel):
    """答え合わせAPIのレスポンスモデル"""

    summary: StatsSummaryOut
    cumulative: list[StatsCumulativeOut]
    rows: list[StatsRowOut]
