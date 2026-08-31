"""答え合わせ（verification_service.build_stats）のテスト

ベット規則: 各レース、予想1位（◎）に単勝100円 + 複勝100円（投下200円）。
数値は手計算値で検算する。
"""

from __future__ import annotations

from datetime import date, datetime

from app.models import Entry, Result
from app.services.verification_service import build_stats
from tests.factories import (
    make_entry,
    make_horse,
    make_payout,
    make_prediction,
    make_race,
    make_result,
)

_RACE_DATE = date(2024, 4, 28)
_PREDICTED_AT = datetime(2024, 4, 27, 12, 0)  # レース前に出した予想

_SUMMARY_KEYS = {
    "races",
    "win_hit_rate",
    "win_roi",
    "place_hit_rate",
    "place_roi",
    "top3_in_top_picks",
}
_CUMULATIVE_KEYS = {"date", "race_id", "balance_win", "balance_place"}
_ROW_KEYS = {
    "date",
    "race_id",
    "race_name",
    "grade",
    "venue",
    "pick_horse_name",
    "pick_odds",
    "finish_position",
    "win_payout",
    "place_payout",
    "net",
}


def _build_race(
    db,
    race_id: str,
    *,
    race_date: date = _RACE_DATE,
    name: str = "検証レース",
    grade: str = "G1",
    venue: str = "東京",
    finish_by_rank: tuple[int, ...] = (1, 2, 3),
    pick_odds: float | None = 4.2,
    predicted_at: datetime | None = None,
) -> list[str]:
    """予想上位3頭・Entry・Result を作る。戻り値は予想順の horse_id。

    馬番は予想順に 1, 2, 3。finish_by_rank[i] が予想 i+1 位の馬の実着順。
    """
    make_race(db, race_id, name=name, grade=grade, venue=venue, race_date=race_date)
    horse_ids: list[str] = []
    for rank, finish_position in enumerate(finish_by_rank, start=1):
        horse_id = f"{race_id}_h{rank}"
        make_horse(db, horse_id, name=f"検証馬{rank}")
        make_entry(
            db, race_id, horse_id,
            post_position=rank,
            horse_number=rank,
            odds=pick_odds if rank == 1 else None,
        )
        make_result(
            db, race_id, horse_id,
            finish_position=finish_position,
            horse_number=rank,
        )
        make_prediction(
            db, race_id, horse_id,
            rank=rank,
            created_at=predicted_at or _PREDICTED_AT,
        )
        horse_ids.append(horse_id)
    return horse_ids


def _add_payouts(
    db,
    race_id: str,
    *,
    win: tuple[str, int],
    places: tuple[tuple[str, int], ...],
) -> None:
    """単勝1件・複勝複数件の払戻を作る"""
    make_payout(db, race_id, bet_type="単勝", combination=win[0], amount=win[1])
    for combination, amount in places:
        make_payout(
            db, race_id, bet_type="複勝", combination=combination, amount=amount
        )


class TestBuildStatsSingleRace:
    """1レース分の払戻・収支の検算"""

    def test_win_and_place_hit(self, db):
        """◎が1着 → 単勝＋複勝ともに的中"""
        _build_race(db, "r_ver_win")
        _add_payouts(
            db, "r_ver_win",
            win=("1", 380),
            places=(("1", 150), ("2", 210), ("3", 130)),
        )

        stats = build_stats(db)

        assert stats["summary"] == {
            "races": 1,
            "win_hit_rate": 1.0,
            "win_roi": 3.8,  # 380 / 100
            "place_hit_rate": 1.0,
            "place_roi": 1.5,  # 150 / 100
            "top3_in_top_picks": 1.0,  # 上位3頭が1/2/3着
        }
        assert len(stats["rows"]) == 1
        row = stats["rows"][0]
        assert row["win_payout"] == 380
        assert row["place_payout"] == 150
        assert row["net"] == 330  # 380 + 150 - 200
        assert row["finish_position"] == 1
        assert row["pick_horse_name"] == "検証馬1"
        assert row["pick_odds"] == 4.2
        assert row["date"] == "2024-04-28"
        assert row["grade"] == "G1"
        assert row["venue"] == "東京"
        assert stats["cumulative"] == [{
            "date": "2024-04-28",
            "race_id": "r_ver_win",
            "balance_win": 280,  # 380 - 100
            "balance_place": 50,  # 150 - 100
        }]

    def test_place_only_hit(self, db):
        """◎が2着 → 単勝は外れ、複勝のみ的中"""
        _build_race(db, "r_ver_place", finish_by_rank=(2, 1, 3))
        _add_payouts(
            db, "r_ver_place",
            win=("2", 500),
            places=(("1", 150), ("2", 210), ("3", 130)),
        )

        stats = build_stats(db)

        assert stats["summary"]["win_hit_rate"] == 0.0
        assert stats["summary"]["win_roi"] == 0.0
        assert stats["summary"]["place_hit_rate"] == 1.0
        assert stats["summary"]["place_roi"] == 1.5
        row = stats["rows"][0]
        assert row["win_payout"] == 0
        assert row["place_payout"] == 150
        assert row["net"] == -50  # 150 - 200

    def test_no_hit(self, db):
        """◎が着外 → 単勝・複勝ともに外れ、投下200円が丸損"""
        _build_race(db, "r_ver_lose", finish_by_rank=(8, 9, 10))
        _add_payouts(
            db, "r_ver_lose",
            win=("4", 720),
            places=(("4", 220), ("5", 180), ("6", 160)),
        )

        stats = build_stats(db)

        assert stats["summary"] == {
            "races": 1,
            "win_hit_rate": 0.0,
            "win_roi": 0.0,
            "place_hit_rate": 0.0,
            "place_roi": 0.0,
            "top3_in_top_picks": 0.0,
        }
        row = stats["rows"][0]
        assert row["net"] == -200
        assert stats["cumulative"][0]["balance_win"] == -100
        assert stats["cumulative"][0]["balance_place"] == -100

    def test_horse_number_falls_back_to_result(self, db):
        """Entry.horse_number が無い場合は Result.horse_number で払戻と突合する"""
        horse_ids = _build_race(db, "r_ver_fallback")
        _add_payouts(db, "r_ver_fallback", win=("1", 380), places=(("1", 150),))
        pick_entry = (
            db.query(Entry)
            .filter_by(race_id="r_ver_fallback", horse_id=horse_ids[0])
            .one()
        )
        pick_entry.horse_number = None
        db.flush()

        stats = build_stats(db)

        assert stats["rows"][0]["win_payout"] == 380
        assert stats["rows"][0]["place_payout"] == 150


class TestBuildStatsExclusions:
    """検証対象から外れるレースの判定"""

    def test_post_race_batch_is_ignored(self, db):
        """レース後に作られたバッチではなく、レース前の最新バッチを使う"""
        horse_ids = _build_race(db, "r_ver_batch", finish_by_rank=(5, 1, 2))
        _add_payouts(
            db, "r_ver_batch",
            win=("2", 500),
            places=(("2", 210), ("3", 160)),
        )
        # レース翌日に作られたバッチ（1着馬を◎にしている）は無視される
        for rank, horse_id in enumerate([horse_ids[1], horse_ids[0], horse_ids[2]], 1):
            make_prediction(
                db, "r_ver_batch", horse_id, rank=rank,
                created_at=datetime(2024, 4, 29, 9, 0),
            )

        stats = build_stats(db)

        row = stats["rows"][0]
        assert row["pick_horse_name"] == "検証馬1"  # レース前バッチの1位
        assert row["finish_position"] == 5
        assert row["win_payout"] == 0
        assert row["place_payout"] == 0

    def test_race_without_pre_race_batch_is_excluded(self, db):
        """レース前のバッチが1つも無いレースは検証対象外"""
        _build_race(
            db, "r_ver_after", predicted_at=datetime(2024, 4, 29, 9, 0),
        )
        _add_payouts(db, "r_ver_after", win=("1", 380), places=(("1", 150),))

        stats = build_stats(db)

        assert stats["summary"]["races"] == 0
        assert stats["rows"] == []

    def test_race_without_payouts_is_excluded(self, db):
        """払戻が未取得のレースは検証対象外"""
        _build_race(db, "r_ver_nopay")

        assert build_stats(db)["summary"]["races"] == 0

    def test_race_with_only_win_payout_is_excluded(self, db):
        """単勝しか払戻が無いレースは検証対象外（複勝の判定ができない）"""
        _build_race(db, "r_ver_winonly")
        make_payout(db, "r_ver_winonly", bet_type="単勝", combination="1", amount=380)

        assert build_stats(db)["summary"]["races"] == 0

    def test_scratched_pick_is_excluded(self, db):
        """◎が出走取消（着順なし）のレースは検証対象外"""
        horse_ids = _build_race(db, "r_ver_scratch")
        _add_payouts(db, "r_ver_scratch", win=("2", 500), places=(("2", 210),))
        db.query(Result).filter_by(
            race_id="r_ver_scratch", horse_id=horse_ids[0]
        ).delete()
        db.flush()

        stats = build_stats(db)

        assert stats["summary"]["races"] == 0
        assert stats["rows"] == []


class TestBuildStatsAggregation:
    """複数レースのサマリ・累計・並び順の検算"""

    def test_summary_cumulative_and_ordering(self, db):
        """2レース分の的中率・回収率・累計収支・並び順を手計算値で検算する"""
        # レースA: ◎が1着（単勝300円・複勝140円）
        _build_race(
            db, "r_ver_a", race_date=date(2024, 5, 1), name="レースA",
            predicted_at=datetime(2024, 4, 30, 12, 0),
        )
        _add_payouts(db, "r_ver_a", win=("1", 300), places=(("1", 140),))
        # レースB: ◎が5着（払戻なし）、予想2位が1着・3位が2着
        _build_race(
            db, "r_ver_b", race_date=date(2024, 5, 2), name="レースB",
            finish_by_rank=(5, 1, 2),
            predicted_at=datetime(2024, 5, 1, 12, 0),
        )
        _add_payouts(
            db, "r_ver_b", win=("2", 600), places=(("2", 180), ("3", 160)),
        )

        stats = build_stats(db)

        assert stats["summary"] == {
            "races": 2,
            "win_hit_rate": 0.5,  # 1 / 2
            "win_roi": 1.5,  # 300 / (100 * 2)
            "place_hit_rate": 0.5,
            "place_roi": 0.7,  # 140 / (100 * 2)
            # A: 3/3、B: 2/3 → (1.0 + 0.666…) / 2
            "top3_in_top_picks": 0.833,
        }
        # cumulative は date 昇順で累計
        assert stats["cumulative"] == [
            {
                "date": "2024-05-01", "race_id": "r_ver_a",
                "balance_win": 200, "balance_place": 40,
            },
            {
                "date": "2024-05-02", "race_id": "r_ver_b",
                "balance_win": 100, "balance_place": -60,
            },
        ]
        # rows は date 降順
        assert [row["race_id"] for row in stats["rows"]] == ["r_ver_b", "r_ver_a"]
        assert [row["net"] for row in stats["rows"]] == [-200, 240]

    def test_contract_keys(self, db):
        """返り値のキーがフロント／Pages用JSONの契約と一致すること"""
        _build_race(db, "r_ver_keys")
        _add_payouts(db, "r_ver_keys", win=("1", 380), places=(("1", 150),))

        stats = build_stats(db)

        assert set(stats.keys()) == {"summary", "cumulative", "rows"}
        assert set(stats["summary"].keys()) == _SUMMARY_KEYS
        assert set(stats["cumulative"][0].keys()) == _CUMULATIVE_KEYS
        assert set(stats["rows"][0].keys()) == _ROW_KEYS

    def test_empty_database_returns_zero_shape(self, db):
        """対象0件でも同じ形（率は全て0.0）を返すこと"""
        stats = build_stats(db)

        assert stats == {
            "summary": {
                "races": 0,
                "win_hit_rate": 0.0,
                "win_roi": 0.0,
                "place_hit_rate": 0.0,
                "place_roi": 0.0,
                "top3_in_top_picks": 0.0,
            },
            "cumulative": [],
            "rows": [],
        }
