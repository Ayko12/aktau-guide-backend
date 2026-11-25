"""Личное: избранное и сохранённые маршруты."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import DB, CurrentUser, Today
from ..domain.catalog import biz_cat_name, loc_cat_name
from ..domain.planner import plan_title
from ..models import Business, Favorite, Location, SavedRoute
from ..schemas import FavoriteOut, RouteIn, RouteOut
from ..services.common import new_id

router = APIRouter(prefix="/me", tags=["me"])


def _favorites(db: DB, user_id: str) -> list[FavoriteOut]:
    out = []
    for fav in db.scalars(select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at)):
        if loc := db.get(Location, fav.item_id):
            out.append(FavoriteOut(id=loc.id, kind="place", name=loc.name, cat=loc_cat_name(loc.cats[0]) if loc.cats else ""))
        elif biz := db.get(Business, fav.item_id):
            out.append(FavoriteOut(id=biz.id, kind="biz", name=biz.name, cat=biz_cat_name(biz.cat)))
    return out


@router.get("/favorites", response_model=list[FavoriteOut])
def list_favorites(user: CurrentUser, db: DB):
    return _favorites(db, user.id)


@router.put("/favorites/{item_id}", response_model=list[FavoriteOut], summary="Добавить место или организацию в избранное")
def add_favorite(item_id: str, user: CurrentUser, db: DB):
    loc = db.get(Location, item_id)
    biz = db.get(Business, item_id) if loc is None else None
    if not ((loc and loc.published) or (biz and biz.status == "approved")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Место или организация не найдены")
    if db.get(Favorite, (user.id, item_id)) is None:
        db.add(Favorite(user_id=user.id, item_id=item_id))
        db.commit()
    return _favorites(db, user.id)


@router.delete("/favorites/{item_id}", response_model=list[FavoriteOut])
def remove_favorite(item_id: str, user: CurrentUser, db: DB):
    fav = db.get(Favorite, (user.id, item_id))
    if fav:
        db.delete(fav)
        db.commit()
    return _favorites(db, user.id)


@router.get("/routes", response_model=list[RouteOut])
def list_routes(user: CurrentUser, db: DB):
    return db.scalars(select(SavedRoute).where(SavedRoute.owner_id == user.id).order_by(SavedRoute.created.desc(), SavedRoute.id.desc())).all()


@router.post("/routes", response_model=RouteOut, status_code=201)
def save_route(body: RouteIn, user: CurrentUser, db: DB, today: Today):
    w = body.w.model_dump(by_alias=False)
    route = SavedRoute(
        id=new_id("r"), owner_id=user.id, title=body.title or plan_title(w), w=w,
        stops=[s.model_dump(by_alias=False, exclude_none=True) for s in body.stops], created=today,
    )
    db.add(route)
    db.commit()
    return route


@router.delete("/routes/{route_id}", status_code=204)
def delete_route(route_id: str, user: CurrentUser, db: DB):
    route = db.get(SavedRoute, route_id)
    if route is None or route.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Маршрут не найден")
    db.delete(route)
    db.commit()
