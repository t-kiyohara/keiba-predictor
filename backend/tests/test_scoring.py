"""スコアリングエンジンのテスト"""

from __future__ import annotations

from datetime import date

import pytest

from app.models import Horse, Prediction, Race, Result
from app.scoring import factors
from app.scoring.engine import ScoringEngine
from app.scoring.factors import _position_score
from app.scoring.weights import FACTOR_WEIGHTS
from tests.factories import (
    make_entry as _make_entry,
)
from tests.factories import (
    make_horse as _make_horse,
)
from tests.factories import (
    make_jockey as _make_jockey,
)
from tests.factories import (
    make_race as _make_race,
)
from tests.factories import (
    make_result as _make_result,
)
from tests.factories import (
    make_trainer as _make_trainer,
)

# ---------------------------------------------------------------------------
# インメモリ用ヘルパー（ファクター純粋ユニットテストで使用）
# ---------------------------------------------------------------------------

def _race(race_id="r1", name="テスト", venue="東京", distance=2000,
          course_type="芝", grade="G1", track_condition="良",
          race_date=None) -> Race:
    """DBなしで Race オブジェクトを生成する"""
    return Race(
        id=race_id, name=name, date=race_date or date(2024, 4, 28),
        venue=venue, course_type=course_type, distance=distance,
        track_condition=track_condition, grade=grade,
    )


def _result(race_id="r1", horse_id="h1", finish_position=1,
            last_3f=None) -> Result:
    """DBなしで Result オブジェクトを生成する"""
    return Result(
        race_id=race_id, horse_id=horse_id,
        finish_position=finish_position, last_3f=last_3f,
    )


# ---------------------------------------------------------------------------
# ファクターテスト: score_recent_form
# ---------------------------------------------------------------------------

class TestScoreRecentForm:
    def test_score_recent_form_no_data(self):
        """結果データなしの場合は中立スコア50.0を返す"""
        score = factors.score_recent_form([], {})
        assert score == 50.0

    def test_score_recent_form_with_results(self):
        """1着・2着の結果とlast_3f最速でスコアを計算"""
        race1 = _race("r_rf_001", race_date=date(2024, 3, 1))
        race2 = _race("r_rf_002", race_date=date(2024, 5, 1))
        result1 = _result("r_rf_001", finish_position=1, last_3f=34.0)
        result2 = _result("r_rf_002", finish_position=2, last_3f=33.5)

        # horse_results は date 降順でソート済み（race2が新しい）
        horse_results = [(result2, race2), (result1, race1)]
        race_last3f = {"r_rf_001": [34.0], "r_rf_002": [33.5]}

        score = factors.score_recent_form(horse_results, race_last3f, limit=5)
        # 1着=100, 2着=85 → 平均92.5
        # 両レースで最速(唯一) +10 → ボーナス平均10
        # 期待: 92.5 + 10 = 102.5 → clampで100.0
        assert score == 100.0

    def test_score_recent_form_lower_positions(self):
        """下位着順の計算を検証"""
        race = _race("r_rf_003", race_date=date(2024, 10, 1))
        result = _result("r_rf_003", finish_position=6)

        score = factors.score_recent_form([(result, race)], {}, limit=5)
        # 6着: max(0, 40 - 5*(6-5)) = 35.0、ボーナスなし
        assert score == pytest.approx(35.0)


# ---------------------------------------------------------------------------
# ファクターテスト: score_same_race
# ---------------------------------------------------------------------------

class TestScoreSameRace:
    def test_score_same_race_no_history(self):
        """同レース出走歴なしの場合は50.0"""
        score = factors.score_same_race([], "天皇賞")
        assert score == 50.0

    def test_score_same_race_with_win(self):
        """1着経験ありの場合は90以上"""
        race = _race("r_sr_001", name="天皇賞（春）")
        result = _result("r_sr_001", finish_position=1)

        score = factors.score_same_race([(result, race)], "天皇賞")
        assert score >= 90.0

    def test_score_same_race_with_second(self):
        """2着経験ありの場合は75以上"""
        race = _race("r_sr_002", name="天皇賞（秋）")
        result = _result("r_sr_002", finish_position=2)

        score = factors.score_same_race([(result, race)], "天皇賞")
        assert score >= 75.0


# ---------------------------------------------------------------------------
# ファクターテスト: score_course_aptitude
# ---------------------------------------------------------------------------

class TestScoreCourseAptitude:
    def test_score_course_aptitude_no_data(self):
        """データなしの場合は50.0"""
        score = factors.score_course_aptitude([], "東京", 2000)
        assert score == 50.0

    def test_score_course_aptitude_with_wins(self):
        """同コース全勝の場合は高スコア"""
        race = _race("r_ca_001", venue="東京", distance=2000)
        result = _result("r_ca_001", finish_position=1)

        score = factors.score_course_aptitude([(result, race)], "東京", 2000)
        # 勝率1.0 * 60 + 連対率1.0 * 30 + 複勝率1.0 * 10 = 100
        assert score == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# ファクターテスト: score_track_condition
# ---------------------------------------------------------------------------

class TestScoreTrackCondition:
    def test_score_track_condition_no_data(self):
        """データなしの場合は50.0"""
        score = factors.score_track_condition([], "良")
        assert score == 50.0

    def test_score_track_condition_with_results(self):
        """同馬場状態で全勝の場合は高スコア"""
        race = _race("r_tc_001", track_condition="良")
        result = _result("r_tc_001", finish_position=1)

        score = factors.score_track_condition([(result, race)], "良")
        # 勝率1.0*60 + 連対率1.0*30 + 複勝率1.0*10 = 100
        assert score == pytest.approx(100.0)

    def test_score_track_condition_wrong_condition(self):
        """異なる馬場状態でデータなし → 50.0"""
        race = _race("r_tc_002", track_condition="良")
        result = _result("r_tc_002", finish_position=1)

        # 重馬場での成績は未登録
        score = factors.score_track_condition([(result, race)], "重")
        assert score == 50.0


# ---------------------------------------------------------------------------
# 重みの合計テスト
# ---------------------------------------------------------------------------

class TestFactorWeights:
    def test_factor_weights_sum_to_one(self):
        """FACTOR_WEIGHTS の合計が1.0であることを検証"""
        total = sum(FACTOR_WEIGHTS.values())
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_factor_weights_all_positive(self):
        """全ての重みが正の値であること"""
        for key, weight in FACTOR_WEIGHTS.items():
            assert weight > 0, f"{key} の重みが0以下"

    def test_factor_weights_has_all_factors(self):
        """8つのファクターが存在すること"""
        expected_factors = {
            "recent_form", "same_race", "course_aptitude", "bloodline",
            "track_condition", "jockey", "trainer", "overall"
        }
        assert set(FACTOR_WEIGHTS.keys()) == expected_factors


# ---------------------------------------------------------------------------
# ScoringEngine テスト
# ---------------------------------------------------------------------------

class TestScoringEngine:
    def _setup_race_and_entries(self, db):
        """テスト用の最小データセットを構築"""
        jockey = _make_jockey(db, "j_eng_001")
        trainer = _make_trainer(db, "tr_eng_001")
        race = _make_race(db, "r_eng_001", name="エンジンテストレース",
                          venue="東京", distance=2000, course_type="芝",
                          grade="G1", track_condition="良")
        horse1 = _make_horse(
            db, "h_eng_001", name="テスト馬A", sire="ディープインパクト",
        )
        horse2 = _make_horse(db, "h_eng_002", name="テスト馬B")
        horse3 = _make_horse(db, "h_eng_003", name="テスト馬C")

        entry1 = _make_entry(db, race.id, horse1.id, jockey_id=jockey.id,
                             trainer_id=trainer.id, post_position=1, horse_number=1)
        entry2 = _make_entry(db, race.id, horse2.id, jockey_id=jockey.id,
                             trainer_id=trainer.id, post_position=2, horse_number=2)
        entry3 = _make_entry(db, race.id, horse3.id, post_position=3, horse_number=3)

        return race, [horse1, horse2, horse3], [entry1, entry2, entry3]

    def test_scoring_engine_calculate(self, db):
        """Engine.calculate_horse_score が dict を返し、全8ファクターを含むこと"""
        race, horses, entries = self._setup_race_and_entries(db)
        engine = ScoringEngine(db)

        result = engine.calculate_horse_score(horses[0].id, race, entries[0])

        # 返値の型確認
        assert isinstance(result, dict)
        assert "total_score" in result
        assert "factor_scores" in result

        # 全8ファクターが含まれること
        expected_factors = {
            "recent_form", "same_race", "course_aptitude", "bloodline",
            "track_condition", "jockey", "trainer", "overall"
        }
        assert set(result["factor_scores"].keys()) == expected_factors

        # 各ファクターのキー構造
        for factor_name, detail in result["factor_scores"].items():
            assert "score" in detail, f"{factor_name}: 'score' キーなし"
            assert "label" in detail, f"{factor_name}: 'label' キーなし"
            assert "weighted" in detail, f"{factor_name}: 'weighted' キーなし"
            assert 0.0 <= detail["score"] <= 100.0, (
                f"{factor_name}: スコアが0〜100範囲外"
            )

        # total_score は非負
        assert result["total_score"] >= 0.0

    def test_scoring_engine_predict_race(self, db):
        """Engine.predict_race がランキングを返し、Prediction に保存されること"""
        race, horses, entries = self._setup_race_and_entries(db)

        # 一部の馬に成績を入れてスコア差を出す
        past_race = _make_race(db, "r_eng_past_001", name="過去レース",
                               race_date=date(2024, 1, 1))
        _make_result(db, past_race.id, horses[0].id, finish_position=1)
        _make_result(db, past_race.id, horses[1].id, finish_position=3)

        engine = ScoringEngine(db)
        ranking = engine.predict_race(race.id)

        # 戻り値がリストであること
        assert isinstance(ranking, list)
        assert len(ranking) == 3  # 3頭分

        # ランキングが1から始まること
        ranks = [item["rank"] for item in ranking]
        assert sorted(ranks) == [1, 2, 3]

        # total_score 降順であること
        scores = [item["total_score"] for item in ranking]
        assert scores == sorted(scores, reverse=True)

        # 必要なキーが存在すること
        for item in ranking:
            assert "rank" in item
            assert "horse_id" in item
            assert "horse_name" in item
            assert "total_score" in item
            assert "factor_scores" in item

        # Prediction テーブルに保存されていること
        predictions = db.query(Prediction).filter(Prediction.race_id == race.id).all()
        assert len(predictions) == 3

        # ランク1の馬が正しく保存されていること
        rank1_pred = db.query(Prediction).filter(
            Prediction.race_id == race.id,
            Prediction.rank == 1
        ).first()
        assert rank1_pred is not None
        assert rank1_pred.total_score == ranking[0]["total_score"]

    def test_scoring_engine_predict_race_not_found(self, db):
        """存在しないレースIDでは ValueError が発生すること"""
        engine = ScoringEngine(db)
        with pytest.raises(ValueError, match="Race not found"):
            engine.predict_race("nonexistent_race_id")

    def test_scoring_engine_predict_race_replaces_existing(self, db):
        """predict_race を2回呼ぶと Prediction が上書きされること"""
        race, horses, entries = self._setup_race_and_entries(db)
        engine = ScoringEngine(db)

        # 1回目
        engine.predict_race(race.id)
        count_after_first = (
            db.query(Prediction).filter(Prediction.race_id == race.id).count()
        )

        # 2回目
        engine.predict_race(race.id)
        count_after_second = (
            db.query(Prediction).filter(Prediction.race_id == race.id).count()
        )

        # 重複なく同じ件数
        assert count_after_first == count_after_second == 3


class TestEngineJockeyTrainerLoad:
    """_load_jockey_results / _load_trainer_results が Result.jockey_name /
    trainer_name 経由で成績を取得することのテスト。

    過去成績（fetch_horse_results 由来の Result）は Entry を作らないため、
    Entry⋈Result JOIN では常に0件になる構造的な問題があった。
    """

    def test_load_jockey_results_matches_by_name(self, db):
        """Entryを作らずに Result.jockey_name のみで騎手成績が取得できること"""
        jockey = _make_jockey(db, "j_load_001", "ロード騎手")
        race = _make_race(db, "r_load_001", name="ロードテストレース")
        horse = _make_horse(db, "h_load_001", name="ロード馬")
        # Entryは作らない（過去成績はEntryを作らない構造を再現）
        _make_result(
            db, race.id, horse.id, finish_position=1, jockey_name="ロード騎手"
        )

        engine = ScoringEngine(db)
        results_map = engine._load_jockey_results([jockey.id])

        assert jockey.id in results_map
        assert len(results_map[jockey.id]) == 1
        result_row, matched_race = results_map[jockey.id][0]
        assert matched_race.id == race.id
        assert result_row.jockey_name == "ロード騎手"

    def test_load_jockey_results_no_match_returns_empty(self, db):
        """該当する名前のResultがない場合は空リストを返す"""
        jockey = _make_jockey(db, "j_load_002", "無成績騎手")

        engine = ScoringEngine(db)
        results_map = engine._load_jockey_results([jockey.id])

        assert results_map == {}

    def test_load_trainer_results_matches_by_name(self, db):
        """Entryを作らずに Result.trainer_name のみで調教師成績が取得できること"""
        trainer = _make_trainer(db, "tr_load_001", "ロード調教師")
        race = _make_race(db, "r_load_002", name="ロードテストレース2")
        horse = _make_horse(db, "h_load_002", name="ロード馬2")
        _make_result(
            db, race.id, horse.id, finish_position=2, trainer_name="ロード調教師"
        )

        engine = ScoringEngine(db)
        results_map = engine._load_trainer_results([trainer.id])

        assert trainer.id in results_map
        assert len(results_map[trainer.id]) == 1
        result_row, matched_race = results_map[trainer.id][0]
        assert matched_race.id == race.id
        assert result_row.trainer_name == "ロード調教師"


# ---------------------------------------------------------------------------
# ファクターテスト: score_jockey（データなし）
# ---------------------------------------------------------------------------

class TestScoreJockeyNoData:
    def test_score_jockey_no_data(self):
        """騎手の成績データなし（空リスト）→ 50.0 を返す"""
        score = factors.score_jockey([], "東京", "G1")
        assert score == 50.0

    def test_score_jockey_no_venue_match(self):
        """同競馬場・同グレードのデータなし → 50.0 を返す"""
        race = _race("r_jk_001", venue="阪神", grade="G3")
        result = _result("r_jk_001", finish_position=1)
        # 「東京G1」を問い合わせるが、データは「阪神G3」のみ
        score = factors.score_jockey([(result, race)], "東京", "G1")
        assert score == 50.0

    def test_score_jockey_with_results(self):
        """同競馬場のデータあり → 50.0 より高いスコア"""
        race = _race("r_jk_002", venue="東京", grade="G1")
        result = _result("r_jk_002", finish_position=1)
        score = factors.score_jockey([(result, race)], "東京", "G1")
        assert score > 50.0


# ---------------------------------------------------------------------------
# ファクターテスト: score_trainer（データなし）
# ---------------------------------------------------------------------------

class TestScoreTrainerNoData:
    def test_score_trainer_no_data(self):
        """調教師の成績データなし（空リスト）→ 50.0 を返す"""
        score = factors.score_trainer([], "阪神", "G2")
        assert score == 50.0

    def test_score_trainer_no_venue_match(self):
        """同競馬場・同グレードのデータなし → 50.0 を返す"""
        race = _race("r_tr_001", venue="東京", grade="G1")
        result = _result("r_tr_001", finish_position=2)
        score = factors.score_trainer([(result, race)], "阪神", "G2")
        assert score == 50.0

    def test_score_trainer_with_results(self):
        """同グレードのデータあり → NEUTRAL_SCORE から外れる"""
        race = _race("r_tr_002", venue="阪神", grade="G2")
        result = _result("r_tr_002", finish_position=1)
        score = factors.score_trainer([(result, race)], "阪神", "G2")
        assert score > 50.0


# ---------------------------------------------------------------------------
# ファクターテスト: score_bloodline（データなし）
# ---------------------------------------------------------------------------

class TestScoreBloodlineNoData:
    def test_score_bloodline_no_data(self):
        """血統データなし（父なし馬）→ 50.0 を返す"""
        horse = Horse(id="h_bl_nodata", name="無血統馬", sire=None, dam_sire=None)
        score = factors.score_bloodline(horse, [], [], "東京", 2000, "芝")
        assert score == 50.0

    def test_score_bloodline_no_siblings(self):
        """同じ父を持つ兄弟馬の成績なし → 50.0 を返す"""
        horse = Horse(
            id="h_bl_alone", name="孤独馬", sire="ユニーク種牡馬XYZ", dam_sire=None,
        )
        score = factors.score_bloodline(horse, [], [], "東京", 2000, "芝")
        assert score == 50.0

    def test_score_bloodline_horse_none(self):
        """horse が None → 50.0 を返す"""
        score = factors.score_bloodline(None, [], [], "東京", 2000, "芝")
        assert score == 50.0


# ---------------------------------------------------------------------------
# ファクターテスト: score_overall（データなし）
# ---------------------------------------------------------------------------

class TestScoreOverallNoData:
    def test_score_overall_no_data(self):
        """全結果なし → 50.0 を返す"""
        score = factors.score_overall([])
        assert score == 50.0

    def test_score_overall_with_wins(self):
        """勝利実績あり → 50.0 より高いスコアを返す"""
        race = _race("r_ov_001", grade="G1")
        result = _result("r_ov_001", finish_position=1)
        score = factors.score_overall([(result, race)])
        assert score > 50.0

    def test_score_overall_range(self):
        """score_overall は 0〜100 の範囲内であること"""
        race = _race("r_ov_range", grade="G2")
        result = _result("r_ov_range", finish_position=5)
        score = factors.score_overall([(result, race)])
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# 全ファクターの範囲テスト
# ---------------------------------------------------------------------------

class TestScoreAllFactorsRange:
    """全ファクターの結果が 0〜100 の範囲内であることを検証"""

    def _setup(self, db):
        """テスト用の最小限のデータを構築"""
        jockey = _make_jockey(db, "j_range_001", "範囲テスト騎手")
        trainer = _make_trainer(db, "tr_range_001", "範囲テスト調教師")
        race = _make_race(db, "r_range_001", name="天皇賞（春）",
                          venue="京都", distance=3200, course_type="芝",
                          grade="G1", track_condition="良")
        horse = _make_horse(db, "h_range_001", name="範囲テスト馬",
                            sire="ディープインパクト", dam_sire="Storm Cat")
        entry = _make_entry(db, race.id, horse.id, jockey_id=jockey.id,
                            trainer_id=trainer.id)
        # 過去成績
        past_race = _make_race(db, "r_range_past", name="天皇賞（春）",
                               venue="京都", distance=3200, course_type="芝",
                               grade="G1", track_condition="良",
                               race_date=date(2023, 4, 30))
        _make_result(db, past_race.id, horse.id, finish_position=2, last_3f=33.5)
        return race, horse, jockey, trainer, entry

    def test_score_all_factors_range(self, db):
        """全8ファクターが 0〜100 の範囲内（エンジン経由）"""
        race, horse, jockey, trainer, entry = self._setup(db)
        engine = ScoringEngine(db)
        result = engine.calculate_horse_score(horse.id, race, entry)

        for factor_name, detail in result["factor_scores"].items():
            assert 0.0 <= detail["score"] <= 100.0, (
                f"{factor_name} のスコアが 0〜100 の範囲外: {detail['score']}"
            )

    def test_score_recent_form_range(self):
        """score_recent_form は 0〜100 の範囲内"""
        race = _race("r_rf_range", grade="G1")
        result = _result("r_rf_range", finish_position=10, last_3f=36.0)
        score = factors.score_recent_form([(result, race)], {"r_rf_range": [36.0]})
        assert 0.0 <= score <= 100.0

    def test_score_same_race_range(self):
        """score_same_race は 0〜100 の範囲内"""
        race = _race("r_sr_range", name="菊花賞", grade="G1")
        result = _result("r_sr_range", finish_position=8)
        score = factors.score_same_race([(result, race)], "菊花賞")
        assert 0.0 <= score <= 100.0

    def test_score_course_aptitude_range(self):
        """score_course_aptitude は 0〜100 の範囲内"""
        race = _race("r_ca_range", venue="新潟", distance=1800, grade="G3")
        result = _result("r_ca_range", finish_position=1)
        score = factors.score_course_aptitude([(result, race)], "新潟", 1800)
        assert 0.0 <= score <= 100.0

    def test_score_track_condition_range(self):
        """score_track_condition は 0〜100 の範囲内"""
        race = _race("r_tc_range", track_condition="重", grade="G2")
        result = _result("r_tc_range", finish_position=1)
        score = factors.score_track_condition([(result, race)], "重")
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# _position_score エッジケーステスト
# ---------------------------------------------------------------------------

class TestPositionScore:
    def test_position_score_first(self):
        """1着 = 100.0"""
        assert _position_score(1) == 100.0

    def test_position_score_second(self):
        """2着 = 85.0"""
        assert _position_score(2) == 85.0

    def test_position_score_third(self):
        """3着 = 70.0"""
        assert _position_score(3) == 70.0

    def test_position_score_fourth(self):
        """4着 = 55.0"""
        assert _position_score(4) == 55.0

    def test_position_score_fifth(self):
        """5着 = 40.0"""
        assert _position_score(5) == 40.0

    def test_position_score_sixth(self):
        """6着 = max(0, 40-5*(6-5)) = 35.0"""
        assert _position_score(6) == pytest.approx(35.0)

    def test_position_score_thirteen(self):
        """13着 = max(0, 40-5*(13-5)) = max(0, 0) = 0.0"""
        assert _position_score(13) == pytest.approx(0.0)

    def test_position_score_eighteen(self):
        """18着 = max(0, 40-5*(18-5)) = max(0, -25) = 0.0（下限クランプ）"""
        assert _position_score(18) == pytest.approx(0.0)

    def test_position_score_zero(self):
        """0着（無効値）= else 分岐: max(0, 40-5*(0-5)) = 65.0（ドキュメント動作）"""
        # pos=0 は通常存在しない無効値だが、現在の実装では else 分岐に落ちて
        # 65.0 を返す。将来的にバリデーションを追加する場合は本テストを更新すること。
        assert _position_score(0) == pytest.approx(65.0)


# ---------------------------------------------------------------------------
# ファクターテスト: score_jockey（データあり）
# ---------------------------------------------------------------------------

class TestScoreJockeyWithData:
    def test_score_jockey_venue_match(self):
        """同競馬場の1着データ → NEUTRAL_SCORE より高スコア"""
        race = _race("r_jk_v_001", venue="東京", grade="G2")
        result = _result("r_jk_v_001", finish_position=1)
        score = factors.score_jockey([(result, race)], "東京", "G1")
        # venue スコアは計算されるが grade スコアは未一致→ venue スコアのみ
        assert score > 50.0

    def test_score_jockey_grade_match(self):
        """同グレードの1着データ → NEUTRAL_SCORE より高スコア"""
        race = _race("r_jk_g_001", venue="阪神", grade="G1")
        result = _result("r_jk_g_001", finish_position=1)
        score = factors.score_jockey([(result, race)], "東京", "G1")
        # grade スコアは計算されるが venue スコアは未一致
        assert score > 50.0

    def test_score_jockey_both_match(self):
        """同競馬場・同グレードの1着データ → 両方加算でさらに高スコア"""
        race_v = _race("r_jk_bv_001", venue="東京", grade="G1")
        result_v = _result("r_jk_bv_001", finish_position=1)
        # 片方しか一致しない場合のスコア
        score_partial = factors.score_jockey([(result_v, race_v)], "東京", "G2")

        # 両方一致する場合のスコア
        score_both = factors.score_jockey([(result_v, race_v)], "東京", "G1")
        assert score_both >= score_partial

    def test_score_jockey_low_position(self):
        """下位着順データのみ → NEUTRAL_SCORE より低い可能性があること"""
        race = _race("r_jk_low_001", venue="東京", grade="G1")
        result = _result("r_jk_low_001", finish_position=10)
        score = factors.score_jockey([(result, race)], "東京", "G1")
        # 勝率0・連対率0・複勝率0 → スコアは低い（0に近い）
        assert score < 50.0


# ---------------------------------------------------------------------------
# ファクターテスト: score_trainer（データあり）
# ---------------------------------------------------------------------------

class TestScoreTrainerWithData:
    def test_score_trainer_venue_match(self):
        """同競馬場の1着データ → NEUTRAL_SCORE より高スコア"""
        race = _race("r_tr_v_001", venue="京都", grade="G3")
        result = _result("r_tr_v_001", finish_position=1)
        score = factors.score_trainer([(result, race)], "京都", "G1")
        assert score > 50.0

    def test_score_trainer_grade_match(self):
        """同グレードの1着データ → NEUTRAL_SCORE より高スコア"""
        race = _race("r_tr_g_001", venue="中山", grade="G2")
        result = _result("r_tr_g_001", finish_position=1)
        score = factors.score_trainer([(result, race)], "阪神", "G2")
        assert score > 50.0

    def test_score_trainer_multiple_results(self):
        """複数成績データ → スコアが 0〜100 の範囲内であること"""
        race1 = _race("r_tr_m_001", venue="東京", grade="G1")
        race2 = _race("r_tr_m_002", venue="東京", grade="G1")
        result1 = _result("r_tr_m_001", finish_position=1)
        result2 = _result("r_tr_m_002", finish_position=5)
        score = factors.score_trainer(
            [(result1, race1), (result2, race2)], "東京", "G1"
        )
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# ファクターテスト: score_bloodline（兄弟馬データあり）
# ---------------------------------------------------------------------------

class TestScoreBloodlineWithData:
    def test_score_bloodline_sire_match(self):
        """同父を持つ兄弟馬が同コースで好走 → NEUTRAL_SCORE より高スコア"""
        horse = Horse(
            id="h_bl_sire", name="テスト馬", sire="ディープインパクト", dam_sire=None,
        )
        # 兄弟馬の成績（同コース・同距離・芝）
        sire_race = _race("r_bl_s_001", venue="東京", distance=2000, course_type="芝")
        sire_result = _result("r_bl_s_001", horse_id="h_sibling_001", finish_position=1)
        score = factors.score_bloodline(
            horse, [(sire_result, sire_race)], [], "東京", 2000, "芝"
        )
        assert score > 50.0

    def test_score_bloodline_dam_sire_match(self):
        """同母父を持つ馬が同コースで好走 → NEUTRAL_SCORE より高スコア"""
        horse = Horse(id="h_bl_ds", name="テスト馬", sire=None, dam_sire="Storm Cat")
        dam_race = _race("r_bl_ds_001", venue="阪神", distance=1600, course_type="芝")
        dam_result = _result("r_bl_ds_001", horse_id="h_ds_sibling", finish_position=1)
        score = factors.score_bloodline(
            horse, [], [(dam_result, dam_race)], "阪神", 1600, "芝"
        )
        assert score > 50.0

    def test_score_bloodline_wrong_venue(self):
        """兄弟馬の成績が別コース → フィルタされて NEUTRAL_SCORE"""
        horse = Horse(
            id="h_bl_venue", name="テスト馬", sire="キングカメハメハ", dam_sire=None,
        )
        sire_race = _race("r_bl_v_001", venue="阪神", distance=2000, course_type="芝")
        sire_result = _result("r_bl_v_001", horse_id="h_sib_venue", finish_position=1)
        # 東京2000を問い合わせるが兄弟馬データは阪神2000
        score = factors.score_bloodline(
            horse, [(sire_result, sire_race)], [], "東京", 2000, "芝"
        )
        assert score == 50.0

    def test_score_bloodline_sire_and_dam_sire_combined(self):
        """父・母父の両方にデータ → 0.6:0.4 合成スコア"""
        horse = Horse(id="h_bl_both", name="テスト馬",
                      sire="ディープインパクト", dam_sire="Storm Cat")
        race = _race("r_bl_both_001", venue="東京", distance=2400, course_type="芝")
        sire_result = _result("r_bl_both_001", horse_id="h_sib_s", finish_position=1)
        ds_result = _result("r_bl_both_001", horse_id="h_sib_ds", finish_position=1)

        score_sire_only = factors.score_bloodline(
            horse, [(sire_result, race)], [], "東京", 2400, "芝"
        )
        score_both = factors.score_bloodline(
            horse, [(sire_result, race)], [(ds_result, race)], "東京", 2400, "芝"
        )
        # 両方合成でも範囲内
        assert 0.0 <= score_both <= 100.0
        # 父スコアと大きく外れないこと（0.6係数で重み付けされた合成）
        assert abs(score_both - score_sire_only) < 50.0
