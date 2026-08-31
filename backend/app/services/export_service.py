"""DBから静的JSON（GitHub Pages 配信用）を書き出すサービス。

フロントの静的モード（`frontend/src/api/staticRoutes.ts`）が読む
ファイル構成をそのまま生成する:

    meta.json                 生成時刻とレース件数
    races.json                予想を持つ全レース（date降順）
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

from app.models import Entry, Horse, Jockey, Prediction, Race, Result
from app.scoring.engine import latest_prediction_batch
from app.services.verification_service import build_stats

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# SQLite のバインドパラメータ上限（既定999）を踏まないためのIN句分割サイズ
_QUERY_CHUNK_SIZE = 500

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
    races = _load_predicted_races(db)
    race_ids = [race.id for race in races]
    batch_by_race = _load_latest_batches(db, race_ids)
    entries_by_race = _load_entries(db, race_ids)

    horse_ids = sorted(
        {entry.horse_id for entries in entries_by_race.values() for entry in entries}
        | {
            prediction.horse_id
            for batch in batch_by_race.values()
            for prediction in batch
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
        top_pick = (
            {
                "horse_id": predictions[0]["horse_id"],
                "horse_name": predictions[0]["horse_name"],
                "total_score": predictions[0]["total_score"],
            }
            if predictions
            else None
        )
        race_payload = _race_payload(race, top_pick)
        race_payloads.append(race_payload)

        if _is_safe_file_id(race.id, "race_id"):
            _write_json(
                races_dir / f"{race.id}.json",
                {
                    "race": race_payload,
                    "predictions": predictions,
                    "entries": [
                        _entry_payload(entry, horse_by_id, jockey_name_by_id, race.date)
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


def _race_payload(race: Race, top_pick: dict | None) -> dict:
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
    }


def _entry_payload(
    entry: Entry,
    horse_by_id: dict[str, Horse],
    jockey_name_by_id: dict[str, str],
    race_date: date,
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


def _load_predicted_races(db: Session) -> list[Race]:
    """予想を持つレースを date 降順（同日内は race_id 降順）で返す。"""
    return (
        db.query(Race)
        .filter(Race.predictions.any())
        .order_by(Race.date.desc(), Race.id.desc())
        .all()
    )


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
