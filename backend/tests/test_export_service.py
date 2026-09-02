"""静的JSON書き出し（export_service.export_static_json）のテスト。

フロントの静的モード（frontend/src/api/staticRoutes.ts）が読む
ファイル構成・キー・件数・エンコーディングを検証する。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from app.services.export_service import export_static_json
from app.services.verification_service import build_stats
from tests.factories import (
    make_entry,
    make_horse,
    make_jockey,
    make_payout,
    make_prediction,
    make_race,
    make_result,
)

RACE_ID_NEW = "202412280611"
RACE_ID_OLD = "202405021211"
RACE_ID_PAST = "202305021211"  # 予想・払戻なし（races.jsonに載らない）
RACE_ID_RESULT_ONLY = "202411020511"  # 予想なし・結果と払戻あり
HORSE_ID_A = "2021105165"
HORSE_ID_B = "2021104976"
HORSE_ID_C = "2021104111"
HORSE_ID_D = "2021104222"
JOCKEY_ID = "01167"

_RACE_KEYS = {
    "id",
    "name",
    "date",
    "venue",
    "grade",
    "course_type",
    "distance",
    "weather",
    "track_condition",
    "top_pick",
    "results",
    "payouts",
}
_PREDICTION_KEYS = {
    "rank",
    "horse_id",
    "horse_name",
    "total_score",
    "factor_scores",
}
_ENTRY_KEYS = {
    "horse_id",
    "horse_number",
    "post_position",
    "weight",
    "odds",
    "jockey_name",
    "sex",
    "age",
    "recent_finishes",
}
_HORSE_KEYS = {"id", "name", "sex", "birthday", "sire", "dam", "dam_sire"}
_RESULT_KEYS = {
    "date",
    "race_id",
    "race_name",
    "venue",
    "grade",
    "distance",
    "course_type",
    "track_condition",
    "finish_position",
    "time",
    "margin",
    "last_3f",
    "jockey_name",
}

_FACTOR_SCORES = {
    "recent_form": {"score": 82.0, "label": "近走成績", "weighted": 16.4}
}


_FINISHER_KEYS = {
    "horse_id",
    "horse_name",
    "horse_number",
    "finish_position",
    "jockey_name",
    "time",
    "margin",
    "last_3f",
}


def _finisher_identities(finishers: list[dict]) -> list[dict]:
    """結果行から馬の識別子と着順だけを取り出す（騎手・タイム等は別途検証）。"""
    assert all(set(finisher) == _FINISHER_KEYS for finisher in finishers)
    return [
        {
            key: finisher[key]
            for key in ("horse_id", "horse_name", "horse_number", "finish_position")
        }
        for finisher in finishers
    ]


def _build_dataset(db) -> None:
    """予想2レース＋過去成績1レースを持つDBを組む。"""
    make_race(
        db,
        race_id=RACE_ID_NEW,
        name="ホープフルステークス",
        race_date=date(2024, 12, 28),
        venue="中山",
        course_type="芝",
        distance=2000,
        grade="G1",
        track_condition="良",
        weather="晴",
    )
    make_race(
        db,
        race_id=RACE_ID_OLD,
        name="安田記念",
        race_date=date(2024, 6, 2),
        venue="東京",
        course_type="芝",
        distance=1600,
        grade="G1",
    )
    make_race(
        db,
        race_id=RACE_ID_PAST,
        name="ダービー卿チャレンジトロフィー",
        race_date=date(2023, 4, 1),
        venue="中山",
        course_type="芝",
        distance=1600,
        grade="G3",
        track_condition="稍重",
    )

    make_horse(
        db,
        HORSE_ID_A,
        name="テスト馬アルファ",
        sex="牡",
        birthday=date(2021, 3, 5),
        sire="ディープインパクト",
        dam="テスト母馬",
        dam_sire="Storm Cat",
    )
    make_horse(db, HORSE_ID_B, name="テスト馬ベータ", sex="牝")
    make_jockey(db, JOCKEY_ID, name="テスト騎手")

    # 出走馬（馬番の昇順に並ぶことを確認するため降順で登録する）
    make_entry(
        db,
        RACE_ID_NEW,
        HORSE_ID_A,
        jockey_id=JOCKEY_ID,
        post_position=2,
        horse_number=4,
        weight=57.0,
        odds=3.2,
    )
    make_entry(
        db,
        RACE_ID_NEW,
        HORSE_ID_B,
        post_position=1,
        horse_number=1,
        weight=55.0,
    )
    make_entry(
        db,
        RACE_ID_OLD,
        HORSE_ID_A,
        jockey_id=JOCKEY_ID,
        post_position=3,
        horse_number=5,
        odds=4.1,
    )

    # 古い予想バッチ（◎はベータ）と新しいバッチ（◎はアルファ）
    stale_batch_at = datetime(2024, 12, 20, 12, 0)
    latest_batch_at = datetime(2024, 12, 27, 12, 0)
    make_prediction(
        db, RACE_ID_NEW, HORSE_ID_B, rank=1, total_score=70.0,
        created_at=stale_batch_at,
    )
    make_prediction(
        db, RACE_ID_NEW, HORSE_ID_A, rank=2, total_score=65.0,
        created_at=stale_batch_at,
    )
    make_prediction(
        db, RACE_ID_NEW, HORSE_ID_A, rank=1, total_score=88.5,
        score_details=_FACTOR_SCORES, created_at=latest_batch_at,
    )
    make_prediction(
        db, RACE_ID_NEW, HORSE_ID_B, rank=2, total_score=71.2,
        created_at=latest_batch_at,
    )
    make_prediction(
        db, RACE_ID_OLD, HORSE_ID_A, rank=1, total_score=80.0,
        created_at=datetime(2024, 6, 1, 12, 0),
    )

    # 過去成績（安田記念=1着 / ダービー卿CT=3着）と払戻（stats.json用）
    make_result(
        db, RACE_ID_OLD, HORSE_ID_A, finish_position=1, time="1:31.2",
        margin="クビ", last_3f=33.4, jockey_name="テスト騎手", horse_number=5,
    )
    make_result(
        db, RACE_ID_PAST, HORSE_ID_A, finish_position=3, time="1:32.8",
        margin="1.1/2", last_3f=34.6, jockey_name="テスト騎手", horse_number=8,
    )
    make_payout(db, RACE_ID_OLD, bet_type="単勝", combination="5", amount=410)
    make_payout(db, RACE_ID_OLD, bet_type="複勝", combination="5", amount=150)


def _add_result_only_race(db) -> None:
    """予想なし・結果と払戻ありのレース（4着分）を足す。"""
    make_race(
        db,
        race_id=RACE_ID_RESULT_ONLY,
        name="アルゼンチン共和国杯",
        race_date=date(2024, 11, 2),
        venue="東京",
        grade="G2",
    )
    make_horse(db, HORSE_ID_C, name="テスト馬ガンマ")
    make_horse(db, HORSE_ID_D, name="テスト馬デルタ")
    # (horse_id, 着順, 馬番) — 着順昇順に並ぶことを確認するため降順で登録する
    finish_order = [
        (HORSE_ID_A, 1, 5),
        (HORSE_ID_B, 2, 3),
        (HORSE_ID_C, 3, 8),
        (HORSE_ID_D, 4, 1),
    ]
    for horse_id, finish_position, horse_number in reversed(finish_order):
        make_result(
            db,
            RACE_ID_RESULT_ONLY,
            horse_id,
            finish_position=finish_position,
            horse_number=horse_number,
        )
    make_payout(db, RACE_ID_RESULT_ONLY, bet_type="単勝", combination="5", amount=760)
    make_payout(db, RACE_ID_RESULT_ONLY, bet_type="複勝", combination="5", amount=210)
    make_payout(db, RACE_ID_RESULT_ONLY, bet_type="複勝", combination="3", amount=180)
    # 単勝・複勝以外の券種は payouts に含めない
    make_payout(
        db, RACE_ID_RESULT_ONLY, bet_type="馬連", combination="3-5", amount=1200
    )


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestExportStaticJson:
    def test_writes_all_contract_files(self, db, tmp_path):
        _build_dataset(db)

        counts = export_static_json(db, tmp_path)

        assert counts == {"races": 2, "horses": 2}
        assert sorted(child.name for child in tmp_path.iterdir()) == [
            "horses",
            "meta.json",
            "races",
            "races.json",
            "stats.json",
        ]
        assert sorted(p.name for p in (tmp_path / "races").iterdir()) == sorted(
            [f"{RACE_ID_NEW}.json", f"{RACE_ID_OLD}.json"]
        )
        assert sorted(p.name for p in (tmp_path / "horses").iterdir()) == sorted(
            [f"{HORSE_ID_A}.json", f"{HORSE_ID_B}.json"]
        )

    def test_meta_json(self, db, tmp_path):
        _build_dataset(db)

        export_static_json(db, tmp_path)
        meta = _read(tmp_path / "meta.json")

        assert set(meta) == {"generated_at", "race_count"}
        assert meta["race_count"] == len(_read(tmp_path / "races.json"))
        # JSTのISO8601（オフセット付き）
        assert meta["generated_at"].endswith("+09:00")
        generated_at = datetime.fromisoformat(meta["generated_at"])
        assert generated_at.utcoffset() == timedelta(hours=9)

    def test_races_json_is_date_desc_with_top_pick(self, db, tmp_path):
        _build_dataset(db)

        export_static_json(db, tmp_path)
        races = _read(tmp_path / "races.json")

        # 予想も払戻も持たない RACE_ID_PAST は載らない
        assert [race["id"] for race in races] == [RACE_ID_NEW, RACE_ID_OLD]
        assert set(races[0]) == _RACE_KEYS
        assert races[0]["name"] == "ホープフルステークス"
        assert races[0]["date"] == "2024-12-28"
        assert races[0]["venue"] == "中山"
        assert races[0]["grade"] == "G1"
        assert races[0]["course_type"] == "芝"
        assert races[0]["distance"] == 2000
        assert races[0]["weather"] == "晴"
        assert races[0]["track_condition"] == "良"
        # 最新バッチの rank=1（古いバッチの◎ベータではない）
        assert races[0]["top_pick"] == {
            "horse_id": HORSE_ID_A,
            "horse_name": "テスト馬アルファ",
            "total_score": 88.5,
            "finish_position": None,  # 結果未収集
        }
        assert races[0]["results"] == []
        assert races[0]["payouts"] is None
        # 結果収集済みのレースは◎の着順と払戻を持つ
        assert races[1]["top_pick"]["finish_position"] == 1
        assert races[1]["payouts"] == {"win": 410, "place": {"5": 150}}
        assert races[1]["weather"] is None
        assert races[1]["track_condition"] == "良"

    def test_race_detail_json(self, db, tmp_path):
        _build_dataset(db)

        export_static_json(db, tmp_path)
        payload = _read(tmp_path / "races" / f"{RACE_ID_NEW}.json")

        assert set(payload) == {"race", "predictions", "entries"}
        assert payload["race"] == _read(tmp_path / "races.json")[0]

        predictions = payload["predictions"]
        assert [p["rank"] for p in predictions] == [1, 2]
        assert [p["horse_id"] for p in predictions] == [HORSE_ID_A, HORSE_ID_B]
        assert set(predictions[0]) == _PREDICTION_KEYS
        assert predictions[0]["horse_name"] == "テスト馬アルファ"
        assert predictions[0]["total_score"] == 88.5
        assert predictions[0]["factor_scores"] == _FACTOR_SCORES
        assert predictions[1]["factor_scores"] == {}

    def test_entries_are_sorted_with_jockey_sex_and_age(self, db, tmp_path):
        _build_dataset(db)

        export_static_json(db, tmp_path)
        entries = _read(tmp_path / "races" / f"{RACE_ID_NEW}.json")["entries"]

        assert [entry["horse_number"] for entry in entries] == [1, 4]
        assert set(entries[0]) == _ENTRY_KEYS

        beta, alpha = entries
        assert alpha["horse_id"] == HORSE_ID_A
        assert alpha["post_position"] == 2
        assert alpha["weight"] == 57.0
        assert alpha["odds"] == 3.2
        assert alpha["jockey_name"] == "テスト騎手"
        assert alpha["sex"] == "牡"
        assert alpha["age"] == 3  # 2024年 − 2021年生まれ
        # 騎手・生年月日が未取得なら null
        assert beta["jockey_name"] is None
        assert beta["odds"] is None
        assert beta["age"] is None
        assert beta["sex"] == "牝"

    def test_horse_json_with_results_desc(self, db, tmp_path):
        _build_dataset(db)

        export_static_json(db, tmp_path)
        payload = _read(tmp_path / "horses" / f"{HORSE_ID_A}.json")

        assert set(payload) == {"horse", "results"}
        assert set(payload["horse"]) == _HORSE_KEYS
        assert payload["horse"] == {
            "id": HORSE_ID_A,
            "name": "テスト馬アルファ",
            "sex": "牡",
            "birthday": "2021-03-05",
            "sire": "ディープインパクト",
            "dam": "テスト母馬",
            "dam_sire": "Storm Cat",
        }

        results = payload["results"]
        assert [result["date"] for result in results] == ["2024-06-02", "2023-04-01"]
        assert set(results[0]) == _RESULT_KEYS
        assert results[0] == {
            "date": "2024-06-02",
            "race_id": RACE_ID_OLD,
            "race_name": "安田記念",
            "venue": "東京",
            "grade": "G1",
            "distance": 1600,
            "course_type": "芝",
            "track_condition": "良",
            "finish_position": 1,
            "time": "1:31.2",
            "margin": "クビ",
            "last_3f": 33.4,
            "jockey_name": "テスト騎手",
        }

    def test_horse_without_results_gets_empty_list(self, db, tmp_path):
        _build_dataset(db)

        export_static_json(db, tmp_path)
        payload = _read(tmp_path / "horses" / f"{HORSE_ID_B}.json")

        assert payload["results"] == []
        assert payload["horse"]["birthday"] is None

    def test_result_only_race_is_exported(self, db, tmp_path):
        """予想がなくても払戻があれば紙面に載る（過去の重賞結果）"""
        _build_dataset(db)
        _add_result_only_race(db)

        export_static_json(db, tmp_path)
        races = _read(tmp_path / "races.json")

        assert [race["id"] for race in races] == [
            RACE_ID_NEW,
            RACE_ID_RESULT_ONLY,
            RACE_ID_OLD,
        ]
        listed = races[1]
        assert listed["top_pick"] is None
        # 一覧は上位3頭のみ
        assert _finisher_identities(listed["results"]) == [
            {
                "horse_id": HORSE_ID_A,
                "horse_name": "テスト馬アルファ",
                "horse_number": 5,
                "finish_position": 1,
            },
            {
                "horse_id": HORSE_ID_B,
                "horse_name": "テスト馬ベータ",
                "horse_number": 3,
                "finish_position": 2,
            },
            {
                "horse_id": HORSE_ID_C,
                "horse_name": "テスト馬ガンマ",
                "horse_number": 8,
                "finish_position": 3,
            },
        ]
        assert listed["payouts"] == {"win": 760, "place": {"5": 210, "3": 180}}

        # 詳細JSONは全着順を持つ
        detail = _read(tmp_path / "races" / f"{RACE_ID_RESULT_ONLY}.json")["race"]
        assert [result["finish_position"] for result in detail["results"]] == [
            1,
            2,
            3,
            4,
        ]
        # 結果表からリンクするため、結果に出る馬の詳細JSONも書き出す
        assert (tmp_path / "horses" / f"{HORSE_ID_C}.json").exists()
        assert (tmp_path / "horses" / f"{HORSE_ID_D}.json").exists()

    def test_result_without_payout_is_not_exported(self, db, tmp_path):
        """払戻のないスタブレース（fetchが外部キー用に作る）は載らない"""
        _build_dataset(db)

        export_static_json(db, tmp_path)

        race_ids = {race["id"] for race in _read(tmp_path / "races.json")}
        assert RACE_ID_PAST not in race_ids
        assert not (tmp_path / "races" / f"{RACE_ID_PAST}.json").exists()

    def test_entry_recent_finishes(self, db, tmp_path):
        """recent_finishes は対象レースより前の着順を新しい順に最大5件持つ"""
        _build_dataset(db)
        # アルファの過去成績を増やす（対象レースより前が6件になる）
        for race_date, finish_position in [
            (date(2024, 5, 1), 4),
            (date(2024, 4, 1), 5),
            (date(2024, 3, 1), 6),
            (date(2024, 2, 1), 7),
        ]:
            past_race_id = f"{race_date.strftime('%Y%m%d')}0511"
            make_race(db, race_id=past_race_id, name="過去戦", race_date=race_date)
            make_result(
                db, past_race_id, HORSE_ID_A, finish_position=finish_position
            )

        export_static_json(db, tmp_path)

        new_entries = _read(tmp_path / "races" / f"{RACE_ID_NEW}.json")["entries"]
        alpha = next(e for e in new_entries if e["horse_id"] == HORSE_ID_A)
        beta = next(e for e in new_entries if e["horse_id"] == HORSE_ID_B)
        # 2023-04-01(3着) は6件目なので落ちる
        assert alpha["recent_finishes"] == [1, 4, 5, 6, 7]
        assert beta["recent_finishes"] == []

        # 対象レース当日以降の成績（安田記念の1着）は含めない
        old_entries = _read(tmp_path / "races" / f"{RACE_ID_OLD}.json")["entries"]
        alpha_old = next(e for e in old_entries if e["horse_id"] == HORSE_ID_A)
        assert alpha_old["recent_finishes"] == [4, 5, 6, 7, 3]

    def test_stats_json_matches_build_stats(self, db, tmp_path):
        _build_dataset(db)

        export_static_json(db, tmp_path)

        assert _read(tmp_path / "stats.json") == build_stats(db)

    def test_japanese_is_not_escaped(self, db, tmp_path):
        _build_dataset(db)

        export_static_json(db, tmp_path)
        raw = (tmp_path / "races.json").read_text(encoding="utf-8")

        assert "ホープフルステークス" in raw
        assert "\\u" not in raw

    def test_output_dir_is_emptied_first(self, db, tmp_path):
        _build_dataset(db)
        (tmp_path / "stale.json").write_text("{}", encoding="utf-8")
        (tmp_path / "races").mkdir()
        (tmp_path / "races" / "stale_race.json").write_text("{}", encoding="utf-8")

        export_static_json(db, tmp_path)

        assert not (tmp_path / "stale.json").exists()
        assert not (tmp_path / "races" / "stale_race.json").exists()

    def test_creates_missing_output_dir(self, db, tmp_path):
        _build_dataset(db)
        out_dir = tmp_path / "nested" / "data"

        export_static_json(db, out_dir)

        assert (out_dir / "races.json").exists()

    def test_refuses_repository_root(self, db, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "keep.txt").write_text("消してはいけない", encoding="utf-8")

        try:
            export_static_json(db, tmp_path)
        except ValueError as e:
            assert "リポジトリルート" in str(e)
        else:
            raise AssertionError("リポジトリルートへの出力が拒否されなかった")

        assert (tmp_path / "keep.txt").exists()

    def test_empty_db_writes_empty_contract(self, db, tmp_path):
        counts = export_static_json(db, tmp_path)

        assert counts == {"races": 0, "horses": 0}
        assert _read(tmp_path / "races.json") == []
        assert _read(tmp_path / "meta.json")["race_count"] == 0
        assert _read(tmp_path / "stats.json")["summary"]["races"] == 0
        assert list((tmp_path / "races").iterdir()) == []
        assert list((tmp_path / "horses").iterdir()) == []
