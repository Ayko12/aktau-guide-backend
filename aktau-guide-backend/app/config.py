"""Настройки приложения из переменных окружения (префикс AG_) и файла .env."""
from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

DEFAULT_SECRET = "dev-secret-change-me"


def _load_env_file(path: Path) -> None:
    """Минимальный загрузчик .env (KEY=VALUE), не перетирает уже заданные переменные."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Settings(BaseModel):
    database_url: str = "sqlite:///./aktau_guide.db"
    secret_key: str = DEFAULT_SECRET
    token_ttl_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = ["http://localhost:5173"]
    # Демо-режим: эндпоинт входа по роли и демо-пароли у сидовых пользователей
    demo_mode: bool = True
    seed_on_startup: bool = True
    # Фиксированная «сегодняшняя» дата под демо-данные (как TODAY во фронтенде).
    # Пустое значение AG_TODAY = реальная текущая дата.
    today_override: dt.date | None = dt.date(2026, 11, 22)

    def today(self) -> dt.date:
        return self.today_override or dt.date.today()

    def check_production_safety(self) -> None:
        if not self.demo_mode and self.secret_key == DEFAULT_SECRET:
            raise RuntimeError("Задайте AG_SECRET_KEY: стандартный ключ допустим только в демо-режиме")


def _bool(v: str) -> bool:
    return v.strip().lower() in {"1", "true", "yes", "on"}


def settings_from_env(env_file: str | Path = ".env") -> Settings:
    _load_env_file(Path(env_file))
    e = os.environ
    data: dict = {}
    if "AG_DATABASE_URL" in e:
        data["database_url"] = e["AG_DATABASE_URL"]
    if "AG_SECRET_KEY" in e:
        data["secret_key"] = e["AG_SECRET_KEY"]
    if "AG_TOKEN_TTL_MINUTES" in e:
        data["token_ttl_minutes"] = int(e["AG_TOKEN_TTL_MINUTES"])
    if "AG_CORS_ORIGINS" in e:
        data["cors_origins"] = [o.strip() for o in e["AG_CORS_ORIGINS"].split(",") if o.strip()]
    if "AG_DEMO_MODE" in e:
        data["demo_mode"] = _bool(e["AG_DEMO_MODE"])
    if "AG_SEED_ON_STARTUP" in e:
        data["seed_on_startup"] = _bool(e["AG_SEED_ON_STARTUP"])
    if "AG_TODAY" in e:
        data["today_override"] = e["AG_TODAY"].strip() or None
    return Settings(**data)


@lru_cache
def get_settings() -> Settings:
    return settings_from_env()
