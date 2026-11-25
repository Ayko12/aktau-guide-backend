"""Кабинет бизнеса: свои организации, профиль, акции, статистика, подписка."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import DB, AppConfig, BusinessUser, Today
from ..domain.plans import is_paid, monogram
from ..models import Business, Payment
from ..schemas import BizFull, BizStatsOut, OfferIn, OrgCreateIn, OrgUpdateIn, PaymentOut, SubscribeIn, SubscribeOut
from ..services import stats
from ..services.common import apply_patch, patch_data
from ..services.orgs import change_plan, create_org, get_owned
from ..services.serializers import biz_full, biz_full_many

router = APIRouter(prefix="/cabinet", tags=["cabinet"])

LOCKED = "Доступно на Pro и Premium"


def _require_paid(b: Business, today) -> None:
    if not is_paid(b.plan, b.sub_end, today):
        raise HTTPException(status.HTTP_403_FORBIDDEN, LOCKED)


@router.get("/orgs", response_model=list[BizFull], summary="Мои организации (админ — все)")
def my_orgs(user: BusinessUser, db: DB, today: Today):
    items = db.scalars(select(Business).order_by(Business.created)).all() if user.role == "admin" else sorted(user.businesses, key=lambda b: b.created)
    return biz_full_many(db, list(items), today)


@router.post("/orgs", response_model=BizFull, status_code=201, summary="Новая организация — Trial включается автоматически")
def new_org(body: OrgCreateIn, user: BusinessUser, db: DB, today: Today):
    b = create_org(db, user, body.name, body.cat, today)
    db.commit()
    return biz_full(db, b, today)


@router.get("/orgs/{org_id}", response_model=BizFull)
def get_org(org_id: str, user: BusinessUser, db: DB, today: Today):
    return biz_full(db, get_owned(db, user, org_id), today)


@router.patch("/orgs/{org_id}", response_model=BizFull, summary="Изменить профиль организации")
def update_org(org_id: str, body: OrgUpdateIn, user: BusinessUser, db: DB, today: Today):
    b = get_owned(db, user, org_id)
    data = patch_data(body)
    if "name" in data:
        data["name"] = data["name"].strip()
        data["short"] = monogram(data["name"])
    apply_patch(b, data)
    db.commit()
    return biz_full(db, b, today)


@router.get("/orgs/{org_id}/stats", response_model=BizStatsOut, summary="Статистика за 30 дней (Pro/Premium)")
def org_stats(org_id: str, user: BusinessUser, db: DB, today: Today):
    b = get_owned(db, user, org_id)
    _require_paid(b, today)
    t = stats.totals(db, [b.id], today)[b.id]
    days, daily = stats.daily_views(db, b.id, today)
    return BizStatsOut(views=t["view"], clicks={k: t[k] for k in ("phone", "wa", "ig", "site")}, daily_views=daily, days=days)


@router.post("/orgs/{org_id}/offers", response_model=BizFull, status_code=201, summary="Опубликовать акцию (Pro/Premium)")
def add_offer(org_id: str, body: OfferIn, user: BusinessUser, db: DB, today: Today):
    b = get_owned(db, user, org_id)
    _require_paid(b, today)
    if len(b.offers) >= 10:
        raise HTTPException(status.HTTP_409_CONFLICT, "Не больше 10 акций одновременно")
    b.offers = [*b.offers, body.text.strip()]  # новый список — чтобы SQLAlchemy заметил изменение JSON
    db.commit()
    return biz_full(db, b, today)


@router.delete("/orgs/{org_id}/offers/{index}", response_model=BizFull)
def delete_offer(org_id: str, index: int, user: BusinessUser, db: DB, today: Today):
    b = get_owned(db, user, org_id)
    if not 0 <= index < len(b.offers):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Акция не найдена")
    b.offers = [o for i, o in enumerate(b.offers) if i != index]
    db.commit()
    return biz_full(db, b, today)


@router.post("/orgs/{org_id}/subscription", response_model=SubscribeOut, summary="Сменить тариф (оплата — демо)")
def subscribe(org_id: str, body: SubscribeIn, user: BusinessUser, db: DB, today: Today, settings: AppConfig):
    b = get_owned(db, user, org_id)
    payment = change_plan(db, b, body.plan, today, settings)
    db.commit()
    return SubscribeOut(org=biz_full(db, b, today), payment=PaymentOut.model_validate(payment) if payment else None)


@router.get("/orgs/{org_id}/payments", response_model=list[PaymentOut])
def org_payments(org_id: str, user: BusinessUser, db: DB):
    b = get_owned(db, user, org_id)
    return db.scalars(select(Payment).where(Payment.business_id == b.id).order_by(Payment.date.desc())).all()
