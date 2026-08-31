from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Payout(Base):
    """レースの払戻金（1レース×券種×組番で1行）。"""

    __tablename__ = "payouts"
    __table_args__ = (
        UniqueConstraint(
            "race_id", "bet_type", "combination", name="uq_payout_race_bet_combination"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(String, ForeignKey("races.id"), nullable=False, index=True)
    # 単勝/複勝/枠連/馬連/ワイド/馬単/三連複/三連単
    bet_type = Column(String, nullable=False)
    # 組番（例: "5" / "5-15" / "5→15→13"）。空白除去済み、区切りは原文のまま
    combination = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)  # 100円あたりの払戻金（円）

    race = relationship("Race", back_populates="payouts")
