"""
Планировщик «Мои выходные» — порт lib/planner.js фронтенда 1:1.

Подбирает точки по интересам, бюджету и расстоянию, раскладывает по дням
и считает время. Чистые функции: на вход — обычные словари.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Any

INTERESTS = {"nature": "Природа", "sea": "Море", "family": "Семья", "culture": "Культура", "food": "Еда", "active": "Активность"}
DURATIONS = {"half": ("Полдня", 3), "day": ("1 день", 5), "two": ("2 дня", 8)}
MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
WD = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"]  # индекс как у JS getUTCDay(): 0 = воскресенье

START_POINT = (51.153, 43.649)
DAY_START = 600  # 10:00

Stop = dict[str, Any]


def _d(v: dt.date | str) -> dt.date:
    return v if isinstance(v, dt.date) else dt.date.fromisoformat(v)


def js_weekday(d: dt.date) -> int:
    return (d.weekday() + 1) % 7


def fmt_date(d: dt.date) -> str:
    return f"{d.day} {MON[d.month - 1]}"


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def dist(a, b) -> float:
    """Псевдо-евклидово расстояние в градусах с поправкой на широту Актау."""
    return math.hypot((a[0] - b[0]) * 0.72, a[1] - b[1])


def weekend_days(duration: str, today: dt.date) -> list[dt.date]:
    dow = js_weekday(today)
    sat = today + dt.timedelta(days=((6 - dow + 7) % 7) or 7)
    return [sat, sat + dt.timedelta(days=1)] if duration == "two" else [sat]


def candidates(w: dict, data: dict, today: dt.date) -> list[Stop]:
    """
    data: {
      locs:        [{id, name, ll, price, tags, cats}],
      events:      [{id, title, ll, price, tags, date, end, t1, status}],
      restaurants: [{id, name, ll, avg}],
      hidden:      [{id, title, ll, col}],
      cat_name:    callable(cat_id) -> str,
    }
    """
    c: list[Stop] = []
    for loc in data["locs"]:
        c.append({"key": "l" + loc["id"], "kind": "place", "ref": loc["id"], "title": loc["name"], "ll": list(loc["ll"]),
                  "cost": loc["price"], "tags": list(loc["tags"]), "sub": data["cat_name"](loc["cats"][0])})
    days = weekend_days(w["duration"], today)
    for e in data["events"]:
        if e.get("status"):
            continue
        di = next((i for i, d in enumerate(days) if _d(e["date"]) <= d <= _d(e["end"])), -1)
        if di < 0:
            continue
        c.append({"key": "e" + e["id"], "kind": "event", "ref": e["id"], "title": e["title"], "ll": list(e["ll"]),
                  "cost": e["price"], "tags": list(e["tags"]), "day": di,
                  "t": int(e["t1"][:2]) * 60 + int(e["t1"][3:]), "sub": fmt_date(days[di]) + ", " + e["t1"]})
    for b in data["restaurants"]:
        c.append({"key": "b" + b["id"], "kind": "biz", "ref": b["id"], "title": b["name"], "ll": list(b["ll"]),
                  "cost": b["avg"], "tags": ["food"], "sub": "Обед, средний чек"})
    for h in data["hidden"]:
        c.append({"key": "h" + h["id"], "kind": "hidden", "ref": h["id"], "title": h["title"], "ll": list(h["ll"]),
                  "cost": 0, "tags": ["sea", "nature"] if h["col"] == "sea" else ["culture"], "sub": "Hidden Aktau"})

    interests = set(w["interests"])

    def score(x: Stop) -> int:
        return (
            sum(1 for t in x["tags"] if t in interests) * 2
            + (2 if w.get("kids") and "family" in x["tags"] else 0)
            + (1 if x["kind"] == "event" else 0)
            + (1 if x["kind"] == "biz" else 0)
        )

    scored = [{**x, "score": score(x)} for x in c]
    return sorted(scored, key=lambda x: (-x["score"], x["cost"]))


def _order_stops(items: list[Stop]) -> list[Stop]:
    """Жадный «ближайший сосед» от стартовой точки."""
    cur = START_POINT
    rest = list(items)
    out: list[Stop] = []
    while rest:
        rest.sort(key=lambda x: dist(cur, x["ll"]))
        nx = rest.pop(0)
        out.append(nx)
        cur = nx["ll"]
    return out


def make_plan(w: dict, data: dict, today: dt.date) -> dict:
    duration = w["duration"]
    n = DURATIONS[duration][1]
    max_food = (2 if duration == "two" else 1 if duration == "day" else 0) + (1 if "food" in w["interests"] else 0)
    total = food = 0
    pick: list[Stop] = []
    for x in candidates(w, data, today):
        if len(pick) >= n:
            break
        if x["kind"] == "biz" and food >= max_food:
            continue
        if x["score"] == 0 and len(pick) >= math.ceil(n / 2):
            continue
        if total + x["cost"] > w["budget"]:
            continue
        pick.append(x)
        total += x["cost"]
        if x["kind"] == "biz":
            food += 1

    nd = 2 if duration == "two" else 1
    step = 75 if duration == "half" else 110
    evs = [x for x in pick if x["kind"] == "event"]
    others = _order_stops([x for x in pick if x["kind"] != "event"])
    per_day = math.ceil(len(others) / nd)
    out: list[Stop] = []
    for d in range(nd):
        pl = [{**x, "day": d} for x in others[d * per_day:(d + 1) * per_day]]
        ev = sorted((x for x in evs if x["day"] == d), key=lambda x: x["t"])
        cur = DAY_START
        while pl or ev:
            if ev and (not pl or cur + step > ev[0]["t"]):
                e = ev.pop(0)
                out.append(e)
                cur = max(cur, e["t"]) + 120
            else:
                out.append(pl.pop(0))
                cur += step
    return {"w": dict(w), "stops": out}


def plan_title(w: dict) -> str:
    labels = [INTERESTS[i] for i in w["interests"] if i in INTERESTS]
    return " и ".join(labels) + " · " + DURATIONS[w["duration"]][0]


def schedule(plan: dict, today: dt.date) -> list[dict]:
    """Время каждой точки и заголовки дней (для текущего порядка точек)."""
    w = plan["w"]
    two = w["duration"] == "two"
    step = 75 if w["duration"] == "half" else 110
    wd = weekend_days(w["duration"], today)
    cur, prev_day = DAY_START, -1
    res = []
    for i, p in enumerate(plan["stops"]):
        day = p.get("day") or 0
        if day != prev_day:
            cur = DAY_START
        date = wd[day] if day < len(wd) else wd[0]
        head = ""
        if i == 0 or day != prev_day:
            head = (f"День {day + 1} · " if two else "") + fmt_date(date) + ", " + WD[js_weekday(date)]
        prev_day = day
        if p["kind"] == "event" and p.get("t") is not None:
            m = p["t"]
            cur = max(cur, p["t"]) + 120
        else:
            m = cur
            cur += step
        res.append({"head": head, "minutes": m, "time": hhmm(m), "date": date.isoformat()})
    return res


def with_schedule(plan: dict, today: dt.date) -> dict:
    """План + title, days, total, overBudget и время у каждой точки."""
    times = schedule(plan, today)
    stops = [{**s, "time": t["time"], "head": t["head"], "date": t["date"]} for s, t in zip(plan["stops"], times, strict=True)]
    total = sum(s["cost"] for s in stops)
    return {
        "w": plan["w"],
        "title": plan_title(plan["w"]),
        "days": [d.isoformat() for d in weekend_days(plan["w"]["duration"], today)],
        "total": total,
        "over_budget": total > plan["w"]["budget"],
        "stops": stops,
    }
