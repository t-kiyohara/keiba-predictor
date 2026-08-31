"""Alembicマイグレーションとモデル定義の乖離を検知するテスト。

モデル（app/models/*.py）を変更したのにマイグレーションを追加し忘れると、
本番DBには反映されないままアプリだけが新しい列を期待する事故になる。
一時ファイルDBに `alembic upgrade head` を適用した結果と `Base.metadata` を
比較し、差分が無いことを assert してCIで検知する。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

import app.models  # noqa: F401 - Base.metadata にモデルを登録する
from alembic import command
from app.config import settings
from app.database import Base

_ALEMBIC_INI_PATH = Path(__file__).resolve().parent.parent / "alembic.ini"


def test_migrations_match_models(monkeypatch: pytest.MonkeyPatch):
    """一時ファイルDBにマイグレーションを適用した結果が Base.metadata と一致すること"""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "migration_check.sqlite3"
        db_url = f"sqlite:///{db_path}"
        # alembic/env.py は app.config.settings.DATABASE_URL を参照するため差し替える
        monkeypatch.setattr(settings, "DATABASE_URL", db_url)

        alembic_config = Config(str(_ALEMBIC_INI_PATH))
        alembic_config.set_main_option(
            "script_location", str(_ALEMBIC_INI_PATH.parent / "alembic")
        )
        command.upgrade(alembic_config, "head")

        engine = create_engine(db_url)
        try:
            with engine.connect() as connection:
                migration_context = MigrationContext.configure(connection)
                diff = compare_metadata(migration_context, Base.metadata)
        finally:
            engine.dispose()

    assert diff == [], f"モデルとマイグレーションに乖離があります: {diff}"
