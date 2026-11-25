"""
Pydantic-схемы. Наружу поля отдаются в camelCase (onHome, trialDays, overBudget),
принимаются и camelCase, и snake_case. Формы ответов совпадают с данными фронтенда.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from .domain.catalog import BIZ_CAT_IDS, EV_CAT_IDS, HID_COL_IDS, LOC_CAT_IDS, ROLES

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TIME_RE = r"^([01]\d|2[0-3]):[0-5]\d$"

Interest = Literal["nature", "sea", "family", "culture", "food", "active"]
Duration = Literal["half", "day", "two"]
StopKind = Literal["place", "event", "biz", "hidden"]
PlanId = Literal["free", "pro", "premium"]
LngLat = Annotated[list[float], Field(min_length=2, max_length=2)]
Str200 = Annotated[str, Field(max_length=200)]


class Schema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


def _check_in(value: str | None, allowed: set[str], what: str) -> str | None:
    if value is not None and value not in allowed:
        raise ValueError(f"Неизвестная {what}: {value}")
    return value


# ------------------------------------------------------------------ users / auth
class UserOut(Schema):
    id: str
    name: str
    email: str
    role: str
    created: dt.date
    blocked: bool = False


class RegisterIn(Schema):
    name: str = Field("", max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
    is_biz: bool = False
    org_name: str = Field("", max_length=120)
    org_cat: str = "restaurants"

    @field_validator("org_cat")
    @classmethod
    def _cat(cls, v: str) -> str:
        return _check_in(v, BIZ_CAT_IDS, "категория бизнеса")  # type: ignore[return-value]


class LoginIn(Schema):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class MePatch(Schema):
    name: str = Field(min_length=1, max_length=120)


# ------------------------------------------------------------------ catalog
class LocationOut(Schema):
    id: str
    name: str
    cats: list[str]
    addr: str
    ll: list[float]
    hours: str
    price: int
    contact: str
    tags: list[str]
    desc: str
    published: bool
    on_home: bool


class HiddenOut(Schema):
    id: str
    n: str
    title: str
    col: str
    author: str
    ll: list[float]
    lead: str
    story: str
    tip: str
    published: bool


class EventOut(Schema):
    id: str
    title: str
    cat: str
    date: dt.date
    end: dt.date
    t1: str
    t2: str
    venue: str
    ll: list[float]
    org: str
    price: int
    desc: str
    tags: list[str]
    status: str | None = None
    tickets: bool = False
    published: bool


# ------------------------------------------------------------------ business
class SubscriptionOut(Schema):
    plan: str
    status: str
    start: dt.date
    end: dt.date | None = None


class BizOut(Schema):
    id: str
    name: str
    cat: str
    short: str
    desc: str
    addr: str
    ll: list[float]
    phone: str
    ig: str
    site: str
    hours: str
    services: list[str]
    offers: list[str]
    verified: bool
    status: str
    sub: SubscriptionOut
    avg: int
    created: dt.date
    effective_plan: str = "free"


class BizFull(BizOut):
    """Для владельца и персонала: + владельцы и статистика за 30 дней."""

    owners: list[str] = []
    views: int = 0
    clicks: dict[str, int] = {}


class BizStatsOut(Schema):
    views: int
    clicks: dict[str, int]
    daily_views: list[int]  # последние 14 дней, по возрастанию даты
    days: list[dt.date]


class OrgCreateIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    cat: str

    @field_validator("cat")
    @classmethod
    def _cat(cls, v: str) -> str:
        return _check_in(v, BIZ_CAT_IDS, "категория бизнеса")  # type: ignore[return-value]


class OrgUpdateIn(Schema):
    name: str | None = Field(None, min_length=1, max_length=120)
    cat: str | None = None
    desc: str | None = Field(None, max_length=2000)
    addr: str | None = Field(None, max_length=300)
    phone: str | None = Field(None, max_length=40)
    ig: str | None = Field(None, max_length=80)
    site: str | None = Field(None, max_length=200)
    hours: str | None = Field(None, max_length=200)
    services: list[Str200] | None = Field(None, max_length=30)
    avg: int | None = Field(None, ge=0, le=1_000_000)
    ll: LngLat | None = None

    @field_validator("cat")
    @classmethod
    def _cat(cls, v: str | None) -> str | None:
        return _check_in(v, BIZ_CAT_IDS, "категория бизнеса")


class OfferIn(Schema):
    text: str = Field(min_length=1, max_length=200)


class SubscribeIn(Schema):
    plan: PlanId


class PaymentOut(Schema):
    id: str
    biz: str
    plan: str
    amount: int
    date: dt.date
    provider: str
    status: str


class SubscribeOut(Schema):
    org: BizFull
    payment: PaymentOut | None = None


class AuthOut(Schema):
    token: str
    user: UserOut
    org: BizFull | None = None


# ------------------------------------------------------------------ planner / routes
class WeekendIn(Schema):
    interests: list[Interest] = Field(default_factory=list, max_length=6)
    duration: Duration = "day"
    budget: int = Field(15000, ge=0, le=1_000_000)
    kids: bool = False


class StopIn(Schema):
    model_config = ConfigDict(extra="ignore")
    key: str = Field(max_length=40)
    kind: StopKind
    ref: str = Field(max_length=32)
    title: str = Field(max_length=200)
    ll: LngLat
    cost: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list, max_length=20)
    sub: str = Field("", max_length=200)
    day: int | None = Field(None, ge=0, le=1)
    t: int | None = Field(None, ge=0, le=24 * 60)
    score: int | None = None


class StopOut(StopIn):
    time: str | None = None
    head: str | None = None
    date: dt.date | None = None


class PlanOut(Schema):
    w: WeekendIn
    title: str
    days: list[dt.date]
    total: int
    over_budget: bool
    stops: list[StopOut]


class ScheduleIn(Schema):
    w: WeekendIn
    stops: list[StopIn] = Field(max_length=30)


class RouteIn(Schema):
    w: WeekendIn
    stops: list[StopIn] = Field(min_length=1, max_length=30)
    title: str | None = Field(None, max_length=200)


class RouteOut(Schema):
    id: str
    owner: str
    title: str
    w: dict[str, Any]
    stops: list[dict[str, Any]]
    created: dt.date


class FavoriteOut(Schema):
    id: str
    kind: Literal["place", "biz"]
    name: str
    cat: str


# ------------------------------------------------------------------ admin
class UserPatch(Schema):
    blocked: bool | None = None
    role: str | None = None

    @field_validator("role")
    @classmethod
    def _role(cls, v: str | None) -> str | None:
        return _check_in(v, set(ROLES), "роль")


class BizModerateIn(Schema):
    status: Literal["pending", "approved", "rejected"] | None = None
    verified: bool | None = None


class ExtendIn(Schema):
    days: int = Field(30, ge=1, le=366)


class LocationPatch(Schema):
    name: str | None = Field(None, min_length=1, max_length=200)
    cats: list[str] | None = Field(None, min_length=1)
    addr: str | None = Field(None, max_length=300)
    ll: LngLat | None = None
    hours: str | None = Field(None, max_length=200)
    price: int | None = Field(None, ge=0)
    contact: str | None = Field(None, max_length=200)
    tags: list[str] | None = None
    desc: str | None = Field(None, max_length=5000)
    published: bool | None = None
    on_home: bool | None = None

    @field_validator("cats")
    @classmethod
    def _cats(cls, v: list[str] | None) -> list[str] | None:
        for c in v or []:
            _check_in(c, LOC_CAT_IDS, "категория места")
        return v


class LocationIn(LocationPatch):
    name: str = Field(min_length=1, max_length=200)
    cats: list[str] = Field(min_length=1)
    ll: LngLat


class HiddenPatch(Schema):
    n: str | None = Field(None, max_length=8)
    title: str | None = Field(None, min_length=1, max_length=200)
    col: str | None = None
    author: str | None = Field(None, max_length=120)
    ll: LngLat | None = None
    lead: str | None = Field(None, max_length=1000)
    story: str | None = Field(None, max_length=10000)
    tip: str | None = Field(None, max_length=1000)
    published: bool | None = None

    @field_validator("col")
    @classmethod
    def _col(cls, v: str | None) -> str | None:
        return _check_in(v, HID_COL_IDS, "подборка")


class HiddenIn(HiddenPatch):
    title: str = Field(min_length=1, max_length=200)
    col: str
    ll: LngLat


class EventPatch(Schema):
    title: str | None = Field(None, min_length=1, max_length=200)
    cat: str | None = None
    date: dt.date | None = None
    end: dt.date | None = None
    t1: str | None = Field(None, pattern=TIME_RE)
    t2: str | None = Field(None, pattern=TIME_RE)
    venue: str | None = Field(None, max_length=200)
    ll: LngLat | None = None
    org: str | None = Field(None, max_length=200)
    price: int | None = Field(None, ge=0)
    desc: str | None = Field(None, max_length=5000)
    tags: list[str] | None = None
    status: Literal["cancelled", "postponed"] | None = None
    clear_status: bool = False  # true — снять отмену/перенос
    tickets: bool | None = None
    published: bool | None = None

    @field_validator("cat")
    @classmethod
    def _cat(cls, v: str | None) -> str | None:
        return _check_in(v, EV_CAT_IDS, "категория события")


class EventIn(EventPatch):
    title: str = Field(min_length=1, max_length=200)
    cat: str
    date: dt.date
    end: dt.date
    t1: str = Field(pattern=TIME_RE)
    t2: str = Field(pattern=TIME_RE)
    ll: LngLat


class AdOut(Schema):
    id: str
    name: str
    slot: str
    biz: str | None
    date_from: dt.date = Field(alias="from")
    date_to: dt.date = Field(alias="to")
    active: bool


class AdPatch(Schema):
    name: str | None = Field(None, min_length=1, max_length=200)
    slot: str | None = Field(None, max_length=80)
    biz: str | None = None
    date_from: dt.date | None = Field(None, alias="from")
    date_to: dt.date | None = Field(None, alias="to")
    active: bool | None = None


class AdIn(AdPatch):
    name: str = Field(min_length=1, max_length=200)
    slot: str = Field(max_length=80)
    date_from: dt.date = Field(alias="from")
    date_to: dt.date = Field(alias="to")


class AppSettings(Schema):
    kz: bool = True
    en: bool = True
    trial_days: int = Field(30, ge=1, le=365)


class SettingsPatch(Schema):
    kz: bool | None = None
    en: bool | None = None
    trial_days: int | None = Field(None, ge=1, le=365)


class AdminRouteOut(RouteOut):
    owner_name: str = ""


class ReportRow(Schema):
    id: str
    name: str
    plan: str
    views: int
    clicks: int
