"""Basic CRUD tests for Race and Horse models."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Entry, Horse, Payout, Race, Result


class TestRaceModel:
    def test_create_race(self, db):
        race = Race(
            id="test_race_001",
            name="テストレース",
            date=date(2024, 4, 28),
            venue="東京",
            course_type="芝",
            distance=2000,
            weather="晴",
            track_condition="良",
            grade="G1",
        )
        db.add(race)
        db.flush()

        fetched = db.get(Race, "test_race_001")
        assert fetched is not None
        assert fetched.name == "テストレース"
        assert fetched.venue == "東京"
        assert fetched.distance == 2000
        assert fetched.grade == "G1"
        assert fetched.date == date(2024, 4, 28)

    def test_race_optional_fields(self, db):
        race = Race(
            id="test_race_002",
            name="未定レース",
            date=date(2024, 5, 1),
            venue="阪神",
            course_type="ダート",
            distance=1800,
            grade="G2",
        )
        db.add(race)
        db.flush()

        fetched = db.get(Race, "test_race_002")
        assert fetched.weather is None
        assert fetched.track_condition is None

    def test_race_relationships_empty(self, db):
        race = Race(
            id="test_race_003",
            name="関係テスト",
            date=date(2024, 6, 1),
            venue="中山",
            course_type="芝",
            distance=1600,
            grade="G3",
        )
        db.add(race)
        db.flush()

        fetched = db.get(Race, "test_race_003")
        assert fetched.entries == []
        assert fetched.results == []
        assert fetched.predictions == []


class TestHorseModel:
    def test_create_horse(self, db):
        horse = Horse(
            id="test_horse_001",
            name="テスト馬",
            sex="牡",
            birthday=date(2020, 3, 15),
            sire="ディープインパクト",
            dam="テスト母",
            dam_sire="Storm Cat",
        )
        db.add(horse)
        db.flush()

        fetched = db.get(Horse, "test_horse_001")
        assert fetched is not None
        assert fetched.name == "テスト馬"
        assert fetched.sex == "牡"
        assert fetched.sire == "ディープインパクト"
        assert fetched.birthday == date(2020, 3, 15)

    def test_horse_optional_fields(self, db):
        horse = Horse(
            id="test_horse_002",
            name="不明馬",
        )
        db.add(horse)
        db.flush()

        fetched = db.get(Horse, "test_horse_002")
        assert fetched.sex is None
        assert fetched.birthday is None
        assert fetched.sire is None
        assert fetched.dam is None
        assert fetched.dam_sire is None

    def test_horse_relationships_empty(self, db):
        horse = Horse(
            id="test_horse_003",
            name="関係テスト馬",
        )
        db.add(horse)
        db.flush()

        fetched = db.get(Horse, "test_horse_003")
        assert fetched.entries == []
        assert fetched.results == []


class TestUniqueConstraints:
    """DBレベルの一意制約がスキーマに反映されていることの確認。"""

    def _make_race_and_horse(self, db, suffix: str) -> tuple[str, str]:
        race_id = f"r_uq_{suffix}"
        horse_id = f"h_uq_{suffix}"
        db.add(
            Race(
                id=race_id,
                name="制約テスト",
                date=date(2024, 4, 28),
                venue="東京",
                course_type="芝",
                distance=2000,
                grade="G1",
            )
        )
        db.add(Horse(id=horse_id, name="制約テスト馬"))
        db.flush()
        return race_id, horse_id

    def test_entry_race_horse_is_unique(self, db):
        race_id, horse_id = self._make_race_and_horse(db, "entry")
        db.add(Entry(race_id=race_id, horse_id=horse_id, horse_number=1))
        db.flush()

        db.add(Entry(race_id=race_id, horse_id=horse_id, horse_number=2))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_result_race_horse_is_unique(self, db):
        race_id, horse_id = self._make_race_and_horse(db, "result")
        db.add(Result(race_id=race_id, horse_id=horse_id, finish_position=1))
        db.flush()

        db.add(Result(race_id=race_id, horse_id=horse_id, finish_position=2))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_payout_race_bet_combination_is_unique(self, db):
        race_id, _ = self._make_race_and_horse(db, "payout")
        db.add(
            Payout(race_id=race_id, bet_type="単勝", combination="5", amount=4660)
        )
        db.flush()

        db.add(Payout(race_id=race_id, bet_type="単勝", combination="5", amount=200))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_payout_allows_multiple_combinations_per_bet_type(self, db):
        """複勝のように同一券種で複数組番があるケースは許可されること。"""
        race_id, _ = self._make_race_and_horse(db, "payout_multi")
        db.add_all(
            [
                Payout(
                    race_id=race_id, bet_type="複勝", combination="5", amount=1020
                ),
                Payout(race_id=race_id, bet_type="複勝", combination="15", amount=240),
            ]
        )
        db.flush()

        assert db.query(Payout).filter_by(race_id=race_id).count() == 2
