"""スコアリングエンジン"""

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

    def calculate_horse_score(self, horse_id: str, race: Race, entry: Entry) -> dict:
        """1頭のスコアを全ファクターで算出

        Returns:
            {
                "total_score": 75.5,
                "factor_scores": {
                    "recent_form": {"score": 80.0, "label": "近走成績", "weighted": 16.0},
                    "same_race": {"score": 60.0, "label": "同レース成績", "weighted": 9.0},
                    ...
                }
            }
        """
        # 各ファクターのスコアを算出
        raw_scores = {
            "recent_form": factors.score_recent_form(self.db, horse_id),
            "same_race": factors.score_same_race(self.db, horse_id, race.name),
            "course_aptitude": factors.score_course_aptitude(self.db, horse_id, race.venue, race.distance),
            "track_condition": factors.score_track_condition(self.db, horse_id, race.track_condition or "良"),
            "jockey": factors.score_jockey(self.db, entry.jockey_id, race.venue, race.grade),
            "trainer": factors.score_trainer(self.db, entry.trainer_id, race.venue, race.grade),
            "bloodline": factors.score_bloodline(self.db, horse_id, race.venue, race.distance, race.course_type),
            "overall": factors.score_overall(self.db, horse_id),
        }

        # データ不足ペナルティ判定
        race_count = self.db.query(Result).filter(Result.horse_id == horse_id).count()
        penalty = 1.0 if race_count >= MIN_RACES_FOR_FULL_SCORE else DATA_SHORTAGE_PENALTY

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

    def predict_race(self, race_id: str) -> list[dict]:
        """レース全体の予想を生成

        1. レースの全出走馬のスコアを算出
        2. スコア順にソート
        3. Prediction テーブルに保存
        4. ランキング結果を返却

        Returns:
            [
                {"rank": 1, "horse_id": "...", "horse_name": "...", "total_score": 82.3, "factor_scores": {...}},
                {"rank": 2, ...},
                ...
            ]
        """
        # レースを取得
        race = self.db.query(Race).filter(Race.id == race_id).first()
        if race is None:
            raise ValueError(f"Race not found: {race_id}")

        # 関連する Entry を全件取得
        entries = self.db.query(Entry).filter(Entry.race_id == race_id).all()
        if not entries:
            return []

        # 各 Entry に対してスコアを算出
        scored_entries = []
        for entry in entries:
            result = self.calculate_horse_score(entry.horse_id, race, entry)
            # 馬名を取得
            horse = self.db.query(Horse).filter(Horse.id == entry.horse_id).first()
            horse_name = horse.name if horse else entry.horse_id
            scored_entries.append({
                "horse_id": entry.horse_id,
                "horse_name": horse_name,
                "total_score": result["total_score"],
                "factor_scores": result["factor_scores"],
            })

        # total_score 降順でソート
        scored_entries.sort(key=lambda x: x["total_score"], reverse=True)

        # rank を1から振る
        for i, item in enumerate(scored_entries, start=1):
            item["rank"] = i

        # 既存の Prediction を削除してから新規保存
        self.db.query(Prediction).filter(Prediction.race_id == race_id).delete()

        for item in scored_entries:
            prediction = Prediction(
                race_id=race_id,
                horse_id=item["horse_id"],
                total_score=item["total_score"],
                rank=item["rank"],
                score_details=item["factor_scores"],
            )
            self.db.add(prediction)

        self.db.flush()

        return scored_entries
