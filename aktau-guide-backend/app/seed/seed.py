"""Заполнение пустой БД демо-данными фронтенда. Пароль всех демо-пользователей — DEMO_PASSWORD."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.catalog import seed_data
from ..models import Ad, Business, Event, HiddenEntry, Location, Payment, User
from ..security import hash_password
from ..services import app_settings, stats

DEMO_PASSWORD = "demo1234"


def _d(s: str | None) -> dt.date | None:
    return dt.date.fromisoformat(s) if s else None


def _seed_num(s: str) -> int:
    return sum(ord(c) for c in s)


def seed_database(db: Session, today: dt.date) -> bool:
    """Возвращает True, если данные были добавлены (БД была пустой)."""
    if db.scalar(select(func.count()).select_from(User)):
        return False
    S = seed_data()  # noqa: N806
    pw = hash_password(DEMO_PASSWORD)  # один хеш на всех — быстрее старт

    users = {u["id"]: User(id=u["id"], name=u["name"], email=u["email"], role=u["role"], password_hash=pw, created=_d(u["created"])) for u in S["USERS"]}
    db.add_all(users.values())

    for x in S["LOCS"]:
        db.add(Location(id=x["id"], name=x["name"], cats=x["cats"], addr=x["addr"], lng=x["ll"][0], lat=x["ll"][1], hours=x["hours"],
                        price=x["price"], contact=x.get("contact") or "—", tags=x["tags"], desc=x["desc"], published=True, on_home=bool(x.get("feat"))))
    for x in S["HIDDEN"]:
        db.add(HiddenEntry(id=x["id"], n=x["n"], title=x["title"], col=x["col"], author=x["author"], lng=x["ll"][0], lat=x["ll"][1],
                           lead=x["lead"], story=x["story"], tip=x["tip"], published=True))
    for x in S["EVENTS"]:
        db.add(Event(id=x["id"], title=x["title"], cat=x["cat"], date=_d(x["date"]), end=_d(x["end"]), t1=x["t1"], t2=x["t2"], venue=x["venue"],
                     lng=x["ll"][0], lat=x["ll"][1], org=x["org"], price=x["price"], desc=x["desc"], tags=x["tags"],
                     status=x.get("status"), tickets=bool(x.get("tickets")), published=True))
    for x in S["BIZ"]:
        b = Business(id=x["id"], name=x["name"], cat=x["cat"], short=x["short"], desc=x["desc"], addr=x["addr"], lng=x["ll"][0], lat=x["ll"][1],
                     phone=x["phone"], ig=x["ig"], site=x["site"], hours=x["hours"], services=x["services"], offers=x["offers"],
                     verified=x["verified"], status=x["status"], avg=x["avg"], created=_d(x["created"]))
        sub = x["sub"]
        b.set_sub({"plan": sub["plan"], "status": sub["status"], "start": _d(sub["start"]), "end": _d(sub["end"])})
        b.owner_users = [users[o] for o in x["owners"]]
        db.add(b)
    db.flush()

    for x in S["PAYMENTS"]:
        db.add(Payment(id=x["id"], business_id=x["biz"], plan=x["plan"], amount=x["amount"], date=_d(x["date"]), provider=x["provider"], status=x["status"]))
    for x in S["ADS"]:
        db.add(Ad(id=x["id"], name=x["name"], slot=x["slot"], business_id=x["biz"], date_from=_d(x["from"]), date_to=_d(x["to"]), active=x["active"]))

    # демо-история статистики за 30 дней (детерминированная, как во фронтенде)
    for x in S["BIZ"]:
        if x["status"] != "approved":
            continue
        n = _seed_num(x["id"])
        base = (300 + (n * 37) % 900) / 30
        for i in range(30):
            day = today - dt.timedelta(days=i)
            stats.record(db, x["id"], "view", day, round(base * (0.6 + ((n * (i + 3)) % 9) / 10)))
            for k, mod in (("phone", 40), ("wa", 55), ("ig", 30), ("site", 18)):
                c = ((n + i * 7) % mod) // 12
                if c:
                    stats.record(db, x["id"], k, day, c)

    app_settings.save(db, {"kz": True, "en": True, "trial_days": 30})
    db.commit()
    return True
