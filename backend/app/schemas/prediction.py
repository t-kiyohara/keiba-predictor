from pydantic import BaseModel


class FactorScoreOut(BaseModel):
    """スコアリングファクターの内訳"""

    score: float
    label: str
    weighted: float


class PredictionOut(BaseModel):
    """予想結果APIのレスポンスモデル"""

    rank: int
    horse_id: str
    horse_name: str
    total_score: float
    factor_scores: dict[str, FactorScoreOut]
