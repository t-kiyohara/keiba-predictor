"""馬API統合テスト — FastAPI TestClient を使用"""

from __future__ import annotations

from datetime import date

from tests.factories import make_horse as _make_horse, make_race as _make_race, make_result as _make_result


# ---------------------------------------------------------------------------
# GET /api/horses/{horse_id}
# ---------------------------------------------------------------------------

class TestGetHorse:
    def test_get_horse_found(self, client, db):
        """存在する馬 → 200 + 正しいデータ（血統含む）"""
        _make_horse(
            db, "h_api_001",
            name="ディープインパクト",
            sex="牡",
            birthday=date(2002, 3, 25),
            sire="サンデーサイレンス",
            dam="ウインドインハーヘア",
            dam_sire="Alzao",
        )
        response = client.get("/api/horses/h_api_001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "h_api_001"
        assert data["name"] == "ディープインパクト"
        assert data["sex"] == "牡"
        assert data["birthday"] == "2002-03-25"
        assert data["sire"] == "サンデーサイレンス"
        assert data["dam"] == "ウインドインハーヘア"
        assert data["dam_sire"] == "Alzao"

    def test_get_horse_not_found(self, client):
        """存在しない馬 → 404"""
        response = client.get("/api/horses/nonexistent_horse_id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Horse not found"

    def test_get_horse_optional_fields_null(self, client, db):
        """オプションフィールドが null の場合もレスポンスに含まれること"""
        _make_horse(db, "h_api_null", name="無血統馬", sex=None, birthday=None,
                    sire=None, dam=None, dam_sire=None)
        response = client.get("/api/horses/h_api_null")
        assert response.status_code == 200
        data = response.json()
        assert data["sex"] is None
        assert data["birthday"] is None
        assert data["sire"] is None
        assert data["dam"] is None
        assert data["dam_sire"] is None

    def test_get_horse_response_keys(self, client, db):
        """レスポンスのキーが frontend/src/types/index.ts の Horse 型と一致する"""
        _make_horse(db, "h_api_keys", name="キーテスト馬")
        response = client.get("/api/horses/h_api_keys")
        assert response.status_code == 200
        data = response.json()
        # frontend/src/types/index.ts の Horse interface と一致するキーを検証
        expected_keys = {"id", "name", "sex", "birthday", "sire", "dam", "dam_sire"}
        assert set(data.keys()) == expected_keys


# ---------------------------------------------------------------------------
# GET /api/horses/{horse_id}/results
# ---------------------------------------------------------------------------

class TestGetHorseResults:
    def test_get_horse_results_not_found(self, client):
        """存在しない馬の成績 → 404"""
        response = client.get("/api/horses/nonexistent/results")
        assert response.status_code == 404

    def test_get_horse_results_empty(self, client, db):
        """結果なし → 空リスト"""
        _make_horse(db, "h_res_empty", name="未出走馬")
        response = client.get("/api/horses/h_res_empty/results")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_horse_results_with_data(self, client, db):
        """Result + Race を挿入 → 正しいデータが返る"""
        horse = _make_horse(db, "h_res_001", name="実績馬")
        race1 = _make_race(db, "r_res_001", name="桜花賞",
                           race_date=date(2024, 4, 7), venue="阪神",
                           course_type="芝", distance=1600, grade="G1",
                           track_condition="良")
        _make_result(db, race1.id, horse.id, finish_position=1,
                     time="1:34.5", last_3f=33.2)

        response = client.get(f"/api/horses/{horse.id}/results")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        result = data[0]
        assert result["race_id"] == race1.id
        assert result["race_name"] == "桜花賞"
        assert result["date"] == "2024-04-07"
        assert result["venue"] == "阪神"
        assert result["distance"] == 1600
        assert result["course_type"] == "芝"
        assert result["finish_position"] == 1
        assert result["time"] == "1:34.5"
        assert result["last_3f"] == 33.2

    def test_get_horse_results_date_desc_order(self, client, db):
        """複数成績 → 日付降順で返る"""
        horse = _make_horse(db, "h_res_order", name="順序テスト馬")
        race_old = _make_race(db, "r_res_order_01", name="旧レース",
                              race_date=date(2024, 1, 1))
        race_new = _make_race(db, "r_res_order_02", name="新レース",
                              race_date=date(2024, 6, 1))
        _make_result(db, race_old.id, horse.id, finish_position=2)
        _make_result(db, race_new.id, horse.id, finish_position=1)

        response = client.get(f"/api/horses/{horse.id}/results")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # 日付降順（新しいレースが先）
        assert data[0]["race_id"] == race_new.id
        assert data[1]["race_id"] == race_old.id

    def test_get_horse_results_limit(self, client, db):
        """limit パラメータで件数制限できること"""
        horse = _make_horse(db, "h_res_limit", name="多出走馬")
        for i in range(5):
            race = _make_race(db, f"r_res_limit_{i:02d}", name=f"レース{i}",
                              race_date=date(2024, i + 1, 1))
            _make_result(db, race.id, horse.id, finish_position=i + 1)

        # デフォルト（最大10件）
        response = client.get(f"/api/horses/{horse.id}/results")
        assert response.status_code == 200
        assert len(response.json()) == 5

        # limit=3 を指定
        response = client.get(f"/api/horses/{horse.id}/results?limit=3")
        assert response.status_code == 200
        assert len(response.json()) == 3

        # limit=1 を指定
        response = client.get(f"/api/horses/{horse.id}/results?limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_get_horse_results_response_keys(self, client, db):
        """レスポンスのキーが frontend/src/types/index.ts の RaceResult 型と一致する"""
        horse = _make_horse(db, "h_res_keys", name="キーテスト馬")
        race = _make_race(db, "r_res_keys", name="キーテストレース")
        _make_result(db, race.id, horse.id, finish_position=3)

        response = client.get(f"/api/horses/{horse.id}/results")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        result = data[0]
        # frontend/src/types/index.ts の RaceResult interface と一致するキーを検証
        expected_keys = {"race_id", "race_name", "date", "venue", "distance",
                         "course_type", "track_condition", "finish_position",
                         "time", "last_3f"}
        assert set(result.keys()) == expected_keys
