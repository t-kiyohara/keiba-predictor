"""DBから静的JSON（GitHub Pages 配信用）を書き出すサービス。

フロントの静的モード（`frontend/src/api/staticRoutes.ts`）が読む
ファイル構成をそのまま生成する:

    meta.json                 生成時刻とレース件数
    races.json                予想または結果を持つ全レース（date降順）
    races/{race_id}.json      レース + 最新予想バッチ + 出走馬
    horses/{horse_id}.json    馬 + 過去成績（date降順）
    stats.json                答え合わせ集計（verification_service.build_stats）

読み取り専用（commitしない）。JSONは ensure_ascii=False / UTF-8。
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from collections import defaultdict
from collections.abc import Iterator, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Entry, Horse, Jockey, Payout, Prediction, Race, Result
from app.scoring.engine import latest_prediction_batch
from app.services.verification_service import (
    PLACE_BET_TYPE,
    WIN_BET_TYPE,
    build_stats,
)

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# SQLite のバインドパラメータ上限（既定999）を踏まないためのIN句分割サイズ
_QUERY_CHUNK_SIZE = 500

# races.json に載せる着順の件数（一覧の軽量化。詳細JSONは全着順を持つ）
_RACES_JSON_RESULT_LIMIT = 3

# entries の recent_finishes に載せる過去成績の件数
_RECENT_FINISH_LIMIT = 5

# ファイル名に使うID。netkeiba由来の外部文字列なのでパス要素として検証する
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def export_static_json(db: Session, out_dir: Path) -> dict[str, int]:
    """静的JSONを `out_dir` に書き出す。

    Args:
        db: SQLAlchemyセッション
        out_dir: 出力先ディレクトリ。書き出し前に中身を空にする

    Returns:
        {"races": レース件数, "horses": 馬件数}
    """
    races = _load_published_races(db)
    race_ids = [race.id for race in races]
    batch_by_race = _load_latest_batches(db, race_ids)
    entries_by_race = _load_entries(db, race_ids)
    results_by_race = _load_race_results(db, race_ids)
    payouts_by_race = _load_win_place_payouts(db, race_ids)

    horse_ids = sorted(
        {entry.horse_id for entries in entries_by_race.values() for entry in entries}
        | {
            prediction.horse_id
            for batch in batch_by_race.values()
            for prediction in batch
        }
        | {
            result.horse_id
            for results in results_by_race.values()
            for result in results
        }
    )
    horse_by_id = _load_horses(db, horse_ids)
    jockey_name_by_id = _load_jockey_names(
        db,
        sorted(
            {
                entry.jockey_id
                for entries in entries_by_race.values()
                for entry in entries
                if entry.jockey_id
            }
        ),
    )
    results_by_horse = _load_results(db, horse_ids)

    _reset_output_dir(out_dir)
    races_dir = out_dir / "races"
    horses_dir = out_dir / "horses"
    races_dir.mkdir()
    horses_dir.mkdir()

    race_payloads: list[dict] = []
    for race in races:
        batch = batch_by_race.get(race.id, [])
        predictions = [
            {
                "rank": prediction.rank,
                "horse_id": prediction.horse_id,
                "horse_name": _horse_name(horse_by_id, prediction.horse_id),
                "total_score": prediction.total_score,
                "factor_scores": prediction.score_details or {},
            }
            for prediction in batch
        ]
        result_payloads = [
            _race_result_payload(result, horse_by_id)
            for result in results_by_race.get(race.id, [])
        ]
        finish_position_by_horse = {
            result["horse_id"]: result["finish_position"]
            for result in result_payloads
        }
        top_pick = (
            {
                "horse_id": predictions[0]["horse_id"],
                "horse_name": predictions[0]["horse_name"],
                "total_score": predictions[0]["total_score"],
                "finish_position": finish_position_by_horse.get(
                    predictions[0]["horse_id"]
                ),
            }
            if predictions
            else None
        )
        payouts = payouts_by_race.get(race.id)
        race_payloads.append(
            _race_payload(
                race,
                top_pick,
                result_payloads[:_RACES_JSON_RESULT_LIMIT],
                payouts,
            )
        )

        if _is_safe_file_id(race.id, "race_id"):
            _write_json(
                races_dir / f"{race.id}.json",
                {
                    # 詳細JSONは全着順を載せる（races.json は上位のみ）
                    "race": _race_payload(race, top_pick, result_payloads, payouts),
                    "predictions": predictions,
                    "entries": [
                        _entry_payload(
                            entry,
                            horse_by_id,
                            jockey_name_by_id,
                            race.date,
                            _recent_finishes(
                                results_by_horse, entry.horse_id, race.date
                            ),
                        )
                        for entry in _sorted_entries(entries_by_race.get(race.id, []))
                    ],
                },
            )

    for horse_id in horse_ids:
        horse = horse_by_id.get(horse_id)
        if horse is None or not _is_safe_file_id(horse_id, "horse_id"):
            continue
        _write_json(
            horses_dir / f"{horse_id}.json",
            {
                "horse": _horse_payload(horse),
                "results": [
                    _result_payload(result, race)
                    for result, race in results_by_horse.get(horse_id, [])
                ],
            },
        )

    _write_json(out_dir / "races.json", race_payloads)
    _write_json(out_dir / "stats.json", build_stats(db))
    _write_json(
        out_dir / "meta.json",
        {
            "generated_at": datetime.now(JST).replace(microsecond=0).isoformat(),
            "race_count": len(race_payloads),
        },
    )

    logger.info(
        "静的JSONを書き出しました: レース%d件 / 馬%d件 → %s",
        len(race_payloads),
        len(horse_by_id),
        out_dir,
    )
    return {"races": len(race_payloads), "horses": len(horse_by_id)}


# ---------------------------------------------------------------------------
# ペイロード組み立て
# ---------------------------------------------------------------------------


def _race_payload(
    race: Race,
    top_pick: dict | None,
    results: list[dict],
    payouts: dict | None,
) -> dict:
    return {
        "id": race.id,
        "name": race.name,
        "date": race.date.isoformat(),
        "venue": race.venue,
        "grade": race.grade,
        "course_type": race.course_type,
        "distance": race.distance,
        "weather": race.weather,
        "track_condition": race.track_condition,
        "top_pick": top_pick,
        "results": results,
        "payouts": payouts,
    }


def _race_result_payload(result: Result, horse_by_id: dict[str, Horse]) -> dict:
    """レースの着順1行（結果表用）。"""
    return {
        "horse_id": result.horse_id,
        "horse_name": _horse_name(horse_by_id, result.horse_id),
        "horse_number": result.horse_number,
        "finish_position": result.finish_position,
        "jockey_name": result.jockey_name,
        "time": result.time,
        "margin": result.margin,
        "last_3f": result.last_3f,
    }


def _entry_payload(
    entry: Entry,
    horse_by_id: dict[str, Horse],
    jockey_name_by_id: dict[str, str],
    race_date: date,
    recent_finishes: Sequence[int] = (),
) -> dict:
    horse = horse_by_id.get(entry.horse_id)
    return {
        "horse_id": entry.horse_id,
        "horse_number": entry.horse_number,
        "post_position": entry.post_position,
        "weight": entry.weight,
        "odds": entry.odds,
        "jockey_name": jockey_name_by_id.get(entry.jockey_id or ""),
        "sex": horse.sex if horse else None,
        "age": _horse_age(horse, race_date),
        "recent_finishes": list(recent_finishes),
    }


def _horse_payload(horse: Horse) -> dict:
    return {
        "id": horse.id,
        "name": horse.name,
        "sex": horse.sex,
        "birthday": horse.birthday.isoformat() if horse.birthday else None,
        "sire": horse.sire,
        "dam": horse.dam,
        "dam_sire": horse.dam_sire,
    }


def _result_payload(result: Result, race: Race) -> dict:
    return {
        "date": race.date.isoformat(),
        "race_id": result.race_id,
        "race_name": race.name,
        "venue": race.venue,
        "grade": race.grade,
        "distance": race.distance,
        "course_type": race.course_type,
        "track_condition": race.track_condition,
        "finish_position": result.finish_position,
        "time": result.time,
        "margin": result.margin,
        "last_3f": result.last_3f,
        "jockey_name": result.jockey_name,
    }


def _horse_age(horse: Horse | None, race_date: date) -> int | None:
    """日本の競走馬の年齢（レース年 − 生年）。生年不明ならNone。"""
    if horse is None or horse.birthday is None:
        return None
    return race_date.year - horse.birthday.year


def _recent_finishes(
    results_by_horse: dict[str, list[tuple[Result, Race]]],
    horse_id: str,
    race_date: date,
) -> list[int]:
    """対象レースより前の着順を新しい順に最大 _RECENT_FINISH_LIMIT 件返す。

    `_load_results()` が date 降順で読んだリストを前提にする。
    """
    finishes: list[int] = []
    for result, past_race in results_by_horse.get(horse_id, []):
        if past_race.date >= race_date or result.finish_position is None:
            continue
        finishes.append(result.finish_position)
        if len(finishes) == _RECENT_FINISH_LIMIT:
            break
    return finishes


def _horse_name(horse_by_id: dict[str, Horse], horse_id: str) -> str:
    horse = horse_by_id.get(horse_id)
    return horse.name if horse else horse_id


def _sorted_entries(entries: Sequence[Entry]) -> list[Entry]:
    """馬番昇順（馬番なしは末尾）に並べる。"""
    return sorted(
        entries,
        key=lambda entry: (
            entry.horse_number is None,
            entry.horse_number or 0,
            entry.horse_id,
        ),
    )


# ---------------------------------------------------------------------------
# ファイル出力
# ---------------------------------------------------------------------------


def _reset_output_dir(out_dir: Path) -> None:
    """出力先の中身を空にする（ディレクトリ自体は消さない）。

    バインドマウントされたディレクトリを壊さないため、`out_dir` ではなく
    その子要素を消す。誤って作業ツリーを指した場合の事故を防ぐため、
    リポジトリルート（.git を含むディレクトリ）は拒否する。
    """
    if (out_dir / ".git").exists():
        raise ValueError(f"リポジトリルートは出力先にできません: {out_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    for child in out_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _is_safe_file_id(entity_id: str, label: str) -> bool:
    """IDがファイル名として安全か（netkeiba由来の文字列を素で使わない）。"""
    if _SAFE_ID_PATTERN.match(entity_id):
        return True
    logger.warning("ファイル名に使えない%sをスキップしました: %r", label, entity_id)
    return False


# ---------------------------------------------------------------------------
# プリロードヘルパー（engine.predict_race と同じくN+1を避ける）
# ---------------------------------------------------------------------------


def _chunks(items: Sequence[str]) -> Iterator[Sequence[str]]:
    for offset in range(0, len(items), _QUERY_CHUNK_SIZE):
        yield items[offset : offset + _QUERY_CHUNK_SIZE]


def _load_published_races(db: Session) -> list[Race]:
    """予想または払戻を持つレースを date 降順（同日内は race_id 降順）で返す。

    払戻の有無を「結果を収集済み」の判定に使う（collection_service と同じ基準）。
    fetch が外部キーのために作る Result だけのスタブレースは載せない。
    """
    return (
        db.query(Race)
        .filter(Race.predictions.any() | Race.payouts.any())
        .order_by(Race.date.desc(), Race.id.desc())
        .all()
    )


def _load_race_results(db: Session, race_ids: Sequence[str]) -> dict[str, list[Result]]:
    """レースごとの着順確定 Result を finish_position 昇順で返す。"""
    results_by_race: dict[str, list[Result]] = defaultdict(list)
    for chunk in _chunks(race_ids):
        rows = (
            db.query(Result)
            .filter(Result.race_id.in_(chunk))
            .filter(Result.finish_position.isnot(None))
            .order_by(Result.finish_position)
            .all()
        )
        for result in rows:
            results_by_race[result.race_id].append(result)
    return dict(results_by_race)


def _load_win_place_payouts(db: Session, race_ids: Sequence[str]) -> dict[str, dict]:
    """レースごとの単勝・複勝払戻を返す。

    Returns:
        race_id → {"win": 単勝払戻 | None, "place": {組番: 複勝払戻}}。
        単勝・複勝の払戻行が1件も無いレースはキーを持たない（= 結果未収集）。
    """
    win_amounts_by_race: dict[str, dict[str, int]] = defaultdict(dict)
    place_amounts_by_race: dict[str, dict[str, int]] = defaultdict(dict)
    for chunk in _chunks(race_ids):
        rows = (
            db.query(
                Payout.race_id, Payout.bet_type, Payout.combination, Payout.amount
            )
            .filter(Payout.race_id.in_(chunk))
            .filter(Payout.bet_type.in_((WIN_BET_TYPE, PLACE_BET_TYPE)))
            .all()
        )
        for race_id, bet_type, combination, amount in rows:
            amounts_by_combination = (
                win_amounts_by_race
                if bet_type == WIN_BET_TYPE
                else place_amounts_by_race
            )
            amounts_by_combination[race_id][combination] = amount

    payouts_by_race: dict[str, dict] = {}
    for race_id in win_amounts_by_race.keys() | place_amounts_by_race.keys():
        win_amounts = win_amounts_by_race.get(race_id, {})
        payouts_by_race[race_id] = {
            # 同着で単勝が複数行ある場合は組番の昇順で最初の1件を採る
            "win": win_amounts[min(win_amounts)] if win_amounts else None,
            "place": place_amounts_by_race.get(race_id, {}),
        }
    return payouts_by_race


def _load_latest_batches(
    db: Session, race_ids: Sequence[str]
) -> dict[str, list[Prediction]]:
    """レースごとの最新予想バッチ（rank昇順）を返す。"""
    predictions_by_race: dict[str, list[Prediction]] = defaultdict(list)
    for chunk in _chunks(race_ids):
        rows = db.query(Prediction).filter(Prediction.race_id.in_(chunk)).all()
        for prediction in rows:
            predictions_by_race[prediction.race_id].append(prediction)
    return {
        race_id: latest_prediction_batch(predictions)
        for race_id, predictions in predictions_by_race.items()
    }


def _load_entries(db: Session, race_ids: Sequence[str]) -> dict[str, list[Entry]]:
    entries_by_race: dict[str, list[Entry]] = defaultdict(list)
    for chunk in _chunks(race_ids):
        for entry in db.query(Entry).filter(Entry.race_id.in_(chunk)).all():
            entries_by_race[entry.race_id].append(entry)
    return dict(entries_by_race)


def _load_horses(db: Session, horse_ids: Sequence[str]) -> dict[str, Horse]:
    horse_by_id: dict[str, Horse] = {}
    for chunk in _chunks(horse_ids):
        for horse in db.query(Horse).filter(Horse.id.in_(chunk)).all():
            horse_by_id[horse.id] = horse
    return horse_by_id


def _load_jockey_names(db: Session, jockey_ids: Sequence[str]) -> dict[str, str]:
    jockey_name_by_id: dict[str, str] = {}
    for chunk in _chunks(jockey_ids):
        rows = db.query(Jockey.id, Jockey.name).filter(Jockey.id.in_(chunk)).all()
        for jockey_id, jockey_name in rows:
            jockey_name_by_id[jockey_id] = jockey_name
    return jockey_name_by_id


def _load_results(
    db: Session, horse_ids: Sequence[str]
) -> dict[str, list[tuple[Result, Race]]]:
    """馬ごとの過去成績を date 降順（同日内は race_id 降順）で返す。"""
    results_by_horse: dict[str, list[tuple[Result, Race]]] = defaultdict(list)
    for chunk in _chunks(horse_ids):
        rows = (
            db.query(Result, Race)
            .join(Race, Result.race_id == Race.id)
            .filter(Result.horse_id.in_(chunk))
            .order_by(Race.date.desc(), Race.id.desc())
            .all()
        )
        for result, race in rows:
            results_by_horse[result.horse_id].append((result, race))
    return dict(results_by_horse)
