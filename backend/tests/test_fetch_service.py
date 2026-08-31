"""FetchService 統合テスト

スクレイパーをモックした状態で FetchService.execute() の
全7ステップ・オーケストレーションを検証する。
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import date
from unittest.mock import AsyncMock, patch

from app.models import Entry, Horse, Prediction, Race
from app.services.fetch_service import FetchService
from tests.factories import make_entry, make_horse, make_race

# ---------------------------------------------------------------------------
# テスト用定数
# ---------------------------------------------------------------------------

_TARGET_DATE = date(2024, 4, 28)
_RACE_ID = "202604280811"  # "08" = 京都


def _make_graded_races() -> list[dict]:
    return [
        {
            "name": "天皇賞（春）",
            "grade": "G1",
            "venue": "京都",
            "course_type": "芝",
            "distance": 3200,
            "date": _TARGET_DATE,
            "race_number": 11,
        }
    ]


def _make_netkeiba_race_list() -> list[dict]:
    return [{"race_id": _RACE_ID, "race_number": 11}]


def _make_entries_data() -> dict:
    return {
        "race_info": {
            "race_id": _RACE_ID,
            "name": "天皇賞（春）",
            "grade": "G1",
            "venue": "京都",
            "course_type": "芝",
            "distance": 3200,
            "date": _TARGET_DATE.isoformat(),
        },
        "entries": [
            {
                "horse_id": "h_fs_001",
                "horse_name": "フェッチテスト馬A",
                "jockey_id": "j_fs_001",
                "jockey_name": "フェッチテスト騎手",
                "trainer_id": "tr_fs_001",
                "trainer_name": "フェッチテスト調教師",
                "post_position": 1,
                "horse_number": 1,
                "weight": 57.0,
                "odds": None,
            },
            {
                "horse_id": "h_fs_002",
                "horse_name": "フェッチテスト馬B",
                "jockey_id": "j_fs_002",
                "jockey_name": "フェッチテスト騎手2",
                "trainer_id": None,
                "trainer_name": None,
                "post_position": 2,
                "horse_number": 2,
                "weight": 55.0,
                "odds": None,
            },
        ],
    }


def _make_horse_profile() -> dict:
    return {
        "name": "フェッチテスト馬A",
        "sex": "牡",
        "birthday": "2020-03-01",
        "sire": "ディープインパクト",
        "dam": "テスト母馬",
        "dam_sire": "Storm Cat",
    }


@contextmanager
def _full_pipeline_mocks(service: FetchService):
    """全7ステップのスクレイパーをモックするコンテキストマネージャ"""
    with (
        patch.object(service, "_step_determine_dates", return_value=[_TARGET_DATE]),
        patch.object(
            service.jra, "fetch_graded_races",
            new=AsyncMock(return_value=_make_graded_races()),
        ),
        patch.object(
            service.netkeiba, "fetch_race_list_by_date",
            new=AsyncMock(return_value=_make_netkeiba_race_list()),
        ),
        patch.object(
            service.netkeiba, "fetch_race_entries",
            new=AsyncMock(return_value=_make_entries_data()),
        ),
        patch.object(
            service.netkeiba, "fetch_horse_profile",
            new=AsyncMock(return_value=_make_horse_profile()),
        ),
        patch.object(
            service.netkeiba, "fetch_horse_results",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(
            service.weather, "get_weather",
            new=AsyncMock(return_value={"weather": "晴れ", "temp": 20.0,
                                        "humidity": 45, "description": "clear sky"}),
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# テストクラス
# ---------------------------------------------------------------------------

class TestFetchServiceFallback:
    """JRA がレースを返さない場合のフォールバック動作テスト"""

    def test_fallback_scores_existing_races(self, db):
        """JRA がレースなしの場合、既存DB全レースでスコアリングが実行される"""
        # DBに既存レースと出走馬を作成
        race = make_race(db, "r_fb_001", name="フォールバックレース",
                         venue="東京", distance=2000, grade="G1")
        horse = make_horse(db, "h_fb_001", name="フォールバック馬")
        make_entry(db, race.id, horse.id)

        service = FetchService(db)
        with (
            patch.object(service, "_step_determine_dates", return_value=[_TARGET_DATE]),
            patch.object(
                service.jra, "fetch_graded_races", new=AsyncMock(return_value=[]),
            ),
            patch.object(
                service.netkeiba, "fetch_race_list_by_date",
                new=AsyncMock(return_value=[]),
            ),
        ):
            asyncio.run(service.execute())

        # フォールバックスコアリングで Prediction が作成されていること
        preds = db.query(Prediction).filter(Prediction.race_id == race.id).all()
        assert len(preds) == 1
        assert preds[0].rank == 1

    def test_fallback_with_no_db_races(self, db):
        """DBにレースが存在しない場合はエラーなく終了する"""
        service = FetchService(db)
        with (
            patch.object(service, "_step_determine_dates", return_value=[_TARGET_DATE]),
            patch.object(
                service.jra, "fetch_graded_races", new=AsyncMock(return_value=[]),
            ),
            patch.object(
                service.netkeiba, "fetch_race_list_by_date",
                new=AsyncMock(return_value=[]),
            ),
        ):
            # エラーなく完了すること
            asyncio.run(service.execute())

        # Prediction は作成されない（レースなし）
        assert db.query(Prediction).count() == 0


class TestFetchServiceFullPipeline:
    """スクレイパーをモックした全7ステップパイプラインテスト"""

    def test_execute_creates_race_and_horse(self, db):
        """execute() が Race と Horse を DB に作成すること"""
        service = FetchService(db)

        with _full_pipeline_mocks(service):
            asyncio.run(service.execute())

        # Race が DB に保存されていること
        race = db.get(Race, _RACE_ID)
        assert race is not None
        assert race.name == "天皇賞（春）"
        assert race.grade == "G1"
        assert race.venue == "京都"

        # Horse が DB に保存されていること
        horse = db.get(Horse, "h_fs_001")
        assert horse is not None

    def test_execute_creates_entries(self, db):
        """execute() が Entry を DB に作成すること"""
        service = FetchService(db)

        with _full_pipeline_mocks(service):
            asyncio.run(service.execute())

        # 2頭分の Entry が作成されていること
        entries = db.query(Entry).filter(Entry.race_id == _RACE_ID).all()
        assert len(entries) == 2
        horse_ids = {e.horse_id for e in entries}
        assert "h_fs_001" in horse_ids
        assert "h_fs_002" in horse_ids

    def test_execute_creates_predictions(self, db):
        """execute() がスコアリングして Prediction を DB に保存すること"""
        service = FetchService(db)

        with _full_pipeline_mocks(service):
            asyncio.run(service.execute())

        # Prediction が 2 頭分作成されていること
        preds = db.query(Prediction).filter(Prediction.race_id == _RACE_ID).all()
        assert len(preds) == 2

        # ランキングが正しいこと
        ranks = sorted(p.rank for p in preds)
        assert ranks == [1, 2]

    def test_execute_updates_weather(self, db):
        """execute() が天気情報を Race に反映すること"""
        service = FetchService(db)

        with (
            patch.object(service, "_step_determine_dates", return_value=[_TARGET_DATE]),
            patch.object(
                service.jra, "fetch_graded_races",
                new=AsyncMock(return_value=_make_graded_races()),
            ),
            patch.object(
                service.netkeiba, "fetch_race_list_by_date",
                new=AsyncMock(return_value=_make_netkeiba_race_list()),
            ),
            patch.object(
                service.netkeiba, "fetch_race_entries",
                new=AsyncMock(return_value=_make_entries_data()),
            ),
            patch.object(
                service.netkeiba, "fetch_horse_profile",
                new=AsyncMock(return_value=_make_horse_profile()),
            ),
            patch.object(
                service.netkeiba, "fetch_horse_results",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                service.weather, "get_weather",
                new=AsyncMock(return_value={"weather": "曇り", "temp": 15.0,
                                            "humidity": 70, "description": "overcast"}),
            ),
        ):
            asyncio.run(service.execute())

        race = db.get(Race, _RACE_ID)
        assert race is not None
        assert race.weather == "曇り"

    def test_execute_progress_callback_called(self, db):
        """execute() が progress_callback を各ステップで呼び出すこと"""
        progress_calls: list[tuple] = []

        def capture_progress(step, current, total, message, **kwargs):
            progress_calls.append((step, current, total))

        service = FetchService(db, progress_callback=capture_progress)

        with (
            patch.object(service, "_step_determine_dates", return_value=[_TARGET_DATE]),
            patch.object(
                service.jra, "fetch_graded_races", new=AsyncMock(return_value=[]),
            ),
            patch.object(
                service.netkeiba, "fetch_race_list_by_date",
                new=AsyncMock(return_value=[]),
            ),
        ):
            asyncio.run(service.execute())

        # 少なくとも 2 ステップ（日程取得 + レース一覧）の progress が呼ばれること
        assert len(progress_calls) >= 2
        # 全ステップの total は TOTAL_STEPS = 7
        for _, _current, total in progress_calls:
            assert total == FetchService.TOTAL_STEPS
