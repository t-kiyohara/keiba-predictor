from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Entry, Horse, Jockey, Race, Result, Trainer
from app.scoring.engine import ScoringEngine
from app.scrapers.jra import JraScraper, get_target_race_dates
from app.scrapers.netkeiba import NetkeibaScraper, _normalize_grade, venue_from_race_id
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

    # ------------------------------------------------------------------
    # 公開メソッド
    # ------------------------------------------------------------------

    async def execute(self) -> None:
        """7ステップのフェッチ・スコアリングパイプラインを実行する"""

        # ステップ1: 対象日を決定する
        self.progress("日程取得", 1, self.TOTAL_STEPS, "対象レース日を決定中...")
        target_dates = self._step_determine_dates()

        # ステップ2: JRAグレードレース一覧とnetkeiba race_idを取得
        self.progress(
            "レース一覧", 2, self.TOTAL_STEPS, "JRAから重賞レース一覧を取得中..."
        )
        graded_races = await self._step_fetch_race_list(target_dates)

        # レースが見つからない場合は既存DBデータでスコアリングのみ実行
        if not graded_races:
            self._run_fallback_scoring()
            return

        # ステップ3: 各レースのエントリを取得・永続化
        total_races = len(graded_races)
        self.progress(
            "出走馬取得",
            3,
            self.TOTAL_STEPS,
            f"出走馬情報を取得中 (0/{total_races})...",
            estimated_remaining=total_races * 30,
        )
        races = await self._step_fetch_entries(graded_races)
        self.db.commit()

        # ステップ4: 馬プロフィールを取得・永続化
        horse_ids = self._collect_horse_ids(races)
        total_horses = len(horse_ids)
        self.progress(
            "馬情報取得",
            4,
            self.TOTAL_STEPS,
            f"馬のプロフィールを取得中 (0/{total_horses})...",
        )
        await self._step_fetch_profiles(horse_ids)

        # ステップ5: 馬成績を取得・永続化
        self.progress(
            "成績取得",
            5,
            self.TOTAL_STEPS,
            f"馬の過去成績を取得中 (0/{total_horses})...",
        )
        await self._step_fetch_results(horse_ids)

        # ステップ6: 各レースの天気を取得・更新
        self.progress(
            "天気取得",
            6,
            self.TOTAL_STEPS,
            "レース当日の天気を取得中...",
        )
        await self._step_fetch_weather(races)
        self.db.commit()

        # ステップ7: スコアリングを実行
        self.progress(
            "スコアリング", 7, self.TOTAL_STEPS, "予想スコアを算出中..."
        )
        self._step_score(races)

    # ------------------------------------------------------------------
    # プライベートステップメソッド
    # ------------------------------------------------------------------

    def _step_determine_dates(self) -> list[date]:
        """ステップ1: 対象日を決定する"""
        today = date.today()
        return get_target_race_dates(today)

    async def _step_fetch_race_list(
        self, target_dates: list[date]
    ) -> list[dict]:
        """ステップ2: JRAグレードレース一覧とnetkeiba race_idを取得

        JRAから重賞レース一覧を取得し、netkeibaのrace_idと突合して返す。
        レースが見つからない場合は空リストを返す。
        """
        graded_races = await self.jra.fetch_graded_races(target_dates)

        # netkeibaからrace_id一覧を日付ごとに取得
        netkeiba_race_map: dict[str, list[dict]] = {}
        for target_date in target_dates:
            nb_list = await self.netkeiba.fetch_race_list_by_date(target_date)
            date_str = target_date.isoformat()
            netkeiba_race_map[date_str] = nb_list

        # JRAの重賞データとnetkeibaのrace_idをマッチング
        # （race_number + venue で突合）
        for gr in graded_races:
            race_date = gr.get("date")
            race_number = gr.get("race_number", 11)
            jra_venue = gr.get("venue", "")
            if not race_date:
                continue
            date_str = (
                race_date.isoformat()
                if isinstance(race_date, date)
                else race_date
            )
            nb_races = netkeiba_race_map.get(date_str, [])
            # 1st pass: race_number + venue で完全一致
            for nb_race in nb_races:
                nb_rid = nb_race.get("race_id", "")
                nb_venue = venue_from_race_id(nb_rid)
                if (
                    nb_race.get("race_number") == race_number
                    and nb_venue == jra_venue
                ):
                    gr["race_id"] = nb_rid
                    break
            else:
                # 2nd pass: race_number のみで照合（venue不一致時のフォールバック）
                for nb_race in nb_races:
                    if nb_race.get("race_number") == race_number:
                        gr["race_id"] = nb_race["race_id"]
                        break

        return graded_races

    async def _step_fetch_entries(
        self, graded_races: list[dict]
    ) -> list[Race]:
        """ステップ3: 各レースのエントリを取得・永続化

        取得・保存したレースのリストを返す。
        """
        total_races = len(graded_races)
        persisted_races: list[Race] = []

        for i, race_info in enumerate(graded_races, start=1):
            self.progress(
                "出走馬取得",
                3,
                self.TOTAL_STEPS,
                f"出走馬情報を取得中 ({i}/{total_races})...",
                estimated_remaining=(total_races - i) * 30,
            )
            race_id = race_info.get("race_id", "")
            if not race_id:
                continue

            entries_data = await self.netkeiba.fetch_race_entries(race_id)
            if not entries_data:
                continue

            # graded_racesのデータでrace_infoを補完
            ri = entries_data.get("race_info", {})
            if not ri.get("name"):
                ri["name"] = race_info.get("name", "")
            if not ri.get("grade"):
                ri["grade"] = race_info.get("grade", "")
            if not ri.get("venue"):
                ri["venue"] = race_info.get("venue", "")

            self._persist_race_entries(entries_data)

            # 単勝オッズを取得・反映（失敗してもレース処理は継続する）
            odds_by_horse_number = await self.netkeiba.fetch_odds(race_id)
            if odds_by_horse_number:
                self._persist_odds(race_id, odds_by_horse_number)

            # 保存したRaceオブジェクトを収集
            race = self.db.get(Race, race_id)
            if race:
                persisted_races.append(race)

        return persisted_races

    async def _step_fetch_profiles(
        self, horse_ids: list[str]
    ) -> None:
        """ステップ4: 馬プロフィールを取得・永続化"""
        total_horses = len(horse_ids)
        for j, horse_id in enumerate(horse_ids, start=1):
            self.progress(
                "馬情報取得",
                4,
                self.TOTAL_STEPS,
                f"馬のプロフィールを取得中 ({j}/{total_horses})...",
            )
            profile = await self.netkeiba.fetch_horse_profile(horse_id)
            if profile:
                self._persist_horse_profile(profile)
            # 途中で例外が起きても取得済み分を失わないよう馬ごとにcommitする
            self.db.commit()

    async def _step_fetch_results(
        self, horse_ids: list[str]
    ) -> None:
        """ステップ5: 馬成績を取得・永続化"""
        total_horses = len(horse_ids)
        for k, horse_id in enumerate(horse_ids, start=1):
            self.progress(
                "成績取得",
                5,
                self.TOTAL_STEPS,
                f"馬の過去成績を取得中 ({k}/{total_horses})...",
            )
            results = await self.netkeiba.fetch_horse_results(horse_id)
            if results:
                self._persist_horse_results(horse_id, results)
            # 途中で例外が起きても取得済み分を失わないよう馬ごとにcommitする
            self.db.commit()

    async def _step_fetch_weather(
        self, races: list[Race]
    ) -> None:
        """ステップ6: 各レースの天気を取得・更新"""
        for race in races:
            venue = race.venue or ""
            if not venue:
                continue
            weather_info = await self.weather.get_weather(venue)
            if weather_info:
                race.weather = weather_info.get("weather", "")
                self.db.flush()

    def _step_score(
        self, _races: list[Race]
    ) -> None:
        """ステップ7: スコアリングを実行

        DBに存在する全レースを対象にスコアリングする。
        過去フェッチで蓄積されたデータも含めて再スコアリングされる。
        """
        self._score_existing_races()

    # ------------------------------------------------------------------
    # 内部ユーティリティ
    # ------------------------------------------------------------------

    def _collect_horse_ids(self, races: list[Race]) -> list[str]:
        """レースリストから重複なしの馬IDリストを収集する"""
        horse_ids: list[str] = []
        for race in races:
            for entry in race.entries:
                hid = entry.horse_id
                if hid and hid not in horse_ids:
                    horse_ids.append(hid)
        return horse_ids

    def _run_fallback_scoring(self) -> None:
        """重賞レースが見つからない場合の既存DBデータでのスコアリング"""
        not_found_message = (
            "対象期間に重賞レースが見つかりませんでした。既存データで再スコアリングします"
        )
        self.progress("レース一覧", 2, self.TOTAL_STEPS, not_found_message)
        self.progress("出走馬取得", 3, self.TOTAL_STEPS, not_found_message)
        self.progress("馬情報取得", 4, self.TOTAL_STEPS, not_found_message)
        self.progress("成績取得", 5, self.TOTAL_STEPS, not_found_message)
        self.progress("天気取得", 6, self.TOTAL_STEPS, not_found_message)
        self.progress(
            "スコアリング",
            7,
            self.TOTAL_STEPS,
            "DBのサンプルデータで予想スコアを算出中...",
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

    def _persist_odds(
        self, race_id: str, odds_by_horse_number: dict[int, float]
    ) -> None:
        """単勝オッズをEntry.oddsに反映する（馬番マッチでupdate）。

        Args:
            race_id: netkeibaのレースID
            odds_by_horse_number: fetch_odds() の返り値（馬番→単勝オッズ）

        該当馬番のオッズが無いEntryはoddsをNoneのままにする。
        """
        entries = self.db.query(Entry).filter_by(race_id=race_id).all()
        for entry in entries:
            odds_value = odds_by_horse_number.get(entry.horse_number)
            if odds_value is not None:
                entry.odds = odds_value
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
            existing_race = self.db.get(Race, race_id)
            if existing_race is None:
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
                    grade=_normalize_grade(res.get("race_name") or "") or "OP",
                    track_condition=res.get("track_condition") or None,
                )
                self.db.add(stub_race)
                self.db.flush()
            elif existing_race.track_condition is None and res.get("track_condition"):
                # 既存Raceに馬場状態が未設定なら成績データで埋める（上書きはしない）
                existing_race.track_condition = res["track_condition"]

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
                    jockey_name=res.get("jockey_name") or None,
                )
                self.db.add(new_result)

        self.db.flush()

    def _score_existing_races(self) -> None:
        """DBに存在する全レースに対してスコアリングを実行"""
        engine = ScoringEngine(self.db)
        races = self.db.query(Race).all()
        for race in races:
            try:
                engine.predict_race(race.id)
            except Exception as e:
                logger.warning("Scoring failed for race %s: %s", race.id, e)
        self.db.commit()
