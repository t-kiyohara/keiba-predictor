from fastapi import APIRouter, BackgroundTasks

from app.services.fetch_service import FetchService

router = APIRouter(prefix="/api/fetch", tags=["fetch"])

# 進捗をモジュールレベルで管理（シンプルな実装）
_progress: dict = {
    "status": "idle",  # idle | running | completed | error
    "step": "",
    "current": 0,
    "total": 0,
    "message": "",
    "estimated_remaining": None,
}


@router.post("")
async def start_fetch(background_tasks: BackgroundTasks):
    """データ取得を開始（バックグラウンドタスク）"""
    global _progress
    if _progress["status"] == "running":
        return {"status": "already_running", "message": "データ取得が既に実行中です"}

    _progress = {
        "status": "running",
        "step": "初期化",
        "current": 0,
        "total": 7,
        "message": "データ取得を開始します...",
        "estimated_remaining": None,
    }

    background_tasks.add_task(_run_fetch)
    return {"status": "started", "message": "データ取得を開始しました"}


@router.get("/progress")
def get_progress():
    """データ取得の進捗を返す"""
    return _progress


async def _run_fetch():
    """バックグラウンドでデータ取得を実行（独自セッションを使用）"""
    global _progress
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        service = FetchService(db, progress_callback=_update_progress)
        await service.execute()
        _progress["status"] = "completed"
        _progress["message"] = "データ取得が完了しました"
    except Exception as e:
        _progress["status"] = "error"
        _progress["message"] = f"エラー: {str(e)}"
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
    global _progress
    _progress.update(
        {
            "step": step,
            "current": current,
            "total": total,
            "message": message,
            "estimated_remaining": estimated_remaining,
        }
    )
