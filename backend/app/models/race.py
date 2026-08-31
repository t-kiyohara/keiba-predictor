from sqlalchemy import Column, Date, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Race(Base):
    __tablename__ = "races"

    id = Column(String, primary_key=True)  # netkeiba race_id
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False, index=True)
    venue = Column(String, nullable=False, index=True)  # 競馬場名
    course_type = Column(String, nullable=False)  # 芝/ダート
    distance = Column(Integer, nullable=False)  # メートル
    weather = Column(String, nullable=True)
    track_condition = Column(String, nullable=True)  # 良/稍重/重/不良
    grade = Column(String, nullable=False, index=True)  # G1/G2/G3

    entries = relationship("Entry", back_populates="race")
    results = relationship("Result", back_populates="race")
    predictions = relationship("Prediction", back_populates="race")
    payouts = relationship("Payout", back_populates="race")
