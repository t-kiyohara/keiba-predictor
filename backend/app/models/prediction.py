from sqlalchemy import Column, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(String, ForeignKey("races.id"), nullable=False)
    horse_id = Column(String, ForeignKey("horses.id"), nullable=False)
    total_score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)
    score_details = Column(JSON, nullable=True)  # ファクター別スコア内訳

    race = relationship("Race", back_populates="predictions")
    horse = relationship("Horse", back_populates="predictions")
