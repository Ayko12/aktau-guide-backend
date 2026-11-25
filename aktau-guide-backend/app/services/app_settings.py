"""Настройки, которые меняет администратор (языки, длительность Trial). Хранятся в таблице settings."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Setting
from ..schemas import AppSettings


def load(db: Session) -> AppSettings:
    stored = {s.key: s.value for s in db.query(Setting).all()}
    return AppSettings.model_validate(stored)


def save(db: Session, values: dict) -> AppSettings:
    for key, value in values.items():
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
    db.flush()
    return load(db)
