"""ORM → схемы ответа, с учётом тарифа (акции видны только у Pro/Premium)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from ..domain.plans import effective_plan
from ..models import Business
from ..schemas import BizFull, BizOut
from . import stats


def biz_public(b: Business, today: dt.date) -> BizOut:
    ep = effective_plan(b.plan, b.sub_end, today)
    out = BizOut.model_validate(b)
    return out.model_copy(update={"effective_plan": ep, "offers": b.offers if ep != "free" else []})


def biz_full_many(db: Session, items: list[Business], today: dt.date) -> list[BizFull]:
    tot = stats.totals(db, [b.id for b in items], today)
    res = []
    for b in items:
        t = tot[b.id]
        res.append(
            BizFull.model_validate(b).model_copy(
                update={
                    "effective_plan": effective_plan(b.plan, b.sub_end, today),
                    "views": t["view"],
                    "clicks": {k: t[k] for k in ("phone", "wa", "ig", "site")},
                }
            )
        )
    return res


def biz_full(db: Session, b: Business, today: dt.date) -> BizFull:
    return biz_full_many(db, [b], today)[0]
