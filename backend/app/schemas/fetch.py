from pydantic import BaseModel


class FetchProgressOut(BaseModel):
    """データ取得進捗APIのレスポンスモデル"""

    status: str  # idle | running | completed | error
    step: str
    current: int
    total: int
    message: str
    estimated_remaining: float | None = None


class FetchStartOut(BaseModel):
    """データ取得開始APIのレスポンスモデル"""

    status: str
    message: str
