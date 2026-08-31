import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

_is_sqlite = "sqlite" in settings.DATABASE_URL
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _reconcile_schema() -> None:
    """モデルと実スキーマの差を、列追加の範囲だけ埋める。

    このプロジェクトにマイグレーション機構は無く、テーブル作成は create_all だけ。
    create_all は既存テーブルを変更しないため、モデルに足した列がDBに無いまま
    残り、その列を触るクエリが実行時に "no such column" で落ちる。

    - NULL許容の追加列: ALTER TABLE ADD COLUMN で埋める（既存行は NULL）
    - predictions.created_at (NOT NULL): 既存行は「いつ出した予想か」が判別できず
      答え合わせに使えない。仮の値を入れるとレース前の予想として集計を汚染するので、
      テーブルごと捨てて次回フェッチで作り直す（予想は派生データ）
    - その他の NOT NULL 列: 安全な既定値が決められないため警告だけ出す

    # ponytail: 列追加までしか面倒を見ない。型変更・列削除が要るなら Alembic を入れる
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    if "predictions" in existing_tables:
        prediction_columns = {
            column["name"] for column in inspector.get_columns("predictions")
        }
        if "created_at" not in prediction_columns:
            with engine.begin() as connection:
                connection.execute(text("DROP TABLE predictions"))
            existing_tables.discard("predictions")
            logger.info("予想の履歴化に伴い predictions テーブルを作り直しました")

    for table in Base.metadata.tables.values():
        if table.name not in existing_tables:
            continue  # create_all が作る
        db_column_names = {
            column["name"] for column in inspector.get_columns(table.name)
        }
        for column in table.columns:
            if column.name in db_column_names:
                continue
            if not column.nullable:
                logger.warning(
                    "%s.%s (NOT NULL) がDBに存在しません。手動での移行が必要です",
                    table.name,
                    column.name,
                )
                continue
            # テーブル名・列名はモデル定義由来（外部入力ではない）
            with engine.begin() as connection:
                connection.execute(text(
                    f"ALTER TABLE {table.name} ADD COLUMN "
                    f"{column.name} {column.type.compile(engine.dialect)}"
                ))
            logger.info("列を追加しました: %s.%s", table.name, column.name)


def init_db() -> None:
    """Create all tables in the database."""
    # Import models so they are registered with Base before create_all
    import app.models  # noqa: F401

    _reconcile_schema()
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency: yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
