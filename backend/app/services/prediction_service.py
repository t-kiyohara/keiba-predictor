from sqlalchemy.orm import Session

from app.scoring.engine import ScoringEngine


class PredictionService:
    """予想生成のサービス層"""

    def __init__(self, db: Session):
        self.db = db
        self.engine = ScoringEngine(db)

    def generate_predictions(self, race_id: str) -> list[dict]:
        """指定レースの予想を生成（または再生成）"""
        return self.engine.predict_race(race_id)
