import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./db/keiba.sqlite3"
    )
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")


settings = Settings()
