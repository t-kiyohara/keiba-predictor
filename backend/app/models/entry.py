from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Entry(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(String, ForeignKey("races.id"), nullable=False)
    horse_id = Column(String, ForeignKey("horses.id"), nullable=False)
    jockey_id = Column(String, ForeignKey("jockeys.id"), nullable=True)
    trainer_id = Column(String, ForeignKey("trainers.id"), nullable=True)
    post_position = Column(Integer, nullable=True)  # 枠番
    horse_number = Column(Integer, nullable=True)  # 馬番
    weight = Column(Float, nullable=True)  # 斤量
    odds = Column(Float, nullable=True)

    race = relationship("Race", back_populates="entries")
    horse = relationship("Horse", back_populates="entries")
    jockey = relationship("Jockey", back_populates="entries")
    trainer = relationship("Trainer", back_populates="entries")
