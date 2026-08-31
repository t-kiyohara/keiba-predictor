"""Seed script: load fixtures/sample_race.json into the database.

Usage:
    python -m app.seed
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.database import SessionLocal, init_db
from app.models import Entry, Horse, Jockey, Race, Result, Trainer
from app.scrapers.jra import get_target_race_dates


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def seed() -> None:
    init_db()

    fixtures_path = Path(__file__).parent.parent / "fixtures" / "sample_race.json"
    data = json.loads(fixtures_path.read_text(encoding="utf-8"))

    # スコアリング対象は date >= today のみ（fetch_service._score_existing_races）。
    # fixture のレース日付は固定の過去日なので、実行日から見た直近の土曜日
    # （get_target_race_dates と同じ規則）に付け替えて予想が生成されるようにする。
    upcoming_race_date = get_target_race_dates(date.today())[0]

    db = SessionLocal()
    try:
        # ---- Races ----
        for r in data.get("races", []):
            if db.get(Race, r["id"]) is None:
                db.add(
                    Race(
                        id=r["id"],
                        name=r["name"],
                        date=upcoming_race_date,
                        venue=r["venue"],
                        course_type=r["course_type"],
                        distance=r["distance"],
                        weather=r.get("weather"),
                        track_condition=r.get("track_condition"),
                        grade=r["grade"],
                    )
                )

        # ---- Horses ----
        for h in data.get("horses", []):
            if db.get(Horse, h["id"]) is None:
                db.add(
                    Horse(
                        id=h["id"],
                        name=h["name"],
                        sex=h.get("sex"),
                        birthday=_parse_date(h.get("birthday")),
                        sire=h.get("sire"),
                        dam=h.get("dam"),
                        dam_sire=h.get("dam_sire"),
                    )
                )

        # ---- Jockeys ----
        for j in data.get("jockeys", []):
            if db.get(Jockey, j["id"]) is None:
                db.add(Jockey(id=j["id"], name=j["name"]))

        # ---- Trainers ----
        for t in data.get("trainers", []):
            if db.get(Trainer, t["id"]) is None:
                db.add(Trainer(id=t["id"], name=t["name"]))

        db.flush()

        # ---- Entries ----
        for e in data.get("entries", []):
            exists = (
                db.query(Entry)
                .filter_by(race_id=e["race_id"], horse_id=e["horse_id"])
                .first()
            )
            if exists is None:
                db.add(
                    Entry(
                        race_id=e["race_id"],
                        horse_id=e["horse_id"],
                        jockey_id=e.get("jockey_id"),
                        trainer_id=e.get("trainer_id"),
                        post_position=e.get("post_position"),
                        horse_number=e.get("horse_number"),
                        weight=e.get("weight"),
                        odds=e.get("odds"),
                    )
                )

        # ---- Results ----
        for res in data.get("results", []):
            # Results may reference races not in the races fixture (past races)
            # Ensure race row exists as a minimal stub so FK is satisfied
            race_id = res["race_id"]
            if db.get(Race, race_id) is None:
                db.add(
                    Race(
                        id=race_id,
                        name="（過去レース）",
                        date=date(2024, 1, 1),
                        venue="不明",
                        course_type="芝",
                        distance=2000,
                        grade="OP",
                    )
                )
                db.flush()

            exists = (
                db.query(Result)
                .filter_by(race_id=race_id, horse_id=res["horse_id"])
                .first()
            )
            if exists is None:
                db.add(
                    Result(
                        race_id=race_id,
                        horse_id=res["horse_id"],
                        finish_position=res.get("finish_position"),
                        time=res.get("time"),
                        margin=res.get("margin"),
                        last_3f=res.get("last_3f"),
                    )
                )

        db.commit()
        print("Seed completed successfully.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
