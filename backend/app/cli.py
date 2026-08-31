"""GitHub Actions から叩くCLI（FastAPIには依存しない）。

    python -m app.cli fetch                        週次の重賞データ取得＋予想生成
    python -m app.cli verify [--days 8]            確定したレース結果を取得
    python -m app.cli backfill --years 5           過去のJRA重賞の結果を一括収集
    python -m app.cli backfill --from 2021 --to 2026
    python -m app.cli export --out ../frontend/public/data

進捗は logger（INFO）で stdout に出す。終了コードは 0=成功 / 1=失敗。
verify・backfill の個別レースの失敗は WARNING でスキップして続行し、
1件も保存できなかった場合だけ 1 を返す（スクレイパー崩壊の検知用）。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

from app.database import SessionLocal, init_db
from app.scrapers.netkeiba import NetkeibaScraper
from app.services.collection_service import (
    backfill_race_results,
    verify_race_results,
)
from app.services.export_service import export_static_json
from app.services.fetch_service import FetchService

logger = logging.getLogger("app.cli")

DEFAULT_VERIFY_DAYS = 8
DEFAULT_BACKFILL_YEARS = 5
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def _log_progress(
    step: str,
    current: int,
    total: int,
    message: str,
    estimated_remaining: int | None = None,
) -> None:
    """FetchService の進捗コールバックをログ出力に変換する。"""
    logger.info("[%d/%d] %s: %s", current, total, step, message)


# ---------------------------------------------------------------------------
# サブコマンド
# ---------------------------------------------------------------------------


async def _run_fetch(db) -> int:
    await FetchService(db, progress_callback=_log_progress).execute()
    logger.info("フェッチ完了")
    return 0


async def _run_verify(db, days: int) -> int:
    saved_count, failed_count = await verify_race_results(
        db, NetkeibaScraper(), days
    )
    return _report_collection("答え合わせ", saved_count, failed_count)


async def _run_backfill(db, start_year: int, end_year: int) -> int:
    saved_count, failed_count = await backfill_race_results(
        db, NetkeibaScraper(), start_year, end_year
    )
    return _report_collection("バックフィル", saved_count, failed_count)


def _run_export(db, out_dir: Path) -> int:
    counts = export_static_json(db, out_dir)
    logger.info(
        "エクスポート完了: レース%d件 / 馬%d件", counts["races"], counts["horses"]
    )
    return 0


def _report_collection(label: str, saved_count: int, failed_count: int) -> int:
    logger.info("%s完了: 保存%d件 / 失敗%d件", label, saved_count, failed_count)
    if failed_count and not saved_count:
        logger.error("%s: 対象レースを1件も保存できませんでした", label)
        return 1
    return 0


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="重賞予想データのバッチ処理（fetch / verify / backfill / export）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("fetch", help="週末の重賞データを取得して予想を生成する")

    verify_parser = subparsers.add_parser(
        "verify", help="確定したレース結果と払戻を取得して答え合わせを可能にする"
    )
    verify_parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_VERIFY_DAYS,
        help=f"何日前まで遡るか（既定: {DEFAULT_VERIFY_DAYS}）",
    )

    backfill_parser = subparsers.add_parser(
        "backfill", help="過去のJRA重賞の結果を一括収集する（取得済みはスキップ）"
    )
    backfill_parser.add_argument(
        "--years",
        type=int,
        default=DEFAULT_BACKFILL_YEARS,
        help=(
            "今年から遡る年数（既定: "
            f"{DEFAULT_BACKFILL_YEARS}。2026年に --years 5 なら 2021〜2026年）"
        ),
    )
    backfill_parser.add_argument(
        "--from", dest="from_year", type=int, help="開始年（--years より優先）"
    )
    backfill_parser.add_argument(
        "--to", dest="to_year", type=int, help="終了年（既定: 今年）"
    )

    export_parser = subparsers.add_parser(
        "export", help="DBから静的JSONを書き出す"
    )
    export_parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="出力先ディレクトリ（書き出し前に中身を空にする）",
    )

    return parser


def _backfill_years(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> tuple[int, int]:
    """--years / --from / --to から対象期間（両端含む）を決める。"""
    end_year = args.to_year if args.to_year is not None else date.today().year
    start_year = (
        args.from_year if args.from_year is not None else end_year - args.years
    )
    if start_year > end_year:
        parser.error(f"開始年({start_year})が終了年({end_year})より後です")
    return start_year, end_year


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format=LOG_FORMAT)

    init_db()
    db = SessionLocal()
    try:
        if args.command == "fetch":
            return asyncio.run(_run_fetch(db))
        if args.command == "verify":
            if args.days < 1:
                parser.error("--days は1以上を指定してください")
            return asyncio.run(_run_verify(db, args.days))
        if args.command == "backfill":
            start_year, end_year = _backfill_years(parser, args)
            return asyncio.run(_run_backfill(db, start_year, end_year))
        if args.command == "export":
            return _run_export(db, args.out)
        parser.error(f"不明なコマンド: {args.command}")
    except Exception:
        logger.exception("コマンドが失敗しました: %s", args.command)
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
