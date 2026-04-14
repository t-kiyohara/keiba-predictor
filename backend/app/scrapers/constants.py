"""スクレイパー共通定数モジュール。"""
import re

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
}

# グレード検出用正規表現パターン
# 半角・全角両方の括弧に対応: (GⅠ) / （GⅠ）
GRADE_PATTERN = re.compile(
    r"[（(](" + "|".join(re.escape(k) for k in GRADE_NORMALIZE) + r")[）)]"
)
