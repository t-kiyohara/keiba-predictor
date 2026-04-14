from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Horse, Prediction, Race
from app.schemas import PredictionOut, RaceOut

router = APIRouter(prefix="/api/races", tags=["races"])


@router.get("", response_model=list[RaceOut])
def list_races(db: Session = Depends(get_db)):
    """レース一覧を返す（日付降順）"""
    return db.query(Race).order_by(Race.date.desc()).all()


@router.get("/{race_id}", response_model=RaceOut)
def get_race(race_id: str, db: Session = Depends(get_db)):
    """レース詳細を返す"""
    race = db.get(Race, race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return race


@router.get("/{race_id}/predictions", response_model=list[PredictionOut])
def get_race_predictions(race_id: str, db: Session = Depends(get_db)):
    """レースの予想結果を返す（スコア降順）"""
    race = db.get(Race, race_id)
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
        PredictionOut(
            rank=pred.rank,
            horse_id=pred.horse_id,
            horse_name=horse.name,
            total_score=pred.total_score,
            factor_scores=pred.score_details or {},
        )
        for pred, horse in rows
    ]
