from datetime import date

from pydantic import BaseModel, ConfigDict


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
