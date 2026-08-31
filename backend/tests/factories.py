"""テスト用ファクトリ関数 — 共通のデータ生成ヘルパー

テスト間でコードを重複させないよう、各テストファイルで共通使用する
エンティティ生成ロジックをここに集約する。
"""

from __future__ import annotations

from datetime import date as DateType

from app.models import Entry, Horse, Jockey, Prediction, Race, Result, Trainer


def make_race(
    db,
    race_id: str = "r_test_001",
    name: str = "テストレース",
    venue: str = "東京",
    course_type: str = "芝",
    distance: int = 2000,
    grade: str = "G1",
    track_condition: str = "良",
    weather: str | None = None,
    race_date: DateType | None = None,
) -> Race:
    """Race を生成して DB に追加する"""
    race = Race(
        id=race_id,
        name=name,
        date=race_date or DateType(2024, 4, 28),
        venue=venue,
        course_type=course_type,
        distance=distance,
        grade=grade,
        track_condition=track_condition,
        weather=weather,
    )
    db.add(race)
    db.flush()
    return race


def make_horse(
    db,
    horse_id: str,
    name: str = "テスト馬",
    sex: str | None = None,
    birthday: DateType | None = None,
    sire: str | None = None,
    dam: str | None = None,
    dam_sire: str | None = None,
) -> Horse:
    """Horse を生成して DB に追加する"""
    horse = Horse(
        id=horse_id,
        name=name,
        sex=sex,
        birthday=birthday,
        sire=sire,
        dam=dam,
        dam_sire=dam_sire,
    )
    db.add(horse)
    db.flush()
    return horse


def make_result(
    db,
    race_id: str,
    horse_id: str,
    finish_position: int = 1,
    time: str | None = None,
    last_3f: float | None = None,
    margin: str | None = None,
    jockey_name: str | None = None,
    trainer_name: str | None = None,
) -> Result:
    """Result を生成して DB に追加する"""
    result = Result(
        race_id=race_id,
        horse_id=horse_id,
        finish_position=finish_position,
        time=time,
        last_3f=last_3f,
        margin=margin,
        jockey_name=jockey_name,
        trainer_name=trainer_name,
    )
    db.add(result)
    db.flush()
    return result


def make_prediction(
    db,
    race_id: str,
    horse_id: str,
    rank: int = 1,
    total_score: float = 80.0,
    score_details: dict | None = None,
) -> Prediction:
    """Prediction を生成して DB に追加する"""
    pred = Prediction(
        race_id=race_id,
        horse_id=horse_id,
        rank=rank,
        total_score=total_score,
        score_details=score_details or {},
    )
    db.add(pred)
    db.flush()
    return pred


def make_jockey(
    db,
    jockey_id: str = "j_test_001",
    name: str = "テスト騎手",
) -> Jockey:
    """Jockey を生成して DB に追加する"""
    jockey = Jockey(id=jockey_id, name=name)
    db.add(jockey)
    db.flush()
    return jockey


def make_trainer(
    db,
    trainer_id: str = "tr_test_001",
    name: str = "テスト調教師",
) -> Trainer:
    """Trainer を生成して DB に追加する"""
    trainer = Trainer(id=trainer_id, name=name)
    db.add(trainer)
    db.flush()
    return trainer


def make_entry(
    db,
    race_id: str,
    horse_id: str,
    jockey_id: str | None = None,
    trainer_id: str | None = None,
    post_position: int = 1,
    horse_number: int = 1,
    weight: float | None = None,
    odds: float | None = None,
) -> Entry:
    """Entry を生成して DB に追加する"""
    entry = Entry(
        race_id=race_id,
        horse_id=horse_id,
        jockey_id=jockey_id,
        trainer_id=trainer_id,
        post_position=post_position,
        horse_number=horse_number,
        weight=weight,
        odds=odds,
    )
    db.add(entry)
    db.flush()
    return entry
