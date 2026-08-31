"""各スコアリングファクターの算出関数群

全てのファクター関数はDBセッションではなく事前ロード済みデータを受け取る。
エンジン側で全馬分のデータを一括プリロードし、N+1クエリを解消する。
"""

from app.models import Horse
from app.scoring.weights import DISTANCE_TOLERANCE_M, NEUTRAL_SCORE


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
    results は finish_position 属性を持つ Result オブジェクトのリスト。
    """
    if not results:
        return NEUTRAL_SCORE
    total = len(results)
    win_rate = sum(1 for r in results if r.finish_position == 1) / total
    rentai_rate = sum(1 for r in results if r.finish_position <= 2) / total
    fukusho_rate = sum(1 for r in results if r.finish_position <= 3) / total
    raw = win_rate * w_win + rentai_rate * w_rentai + fukusho_rate * w_fukusho
    return _clamp(raw)


def score_recent_form(
    horse_results: list[tuple],
    race_last3f: dict[str, list[float]],
    limit: int = 5,
) -> float:
    """近走成績スコア（直近N走の着順と上がり3Fから算出）

    Args:
        horse_results: (Result, Race) のリスト（race.date 降順でソート済み）
        race_last3f: race_id → そのレース全出走馬の last_3f 昇順リスト
        limit: 直近N走

    - 着順スコア: 1着=100, 2着=85, 3着=70, 4着=55, 5着=40, 6着以下=max(0, 40-5*(pos-5))
    - 上がり3Fボーナス: 出走レースの中で上がり3F最速なら+10, 2位なら+5
    - 最終スコア = 着順スコアの平均 + 上がり3Fボーナスの平均（上限100）
    """
    recent = horse_results[:limit]
    if not recent:
        return NEUTRAL_SCORE

    position_scores = []
    last3f_bonuses = []

    for result, _race in recent:
        position_scores.append(_position_score(result.finish_position))

        bonus = 0.0
        if result.last_3f is not None:
            times = race_last3f.get(result.race_id, [])
            if times:
                if times[0] == result.last_3f:
                    bonus = 10.0
                elif len(times) >= 2 and times[1] == result.last_3f:
                    bonus = 5.0
        last3f_bonuses.append(bonus)

    avg_position_score = sum(position_scores) / len(position_scores)
    avg_bonus = sum(last3f_bonuses) / len(last3f_bonuses)
    return _clamp(avg_position_score + avg_bonus)


def score_same_race(
    horse_results: list[tuple],
    race_name: str,
) -> float:
    """同レース成績スコア

    Args:
        horse_results: (Result, Race) のリスト
        race_name: 対象レース名（部分一致）

    - 出走なし → 50（中立スコア）
    - 1着経験あり → 90+, 2着 → 75+, 3着 → 65+
    - 複数回出走の場合は平均着順で算出
    """
    matching = [r for r, race in horse_results if race_name in race.name]
    if not matching:
        return NEUTRAL_SCORE

    scores = [_position_score(r.finish_position) for r in matching]
    avg_score = sum(scores) / len(scores)

    best_pos = min(r.finish_position for r in matching)
    if best_pos == 1:
        base = 90.0
    elif best_pos == 2:
        base = 75.0
    elif best_pos == 3:
        base = 65.0
    else:
        base = avg_score

    return _clamp((base + avg_score) / 2.0)


def score_course_aptitude(
    horse_results: list[tuple],
    venue: str,
    distance: int,
) -> float:
    """コース適性スコア

    Args:
        horse_results: (Result, Race) のリスト
        venue: 競馬場名
        distance: 距離（メートル）

    - 同競馬場(race.venue)での成績
    - 同距離(race.distance, ±DISTANCE_TOLERANCE_M許容)での成績
    - 両方の条件に合致するレースほど高いウェイト
    """
    both = [r for r, race in horse_results
            if race.venue == venue
            and abs(race.distance - distance) <= DISTANCE_TOLERANCE_M]
    venue_only = [r for r, race in horse_results if race.venue == venue]
    dist_only = [r for r, race in horse_results
                 if abs(race.distance - distance) <= DISTANCE_TOLERANCE_M]

    score_both = _win_rate_score(both) if both else None
    score_venue = _win_rate_score(venue_only) if venue_only else None
    score_dist = _win_rate_score(dist_only) if dist_only else None

    if score_both is not None:
        parts = [score_both * 0.6]
        weight_sum = 0.6
        if score_venue is not None:
            parts.append(score_venue * 0.25)
            weight_sum += 0.25
        if score_dist is not None:
            parts.append(score_dist * 0.15)
            weight_sum += 0.15
        return _clamp(sum(parts) / weight_sum)
    elif score_venue is not None and score_dist is not None:
        return _clamp((score_venue + score_dist) / 2.0)
    elif score_venue is not None:
        return _clamp(score_venue)
    elif score_dist is not None:
        return _clamp(score_dist)
    else:
        return NEUTRAL_SCORE


def score_track_condition(
    horse_results: list[tuple],
    track_condition: str,
) -> float:
    """馬場状態適性スコア

    Args:
        horse_results: (Result, Race) のリスト
        track_condition: 馬場状態（良/稍重/重/不良）

    - 同じ馬場状態(race.track_condition)での成績
    - 勝率ベースでスコア化
    - 当該馬場状態でのデータなし → NEUTRAL_SCORE
    """
    matching = [r for r, race in horse_results
                if race.track_condition == track_condition]
    if not matching:
        return NEUTRAL_SCORE
    return _win_rate_score(matching)


def _score_person(
    person_results: list[tuple],
    venue: str,
    grade: str,
) -> float:
    """騎手または調教師のスコアを算出する共通ロジック。

    Args:
        person_results: (Result, Race) のリスト（対象人物の全成績）
        venue: 競馬場名
        grade: グレード（G1/G2/G3）

    venue別勝率スコアと grade別勝率スコアを50:50で合算する。
    """
    if not person_results:
        return NEUTRAL_SCORE

    def calc(results_list):
        if not results_list:
            return None
        return _win_rate_score(results_list, w_win=60, w_rentai=25, w_fukusho=15)

    venue_results = [r for r, race in person_results if race.venue == venue]
    grade_results = [r for r, race in person_results if race.grade == grade]

    venue_score = calc(venue_results)
    grade_score = calc(grade_results)

    if venue_score is not None and grade_score is not None:
        return _clamp((venue_score + grade_score) / 2.0)
    elif venue_score is not None:
        return _clamp(venue_score)
    elif grade_score is not None:
        return _clamp(grade_score)
    else:
        return NEUTRAL_SCORE


def score_jockey(
    jockey_results: list[tuple],
    venue: str,
    grade: str,
) -> float:
    """騎手成績スコア

    Args:
        jockey_results: 騎手の (Result, Race) リスト（空リストならNEUTRAL_SCORE）
        venue: 競馬場名
        grade: グレード

    - 同競馬場での勝率
    - 同グレード(G1/G2/G3)での勝率
    - 両方を50:50で合成
    """
    return _score_person(jockey_results, venue, grade)


def score_trainer(
    trainer_results: list[tuple],
    venue: str,
    grade: str,
) -> float:
    """調教師成績スコア

    Args:
        trainer_results: 調教師の (Result, Race) リスト（空リストならNEUTRAL_SCORE）
        venue: 競馬場名
        grade: グレード

    - 同競馬場での勝率
    - 同グレードでの勝率
    - 両方を50:50で合成
    """
    return _score_person(trainer_results, venue, grade)


def score_bloodline(
    horse: Horse | None,
    sire_results: list[tuple],
    dam_sire_results: list[tuple],
    venue: str,
    distance: int,
    course_type: str,
) -> float:
    """血統適性スコア

    Args:
        horse: 対象馬オブジェクト（sire/dam_sire フィールドを使用）
        sire_results: 同父を持つ馬群の (Result, Race) リスト
        dam_sire_results: 同母父を持つ馬群の (Result, Race) リスト
        venue: 競馬場名
        distance: 距離（メートル）
        course_type: コース種別（芝/ダート）

    - 同じ父(sire)を持つ馬の同コース(場/距離/芝ダート)での成績
    - 同じ母父(dam_sire)を持つ馬の同コースでの成績
    - 父スコア * 0.6 + 母父スコア * 0.4
    """
    if horse is None:
        return NEUTRAL_SCORE

    def filter_course(results: list[tuple]) -> list:
        return [
            r for r, race in results
            if race.venue == venue
            and abs(race.distance - distance) <= DISTANCE_TOLERANCE_M
            and race.course_type == course_type
        ]

    def calc_bloodline_score(results_list: list) -> float | None:
        if not results_list:
            return None
        total = len(results_list)
        wins = sum(1 for r in results_list if r.finish_position == 1)
        top2 = sum(1 for r in results_list if r.finish_position <= 2)
        return _clamp(wins / total * 60.0 + top2 / total * 40.0)

    sire_score = (
        calc_bloodline_score(filter_course(sire_results)) if horse.sire else None
    )
    dam_sire_score = (
        calc_bloodline_score(filter_course(dam_sire_results))
        if horse.dam_sire
        else None
    )

    if sire_score is not None and dam_sire_score is not None:
        return _clamp(sire_score * 0.6 + dam_sire_score * 0.4)
    elif sire_score is not None:
        return _clamp(sire_score)
    elif dam_sire_score is not None:
        return _clamp(dam_sire_score)
    else:
        return NEUTRAL_SCORE


def score_overall(
    horse_results: list[tuple],
) -> float:
    """総合実績スコア

    Args:
        horse_results: 全 (Result, Race) のリスト

    - 通算勝率
    - 重賞(G1/G2/G3)での着順
    - 勝率 * 50 + 重賞好走率 * 50
    """
    if not horse_results:
        return NEUTRAL_SCORE

    all_results = [r for r, _ in horse_results]
    total = len(all_results)
    wins = sum(1 for r in all_results if r.finish_position == 1)
    win_rate = wins / total

    graded = [r for r, race in horse_results if race.grade in ("G1", "G2", "G3")]
    if graded:
        graded_top3 = sum(1 for r in graded if r.finish_position <= 3)
        graded_rate = graded_top3 / len(graded)
    else:
        graded_rate = 0.0

    return _clamp(win_rate * 50.0 + graded_rate * 50.0)
