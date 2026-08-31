"""レース結果の一括収集（collection_service）のテスト。

実ネットワークには出ない。スクレイパーは呼び出しを記録するスタブに差し替える。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models import Payout, Result
from app.services.collection_service import (
    backfill_race_results,
    collect_race_results,
    select_uncollected_race_ids,
    select_verify_targets,
    verify_race_results,
)
from tests.factories import make_horse, make_payout, make_prediction, make_race


def _parsed_result(race_id: str) -> dict:
    """NetkeibaScraper.fetch_race_result() の返り値と同じ形（1着のみ）。"""
    return {
        "race": {
            "race_id": race_id,
            "name": f"収集テスト{race_id}",
            "grade": "G3",
            "date": "2024-03-03",
            "venue": "中山",
            "course_type": "芝",
            "distance": 1800,
            "weather": "晴",
            "track_condition": "良",
        },
        "results": [
            {
                "horse_id": f"h_{race_id}",
                "horse_name": "収集テスト馬",
                "horse_number": 3,
                "finish_position": 1,
                "time": "1:48.0",
                "margin": None,
                "last_3f": 34.5,
                "jockey_id": f"j_{race_id}",
                "jockey_name": "収集テスト騎手",
                "trainer_id": f"t_{race_id}",
                "trainer_name": "収集テスト調教師",
            }
        ],
        "payouts": [
            {"bet_type": "単勝", "combination": "3", "amount": 250},
            {"bet_type": "複勝", "combination": "3", "amount": 130},
        ],
    }


class _StubScraper:
    """NetkeibaScraper の代役。どの race_id を取りに行ったかを記録する。"""

    def __init__(
        self,
        graded_race_ids: list[str] | None = None,
        unavailable_race_ids: tuple[str, ...] = (),
    ):
        self.graded_race_ids = list(graded_race_ids or [])
        self.unavailable_race_ids = set(unavailable_race_ids)
        self.requested_year_ranges: list[tuple[int, int]] = []
        self.requested_race_ids: list[str] = []

    async def fetch_graded_race_ids(
        self, start_year: int, end_year: int
    ) -> list[str]:
        self.requested_year_ranges.append((start_year, end_year))
        return list(self.graded_race_ids)

    async def fetch_race_result(self, race_id: str) -> dict:
        self.requested_race_ids.append(race_id)
        if race_id in self.unavailable_race_ids:
            return {}  # 結果ページが取れないレース
        return _parsed_result(race_id)


def _make_predicted_race(
    db, race_id: str, days_ago: int, *, with_payout: bool = False
) -> None:
    """予想を持つレースを作る（days_ago日前開催）。"""
    make_race(db, race_id=race_id, race_date=date.today() - timedelta(days=days_ago))
    horse_id = f"h_{race_id}"
    make_horse(db, horse_id)
    make_prediction(db, race_id, horse_id, rank=1)
    if with_payout:
        make_payout(db, race_id)


# ---------------------------------------------------------------------------
# 対象選定: verify
# ---------------------------------------------------------------------------


class TestSelectVerifyTargets:
    """予想あり・期間内・払戻なしのレースだけが対象になること。"""

    def test_includes_predicted_race_without_payout(self, db):
        _make_predicted_race(db, "r_in_range", days_ago=2)

        assert select_verify_targets(db, 8) == ["r_in_range"]

    def test_excludes_race_with_payout(self, db):
        _make_predicted_race(db, "r_collected", days_ago=2, with_payout=True)

        assert select_verify_targets(db, 8) == []

    def test_excludes_race_without_prediction(self, db):
        make_race(
            db, race_id="r_no_prediction", race_date=date.today() - timedelta(days=2)
        )

        assert select_verify_targets(db, 8) == []

    def test_excludes_race_older_than_days(self, db):
        _make_predicted_race(db, "r_too_old", days_ago=30)

        assert select_verify_targets(db, 8) == []

    def test_excludes_today_and_future(self, db):
        _make_predicted_race(db, "r_today", days_ago=0)
        _make_predicted_race(db, "r_future", days_ago=-3)

        assert select_verify_targets(db, 8) == []

    def test_orders_by_date(self, db):
        _make_predicted_race(db, "r_newer", days_ago=1)
        _make_predicted_race(db, "r_older", days_ago=7)

        assert select_verify_targets(db, 8) == ["r_older", "r_newer"]


# ---------------------------------------------------------------------------
# 対象選定: backfill
# ---------------------------------------------------------------------------


class TestSelectUncollectedRaceIds:
    """払戻を持つレースが除かれ、入力順が保たれること。"""

    def test_removes_race_ids_with_payout(self, db):
        make_race(db, race_id="r_done")
        make_payout(db, "r_done")

        race_ids = select_uncollected_race_ids(db, ["r_todo1", "r_done", "r_todo2"])

        assert race_ids == ["r_todo1", "r_todo2"]

    def test_empty_input_returns_empty(self, db):
        assert select_uncollected_race_ids(db, []) == []


# ---------------------------------------------------------------------------
# 収集ループ
# ---------------------------------------------------------------------------


class TestCollectRaceResults:
    @pytest.mark.asyncio
    async def test_saves_each_race(self, db):
        scraper = _StubScraper()

        saved_count, failed_count = await collect_race_results(
            db, scraper, ["r_a", "r_b"]
        )

        assert (saved_count, failed_count) == (2, 0)
        assert scraper.requested_race_ids == ["r_a", "r_b"]
        assert db.query(Result).count() == 2
        assert db.query(Payout).filter_by(race_id="r_a").count() == 2
        assert db.query(Payout).filter_by(race_id="r_b").count() == 2

    @pytest.mark.asyncio
    async def test_commits_per_race(self, db, monkeypatch):
        """1レースごとにcommitすること（途中失敗で全損しない）。"""
        scraper = _StubScraper()
        original_commit = db.commit
        commit_count = 0

        def counting_commit():
            nonlocal commit_count
            commit_count += 1
            original_commit()

        monkeypatch.setattr(db, "commit", counting_commit)

        await collect_race_results(db, scraper, ["r_a", "r_b", "r_c"])

        assert commit_count == 3

    @pytest.mark.asyncio
    async def test_unavailable_race_is_skipped_without_stopping(self, db):
        scraper = _StubScraper(unavailable_race_ids=("r_b",))

        saved_count, failed_count = await collect_race_results(
            db, scraper, ["r_a", "r_b", "r_c"]
        )

        assert (saved_count, failed_count) == (2, 1)
        assert scraper.requested_race_ids == ["r_a", "r_b", "r_c"]
        assert {race_id for (race_id,) in db.query(Payout.race_id).distinct()} == {
            "r_a",
            "r_c",
        }

    @pytest.mark.asyncio
    async def test_empty_targets_is_noop(self, db):
        scraper = _StubScraper()

        assert await collect_race_results(db, scraper, []) == (0, 0)
        assert scraper.requested_race_ids == []


# ---------------------------------------------------------------------------
# backfill / verify のオーケストレーション
# ---------------------------------------------------------------------------


class TestBackfillRaceResults:
    @pytest.mark.asyncio
    async def test_skips_race_ids_with_payout(self, db):
        """払戻済みレースにはスクレイパー呼び出しが起きないこと。"""
        make_race(db, race_id="r_done")
        make_payout(db, "r_done")
        scraper = _StubScraper(graded_race_ids=["r_done", "r_todo"])

        saved_count, failed_count = await backfill_race_results(
            db, scraper, 2024, 2024
        )

        assert scraper.requested_race_ids == ["r_todo"]
        assert (saved_count, failed_count) == (1, 0)

    @pytest.mark.asyncio
    async def test_all_collected_returns_zero(self, db):
        make_race(db, race_id="r_done")
        make_payout(db, "r_done")
        scraper = _StubScraper(graded_race_ids=["r_done"])

        assert await backfill_race_results(db, scraper, 2024, 2024) == (0, 0)
        assert scraper.requested_race_ids == []

    @pytest.mark.asyncio
    async def test_passes_year_range_to_scraper(self, db):
        scraper = _StubScraper(graded_race_ids=[])

        await backfill_race_results(db, scraper, 2021, 2026)

        assert scraper.requested_year_ranges == [(2021, 2026)]


class TestVerifyRaceResults:
    @pytest.mark.asyncio
    async def test_collects_only_selected_targets(self, db):
        _make_predicted_race(db, "r_target", days_ago=2)
        _make_predicted_race(db, "r_collected", days_ago=2, with_payout=True)
        _make_predicted_race(db, "r_too_old", days_ago=40)
        scraper = _StubScraper()

        saved_count, failed_count = await verify_race_results(db, scraper, 8)

        assert scraper.requested_race_ids == ["r_target"]
        assert (saved_count, failed_count) == (1, 0)

    @pytest.mark.asyncio
    async def test_no_targets_returns_zero(self, db):
        scraper = _StubScraper()

        assert await verify_race_results(db, scraper, 8) == (0, 0)
        assert scraper.requested_race_ids == []
