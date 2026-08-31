from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from alembic import command
from app.config import settings

_is_sqlite = "sqlite" in settings.DATABASE_URL
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
# :memory: はプロセス内の接続ごとに別DBになるため、テスト用の in-memory URL のみ判定
_is_memory_sqlite = _is_sqlite and ":memory:" in settings.DATABASE_URL

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_ALEMBIC_INI_PATH = Path(__file__).resolve().parent.parent / "alembic.ini"


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """DBスキーマを最新（head）まで揃える。

    通常は Alembic の `upgrade head` を実行する。マイグレーション本体は
    backend/alembic/versions/ にあり、env.py が app.config.settings.DATABASE_URL
    と app.models のメタデータを参照する。

    in-memory SQLite（テスト用）だけは接続のたびに空DBになる上、
    ファイルが無いため Alembic を通す意味が無く create_all で十分。
    """
    # Import models so they are registered with Base before create_all/autogenerate
    import app.models  # noqa: F401

    if _is_memory_sqlite:
        Base.metadata.create_all(bind=engine)
        return

    alembic_config = Config(str(_ALEMBIC_INI_PATH))
    alembic_config.set_main_option(
        "script_location", str(_ALEMBIC_INI_PATH.parent / "alembic")
    )
    command.upgrade(alembic_config, "head")


def get_db():
    """Dependency: yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
