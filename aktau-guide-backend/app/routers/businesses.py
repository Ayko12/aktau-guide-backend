"""Публичный каталог организаций, учёт просмотров и переходов."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from ..deps import DB, OptionalUser, Today, is_staff
from ..domain.catalog import CONTACT_KINDS
from ..domain.plans import PLAN_WEIGHT, effective_plan
from ..models import Business
from ..schemas import BizOut
from ..services import stats
from ..services.serializers import biz_public

router = APIRouter(prefix="/businesses", tags=["businesses"])


def _searchable(b: Business) -> str:
    return " ".join([b.name, b.desc, *b.services]).casefold()


@router.get("", response_model=list[BizOut], summary="Опубликованные организации; sort=rec — Premium/Pro выше")
def list_businesses(
    db: DB,
    today: Today,
    q: str | None = Query(None, max_length=100),
    cat: str | None = None,
    sort: Literal["rec", "name", "new"] = "rec",
):
    stmt = select(Business).where(Business.status == "approved")
    if cat and cat != "all":
        stmt = stmt.where(Business.cat == cat)
    items = list(db.scalars(stmt).all())
    if q:
        needle = q.strip().casefold()
        items = [b for b in items if needle in _searchable(b)]
    if sort == "name":
        items.sort(key=lambda b: b.name.casefold())
    elif sort == "new":
        items.sort(key=lambda b: b.created, reverse=True)
    else:
        items.sort(key=lambda b: (-PLAN_WEIGHT[effective_plan(b.plan, b.sub_end, today)], b.name.casefold()))
    return [biz_public(b, today) for b in items]


def _visible(db: DB, biz_id: str, user) -> Business:
    b = db.get(Business, biz_id)
    owner = user is not None and b is not None and user in b.owner_users
    if b is None or (b.status != "approved" and not owner and not is_staff(user)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Организация не найдена")
    return b


@router.get("/{biz_id}", response_model=BizOut)
def get_business(biz_id: str, db: DB, user: OptionalUser, today: Today):
    return biz_public(_visible(db, biz_id, user), today)


@router.post("/{biz_id}/view", status_code=204, summary="Учесть просмотр карточки")
def track_view(biz_id: str, db: DB, user: OptionalUser, today: Today):
    _visible(db, biz_id, user)
    stats.record(db, biz_id, "view", today)
    db.commit()


@router.post("/{biz_id}/contact/{kind}", status_code=204, summary="Учесть переход: phone | wa | ig | site")
def track_contact(biz_id: str, kind: str, db: DB, user: OptionalUser, today: Today):
    if kind not in CONTACT_KINDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Неизвестный тип контакта")
    _visible(db, biz_id, user)
    stats.record(db, biz_id, kind, today)
    db.commit()
