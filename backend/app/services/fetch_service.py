from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Entry, Horse, Jockey, Race, Result, Trainer
from app.scoring.engine import ScoringEngine
from app.scrapers.jra import JraScraper, get_target_race_dates
from app.scrapers.netkeiba import NetkeibaScraper
from app.scrapers.weather import WeatherClient

logger = logging.getLogger(__name__)


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

        # Step 2b: netkeibaからrace_id一覧を取得してgraded_racesに紐付ける
        netkeiba_race_map: dict[str, list[dict]] = {}
        for target_date in target_dates:
            nb_list = await self.netkeiba.fetch_race_list_by_date(target_date)
            date_str = target_date.isoformat()
            netkeiba_race_map[date_str] = nb_list

        # JRAの重賞データとnetkeibaのrace_idをマッチング（race_numberで突合）
        for gr in graded_races:
            race_date = gr.get("date")
            race_number = gr.get("race_number", 11)
            if not race_date:
                continue
            date_str = (
                race_date.isoformat() if isinstance(race_date, date) else race_date
            )
            nb_races = netkeiba_race_map.get(date_str, [])
            for nb_race in nb_races:
                if nb_race.get("race_number") == race_number:
                    gr["race_id"] = nb_race["race_id"]
                    break

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

        # Step 3: 各レースの出走馬取得とDB保存
        total_races = len(graded_races)
        self.progress(
            "出走馬取得",
            3,
            self.TOTAL_STEPS,
            f"出走馬情報を取得中 (0/{total_races})...",
            estimated_remaining=total_races * 30,
        )
        race_entries_list = []
        all_horse_ids: list[str] = []
        all_venues: list[str] = []

        for i, race_info in enumerate(graded_races, start=1):
            self.progress(
                "出走馬取得",
                3,
                self.TOTAL_STEPS,
                f"出走馬情報を取得中 ({i}/{total_races})...",
                estimated_remaining=(total_races - i) * 30,
            )
            race_id = race_info.get("race_id", "")
            if race_id:
                entries_data = await self.netkeiba.fetch_race_entries(race_id)
                if entries_data:
                    # graded_racesのデータでrace_infoを補完
                    ri = entries_data.get("race_info", {})
                    if not ri.get("name"):
                        ri["name"] = race_info.get("name", "")
                    if not ri.get("grade"):
                        ri["grade"] = race_info.get("grade", "")
                    if not ri.get("venue"):
                        ri["venue"] = race_info.get("venue", "")
                    race_entries_list.append(entries_data)
                    self._persist_race_entries(entries_data)
                    # 全馬IDを収集
                    for entry in entries_data.get("entries", []):
                        hid = entry.get("horse_id", "")
                        if hid and hid not in all_horse_ids:
                            all_horse_ids.append(hid)
                    # 会場を収集
                    venue = ri.get("venue", "")
                    if venue and venue not in all_venues:
                        all_venues.append(venue)

        # Step 4: 馬プロフィール取得とDB保存
        total_horses = len(all_horse_ids)
        self.progress(
            "馬情報取得",
            4,
            self.TOTAL_STEPS,
            f"馬のプロフィールを取得中 (0/{total_horses})...",
        )
        for j, horse_id in enumerate(all_horse_ids, start=1):
            self.progress(
                "馬情報取得",
                4,
                self.TOTAL_STEPS,
                f"馬のプロフィールを取得中 ({j}/{total_horses})...",
            )
            profile = await self.netkeiba.fetch_horse_profile(horse_id)
            if profile:
                self._persist_horse_profile(profile)

        # Step 5: 過去成績取得とDB保存
        self.progress(
            "成績取得",
            5,
            self.TOTAL_STEPS,
            f"馬の過去成績を取得中 (0/{total_horses})...",
        )
        for k, horse_id in enumerate(all_horse_ids, start=1):
            self.progress(
                "成績取得",
                5,
                self.TOTAL_STEPS,
                f"馬の過去成績を取得中 ({k}/{total_horses})...",
            )
            results = await self.netkeiba.fetch_horse_results(horse_id)
            if results:
                self._persist_horse_results(horse_id, results)

        # Step 6: 天気情報取得とRace.weather更新
        self.progress(
            "天気取得",
            6,
            self.TOTAL_STEPS,
            "レース当日の天気を取得中...",
        )
        for entries_data in race_entries_list:
            ri = entries_data.get("race_info", {})
            race_id = ri.get("race_id", "")
            venue = ri.get("venue", "")
            if race_id and venue:
                weather_info = await self.weather.get_weather(venue)
                race = self.db.get(Race, race_id)
                if race and weather_info:
                    race.weather = weather_info.get("weather", "")
                    self.db.flush()

        # Step 7: スコアリング
        self.progress(
            "スコアリング", 7, self.TOTAL_STEPS, "予想スコアを算出中..."
        )
        self._score_existing_races()

    def _persist_race_entries(self, entries_data: dict) -> None:
        """出馬表データをDBに保存する（Race/Horse/Jockey/Trainer/Entry のupsert）。

        Args:
            entries_data: fetch_race_entries() の返り値
        """
        ri = entries_data.get("race_info", {})
        race_id = ri.get("race_id", "")
        if not race_id:
            return

        # Race のupsert
        race_date = None
        date_str = ri.get("date", "")
        if date_str:
            try:
                race_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                race_date = date.today()
        else:
            race_date = date.today()

        race = self.db.get(Race, race_id)
        if race is None:
            race = Race(
                id=race_id,
                name=ri.get("name") or "（未取得）",
                date=race_date,
                venue=ri.get("venue") or "不明",
                course_type=ri.get("course_type") or "芝",
                distance=ri.get("distance") or 2000,
                grade=ri.get("grade") or "OP",
            )
            self.db.add(race)
        else:
            # 既存レコードを更新
            if ri.get("name"):
                race.name = ri["name"]
            if ri.get("venue"):
                race.venue = ri["venue"]
            if ri.get("course_type"):
                race.course_type = ri["course_type"]
            if ri.get("distance"):
                race.distance = ri["distance"]
            if ri.get("grade"):
                race.grade = ri["grade"]
        self.db.flush()

        for entry_data in entries_data.get("entries", []):
            horse_id = entry_data.get("horse_id", "")
            if not horse_id:
                continue

            # Horse のupsert
            horse = self.db.get(Horse, horse_id)
            if horse is None:
                horse = Horse(
                    id=horse_id,
                    name=entry_data.get("horse_name") or "（未取得）",
                )
                self.db.add(horse)
            self.db.flush()

            # Jockey のupsert
            jockey_id = entry_data.get("jockey_id", "")
            if jockey_id:
                jockey = self.db.get(Jockey, jockey_id)
                if jockey is None:
                    jockey = Jockey(
                        id=jockey_id,
                        name=entry_data.get("jockey_name") or "（未取得）",
                    )
                    self.db.add(jockey)
                self.db.flush()

            # Trainer のupsert
            trainer_id = entry_data.get("trainer_id", "")
            if trainer_id:
                trainer = self.db.get(Trainer, trainer_id)
                if trainer is None:
                    trainer = Trainer(
                        id=trainer_id,
                        name=entry_data.get("trainer_name") or "（未取得）",
                    )
                    self.db.add(trainer)
                self.db.flush()

            # Entry のupsert（race_id + horse_id でユニーク）
            existing_entry = (
                self.db.query(Entry)
                .filter_by(race_id=race_id, horse_id=horse_id)
                .first()
            )
            if existing_entry is None:
                new_entry = Entry(
                    race_id=race_id,
                    horse_id=horse_id,
                    jockey_id=jockey_id or None,
                    trainer_id=trainer_id or None,
                    post_position=entry_data.get("post_position"),
                    horse_number=entry_data.get("horse_number"),
                    weight=entry_data.get("weight"),
                )
                self.db.add(new_entry)
            else:
                # 既存エントリを更新
                existing_entry.jockey_id = jockey_id or existing_entry.jockey_id
                existing_entry.trainer_id = trainer_id or existing_entry.trainer_id
                existing_entry.post_position = entry_data.get(
                    "post_position", existing_entry.post_position
                )
                existing_entry.horse_number = entry_data.get(
                    "horse_number", existing_entry.horse_number
                )
                existing_entry.weight = entry_data.get("weight", existing_entry.weight)

        self.db.flush()

    def _persist_horse_profile(self, profile: dict) -> None:
        """馬プロフィール情報をDBに保存する（Horseレコード更新）。

        Args:
            profile: fetch_horse_profile() の返り値
        """
        horse_id = profile.get("id", "")
        if not horse_id:
            return

        horse = self.db.get(Horse, horse_id)
        if horse is None:
            horse = Horse(
                id=horse_id,
                name=profile.get("name") or "（未取得）",
            )
            self.db.add(horse)

        # 各フィールドを更新（値がある場合のみ）
        if profile.get("name"):
            horse.name = profile["name"]
        if profile.get("sex"):
            horse.sex = profile["sex"]
        if profile.get("birthday"):
            try:
                horse.birthday = datetime.strptime(
                    profile["birthday"], "%Y-%m-%d"
                ).date()
            except ValueError:
                pass
        if profile.get("sire"):
            horse.sire = profile["sire"]
        if profile.get("dam"):
            horse.dam = profile["dam"]
        if profile.get("dam_sire"):
            horse.dam_sire = profile["dam_sire"]

        self.db.flush()

    def _persist_horse_results(self, horse_id: str, results: list[dict]) -> None:
        """馬の過去成績をDBに保存する。

        Args:
            horse_id: netkeibaの馬ID
            results: fetch_horse_results() の返り値

        前提条件:
            horse_id に対応する Horse レコードが DB 上に存在すること。
            存在しない場合、Result の外部キー制約違反が発生する可能性がある。
        """
        for res in results:
            race_id = res.get("race_id", "")
            if not race_id:
                continue

            # 参照先Raceが存在しない場合はスタブRaceを作成（seed.pyのパターン）
            if self.db.get(Race, race_id) is None:
                date_str = res.get("date", "")
                stub_date = date(2024, 1, 1)
                if date_str:
                    try:
                        # "YYYY/MM/DD" または "YYYY-MM-DD" 形式
                        stub_date = datetime.strptime(
                            date_str.replace("/", "-"), "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        pass
                stub_race = Race(
                    id=race_id,
                    name=res.get("race_name") or "（過去レース）",
                    date=stub_date,
                    venue=res.get("venue") or "不明",
                    course_type=res.get("course_type") or "芝",
                    distance=res.get("distance") or 2000,
                    grade="OP",
                )
                self.db.add(stub_race)
                self.db.flush()

            # Resultのupsert（race_id + horse_id でユニーク）
            existing = (
                self.db.query(Result)
                .filter_by(race_id=race_id, horse_id=horse_id)
                .first()
            )
            if existing is None:
                last_3f = res.get("last_3f")
                if last_3f == 0.0:
                    last_3f = None
                new_result = Result(
                    race_id=race_id,
                    horse_id=horse_id,
                    finish_position=res.get("finish_position"),
                    time=res.get("time"),
                    last_3f=last_3f,
                )
                self.db.add(new_result)

        self.db.flush()

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
