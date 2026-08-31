"""レース結果（全着順＋払戻）の永続化サービス。

`NetkeibaScraper.fetch_race_result()` の返り値をDBに反映する。
「答え合わせ」(WP6) と「過去5年バックフィル」(WP7) の共通土台。

commit は呼び出し側の責務。この関数は flush までしか行わない。
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Horse, Jockey, Payout, Race, Result, Trainer

logger = logging.getLogger(__name__)

# 既存コード（fetch_service._persist_race_entries / _persist_horse_results,
# seed.py）がFK整合のために作るスタブRaceの既定値。
# これらに一致する値は「信頼できない値」として扱い、結果ページの値で上書きする。
STUB_RACE_NAMES = frozenset({"（未取得）", "（過去レース）"})
STUB_VENUE = "不明"
STUB_COURSE_TYPE = "芝"
STUB_DISTANCE = 2000
STUB_GRADE = "OP"

# レース名にグレード表記がない場合、既存コードは grade を "OP" にする。
# 結果ページから重賞と判明した場合のみ昇格させる。
PROMOTABLE_GRADES = frozenset({"G1", "G2", "G3"})

# Result で「値があるときだけ上書きする」フィールド
_RESULT_UPDATABLE_FIELDS = (
    "finish_position",
    "time",
    "margin",
    "last_3f",
    "horse_number",
    "jockey_name",
    "trainer_name",
)


def _parse_iso_date(date_str: str) -> date | None:
    """"YYYY-MM-DD" 形式の文字列を date に変換する。失敗時は None。"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        logger.warning("レース日付の解析に失敗: %s", date_str)
        return None


def _fallback_race_date(race_id: str) -> date:
    """race_idの年を使った日付フォールバック（既存スクレイパーと同じ 1月1日）。"""
    try:
        return date(int(race_id[:4]), 1, 1)
    except ValueError:
        return date(2024, 1, 1)


def _is_stub_race_date(race_date: date | None) -> bool:
    """Race.date がスタブ由来かを判定する。

    既存コードの日付フォールバックはいずれも1月1日（`{year}-01-01` /
    `date(2024, 1, 1)`）。JRAは1月1日に開催しないため、1月1日は
    スタブ値の目印として使える。

    ponytail: `date.today()` フォールバック（出馬表の日付が解析できなかった場合）
    は区別できないため更新されない。実害が出たら race_id の開催日エンコードから
    判定する。
    """
    return race_date is None or (race_date.month, race_date.day) == (1, 1)


def _apply_race_info(race: Race, race_info: dict) -> None:
    """既存Raceに結果ページの値を反映する（劣化させない上書きのみ）。

    - name/venue/course_type/distance/date: スタブ値のときだけ更新する
    - grade: "OP"（グレード不明）から重賞への昇格のみ行う
    - weather/track_condition: 未設定（None）のときだけ埋める

    いずれも結果ページ側の値が空/0/Noneのときは既存値を残す。
    """
    name = race_info.get("name")
    if name and (not race.name or race.name in STUB_RACE_NAMES):
        race.name = name

    race_date = _parse_iso_date(race_info.get("date", ""))
    if race_date and _is_stub_race_date(race.date):
        race.date = race_date

    venue = race_info.get("venue")
    if venue and (not race.venue or race.venue == STUB_VENUE):
        race.venue = venue

    course_type = race_info.get("course_type")
    if course_type and (not race.course_type or race.course_type == STUB_COURSE_TYPE):
        race.course_type = course_type

    distance = race_info.get("distance")
    if distance and (not race.distance or race.distance == STUB_DISTANCE):
        race.distance = distance

    grade = race_info.get("grade")
    if grade in PROMOTABLE_GRADES and (not race.grade or race.grade == STUB_GRADE):
        race.grade = grade

    weather = race_info.get("weather")
    if weather and race.weather is None:
        race.weather = weather

    track_condition = race_info.get("track_condition")
    if track_condition and race.track_condition is None:
        race.track_condition = track_condition


def _upsert_race(db: Session, race_info: dict) -> Race:
    """Race を取得または作成し、結果ページの値を反映して返す。"""
    race_id = race_info["race_id"]
    race = db.get(Race, race_id)
    if race is None:
        race = Race(
            id=race_id,
            name=race_info.get("name") or "（過去レース）",
            date=(
                _parse_iso_date(race_info.get("date", ""))
                or _fallback_race_date(race_id)
            ),
            venue=race_info.get("venue") or STUB_VENUE,
            course_type=race_info.get("course_type") or STUB_COURSE_TYPE,
            distance=race_info.get("distance") or STUB_DISTANCE,
            grade=race_info.get("grade") or STUB_GRADE,
            weather=race_info.get("weather") or None,
            track_condition=race_info.get("track_condition") or None,
        )
        db.add(race)
    else:
        _apply_race_info(race, race_info)
    db.flush()
    return race


def _ensure_master_row(db: Session, model, entity_id: str, name: str) -> None:
    """Horse/Jockey/Trainer の未知IDに対してnameだけのスタブ行を作る（FK整合）。"""
    if not entity_id:
        return
    if db.get(model, entity_id) is not None:
        return
    db.add(model(id=entity_id, name=name or "（未取得）"))
    db.flush()


def _upsert_result(db: Session, race_id: str, result_data: dict) -> None:
    """Result を (race_id, horse_id) でupsertする（Noneで既存値を潰さない）。"""
    horse_id = result_data.get("horse_id", "")
    if not horse_id:
        return

    result_row = (
        db.query(Result).filter_by(race_id=race_id, horse_id=horse_id).first()
    )
    if result_row is None:
        result_row = Result(race_id=race_id, horse_id=horse_id)
        db.add(result_row)

    for field_name in _RESULT_UPDATABLE_FIELDS:
        value = result_data.get(field_name)
        if value is not None:
            setattr(result_row, field_name, value)


def _replace_payouts(db: Session, race_id: str, payouts: list[dict]) -> None:
    """そのレースの払戻を全削除して入れ直す（何度呼んでも重複しない）。

    先に DELETE を実行してから add する。順序を逆にすると、bulk delete の
    autoflush で新しい行がINSERTされ、その直後のDELETEで消えてしまう。
    """
    db.query(Payout).filter_by(race_id=race_id).delete()

    seen_combinations: set[tuple[str, str]] = set()
    for payout_data in payouts:
        bet_type = payout_data.get("bet_type", "")
        combination = payout_data.get("combination", "")
        amount = payout_data.get("amount")
        if not bet_type or not combination or amount is None:
            continue
        # UniqueConstraint(race_id, bet_type, combination) 違反を防ぐ
        if (bet_type, combination) in seen_combinations:
            continue
        seen_combinations.add((bet_type, combination))
        db.add(
            Payout(
                race_id=race_id,
                bet_type=bet_type,
                combination=combination,
                amount=amount,
            )
        )


def persist_race_result(db: Session, parsed: dict) -> None:
    """`fetch_race_result()` の結果をDBに反映する（commitは呼び出し側の責務）。

    Args:
        db: SQLAlchemyセッション
        parsed: NetkeibaScraper.fetch_race_result() の返り値。
                空dict（取得失敗）の場合は何もしない。
    """
    race_info = parsed.get("race") or {}
    race_id = race_info.get("race_id", "")
    if not race_id:
        logger.warning("race_idが無いためレース結果を保存できません")
        return

    _upsert_race(db, race_info)

    for result_data in parsed.get("results", []):
        _ensure_master_row(
            db,
            Horse,
            result_data.get("horse_id", ""),
            result_data.get("horse_name", ""),
        )
        _ensure_master_row(
            db,
            Jockey,
            result_data.get("jockey_id", ""),
            result_data.get("jockey_name", ""),
        )
        _ensure_master_row(
            db,
            Trainer,
            result_data.get("trainer_id", ""),
            result_data.get("trainer_name", ""),
        )
        _upsert_result(db, race_id, result_data)

    _replace_payouts(db, race_id, parsed.get("payouts", []))
    db.flush()
