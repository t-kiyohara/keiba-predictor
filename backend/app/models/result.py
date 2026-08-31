from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (
        UniqueConstraint("race_id", "horse_id", name="uq_result_race_horse"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(String, ForeignKey("races.id"), nullable=False, index=True)
    horse_id = Column(String, ForeignKey("horses.id"), nullable=False, index=True)
    horse_number = Column(Integer, nullable=True)  # 馬番（払戻の組番との突合に使う）
    finish_position = Column(Integer, nullable=True)  # 着順
    time = Column(String, nullable=True)  # 走破タイム
    margin = Column(String, nullable=True)  # 着差
    last_3f = Column(Float, nullable=True)  # 上がり3F
    jockey_name = Column(String, nullable=True, index=True)  # 騎手名（Entry非依存）
    trainer_name = Column(String, nullable=True, index=True)  # 調教師名（後続WPで導入）

    race = relationship("Race", back_populates="results")
    horse = relationship("Horse", back_populates="results")
