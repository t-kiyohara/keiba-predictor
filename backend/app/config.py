from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./db/keiba.sqlite3"
    OPENWEATHER_API_KEY: str = ""
    # 許可するCORSオリジン。環境変数 CORS_ORIGINS でカンマ区切りの文字列として上書き可能
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
