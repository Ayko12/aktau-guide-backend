"""Правила тарифов и подписок: Trial → Pro/Premium → Free."""
from __future__ import annotations

import datetime as dt
import re

PLAN_WEIGHT = {"premium": 3, "pro": 2, "free": 1}
PAID_PERIOD_DAYS = 30


def is_expired(plan: str, end: dt.date | None, today: dt.date) -> bool:
    return plan != "free" and end is not None and end < today


def effective_plan(plan: str, end: dt.date | None, today: dt.date) -> str:
    """Тариф, по которому работают функции: Trial = Pro, истёкшая подписка = Free."""
    if plan == "free" or is_expired(plan, end, today):
        return "free"
    return "pro" if plan == "trial" else plan


def is_paid(plan: str, end: dt.date | None, today: dt.date) -> bool:
    return effective_plan(plan, end, today) != "free"


def trial_subscription(today: dt.date, days: int) -> dict:
    return {"plan": "trial", "status": "trial", "start": today, "end": today + dt.timedelta(days=days)}


def paid_subscription(plan: str, today: dt.date) -> dict:
    return {"plan": plan, "status": "active", "start": today, "end": today + dt.timedelta(days=PAID_PERIOD_DAYS)}


def free_subscription(today: dt.date) -> dict:
    return {"plan": "free", "status": "active", "start": today, "end": None}


def monogram(name: str) -> str:
    """Инициалы организации вместо логотипа (как во фронтенде)."""
    clean = re.sub(r"[^A-Za-zА-Яа-яЁё ]", "", name)
    return "".join(w[0] for w in clean.split() if w)[:2].upper() or "AG"
