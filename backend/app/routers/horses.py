from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Horse, Race, Result
from app.schemas import HorseOut, HorseResultOut

router = APIRouter(prefix="/api/horses", tags=["horses"])


@router.get("/{horse_id}", response_model=HorseOut)
def get_horse(horse_id: str, db: Session = Depends(get_db)):
    """馬の詳細情報を返す"""
    horse = db.get(Horse, horse_id)
    if horse is None:
        raise HTTPException(status_code=404, detail="Horse not found")
    return horse


@router.get("/{horse_id}/results", response_model=list[HorseResultOut])
def get_horse_results(
    horse_id: str, db: Session = Depends(get_db), limit: int = 10
):
    """馬の過去成績を返す（日付降順、最大limit件）"""
    if db.get(Horse, horse_id) is None:
        raise HTTPException(status_code=404, detail="Horse not found")

    rows = (
        db.query(Result, Race)
        .join(Race, Result.race_id == Race.id)
        .filter(Result.horse_id == horse_id)
        .order_by(Race.date.desc())
        .limit(limit)
        .all()
    )

    return [
        HorseResultOut(
            race_id=result.race_id,
            race_name=race.name,
            date=race.date,
            venue=race.venue,
            distance=race.distance,
            course_type=race.course_type,
            track_condition=race.track_condition,
            finish_position=result.finish_position,
            time=result.time,
            last_3f=result.last_3f,
        )
        for result, race in rows
    ]
