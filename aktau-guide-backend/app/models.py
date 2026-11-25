"""ORM-модели. Имена полей в API совпадают с фронтендом (ll, t1, sub, owners…)."""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

business_owners = Table(
    "business_owners",
    Base.metadata,
    Column("business_id", ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class GeoMixin:
    lng: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)

    @property
    def ll(self) -> list[float]:
        return [self.lng, self.lat]


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(16), default="user")
    password_hash: Mapped[str] = mapped_column(String(255))
    created: Mapped[dt.date] = mapped_column(Date)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    businesses: Mapped[list[Business]] = relationship(secondary=business_owners, back_populates="owner_users")


class Location(GeoMixin, Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    cats: Mapped[list[str]] = mapped_column(JSON, default=list)
    addr: Mapped[str] = mapped_column(String(300), default="")
    hours: Mapped[str] = mapped_column(String(200), default="")
    price: Mapped[int] = mapped_column(Integer, default=0)
    contact: Mapped[str] = mapped_column(String(200), default="—")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    desc: Mapped[str] = mapped_column("description", Text, default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    on_home: Mapped[bool] = mapped_column(Boolean, default=False)


class HiddenEntry(GeoMixin, Base):
    __tablename__ = "hidden_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    n: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(200))
    col: Mapped[str] = mapped_column(String(32))
    author: Mapped[str] = mapped_column(String(120), default="Редакция Aktau Guide")
    lead: Mapped[str] = mapped_column(Text, default="")
    story: Mapped[str] = mapped_column(Text, default="")
    tip: Mapped[str] = mapped_column(Text, default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)


class Event(GeoMixin, Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    cat: Mapped[str] = mapped_column(String(32))
    date: Mapped[dt.date] = mapped_column("start_date", Date, index=True)
    end: Mapped[dt.date] = mapped_column("end_date", Date, index=True)
    t1: Mapped[str] = mapped_column(String(5))
    t2: Mapped[str] = mapped_column(String(5))
    venue: Mapped[str] = mapped_column(String(200), default="")
    org: Mapped[str] = mapped_column(String(200), default="")
    price: Mapped[int] = mapped_column(Integer, default=0)
    desc: Mapped[str] = mapped_column("description", Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # None | cancelled | postponed
    tickets: Mapped[bool] = mapped_column(Boolean, default=False)
    published: Mapped[bool] = mapped_column(Boolean, default=True)


class Business(GeoMixin, Base):
    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    cat: Mapped[str] = mapped_column(String(32), index=True)
    short: Mapped[str] = mapped_column(String(4))
    desc: Mapped[str] = mapped_column("description", Text, default="")
    addr: Mapped[str] = mapped_column(String(300), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    ig: Mapped[str] = mapped_column(String(80), default="")
    site: Mapped[str] = mapped_column(String(200), default="")
    hours: Mapped[str] = mapped_column(String(200), default="")
    services: Mapped[list[str]] = mapped_column(JSON, default=list)
    offers: Mapped[list[str]] = mapped_column(JSON, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending | approved | rejected
    plan: Mapped[str] = mapped_column(String(16), default="trial")  # trial | free | pro | premium
    sub_status: Mapped[str] = mapped_column(String(16), default="trial")
    sub_start: Mapped[dt.date] = mapped_column(Date)
    sub_end: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    avg: Mapped[int] = mapped_column(Integer, default=0)  # средний чек — для планировщика
    created: Mapped[dt.date] = mapped_column(Date)

    owner_users: Mapped[list[User]] = relationship(secondary=business_owners, back_populates="businesses")
    payments: Mapped[list[Payment]] = relationship(back_populates="business", cascade="all, delete-orphan")

    @property
    def owners(self) -> list[str]:
        return [u.id for u in self.owner_users]

    @property
    def sub(self) -> dict[str, Any]:
        return {"plan": self.plan, "status": self.sub_status, "start": self.sub_start, "end": self.sub_end}

    def set_sub(self, sub: dict[str, Any]) -> None:
        self.plan, self.sub_status, self.sub_start, self.sub_end = sub["plan"], sub["status"], sub["start"], sub["end"]


class BizStat(Base):
    """Дневные счётчики карточки: view | phone | wa | ig | site."""

    __tablename__ = "biz_stats"

    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    plan: Mapped[str] = mapped_column(String(16))
    amount: Mapped[int] = mapped_column(Integer)
    date: Mapped[dt.date] = mapped_column("paid_on", Date)
    provider: Mapped[str] = mapped_column(String(40), default="Demo")
    status: Mapped[str] = mapped_column(String(32), default="Оплачено")

    business: Mapped[Business] = relationship(back_populates="payments")

    @property
    def biz(self) -> str:
        return self.business_id


class Ad(Base):
    __tablename__ = "ads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slot: Mapped[str] = mapped_column(String(80))
    business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True)
    date_from: Mapped[dt.date] = mapped_column(Date)
    date_to: Mapped[dt.date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def biz(self) -> str | None:
        return self.business_id


class Favorite(Base):
    """item_id — id места (l…) или организации (b…)."""

    __tablename__ = "favorites"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC))


class SavedRoute(Base):
    __tablename__ = "saved_routes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    w: Mapped[dict] = mapped_column(JSON)
    stops: Mapped[list[dict]] = mapped_column(JSON)
    created: Mapped[dt.date] = mapped_column(Date)

    @property
    def owner(self) -> str:
        return self.owner_id


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
