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
