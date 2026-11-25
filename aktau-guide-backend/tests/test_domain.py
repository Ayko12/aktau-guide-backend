"""Тесты чистой логики — не требуют FastAPI/SQLAlchemy."""
import datetime as dt
import json
from pathlib import Path

import pytest

from app.domain import catalog, plans
from app.domain.planner import candidates, make_plan, plan_title, schedule, weekend_days, with_schedule
from app.security import create_token, decode_token, hash_password, verify_password

TODAY = dt.date(2026, 11, 22)
REF = json.loads((Path(__file__).parent / "fixtures" / "planner_reference.json").read_text(encoding="utf-8"))


def seed_planner_data():
    s = catalog.seed_data()
    return {
        "locs": s["LOCS"],
        "events": s["EVENTS"],
        "restaurants": [b for b in s["BIZ"] if b["status"] == "approved" and b["cat"] == "restaurants"],
        "hidden": s["HIDDEN"],
        "cat_name": catalog.loc_cat_name,
    }


def _case_id(c):
    w = c["w"]
    return f"{w['duration']}-{w['budget']}-{'k' if w['kids'] else 'n'}-{'+'.join(w['interests']) or 'none'}"


@pytest.mark.parametrize("case", REF, ids=_case_id)
def test_planner_matches_frontend(case):
    """Порт выдаёт ровно то же, что lib/planner.js фронтенда."""
    data = seed_planner_data()
    w = case["w"]
    assert [c["key"] for c in candidates(w, data, TODAY)] == case["candidates"]
    plan = make_plan(w, data, TODAY)
    assert plan["stops"] == case["stops"]
    assert [{"head": t["head"], "minutes": t["minutes"]} for t in schedule(plan, TODAY)] == case["schedule"]
    assert plan_title(w) == case["title"]


def test_weekend_days():
    assert weekend_days("day", TODAY) == [dt.date(2026, 11, 28)]  # 22.11 — воскресенье
    assert weekend_days("two", dt.date(2026, 11, 28)) == [dt.date(2026, 12, 5), dt.date(2026, 12, 6)]


def test_with_schedule_totals():
    w = {"interests": ["family", "nature"], "duration": "day", "budget": 15000, "kids": True}
    res = with_schedule(make_plan(w, seed_planner_data(), TODAY), TODAY)
    assert res["total"] == sum(s["cost"] for s in res["stops"]) and not res["over_budget"]
    assert res["stops"][0]["time"] == "10:00" and res["stops"][0]["head"].startswith("28 ноября")


def test_effective_plan():
    end = dt.date(2026, 12, 1)
    assert plans.effective_plan("trial", end, TODAY) == "pro"
    assert plans.effective_plan("premium", end, TODAY) == "premium"
    assert plans.effective_plan("trial", dt.date(2026, 11, 20), TODAY) == "free"  # истёк
    assert plans.effective_plan("free", None, TODAY) == "free"
    assert plans.is_expired("pro", dt.date(2026, 11, 21), TODAY) and not plans.is_expired("free", None, TODAY)


def test_subscriptions_and_monogram():
    t = plans.trial_subscription(TODAY, 30)
    assert t["end"] == dt.date(2026, 12, 22) and t["plan"] == "trial"
    assert plans.paid_subscription("pro", TODAY)["end"] == dt.date(2026, 12, 22)
    assert plans.free_subscription(TODAY)["end"] is None
    assert plans.monogram("Demo Café Caspian") == "DC"
    assert plans.monogram("123") == "AG"


def test_password_hashing():
    h = hash_password("secret123", iterations=1000)
    assert verify_password("secret123", h) and not verify_password("wrong", h)
    assert not verify_password("x", "garbage")


def test_jwt_roundtrip():
    tok = create_token("u1", "k", 5)
    assert decode_token(tok, "k") == "u1"
    assert decode_token(tok, "other") is None
    assert decode_token(create_token("u1", "k", -1), "k") is None  # истёк
