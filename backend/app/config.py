import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./db/keiba.sqlite3"
    )
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
    # 許可するCORSオリジン。環境変数 CORS_ORIGINS でカンマ区切りの文字列として上書き可能
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    ]


settings = Settings()
