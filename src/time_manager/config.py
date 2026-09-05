from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    database_url: str = "sqlite+aiosqlite:///data/time-manager.db"
    student_id: int = 1_359_806_027
    owner_id: int = 6_499_614_618
    timezone: str = "Europe/Moscow"
    school_schedule_path: Path = Path("raspisanie_11g.md")
    sotka_schedule_path: Path = Path("vebinary_sotka_sentyabr_2026.md")
    sotka_api_token: str | None = None
    sotka_sync_days: int = 90

    @field_validator("bot_token")
    @classmethod
    def token_must_not_be_placeholder(cls, value: str) -> str:
        if not value or value.endswith("replace_me"):
            raise ValueError("BOT_TOKEN must contain a real Telegram bot token")
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def allowed_ids(self) -> frozenset[int]:
        return frozenset((self.student_id, self.owner_id))


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
