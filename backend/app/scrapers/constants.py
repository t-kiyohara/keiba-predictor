"""スクレイパー共通定数モジュール。"""
import re
import unicodedata

# グレード正規化マッピング
# 入力文字列 → 正規化されたグレード文字列
# netkeiba.py の _GRADE_NORMALIZE を正として、jra.py との差分はないため統合
GRADE_NORMALIZE: dict[str, str] = {
    "GⅠ": "G1",
    "GⅡ": "G2",
    "GⅢ": "G3",
    "G1": "G1",
    "G2": "G2",
    "G3": "G3",
    "J・GⅠ": "G1",
    "J・GⅡ": "G2",
    "J・GⅢ": "G3",
    # db.netkeiba.com のレース結果ページはローマ数字ではなくASCIIのIを使う。
    # 例: 第91回東京優駿(GI) / 中山大障害(JGI)
    "GI": "G1",
    "GII": "G2",
    "GIII": "G3",
    "JGI": "G1",
    "JGII": "G2",
    "JGIII": "G3",
}

# グレード検出用正規表現パターン
# 半角・全角両方の括弧に対応: (GⅠ) / （GⅠ）
# 長い表記を先に並べる（"GI" が "(GIII)" に先食いしないようにする）
GRADE_PATTERN = re.compile(
    r"[（(]("
    + "|".join(
        re.escape(key) for key in sorted(GRADE_NORMALIZE, key=len, reverse=True)
    )
    + r")[）)]"
)

# 「第62回」のような回次表記
_ROUND_PATTERN = re.compile(r"第\d+回")

# 括弧内のグレード表記。NFKC 正規化後は括弧もローマ数字も半角になっているので
# 半角括弧 + G を含む中身だけを見れば (GIII) / (JGI) / (J・GI) を拾える
_GRADE_PAREN_PATTERN = re.compile(r"\([^)]*G[^)]*\)")

# 末尾の略記 → 完全表記。長い略記を先に並べる（"AH" が "H" に先食いされないように）
_NAME_SUFFIX_EXPANSIONS: tuple[tuple[str, str], ...] = (
    ("AH", "オータムハンデキャップ"),
    ("JS", "ジャンプステークス"),
    ("CT", "チャレンジトロフィー"),
    ("S", "ステークス"),
    ("C", "カップ"),
    ("T", "トロフィー"),
    ("H", "ハンデキャップ"),
    ("D", "ダッシュ"),
)


def race_name_key(name: str) -> str:
    """レース名の名寄せキーを返す。

    出馬表の「京成杯AH」と結果ページの「第xx回京成杯オータムハンデキャップ(GIII)」を
    同じキーに寄せるため、回次・グレード表記・空白を落として末尾の略記を展開する。
    完全表記（「紫苑ステークス」等）はそのまま通る。
    """
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", name or ""))
    normalized = _GRADE_PAREN_PATTERN.sub("", _ROUND_PATTERN.sub("", normalized))
    for abbreviation, full_form in _NAME_SUFFIX_EXPANSIONS:
        if normalized.endswith(abbreviation):
            return normalized[: -len(abbreviation)] + full_form
    return normalized
