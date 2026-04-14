from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(String, ForeignKey("races.id"), nullable=False, index=True)
    horse_id = Column(String, ForeignKey("horses.id"), nullable=False, index=True)
    finish_position = Column(Integer, nullable=True)  # 着順
    time = Column(String, nullable=True)  # 走破タイム
    margin = Column(String, nullable=True)  # 着差
    last_3f = Column(Float, nullable=True)  # 上がり3F

    race = relationship("Race", back_populates="results")
    horse = relationship("Horse", back_populates="results")
