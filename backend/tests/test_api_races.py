"""レースAPI統合テスト — FastAPI TestClient を使用"""

from __future__ import annotations

from datetime import date

from app.models import Horse, Prediction, Race


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def _make_race(db, race_id="r_api_001", name="テストレース", venue="東京",
               course_type="芝", distance=2000, grade="G1",
               race_date=None, weather="晴", track_condition="良"):
    race_date = race_date or date(2024, 4, 28)
    race = Race(
        id=race_id,
        name=name,
        date=race_date,
        venue=venue,
        course_type=course_type,
        distance=distance,
        weather=weather,
        track_condition=track_condition,
        grade=grade,
    )
    db.add(race)
    db.flush()
    return race


def _make_horse(db, horse_id, name="テスト馬"):
    horse = Horse(id=horse_id, name=name)
    db.add(horse)
    db.flush()
    return horse


def _make_prediction(db, race_id, horse_id, rank=1, total_score=80.0, score_details=None):
    pred = Prediction(
        race_id=race_id,
        horse_id=horse_id,
        rank=rank,
        total_score=total_score,
        score_details=score_details or {},
    )
    db.add(pred)
    db.flush()
    return pred


# ---------------------------------------------------------------------------
# GET /api/races
# ---------------------------------------------------------------------------

class TestListRaces:
    def test_list_races_empty(self, client):
        """レースがない場合は空リストを返す"""
        response = client.get("/api/races")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_races_with_data(self, client, db):
        """Race を挿入後、リストに含まれること"""
        _make_race(db, "r_list_001", name="天皇賞（春）")
        response = client.get("/api/races")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "r_list_001"
        assert data[0]["name"] == "天皇賞（春）"

    def test_list_races_response_keys(self, client, db):
        """レスポンスのキーが frontend/src/types/index.ts の Race 型と一致する"""
        _make_race(db, "r_list_002", name="安田記念")
        response = client.get("/api/races")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        race = data[0]
        # frontend/src/types/index.ts の Race interface と一致するキーを検証
        expected_keys = {"id", "name", "date", "venue", "course_type", "distance",
                         "weather", "track_condition", "grade"}
        assert set(race.keys()) == expected_keys

    def test_list_races_multiple_date_order(self, client, db):
        """複数レースが日付降順で返ること"""
        _make_race(db, "r_order_001", name="旧レース", race_date=date(2024, 1, 1))
        _make_race(db, "r_order_002", name="新レース", race_date=date(2024, 6, 1))
        response = client.get("/api/races")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # 日付降順（新しい順）
        assert data[0]["id"] == "r_order_002"
        assert data[1]["id"] == "r_order_001"


# ---------------------------------------------------------------------------
# GET /api/races/{race_id}
# ---------------------------------------------------------------------------

class TestGetRace:
    def test_get_race_found(self, client, db):
        """存在するレース → 200 + 正しいデータ"""
        _make_race(db, "r_get_001", name="皐月賞", venue="中山",
                   course_type="芝", distance=2000, grade="G1",
                   race_date=date(2024, 4, 14), weather="曇", track_condition="良")
        response = client.get("/api/races/r_get_001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "r_get_001"
        assert data["name"] == "皐月賞"
        assert data["venue"] == "中山"
        assert data["course_type"] == "芝"
        assert data["distance"] == 2000
        assert data["grade"] == "G1"
        assert data["date"] == "2024-04-14"
        assert data["weather"] == "曇"
        assert data["track_condition"] == "良"

    def test_get_race_not_found(self, client):
        """存在しないレース → 404"""
        response = client.get("/api/races/nonexistent_race_id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Race not found"

    def test_get_race_response_keys(self, client, db):
        """レスポンスのキーが frontend/src/types/index.ts の Race 型と一致する"""
        _make_race(db, "r_keys_001", name="日本ダービー")
        response = client.get("/api/races/r_keys_001")
        assert response.status_code == 200
        data = response.json()
        expected_keys = {"id", "name", "date", "venue", "course_type", "distance",
                         "weather", "track_condition", "grade"}
        assert set(data.keys()) == expected_keys


# ---------------------------------------------------------------------------
# GET /api/races/{race_id}/predictions
# ---------------------------------------------------------------------------

class TestGetRacePredictions:
    def test_get_predictions_race_not_found(self, client):
        """存在しないレースの予想 → 404"""
        response = client.get("/api/races/nonexistent_id/predictions")
        assert response.status_code == 404

    def test_get_predictions_empty(self, client, db):
        """予想なしレース → 空リスト"""
        _make_race(db, "r_pred_empty", name="予想なしレース")
        response = client.get("/api/races/r_pred_empty/predictions")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_predictions_with_data(self, client, db):
        """Prediction + Horse を挿入 → ランキング順で返る"""
        race = _make_race(db, "r_pred_001", name="予想ありレース")
        horse1 = _make_horse(db, "h_pred_001", name="予想馬A")
        horse2 = _make_horse(db, "h_pred_002", name="予想馬B")
        horse3 = _make_horse(db, "h_pred_003", name="予想馬C")
        _make_prediction(db, race.id, horse1.id, rank=1, total_score=90.0)
        _make_prediction(db, race.id, horse2.id, rank=2, total_score=75.0)
        _make_prediction(db, race.id, horse3.id, rank=3, total_score=60.0)

        response = client.get(f"/api/races/{race.id}/predictions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # ランキング順（rank 昇順）で返ること
        assert data[0]["rank"] == 1
        assert data[1]["rank"] == 2
        assert data[2]["rank"] == 3
        # スコア降順であること
        assert data[0]["total_score"] == 90.0
        assert data[1]["total_score"] == 75.0
        assert data[2]["total_score"] == 60.0

    def test_get_predictions_horse_name_included(self, client, db):
        """予想結果に馬名が含まれること"""
        race = _make_race(db, "r_pred_name", name="馬名テストレース")
        horse = _make_horse(db, "h_pred_name", name="サンプル馬")
        _make_prediction(db, race.id, horse.id, rank=1, total_score=85.0)

        response = client.get(f"/api/races/{race.id}/predictions")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["horse_name"] == "サンプル馬"
        assert data[0]["horse_id"] == horse.id

    def test_get_predictions_response_keys(self, client, db):
        """レスポンスのキーが frontend/src/types/index.ts の Prediction 型と一致する"""
        race = _make_race(db, "r_pred_keys", name="キーテストレース")
        horse = _make_horse(db, "h_pred_keys", name="キーテスト馬")
        _make_prediction(db, race.id, horse.id, rank=1, total_score=70.0,
                         score_details={"recent_form": {"score": 80.0, "label": "近走", "weighted": 16.0}})

        response = client.get(f"/api/races/{race.id}/predictions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        pred = data[0]
        # frontend/src/types/index.ts の Prediction interface と一致するキーを検証
        expected_keys = {"rank", "horse_id", "horse_name", "total_score", "factor_scores"}
        assert set(pred.keys()) == expected_keys
