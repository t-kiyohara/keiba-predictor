"""データ取得API テスト"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.routers.fetch import FetchProgress


@pytest.fixture(autouse=True)
def reset_fetch_progress():
    """各テスト前に fetch router の _progress を idle 状態にリセットする"""
    import app.routers.fetch as fetch_router
    fetch_router._progress = FetchProgress()
    yield


@pytest.fixture
def mock_run_fetch(monkeypatch):
    """_run_fetch を no-op 化し、実スクレイパー呼び出し・本番DB書き込みを防ぐ"""
    mock = AsyncMock()
    monkeypatch.setattr("app.routers.fetch._run_fetch", mock)
    return mock


# ---------------------------------------------------------------------------
# GET /api/fetch/progress
# ---------------------------------------------------------------------------

class TestGetProgress:
    def test_get_progress_keys(self, client):
        """進捗エンドポイントが正しいキーを返すこと"""
        response = client.get("/api/fetch/progress")
        assert response.status_code == 200
        data = response.json()
        # frontend/src/types/index.ts の FetchProgress interface と一致するキーを検証
        expected_keys = {"status", "step", "current", "total", "message",
                         "estimated_remaining"}
        assert set(data.keys()) == expected_keys

    def test_get_progress_initial_status(self, client):
        """初期状態の status が有効な値であること"""
        response = client.get("/api/fetch/progress")
        assert response.status_code == 200
        data = response.json()
        # status は idle / running / completed / error のいずれか
        assert data["status"] in {"idle", "running", "completed", "error"}

    def test_get_progress_status_idle_after_reset(self, client):
        """fetch router の _progress が idle にリセットされていること

        (autouse fixture)
        """
        response = client.get("/api/fetch/progress")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"
        assert data["current"] == 0
        assert data["total"] == 0
        assert data["estimated_remaining"] is None


# ---------------------------------------------------------------------------
# POST /api/fetch
# ---------------------------------------------------------------------------

class TestStartFetch:
    def test_start_fetch_returns_started(self, client, mock_run_fetch):
        """POST /api/fetch → status: "started" が返ること"""
        response = client.post("/api/fetch")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "message" in data
        # バックグラウンドタスクとして _run_fetch がスケジュールされたこと
        mock_run_fetch.assert_called_once()

    def test_start_fetch_already_running(self, client, mock_run_fetch):
        """二重実行防止: running 中に POST → already_running が返ること"""
        import app.routers.fetch as fetch_router
        # running 状態に設定
        fetch_router._progress = FetchProgress(
            status="running",
            step="テスト中",
            current=1,
            total=7,
            message="実行中...",
        )
        response = client.post("/api/fetch")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_running"
        assert "message" in data
        # 既に実行中のため、新たな _run_fetch はスケジュールされないこと
        mock_run_fetch.assert_not_called()

    def test_start_fetch_response_has_status_and_message(self, client, mock_run_fetch):
        """POST /api/fetch のレスポンスに status と message が含まれること"""
        response = client.post("/api/fetch")
        assert response.status_code == 200
        data = response.json()
        # レスポンスには status と message が含まれること
        assert "status" in data
        assert "message" in data
        # idle から開始した場合、started が返ること
        assert data["status"] == "started"
        # バックグラウンドタスクとして _run_fetch がスケジュールされたこと
        mock_run_fetch.assert_called_once()
