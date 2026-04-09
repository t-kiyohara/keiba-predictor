import logging
from datetime import date

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models import Race
from app.scoring.engine import ScoringEngine
from app.scrapers.jra import JraScraper, get_target_race_dates
from app.scrapers.netkeiba import NetkeibaScraper
from app.scrapers.weather import WeatherClient
from app.config import settings


class FetchService:
    """データ取得→スコアリングまでの全体オーケストレーション"""

    TOTAL_STEPS = 7

    def __init__(self, db: Session, progress_callback=None):
        self.db = db
        self.progress = progress_callback or (lambda *args, **kwargs: None)
        self.jra = JraScraper()
        self.netkeiba = NetkeibaScraper()
        self.weather = WeatherClient(
            api_key=getattr(settings, "OPENWEATHER_API_KEY", "")
        )

    async def execute(self):
        """全データ取得フローを実行"""
        today = date.today()

        # Step 1: 対象日の決定
        self.progress("日程取得", 1, self.TOTAL_STEPS, "対象レース日を決定中...")
        target_dates = get_target_race_dates(today)

        # Step 2: 重賞レース一覧の取得
        self.progress(
            "レース一覧", 2, self.TOTAL_STEPS, "JRAから重賞レース一覧を取得中..."
        )
        graded_races = await self.jra.fetch_graded_races(target_dates)

        if not graded_races:
            # スクレイパー未実装期間: 既存データでスコアリングのみ実行
            self.progress(
                "レース一覧",
                2,
                self.TOTAL_STEPS,
                "重賞レースが見つかりませんでした（スクレイパー未実装）",
            )
            self.progress(
                "出走馬取得",
                3,
                self.TOTAL_STEPS,
                "スクレイパー未実装のためスキップします",
            )
            self.progress(
                "馬情報取得",
                4,
                self.TOTAL_STEPS,
                "スクレイパー未実装のためスキップします",
            )
            self.progress(
                "成績取得",
                5,
                self.TOTAL_STEPS,
                "スクレイパー未実装のためスキップします",
            )
            self.progress(
                "天気取得",
                6,
                self.TOTAL_STEPS,
                "スクレイパー未実装のためスキップします",
            )
            self.progress(
                "スコアリング",
                7,
                self.TOTAL_STEPS,
                "DBのサンプルデータで予想スコアを算出中...",
            )
            self._score_existing_races()
            return

        # Step 3: 各レースの出走馬取得
        total_races = len(graded_races)
        self.progress(
            "出走馬取得",
            3,
            self.TOTAL_STEPS,
            f"出走馬情報を取得中 (0/{total_races})...",
            estimated_remaining=total_races * 30,
        )
        race_entries_list = []
        for i, race_info in enumerate(graded_races, start=1):
            self.progress(
                "出走馬取得",
                3,
                self.TOTAL_STEPS,
                f"出走馬情報を取得中 ({i}/{total_races})...",
                estimated_remaining=(total_races - i) * 30,
            )
            # netkeiba の race_id が race_info に含まれていれば取得
            race_id = race_info.get("race_id", "")
            if race_id:
                entries_data = await self.netkeiba.fetch_race_entries(race_id)
                if entries_data:
                    race_entries_list.append(entries_data)

        # Step 4: 馬情報取得（将来の実装用プレースホルダー）
        self.progress(
            "馬情報取得",
            4,
            self.TOTAL_STEPS,
            "馬のプロフィールを取得中...",
        )

        # Step 5: 過去成績取得（将来の実装用プレースホルダー）
        self.progress(
            "成績取得",
            5,
            self.TOTAL_STEPS,
            "馬の過去成績を取得中...",
        )

        # Step 6: 天気情報取得（将来の実装用プレースホルダー）
        self.progress(
            "天気取得",
            6,
            self.TOTAL_STEPS,
            "レース当日の天気を取得中...",
        )

        # Step 7: スコアリング
        self.progress(
            "スコアリング", 7, self.TOTAL_STEPS, "予想スコアを算出中..."
        )
        self._score_existing_races()

    def _score_existing_races(self):
        """DBに存在するレースに対してスコアリングを実行"""
        engine = ScoringEngine(self.db)
        races = self.db.query(Race).all()
        for race in races:
            try:
                engine.predict_race(race.id)
            except Exception as e:
                logger.warning("Scoring failed for race %s: %s", race.id, e)
        self.db.commit()
