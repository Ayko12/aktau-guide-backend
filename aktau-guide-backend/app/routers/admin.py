"""
Админ-панель.
Контент-менеджер: дашборд, модерация организаций, места, Hidden Aktau, события, маршруты.
Администратор: всё это + пользователи, подписки, платежи, реклама, отчёты, настройки.
"""
# Без `from __future__ import annotations`: FastAPI должен видеть реальные типы тел запросов в фабрике _crud.

import datetime as dt
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from ..deps import DB, AdminUser, StaffUser, Today
from ..domain.plans import is_expired
from ..models import Ad, Business, Event, HiddenEntry, Location, Payment, SavedRoute, User
from ..schemas import (
    AdIn,
    AdminRouteOut,
    AdOut,
    AdPatch,
    AppSettings,
    BizFull,
    BizModerateIn,
    EventIn,
    EventOut,
    EventPatch,
    ExtendIn,
    HiddenIn,
    HiddenOut,
    HiddenPatch,
    LocationIn,
    LocationOut,
    LocationPatch,
    PaymentOut,
    ReportRow,
    SettingsPatch,
    UserOut,
    UserPatch,
)
from ..services import app_settings, stats
from ..services.common import apply_patch, get_or_404, new_id, patch_data
from ..services.orgs import expire_subscriptions, extend
from ..services.serializers import biz_full, biz_full_many

router = APIRouter(prefix="/admin", tags=["admin"])


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard")
def dashboard(_: StaffUser, db: DB, today: Today):
    biz = db.scalars(select(Business)).all()
    count = lambda m, *w: db.scalar(select(func.count()).select_from(m).where(*w)) or 0  # noqa: E731
    weeks = []
    for i in range(11, -1, -1):
        start = today - dt.timedelta(days=7 * i + 6)
        end = today - dt.timedelta(days=7 * i)
        weeks.append({"from": start, "to": end, "count": count(User, User.created >= start, User.created <= end)})
    views = stats.totals(db, [b.id for b in biz], today)
    return {
        "users": count(User),
        "businesses": len(biz),
        "activePaid": sum(1 for b in biz if b.plan in ("pro", "premium") and not is_expired(b.plan, b.sub_end, today)),
        "trial": sum(1 for b in biz if b.plan == "trial"),
        "pending": sum(1 for b in biz if b.status == "pending"),
        "publishedEvents": count(Event, Event.published.is_(True), Event.end >= today),
        "locations": count(Location, Location.published.is_(True)),
        "views30d": sum(v["view"] for v in views.values()),
        "registrationsByWeek": weeks,
    }


# ------------------------------------------------------------------ users (admin)
@router.get("/users", response_model=list[UserOut])
def list_users(_: AdminUser, db: DB):
    return db.scalars(select(User).order_by(User.created, User.id)).all()


@router.patch("/users/{user_id}", response_model=UserOut, summary="Блокировка / смена роли")
def patch_user(user_id: str, body: UserPatch, me: AdminUser, db: DB):
    u = get_or_404(db, User, user_id, "Пользователь")
    if u.id == me.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Нельзя менять собственную учётную запись")
    apply_patch(u, patch_data(body))
    db.commit()
    return u


# ------------------------------------------------------------------ businesses (staff)
@router.get("/businesses", response_model=list[BizFull], summary="Все организации; сначала ожидающие модерации")
def list_businesses(_: StaffUser, db: DB, today: Today, status_: Literal["pending", "approved", "rejected"] | None = Query(None, alias="status")):
    stmt = select(Business)
    if status_:
        stmt = stmt.where(Business.status == status_)
    items = sorted(db.scalars(stmt).all(), key=lambda b: (b.status != "pending", b.created))
    return biz_full_many(db, items, today)


@router.patch("/businesses/{biz_id}", response_model=BizFull, summary="Модерация и верификация")
def moderate_business(biz_id: str, body: BizModerateIn, _: StaffUser, db: DB, today: Today):
    b = get_or_404(db, Business, biz_id, "Организация")
    apply_patch(b, patch_data(body))
    db.commit()
    return biz_full(db, b, today)


# ------------------------------------------------------------------ content CRUD (staff)
def _crud(model, out, create_in, patch_in, prefix: str, path: str, what: str, order):
    @router.get(f"/{path}", response_model=list[out], name=f"admin_list_{path}")
    def list_items(_: StaffUser, db: DB):
        return db.scalars(select(model).order_by(order)).all()

    @router.post(f"/{path}", response_model=out, status_code=201, name=f"admin_create_{path}")
    def create_item(body: create_in, _: StaffUser, db: DB):  # type: ignore[valid-type]
        data = patch_data(body)
        data.pop("clear_status", None)
        obj = model(id=new_id(prefix))
        apply_patch(obj, data)
        if isinstance(obj, HiddenEntry) and not obj.n:  # номер записи дневника: 01, 02…
            obj.n = f"{(db.scalar(select(func.count()).select_from(HiddenEntry)) or 0) + 1:02d}"
        _validate(obj)
        db.add(obj)
        db.commit()
        return obj

    @router.patch(f"/{path}/{{item_id}}", response_model=out, name=f"admin_patch_{path}")
    def patch_item(item_id: str, body: patch_in, _: StaffUser, db: DB):  # type: ignore[valid-type]
        obj = get_or_404(db, model, item_id, what)
        data = patch_data(body)
        if data.pop("clear_status", False):
            data["status"] = None
        apply_patch(obj, data)
        _validate(obj)
        db.commit()
        return obj

    @router.delete(f"/{path}/{{item_id}}", status_code=204, name=f"admin_delete_{path}")
    def delete_item(item_id: str, _: StaffUser, db: DB):
        db.delete(get_or_404(db, model, item_id, what))
        db.commit()


def _validate(obj) -> None:
    if isinstance(obj, Event) and obj.end < obj.date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Окончание раньше начала")


_crud(Location, LocationOut, LocationIn, LocationPatch, "l", "locations", "Локация", Location.id)
_crud(HiddenEntry, HiddenOut, HiddenIn, HiddenPatch, "h", "hidden", "Запись", HiddenEntry.n)
_crud(Event, EventOut, EventIn, EventPatch, "e", "events", "Событие", Event.date.desc())


# ------------------------------------------------------------------ saved routes (staff)
@router.get("/routes", response_model=list[AdminRouteOut])
def list_routes(_: StaffUser, db: DB):
    rows = db.execute(select(SavedRoute, User.name).join(User, User.id == SavedRoute.owner_id).order_by(SavedRoute.created.desc())).all()
    return [AdminRouteOut.model_validate(r).model_copy(update={"owner_name": name}) for r, name in rows]


@router.delete("/routes/{route_id}", status_code=204)
def delete_route(route_id: str, _: StaffUser, db: DB):
    db.delete(get_or_404(db, SavedRoute, route_id, "Маршрут"))
    db.commit()


# ------------------------------------------------------------------ subscriptions & payments (admin)
@router.post("/subscriptions/expire", summary="Перевести истёкшие подписки на Free")
def run_expiration(_: AdminUser, db: DB, today: Today):
    n = expire_subscriptions(db, today)
    db.commit()
    return {"expired": n}


@router.post("/businesses/{biz_id}/extend", response_model=BizFull, summary="Продлить подписку")
def extend_subscription(biz_id: str, body: ExtendIn, _: AdminUser, db: DB, today: Today):
    b = get_or_404(db, Business, biz_id, "Организация")
    extend(b, body.days, today)
    db.commit()
    return biz_full(db, b, today)


@router.get("/payments", response_model=list[PaymentOut])
def list_payments(_: AdminUser, db: DB):
    return db.scalars(select(Payment).order_by(Payment.date.desc())).all()


# ------------------------------------------------------------------ ads (admin)
@router.get("/ads", response_model=list[AdOut])
def list_ads(_: AdminUser, db: DB):
    return db.scalars(select(Ad).order_by(Ad.date_from.desc())).all()


def _ad_data(db: DB, body: AdIn | AdPatch) -> dict:
    data = patch_data(body, keep_none=("biz",))
    if "biz" in data:
        if data["biz"] is not None:
            get_or_404(db, Business, data["biz"], "Организация")
        data["business_id"] = data.pop("biz")
    return data


@router.post("/ads", response_model=AdOut, status_code=201)
def create_ad(body: AdIn, _: AdminUser, db: DB):
    ad = Ad(id=new_id("a"), active=True)
    apply_patch(ad, _ad_data(db, body))
    db.add(ad)
    db.commit()
    return ad


@router.patch("/ads/{ad_id}", response_model=AdOut)
def patch_ad(ad_id: str, body: AdPatch, _: AdminUser, db: DB):
    ad = get_or_404(db, Ad, ad_id, "Реклама")
    apply_patch(ad, _ad_data(db, body))
    db.commit()
    return ad


# ------------------------------------------------------------------ reports & settings (admin)
@router.get("/reports", response_model=list[ReportRow], summary="Просмотры и переходы по организациям за 30 дней")
def reports(_: AdminUser, db: DB, today: Today):
    biz = db.scalars(select(Business)).all()
    tot = stats.totals(db, [b.id for b in biz], today)
    rows = [ReportRow(id=b.id, name=b.name, plan=b.plan, views=tot[b.id]["view"],
                      clicks=sum(v for k, v in tot[b.id].items() if k != "view")) for b in biz]
    return sorted(rows, key=lambda r: -r.views)


@router.get("/settings", response_model=AppSettings)
def get_settings(_: AdminUser, db: DB):
    return app_settings.load(db)


@router.patch("/settings", response_model=AppSettings)
def patch_settings(body: SettingsPatch, _: AdminUser, db: DB):
    res = app_settings.save(db, patch_data(body))
    db.commit()
    return res
