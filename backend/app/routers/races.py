from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Entry, Horse, Jockey, Prediction, Race
from app.schemas import EntryOut, PredictionOut, RaceOut
from app.scoring.engine import latest_prediction_batch
from app.services.export_service import _entry_payload, _sorted_entries

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
    """レースの最新予想バッチを返す（スコア降順）

    予想は履歴として蓄積されるため、最新の created_at を持つバッチのみを返す。
    """
    race = db.get(Race, race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")

    rows = (
        db.query(Prediction, Horse)
        .join(Horse, Prediction.horse_id == Horse.id)
        .filter(Prediction.race_id == race_id)
        .all()
    )
    horse_name_by_id = {horse.id: horse.name for _, horse in rows}

    return [
        PredictionOut(
            rank=pred.rank,
            horse_id=pred.horse_id,
            horse_name=horse_name_by_id[pred.horse_id],
            total_score=pred.total_score,
            factor_scores=pred.score_details or {},
        )
        for pred in latest_prediction_batch(pred for pred, _ in rows)
    ]


@router.get("/{race_id}/entries", response_model=list[EntryOut])
def get_race_entries(race_id: str, db: Session = Depends(get_db)):
    """レースの出走馬一覧を返す（馬番昇順。静的エクスポートの entries と同形）"""
    race = db.get(Race, race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")

    entries = db.query(Entry).filter(Entry.race_id == race_id).all()
    horse_ids = [e.horse_id for e in entries]
    horse_by_id = (
        {h.id: h for h in db.query(Horse).filter(Horse.id.in_(horse_ids)).all()}
        if horse_ids
        else {}
    )
    jockey_ids = [e.jockey_id for e in entries if e.jockey_id]
    jockey_name_by_id = (
        {j.id: j.name for j in db.query(Jockey).filter(Jockey.id.in_(jockey_ids)).all()}
        if jockey_ids
        else {}
    )
    return [
        _entry_payload(entry, horse_by_id, jockey_name_by_id, race.date)
        for entry in _sorted_entries(entries)
    ]
