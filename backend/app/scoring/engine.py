"""スコアリングエンジン"""

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Entry, Horse, Prediction, Race, Result
from app.scoring import factors
from app.scoring.weights import (
    DATA_SHORTAGE_PENALTY,
    FACTOR_LABELS,
    FACTOR_WEIGHTS,
    MIN_RACES_FOR_FULL_SCORE,
)


class ScoringEngine:
    """スコアリングエンジン: 出走馬の予想スコアを算出"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 公開メソッド
    # ------------------------------------------------------------------

    def calculate_horse_score(self, horse_id: str, race: Race, entry: Entry) -> dict:
        """1頭のスコアを全ファクターで算出（後方互換・テスト用）

        predict_race() を使う場合は全馬分のデータを一括プリロードするため
        N+1が発生しない。このメソッドは単馬のプリロードを行うため、
        テストや単体スコア確認に使用する。

        Note:
            血統スコアで predict_race() と微差が生じる場合がある。
            predict_race() は同レース全馬を除外するが、このメソッドは
            対象馬のみを除外するため、同レースに兄弟馬がいる場合に
            わずかに高い血統スコアを返す可能性がある。

        Returns:
            {
                "total_score": 75.5,
                "factor_scores": {
                    "recent_form": {"score": 80.0, "label": "近走成績", "weighted": 16.0},
                    ...
                }
            }
        """
        horse = self.db.get(Horse, horse_id)
        horse_results = self._load_horse_results([horse_id])
        horse_results_list = horse_results.get(horse_id, [])
        race_ids = {r.race_id for r, _ in horse_results_list}
        race_last3f = self._load_race_last3f(race_ids)
        jockey_results = (
            self._load_jockey_results([entry.jockey_id]).get(entry.jockey_id, [])
            if entry.jockey_id
            else []
        )
        trainer_results = (
            self._load_trainer_results([entry.trainer_id]).get(entry.trainer_id, [])
            if entry.trainer_id
            else []
        )
        sire_results, dam_sire_results = self._load_bloodline_results(horse)

        return self._score_horse(
            horse=horse,
            race=race,
            horse_results=horse_results_list,
            race_last3f=race_last3f,
            jockey_results=jockey_results,
            trainer_results=trainer_results,
            sire_results=sire_results,
            dam_sire_results=dam_sire_results,
        )

    def predict_race(self, race_id: str) -> list[dict]:
        """レース全体の予想を生成（全馬データを一括プリロード）

        1. 全出走馬・騎手・調教師・血統データを一括取得（N+1を解消）
        2. スコア順にソート
        3. Prediction テーブルに保存
        4. ランキング結果を返却

        Returns:
            [
                {"rank": 1, "horse_id": "...", "horse_name": "...", "total_score": 82.3, "factor_scores": {...}},
                ...
            ]
        """
        race = self.db.get(Race, race_id)
        if race is None:
            raise ValueError(f"Race not found: {race_id}")

        entries = self.db.query(Entry).filter(Entry.race_id == race_id).all()
        if not entries:
            return []

        horse_ids = [e.horse_id for e in entries]
        jockey_ids = [e.jockey_id for e in entries if e.jockey_id]
        trainer_ids = [e.trainer_id for e in entries if e.trainer_id]

        # 一括プリロード
        horses_map = {
            h.id: h
            for h in self.db.query(Horse).filter(Horse.id.in_(horse_ids)).all()
        }
        horse_results_map = self._load_horse_results(horse_ids)
        all_race_ids: set[str] = set()
        for results in horse_results_map.values():
            for r, _ in results:
                all_race_ids.add(r.race_id)
        race_last3f = self._load_race_last3f(all_race_ids)
        jockey_results_map = self._load_jockey_results(jockey_ids) if jockey_ids else {}
        trainer_results_map = self._load_trainer_results(trainer_ids) if trainer_ids else {}

        # 血統別プリロード（sire/dam_sire ごとに全兄弟馬の結果をまとめる）
        sire_results_map, dam_sire_results_map = self._load_bloodline_results_bulk(
            horses_map, exclude_ids=horse_ids
        )

        # 各 Entry に対してスコアを算出
        scored_entries = []
        for entry in entries:
            horse = horses_map.get(entry.horse_id)
            horse_results = horse_results_map.get(entry.horse_id, [])
            jockey_results = jockey_results_map.get(entry.jockey_id, []) if entry.jockey_id else []
            trainer_results = trainer_results_map.get(entry.trainer_id, []) if entry.trainer_id else []
            sire_results = sire_results_map.get(horse.sire, []) if horse and horse.sire else []
            dam_sire_results = dam_sire_results_map.get(horse.dam_sire, []) if horse and horse.dam_sire else []

            score_result = self._score_horse(
                horse=horse,
                race=race,
                horse_results=horse_results,
                race_last3f=race_last3f,
                jockey_results=jockey_results,
                trainer_results=trainer_results,
                sire_results=sire_results,
                dam_sire_results=dam_sire_results,
            )
            horse_name = horse.name if horse else entry.horse_id
            scored_entries.append({
                "horse_id": entry.horse_id,
                "horse_name": horse_name,
                "total_score": score_result["total_score"],
                "factor_scores": score_result["factor_scores"],
            })

        # total_score 降順でソート、rank を1から振る
        scored_entries.sort(key=lambda x: x["total_score"], reverse=True)
        for i, item in enumerate(scored_entries, start=1):
            item["rank"] = i

        # 既存の Prediction を削除してから新規保存
        self.db.query(Prediction).filter(Prediction.race_id == race_id).delete()
        for item in scored_entries:
            self.db.add(Prediction(
                race_id=race_id,
                horse_id=item["horse_id"],
                total_score=item["total_score"],
                rank=item["rank"],
                score_details=item["factor_scores"],
            ))
        self.db.flush()

        return scored_entries

    # ------------------------------------------------------------------
    # 内部スコアリング
    # ------------------------------------------------------------------

    def _score_horse(
        self,
        horse: Horse | None,
        race: Race,
        horse_results: list[tuple],
        race_last3f: dict[str, list[float]],
        jockey_results: list[tuple],
        trainer_results: list[tuple],
        sire_results: list[tuple],
        dam_sire_results: list[tuple],
    ) -> dict:
        """プリロード済みデータで1頭のスコアを算出する内部メソッド"""
        raw_scores = {
            "recent_form": factors.score_recent_form(horse_results, race_last3f),
            "same_race": factors.score_same_race(horse_results, race.name),
            "course_aptitude": factors.score_course_aptitude(
                horse_results, race.venue, race.distance
            ),
            "track_condition": factors.score_track_condition(
                horse_results, race.track_condition or "良"
            ),
            "jockey": factors.score_jockey(jockey_results, race.venue, race.grade),
            "trainer": factors.score_trainer(trainer_results, race.venue, race.grade),
            "bloodline": factors.score_bloodline(
                horse, sire_results, dam_sire_results,
                race.venue, race.distance, race.course_type,
            ),
            "overall": factors.score_overall(horse_results),
        }

        result_count = len(horse_results)
        penalty = 1.0 if result_count >= MIN_RACES_FOR_FULL_SCORE else DATA_SHORTAGE_PENALTY

        total_score = 0.0
        factor_scores = {}
        for factor_name, score in raw_scores.items():
            weight = FACTOR_WEIGHTS[factor_name]
            weighted = score * weight * penalty
            total_score += weighted
            factor_scores[factor_name] = {
                "score": round(score, 1),
                "label": FACTOR_LABELS[factor_name],
                "weighted": round(weighted, 1),
            }

        return {
            "total_score": round(total_score, 1),
            "factor_scores": factor_scores,
        }

    # ------------------------------------------------------------------
    # プリロードヘルパー
    # ------------------------------------------------------------------

    def _load_horse_results(
        self, horse_ids: list[str]
    ) -> dict[str, list[tuple]]:
        """複数馬の全成績を一括取得（date 降順でソート済み）"""
        if not horse_ids:
            return {}
        rows = (
            self.db.query(Result, Race)
            .join(Race, Result.race_id == Race.id)
            .filter(Result.horse_id.in_(horse_ids))
            .filter(Result.finish_position.isnot(None))
            .order_by(Race.date.desc(), Race.id.desc())  # Race.id で同日内の順序を安定化
            .all()
        )
        result_map: dict[str, list[tuple]] = defaultdict(list)
        for r, race in rows:
            result_map[r.horse_id].append((r, race))
        return dict(result_map)

    def _load_race_last3f(
        self, race_ids: set[str]
    ) -> dict[str, list[float]]:
        """複数レースの last_3f を一括取得（race_id → 昇順リスト）"""
        if not race_ids:
            return {}
        rows = (
            self.db.query(Result.race_id, Result.last_3f)
            .filter(Result.race_id.in_(race_ids))
            .filter(Result.last_3f.isnot(None))
            .order_by(Result.race_id, Result.last_3f.asc())
            .all()
        )
        last3f_map: dict[str, list[float]] = defaultdict(list)
        for race_id, l3f in rows:
            last3f_map[race_id].append(l3f)
        return dict(last3f_map)

    def _load_jockey_results(
        self, jockey_ids: list[str]
    ) -> dict[str, list[tuple]]:
        """複数騎手の全成績を一括取得（jockey_id → [(Result, Race)]）"""
        if not jockey_ids:
            return {}
        rows = (
            self.db.query(Entry.jockey_id, Result, Race)
            .join(
                Result,
                (Entry.race_id == Result.race_id)
                & (Entry.horse_id == Result.horse_id),
            )
            .join(Race, Result.race_id == Race.id)
            .filter(Entry.jockey_id.in_(jockey_ids))
            .filter(Result.finish_position.isnot(None))
            .distinct()
            .all()
        )
        result_map: dict[str, list[tuple]] = defaultdict(list)
        for jockey_id, r, race in rows:
            result_map[jockey_id].append((r, race))
        return dict(result_map)

    def _load_trainer_results(
        self, trainer_ids: list[str]
    ) -> dict[str, list[tuple]]:
        """複数調教師の全成績を一括取得（trainer_id → [(Result, Race)]）"""
        if not trainer_ids:
            return {}
        rows = (
            self.db.query(Entry.trainer_id, Result, Race)
            .join(
                Result,
                (Entry.race_id == Result.race_id)
                & (Entry.horse_id == Result.horse_id),
            )
            .join(Race, Result.race_id == Race.id)
            .filter(Entry.trainer_id.in_(trainer_ids))
            .filter(Result.finish_position.isnot(None))
            .distinct()
            .all()
        )
        result_map: dict[str, list[tuple]] = defaultdict(list)
        for trainer_id, r, race in rows:
            result_map[trainer_id].append((r, race))
        return dict(result_map)

    def _load_bloodline_results(
        self, horse: Horse | None
    ) -> tuple[list[tuple], list[tuple]]:
        """単馬の血統成績をプリロード（calculate_horse_score 用）"""
        if horse is None:
            return [], []

        def load_by_field(sire_name: str, field_col) -> list[tuple]:
            if not sire_name:
                return []
            rows = (
                self.db.query(Result, Race)
                .join(Horse, Result.horse_id == Horse.id)
                .join(Race, Result.race_id == Race.id)
                .filter(field_col == sire_name)
                .filter(Horse.id != horse.id)
                .filter(Result.finish_position.isnot(None))
                .all()
            )
            return list(rows)

        sire_results = load_by_field(horse.sire, Horse.sire)
        dam_sire_results = load_by_field(horse.dam_sire, Horse.dam_sire)
        return sire_results, dam_sire_results

    def _load_bloodline_results_bulk(
        self,
        horses_map: dict[str, Horse],
        exclude_ids: list[str],
    ) -> tuple[dict[str, list[tuple]], dict[str, list[tuple]]]:
        """全馬の血統成績を一括取得（predict_race 用）

        Returns:
            (sire_results_map, dam_sire_results_map)
            各 map は sire_name/dam_sire_name → [(Result, Race)]
        """
        all_sires = {h.sire for h in horses_map.values() if h and h.sire}
        all_dam_sires = {h.dam_sire for h in horses_map.values() if h and h.dam_sire}

        sire_map: dict[str, list[tuple]] = defaultdict(list)
        if all_sires:
            rows = (
                self.db.query(Horse.sire, Result, Race)
                .join(Result, Horse.id == Result.horse_id)
                .join(Race, Result.race_id == Race.id)
                .filter(Horse.sire.in_(all_sires))
                .filter(Horse.id.notin_(exclude_ids))
                .filter(Result.finish_position.isnot(None))
                .all()
            )
            for sire_name, r, race in rows:
                sire_map[sire_name].append((r, race))

        dam_sire_map: dict[str, list[tuple]] = defaultdict(list)
        if all_dam_sires:
            rows = (
                self.db.query(Horse.dam_sire, Result, Race)
                .join(Result, Horse.id == Result.horse_id)
                .join(Race, Result.race_id == Race.id)
                .filter(Horse.dam_sire.in_(all_dam_sires))
                .filter(Horse.id.notin_(exclude_ids))
                .filter(Result.finish_position.isnot(None))
                .all()
            )
            for dam_sire_name, r, race in rows:
                dam_sire_map[dam_sire_name].append((r, race))

        return dict(sire_map), dict(dam_sire_map)
