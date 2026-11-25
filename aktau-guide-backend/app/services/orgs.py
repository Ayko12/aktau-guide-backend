"""Организации: создание с Trial, смена тарифа, истечение подписок."""
from __future__ import annotations

import datetime as dt
import random

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..domain.catalog import PLAN_BY_ID
from ..domain.plans import free_subscription, is_expired, monogram, paid_subscription, trial_subscription
from ..models import Business, Payment, User
from . import app_settings
from .common import new_id
from .payments import provider_for

CITY_CENTER = (51.158, 43.652)


def create_org(db: Session, owner: User, name: str, cat: str, today: dt.date) -> Business:
    trial_days = app_settings.load(db).trial_days
    b = Business(
        id=new_id("b"),
        name=name.strip(),
        cat=cat,
        short=monogram(name),
        desc="Описание появится после заполнения профиля.",
        addr="Адрес не указан",
        lng=CITY_CENTER[0] + random.random() * 0.01,
        lat=CITY_CENTER[1] + random.random() * 0.006,
        services=[],
        offers=[],
        verified=False,
        status="pending",
        created=today,
    )
    b.set_sub(trial_subscription(today, trial_days))
    b.owner_users.append(owner)
    db.add(b)
    db.flush()
    return b


def get_owned(db: Session, user: User, org_id: str) -> Business:
    b = db.get(Business, org_id)
    if b is None or (user.role != "admin" and user not in b.owner_users):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Организация не найдена")
    return b


def change_plan(db: Session, b: Business, plan_id: str, today: dt.date, settings: Settings) -> Payment | None:
    if b.plan == plan_id and not is_expired(b.plan, b.sub_end, today):
        raise HTTPException(status.HTTP_409_CONFLICT, "Этот тариф уже подключён")
    if plan_id == "free":
        b.set_sub(free_subscription(today))
        return None
    plan = PLAN_BY_ID[plan_id]
    result = provider_for(settings).charge(b.id, plan_id, plan["price"])
    payment = Payment(
        id=new_id("p"), business_id=b.id, plan=plan_id, amount=plan["price"], date=today,
        provider=result.provider, status=result.status,
    )
    db.add(payment)
    if result.paid:
        b.set_sub(paid_subscription(plan_id, today))
    return payment


def expire_subscriptions(db: Session, today: dt.date) -> int:
    """Переводит на Free все Trial/Pro/Premium с истёкшей датой. Запускайте по расписанию (cron)."""
    items = db.scalars(select(Business).where(Business.plan != "free", Business.sub_end < today)).all()
    for b in items:
        b.set_sub(free_subscription(today))
    return len(items)


def extend(b: Business, days: int, today: dt.date) -> None:
    if b.plan == "free":
        raise HTTPException(status.HTTP_409_CONFLICT, "У Free нет срока действия")
    base = b.sub_end if b.sub_end and b.sub_end > today else today
    b.sub_end = base + dt.timedelta(days=days)
