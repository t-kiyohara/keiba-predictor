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


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (
        UniqueConstraint("race_id", "horse_id", name="uq_entry_race_horse"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(String, ForeignKey("races.id"), nullable=False, index=True)
    horse_id = Column(String, ForeignKey("horses.id"), nullable=False, index=True)
    jockey_id = Column(String, ForeignKey("jockeys.id"), nullable=True, index=True)
    trainer_id = Column(String, ForeignKey("trainers.id"), nullable=True, index=True)
    post_position = Column(Integer, nullable=True)  # 枠番
    horse_number = Column(Integer, nullable=True)  # 馬番
    weight = Column(Float, nullable=True)  # 斤量
    odds = Column(Float, nullable=True)

    race = relationship("Race", back_populates="entries")
    horse = relationship("Horse", back_populates="entries")
    jockey = relationship("Jockey", back_populates="entries")
    trainer = relationship("Trainer", back_populates="entries")
