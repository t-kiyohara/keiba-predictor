from sqlalchemy import Column, Date, String
from sqlalchemy.orm import relationship

from app.database import Base


class Horse(Base):
    __tablename__ = "horses"

    id = Column(String, primary_key=True)  # netkeiba horse_id
    name = Column(String, nullable=False)
    sex = Column(String, nullable=True)
    birthday = Column(Date, nullable=True)
    sire = Column(String, nullable=True, index=True)  # 父
    dam = Column(String, nullable=True)  # 母
    dam_sire = Column(String, nullable=True, index=True)  # 母父

    entries = relationship("Entry", back_populates="horse")
    results = relationship("Result", back_populates="horse")
    predictions = relationship("Prediction", back_populates="horse")
