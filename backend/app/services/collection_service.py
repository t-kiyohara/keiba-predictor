"""レース結果の一括収集（CLI の verify / backfill の共通土台）。

`NetkeibaScraper.fetch_race_result()` → `persist_race_result()` を
1レースずつ commit しながら回す。途中で失敗しても取得済みの蓄積は残るため、
同じコマンドを再実行すれば未取得分だけを追いかけられる。

「取得済み」の判定は Payout の有無で行う（結果ページを取得できたレースは
必ず払戻を持つ）。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Payout, Race
from app.scrapers.netkeiba import NetkeibaScraper
from app.services.results_service import persist_race_result

logger = logging.getLogger(__name__)

PROGRESS_INTERVAL = 10  # 進捗ログを出す件数間隔


# ---------------------------------------------------------------------------
# 対象選定
# ---------------------------------------------------------------------------


def select_verify_targets(db: Session, days: int) -> list[str]:
    """答え合わせ待ちのレースIDを返す（日付昇順）。

    条件は次の3つすべて:
        - 予想（Prediction）を持つ = 答え合わせの対象になりうる
        - race.date が「days日前」から「昨日」までの範囲にある
        - 払戻（Payout）が未取得

    Args:
        db: SQLAlchemyセッション
        days: 何日前まで遡るか（両端含む）
    """
    today = date.today()
    since = today - timedelta(days=days)
    until = today - timedelta(days=1)
    races = (
        db.query(Race)
        .filter(Race.date >= since, Race.date <= until)
        .filter(Race.predictions.any())
        .filter(~Race.payouts.any())
        .order_by(Race.date, Race.id)
        .all()
    )
    return [race.id for race in races]


def select_uncollected_race_ids(db: Session, race_ids: list[str]) -> list[str]:
    """払戻を既に持つレースIDを除いて返す（順序は入力のまま）。

    バックフィルの再実行・中断再開を成立させるスキップ規則。
    `race_ids` は数百〜数千件になるため IN 句は使わず、収集済みIDを
    まとめて1回で引いて差集合を取る（バインドパラメータ上限を踏まない）。
    """
    collected_race_ids = {
        race_id for (race_id,) in db.query(Payout.race_id).distinct().all()
    }
    return [race_id for race_id in race_ids if race_id not in collected_race_ids]


# ---------------------------------------------------------------------------
# 収集ループ
# ---------------------------------------------------------------------------


async def _collect_one(
    db: Session, scraper: NetkeibaScraper, race_id: str
) -> bool:
    """1レースの結果を取得・保存してcommitする。成功したらTrue。"""
    try:
        parsed = await scraper.fetch_race_result(race_id)
        if not parsed:
            logger.warning("レース結果を取得できませんでした: %s", race_id)
            return False
        persist_race_result(db, parsed)
        db.commit()
        return True
    except Exception as e:
        # 個別失敗で全体を止めない。未保存の変更は捨てて次のレースへ進む
        db.rollback()
        logger.warning("レース結果の保存に失敗しました (%s): %s", race_id, e)
        return False


async def collect_race_results(
    db: Session, scraper: NetkeibaScraper, race_ids: list[str]
) -> tuple[int, int]:
    """race_idのリストを順に取得・保存する（1レースごとにcommit）。

    Returns:
        (成功件数, 失敗件数)
    """
    total = len(race_ids)
    saved_count = 0
    failed_count = 0
    for processed_count, race_id in enumerate(race_ids, start=1):
        if await _collect_one(db, scraper, race_id):
            saved_count += 1
        else:
            failed_count += 1
        if processed_count % PROGRESS_INTERVAL == 0 or processed_count == total:
            logger.info("%d/%d 完了", processed_count, total)
    return saved_count, failed_count


# ---------------------------------------------------------------------------
# CLIサブコマンドの本体
# ---------------------------------------------------------------------------


async def verify_race_results(
    db: Session, scraper: NetkeibaScraper, days: int
) -> tuple[int, int]:
    """予想済み・結果未取得のレースを答え合わせ用に埋める。

    Returns:
        (成功件数, 失敗件数)。対象0件なら (0, 0)。
    """
    race_ids = select_verify_targets(db, days)
    logger.info("答え合わせ対象: %d件（過去%d日）", len(race_ids), days)
    if not race_ids:
        return 0, 0
    return await collect_race_results(db, scraper, race_ids)


async def backfill_race_results(
    db: Session, scraper: NetkeibaScraper, start_year: int, end_year: int
) -> tuple[int, int]:
    """指定期間のJRA重賞の結果を一括収集する（取得済みはスキップ）。

    Returns:
        (成功件数, 失敗件数)。対象0件なら (0, 0)。
    """
    all_race_ids = await scraper.fetch_graded_race_ids(start_year, end_year)
    race_ids = select_uncollected_race_ids(db, all_race_ids)
    logger.info(
        "重賞 %d件のうち未取得は %d件（%d〜%d年）",
        len(all_race_ids),
        len(race_ids),
        start_year,
        end_year,
    )
    if not race_ids:
        return 0, 0
    return await collect_race_results(db, scraper, race_ids)
