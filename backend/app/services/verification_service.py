"""予想の「答え合わせ」(的中率・回収率) を集計するサービス。

ベット規則（確定仕様）:
    各レース、予想1位（◎）に単勝100円 + 複勝100円（1レースの投下 = 200円）。

複勝の的中判定は「◎の馬番が、そのレースの複勝 Payout の combination に
一致する行があるか」で行う。頭数による複勝2着払いの規則は持たず、
Payout に存在する組番を正とする。

検証対象になるレースの条件:
    - 単勝・複勝の Payout が揃っている（= 結果ページを取得済み）
    - 結果ページ由来の Result（finish_position あり）がある
    - `created_at.date() <= race.date` を満たす予想バッチが存在する
    - ◎に着順がある（出走取消なら投下も無かったものとして検証対象外）
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Entry, Horse, Payout, Prediction, Race, Result
from app.scoring.engine import latest_prediction_batch

WIN_BET_TYPE = "単勝"
PLACE_BET_TYPE = "複勝"
BET_AMOUNT = 100  # 1レース1券種あたりの投下額（円）
TOP_PICKS = 3  # top3_in_top_picks で評価する予想上位頭数
_RATE_DIGITS = 3  # 的中率・回収率の丸め桁数


def build_stats(db: Session) -> dict:
    """答え合わせの集計結果を返す（フロントとPages用JSONが読む契約）。

    Returns:
        {"summary": {...}, "cumulative": [...], "rows": [...]}
        対象レースが0件でも同じ形（率は全て 0.0）を返す。
    """
    win_amounts_by_race, place_amounts_by_race = _load_payouts(db)
    race_ids = sorted(win_amounts_by_race.keys() & place_amounts_by_race.keys())
    if not race_ids:
        return {"summary": _summarize([], []), "cumulative": [], "rows": []}

    races_by_id = {
        race.id: race for race in db.query(Race).filter(Race.id.in_(race_ids)).all()
    }
    results_by_race = _load_results(db, race_ids)
    entries_by_race = _load_entries(db, race_ids)
    predictions_by_race, horse_name_by_id = _load_top_predictions(db, race_ids)

    rows: list[dict] = []
    top3_ratios: list[float] = []
    for race_id in race_ids:
        race = races_by_id.get(race_id)
        if race is None:
            continue
        evaluation = _evaluate_race(
            race=race,
            predictions=predictions_by_race.get(race_id, []),
            results_by_horse=results_by_race.get(race_id, {}),
            entries_by_horse=entries_by_race.get(race_id, {}),
            win_amounts=win_amounts_by_race[race_id],
            place_amounts=place_amounts_by_race[race_id],
            horse_name_by_id=horse_name_by_id,
        )
        if evaluation is None:
            continue
        row, top3_ratio = evaluation
        rows.append(row)
        top3_ratios.append(top3_ratio)

    summary = _summarize(rows, top3_ratios)
    cumulative = _build_cumulative(rows)
    # rows は日付降順（同日内は race_id 降順で安定化）
    rows.sort(key=lambda entry: (entry["date"], entry["race_id"]), reverse=True)
    return {"summary": summary, "cumulative": cumulative, "rows": rows}


# ---------------------------------------------------------------------------
# 1レースの評価
# ---------------------------------------------------------------------------


def _evaluate_race(
    race: Race,
    predictions: list[Prediction],
    results_by_horse: dict[str, Result],
    entries_by_horse: dict[str, Entry],
    win_amounts: dict[str, int],
    place_amounts: dict[str, int],
    horse_name_by_id: dict[str, str],
) -> tuple[dict, float] | None:
    """1レースを評価して (rows用の1行, 予想上位3頭の3着内率) を返す。

    検証対象外のレースでは None を返す。
    """
    if not results_by_horse:
        return None  # 結果ページ由来の着順が無い

    batch = latest_prediction_batch(predictions, as_of=race.date)
    if not batch:
        return None  # レース前に出した予想が無い

    pick = batch[0]  # ◎（そのバッチの rank=1）
    pick_result = results_by_horse.get(pick.horse_id)
    if pick_result is None:
        return None  # ◎が出走取消 → 投下も無かったものとして検証対象外

    pick_entry = entries_by_horse.get(pick.horse_id)
    pick_horse_number = (
        pick_entry.horse_number
        if pick_entry is not None and pick_entry.horse_number is not None
        else pick_result.horse_number
    )
    if pick_horse_number is None:
        return None  # 馬番不明では払戻の組番と突合できない
    pick_combination = str(pick_horse_number)

    finish_position = pick_result.finish_position
    win_payout = (
        win_amounts.get(pick_combination, 0) if finish_position == 1 else 0
    )
    place_payout = place_amounts.get(pick_combination, 0)

    top3_hits = 0
    for prediction in batch[:TOP_PICKS]:
        top_pick_result = results_by_horse.get(prediction.horse_id)
        if top_pick_result is not None and top_pick_result.finish_position <= 3:
            top3_hits += 1
    top3_ratio = top3_hits / min(TOP_PICKS, len(results_by_horse))

    row = {
        "date": race.date.isoformat(),
        "race_id": race.id,
        "race_name": race.name,
        "grade": race.grade,
        "venue": race.venue,
        "pick_horse_name": horse_name_by_id.get(pick.horse_id, pick.horse_id),
        "pick_odds": pick_entry.odds if pick_entry is not None else None,
        "finish_position": finish_position,
        "win_payout": win_payout,
        "place_payout": place_payout,
        "net": win_payout + place_payout - BET_AMOUNT * 2,
    }
    return row, top3_ratio


# ---------------------------------------------------------------------------
# 集計
# ---------------------------------------------------------------------------


def _summarize(rows: list[dict], top3_ratios: list[float]) -> dict:
    """的中率・回収率のサマリを組み立てる。

    的中は「払戻が発生したか」で判定する（複勝の的中判定と同じ基準）。
    回収率 = 総払戻 ÷ (100円 × 対象レース数)。
    """
    race_count = len(rows)
    if race_count == 0:
        return {
            "races": 0,
            "win_hit_rate": 0.0,
            "win_roi": 0.0,
            "place_hit_rate": 0.0,
            "place_roi": 0.0,
            "top3_in_top_picks": 0.0,
        }

    total_stake = BET_AMOUNT * race_count
    win_hits = sum(1 for row in rows if row["win_payout"] > 0)
    place_hits = sum(1 for row in rows if row["place_payout"] > 0)
    total_win_payout = sum(row["win_payout"] for row in rows)
    total_place_payout = sum(row["place_payout"] for row in rows)
    return {
        "races": race_count,
        "win_hit_rate": round(win_hits / race_count, _RATE_DIGITS),
        "win_roi": round(total_win_payout / total_stake, _RATE_DIGITS),
        "place_hit_rate": round(place_hits / race_count, _RATE_DIGITS),
        "place_roi": round(total_place_payout / total_stake, _RATE_DIGITS),
        "top3_in_top_picks": round(sum(top3_ratios) / race_count, _RATE_DIGITS),
    }


def _build_cumulative(rows: list[dict]) -> list[dict]:
    """券種別の累計収支を date 昇順・同日内 race_id 昇順で積み上げる。"""
    balance_win = 0
    balance_place = 0
    cumulative: list[dict] = []
    for row in sorted(rows, key=lambda entry: (entry["date"], entry["race_id"])):
        balance_win += row["win_payout"] - BET_AMOUNT
        balance_place += row["place_payout"] - BET_AMOUNT
        cumulative.append({
            "date": row["date"],
            "race_id": row["race_id"],
            "balance_win": balance_win,
            "balance_place": balance_place,
        })
    return cumulative


# ---------------------------------------------------------------------------
# プリロードヘルパー（engine.predict_race と同じくN+1を避ける）
# ---------------------------------------------------------------------------


def _load_payouts(
    db: Session,
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    """単勝・複勝の払戻を race_id → {組番: 払戻金} で返す。"""
    win_amounts_by_race: dict[str, dict[str, int]] = defaultdict(dict)
    place_amounts_by_race: dict[str, dict[str, int]] = defaultdict(dict)
    rows = (
        db.query(Payout.race_id, Payout.bet_type, Payout.combination, Payout.amount)
        .filter(Payout.bet_type.in_((WIN_BET_TYPE, PLACE_BET_TYPE)))
        .all()
    )
    for race_id, bet_type, combination, amount in rows:
        target = (
            win_amounts_by_race if bet_type == WIN_BET_TYPE else place_amounts_by_race
        )
        target[race_id][combination] = amount
    return dict(win_amounts_by_race), dict(place_amounts_by_race)


def _load_results(
    db: Session, race_ids: list[str]
) -> dict[str, dict[str, Result]]:
    """着順のある Result を race_id → {horse_id: Result} で返す。"""
    results_by_race: dict[str, dict[str, Result]] = defaultdict(dict)
    rows = (
        db.query(Result)
        .filter(Result.race_id.in_(race_ids))
        .filter(Result.finish_position.isnot(None))
        .all()
    )
    for result in rows:
        results_by_race[result.race_id][result.horse_id] = result
    return dict(results_by_race)


def _load_entries(db: Session, race_ids: list[str]) -> dict[str, dict[str, Entry]]:
    """Entry を race_id → {horse_id: Entry} で返す（馬番とオッズの取得元）。"""
    entries_by_race: dict[str, dict[str, Entry]] = defaultdict(dict)
    rows = db.query(Entry).filter(Entry.race_id.in_(race_ids)).all()
    for entry in rows:
        entries_by_race[entry.race_id][entry.horse_id] = entry
    return dict(entries_by_race)


def _load_top_predictions(
    db: Session, race_ids: list[str]
) -> tuple[dict[str, list[Prediction]], dict[str, str]]:
    """上位 TOP_PICKS 頭の予想を race_id ごとに、併せて馬名を返す。

    バッチ選定は Python 側（latest_prediction_batch）で行うため、
    全バッチ分の上位行をまとめて読む。
    """
    predictions_by_race: dict[str, list[Prediction]] = defaultdict(list)
    horse_name_by_id: dict[str, str] = {}
    rows = (
        db.query(Prediction, Horse.name)
        .join(Horse, Prediction.horse_id == Horse.id)
        .filter(Prediction.race_id.in_(race_ids))
        .filter(Prediction.rank <= TOP_PICKS)
        .all()
    )
    for prediction, horse_name in rows:
        predictions_by_race[prediction.race_id].append(prediction)
        horse_name_by_id[prediction.horse_id] = horse_name
    return dict(predictions_by_race), horse_name_by_id
