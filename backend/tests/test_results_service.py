"""Tests for app.services.results_service.persist_race_result."""

from __future__ import annotations

import copy
from datetime import date

from app.models import Horse, Jockey, Payout, Race, Result, Trainer
from app.services.results_service import persist_race_result
from tests.factories import make_horse, make_race, make_result

RACE_ID = "202405021212"

# NetkeibaScraper.fetch_race_result() の返り値と同じ形
PARSED_RACE_RESULT = {
    "race": {
        "race_id": RACE_ID,
        "name": "第91回東京優駿(GI)",
        "grade": "G1",
        "date": "2024-05-26",
        "venue": "東京",
        "course_type": "芝",
        "distance": 2400,
        "weather": "晴",
        "track_condition": "良",
    },
    "results": [
        {
            "horse_id": "2021105165",
            "horse_name": "テスト馬A",
            "horse_number": 10,
            "finish_position": 1,
            "time": "2:24.3",
            "margin": None,
            "last_3f": 33.5,
            "jockey_id": "01167",
            "jockey_name": "テスト騎手A",
            "trainer_id": "01126",
            "trainer_name": "テスト調教師A",
        },
        {
            "horse_id": "2021104976",
            "horse_name": "テスト馬B",
            "horse_number": 15,
            "finish_position": 2,
            "time": "2:24.4",
            "margin": "クビ",
            "last_3f": 33.9,
            "jockey_id": "01088",
            "jockey_name": "テスト騎手B",
            "trainer_id": "01110",
            "trainer_name": "テスト調教師B",
        },
    ],
    "payouts": [
        {"bet_type": "単勝", "combination": "10", "amount": 4660},
        {"bet_type": "複勝", "combination": "10", "amount": 1020},
        {"bet_type": "複勝", "combination": "15", "amount": 240},
        {"bet_type": "三連単", "combination": "10→15→13", "amount": 212300},
    ],
}


def _parsed(**race_overrides) -> dict:
    """PARSED_RACE_RESULT のコピーを返す（race の一部を差し替え可能）。"""
    parsed = copy.deepcopy(PARSED_RACE_RESULT)
    parsed["race"].update(race_overrides)
    return parsed


class TestPersistRaceResultCreates:
    """レース・馬・騎手・調教師・着順・払戻の新規作成。"""

    def test_creates_race_with_all_fields(self, db):
        persist_race_result(db, _parsed())

        race = db.get(Race, RACE_ID)
        assert race is not None
        assert race.name == "第91回東京優駿(GI)"
        assert race.grade == "G1"
        assert race.date == date(2024, 5, 26)
        assert race.venue == "東京"
        assert race.course_type == "芝"
        assert race.distance == 2400
        assert race.weather == "晴"
        assert race.track_condition == "良"

    def test_creates_master_stubs_for_unknown_ids(self, db):
        """未知の馬/騎手/調教師IDに対してnameだけのスタブ行を作ること。"""
        persist_race_result(db, _parsed())

        assert db.get(Horse, "2021105165").name == "テスト馬A"
        assert db.get(Jockey, "01167").name == "テスト騎手A"
        assert db.get(Trainer, "01126").name == "テスト調教師A"

    def test_creates_results(self, db):
        persist_race_result(db, _parsed())

        results = db.query(Result).filter_by(race_id=RACE_ID).all()
        assert len(results) == 2

        winner = next(r for r in results if r.horse_id == "2021105165")
        assert winner.finish_position == 1
        assert winner.horse_number == 10
        assert winner.time == "2:24.3"
        assert winner.last_3f == 33.5
        assert winner.jockey_name == "テスト騎手A"
        assert winner.trainer_name == "テスト調教師A"

    def test_creates_payouts(self, db):
        persist_race_result(db, _parsed())

        payouts = db.query(Payout).filter_by(race_id=RACE_ID).all()
        assert len(payouts) == 4

        win = next(p for p in payouts if p.bet_type == "単勝")
        assert win.combination == "10"
        assert win.amount == 4660

        trifecta = next(p for p in payouts if p.bet_type == "三連単")
        assert trifecta.combination == "10→15→13"

    def test_missing_race_id_is_noop(self, db):
        parsed = _parsed()
        parsed["race"].pop("race_id")
        persist_race_result(db, parsed)

        assert db.query(Race).count() == 0

    def test_empty_parsed_is_noop(self, db):
        persist_race_result(db, {})

        assert db.query(Race).count() == 0


class TestPersistRaceResultUpgradesStubRace:
    """既存Raceのスタブ値・欠損値を結果ページの値で埋める。"""

    def _make_stub_race(self, db) -> Race:
        """fetch_service / seed.py が作るスタブRaceと同じ値のRace。"""
        return make_race(
            db,
            race_id=RACE_ID,
            name="（過去レース）",
            race_date=date(2024, 1, 1),
            venue="不明",
            course_type="芝",
            distance=2000,
            grade="OP",
            track_condition=None,
            weather=None,
        )

    def test_promotes_grade_from_op(self, db):
        """grade が "OP" なら結果ページの重賞グレードに昇格すること。"""
        self._make_stub_race(db)
        persist_race_result(db, _parsed(grade="G2"))

        assert db.get(Race, RACE_ID).grade == "G2"

    def test_backfills_track_condition_and_weather(self, db):
        """track_condition / weather が None なら埋めること。"""
        self._make_stub_race(db)
        persist_race_result(db, _parsed())

        race = db.get(Race, RACE_ID)
        assert race.track_condition == "良"
        assert race.weather == "晴"

    def test_replaces_stub_name_venue_distance_and_date(self, db):
        """スタブのname/venue/distance/dateを結果ページの値で置き換えること。"""
        self._make_stub_race(db)
        persist_race_result(db, _parsed())

        race = db.get(Race, RACE_ID)
        assert race.name == "第91回東京優駿(GI)"
        assert race.venue == "東京"
        assert race.distance == 2400
        assert race.date == date(2024, 5, 26)


class TestPersistRaceResultKeepsTrustedValues:
    """信頼できる既存値を劣化させないこと。"""

    def _make_trusted_race(self, db) -> Race:
        return make_race(
            db,
            race_id=RACE_ID,
            name="東京優駿(GⅠ)",
            race_date=date(2024, 5, 26),
            venue="東京",
            course_type="ダート",
            distance=2500,
            grade="G1",
            track_condition="稍重",
            weather="雨",
        )

    def test_does_not_overwrite_trusted_fields(self, db):
        self._make_trusted_race(db)
        persist_race_result(db, _parsed(grade="G3"))

        race = db.get(Race, RACE_ID)
        # スタブ値ではないので上書きしない
        assert race.name == "東京優駿(GⅠ)"
        assert race.distance == 2500
        assert race.course_type == "ダート"
        # 既に値があるので埋めない
        assert race.track_condition == "稍重"
        assert race.weather == "雨"
        # グレードは "OP" からの昇格のみ（G1 → G3 の降格はしない）
        assert race.grade == "G1"

    def test_does_not_overwrite_date_when_not_stub(self, db):
        make_race(db, race_id=RACE_ID, race_date=date(2024, 5, 20))
        persist_race_result(db, _parsed())

        assert db.get(Race, RACE_ID).date == date(2024, 5, 20)

    def test_empty_parsed_values_do_not_clear_race(self, db):
        """結果ページ側が空の項目でスタブ値すら潰さないこと。"""
        self._make_trusted_race(db)
        persist_race_result(
            db,
            _parsed(
                name="", grade="", date="", venue="", course_type="", distance=0,
                weather="", track_condition="",
            ),
        )

        race = db.get(Race, RACE_ID)
        assert race.name == "東京優駿(GⅠ)"
        assert race.venue == "東京"
        assert race.distance == 2500
        assert race.date == date(2024, 5, 26)


class TestPersistRaceResultUpsertsResults:
    """Result の (race_id, horse_id) upsert。"""

    def test_updates_existing_result_without_duplicating(self, db):
        make_race(db, race_id=RACE_ID)
        make_horse(db, "2021105165", name="テスト馬A")
        make_result(
            db,
            RACE_ID,
            "2021105165",
            finish_position=5,
            time="9:99.9",
            margin="大差",
            jockey_name="旧騎手",
        )

        persist_race_result(db, _parsed())

        results = db.query(Result).filter_by(
            race_id=RACE_ID, horse_id="2021105165"
        ).all()
        assert len(results) == 1
        assert results[0].finish_position == 1
        assert results[0].time == "2:24.3"
        assert results[0].horse_number == 10
        assert results[0].jockey_name == "テスト騎手A"
        # 結果ページ側がNone（1着なので着差なし）の項目は既存値を残す
        assert results[0].margin == "大差"

    def test_repeated_calls_do_not_duplicate_results(self, db):
        persist_race_result(db, _parsed())
        persist_race_result(db, _parsed())

        assert db.query(Result).filter_by(race_id=RACE_ID).count() == 2


class TestPersistRaceResultReplacesPayouts:
    """Payout は毎回入れ直し（冪等）。"""

    def test_repeated_calls_do_not_duplicate_payouts(self, db):
        persist_race_result(db, _parsed())
        persist_race_result(db, _parsed())

        assert db.query(Payout).filter_by(race_id=RACE_ID).count() == 4

    def test_stale_payouts_are_removed(self, db):
        persist_race_result(db, _parsed())

        parsed = _parsed()
        parsed["payouts"] = [{"bet_type": "単勝", "combination": "10", "amount": 4660}]
        persist_race_result(db, parsed)

        payouts = db.query(Payout).filter_by(race_id=RACE_ID).all()
        assert len(payouts) == 1
        assert payouts[0].bet_type == "単勝"

    def test_duplicate_combinations_in_page_are_deduplicated(self, db):
        parsed = _parsed()
        parsed["payouts"] = [
            {"bet_type": "単勝", "combination": "10", "amount": 4660},
            {"bet_type": "単勝", "combination": "10", "amount": 4660},
        ]
        persist_race_result(db, parsed)

        assert db.query(Payout).filter_by(race_id=RACE_ID).count() == 1
