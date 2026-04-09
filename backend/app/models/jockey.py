from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.database import Base


class Jockey(Base):
    __tablename__ = "jockeys"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

    entries = relationship("Entry", back_populates="jockey")
