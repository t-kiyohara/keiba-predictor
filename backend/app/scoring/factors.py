"""各スコアリングファクターの算出関数群"""

from sqlalchemy.orm import Session

from app.models import Race, Horse, Result, Entry, Jockey, Trainer
from app.scoring.weights import NEUTRAL_SCORE, DISTANCE_TOLERANCE_M


def _clamp(score: float) -> float:
    """0〜100の範囲にclamp"""
    return max(0.0, min(100.0, score))


def _position_score(pos: int) -> float:
    """着順を点数に変換"""
    if pos == 1:
        return 100.0
    elif pos == 2:
        return 85.0
    elif pos == 3:
        return 70.0
    elif pos == 4:
        return 55.0
    elif pos == 5:
        return 40.0
    else:
        return max(0.0, 40.0 - 5.0 * (pos - 5))


def _win_rate_score(
    results: list,
    w_win: float = 60,
    w_rentai: float = 30,
    w_fukusho: float = 10,
) -> float:
    """勝率・連対率・複勝率から加重スコアを算出する。

    結果が空の場合は NEUTRAL_SCORE を返す。
    """
    if not results:
        return NEUTRAL_SCORE
    total = len(results)
    win_rate = sum(1 for r in results if r.finish_position == 1) / total
    rentai_rate = sum(1 for r in results if r.finish_position <= 2) / total
    fukusho_rate = sum(1 for r in results if r.finish_position <= 3) / total
    raw = win_rate * w_win + rentai_rate * w_rentai + fukusho_rate * w_fukusho
    return _clamp(raw)


def score_recent_form(db: Session, horse_id: str, limit: int = 5) -> float:
    """近走成績スコア（直近N走の着順と上がり3Fから算出）

    - 直近の結果をlimit件取得（results テーブルから race.date 降順）
    - 着順スコア: 1着=100, 2着=85, 3着=70, 4着=55, 5着=40, 6着以下=max(0, 40-5*(pos-5))
    - 上がり3Fボーナス: 出走レースの中で上がり3F最速なら+10, 2位なら+5
    - 最終スコア = 着順スコアの平均 + 上がり3Fボーナスの平均
    - 上限100にclamp
    """
    # 直近N走を取得（race.date 降順）
    recent_results = (
        db.query(Result)
        .join(Race, Result.race_id == Race.id)
        .filter(Result.horse_id == horse_id)
        .filter(Result.finish_position.isnot(None))
        .order_by(Race.date.desc())
        .limit(limit)
        .all()
    )

    if not recent_results:
        return NEUTRAL_SCORE

    position_scores = []
    last3f_bonuses = []

    for result in recent_results:
        # 着順スコア
        pos = result.finish_position
        position_scores.append(_position_score(pos))

        # 上がり3Fボーナス: 同じレース内での順位を調べる
        bonus = 0.0
        if result.last_3f is not None:
            # 同一レースの上がり3F一覧（NULLを除く、昇順=速い順）
            race_last3f_list = (
                db.query(Result.last_3f)
                .filter(Result.race_id == result.race_id)
                .filter(Result.last_3f.isnot(None))
                .order_by(Result.last_3f.asc())
                .all()
            )
            times = [r[0] for r in race_last3f_list]
            if times:
                if times[0] == result.last_3f:
                    bonus = 10.0
                elif len(times) >= 2 and times[1] == result.last_3f:
                    bonus = 5.0
        last3f_bonuses.append(bonus)

    avg_position_score = sum(position_scores) / len(position_scores)
    avg_bonus = sum(last3f_bonuses) / len(last3f_bonuses)

    return _clamp(avg_position_score + avg_bonus)


def score_same_race(db: Session, horse_id: str, race_name: str) -> float:
    """同レース成績スコア

    - 同じレース名(race.name に race_name を含む)での過去結果を取得
    - 出走なし → 50（中立スコア）
    - 1着経験あり → 90+, 2着 → 75+, 3着 → 65+
    - 複数回出走の場合は平均着順で算出
    """
    results = (
        db.query(Result)
        .join(Race, Result.race_id == Race.id)
        .filter(Result.horse_id == horse_id)
        .filter(Race.name.contains(race_name))
        .filter(Result.finish_position.isnot(None))
        .all()
    )

    if not results:
        return NEUTRAL_SCORE

    scores = [_position_score(r.finish_position) for r in results]
    avg_score = sum(scores) / len(scores)

    # 上位入賞経験ボーナス
    best_pos = min(r.finish_position for r in results)
    if best_pos == 1:
        base = 90.0
    elif best_pos == 2:
        base = 75.0
    elif best_pos == 3:
        base = 65.0
    else:
        base = avg_score

    # ベーススコアと平均スコアの中間値
    score = (base + avg_score) / 2.0
    return _clamp(score)


def score_course_aptitude(db: Session, horse_id: str, venue: str, distance: int) -> float:
    """コース適性スコア

    - 同競馬場(race.venue)での成績
    - 同距離(race.distance, ±DISTANCE_TOLERANCE_M許容)での成績
    - 両方の条件に合致するレースほど高いウェイト
    - 勝率 * 60 + 連対率 * 30 + 複勝率 * 10 を基本算出式に
    """
    # 同競馬場かつ同距離（±DISTANCE_TOLERANCE_M）での成績（ウェイト高）
    both_results = (
        db.query(Result)
        .join(Race, Result.race_id == Race.id)
        .filter(Result.horse_id == horse_id)
        .filter(Race.venue == venue)
        .filter(Race.distance >= distance - DISTANCE_TOLERANCE_M)
        .filter(Race.distance <= distance + DISTANCE_TOLERANCE_M)
        .filter(Result.finish_position.isnot(None))
        .all()
    )

    # 同競馬場のみ
    venue_results = (
        db.query(Result)
        .join(Race, Result.race_id == Race.id)
        .filter(Result.horse_id == horse_id)
        .filter(Race.venue == venue)
        .filter(Result.finish_position.isnot(None))
        .all()
    )

    # 同距離のみ（±DISTANCE_TOLERANCE_M）
    distance_results = (
        db.query(Result)
        .join(Race, Result.race_id == Race.id)
        .filter(Result.horse_id == horse_id)
        .filter(Race.distance >= distance - DISTANCE_TOLERANCE_M)
        .filter(Race.distance <= distance + DISTANCE_TOLERANCE_M)
        .filter(Result.finish_position.isnot(None))
        .all()
    )

    def calc_score(results):
        """結果リストから勝率ベーススコアを算出する（データなしは None）"""
        if not results:
            return None
        return _win_rate_score(results)

    score_both = calc_score(both_results)
    score_venue = calc_score(venue_results)
    score_distance = calc_score(distance_results)

    # データがある組み合わせで加重平均
    if score_both is not None:
        # 両条件一致を最高ウェイト
        parts = [score_both * 0.6]
        weight_sum = 0.6
        if score_venue is not None:
            parts.append(score_venue * 0.25)
            weight_sum += 0.25
        if score_distance is not None:
            parts.append(score_distance * 0.15)
            weight_sum += 0.15
        score = sum(parts) / weight_sum
    elif score_venue is not None and score_distance is not None:
        score = (score_venue + score_distance) / 2.0
    elif score_venue is not None:
        score = score_venue
    elif score_distance is not None:
        score = score_distance
    else:
        return NEUTRAL_SCORE

    return _clamp(score)


def score_track_condition(db: Session, horse_id: str, track_condition: str) -> float:
    """馬場状態適性スコア

    - 同じ馬場状態(result → race.track_condition)での成績
    - 勝率ベースでスコア化
    - 当該馬場状態でのデータなし → NEUTRAL_SCORE
    """
    results = (
        db.query(Result)
        .join(Race, Result.race_id == Race.id)
        .filter(Result.horse_id == horse_id)
        .filter(Race.track_condition == track_condition)
        .filter(Result.finish_position.isnot(None))
        .all()
    )

    if not results:
        return NEUTRAL_SCORE

    return _win_rate_score(results)


def _score_person(
    db: Session,
    person_id: str | None,
    person_id_col,
    venue: str,
    grade: str,
) -> float:
    """騎手または調教師のスコアを算出する共通ロジック。

    venue別勝率スコアと grade別勝率スコアを50:50で合算する。
    """
    if not person_id:
        return NEUTRAL_SCORE

    def calc_win_rate_score(results):
        """結果リストから勝率ベーススコアを算出する（データなしは None）"""
        if not results:
            return None
        return _win_rate_score(results, w_win=60, w_rentai=25, w_fukusho=15)

    # 同競馬場での成績（distinct で重複排除）
    venue_results = (
        db.query(Result)
        .join(Race, Result.race_id == Race.id)
        .join(Entry, (Entry.race_id == Result.race_id) & (Entry.horse_id == Result.horse_id))
        .filter(person_id_col == person_id)
        .filter(Race.venue == venue)
        .filter(Result.finish_position.isnot(None))
        .distinct()
        .all()
    )

    # 同グレードでの成績
    grade_results = (
        db.query(Result)
        .join(Race, Result.race_id == Race.id)
        .join(Entry, (Entry.race_id == Result.race_id) & (Entry.horse_id == Result.horse_id))
        .filter(person_id_col == person_id)
        .filter(Race.grade == grade)
        .filter(Result.finish_position.isnot(None))
        .distinct()
        .all()
    )

    venue_score = calc_win_rate_score(venue_results)
    grade_score = calc_win_rate_score(grade_results)

    if venue_score is not None and grade_score is not None:
        return _clamp((venue_score + grade_score) / 2.0)
    elif venue_score is not None:
        return _clamp(venue_score)
    elif grade_score is not None:
        return _clamp(grade_score)
    else:
        return NEUTRAL_SCORE


def score_jockey(db: Session, jockey_id: str, venue: str, grade: str) -> float:
    """騎手成績スコア

    - 同競馬場での勝率
    - 同グレード(G1/G2/G3)での勝率
    - 両方を50:50で合成
    """
    return _score_person(db, jockey_id, Entry.jockey_id, venue, grade)


def score_trainer(db: Session, trainer_id: str, venue: str, grade: str) -> float:
    """調教師成績スコア

    - 同競馬場での勝率
    - 同グレードでの勝率
    - 両方を50:50で合成
    """
    return _score_person(db, trainer_id, Entry.trainer_id, venue, grade)


def score_bloodline(db: Session, horse_id: str, venue: str, distance: int, course_type: str) -> float:
    """血統適性スコア

    - 同じ父(sire)を持つ馬の同コース(場/距離/芝ダート)での成績
    - 同じ母父(dam_sire)を持つ馬の同コースでの成績
    - 父スコア * 0.6 + 母父スコア * 0.4
    - 勝率・連対率ベース
    """
    # 対象馬の血統情報を取得
    horse = db.query(Horse).filter(Horse.id == horse_id).first()
    if horse is None:
        return NEUTRAL_SCORE

    def calc_bloodline_score(sire_name: str, field: str) -> float | None:
        """指定した父または母父を持つ馬群の同コース成績"""
        if not sire_name:
            return None

        # 同じ父/母父を持つ馬のIDを取得（自馬を除外）
        if field == "sire":
            sibling_horses = db.query(Horse.id).filter(Horse.sire == sire_name, Horse.id != horse_id).all()
        else:
            sibling_horses = db.query(Horse.id).filter(Horse.dam_sire == sire_name, Horse.id != horse_id).all()

        sibling_ids = [h[0] for h in sibling_horses]
        if not sibling_ids:
            return None

        # 同コース（場・距離±DISTANCE_TOLERANCE_M・芝ダート）での成績
        results = (
            db.query(Result)
            .join(Race, Result.race_id == Race.id)
            .filter(Result.horse_id.in_(sibling_ids))
            .filter(Race.venue == venue)
            .filter(Race.distance >= distance - DISTANCE_TOLERANCE_M)
            .filter(Race.distance <= distance + DISTANCE_TOLERANCE_M)
            .filter(Race.course_type == course_type)
            .filter(Result.finish_position.isnot(None))
            .all()
        )

        if not results:
            return None

        total = len(results)
        wins = sum(1 for r in results if r.finish_position == 1)
        top2 = sum(1 for r in results if r.finish_position <= 2)
        win_rate = wins / total
        rentai_rate = top2 / total
        # 勝率60% + 連対率40% で加重スコア算出（fukushoは使用しない）
        return _clamp(win_rate * 60.0 + rentai_rate * 40.0)

    sire_score = calc_bloodline_score(horse.sire, "sire")
    dam_sire_score = calc_bloodline_score(horse.dam_sire, "dam_sire")

    if sire_score is not None and dam_sire_score is not None:
        return _clamp(sire_score * 0.6 + dam_sire_score * 0.4)
    elif sire_score is not None:
        return _clamp(sire_score)
    elif dam_sire_score is not None:
        return _clamp(dam_sire_score)
    else:
        return NEUTRAL_SCORE


def score_overall(db: Session, horse_id: str) -> float:
    """総合実績スコア

    - 通算勝率
    - 重賞(G1/G2/G3)での着順
    - 勝率 * 50 + 重賞好走率 * 50
    """
    all_results = (
        db.query(Result)
        .filter(Result.horse_id == horse_id)
        .filter(Result.finish_position.isnot(None))
        .all()
    )

    if not all_results:
        return NEUTRAL_SCORE

    total = len(all_results)
    wins = sum(1 for r in all_results if r.finish_position == 1)
    win_rate = wins / total

    # 重賞（G1/G2/G3）での好走率（3着以内）
    graded_results = (
        db.query(Result)
        .join(Race, Result.race_id == Race.id)
        .filter(Result.horse_id == horse_id)
        .filter(Race.grade.in_(["G1", "G2", "G3"]))
        .filter(Result.finish_position.isnot(None))
        .all()
    )

    if graded_results:
        graded_total = len(graded_results)
        graded_top3 = sum(1 for r in graded_results if r.finish_position <= 3)
        graded_rate = graded_top3 / graded_total
    else:
        graded_rate = 0.0

    score = win_rate * 50.0 + graded_rate * 50.0
    return _clamp(score)
