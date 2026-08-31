from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import StatsOut
from app.services.verification_service import build_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    """予想の答え合わせ（的中率・回収率・レース別収支）を返す"""
    return build_stats(db)
