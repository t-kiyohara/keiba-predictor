from datetime import date

from pydantic import BaseModel, ConfigDict


class HorseOut(BaseModel):
    """馬詳細APIのレスポンスモデル"""

    id: str
    name: str
    sex: str | None
    birthday: date | None
    sire: str | None
    dam: str | None
    dam_sire: str | None

    model_config = ConfigDict(from_attributes=True)


class HorseResultOut(BaseModel):
    """馬成績APIのレスポンスモデル（Result + Race の結合データ）"""

    race_id: str
    race_name: str
    date: date
    venue: str
    distance: int
    course_type: str
    track_condition: str | None
    finish_position: int | None
    time: str | None
    last_3f: float | None
