"""Публичный каталог: справочники, места, Hidden Aktau, события."""
from __future__ import annotations

import calendar
import datetime as dt
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from ..deps import DB, OptionalUser, Today, is_staff
from ..domain.catalog import BIZ_CATS, EV_CATS, HID_COLS, LOC_CATS, PLANS
from ..domain.planner import dist
from ..models import Event, HiddenEntry, Location
from ..schemas import EventOut, HiddenOut, LocationOut
from ..services import app_settings

router = APIRouter(tags=["catalog"])


def _match(q: str | None, *fields: str) -> bool:
    """Регистронезависимый поиск, корректный для кириллицы (SQLite LIKE — только ASCII)."""
    if not q:
        return True
    needle = q.strip().casefold()
    return needle in " ".join(fields).casefold()


@router.get("/meta", summary="Справочники, тарифы, включённые языки")
def meta(db: DB, today: Today):
    cfg = app_settings.load(db)
    return {
        "today": today,
        "locCats": [{"id": i, "label": label, "icon": ic} for i, label, ic in LOC_CATS],
        "evCats": [{"id": i, "label": label} for i, label in EV_CATS],
        "bizCats": [{"id": i, "label": label, "icon": ic} for i, label, ic in BIZ_CATS],
        "hidCols": [{"id": i, "label": label} for i, label in HID_COLS],
        "plans": PLANS,
        "languages": ["ru"] + [lang for lang in ("kz", "en") if getattr(cfg, lang)],
        "trialDays": cfg.trial_days,
    }


# ------------------------------------------------------------------ locations
@router.get("/locations", response_model=list[LocationOut])
def list_locations(
    db: DB,
    q: str | None = Query(None, max_length=100),
    cat: str | None = None,
    free: bool = False,
    on_home: bool | None = Query(None, alias="onHome"),
):
    stmt = select(Location).where(Location.published.is_(True)).order_by(Location.id)
    if free:
        stmt = stmt.where(Location.price == 0)
    if on_home is not None:
        stmt = stmt.where(Location.on_home.is_(on_home))
    items = db.scalars(stmt).all()
    return [
        loc for loc in items
        if (not cat or cat == "all" or cat in loc.cats or (cat == "free" and loc.price == 0))
        and _match(q, loc.name, loc.desc, loc.addr)
    ]


def _visible_location(db: DB, loc_id: str, user) -> Location:
    loc = db.get(Location, loc_id)
    if loc is None or (not loc.published and not is_staff(user)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Место не найдено")
    return loc


@router.get("/locations/{loc_id}", response_model=LocationOut)
def get_location(loc_id: str, db: DB, user: OptionalUser):
    return _visible_location(db, loc_id, user)


@router.get("/locations/{loc_id}/nearby", response_model=list[LocationOut], summary="Ближайшие места")
def nearby(loc_id: str, db: DB, user: OptionalUser, limit: int = Query(3, ge=1, le=20)):
    loc = _visible_location(db, loc_id, user)
    others = db.scalars(select(Location).where(Location.published.is_(True), Location.id != loc.id)).all()
    return sorted(others, key=lambda x: dist(loc.ll, x.ll))[:limit]


# ------------------------------------------------------------------ hidden
@router.get("/hidden", response_model=list[HiddenOut])
def list_hidden(db: DB, col: str | None = None):
    stmt = select(HiddenEntry).where(HiddenEntry.published.is_(True)).order_by(HiddenEntry.n)
    if col and col != "all":
        stmt = stmt.where(HiddenEntry.col == col)
    return db.scalars(stmt).all()


@router.get("/hidden/{entry_id}", response_model=HiddenOut)
def get_hidden(entry_id: str, db: DB, user: OptionalUser):
    h = db.get(HiddenEntry, entry_id)
    if h is None or (not h.published and not is_staff(user)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запись не найдена")
    return h


# ------------------------------------------------------------------ events
@router.get("/events", response_model=list[EventOut], summary="Афиша; archive=true — прошедшие события")
def list_events(
    db: DB,
    today: Today,
    when: Literal["all", "today", "week", "month", "free"] = "all",
    cat: str | None = None,
    archive: bool = False,
):
    stmt = select(Event).where(Event.published.is_(True))
    if cat and cat != "all":
        stmt = stmt.where(Event.cat == cat)
    if archive:
        return db.scalars(stmt.where(Event.end < today).order_by(Event.date.desc())).all()

    stmt = stmt.where(Event.end >= today).order_by(Event.date, Event.t1)
    if when == "today":
        stmt = stmt.where(Event.date <= today)
    elif when == "week":
        stmt = stmt.where(Event.date <= today + dt.timedelta(days=6))
    elif when == "month":
        first = today.replace(day=1)
        last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        stmt = stmt.where(Event.date >= first, Event.date <= last)
    elif when == "free":
        stmt = stmt.where(Event.price == 0)
    return db.scalars(stmt).all()


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: str, db: DB, user: OptionalUser):
    e = db.get(Event, event_id)
    if e is None or (not e.published and not is_staff(user)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Событие не найдено")
    return e
