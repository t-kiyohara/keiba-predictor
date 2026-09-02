"""レース名の名寄せキー（scrapers.constants.race_name_key）のテスト。

出馬表の略記名と、結果ページの「第n回◯◯(GIII)」形式を同じキーに寄せる。
"""

from app.scrapers.constants import race_name_key


class TestRaceNameKey:
    def test_expands_abbreviations(self):
        assert race_name_key("紫苑S") == "紫苑ステークス"
        assert race_name_key("京成杯AH") == "京成杯オータムハンデキャップ"
        assert race_name_key("アイビスサマーD") == "アイビスサマーダッシュ"
        assert race_name_key("ジャパンC") == "ジャパンカップ"
        assert race_name_key("ダービー卿CT") == "ダービー卿チャレンジトロフィー"

    def test_strips_round_and_grade(self):
        assert race_name_key("第62回紫苑ステークス(GII)") == "紫苑ステークス"
        assert race_name_key("第91回東京優駿(GI)") == "東京優駿"
        assert race_name_key("中山大障害(JGI)") == "中山大障害"
        assert race_name_key("阪神ジュベナイルフィリーズ（GⅠ）") == (
            "阪神ジュベナイルフィリーズ"
        )

    def test_full_names_pass_through(self):
        assert race_name_key("有馬記念") == "有馬記念"
        assert race_name_key("セントウルステークス") == "セントウルステークス"

    def test_abbreviated_and_full_names_share_a_key(self):
        assert race_name_key("京成杯AH") == race_name_key(
            "第70回京成杯オータムハンデキャップ(GIII)"
        )
        assert race_name_key(" 紫苑Ｓ ") == race_name_key("第62回紫苑ステークス(GII)")

    def test_empty_name(self):
        assert race_name_key("") == ""
