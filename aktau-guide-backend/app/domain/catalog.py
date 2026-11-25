"""Справочники: категории, подборки Hidden Aktau, тарифы (общие с фронтендом)."""
from __future__ import annotations

import json
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "seed_data.json"
_SEED = json.loads(SEED_PATH.read_text(encoding="utf-8"))

LOC_CATS: list[tuple[str, str, str]] = [tuple(x) for x in _SEED["LOC_CATS"]]  # (id, label, icon)
EV_CATS: list[tuple[str, str]] = [tuple(x) for x in _SEED["EV_CATS"]]
BIZ_CATS: list[tuple[str, str, str]] = [tuple(x) for x in _SEED["BIZ_CATS"]]
HID_COLS: list[tuple[str, str]] = [tuple(x) for x in _SEED["HID_COLS"]]
PLANS: list[dict] = _SEED["PLANS"]

LOC_CAT_IDS = {c[0] for c in LOC_CATS}
EV_CAT_IDS = {c[0] for c in EV_CATS}
BIZ_CAT_IDS = {c[0] for c in BIZ_CATS}
HID_COL_IDS = {c[0] for c in HID_COLS if c[0] != "all"}
PLAN_BY_ID = {p["id"]: p for p in PLANS}

ROLES = ("user", "business", "manager", "admin")
STAFF_ROLES = ("manager", "admin")
CONTACT_KINDS = ("phone", "wa", "ig", "site")


def loc_cat_name(cat_id: str) -> str:
    return next((c[1] for c in LOC_CATS if c[0] == cat_id), "")


def biz_cat_name(cat_id: str) -> str:
    return next((c[1] for c in BIZ_CATS if c[0] == cat_id), "")


def seed_data() -> dict:
    return _SEED
