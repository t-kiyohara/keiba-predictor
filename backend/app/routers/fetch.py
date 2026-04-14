from dataclasses import dataclass
from threading import Lock

from fastapi import APIRouter, BackgroundTasks

from app.schemas import FetchProgressOut, FetchStartOut
from app.services.fetch_service import FetchService

router = APIRouter(prefix="/api/fetch", tags=["fetch"])


@dataclass
class FetchProgress:
    """データ取得進捗の内部状態"""

    status: str = "idle"  # idle | running | completed | error
    step: str = ""
    current: int = 0
    total: int = 0
    message: str = ""
    estimated_remaining: float | None = None


_progress = FetchProgress()
_progress_lock = Lock()


@router.post("", response_model=FetchStartOut)
async def start_fetch(background_tasks: BackgroundTasks):
    """データ取得を開始（バックグラウンドタスク）"""
    with _progress_lock:
        if _progress.status == "running":
            return FetchStartOut(
                status="already_running", message="データ取得が既に実行中です"
            )
        _progress.status = "running"
        _progress.step = "初期化"
        _progress.current = 0
        _progress.total = 7
        _progress.message = "データ取得を開始します..."
        _progress.estimated_remaining = None

    background_tasks.add_task(_run_fetch)
    return FetchStartOut(status="started", message="データ取得を開始しました")


@router.get("/progress", response_model=FetchProgressOut)
def get_progress():
    """データ取得の進捗を返す"""
    with _progress_lock:
        return FetchProgressOut(
            status=_progress.status,
            step=_progress.step,
            current=_progress.current,
            total=_progress.total,
            message=_progress.message,
            estimated_remaining=_progress.estimated_remaining,
        )


async def _run_fetch():
    """バックグラウンドでデータ取得を実行（独自セッションを使用）"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        service = FetchService(db, progress_callback=_update_progress)
        await service.execute()
        with _progress_lock:
            _progress.status = "completed"
            _progress.message = "データ取得が完了しました"
    except Exception as e:
        with _progress_lock:
            _progress.status = "error"
            _progress.message = f"エラー: {str(e)}"
    finally:
        db.close()


def _update_progress(
    step: str,
    current: int,
    total: int,
    message: str,
    estimated_remaining: float | None = None,
):
    """進捗更新コールバック"""
    with _progress_lock:
        _progress.step = step
        _progress.current = current
        _progress.total = total
        _progress.message = message
        _progress.estimated_remaining = estimated_remaining
