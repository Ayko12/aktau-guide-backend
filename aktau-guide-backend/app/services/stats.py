"""Статистика карточек: просмотры и переходы по контактам, по дням."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.catalog import CONTACT_KINDS
from ..models import BizStat

KINDS = ("view", *CONTACT_KINDS)


def record(db: Session, business_id: str, kind: str, day: dt.date, n: int = 1) -> None:
    row = db.get(BizStat, (business_id, day, kind))
    if row is None:
        db.add(BizStat(business_id=business_id, day=day, kind=kind, count=n))
    else:
        row.count += n


def totals(db: Session, business_ids: list[str], today: dt.date, days: int = 30) -> dict[str, dict[str, int]]:
    """{business_id: {view, phone, wa, ig, site}} за последние `days` дней."""
    since = today - dt.timedelta(days=days - 1)
    res: dict[str, dict[str, int]] = {b: dict.fromkeys(KINDS, 0) for b in business_ids}
    if not business_ids:
        return res
    q = (
        select(BizStat.business_id, BizStat.kind, func.sum(BizStat.count))
        .where(BizStat.business_id.in_(business_ids), BizStat.day >= since, BizStat.day <= today)
        .group_by(BizStat.business_id, BizStat.kind)
    )
    for biz_id, kind, total in db.execute(q):
        res[biz_id][kind] = int(total or 0)
    return res


def daily_views(db: Session, business_id: str, today: dt.date, days: int = 14) -> tuple[list[dt.date], list[int]]:
    since = today - dt.timedelta(days=days - 1)
    rows = db.execute(
        select(BizStat.day, BizStat.count).where(
            BizStat.business_id == business_id, BizStat.kind == "view", BizStat.day >= since, BizStat.day <= today
        )
    ).all()
    by_day = {d: c for d, c in rows}
    dates = [since + dt.timedelta(days=i) for i in range(days)]
    return dates, [by_day.get(d, 0) for d in dates]
