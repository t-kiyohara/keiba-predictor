from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Entry, Horse, Jockey, Prediction, Race, Trainer

router = APIRouter(prefix="/api/races", tags=["races"])


@router.get("")
def list_races(db: Session = Depends(get_db)):
    """レース一覧を返す（日付降順）"""
    races = db.query(Race).order_by(Race.date.desc()).all()
    return [
        {
            "id": race.id,
            "name": race.name,
            "date": str(race.date),
            "venue": race.venue,
            "course_type": race.course_type,
            "distance": race.distance,
            "weather": race.weather,
            "track_condition": race.track_condition,
            "grade": race.grade,
        }
        for race in races
    ]


@router.get("/{race_id}")
def get_race(race_id: str, db: Session = Depends(get_db)):
    """レース詳細を返す"""
    race = db.query(Race).filter(Race.id == race_id).first()
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return {
        "id": race.id,
        "name": race.name,
        "date": str(race.date),
        "venue": race.venue,
        "course_type": race.course_type,
        "distance": race.distance,
        "weather": race.weather,
        "track_condition": race.track_condition,
        "grade": race.grade,
    }


@router.get("/{race_id}/predictions")
def get_race_predictions(race_id: str, db: Session = Depends(get_db)):
    """レースの予想結果を返す（スコア降順）"""
    # レースの存在確認
    race = db.query(Race).filter(Race.id == race_id).first()
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")

    rows = (
        db.query(Prediction, Horse)
        .join(Horse, Prediction.horse_id == Horse.id)
        .filter(Prediction.race_id == race_id)
        .order_by(Prediction.rank)
        .all()
    )

    return [
        {
            "rank": pred.rank,
            "horse_id": pred.horse_id,
            "horse_name": horse.name,
            "total_score": pred.total_score,
            "factor_scores": pred.score_details or {},
        }
        for pred, horse in rows
    ]
