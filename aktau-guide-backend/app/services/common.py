from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session


def new_id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


def get_or_404(db: Session, model: type, obj_id: str, what: str = "Запись") -> Any:
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what} не найдена")
    return obj


def patch_data(patch: BaseModel, keep_none: tuple[str, ...] = ()) -> dict[str, Any]:
    """Только переданные поля, с python-именами (не алиасами). null отбрасывается, кроме keep_none."""
    data = patch.model_dump(exclude_unset=True, by_alias=False)
    return {k: v for k, v in data.items() if v is not None or k in keep_none}


def apply_patch(obj: Any, data: dict[str, Any]) -> None:
    """Применяет словарь к ORM-объекту; ll раскладывается в lng/lat."""
    for key, value in data.items():
        if key == "ll":
            obj.lng, obj.lat = value
        else:
            setattr(obj, key, value)
