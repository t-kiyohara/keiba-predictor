from datetime import date

from pydantic import BaseModel, ConfigDict


class EntryOut(BaseModel):
    """出走馬一覧APIのレスポンスモデル(静的エクスポートの entries と同形)"""

    horse_id: str
    horse_number: int | None
    post_position: int | None
    weight: float | None
    odds: float | None
    jockey_name: str | None
    sex: str | None
    age: int | None


class RaceOut(BaseModel):
    """レース一覧・詳細APIのレスポンスモデル"""

    id: str
    name: str
    date: date
    venue: str
    course_type: str
    distance: int
    weather: str | None
    track_condition: str | None
    grade: str

    model_config = ConfigDict(from_attributes=True)
