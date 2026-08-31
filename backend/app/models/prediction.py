from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Prediction(Base):
    """1頭分の予想。過去の予想を残すため、生成のたびに新しい行を追加する。

    同じ `created_at` を持つ行の集合が1回の予想（バッチ）に対応する。
    答え合わせ（verification_service）は「レース前に出したバッチ」だけを使う。
    """

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(String, ForeignKey("races.id"), nullable=False)
    horse_id = Column(String, ForeignKey("horses.id"), nullable=False)
    total_score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)
    score_details = Column(JSON, nullable=True)  # ファクター別スコア内訳
    # 予想バッチの識別子（同一バッチの全行が同じ値を持つ）
    created_at = Column(DateTime, nullable=False, index=True)

    race = relationship("Race", back_populates="predictions")
    horse = relationship("Horse", back_populates="predictions")
