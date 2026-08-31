"""シードデータのテスト"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.models import Entry, Horse, Jockey, Race, Result, Trainer

# ---------------------------------------------------------------------------
# seed() の内部ロジックを直接テストするためのヘルパー
# ---------------------------------------------------------------------------

def _run_seed_with_db(db):
    """
    seed() のロジックを、テスト用 db セッションを使って実行する。
    SessionLocal と init_db をモックして、テスト用セッションを注入する。
    """
    # SessionLocal() の呼び出しがテスト用 db を返すようにモック
    mock_session_local = MagicMock(return_value=db)

    with patch("app.seed.SessionLocal", mock_session_local), \
         patch("app.seed.init_db", return_value=None):
        # db.close() がロールバックを邪魔しないようにモック
        original_close = db.close
        db.close = MagicMock()
        # db.commit() もロールバック対象のままにするため flush に変換
        original_commit = db.commit
        db.commit = db.flush

        try:
            from app.seed import seed
            seed()
        finally:
            # 元のメソッドを復元
            db.close = original_close
            db.commit = original_commit


# ---------------------------------------------------------------------------
# TestSeedCreatesData
# ---------------------------------------------------------------------------

class TestSeedCreatesData:
    def test_seed_creates_races(self, db):
        """seed 実行後に Race が存在すること"""
        _run_seed_with_db(db)
        races = db.query(Race).all()
        assert len(races) > 0

    def test_seed_creates_horses(self, db):
        """seed 実行後に Horse が存在すること"""
        _run_seed_with_db(db)
        horses = db.query(Horse).all()
        assert len(horses) > 0

    def test_seed_creates_jockeys(self, db):
        """seed 実行後に Jockey が存在すること"""
        _run_seed_with_db(db)
        jockeys = db.query(Jockey).all()
        assert len(jockeys) > 0

    def test_seed_creates_trainers(self, db):
        """seed 実行後に Trainer が存在すること"""
        _run_seed_with_db(db)
        trainers = db.query(Trainer).all()
        assert len(trainers) > 0

    def test_seed_creates_entries(self, db):
        """seed 実行後に Entry が存在すること"""
        _run_seed_with_db(db)
        entries = db.query(Entry).all()
        assert len(entries) > 0

    def test_seed_creates_results(self, db):
        """seed 実行後に Result が存在すること"""
        _run_seed_with_db(db)
        results = db.query(Result).all()
        assert len(results) > 0

    def test_seed_race_has_required_fields(self, db):
        """seed で作成された Race が必須フィールドを持つこと"""
        _run_seed_with_db(db)
        race = db.query(Race).first()
        assert race is not None
        assert race.id is not None
        assert race.name is not None
        assert race.date is not None
        assert race.venue is not None
        assert race.course_type is not None
        assert race.distance is not None
        assert race.grade is not None

    def test_seed_horse_has_required_fields(self, db):
        """seed で作成された Horse が必須フィールドを持つこと"""
        _run_seed_with_db(db)
        horse = db.query(Horse).first()
        assert horse is not None
        assert horse.id is not None
        assert horse.name is not None


# ---------------------------------------------------------------------------
# TestSeedIdempotent
# ---------------------------------------------------------------------------

class TestSeedIdempotent:
    def test_seed_idempotent_races(self, db):
        """2回 seed を実行しても Race が重複しないこと"""
        _run_seed_with_db(db)
        count_first = db.query(Race).count()

        _run_seed_with_db(db)
        count_second = db.query(Race).count()

        assert count_first == count_second
        assert count_first > 0

    def test_seed_idempotent_horses(self, db):
        """2回 seed を実行しても Horse が重複しないこと"""
        _run_seed_with_db(db)
        count_first = db.query(Horse).count()

        _run_seed_with_db(db)
        count_second = db.query(Horse).count()

        assert count_first == count_second

    def test_seed_idempotent_jockeys(self, db):
        """2回 seed を実行しても Jockey が重複しないこと"""
        _run_seed_with_db(db)
        count_first = db.query(Jockey).count()

        _run_seed_with_db(db)
        count_second = db.query(Jockey).count()

        assert count_first == count_second

    def test_seed_idempotent_entries(self, db):
        """2回 seed を実行しても Entry が重複しないこと"""
        _run_seed_with_db(db)
        count_first = db.query(Entry).count()

        _run_seed_with_db(db)
        count_second = db.query(Entry).count()

        assert count_first == count_second

    def test_seed_idempotent_results(self, db):
        """2回 seed を実行しても Result が重複しないこと"""
        _run_seed_with_db(db)
        count_first = db.query(Result).count()

        _run_seed_with_db(db)
        count_second = db.query(Result).count()

        assert count_first == count_second
