"""Сквозные тесты API (нужны fastapi, sqlalchemy, httpx — см. requirements-dev.txt)."""
import pytest

from .conftest import HAS_API_DEPS

pytestmark = pytest.mark.skipif(not HAS_API_DEPS, reason="fastapi/sqlalchemy/httpx не установлены")


def test_health_and_meta(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    m = client.get("/api/meta").json()
    assert m["today"] == "2026-11-22" and m["trialDays"] == 30
    assert {p["id"] for p in m["plans"]} == {"free", "pro", "premium"}
    assert m["languages"] == ["ru", "kz", "en"]


def test_locations_filters_and_shape(client):
    all_ = client.get("/api/locations").json()
    assert len(all_) == 10
    loc = next(x for x in all_ if x["id"] == "l1")
    assert loc["ll"] == [51.1505, 43.6475] and loc["onHome"] is True and "desc" in loc
    assert all(x["price"] == 0 for x in client.get("/api/locations", params={"free": True}).json())
    assert [x["id"] for x in client.get("/api/locations", params={"q": "набережная"}).json()] == ["l1"]  # кириллица без учёта регистра
    beaches = client.get("/api/locations", params={"cat": "beaches"}).json()
    assert beaches and all("beaches" in x["cats"] for x in beaches)
    assert len(client.get("/api/locations/l1/nearby").json()) == 3
    assert client.get("/api/locations/nope").status_code == 404


def test_events_when_and_archive(client):
    upcoming = client.get("/api/events").json()
    assert all(e["end"] >= "2026-11-22" for e in upcoming)
    assert [e["date"] for e in upcoming] == sorted(e["date"] for e in upcoming)
    today = client.get("/api/events", params={"when": "today"}).json()
    assert {e["id"] for e in today} == {"e1", "e11"}
    archive = client.get("/api/events", params={"archive": True}).json()
    assert {e["id"] for e in archive} == {"e9", "e10"}
    assert client.get("/api/events/e8").json()["status"] == "postponed"


def test_hidden(client):
    assert len(client.get("/api/hidden").json()) == 6
    assert all(h["col"] == "sea" for h in client.get("/api/hidden", params={"col": "sea"}).json())


def test_business_catalog_and_tracking(client):
    items = client.get("/api/businesses").json()
    assert "b8" not in {b["id"] for b in items}  # на модерации — не в каталоге
    assert items[0]["effectivePlan"] == "premium"
    b5 = client.get("/api/businesses/b5").json()
    assert b5["effectivePlan"] == "free" and b5["offers"] == []  # акции только у Pro/Premium
    b6 = client.get("/api/businesses/b6").json()
    assert b6["sub"]["plan"] == "trial" and b6["effectivePlan"] == "free"  # Trial истёк 20.11
    assert client.post("/api/businesses/b1/view").status_code == 204
    assert client.post("/api/businesses/b1/contact/wa").status_code == 204
    assert client.post("/api/businesses/b1/contact/fax").status_code == 404
    assert client.get("/api/businesses/b8").status_code == 404


def test_register_login_and_validation(client):
    r = client.post("/api/auth/register", json={"name": "", "email": "a@b.kz", "password": "12345678"})
    assert r.status_code == 422 and r.json()["detail"] == "Введите имя"
    r = client.post("/api/auth/register", json={"name": "Асель", "email": "asel@mail.kz", "password": "short"})
    assert r.json()["detail"] == "Пароль — минимум 8 символов"
    r = client.post("/api/auth/register", json={"name": "Асель", "email": "Asel@mail.kz", "password": "password1"})
    assert r.status_code == 201 and r.json()["user"]["role"] == "user"
    assert client.post("/api/auth/register", json={"name": "X", "email": "asel@mail.kz", "password": "password1"}).status_code == 409
    r = client.post("/api/auth/login", json={"email": "asel@mail.kz", "password": "password1"})
    token = r.json()["token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["email"] == "asel@mail.kz"
    assert client.post("/api/auth/login", json={"email": "asel@mail.kz", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "user@demo.kz", "password": "demo1234"}).status_code == 200


def test_register_business_gets_trial(client):
    r = client.post("/api/auth/register", json={"name": "Ержан", "email": "erzhan@mail.kz", "password": "password1",
                                                 "isBiz": True, "orgName": "Кофейня Бриз", "orgCat": "restaurants"})
    body = r.json()
    assert r.status_code == 201 and body["user"]["role"] == "business"
    assert body["org"]["sub"] == {"plan": "trial", "status": "trial", "start": "2026-11-22", "end": "2026-12-22"}
    assert body["org"]["status"] == "pending" and body["org"]["short"] == "КБ"


def test_auth_required_and_roles(client, as_role):
    assert client.get("/api/me/favorites").status_code == 401
    assert client.get("/api/cabinet/orgs", headers=as_role("user")).status_code == 403
    assert client.get("/api/admin/users", headers=as_role("manager")).status_code == 403
    assert client.get("/api/admin/locations", headers=as_role("manager")).status_code == 200
    # недействительный токен на публичном эндпоинте = гость
    assert client.get("/api/locations", headers={"Authorization": "Bearer junk"}).status_code == 200


def test_favorites_and_routes(client, as_role):
    h = as_role("user")
    assert client.put("/api/me/favorites/l3", headers=h).status_code == 200
    favs = client.put("/api/me/favorites/b1", headers=h).json()
    assert [(f["id"], f["kind"]) for f in favs] == [("l3", "place"), ("b1", "biz")]
    assert client.put("/api/me/favorites/b8", headers=h).status_code == 404  # не опубликована
    assert [f["id"] for f in client.delete("/api/me/favorites/l3", headers=h).json()] == ["b1"]

    plan = client.post("/api/planner/plan", json={"interests": ["family", "nature"], "duration": "day", "budget": 15000, "kids": True}).json()
    assert plan["stops"] and plan["stops"][0]["time"] == "10:00" and plan["overBudget"] is False
    r = client.post("/api/me/routes", headers=h, json={"w": plan["w"], "stops": plan["stops"]})
    assert r.status_code == 201 and r.json()["title"] == "Семья и Природа · 1 день"
    rid = r.json()["id"]
    assert len(client.get("/api/me/routes", headers=h).json()) == 1
    assert client.delete(f"/api/me/routes/{rid}", headers=as_role("admin")).status_code == 404  # чужой
    assert client.delete(f"/api/me/routes/{rid}", headers=h).status_code == 204


def test_planner_schedule_and_candidates(client):
    w = {"interests": ["sea"], "duration": "two", "budget": 50000}
    plan = client.post("/api/planner/plan", json=w).json()
    assert plan["days"] == ["2026-11-28", "2026-11-29"]
    stops = list(reversed(plan["stops"]))
    re = client.post("/api/planner/schedule", json={"w": plan["w"], "stops": stops}).json()
    assert [s["key"] for s in re["stops"]] == [s["key"] for s in stops]
    cands = client.post("/api/planner/candidates", json=w, params={"limit": 5}).json()
    assert len(cands) == 5 and cands[0]["score"] >= cands[-1]["score"]


def test_cabinet_flow(client, as_role):
    h = as_role("business")  # u3: b3 (Trial), b6 (Trial истёк)
    orgs = {o["id"]: o for o in client.get("/api/cabinet/orgs", headers=h).json()}
    assert set(orgs) == {"b3", "b6"} and orgs["b3"]["views"] > 0
    assert client.get("/api/cabinet/orgs/b1", headers=h).status_code == 404  # чужая

    st = client.get("/api/cabinet/orgs/b3/stats", headers=h).json()
    assert len(st["dailyViews"]) == 14 and set(st["clicks"]) == {"phone", "wa", "ig", "site"}
    assert client.get("/api/cabinet/orgs/b6/stats", headers=h).status_code == 403  # Free
    assert client.post("/api/cabinet/orgs/b6/offers", headers=h, json={"text": "−10%"}).status_code == 403

    r = client.post("/api/cabinet/orgs/b3/offers", headers=h, json={"text": "−10% на обед"})
    assert r.status_code == 201 and "−10% на обед" in r.json()["offers"]
    offers = r.json()["offers"]
    after = client.delete(f"/api/cabinet/orgs/b3/offers/{len(offers) - 1}", headers=h).json()["offers"]
    assert after == offers[:-1]

    upd = client.patch("/api/cabinet/orgs/b3", headers=h, json={"name": "Студия Ромашка", "phone": "+7 700 111 22 33", "ll": [51.16, 43.65]}).json()
    assert upd["short"] == "СР" and upd["ll"] == [51.16, 43.65]

    r = client.post("/api/cabinet/orgs/b6/subscription", headers=h, json={"plan": "pro"})
    body = r.json()
    assert r.status_code == 200 and body["org"]["sub"]["plan"] == "pro" and body["payment"]["amount"] == 9900
    assert client.post("/api/cabinet/orgs/b6/subscription", headers=h, json={"plan": "pro"}).status_code == 409
    assert len(client.get("/api/cabinet/orgs/b6/payments", headers=h).json()) == 1
    down = client.post("/api/cabinet/orgs/b6/subscription", headers=h, json={"plan": "free"}).json()
    assert down["payment"] is None and down["org"]["effectivePlan"] == "free"

    new = client.post("/api/cabinet/orgs", headers=h, json={"name": "Новая точка", "cat": "services"})
    assert new.status_code == 201 and new.json()["sub"]["plan"] == "trial"


def test_admin_moderation_and_content(client, as_role):
    m = as_role("manager")
    biz = client.get("/api/admin/businesses", headers=m).json()
    assert biz[0]["id"] == "b8"  # ожидающие модерации — первыми
    assert client.patch("/api/admin/businesses/b8", headers=m, json={"status": "approved", "verified": True}).json()["verified"] is True
    assert "b8" in {b["id"] for b in client.get("/api/businesses").json()}

    loc = client.post("/api/admin/locations", headers=m, json={"name": "Маяк", "cats": ["attractions"], "ll": [51.15, 43.65]})
    assert loc.status_code == 201 and loc.json()["published"] is True
    lid = loc.json()["id"]
    assert client.patch(f"/api/admin/locations/{lid}", headers=m, json={"published": False}).json()["published"] is False
    assert client.get(f"/api/locations/{lid}").status_code == 404
    assert client.get(f"/api/locations/{lid}", headers=m).status_code == 200
    assert client.post("/api/admin/locations", headers=m, json={"name": "X", "cats": ["bad"], "ll": [1, 2]}).status_code == 422

    h = client.post("/api/admin/hidden", headers=m, json={"title": "Новая запись", "col": "urban", "ll": [51.15, 43.65]}).json()
    assert h["n"] == "07"

    ev = client.post("/api/admin/events", headers=m, json={"title": "Концерт", "cat": "concerts", "date": "2026-12-01", "end": "2026-11-30",
                                                            "t1": "19:00", "t2": "21:00", "ll": [51.15, 43.65]})
    assert ev.status_code == 422
    assert client.patch("/api/admin/events/e2", headers=m, json={"status": "cancelled"}).json()["status"] == "cancelled"
    assert client.patch("/api/admin/events/e2", headers=m, json={"clearStatus": True}).json()["status"] is None
    assert client.delete(f"/api/admin/locations/{lid}", headers=m).status_code == 204


def test_admin_only_sections(client, as_role):
    a = as_role("admin")
    d = client.get("/api/admin/dashboard", headers=a).json()
    assert d["users"] == 9 and d["pending"] == 1 and len(d["registrationsByWeek"]) == 12
    assert client.post("/api/admin/subscriptions/expire", headers=a).json() == {"expired": 1}  # b6
    assert client.get("/api/businesses/b6").json()["sub"]["plan"] == "free"
    ext = client.post("/api/admin/businesses/b3/extend", headers=a, json={"days": 10}).json()
    assert ext["sub"]["end"] == "2026-12-20"
    assert client.patch("/api/admin/users/u1", headers=a, json={"blocked": True}).json()["blocked"] is True
    assert client.get("/api/me/favorites", headers=login_token(client)).status_code == 403
    assert client.patch("/api/admin/users/u5", headers=a, json={"blocked": True}).status_code == 409
    s = client.patch("/api/admin/settings", headers=a, json={"kz": False, "trialDays": 14}).json()
    assert s == {"kz": False, "en": True, "trialDays": 14}
    assert client.get("/api/meta").json()["languages"] == ["ru", "en"]
    ad = client.post("/api/admin/ads", headers=a, json={"name": "Баннер", "slot": "Главная", "biz": "b2", "from": "2026-12-01", "to": "2026-12-31"}).json()
    assert ad["from"] == "2026-12-01" and ad["biz"] == "b2"
    assert client.patch(f"/api/admin/ads/{ad['id']}", headers=a, json={"biz": None}).json()["biz"] is None
    assert client.post("/api/admin/ads", headers=a, json={"name": "X", "slot": "Y", "biz": "nope", "from": "2026-12-01", "to": "2026-12-02"}).status_code == 404
    rep = client.get("/api/admin/reports", headers=a).json()
    assert rep[0]["views"] >= rep[-1]["views"]


def login_token(client) -> dict:
    """Токен u1, полученный до блокировки, должен перестать работать."""
    r = client.post("/api/auth/login", json={"email": "user@demo.kz", "password": "demo1234"})
    assert r.status_code == 403
    from app.security import create_token

    return {"Authorization": "Bearer " + create_token("u1", "test-secret-key-of-sufficient-length-123", 5)}
