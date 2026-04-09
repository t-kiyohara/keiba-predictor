"""Basic CRUD tests for Race and Horse models."""

from __future__ import annotations

from datetime import date

from app.models import Horse, Race


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
