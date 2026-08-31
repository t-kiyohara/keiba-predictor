"""Tests for scraping utilities: date targeting, HTML parsing, weather client."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.scrapers.base import BaseScraper
from app.scrapers.jra import JraScraper, get_target_race_dates
from app.scrapers.netkeiba import NetkeibaScraper
from app.scrapers.weather import VENUE_COORDINATES, WEATHER_JP, WeatherClient

# ---------------------------------------------------------------------------
# HTMLフィクスチャ定義
# ---------------------------------------------------------------------------

# JRA今週の重賞ページフィクスチャ（年はdate.today().yearに合わせる）
JRA_THISWEEK_HTML = """
<html><body>
<div class="content">
  <div class="race_unit g1">
    <div class="head">
      <dt>4月13日（日曜）</dt>
      <dd><div class="race_title"><div class="txt">
        <h3>天皇賞（春）（GⅠ）</h3>
        <p>京都競馬場　芝3200メートル</p>
      </div></div></dd>
    </div>
  </div>
  <div class="race_unit g2">
    <div class="head">
      <dt>4月12日（土曜）</dt>
      <dd><div class="race_title"><div class="txt">
        <h3>青葉賞（GⅡ）</h3>
        <p>東京競馬場　芝2400メートル</p>
      </div></div></dd>
    </div>
  </div>
  <div class="race_unit g2">
    <div class="head">
      <dt>4月13日（日曜）</dt>
      <dd><div class="race_title"><div class="txt">
        <h3>フローラステークス（GⅡ）</h3>
        <p>東京競馬場　芝2000メートル</p>
      </div></div></dd>
    </div>
  </div>
  <div class="race_unit g1">
    <div class="head">
      <dt>5月3日（土曜）</dt>
      <dd><div class="race_title"><div class="txt">
        <h3>NHKマイルカップ（GⅠ）</h3>
        <p>東京競馬場　芝1600メートル</p>
      </div></div></dd>
    </div>
  </div>
  <div class="race_unit g3">
    <div class="head">
      <dt>4月12日（土曜）</dt>
      <dd><div class="race_title"><div class="txt">
        <h3>福島牝馬ステークス（GⅢ）</h3>
        <p>福島競馬場　芝1800メートル</p>
      </div></div></dd>
    </div>
  </div>
</div>
</body></html>
"""

# JRA 障害グレードのテスト用HTML
JRA_JUMP_HTML = """
<html><body>
<div class="content">
  <div class="race_unit">
    <div class="head">
      <dt>4月13日（日曜）</dt>
      <dd><div class="race_title"><div class="txt">
        <h3>阪神スプリングジャンプ（J・GⅡ）</h3>
        <p>阪神競馬場　芝3900メートル</p>
      </div></div></dd>
    </div>
  </div>
</div>
</body></html>
"""

# netkeibaレース一覧フィクスチャ
RACE_LIST_HTML = """
<html><body>
<ul>
  <li><a href="https://race.netkeiba.com/race/shutuba.html?race_id=202606030501">1R</a></li>
  <li><a href="https://race.netkeiba.com/race/shutuba.html?race_id=202606030511">11R</a></li>
  <li><a href="https://race.netkeiba.com/race/shutuba.html?race_id=202609020511">11R</a></li>
</ul>
</body></html>
"""

# netkeiba出馬表フィクスチャ
SHUTUBA_HTML = """
<html><body>
<div class="RaceData01">15:45発走 / 2000m (芝) / 天気:晴</div>
<h1 class="RaceName">テストステークス(GⅠ)</h1>
<table class="Shutuba_Table">
<tr class="Header"><th class="Waku">枠</th><th class="Umaban">馬番</th>
<th class="CheckMark">印</th><th class="HorseInfo">馬名</th>
<th class="Barei">性齢</th><th class="Dredging">斤量</th>
<th class="Jockey">騎手</th><th class="Trainer">厩舎</th></tr>
<tr class="HorseList">
  <td class="Waku1 Txt_C">1</td>
  <td class="Umaban1 Txt_C">1</td>
  <td class="CheckMark">--</td>
  <td class="HorseInfo"><a href="https://db.netkeiba.com/horse/2019105943">テスト馬A</a></td>
  <td class="Barei Txt_C">牡4</td>
  <td class="Txt_C">58.0</td>
  <td class="Jockey"><a href="https://db.netkeiba.com/jockey/result/recent/01167/">テスト騎手A</a></td>
  <td class="Trainer"><a href="https://db.netkeiba.com/trainer/result/recent/01234/">テスト調教師A</a></td>
</tr>
<tr class="HorseList">
  <td class="Waku2 Txt_C">2</td>
  <td class="Umaban2 Txt_C">2</td>
  <td class="CheckMark">--</td>
  <td class="HorseInfo"><a href="https://db.netkeiba.com/horse/2020101234">テスト馬B</a></td>
  <td class="Barei Txt_C">牝3</td>
  <td class="Txt_C">54.0</td>
  <td class="Jockey"><a href="https://db.netkeiba.com/jockey/result/recent/00422/">テスト騎手B</a></td>
  <td class="Trainer"><a href="https://db.netkeiba.com/trainer/result/recent/01046/">テスト調教師B</a></td>
</tr>
<tr class="HorseList Cancel">
  <td class="Waku3 Txt_C">3</td>
  <td class="Umaban3 Txt_C">3</td>
  <td class="CheckMark">--</td>
  <td class="HorseInfo"><a href="https://db.netkeiba.com/horse/2020109999">取消馬C</a></td>
  <td class="Barei Txt_C">牡4</td>
  <td class="Txt_C">58.0</td>
  <td class="Jockey"><a href="https://db.netkeiba.com/jockey/result/recent/01999/">テスト騎手C</a></td>
  <td class="Trainer"><a href="https://db.netkeiba.com/trainer/result/recent/01999/">テスト調教師C</a></td>
</tr>
</table>
</body></html>
"""

# 出馬表テーブルなしフィクスチャ
SHUTUBA_NO_TABLE_HTML = """
<html><body>
<div class="RaceData01">15:45発走 / 2000m (芝) / 天気:晴</div>
<h1 class="RaceName">テストステークス(GⅠ)</h1>
<p>出馬表データが見つかりません</p>
</body></html>
"""

# ダートコース出馬表フィクスチャ
SHUTUBA_DIRT_HTML = """
<html><body>
<div class="RaceData01">16:00発走 / 1600m (ダート) / 天気:曇り</div>
<h1 class="RaceName">ダートレース(GⅡ)</h1>
<table class="Shutuba_Table">
<tr class="HorseList">
  <td class="Waku1 Txt_C">1</td>
  <td class="Umaban1 Txt_C">1</td>
  <td class="CheckMark">--</td>
  <td class="HorseInfo"><a href="https://db.netkeiba.com/horse/2021101111">ダート馬A</a></td>
  <td class="Barei Txt_C">牡4</td>
  <td class="Txt_C">57.0</td>
  <td class="Jockey"><a href="https://db.netkeiba.com/jockey/result/recent/01001/">騎手X</a></td>
  <td class="Trainer"><a href="https://db.netkeiba.com/trainer/result/recent/02001/">調教師X</a></td>
</tr>
</table>
</body></html>
"""

# 馬プロフィールフィクスチャ
HORSE_PROFILE_HTML = """
<html><head><title>テスト馬A（テスト牧場）</title></head>
<body>
<div class="db_main_box">
  <div class="horse_title">
    <h1>テスト馬A</h1>
  </div>
  <table class="db_prof_table">
    <tr><th>生年月日</th><td>2019年3月1日</td></tr>
    <tr><th>性齢</th><td>牡7</td></tr>
    <tr><th>調教師</th><td>テスト調教師</td></tr>
  </table>
</div>
</body></html>
"""

# 血統フィクスチャ（Ajax）
HORSE_PEDIGREE_HTML = """
<html><body>
<table class="blood_table">
<tr>
  <td><a href="/horse/pedigree/0000000001/">テスト父馬</a></td>
  <td><a href="/horse/pedigree/0000000002/">父の父</a></td>
</tr>
<tr>
  <td><a href="/horse/pedigree/0000000003/">テスト母馬</a></td>
  <td><a href="/horse/pedigree/0000000004/">母の父</a></td>
</tr>
<tr>
  <td><a href="/horse/pedigree/0000000005/">テスト母父馬</a></td>
  <td></td>
</tr>
</table>
</body></html>
"""

# 過去成績フィクスチャ（実際のnetkeiba AJAXテーブル構造に合わせた33列）
HORSE_RESULTS_HTML = """
<html><body>
<table>
<tr>
  <th>日付</th><th>開催</th><th>天気</th><th>R</th><th>レース名</th>
  <th>映像</th><th>頭数</th><th>枠番</th><th>馬番</th><th>オッズ</th><th>人気</th>
  <th>着順</th><th>騎手</th><th>斤量</th><th>距離</th><th>水分量</th><th>馬場</th>
  <th>馬場指数</th><th>タイム</th><th>着差</th><th>ﾀｲﾑ指数</th><th>ﾀｲﾑ指数M</th>
  <th>ｽﾀｰﾄ指数</th><th>追走指数</th><th>上がり指数</th><th>通過</th><th>ペース</th>
  <th>上り</th><th>馬体重</th><th>厩舎ｺﾒﾝﾄ</th><th>備考</th>
  <th>勝ち馬(2着馬)</th><th>賞金</th>
</tr>
<tr>
  <td>2024/04/28</td><td>阪神1回1日</td><td>晴</td><td>11</td>
  <td><a href="https://db.netkeiba.com/race/202409020511/">天皇賞（春）</a></td>
  <td></td><td>18</td><td>3</td><td>5</td><td>3.5</td><td>2</td>
  <td>1</td><td>テスト騎手A</td><td>58.0</td><td>芝3200</td><td></td><td>良</td>
  <td>100</td><td>3:14.2</td><td>-</td><td>120</td><td>120</td>
  <td>89</td><td>83</td><td>108</td><td>5-5</td><td>36.0-34.0</td>
  <td>34.8</td><td>480(+2)</td><td></td><td></td><td></td><td>10000.0</td>
</tr>
<tr>
  <td>2024/02/10</td><td>東京1回2日</td><td>晴</td><td>9</td>
  <td><a href="https://db.netkeiba.com/race/202405050905/">日経新春杯</a></td>
  <td></td><td>16</td><td>5</td><td>9</td><td>5.1</td><td>3</td>
  <td>2</td><td>テスト騎手B</td><td>58.0</td><td>芝2200</td><td></td><td>良</td>
  <td>98</td><td>2:11.5</td><td>0.4</td><td>115</td><td>115</td>
  <td>88</td><td>80</td><td>105</td><td>3-3</td><td>35.0-35.0</td>
  <td>35.2</td><td>478(0)</td><td></td><td></td><td></td><td>5000.0</td>
</tr>
<tr>
  <td>2023/12/25</td><td>中山1回1日</td><td>曇</td><td>10</td>
  <td><a href="https://db.netkeiba.com/race/202406031010/">有馬記念</a></td>
  <td></td><td>16</td><td>2</td><td>3</td><td>8.0</td><td>4</td>
  <td>中止</td><td>テスト騎手A</td><td>58.0</td><td>芝2500</td><td></td><td>良</td>
  <td></td><td></td><td></td><td></td><td></td>
  <td></td><td></td><td></td><td></td><td></td>
  <td></td><td></td><td></td><td>競走中止</td><td></td><td></td>
</tr>
</table>
</body></html>
"""


# db.netkeiba.com レース結果ページフィクスチャ（着順テーブル25列 + 払戻2テーブル）
# - 3行目は取消行（着順が非数値、単勝="---"、馬体重="計不"）
# - 2行目の馬名セルは非標準タグ <diary_snap_cut> に包まれている
# - 調教師セルはaタグの前に [西]/[東] テキストが付く
RACE_RESULT_HTML = """
<html><body>
<div class="data_intro">
  <dl class="racedata fc">
    <dt>12 R</dt>
    <dd>
      <h1>第91回東京優駿(GI)</h1>
      <p><diary_snap_cut>
        <span>芝左2400m / 天候 : 晴 / 芝 : 良 / 発走 : 15:40</span>
      </diary_snap_cut></p>
    </dd>
  </dl>
  <p class="smalltxt">2024年05月26日 2回東京12日目&nbsp;3歳オープン</p>
</div>
<table class="race_table_01">
<tr>
  <th>着順</th><th>枠番</th><th>馬番</th><th>馬名</th><th>性齢</th><th>斤量</th>
  <th>騎手</th><th>タイム</th><th>着差</th><th>ﾀｲﾑ指数</th><th>ﾀｲﾑ指数M</th>
  <th>ｽﾀｰﾄ指数</th><th>追走指数</th><th>上がり指数</th><th>通過</th><th>上り</th>
  <th>単勝</th><th>人気</th><th>馬体重</th><th>調教ﾀｲﾑ</th><th>厩舎ｺﾒﾝﾄ</th>
  <th>備考</th><th>調教師</th><th>馬主</th><th>賞金(万円)</th>
</tr>
<tr>
  <td>1</td><td>5</td><td>10</td>
  <td><a href="/horse/2021105165/">テスト馬A</a></td>
  <td>牡3</td><td>57</td>
  <td><a href="/jockey/result/recent/01167/">テスト騎手A</a></td>
  <td>2:24.3</td><td></td>
  <td></td><td></td><td></td><td></td><td></td>
  <td>2-2-2-2</td><td>33.5</td><td>46.6</td><td>12</td><td>488(+2)</td>
  <td></td><td></td><td></td>
  <td><diary_snap_cut>[西]
    <a href="/trainer/result/recent/01126/">テスト調教師A</a></diary_snap_cut></td>
  <td><a href="/owner/199401/">テストオーナーA</a></td><td>30000.0</td>
</tr>
<tr>
  <td>2</td><td>8</td><td>15</td>
  <td><diary_snap_cut><a href="/horse/2021104976/">テスト馬B</a></diary_snap_cut></td>
  <td>牡3</td><td>57</td>
  <td><a href="/jockey/result/recent/01088/">テスト騎手B</a></td>
  <td>2:24.4</td><td>クビ</td>
  <td></td><td></td><td></td><td></td><td></td>
  <td>5-5-5-4</td><td>33.9</td><td>2.1</td><td>1</td><td>512(0)</td>
  <td></td><td></td><td></td>
  <td><diary_snap_cut>[東]
    <a href="/trainer/result/recent/01110/">テスト調教師B</a></diary_snap_cut></td>
  <td><a href="/owner/475400/">テストオーナーB</a></td><td>12000.0</td>
</tr>
<tr>
  <td>取</td><td>3</td><td>5</td>
  <td><a href="/horse/2021109999/">取消馬C</a></td>
  <td>牝3</td><td>55</td>
  <td><a href="/jockey/result/recent/01999/">テスト騎手C</a></td>
  <td></td><td></td>
  <td></td><td></td><td></td><td></td><td></td>
  <td></td><td></td><td>---</td><td></td><td>計不</td>
  <td></td><td></td><td></td>
  <td><diary_snap_cut>[西]
    <a href="/trainer/result/recent/01999/">テスト調教師C</a></diary_snap_cut></td>
  <td><a href="/owner/999999/">テストオーナーC</a></td><td></td>
</tr>
</table>
<table class="pay_table_01">
<tr><th class="tan">単勝</th><td class="txt_r">10</td><td class="txt_r">4,660</td>
    <td class="txt_r">12</td></tr>
<tr><th class="fuku">複勝</th>
    <td class="txt_r">10<br/>15<br/>13</td>
    <td class="txt_r">1,020<br/>240<br/>210</td>
    <td class="txt_r">12<br/>3<br/>2</td></tr>
<tr><th class="waku">枠連</th><td class="txt_r">5 - 8</td><td class="txt_r">2,300</td>
    <td class="txt_r">10</td></tr>
<tr><th class="uren">馬連</th><td class="txt_r">10 - 15</td>
    <td class="txt_r">14,220</td><td class="txt_r">45</td></tr>
</table>
<table class="pay_table_01">
<tr><th class="wide">ワイド</th>
    <td class="txt_r">10 - 15<br/>10 - 13<br/>13 - 15</td>
    <td class="txt_r">4,240<br/>3,290<br/>640</td>
    <td class="txt_r">44<br/>36<br/>6</td></tr>
<tr><th class="utan">馬単</th><td class="txt_r">10 → 15</td>
    <td class="txt_r">32,600</td><td class="txt_r">101</td></tr>
<tr><th class="sanfuku">三連複</th><td class="txt_r">10 - 13 - 15</td>
    <td class="txt_r">25,180</td><td class="txt_r">78</td></tr>
<tr><th class="santan">三連単</th><td class="txt_r">10 → 15 → 13</td>
    <td class="txt_r">212,300</td><td class="txt_r">601</td></tr>
</table>
</body></html>
"""

# ダートのレース結果フィクスチャ（馬場キーが「ダート」、ASCIIグレード (GIII)）
RACE_RESULT_DIRT_HTML = """
<html><body>
<div class="data_intro">
  <dl class="racedata fc">
    <dt>11 R</dt>
    <dd>
      <h1>第41回テストダート記念(GIII)</h1>
      <p><span>ダ左1600m / 天候 : 曇 / ダート : 稍重 / 発走 : 15:40</span></p>
    </dd>
  </dl>
  <p class="smalltxt">2024年02月18日 1回東京8日目</p>
</div>
<table class="race_table_01">
<tr><th>着順</th><th>枠番</th><th>馬番</th><th>馬名</th><th>性齢</th><th>斤量</th>
    <th>騎手</th><th>タイム</th><th>上り</th></tr>
<tr><td>1</td><td>2</td><td>3</td>
    <td><a href="/horse/2020101111/">ダート馬A</a></td>
    <td>牡5</td><td>57</td>
    <td><a href="/jockey/result/recent/01001/">騎手X</a></td>
    <td>1:34.5</td><td>36.1</td></tr>
</table>
</body></html>
"""

# 障害のレース結果フィクスチャ（ASCIIの障害グレード (JGIII)、コース「障芝」）
RACE_RESULT_JUMP_HTML = """
<html><body>
<div class="data_intro">
  <dl class="racedata fc">
    <dt>9 R</dt>
    <dd>
      <h1>第26回テスト障害ステークス(JGIII)</h1>
      <p><span>障芝3000m / 天候 : 晴 / 芝 : 良 / 発走 : 15:25</span></p>
    </dd>
  </dl>
  <p class="smalltxt">2024年04月13日 3回中山6日目</p>
</div>
<table class="race_table_01">
<tr><th>着順</th><th>枠番</th><th>馬番</th><th>馬名</th><th>性齢</th><th>斤量</th>
    <th>騎手</th><th>タイム</th><th>上り</th></tr>
<tr><td>1</td><td>1</td><td>1</td>
    <td><a href="/horse/2019102222/">障害馬A</a></td>
    <td>牡7</td><td>63</td>
    <td><a href="/jockey/result/recent/01002/">騎手Y</a></td>
    <td>3:19.8</td><td></td></tr>
</table>
</body></html>
"""

# 着順テーブルなしのレース結果フィクスチャ
RACE_RESULT_NO_TABLE_HTML = """
<html><body>
<div class="data_intro"><dl class="racedata">
  <dd><h1>存在しないレース</h1></dd>
</dl></div>
<p>データがありません</p>
</body></html>
"""


# ---------------------------------------------------------------------------
# get_target_race_dates
# ---------------------------------------------------------------------------


class TestGetTargetRaceDates:
    def test_get_target_race_dates_saturday(self):
        """土曜日 → 当日(土) + 翌日(日) の2日分を返す。"""
        saturday = date(2024, 4, 27)  # weekday() == 5
        assert saturday.weekday() == 5, "fixture is not a Saturday"
        result = get_target_race_dates(saturday)
        assert result == [date(2024, 4, 27), date(2024, 4, 28)]

    def test_get_target_race_dates_sunday(self):
        """日曜日 → 当日(日)のみ返す。"""
        sunday = date(2024, 4, 28)  # weekday() == 6
        assert sunday.weekday() == 6, "fixture is not a Sunday"
        result = get_target_race_dates(sunday)
        assert result == [date(2024, 4, 28)]

    def test_get_target_race_dates_weekday(self):
        """平日(水曜) → 次の土曜 + 日曜を返す。"""
        wednesday = date(2024, 4, 24)  # weekday() == 2
        assert wednesday.weekday() == 2, "fixture is not a Wednesday"
        result = get_target_race_dates(wednesday)
        # 2024-04-24(水) の次の土曜は 2024-04-27
        assert result == [date(2024, 4, 27), date(2024, 4, 28)]

    def test_get_target_race_dates_monday(self):
        """月曜 → 次の土曜 + 日曜を返す。"""
        monday = date(2024, 4, 22)  # weekday() == 0
        assert monday.weekday() == 0, "fixture is not a Monday"
        result = get_target_race_dates(monday)
        # 2024-04-22(月) の次の土曜は 2024-04-27
        assert result == [date(2024, 4, 27), date(2024, 4, 28)]

    def test_get_target_race_dates_friday(self):
        """金曜 → 翌日の土曜 + 日曜を返す。"""
        friday = date(2024, 4, 26)  # weekday() == 4
        assert friday.weekday() == 4, "fixture is not a Friday"
        result = get_target_race_dates(friday)
        # 2024-04-26(金) の次の日が土曜 2024-04-27
        assert result == [date(2024, 4, 27), date(2024, 4, 28)]


# ---------------------------------------------------------------------------
# BaseScraper.parse_html
# ---------------------------------------------------------------------------


class TestBaseScraperParseHtml:
    def test_base_scraper_parse_html(self):
        """HTMLパースが正しく動作するか確認する。"""
        scraper = BaseScraper()
        html = "<html><body><h1>テスト</h1><p class='info'>情報</p></body></html>"
        soup = scraper.parse_html(html)

        assert soup.find("h1") is not None
        assert soup.find("h1").text == "テスト"
        assert soup.find("p", class_="info") is not None
        assert soup.find("p", class_="info").text == "情報"

    def test_base_scraper_parse_html_returns_beautifulsoup(self):
        """parse_html が BeautifulSoup インスタンスを返すことを確認する。"""
        from bs4 import BeautifulSoup

        scraper = BaseScraper()
        soup = scraper.parse_html("<html></html>")
        assert isinstance(soup, BeautifulSoup)


# ---------------------------------------------------------------------------
# WeatherClient — venue coordinates
# ---------------------------------------------------------------------------


class TestWeatherVenueCoordinates:
    EXPECTED_VENUES = [
        "東京",
        "中山",
        "阪神",
        "京都",
        "中京",
        "小倉",
        "新潟",
        "札幌",
        "函館",
        "福島",
    ]

    def test_weather_venue_coordinates(self):
        """全10競馬場の座標が VENUE_COORDINATES に定義されているか確認する。"""
        assert len(VENUE_COORDINATES) == 10

        for venue in self.EXPECTED_VENUES:
            assert venue in VENUE_COORDINATES, f"{venue} が VENUE_COORDINATES に未定義"
            lat, lon = VENUE_COORDINATES[venue]
            assert isinstance(lat, float), f"{venue} の緯度が float ではない"
            assert isinstance(lon, float), f"{venue} の経度が float ではない"
            # 日本の緯度経度範囲チェック
            assert 24.0 <= lat <= 46.0, f"{venue} の緯度が日本の範囲外: {lat}"
            assert 122.0 <= lon <= 154.0, f"{venue} の経度が日本の範囲外: {lon}"


# ---------------------------------------------------------------------------
# WeatherClient — Japanese weather mapping
# ---------------------------------------------------------------------------


class TestWeatherJapaneseMapping:
    def test_weather_japanese_mapping(self):
        """天気の日本語変換が正しいか確認する。"""
        assert WEATHER_JP["Clear"] == "晴れ"
        assert WEATHER_JP["Clouds"] == "曇り"
        assert WEATHER_JP["Rain"] == "雨"
        assert WEATHER_JP["Snow"] == "雪"

    def test_weather_japanese_mapping_drizzle(self):
        """小雨が正しくマッピングされているか確認する。"""
        assert WEATHER_JP["Drizzle"] == "小雨"

    def test_weather_japanese_mapping_thunderstorm(self):
        """雷雨が正しくマッピングされているか確認する。"""
        assert WEATHER_JP["Thunderstorm"] == "雷雨"

    def test_weather_japanese_mapping_completeness(self):
        """主要な天気種別が全てマッピングされているか確認する。"""
        required_keys = ["Clear", "Clouds", "Rain", "Drizzle", "Thunderstorm", "Snow"]
        for key in required_keys:
            assert key in WEATHER_JP, f"'{key}' が WEATHER_JP に未定義"
            assert WEATHER_JP[key], f"'{key}' のマッピングが空"


# ---------------------------------------------------------------------------
# WeatherClient — no API key fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weather_client_no_api_key_returns_default():
    """APIキーが空の場合はデフォルト値を返すことを確認する。"""
    client = WeatherClient(api_key="")
    result = await client.get_weather("東京")
    assert isinstance(result, dict)
    assert "weather" in result
    assert "temp" in result
    assert "humidity" in result
    assert "description" in result


@pytest.mark.asyncio
async def test_weather_client_unknown_venue_returns_default():
    """未定義の競馬場名を渡した場合はデフォルト値を返すことを確認する。"""
    client = WeatherClient(api_key="dummy_key")
    result = await client.get_weather("未定義競馬場")
    assert isinstance(result, dict)
    assert result["weather"] == "不明"


def test_weather_client_successful_api_response():
    """HTTPレスポンスをモックして晴れ天気データが正しく変換されること"""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    api_response_json = {
        "weather": [{"main": "Clear", "description": "clear sky"}],
        "main": {"temp": 22.5, "humidity": 40},
    }

    mock_response = MagicMock()
    mock_response.json.return_value = api_response_json
    mock_response.raise_for_status = MagicMock()

    mock_async_client = AsyncMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=False)
    mock_async_client.get = AsyncMock(return_value=mock_response)

    client = WeatherClient(api_key="test_api_key_12345")

    with patch("httpx.AsyncClient", return_value=mock_async_client):
        result = asyncio.run(client.get_weather("東京"))

    assert result["weather"] == "晴れ"
    assert result["temp"] == pytest.approx(22.5)
    assert result["humidity"] == 40
    assert result["description"] == "clear sky"


# ---------------------------------------------------------------------------
# JraScraper.fetch_graded_races
# ---------------------------------------------------------------------------


class TestJraFetchGradedRaces:
    """JraScraper.fetch_graded_races() のHTMLパーステスト。

    フィクスチャHTMLは当年（date.today().year）の4月日付を使用する。
    JraScraper.fetch_graded_races() は date.today().year で年を決定するため。
    """

    @pytest.mark.asyncio
    async def test_grade_normalization_g1(self):
        """GⅠ表記がG1に正規化されること。"""
        from datetime import date as d

        scraper = JraScraper()
        # フィクスチャHTMLの「4月13日」に合わせて対象日を設定
        target = [d(d.today().year, 4, 13)]
        mock = AsyncMock(return_value=JRA_THISWEEK_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_graded_races(target)
        g1_races = [r for r in result if r["grade"] == "G1"]
        assert len(g1_races) >= 1
        names = [r["name"] for r in g1_races]
        assert any("天皇賞" in n for n in names)

    @pytest.mark.asyncio
    async def test_venue_and_distance_extraction(self):
        """会場名と距離が正しく抽出されること。"""
        from datetime import date as d

        scraper = JraScraper()
        target = [d(d.today().year, 4, 13)]
        mock = AsyncMock(return_value=JRA_THISWEEK_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_graded_races(target)
        # 天皇賞（春）: 京都 / 3200メートル
        tenno = next((r for r in result if "天皇賞" in r.get("name", "")), None)
        assert tenno is not None
        assert tenno["venue"] == "京都"
        assert tenno["distance"] == 3200

    @pytest.mark.asyncio
    async def test_target_dates_filter(self):
        """target_datesに含まれない日付のレースが除外されること。"""
        from datetime import date as d

        scraper = JraScraper()
        # 4/12（土）のみ取得
        target_saturday = [d(d.today().year, 4, 12)]
        mock = AsyncMock(return_value=JRA_THISWEEK_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_graded_races(target_saturday)
        # 4/13の天皇賞は含まれないこと
        assert all(r["date"] == d(d.today().year, 4, 12) for r in result)
        # 4/12の青葉賞は含まれること
        names = [r["name"] for r in result]
        assert any("青葉賞" in n for n in names)

    @pytest.mark.asyncio
    async def test_no_matching_races_returns_empty(self):
        """対象日に該当レースがない場合は空リストを返すこと。"""
        from datetime import date as d

        scraper = JraScraper()
        # HTML内に存在しない日付
        target = [d(d.today().year, 6, 15)]
        mock = AsyncMock(return_value=JRA_THISWEEK_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_graded_races(target)
        assert result == []

    @pytest.mark.asyncio
    async def test_jump_grade_normalization(self):
        """障害グレード（J・GⅡ等）が正規化されること。"""
        from datetime import date as d

        scraper = JraScraper()
        target = [d(d.today().year, 4, 13)]
        mock = AsyncMock(return_value=JRA_JUMP_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_graded_races(target)
        assert len(result) >= 1
        assert result[0]["grade"] == "G2"


# 単勝オッズAPIフィクスチャ（確定レース）
ODDS_API_RESPONSE = json.dumps(
    {
        "status": "result",
        "data": {
            "official_datetime": "2026-04-27 10:00:00",
            "odds": {
                "1": {"01": ["76.9", "0.0", "10"], "13": ["2.1", "0.0", "1"]},
                "2": {"01": ["11.6", "22.1", "15"]},
            },
        },
        "update_count": "0",
        "reason": "",
    }
)

# 単勝オッズAPIフィクスチャ（未発売/存在しないレース: dataが空文字列）
ODDS_API_RESPONSE_NOT_AVAILABLE = json.dumps(
    {"status": "middle", "data": "", "update_count": "0", "reason": ""}
)

# 単勝オッズAPIフィクスチャ（取消馬など数値変換できないオッズを含む）
ODDS_API_RESPONSE_WITH_SCRATCH = json.dumps(
    {
        "status": "result",
        "data": {
            "official_datetime": "2026-04-27 10:00:00",
            "odds": {
                "1": {"01": ["5.2", "0.0", "3"], "02": ["---", "0.0", "0"]},
            },
        },
        "update_count": "0",
        "reason": "",
    }
)


# ---------------------------------------------------------------------------
# NetkeibaScraper.fetch_race_entries
# ---------------------------------------------------------------------------


class TestNetkeibaFetchRaceEntries:
    """NetkeibaScraper.fetch_race_entries() のHTMLパーステスト。"""

    @pytest.mark.asyncio
    async def test_race_info_extraction(self):
        """レース名・距離・コース種別が正しく抽出されること。"""
        scraper = NetkeibaScraper()
        race_id = "202409020511"
        with patch.object(scraper, "fetch", new=AsyncMock(return_value=SHUTUBA_HTML)):
            result = await scraper.fetch_race_entries(race_id)
        assert result != {}
        ri = result["race_info"]
        assert ri["race_id"] == race_id
        assert "テストステークス" in ri["name"]
        assert ri["distance"] == 2000
        assert ri["course_type"] == "芝"

    @pytest.mark.asyncio
    async def test_grade_extraction(self):
        """グレードがレース名から正しく抽出されること。"""
        scraper = NetkeibaScraper()
        with patch.object(scraper, "fetch", new=AsyncMock(return_value=SHUTUBA_HTML)):
            result = await scraper.fetch_race_entries("202409020511")
        assert result["race_info"]["grade"] == "G1"

    @pytest.mark.asyncio
    async def test_entries_parsing(self):
        """出走馬リストが正しくパースされること（ID・名前・斤量）。"""
        scraper = NetkeibaScraper()
        with patch.object(scraper, "fetch", new=AsyncMock(return_value=SHUTUBA_HTML)):
            result = await scraper.fetch_race_entries("202409020511")
        entries = result["entries"]
        # 取消馬(Cancel class)を除いた2頭
        assert len(entries) == 2
        horse_a = next(e for e in entries if e["horse_name"] == "テスト馬A")
        assert horse_a["horse_id"] == "2019105943"
        assert horse_a["weight"] == 58.0
        assert horse_a["jockey_id"] == "01167"
        assert horse_a["trainer_id"] == "01234"
        assert horse_a["post_position"] == 1
        assert horse_a["horse_number"] == 1

    @pytest.mark.asyncio
    async def test_cancelled_horse_skipped(self):
        """取消馬（Cancelクラス）がエントリーから除外されること。"""
        scraper = NetkeibaScraper()
        with patch.object(scraper, "fetch", new=AsyncMock(return_value=SHUTUBA_HTML)):
            result = await scraper.fetch_race_entries("202409020511")
        entries = result["entries"]
        horse_ids = [e["horse_id"] for e in entries]
        # 取消馬のIDは含まれないこと
        assert "2020109999" not in horse_ids

    @pytest.mark.asyncio
    async def test_no_table_returns_empty_dict(self):
        """出馬表テーブルが見つからない場合は空dictを返すこと。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=SHUTUBA_NO_TABLE_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_race_entries("202409020511")
        assert result == {}

    @pytest.mark.asyncio
    async def test_dirt_course_type(self):
        """ダートコースのコース種別が正しく取得されること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=SHUTUBA_DIRT_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_race_entries("202409010511")
        assert result["race_info"]["course_type"] == "ダート"
        assert result["race_info"]["distance"] == 1600


# ---------------------------------------------------------------------------
# NetkeibaScraper.fetch_odds
# ---------------------------------------------------------------------------


class TestNetkeibaFetchOdds:
    """NetkeibaScraper.fetch_odds() の単勝オッズJSON APIパーステスト。"""

    @pytest.mark.asyncio
    async def test_fetch_odds_parses_zero_padded_keys_and_win_odds_only(self):
        """ゼロ埋め馬番キーがintに変換され、複勝("2")は無視され、
        人気順を捨てて単勝オッズのfloatのみ返ること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=ODDS_API_RESPONSE)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_odds("202604270511")
        assert result == {1: 76.9, 13: 2.1}

    @pytest.mark.asyncio
    async def test_fetch_odds_unavailable_race_returns_empty_dict(self):
        """未発売/存在しないレース（dataが空文字列）で空dictを返すこと。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=ODDS_API_RESPONSE_NOT_AVAILABLE)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_odds("202604270599")
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_odds_malformed_json_returns_empty_dict(self):
        """JSON破損時に空dictを返すこと。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value="{this is not valid json")
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_odds("202604270511")
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_odds_skips_non_numeric_values(self):
        """取消馬("---")等の数値変換できないオッズ要素をスキップすること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=ODDS_API_RESPONSE_WITH_SCRATCH)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_odds("202604270511")
        assert result == {1: 5.2}


# ---------------------------------------------------------------------------
# NetkeibaScraper.fetch_horse_profile
# ---------------------------------------------------------------------------


class TestNetkeibaFetchHorseProfile:
    """NetkeibaScraper.fetch_horse_profile() のHTMLパーステスト。"""

    @pytest.mark.asyncio
    async def test_horse_name_and_birthday_extraction(self):
        """馬名と誕生日が正しく抽出されること。"""
        scraper = NetkeibaScraper()
        with patch.object(
            scraper,
            "fetch",
            new=AsyncMock(side_effect=[HORSE_PROFILE_HTML, HORSE_PEDIGREE_HTML]),
        ):
            result = await scraper.fetch_horse_profile("2019105943")
        assert result["name"] == "テスト馬A"
        assert result["birthday"] == "2019-03-01"
        assert result["id"] == "2019105943"

    @pytest.mark.asyncio
    async def test_pedigree_extraction(self):
        """血統（父・母・母父）が正しく抽出されること。"""
        scraper = NetkeibaScraper()
        with patch.object(
            scraper,
            "fetch",
            new=AsyncMock(side_effect=[HORSE_PROFILE_HTML, HORSE_PEDIGREE_HTML]),
        ):
            result = await scraper.fetch_horse_profile("2019105943")
        assert result["sire"] == "テスト父馬"
        assert result["dam"] == "テスト母馬"
        assert result["dam_sire"] == "テスト母父馬"

    @pytest.mark.asyncio
    async def test_sex_extraction(self):
        """性別が正しく抽出されること。"""
        scraper = NetkeibaScraper()
        with patch.object(
            scraper,
            "fetch",
            new=AsyncMock(side_effect=[HORSE_PROFILE_HTML, HORSE_PEDIGREE_HTML]),
        ):
            result = await scraper.fetch_horse_profile("2019105943")
        assert result["sex"] == "牡"

    @pytest.mark.asyncio
    async def test_fetch_error_returns_empty_dict(self):
        """HTTPエラー時に空dictを返すこと。"""
        import httpx

        scraper = NetkeibaScraper()
        with patch.object(
            scraper,
            "fetch",
            new=AsyncMock(side_effect=httpx.HTTPError("404 Not Found")),
        ):
            result = await scraper.fetch_horse_profile("9999999999")
        assert result == {}


# ---------------------------------------------------------------------------
# NetkeibaScraper.fetch_horse_results
# ---------------------------------------------------------------------------


class TestNetkeibaFetchHorseResults:
    """NetkeibaScraper.fetch_horse_results() のHTMLパーステスト。"""

    @pytest.mark.asyncio
    async def test_results_parsing(self):
        """過去成績が正しくパースされること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=HORSE_RESULTS_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_horse_results("2019105943")
        # 着順が数値の2行のみ（中止行はスキップ）
        assert len(result) == 2
        # 1着の行
        first = result[0]
        assert first["finish_position"] == 1
        assert first["time"] == "3:14.2"
        assert first["last_3f"] == 34.8
        assert first["jockey_name"] == "テスト騎手A"

    @pytest.mark.asyncio
    async def test_limit_applied(self):
        """limitが正しく適用されること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=HORSE_RESULTS_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_horse_results("2019105943", limit=1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_non_numeric_position_skipped(self):
        """「中止」「除外」等の非数値着順行がスキップされること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=HORSE_RESULTS_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_horse_results("2019105943")
        positions = [r["finish_position"] for r in result]
        # 全て数値（中止行は除外済み）
        assert all(isinstance(p, int) for p in positions)
        # 中止行の有馬記念は含まれないこと（2行のみ）
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_race_id_extracted_from_link(self):
        """race_idがリンクhrefから正しく抽出されること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=HORSE_RESULTS_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_horse_results("2019105943")
        assert result[0]["race_id"] == "202409020511"

    @pytest.mark.asyncio
    async def test_distance_and_course_type_extracted(self):
        """距離とコース種別が正しく抽出されること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=HORSE_RESULTS_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_horse_results("2019105943")
        assert result[0]["course_type"] == "芝"
        assert result[0]["distance"] == 3200


# ---------------------------------------------------------------------------
# FetchService 永続化テスト
# ---------------------------------------------------------------------------


class TestFetchServicePersistence:
    """FetchService._persist_race_entries / _persist_horse_profile /
    _persist_horse_results のDB永続化テスト。"""

    # 出馬表データのフィクスチャ
    SAMPLE_ENTRIES_DATA = {
        "race_info": {
            "race_id": "202409020511",
            "name": "テストステークス",
            "date": "2026-04-27",
            "venue": "阪神",
            "grade": "G1",
            "distance": 2000,
            "course_type": "芝",
        },
        "entries": [
            {
                "horse_id": "2019105943",
                "horse_name": "テスト馬A",
                "jockey_id": "01167",
                "jockey_name": "テスト騎手A",
                "trainer_id": "01234",
                "trainer_name": "テスト調教師A",
                "post_position": 1,
                "horse_number": 1,
                "weight": 58.0,
            },
            {
                "horse_id": "2020101234",
                "horse_name": "テスト馬B",
                "jockey_id": "00422",
                "jockey_name": "テスト騎手B",
                "trainer_id": "01046",
                "trainer_name": "テスト調教師B",
                "post_position": 2,
                "horse_number": 2,
                "weight": 54.0,
            },
        ],
    }

    def test_persist_race_entries_creates_race(self, db):
        """_persist_race_entries がRaceレコードを作成すること。"""
        from app.models import Race
        from app.services.fetch_service import FetchService

        service = FetchService(db=db)
        service._persist_race_entries(self.SAMPLE_ENTRIES_DATA)

        race = db.get(Race, "202409020511")
        assert race is not None
        assert race.name == "テストステークス"
        assert race.venue == "阪神"
        assert race.grade == "G1"
        assert race.distance == 2000

    def test_persist_race_entries_creates_horses_and_entries(self, db):
        """_persist_race_entries がHorse/Entry/Jockey/Trainerレコードを作成すること。"""
        from app.models import Entry, Horse, Jockey, Trainer
        from app.services.fetch_service import FetchService

        service = FetchService(db=db)
        service._persist_race_entries(self.SAMPLE_ENTRIES_DATA)

        # 馬の確認
        horse_a = db.get(Horse, "2019105943")
        assert horse_a is not None
        assert horse_a.name == "テスト馬A"

        # 騎手・調教師の確認
        jockey = db.get(Jockey, "01167")
        assert jockey is not None
        trainer = db.get(Trainer, "01234")
        assert trainer is not None

        # エントリーの確認
        entries = db.query(Entry).filter_by(race_id="202409020511").all()
        assert len(entries) == 2

    def test_persist_horse_results_creates_stub_race(self, db):
        """_persist_horse_results が参照先Raceが存在しない場合に
        スタブRaceを作成すること。"""
        from app.models import Horse, Race, Result
        from app.services.fetch_service import FetchService

        # 馬を先に作成
        horse = Horse(id="2019105943", name="テスト馬A")
        db.add(horse)
        db.flush()

        service = FetchService(db=db)
        results = [
            {
                "race_id": "202312251010",
                "race_name": "有馬記念",
                "date": "2023-12-25",
                "venue": "中山",
                "distance": 2500,
                "course_type": "芝",
                "track_condition": "良",
                "finish_position": 3,
                "time": "2:31.5",
                "last_3f": 35.1,
                "jockey_name": "テスト騎手A",
            }
        ]
        service._persist_horse_results("2019105943", results)

        # スタブRaceが作成されること
        stub_race = db.get(Race, "202312251010")
        assert stub_race is not None
        assert stub_race.name == "有馬記念"
        # レース名にグレード表記がないためOPのまま
        assert stub_race.grade == "OP"
        # 成績データのtrack_conditionがスタブRaceに設定されること
        assert stub_race.track_condition == "良"

        # Resultが作成されること
        result_row = db.query(Result).filter_by(
            race_id="202312251010", horse_id="2019105943"
        ).first()
        assert result_row is not None
        assert result_row.finish_position == 3
        # 成績データのjockey_nameがResultに保存されること
        assert result_row.jockey_name == "テスト騎手A"

    def test_persist_horse_results_extracts_grade_from_race_name(self, db):
        """_persist_horse_results がレース名からグレードを抽出して
        スタブRaceのgradeに設定すること（OP固定をやめた挙動）。"""
        from app.models import Horse, Race
        from app.services.fetch_service import FetchService

        horse = Horse(id="2019105943", name="テスト馬A")
        db.add(horse)
        db.flush()

        service = FetchService(db=db)
        results = [
            {
                "race_id": "202312251099",
                "race_name": "KBSファンタジーS(GⅢ)",
                "date": "2023-12-25",
                "venue": "中山",
                "distance": 1800,
                "course_type": "芝",
                "track_condition": "稍重",
                "finish_position": 2,
                "time": "1:47.5",
                "last_3f": 34.2,
                "jockey_name": "テスト騎手Z",
            }
        ]
        service._persist_horse_results("2019105943", results)

        stub_race = db.get(Race, "202312251099")
        assert stub_race is not None
        assert stub_race.grade == "G3"

    def test_persist_horse_results_backfills_missing_track_condition(self, db):
        """既存Raceのtrack_conditionがNoneの場合、成績データの値で埋めること。"""
        from app.models import Horse, Race
        from app.services.fetch_service import FetchService

        horse = Horse(id="2019105943", name="テスト馬A")
        race = Race(
            id="202312251010",
            name="有馬記念",
            date=date(2023, 12, 25),
            venue="中山",
            course_type="芝",
            distance=2500,
            grade="G1",
            track_condition=None,
        )
        db.add_all([horse, race])
        db.flush()

        service = FetchService(db=db)
        results = [
            {
                "race_id": "202312251010",
                "race_name": "有馬記念",
                "date": "2023-12-25",
                "venue": "中山",
                "distance": 2500,
                "course_type": "芝",
                "track_condition": "重",
                "finish_position": 5,
                "time": "2:33.0",
                "last_3f": 36.0,
                "jockey_name": "テスト騎手A",
            }
        ]
        service._persist_horse_results("2019105943", results)

        updated_race = db.get(Race, "202312251010")
        assert updated_race.track_condition == "重"

    def test_persist_horse_results_does_not_overwrite_existing_track_condition(
        self, db
    ):
        """既存Raceのtrack_conditionが既に設定されている場合は上書きしないこと。"""
        from app.models import Horse, Race
        from app.services.fetch_service import FetchService

        horse = Horse(id="2019105943", name="テスト馬A")
        race = Race(
            id="202312251010",
            name="有馬記念",
            date=date(2023, 12, 25),
            venue="中山",
            course_type="芝",
            distance=2500,
            grade="G1",
            track_condition="良",
        )
        db.add_all([horse, race])
        db.flush()

        service = FetchService(db=db)
        results = [
            {
                "race_id": "202312251010",
                "race_name": "有馬記念",
                "date": "2023-12-25",
                "venue": "中山",
                "distance": 2500,
                "course_type": "芝",
                "track_condition": "重",
                "finish_position": 5,
                "time": "2:33.0",
                "last_3f": 36.0,
                "jockey_name": "テスト騎手A",
            }
        ]
        service._persist_horse_results("2019105943", results)

        updated_race = db.get(Race, "202312251010")
        assert updated_race.track_condition == "良"

    def test_persist_odds_updates_entry_by_horse_number(self, db):
        """_persist_odds が馬番マッチでEntry.oddsを更新し、
        該当馬番のオッズが無いEntryはNoneのままなこと。"""
        from app.models import Entry
        from app.services.fetch_service import FetchService
        from tests.factories import make_entry, make_horse, make_race

        race = make_race(db, race_id="202409020511")
        horse_a = make_horse(db, "2019105943", name="テスト馬A")
        horse_b = make_horse(db, "2020101234", name="テスト馬B")
        make_entry(db, race.id, horse_a.id, horse_number=1)
        make_entry(db, race.id, horse_b.id, horse_number=2)

        service = FetchService(db=db)
        service._persist_odds(race.id, {1: 2.1})

        entry_a = (
            db.query(Entry).filter_by(race_id=race.id, horse_id=horse_a.id).first()
        )
        entry_b = (
            db.query(Entry).filter_by(race_id=race.id, horse_id=horse_b.id).first()
        )
        assert entry_a.odds == 2.1
        assert entry_b.odds is None

    def test_persist_horse_profile_updates_horse(self, db):
        """_persist_horse_profile が Horse.sire/dam/dam_sire を更新すること。"""
        from app.models import Horse
        from app.services.fetch_service import FetchService

        # 馬を先に作成
        horse = Horse(id="2019105943", name="テスト馬A")
        db.add(horse)
        db.flush()

        service = FetchService(db=db)
        profile = {
            "id": "2019105943",
            "name": "テスト馬A",
            "sex": "牡",
            "birthday": "2019-03-01",
            "sire": "テスト父馬",
            "dam": "テスト母馬",
            "dam_sire": "テスト母父馬",
        }
        service._persist_horse_profile(profile)

        updated = db.get(Horse, "2019105943")
        assert updated is not None
        assert updated.sire == "テスト父馬"
        assert updated.dam == "テスト母馬"
        assert updated.dam_sire == "テスト母父馬"


# ---------------------------------------------------------------------------
# NetkeibaScraper.fetch_race_list_by_date
# ---------------------------------------------------------------------------

# テスト用HTMLフィクスチャ（課題指定のHTML構造）
RACE_LIST_NEW_HTML = """
<html><body>
<ul class="RaceList">
  <li><a href="../race/shutuba.html?race_id=202605060311&rf=race_list">3R</a></li>
  <li><a href="../race/shutuba.html?race_id=202605060311&rf=race_list">重複</a></li>
  <li><a href="../race/shutuba.html?race_id=202605060811&rf=race_list">8R</a></li>
</ul>
</body></html>
"""

RACE_LIST_EMPTY_HTML = """
<html><body>
<p>レースはありません</p>
</body></html>
"""


class TestNetkeibaFetchRaceListByDate:
    """NetkeibaScraper.fetch_race_list_by_date() のHTMLパーステスト。"""

    @pytest.mark.asyncio
    async def test_fetch_race_list_by_date_extracts_race_ids(self):
        """race_id と race_number が正しく抽出されること（重複IDはスキップ）。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=RACE_LIST_NEW_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_race_list_by_date(date(2026, 5, 6))

        race_ids = [r["race_id"] for r in result]
        race_numbers = [r["race_number"] for r in result]

        assert race_ids == ["202605060311", "202605060811"]
        assert race_numbers == [11, 11]

    @pytest.mark.asyncio
    async def test_fetch_race_list_by_date_empty_html(self):
        """テーブルなしHTMLで空リストが返ること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value=RACE_LIST_EMPTY_HTML)
        with patch.object(scraper, "fetch", new=mock):
            result = await scraper.fetch_race_list_by_date(date(2026, 5, 6))

        assert result == []


# ---------------------------------------------------------------------------
# グレード正規化（constants.GRADE_NORMALIZE / GRADE_PATTERN）
# ---------------------------------------------------------------------------


class TestGradeNormalize:
    """ローマ数字表記（race.netkeiba）とASCII表記（db.netkeiba）の両対応テスト。"""

    @pytest.mark.parametrize(
        ("race_name", "expected"),
        [
            # 既存のローマ数字表記（挙動を変えないこと）
            ("天皇賞（春）（GⅠ）", "G1"),
            ("青葉賞(GⅡ)", "G2"),
            ("福島牝馬ステークス（GⅢ）", "G3"),
            ("阪神スプリングジャンプ（J・GⅡ）", "G2"),
            # db.netkeiba.com のASCII表記
            ("第91回東京優駿(GI)", "G1"),
            ("第85回皐月賞(GII)", "G2"),
            ("第41回テストダート記念(GIII)", "G3"),
            ("第76回中山大障害(JGI)", "G1"),
            ("第26回テスト障害ステークス(JGII)", "G2"),
            ("第26回テスト障害ステークス(JGIII)", "G3"),
            # グレード表記なし
            ("3歳未勝利", ""),
            ("テストステークス(L)", ""),
        ],
    )
    def test_normalize_grade(self, race_name, expected):
        from app.scrapers.netkeiba import _normalize_grade

        assert _normalize_grade(race_name) == expected

    def test_ascii_grade_longest_match_wins(self):
        """(GIII) が "GI" に先食いされず G3 になること。"""
        from app.scrapers.constants import GRADE_PATTERN

        assert GRADE_PATTERN.search("第41回テストダート記念(GIII)").group(1) == "GIII"
        assert GRADE_PATTERN.search("第26回テスト(JGIII)").group(1) == "JGIII"


# ---------------------------------------------------------------------------
# NetkeibaScraper.fetch_race_result
# ---------------------------------------------------------------------------


class TestNetkeibaFetchRaceResult:
    """NetkeibaScraper.fetch_race_result() のHTMLパーステスト。"""

    RACE_ID = "202405021212"

    async def _fetch(self, html: str, race_id: str | None = None) -> dict:
        scraper = NetkeibaScraper()
        with patch.object(scraper, "fetch", new=AsyncMock(return_value=html)):
            return await scraper.fetch_race_result(race_id or self.RACE_ID)

    @pytest.mark.asyncio
    async def test_race_info_extraction(self):
        """レース情報（名前・ASCIIグレード・日付・会場・コース・天候・馬場）。"""
        parsed = await self._fetch(RACE_RESULT_HTML)
        race = parsed["race"]
        assert race["race_id"] == self.RACE_ID
        assert race["name"] == "第91回東京優駿(GI)"
        assert race["grade"] == "G1"
        assert race["date"] == "2024-05-26"
        assert race["venue"] == "東京"  # race_idのインデックス4-5 = "05"
        assert race["course_type"] == "芝"
        assert race["distance"] == 2400
        assert race["weather"] == "晴"
        assert race["track_condition"] == "良"

    @pytest.mark.asyncio
    async def test_results_parsing_with_ids_and_types(self):
        """25列テーブルからID抽出・型変換が正しく行われること。"""
        parsed = await self._fetch(RACE_RESULT_HTML)
        results = parsed["results"]
        # 取消行を除いた2頭
        assert len(results) == 2

        winner = results[0]
        assert winner["horse_id"] == "2021105165"
        assert winner["horse_name"] == "テスト馬A"
        assert winner["horse_number"] == 10
        assert winner["finish_position"] == 1
        assert winner["time"] == "2:24.3"
        # 1着は着差が空 → None
        assert winner["margin"] is None
        assert winner["last_3f"] == pytest.approx(33.5)
        assert winner["jockey_id"] == "01167"
        assert winner["jockey_name"] == "テスト騎手A"
        # 調教師セルの [西] はリンクテキストに含まれない
        assert winner["trainer_id"] == "01126"
        assert winner["trainer_name"] == "テスト調教師A"

    @pytest.mark.asyncio
    async def test_diary_snap_cut_wrapped_cell(self):
        """馬名セルが <diary_snap_cut> に包まれていてもIDが取れること。"""
        parsed = await self._fetch(RACE_RESULT_HTML)
        runner_up = parsed["results"][1]
        assert runner_up["horse_id"] == "2021104976"
        assert runner_up["horse_name"] == "テスト馬B"
        assert runner_up["horse_number"] == 15
        assert runner_up["margin"] == "クビ"

    @pytest.mark.asyncio
    async def test_scratched_row_skipped(self):
        """着順が非数値（取消/中止/除外）の行がスキップされること。"""
        parsed = await self._fetch(RACE_RESULT_HTML)
        horse_ids = [row["horse_id"] for row in parsed["results"]]
        assert "2021109999" not in horse_ids

    @pytest.mark.asyncio
    async def test_payouts_parsing(self):
        """8券種すべてがthのclassで判定され、金額のカンマが除去されること。"""
        parsed = await self._fetch(RACE_RESULT_HTML)
        payouts = parsed["payouts"]

        # 単勝1 + 複勝3 + 枠連1 + 馬連1 + ワイド3 + 馬単1 + 三連複1 + 三連単1
        assert len(payouts) == 12
        assert {p["bet_type"] for p in payouts} == {
            "単勝",
            "複勝",
            "枠連",
            "馬連",
            "ワイド",
            "馬単",
            "三連複",
            "三連単",
        }

        win = next(p for p in payouts if p["bet_type"] == "単勝")
        assert win == {"bet_type": "単勝", "combination": "10", "amount": 4660}

        # 順不同系は空白除去のみ（区切りは原文のまま）
        quinella = next(p for p in payouts if p["bet_type"] == "馬連")
        assert quinella["combination"] == "10-15"
        assert quinella["amount"] == 14220

        # 着順固定系の区切り（U+2192）はそのまま
        trifecta = next(p for p in payouts if p["bet_type"] == "三連単")
        assert trifecta["combination"] == "10→15→13"
        assert trifecta["amount"] == 212300

    @pytest.mark.asyncio
    async def test_place_payouts_split_by_br(self):
        """複勝の複数払戻が<br/>で3件に分割されること。"""
        parsed = await self._fetch(RACE_RESULT_HTML)
        place_payouts = [p for p in parsed["payouts"] if p["bet_type"] == "複勝"]
        assert [(p["combination"], p["amount"]) for p in place_payouts] == [
            ("10", 1020),
            ("15", 240),
            ("13", 210),
        ]

    @pytest.mark.asyncio
    async def test_dirt_track_condition_key(self):
        """ダートは馬場キーが「ダート」でも track_condition が取れること。"""
        parsed = await self._fetch(RACE_RESULT_DIRT_HTML, "202405020811")
        race = parsed["race"]
        assert race["course_type"] == "ダート"
        assert race["distance"] == 1600
        assert race["track_condition"] == "稍重"
        assert race["weather"] == "曇"
        assert race["grade"] == "G3"

    @pytest.mark.asyncio
    async def test_jump_ascii_grade_and_course(self):
        """障害の (JGIII) が G3 に、コース「障芝」が芝に正規化されること。"""
        parsed = await self._fetch(RACE_RESULT_JUMP_HTML, "202406030609")
        race = parsed["race"]
        assert race["grade"] == "G3"
        assert race["course_type"] == "芝"
        assert race["distance"] == 3000
        # 上りが空欄なら None
        assert parsed["results"][0]["last_3f"] is None

    @pytest.mark.asyncio
    async def test_no_result_table_returns_empty_dict(self):
        """着順テーブルが無い場合は空dictを返すこと。"""
        parsed = await self._fetch(RACE_RESULT_NO_TABLE_HTML)
        assert parsed == {}

    @pytest.mark.asyncio
    async def test_fetch_error_returns_empty_dict(self):
        """HTTPエラー時に空dictを返すこと。"""
        import httpx

        scraper = NetkeibaScraper()
        with patch.object(
            scraper, "fetch", new=AsyncMock(side_effect=httpx.HTTPError("404"))
        ):
            parsed = await scraper.fetch_race_result("999999999999")
        assert parsed == {}


# ---------------------------------------------------------------------------
# NetkeibaScraper.fetch_graded_race_ids
# ---------------------------------------------------------------------------

# db.netkeiba.com のレース検索結果（pid=race_list）を模したHTML。
# レース名セルのリンク /race/{12桁}/ から race_id を取る。
GRADED_LIST_PAGE1_HTML = """
<html><body>
<div class="race_list">139件中1~100件目</div>
<table class="race_table_01">
  <tr><th>日付</th><th>レース名</th><th>開催</th></tr>
  <tr>
    <td><a href="/race/list/20241228/">2024/12/28</a></td>
    <td><a href="/race/202406050911/" title="ホープフルS(GI)">ホープフルS</a></td>
    <td><a href="/race/sum/06/2024/">5中山9</a></td>
  </tr>
  <tr>
    <td><a href="/race/list/20241222/">2024/12/22</a></td>
    <td><a href="/race/202405051211/" title="有馬記念(GI)">有馬記念</a></td>
    <td><a href="/race/sum/05/2024/">5東京12</a></td>
  </tr>
</table>
</body></html>
"""

GRADED_LIST_PAGE2_HTML = """
<html><body>
<div class="race_list">139件中101~139件目</div>
<table class="race_table_01">
  <tr><th>日付</th><th>レース名</th><th>開催</th></tr>
  <tr>
    <td><a href="/race/list/20240107/">2024/01/07</a></td>
    <td><a href="/race/202406010211/" title="シンザン記念(GIII)">シンザン記念</a></td>
    <td><a href="/race/sum/06/2024/">1中山2</a></td>
  </tr>
</table>
</body></html>
"""

GRADED_LIST_EMPTY_HTML = """
<html><body>
<div class="race_list">該当するレースがありません</div>
<table class="race_table_01">
  <tr><th>日付</th><th>レース名</th><th>開催</th></tr>
</table>
</body></html>
"""


class TestNetkeibaFetchGradedRaceIds:
    """NetkeibaScraper.fetch_graded_race_ids() の列挙・ページングテスト。"""

    @pytest.mark.asyncio
    async def test_paginates_until_empty_page(self):
        """行が無くなるページまで辿り、全ページのrace_idを順に返すこと。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(
            side_effect=[
                GRADED_LIST_PAGE1_HTML,
                GRADED_LIST_PAGE2_HTML,
                GRADED_LIST_EMPTY_HTML,
            ]
        )
        with patch.object(scraper, "fetch", new=mock):
            race_ids = await scraper.fetch_graded_race_ids(2024, 2024)

        assert race_ids == [
            "202406050911",
            "202405051211",
            "202406010211",
        ]
        assert mock.await_count == 3

    @pytest.mark.asyncio
    async def test_query_includes_all_jra_venues_and_grades(self):
        """jyo[]（JRA10場）とgrade[]（G1〜G3）が全て付き、EUC-JPで取得すること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(side_effect=[GRADED_LIST_PAGE1_HTML, GRADED_LIST_EMPTY_HTML])
        with patch.object(scraper, "fetch", new=mock):
            await scraper.fetch_graded_race_ids(2021, 2026)

        first_url = mock.await_args_list[0].args[0]
        assert "pid=race_list" in first_url
        assert "start_year=2021" in first_url
        assert "end_year=2026" in first_url
        assert "list=100" in first_url
        assert "page=1" in first_url
        for grade in (1, 2, 3):
            assert f"grade%5B%5D={grade}" in first_url
        for venue_code in ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10"):
            assert f"jyo%5B%5D={venue_code}" in first_url
        assert mock.await_args_list[0].kwargs["encoding"] == "euc-jp"
        assert "page=2" in mock.await_args_list[1].args[0]

    @pytest.mark.asyncio
    async def test_duplicate_page_stops_pagination(self):
        """同じページが返り続けても新規IDが無い時点で打ち切ること。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(
            side_effect=[GRADED_LIST_PAGE1_HTML, GRADED_LIST_PAGE1_HTML]
        )
        with patch.object(scraper, "fetch", new=mock):
            race_ids = await scraper.fetch_graded_race_ids(2024, 2024)

        assert race_ids == ["202406050911", "202405051211"]
        assert mock.await_count == 2

    @pytest.mark.asyncio
    async def test_fetch_error_returns_collected_ids(self):
        """途中でHTTPエラーになってもそこまでのrace_idを返すこと。"""
        import httpx

        scraper = NetkeibaScraper()
        mock = AsyncMock(
            side_effect=[GRADED_LIST_PAGE1_HTML, httpx.HTTPError("500")]
        )
        with patch.object(scraper, "fetch", new=mock):
            race_ids = await scraper.fetch_graded_race_ids(2024, 2024)

        assert race_ids == ["202406050911", "202405051211"]

    @pytest.mark.asyncio
    async def test_no_table_returns_empty_list(self):
        """検索結果テーブルが無い場合は空リストを返すこと。"""
        scraper = NetkeibaScraper()
        mock = AsyncMock(return_value="<html><body>メンテナンス中</body></html>")
        with patch.object(scraper, "fetch", new=mock):
            race_ids = await scraper.fetch_graded_race_ids(2024, 2024)

        assert race_ids == []
        assert mock.await_count == 1
