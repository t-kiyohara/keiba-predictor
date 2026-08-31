from __future__ import annotations

import json
import re
from datetime import date
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper
from app.scrapers.constants import GRADE_NORMALIZE, GRADE_PATTERN

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

# db.netkeiba.com の払戻テーブルは th の class で券種を表す
_BET_TYPE_BY_CLASS: dict[str, str] = {
    "tan": "単勝",
    "fuku": "複勝",
    "waku": "枠連",
    "uren": "馬連",
    "wide": "ワイド",
    "utan": "馬単",
    "sanfuku": "三連複",
    "santan": "三連単",
}

# db.netkeiba.com の着順テーブル（table.race_table_01）の列順フォールバック。
# 通常はヘッダー文字列から動的に引くが、ヘッダーが取れない場合に使う。
_RESULT_COLUMN_FALLBACK: dict[str, int] = {
    "着順": 0,
    "枠番": 1,
    "馬番": 2,
    "馬名": 3,
    "性齢": 4,
    "斤量": 5,
    "騎手": 6,
    "タイム": 7,
    "着差": 8,
    "通過": 14,
    "上り": 15,
    "単勝": 16,
    "人気": 17,
    "馬体重": 18,
    "調教師": 22,
}


def _normalize_grade(text: str) -> str:
    """レース名テキストからグレードを抽出して正規化する。"""
    m = GRADE_PATTERN.search(text)
    if m:
        return GRADE_NORMALIZE.get(m.group(1), "")
    return ""


def _to_int(text: str | None) -> int | None:
    """数値文字列をintに変換する。変換できない場合はNoneを返す。"""
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _to_float(text: str | None) -> float | None:
    """数値文字列をfloatに変換する。変換できない場合はNoneを返す。"""
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _link_id_and_name(cell, url_path: str) -> tuple[str, str]:
    """セル内の最初のリンクから `/{url_path}/...` のIDとリンクテキストを取り出す。

    調教師セルはリンクの手前に `[西]` / `[東]` が付くため、セル全体ではなく
    リンクのテキストを名前として使う。

    Args:
        cell: BeautifulSoupのtdタグ（Noneの場合は空文字を返す）
        url_path: URLパスの先頭セグメント（"horse" / "jockey" / "trainer"）

    Returns:
        (ID, 名前) のタプル。取得できない要素は空文字。
    """
    if cell is None:
        return "", ""
    link = cell.find("a", href=True)
    if link is None:
        return "", ""
    match = re.search(rf"/{url_path}/(?:result/recent/)?(\w+)", link["href"])
    return (match.group(1) if match else ""), link.get_text(strip=True)


def venue_from_race_id(race_id: str) -> str:
    """race_idの5〜6桁目（インデックス4-5）から会場名を返す。

    例: "202606030511" → インデックス4-5 = "06" → 中山
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

    # レース検索（pid=race_list）のパラメータ
    GRADES = (1, 2, 3)  # 1=G1, 2=G2, 3=G3
    GRADED_LIST_PAGE_SIZE = 100
    # 5年分でも約700件（1ページ100件）。暴走時の無限リクエストを止める安全弁
    MAX_GRADED_LIST_PAGES = 100

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

    def _graded_race_list_url(
        self, start_year: int, end_year: int, page: int
    ) -> str:
        """db.netkeiba のレース検索URLを組み立てる。

        `jyo[]` はJRA10場（_VENUE_CODE のキー）を必ず全て付ける。付けないと
        地方・海外の重賞が結果に混入する。`grade[]` は 1=G1, 2=G2, 3=G3。
        """
        params: list[tuple[str, str | int]] = [
            ("pid", "race_list"),
            ("start_year", start_year),
            ("end_year", end_year),
        ]
        params += [("grade[]", grade) for grade in self.GRADES]
        params += [("jyo[]", venue_code) for venue_code in _VENUE_CODE]
        params += [("list", self.GRADED_LIST_PAGE_SIZE), ("page", page)]
        return f"{self.DB_URL}/?{urlencode(params)}"

    def _parse_graded_race_ids(self, soup: BeautifulSoup) -> list[str]:
        """検索結果テーブル（table.race_table_01）から race_id を抽出する。

        レース名セルのリンク `<a href="/race/202406050911/">` が取得元。
        開催日リンク（`/race/list/20240601/`）は12桁ではないため一致しない。
        """
        table = soup.select_one("table.race_table_01")
        if table is None:
            return []
        race_ids: list[str] = []
        for link in table.select("a[href*='/race/']"):
            match = re.search(r"/race/(\d{12})", link["href"])
            if match:
                race_ids.append(match.group(1))
        return race_ids

    async def fetch_graded_race_ids(
        self, start_year: int, end_year: int
    ) -> list[str]:
        """指定期間のJRA重賞（G1/G2/G3）の race_id を列挙する。

        Args:
            start_year: 検索開始年（両端含む）
            end_year: 検索終了年（両端含む）

        Returns:
            race_id のリスト（重複排除済み、検索結果の出現順）。
            途中で取得に失敗した場合はそこまでに集めた分を返す。

        新しい race_id が現れなくなったページで打ち切る。件数表示
        （"139件中1~100件目"）のパースには依存しない。
        """
        race_ids: list[str] = []
        seen_race_ids: set[str] = set()

        for page in range(1, self.MAX_GRADED_LIST_PAGES + 1):
            url = self._graded_race_list_url(start_year, end_year, page)
            try:
                html = await self.fetch(url, encoding="euc-jp")
            except Exception as e:
                self.logger.warning("重賞一覧取得失敗 (page=%d): %s", page, e)
                break

            page_race_ids = self._parse_graded_race_ids(self.parse_html(html))
            new_race_ids = [
                race_id
                for race_id in page_race_ids
                if race_id not in seen_race_ids
            ]
            if not new_race_ids:
                break
            seen_race_ids.update(new_race_ids)
            race_ids.extend(new_race_ids)
        else:
            self.logger.warning(
                "重賞一覧のページ上限(%d)に達したため打ち切りました",
                self.MAX_GRADED_LIST_PAGES,
            )

        self.logger.info(
            "重賞 %d件を列挙しました (%d〜%d年)", len(race_ids), start_year, end_year
        )
        return race_ids

    def _parse_race_info(self, soup: BeautifulSoup, race_id: str) -> dict:
        """soupからレース情報（距離, コース種別, グレード, 会場, 日付等）を抽出する。

        Args:
            soup: 出馬表ページのBeautifulSoupオブジェクト
            race_id: netkeibaのレースID

        Returns:
            レース情報の辞書（name, grade, distance, course_type, venue, date）
        """
        # 距離とコース種別
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
        venue = venue_from_race_id(race_id)

        # レース日付の取得（ページのメタ情報から）
        race_date_str = ""
        if len(race_id) >= 8:
            year = race_id[:4]
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

        return {
            "name": race_name,
            "grade": grade,
            "distance": distance,
            "course_type": course_type,
            "venue": venue,
            "date": race_date_str,
        }

    def _parse_entry_table(self, soup: BeautifulSoup) -> list[dict] | None:
        """soupから出走表の各エントリを抽出する。

        Args:
            soup: 出馬表ページのBeautifulSoupオブジェクト

        Returns:
            出走馬情報のリスト。テーブルが見つからない場合はNoneを返す。
        """
        table = soup.select_one("table.Shutuba_Table")
        if not table:
            return None

        entries: list[dict] = []
        for tr in table.find_all("tr"):
            # 取消馬スキップ: trにclass "Cancel" があるか、テキストに"取消"を含む行
            tr_classes = tr.get("class", [])
            tr_text = tr.get_text()
            if "Cancel" in tr_classes or "取消" in tr_text:
                continue

            # 枠番（クラス名が Waku1, Waku2 ... の形式）
            waku_td = tr.select_one("td[class*='Waku']")
            post_position = 0
            if waku_td:
                try:
                    post_position = int(waku_td.get_text(strip=True))
                except ValueError:
                    pass

            # 馬番（クラス名が Umaban1, Umaban2 ... の形式）
            umaban_td = tr.select_one("td[class*='Umaban']")
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

            # 斤量（td.Kinryo または6番目のtd）
            kinryo_td = tr.select_one("td.Kinryo")
            weight = 0.0
            if kinryo_td:
                try:
                    weight = float(kinryo_td.get_text(strip=True))
                except ValueError:
                    pass
            else:
                tds = tr.find_all("td")
                if len(tds) > 5:
                    try:
                        weight = float(tds[5].get_text(strip=True))
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

        return entries

    async def fetch_race_entries(self, race_id: str) -> dict:
        """レース出馬表ページから出走馬情報を取得する。

        Args:
            race_id: netkeibaのレースID（例: "202405050811"）

        Returns:
            レース情報と出走馬リストを含む辞書。エラー時は空dict `{}` を返す。
        """
        url = f"{self.BASE_URL}/race/shutuba.html?race_id={race_id}"
        try:
            html = await self.fetch(url, encoding="euc-jp")
        except Exception as e:
            self.logger.warning("出馬表取得失敗 (race_id=%s): %s", race_id, e)
            return {}

        soup = self.parse_html(html)

        # レース情報の抽出
        race_info = self._parse_race_info(soup, race_id)

        # 出走表のパース
        entries = self._parse_entry_table(soup)
        if entries is None:
            self.logger.warning("出馬表テーブルが見つかりません (race_id=%s)", race_id)
            return {}

        return {
            "race_info": {
                "race_id": race_id,
                "name": race_info["name"],
                "date": race_info["date"],
                "venue": race_info["venue"],
                "grade": race_info["grade"],
                "distance": race_info["distance"],
                "course_type": race_info["course_type"],
            },
            "entries": entries,
        }

    async def fetch_odds(self, race_id: str) -> dict[int, float]:
        """非公式オッズJSON APIから単勝オッズを取得する。

        Args:
            race_id: netkeibaのレースID

        Returns:
            馬番(int) → 単勝オッズ(float) の辞書。未発売/存在しないレースや
            解析失敗時は空dict `{}` を返す。
        """
        url = f"{self.BASE_URL}/api/api_get_jra_odds.html?race_id={race_id}&type=1"
        try:
            text = await self.fetch(url)
        except Exception as e:
            self.logger.warning("オッズ取得失敗 (race_id=%s): %s", race_id, e)
            return {}

        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError) as e:
            self.logger.warning("オッズJSON解析失敗 (race_id=%s): %s", race_id, e)
            return {}

        # 未発売/存在しないレースは data が空文字列（dictでない）で返る。
        # statusではなくdataの形で判定する。
        odds_payload = payload.get("data") if isinstance(payload, dict) else None
        win_odds = (
            odds_payload.get("odds", {}).get("1")
            if isinstance(odds_payload, dict)
            else None
        )
        if not isinstance(win_odds, dict):
            self.logger.warning("オッズデータなし (race_id=%s)", race_id)
            return {}

        win_odds_by_horse_number: dict[int, float] = {}
        for horse_number_str, odds_values in win_odds.items():
            try:
                horse_number = int(horse_number_str)
                win_odds_value = float(odds_values[0])
            except (ValueError, TypeError, IndexError):
                # 取消馬（"---"等）や不正な形式の要素はスキップ
                continue
            win_odds_by_horse_number[horse_number] = win_odds_value

        return win_odds_by_horse_number

    def _parse_profile_page(self, soup: BeautifulSoup) -> dict:
        """プロフィールページからプロフィール情報を抽出する。

        Args:
            soup: 馬プロフィールページのBeautifulSoupオブジェクト

        Returns:
            馬名・誕生日・性別を含む辞書
        """
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

        return {
            "name": horse_name,
            "birthday": birthday,
            "sex": sex,
        }

    async def _fetch_pedigree(self, horse_id: str) -> dict:
        """血統AJAXエンドポイントをフェッチして父/母/母父を返す。

        Args:
            horse_id: netkeibaの馬ID

        Returns:
            {"sire": str, "dam": str, "dam_sire": str} の辞書
        """
        pedigree_url = f"{self.DB_URL}/horse/ajax_horse_pedigree.html?id={horse_id}"
        pedigree_html = ""
        try:
            pedigree_html = await self.fetch(pedigree_url, encoding="euc-jp")
        except Exception:
            # euc-jpでの取得に失敗した場合はutf-8でリトライ
            try:
                pedigree_html = await self.fetch(pedigree_url)
            except Exception as e:
                self.logger.warning("血統取得失敗 (horse_id=%s): %s", horse_id, e)

        sire = ""
        dam = ""
        dam_sire = ""

        if pedigree_html:
            ped_soup = self.parse_html(pedigree_html)
            # 血統テーブルから父・母・母父を抽出
            blood_table = ped_soup.find("table", class_="blood_table")
            if not blood_table:
                blood_table = ped_soup.find("table")
            if blood_table:
                rows = blood_table.find_all("tr")
                if len(rows) >= 1:
                    # 1行目に父の情報（最初のaタグ）
                    links = rows[0].find_all("a")
                    if links:
                        sire = links[0].get_text(strip=True)
                if len(rows) >= 2:
                    # 2行目に母の情報
                    links = rows[1].find_all("a")
                    if links:
                        dam = links[0].get_text(strip=True)
                if len(rows) >= 3:
                    # 3行目に母父の情報（またはtd内の特定位置）
                    links = rows[2].find_all("a")
                    if links:
                        dam_sire = links[0].get_text(strip=True)

        return {"sire": sire, "dam": dam, "dam_sire": dam_sire}

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
            html = await self.fetch(profile_url, encoding="euc-jp")
        except Exception as e:
            self.logger.warning("馬プロフィール取得失敗 (horse_id=%s): %s", horse_id, e)
            return {}

        soup = self.parse_html(html)
        profile = self._parse_profile_page(soup)

        # Step 2: 血統AJAXエンドポイント
        pedigree = await self._fetch_pedigree(horse_id)

        if not pedigree["sire"]:
            self.logger.warning("父馬が取得できませんでした (horse_id=%s)", horse_id)
        if not pedigree["dam"]:
            self.logger.warning("母馬が取得できませんでした (horse_id=%s)", horse_id)
        if not pedigree["dam_sire"]:
            self.logger.warning("母父が取得できませんでした (horse_id=%s)", horse_id)

        return {
            "id": horse_id,
            "name": profile["name"],
            "sex": profile["sex"],
            "birthday": profile["birthday"],
            "sire": pedigree["sire"],
            "dam": pedigree["dam"],
            "dam_sire": pedigree["dam_sire"],
        }

    def _detect_column_indices(self, header_row) -> dict[str, int]:
        """ヘッダー行のセルテキストからカラムインデックスを検出する。

        Args:
            header_row: BeautifulSoupのtrタグ（ヘッダー行）

        Returns:
            カラム名 → インデックスの辞書（例: {"着順": 11, "レース名": 4, ...}）
        """
        col_index: dict[str, int] = {}
        for i, th in enumerate(header_row.find_all(["th", "td"])):
            col_name = th.get_text(strip=True)
            col_index[col_name] = i
        return col_index

    def _parse_result_row(self, row, col_indices: dict[str, int]) -> dict | None:
        """成績テーブルの1行をパースする。スキップ行はNoneを返す。

        Args:
            row: BeautifulSoupのtrタグ（データ行）
            col_indices: _detect_column_indices()で取得したカラム名→インデックスの辞書

        Returns:
            成績情報の辞書。着順が数値でない行（中止/除外/取消等）はNoneを返す。
        """
        cells = row.find_all(["td", "th"])
        if not cells:
            return None

        def _cell(key: str, fallback: int = -1) -> str:
            idx = col_indices.get(key, fallback)
            if idx < 0 or idx >= len(cells):
                return ""
            return cells[idx].get_text(strip=True)

        # カラム位置が特定できない場合は位置でフォールバック
        # netkeiba成績テーブルの列順（33列）:
        # 0:日付, 1:開催, 2:天気, 3:R, 4:レース名, 5:映像, 6:頭数,
        # 7:枠番, 8:馬番, 9:オッズ, 10:人気, 11:着順, 12:騎手,
        # 13:斤量, 14:距離, 15:水分量, 16:馬場, 17:馬場指数,
        # 18:タイム, 19:着差, 20-24:各種指数, 25:通過, 26:ペース,
        # 27:上り, 28:馬体重, 29-32:その他
        date_str = _cell("日付", 0)
        race_name = _cell("レース名", 4)
        finish_pos_str = _cell("着順", 11)
        jockey_name = _cell("騎手", 12)
        dist_str = _cell("距離", 14)
        track_cond = _cell("馬場", 16)
        time_str = _cell("タイム", 18)
        last3f_str = _cell("上り", 27)

        # 着順が数値でない行はスキップ（中止, 除外, 取消 等）
        try:
            finish_position = int(finish_pos_str)
        except ValueError:
            return None

        # race_idをリンクから取得
        race_id = ""
        race_name_idx = col_indices.get("レース名", 4)
        if 0 <= race_name_idx < len(cells):
            race_link = cells[race_name_idx].find("a", href=True)
            if race_link:
                href = race_link.get("href", "")
                rid_m = re.search(r"(?:race_id=|/race/)(\d+)", href)
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

        return {
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
            html = await self.fetch(url, encoding="euc-jp")
        except Exception as e:
            self.logger.warning("過去成績取得失敗 (horse_id=%s): %s", horse_id, e)
            return []

        soup = self.parse_html(html)
        table = soup.find("table")
        if not table:
            return []

        # ヘッダー行でカラム位置を特定
        header_row = table.find("tr")
        col_indices: dict[str, int] = {}
        if header_row:
            col_indices = self._detect_column_indices(header_row)

        results: list[dict] = []
        rows = table.find_all("tr")
        # ヘッダー行をスキップしてデータ行を処理
        for tr in rows[1:]:
            result = self._parse_result_row(tr, col_indices)
            if result is not None:
                results.append(result)

        return results[:limit]

    def _parse_race_result_info(self, soup: BeautifulSoup, race_id: str) -> dict:
        """レース結果ページ（db.netkeiba.com）からレース情報を抽出する。

        Args:
            soup: レース結果ページのBeautifulSoupオブジェクト
            race_id: netkeibaのレースID

        Returns:
            race_id, name, grade, date, venue, course_type, distance,
            weather, track_condition を含む辞書
        """
        # レース名: div.data_intro > dl.racedata > dd > h1
        name_el = soup.select_one("div.data_intro dl.racedata h1") or soup.select_one(
            "div.data_intro h1"
        )
        race_name = name_el.get_text(strip=True) if name_el else ""

        # コース情報: h1直後の <p><span>
        #   例: 芝左2400m / 天候 : 晴 / 芝 : 良 / 発走 : 15:40
        #   ダートは「ダ左1800m / ... / ダート : 良 / ...」と馬場のキー名が変わる
        course_text = ""
        if name_el is not None:
            span_el = name_el.find_next("span")
            if span_el is not None:
                course_text = span_el.get_text(" ", strip=True)
        if not course_text:
            intro_el = soup.select_one("div.data_intro")
            course_text = intro_el.get_text(" ", strip=True) if intro_el else ""

        # 距離とコース種別（"芝左2400m" / "ダ左1800m" / "障芝2910m"）
        distance = 0
        course_type = ""
        course_match = re.search(r"([芝ダ障][^/\d]{0,3}?)(\d{3,4})m", course_text)
        if course_match:
            course_type = "ダート" if "ダ" in course_match.group(1) else "芝"
            distance = int(course_match.group(2))

        # 天候・馬場状態（"キー : 値" を "/" 区切りで並べたテキスト）
        weather = ""
        track_condition = ""
        for segment in course_text.split("/"):
            key, _, value = segment.partition(":")
            key = key.strip()
            value = value.strip()
            if not value:
                continue
            if key == "天候":
                weather = value
            elif key in ("芝", "ダート"):
                track_condition = value

        # 開催日: <p class="smalltxt">2024年05月26日 2回東京12日目 ...</p>
        race_date = ""
        smalltxt_el = soup.select_one("p.smalltxt")
        if smalltxt_el:
            date_match = re.search(
                r"(\d{4})年(\d{1,2})月(\d{1,2})日", smalltxt_el.get_text()
            )
            if date_match:
                race_date = (
                    f"{date_match.group(1)}-"
                    f"{int(date_match.group(2)):02d}-"
                    f"{int(date_match.group(3)):02d}"
                )

        return {
            "race_id": race_id,
            "name": race_name,
            "grade": _normalize_grade(race_name),
            "date": race_date,
            "venue": venue_from_race_id(race_id),
            "course_type": course_type,
            "distance": distance,
            "weather": weather,
            "track_condition": track_condition,
        }

    def _parse_race_result_row(self, row, col_indices: dict[str, int]) -> dict | None:
        """着順テーブルの1行をパースする。着順が非数値の行はNoneを返す。

        Args:
            row: BeautifulSoupのtrタグ（データ行）
            col_indices: _detect_column_indices()で取得したカラム名→インデックス

        Returns:
            着順情報の辞書。取消/中止/除外（着順が非数値）の行はNone。
        """
        # 一部のtdは非標準タグ <diary_snap_cut> に包まれるが、find_all("td")では
        # 25個のtdがそのまま取得できる
        cells = row.find_all("td")
        if not cells:
            return None

        def _cell(col_name: str):
            index = col_indices.get(
                col_name, _RESULT_COLUMN_FALLBACK.get(col_name, -1)
            )
            if index < 0 or index >= len(cells):
                return None
            return cells[index]

        def _text(col_name: str) -> str:
            cell = _cell(col_name)
            return cell.get_text(strip=True) if cell is not None else ""

        # 取消/中止/除外は着順が「取」「中」「除」等の非数値になる
        finish_position = _to_int(_text("着順"))
        if finish_position is None:
            return None

        horse_id, horse_name = _link_id_and_name(_cell("馬名"), "horse")
        jockey_id, jockey_name = _link_id_and_name(_cell("騎手"), "jockey")
        trainer_id, trainer_name = _link_id_and_name(_cell("調教師"), "trainer")

        return {
            "horse_id": horse_id,
            "horse_name": horse_name,
            "horse_number": _to_int(_text("馬番")),
            "finish_position": finish_position,
            "time": _text("タイム") or None,
            "margin": _text("着差") or None,
            "last_3f": _to_float(_text("上り")),
            "jockey_id": jockey_id,
            "jockey_name": jockey_name,
            "trainer_id": trainer_id,
            "trainer_name": trainer_name,
        }

    def _parse_payout_tables(self, soup: BeautifulSoup) -> list[dict]:
        """払戻テーブル（table.pay_table_01 が2つ）から払戻金を抽出する。

        Args:
            soup: レース結果ページのBeautifulSoupオブジェクト

        Returns:
            {"bet_type", "combination", "amount"} の辞書のリスト
        """
        payouts: list[dict] = []
        for table in soup.select("table.pay_table_01"):
            for row in table.find_all("tr"):
                header_cell = row.find("th")
                if header_cell is None:
                    continue
                # 券種はthのclassで判定する（テキストは券種名だが表記揺れがある）
                bet_type = next(
                    (
                        _BET_TYPE_BY_CLASS[class_name]
                        for class_name in header_cell.get("class", [])
                        if class_name in _BET_TYPE_BY_CLASS
                    ),
                    "",
                )
                if not bet_type:
                    continue

                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                # 複勝・ワイドの複数払戻は1つのtd内で<br/>区切り。
                # stripped_stringsでテキストノードごとに分解できる。
                combinations = list(cells[0].stripped_strings)
                amounts = list(cells[1].stripped_strings)
                for combination, amount_text in zip(
                    combinations, amounts, strict=False
                ):
                    # 組番は空白を除去（"5 - 15" → "5-15"）。区切り記号は原文のまま
                    normalized_combination = re.sub(r"\s+", "", combination)
                    amount = _to_int(amount_text.replace(",", ""))
                    if not normalized_combination or amount is None:
                        continue
                    payouts.append(
                        {
                            "bet_type": bet_type,
                            "combination": normalized_combination,
                            "amount": amount,
                        }
                    )
        return payouts

    async def fetch_race_result(self, race_id: str) -> dict:
        """db.netkeiba.com のレース結果ページから全着順と払戻を取得する。

        Args:
            race_id: netkeibaのレースID（例: "202405021212"）

        Returns:
            {"race": {...}, "results": [...], "payouts": [...]} の辞書。
            エラー時・着順テーブルが取れない場合は空dict `{}` を返す。
        """
        url = f"{self.DB_URL}/race/{race_id}/"
        try:
            html = await self.fetch(url, encoding="euc-jp")
        except Exception as e:
            self.logger.warning("レース結果取得失敗 (race_id=%s): %s", race_id, e)
            return {}

        soup = self.parse_html(html)
        table = soup.select_one("table.race_table_01")
        if table is None:
            self.logger.warning("着順テーブルが見つかりません (race_id=%s)", race_id)
            return {}

        rows = table.find_all("tr")
        header_row = rows[0] if rows else None
        col_indices = (
            self._detect_column_indices(header_row) if header_row is not None else {}
        )

        results: list[dict] = []
        for row in rows[1:]:
            parsed_row = self._parse_race_result_row(row, col_indices)
            if parsed_row is not None:
                results.append(parsed_row)

        if not results:
            self.logger.warning("着順データが空です (race_id=%s)", race_id)
            return {}

        return {
            "race": self._parse_race_result_info(soup, race_id),
            "results": results,
            "payouts": self._parse_payout_tables(soup),
        }

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
