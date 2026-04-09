from __future__ import annotations

import re
from datetime import date

from app.scrapers.base import BaseScraper

# race_idの5〜6桁目（0始まり: インデックス4-5）で会場を判定
_VENUE_CODE: dict[str, str] = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}

# グレード正規化マップ（netkeibaのレース名中の表記）
_GRADE_NORMALIZE: dict[str, str] = {
    "GⅠ": "G1",
    "GⅡ": "G2",
    "GⅢ": "G3",
    "G1": "G1",
    "G2": "G2",
    "G3": "G3",
    "J・GⅠ": "G1",
    "J・GⅡ": "G2",
    "J・GⅢ": "G3",
}

_GRADE_PATTERN = re.compile(
    r"\((" + "|".join(re.escape(k) for k in _GRADE_NORMALIZE) + r")\)"
)


def _normalize_grade(text: str) -> str:
    """レース名テキストからグレードを抽出して正規化する。"""
    m = _GRADE_PATTERN.search(text)
    if m:
        return _GRADE_NORMALIZE.get(m.group(1), "")
    return ""


def _venue_from_race_id(race_id: str) -> str:
    """race_idの5〜6桁目（インデックス4-5）から会場名を返す。

    例: "202606030501" → インデックス4-5 = "03" → 福島
    race_idフォーマット: YYYY + CC + RR + DD + NN
      YYYY=年, CC=会場コード(2桁), RR=回, DD=日, NN=レース番号(2桁)
    """
    if len(race_id) >= 6:
        code = race_id[4:6]
        return _VENUE_CODE.get(code, "")
    return ""


class NetkeibaScraper(BaseScraper):
    """netkeiba.com から競馬データを取得するスクレイパー。"""

    BASE_URL = "https://race.netkeiba.com"
    DB_URL = "https://db.netkeiba.com"

    async def fetch_race_list_by_date(self, target_date: date) -> list[dict]:
        """日付指定でその日のレース一覧を取得する。

        Args:
            target_date: 取得対象日

        Returns:
            レース情報のリスト。各要素は以下の形式:
            {"race_id": str, "race_number": int}
        """
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/top/race_list_sub.html?kaisai_date={date_str}"
        try:
            html = await self.fetch(url)
        except Exception as e:
            self.logger.warning("レース一覧取得失敗 (%s): %s", date_str, e)
            return []

        soup = self.parse_html(html)
        results: list[dict] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = re.search(r"race_id=(\d+)", href)
            if not m:
                continue
            race_id = m.group(1)
            if race_id in seen:
                continue
            seen.add(race_id)
            # race_idの末尾2桁がレース番号（例: ...01 → 1R）
            try:
                race_number = int(race_id[-2:])
            except ValueError:
                race_number = 0
            results.append({"race_id": race_id, "race_number": race_number})

        return results

    async def fetch_race_entries(self, race_id: str) -> dict:
        """レース出馬表ページから出走馬情報を取得する。

        Args:
            race_id: netkeibaのレースID（例: "202405050811"）

        Returns:
            レース情報と出走馬リストを含む辞書。エラー時は空dict `{}` を返す。
        """
        url = f"{self.BASE_URL}/race/shutuba.html?race_id={race_id}"
        try:
            html = await self.fetch(url)
        except Exception as e:
            self.logger.warning("出馬表取得失敗 (race_id=%s): %s", race_id, e)
            return {}

        soup = self.parse_html(html)

        # ---- レース情報の抽出 ----
        distance = 0
        course_type = ""
        race_data_div = soup.find("div", class_="RaceData01")
        if race_data_div:
            rd_text = race_data_div.get_text()
            dist_m = re.search(r"(\d+)m", rd_text)
            if dist_m:
                distance = int(dist_m.group(1))
            if "芝" in rd_text:
                course_type = "芝"
            elif "ダート" in rd_text or "ダ" in rd_text:
                course_type = "ダート"

        # レース名の取得
        race_name = ""
        for selector in [".RaceName", ".race_name", "h1.RaceName", "h2.RaceName"]:
            name_el = soup.select_one(selector)
            if name_el:
                race_name = name_el.get_text(strip=True)
                break
        if not race_name:
            # fallback: h1, h2 タグ
            for tag in soup.find_all(["h1", "h2"]):
                text = tag.get_text(strip=True)
                if text:
                    race_name = text
                    break

        # グレード判定
        grade = _normalize_grade(race_name)

        # 会場判定（race_idから）
        venue = _venue_from_race_id(race_id)

        # レース日付（race_idの先頭4桁が年、次の4桁が不要、0-3が年）
        race_date_str = ""
        if len(race_id) >= 8:
            year = race_id[:4]
            # race_idから日付は直接取れないため、ページのメタ情報から取得を試みる
            # fallback として空文字
            date_el = soup.select_one(".RaceData02 span")
            if date_el:
                date_text = date_el.get_text(strip=True)
                dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_text)
                if dm:
                    race_date_str = (
                        f"{dm.group(1)}-"
                        f"{int(dm.group(2)):02d}-"
                        f"{int(dm.group(3)):02d}"
                    )
            if not race_date_str:
                # ページ全体からISO日付を探す
                full_text = soup.get_text()
                dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", full_text)
                if dm:
                    race_date_str = (
                        f"{dm.group(1)}-"
                        f"{int(dm.group(2)):02d}-"
                        f"{int(dm.group(3)):02d}"
                    )
            if not race_date_str and len(race_id) >= 4:
                # 最低限、年だけでも使用
                race_date_str = f"{year}-01-01"
                self.logger.warning(
                    "レース日付未取得: %s-01-01 にフォールバック (race_id=%s)",
                    year,
                    race_id,
                )

        # ---- 出馬表のパース ----
        entries: list[dict] = []
        table = soup.select_one("table.Shutuba_Table")
        if not table:
            # テーブルが見つからない場合は空dict
            self.logger.warning("出馬表テーブルが見つかりません (race_id=%s)", race_id)
            return {}

        for tr in table.select("tbody tr"):
            # 取消馬スキップ: trにclass "Cancel" があるか、テキストに"取消"を含む行
            tr_classes = tr.get("class", [])
            tr_text = tr.get_text()
            if "Cancel" in tr_classes or "取消" in tr_text:
                continue

            # 枠番
            waku_td = tr.select_one("td.Waku")
            post_position = 0
            if waku_td:
                try:
                    post_position = int(waku_td.get_text(strip=True))
                except ValueError:
                    pass

            # 馬番
            umaban_td = tr.select_one("td.Umaban")
            horse_number = 0
            if umaban_td:
                try:
                    horse_number = int(umaban_td.get_text(strip=True))
                except ValueError:
                    pass

            # 有効な行かチェック（枠番・馬番が0の行はヘッダー等としてスキップ）
            if post_position == 0 and horse_number == 0:
                continue

            # 馬情報
            horse_link = tr.select_one("td.HorseInfo a[href*='/horse/']")
            if not horse_link:
                continue
            horse_name = horse_link.get_text(strip=True)
            horse_href = horse_link.get("href", "")
            horse_id_m = re.search(r"/horse/(\w+)", horse_href)
            horse_id = horse_id_m.group(1) if horse_id_m else ""

            # 斤量
            kinryo_td = tr.select_one("td.Kinryo")
            weight = 0.0
            if kinryo_td:
                try:
                    weight = float(kinryo_td.get_text(strip=True))
                except ValueError:
                    pass

            # 騎手
            jockey_link = tr.select_one("a[href*='/jockey/']")
            jockey_name = ""
            jockey_id = ""
            if jockey_link:
                jockey_name = jockey_link.get_text(strip=True)
                jockey_href = jockey_link.get("href", "")
                jm = re.search(r"/jockey/(?:result/recent/)?(\w+)", jockey_href)
                jockey_id = jm.group(1).rstrip("/") if jm else ""

            # 調教師
            trainer_link = tr.select_one("a[href*='/trainer/']")
            trainer_name = ""
            trainer_id = ""
            if trainer_link:
                trainer_name = trainer_link.get_text(strip=True)
                trainer_href = trainer_link.get("href", "")
                tm = re.search(r"/trainer/(?:result/recent/)?(\w+)", trainer_href)
                trainer_id = tm.group(1).rstrip("/") if tm else ""

            entries.append(
                {
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "jockey_id": jockey_id,
                    "jockey_name": jockey_name,
                    "trainer_id": trainer_id,
                    "trainer_name": trainer_name,
                    "post_position": post_position,
                    "horse_number": horse_number,
                    "weight": weight,
                }
            )

        return {
            "race_info": {
                "race_id": race_id,
                "name": race_name,
                "date": race_date_str,
                "venue": venue,
                "grade": grade,
                "distance": distance,
                "course_type": course_type,
            },
            "entries": entries,
        }

    async def fetch_horse_profile(self, horse_id: str) -> dict:
        """馬の血統・プロフィールを取得する。

        Args:
            horse_id: netkeibaの馬ID（例: "2019105943"）

        Returns:
            馬のプロフィール情報。エラー時は空dict `{}` を返す。
        """
        # Step 1: メインプロフィールページ（静的HTML）
        profile_url = f"{self.DB_URL}/horse/{horse_id}/"
        try:
            html = await self.fetch(profile_url)
        except Exception as e:
            self.logger.warning("馬プロフィール取得失敗 (horse_id=%s): %s", horse_id, e)
            return {}

        soup = self.parse_html(html)

        # 馬名: <title> から取得
        horse_name = ""
        title_el = soup.find("title")
        if title_el:
            title_text = title_el.get_text(strip=True)
            nm = re.match(r"^(.+?)\s*[（(]", title_text)
            if nm:
                horse_name = nm.group(1).strip()
            else:
                horse_name = title_text.split()[0] if title_text else ""

        # 誕生日: ページテキストから取得
        birthday = ""
        full_text = soup.get_text()
        bm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", full_text)
        if bm:
            birthday = f"{bm.group(1)}-{int(bm.group(2)):02d}-{int(bm.group(3)):02d}"

        # 性別: プロフィール領域から取得
        sex = ""
        sex_m = re.search(r"[牡牝セ]", full_text)
        if sex_m:
            sex = sex_m.group(0)

        # Step 2: 血統AJAXエンドポイント
        pedigree_url = f"{self.DB_URL}/horse/ajax_horse_pedigree.html?id={horse_id}"
        sire = ""
        dam = ""
        dam_sire = ""
        try:
            pedigree_html = await self.fetch(pedigree_url, encoding="euc-jp")
        except Exception:
            # euc-jpでの取得に失敗した場合はutf-8でリトライ
            try:
                pedigree_html = await self.fetch(pedigree_url)
            except Exception as e:
                self.logger.warning("血統取得失敗 (horse_id=%s): %s", horse_id, e)
                pedigree_html = ""

        if pedigree_html:
            ped_soup = self.parse_html(pedigree_html)
            # 血統テーブルから父・母・母父を抽出
            # blood_tableまたは類似クラスを探す
            blood_table = ped_soup.find("table", class_="blood_table")
            if not blood_table:
                blood_table = ped_soup.find("table")
            if blood_table:
                rows = blood_table.find_all("tr")
                if len(rows) >= 1:
                    # 1行目に父の情報（最初のaタグ）
                    first_row = rows[0]
                    links = first_row.find_all("a")
                    if links:
                        sire = links[0].get_text(strip=True)
                if len(rows) >= 2:
                    # 2行目に母の情報
                    second_row = rows[1]
                    links = second_row.find_all("a")
                    if links:
                        dam = links[0].get_text(strip=True)
                if len(rows) >= 3:
                    # 3行目に母父の情報（またはtd内の特定位置）
                    third_row = rows[2]
                    links = third_row.find_all("a")
                    if links:
                        dam_sire = links[0].get_text(strip=True)

        if not sire:
            self.logger.warning("父馬が取得できませんでした (horse_id=%s)", horse_id)
        if not dam:
            self.logger.warning("母馬が取得できませんでした (horse_id=%s)", horse_id)
        if not dam_sire:
            self.logger.warning("母父が取得できませんでした (horse_id=%s)", horse_id)

        return {
            "id": horse_id,
            "name": horse_name,
            "sex": sex,
            "birthday": birthday,
            "sire": sire,
            "dam": dam,
            "dam_sire": dam_sire,
        }

    async def fetch_horse_results(self, horse_id: str, limit: int = 10) -> list[dict]:
        """馬の過去成績を取得する。

        Args:
            horse_id: netkeibaの馬ID（例: "2019105943"）
            limit: 取得する過去成績の最大件数

        Returns:
            過去成績のリスト。エラー時は空リスト `[]` を返す。
        """
        url = f"{self.DB_URL}/horse/ajax_horse_results.html?id={horse_id}"
        try:
            html = await self.fetch(url)
        except Exception as e:
            self.logger.warning("過去成績取得失敗 (horse_id=%s): %s", horse_id, e)
            return []

        soup = self.parse_html(html)
        table = soup.find("table")
        if not table:
            return []

        # ヘッダー行でカラム位置を特定
        col_index: dict[str, int] = {}
        header_row = table.find("tr")
        if header_row:
            for i, th in enumerate(header_row.find_all(["th", "td"])):
                col_name = th.get_text(strip=True)
                col_index[col_name] = i

        results: list[dict] = []
        rows = table.find_all("tr")
        # ヘッダー行をスキップしてデータ行を処理
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue

            def _cell(key: str, fallback: int = -1, _cells: list = cells) -> str:
                idx = col_index.get(key, fallback)
                if idx < 0 or idx >= len(_cells):
                    return ""
                return _cells[idx].get_text(strip=True)

            # カラム位置が特定できない場合は位置でフォールバック
            # 一般的なnetkeiba成績テーブルの列順:
            # 0:日付, 1:開催, 2:天気, 3:R, 4:レース名, 5:映像, 6:頭数, 7:枠, 8:馬番,
            # 9:オッズ, 10:人気, 11:着順, 12:騎手, 13:斤量, 14:距離, 15:馬場,
            # 16:馬場指数, 17:タイム, 18:着差, 19:タイム指数, 20:上3F, 21:コメント
            date_str = _cell("日付", 0)
            race_name = _cell("レース名", 4)
            finish_pos_str = _cell("着順", 11)
            jockey_name = _cell("騎手", 12)
            dist_str = _cell("距離", 14)
            track_cond = _cell("馬場", 15)
            time_str = _cell("タイム", 17)
            last3f_str = _cell("上3F", 20)

            # 着順が数値でない行はスキップ（中止, 除外, 取消 等）
            try:
                finish_position = int(finish_pos_str)
            except ValueError:
                continue

            # race_idをリンクから取得
            race_id = ""
            race_link = None
            race_name_idx = col_index.get("レース名", 4)
            if 0 <= race_name_idx < len(cells):
                race_link = cells[race_name_idx].find("a", href=True)
            if race_link:
                href = race_link.get("href", "")
                rid_m = re.search(r"race_id=(\d+)", href)
                if rid_m:
                    race_id = rid_m.group(1)

            # 距離とコース種別の抽出（例: "芝2000"、"ダ1600"）
            distance = 0
            course_type = ""
            if dist_str:
                if dist_str.startswith("芝"):
                    course_type = "芝"
                    try:
                        distance = int(dist_str[1:])
                    except ValueError:
                        pass
                elif dist_str.startswith("ダ"):
                    course_type = "ダート"
                    try:
                        distance = int(dist_str[1:])
                    except ValueError:
                        pass
                else:
                    dm = re.search(r"(\d+)", dist_str)
                    if dm:
                        distance = int(dm.group(1))

            # 開催・会場
            venue_str = _cell("開催", 1)
            venue = ""
            if venue_str:
                # 「阪神1回1日」のような形式から競馬場名を取得
                for v in _VENUE_CODE.values():
                    if v in venue_str:
                        venue = v
                        break

            # 上がり3F
            last_3f = 0.0
            try:
                last_3f = float(last3f_str)
            except ValueError:
                pass

            results.append(
                {
                    "race_id": race_id,
                    "race_name": race_name,
                    "date": date_str,
                    "venue": venue,
                    "distance": distance,
                    "course_type": course_type,
                    "track_condition": track_cond,
                    "finish_position": finish_position,
                    "time": time_str,
                    "last_3f": last_3f,
                    "jockey_name": jockey_name,
                }
            )

        return results[:limit]

    async def fetch_race_results_history(
        self, race_name: str, limit: int = 5
    ) -> list[dict]:
        """同名レースの過去結果を取得する。

        Args:
            race_name: レース名（例: "天皇賞(春)"）
            limit: 取得する過去年度の最大件数

        Returns:
            過去レース結果のリスト。

        TODO: 将来の実装方針
            - https://db.netkeiba.com/?pid=race_search_detail でレース名検索
            - 結果ページからrace_idを収集し、各レースのtopページから着順を取得する
        """
        # MVP: スコアリングのscore_same_raceは50.0（ニュートラル）を返す
        return []
