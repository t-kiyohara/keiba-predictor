"""答え合わせAPI統合テスト — GET /api/stats"""

from __future__ import annotations

from datetime import datetime

from tests.factories import (
    make_entry,
    make_horse,
    make_payout,
    make_prediction,
    make_race,
    make_result,
)


class TestGetStats:
    def test_get_stats_empty(self, client):
        """対象データが無い場合も契約どおりの形を返す"""
        response = client.get("/api/stats")
        assert response.status_code == 200
        assert response.json() == {
            "summary": {
                "races": 0,
                "win_hit_rate": 0.0,
                "win_roi": 0.0,
                "place_hit_rate": 0.0,
                "place_roi": 0.0,
                "top3_in_top_picks": 0.0,
            },
            "cumulative": [],
            "rows": [],
        }

    def test_get_stats_with_data(self, client, db):
        """◎が1着のレースが1件 → 払戻と収支が返る"""
        race = make_race(db, "r_stats_001", name="答え合わせレース", grade="G2",
                         venue="中山")
        horse = make_horse(db, "h_stats_001", name="答え合わせ馬")
        make_entry(db, race.id, horse.id, horse_number=5, odds=4.2)
        make_result(db, race.id, horse.id, finish_position=1, horse_number=5)
        make_prediction(db, race.id, horse.id, rank=1,
                        created_at=datetime(2024, 4, 27, 12, 0))
        make_payout(db, race.id, bet_type="単勝", combination="5", amount=420)
        make_payout(db, race.id, bet_type="複勝", combination="5", amount=160)

        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()

        assert data["summary"]["races"] == 1
        assert data["summary"]["win_roi"] == 4.2
        assert data["cumulative"] == [{
            "date": "2024-04-28",
            "race_id": race.id,
            "balance_win": 320,
            "balance_place": 60,
        }]
        assert data["rows"] == [{
            "date": "2024-04-28",
            "race_id": race.id,
            "race_name": "答え合わせレース",
            "grade": "G2",
            "venue": "中山",
            "pick_horse_name": "答え合わせ馬",
            "pick_odds": 4.2,
            "finish_position": 1,
            "win_payout": 420,
            "place_payout": 160,
            "net": 380,
        }]
