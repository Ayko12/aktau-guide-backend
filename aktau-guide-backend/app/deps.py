"""Зависимости FastAPI: БД, настройки, текущий пользователь, проверка ролей."""
from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import Settings
from .db import get_db
from .models import User
from .security import decode_token

bearer = HTTPBearer(auto_error=False, description="JWT из /api/auth/login")


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_today(settings: Annotated[Settings, Depends(get_app_settings)]) -> dt.date:
    return settings.today()


DB = Annotated[Session, Depends(get_db)]
AppConfig = Annotated[Settings, Depends(get_app_settings)]
Today = Annotated[dt.date, Depends(get_today)]


Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def _token_user(db: Session, settings: Settings, creds: HTTPAuthorizationCredentials | None) -> User | None:
    if creds is None:
        return None
    user_id = decode_token(creds.credentials, settings.secret_key)
    return db.get(User, user_id) if user_id else None


def current_user_optional(db: DB, settings: AppConfig, creds: Credentials) -> User | None:
    """Для публичных эндпоинтов: недействительный токен или блокировка = гость."""
    user = _token_user(db, settings, creds)
    return None if user is None or user.blocked else user


OptionalUser = Annotated[User | None, Depends(current_user_optional)]


def current_user(db: DB, settings: AppConfig, creds: Credentials) -> User:
    user = _token_user(db, settings, creds)
    if user is None:
        msg = "Нужен вход" if creds is None else "Сессия истекла, войдите снова"
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, msg, headers={"WWW-Authenticate": "Bearer"})
    if user.blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Аккаунт заблокирован администратором")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: str):
    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав для этого раздела")
        return user

    return checker


BusinessUser = Annotated[User, Depends(require_roles("business", "admin"))]
StaffUser = Annotated[User, Depends(require_roles("manager", "admin"))]
AdminUser = Annotated[User, Depends(require_roles("admin"))]


def is_staff(user: User | None) -> bool:
    return user is not None and user.role in ("manager", "admin")
