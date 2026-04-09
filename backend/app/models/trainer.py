from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.database import Base


class Trainer(Base):
    __tablename__ = "trainers"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

    entries = relationship("Entry", back_populates="trainer")
