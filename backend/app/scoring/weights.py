"""スコアリングファクターの重み定数"""

# 各ファクターの重み（合計 = 1.0）
FACTOR_WEIGHTS = {
    "recent_form": 0.20,        # 近走成績（直近5走）
    "same_race": 0.15,          # 同レース成績
    "course_aptitude": 0.15,    # コース適性（同競馬場・同距離）
    "bloodline": 0.15,          # 血統適性
    "track_condition": 0.10,    # 馬場状態適性
    "jockey": 0.10,             # 騎手成績
    "trainer": 0.10,            # 調教師成績
    "overall": 0.05,            # 総合実績
}

# データ不足時のペナルティ
MIN_RACES_FOR_FULL_SCORE = 5  # この走数以上でペナルティなし
DATA_SHORTAGE_PENALTY = 0.7    # データ不足時のスコア乗数

# ファクター名の日本語ラベル（UI表示用）
FACTOR_LABELS = {
    "recent_form": "近走成績",
    "same_race": "同レース成績",
    "course_aptitude": "コース適性",
    "bloodline": "血統適性",
    "track_condition": "馬場状態適性",
    "jockey": "騎手成績",
    "trainer": "調教師成績",
    "overall": "総合実績",
}

# スコアリング共通定数
NEUTRAL_SCORE: float = 50.0
"""データ不足時のデフォルトスコア (factors.py 全域で使用)"""

DISTANCE_TOLERANCE_M: int = 200
"""距離マッチングの許容範囲 (メートル)"""
