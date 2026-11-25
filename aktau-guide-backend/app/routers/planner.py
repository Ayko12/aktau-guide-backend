"""«Мои выходные»: подбор маршрута по интересам, бюджету и расстоянию."""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import DB, Today
from ..domain.catalog import loc_cat_name
from ..domain.planner import candidates, make_plan, with_schedule
from ..models import Business, Event, HiddenEntry, Location
from ..schemas import PlanOut, ScheduleIn, StopOut, WeekendIn

router = APIRouter(prefix="/planner", tags=["planner"])


def planner_data(db: Session) -> dict:
    """Опубликованный контент в формате domain.planner. Порядок по id — для детерминированных результатов."""
    locs = db.scalars(select(Location).where(Location.published.is_(True)).order_by(Location.id)).all()
    events = db.scalars(select(Event).where(Event.published.is_(True)).order_by(Event.id)).all()
    rest = db.scalars(select(Business).where(Business.status == "approved", Business.cat == "restaurants").order_by(Business.id)).all()
    hidden = db.scalars(select(HiddenEntry).where(HiddenEntry.published.is_(True)).order_by(HiddenEntry.id)).all()
    return {
        "locs": [{"id": x.id, "name": x.name, "ll": x.ll, "price": x.price, "tags": x.tags, "cats": x.cats} for x in locs],
        "events": [{"id": x.id, "title": x.title, "ll": x.ll, "price": x.price, "tags": x.tags, "date": x.date, "end": x.end,
                    "t1": x.t1, "status": x.status} for x in events],
        "restaurants": [{"id": x.id, "name": x.name, "ll": x.ll, "avg": x.avg} for x in rest],
        "hidden": [{"id": x.id, "title": x.title, "ll": x.ll, "col": x.col} for x in hidden],
        "cat_name": loc_cat_name,
    }


def _w(body: WeekendIn) -> dict:
    return body.model_dump(by_alias=False)


@router.post("/plan", response_model=PlanOut, summary="Собрать маршрут")
def build_plan(body: WeekendIn, db: DB, today: Today):
    w = _w(body)
    return with_schedule(make_plan(w, planner_data(db), today), today)


@router.post("/candidates", response_model=list[StopOut], summary="Что можно добавить в маршрут (по релевантности)")
def list_candidates(body: WeekendIn, db: DB, today: Today, limit: int = Query(20, ge=1, le=100)):
    return candidates(_w(body), planner_data(db), today)[:limit]


@router.post("/schedule", response_model=PlanOut, summary="Пересчитать время после перестановки/удаления точек")
def reschedule(body: ScheduleIn, today: Today):
    plan = {"w": _w(body.w), "stops": [s.model_dump(by_alias=False) for s in body.stops]}
    return with_schedule(plan, today)
