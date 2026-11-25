from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import DB, AppConfig, CurrentUser, Today
from ..domain.catalog import ROLES
from ..models import User
from ..schemas import EMAIL_RE, AuthOut, LoginIn, MePatch, RegisterIn, UserOut
from ..security import create_token, hash_password, verify_password
from ..services.common import new_id
from ..services.orgs import create_org
from ..services.serializers import biz_full

router = APIRouter(prefix="/auth", tags=["auth"])

# Демо-вход по роли: какой сидовый пользователь соответствует роли
DEMO_USERS = {"user": "u1", "business": "u3", "manager": "u4", "admin": "u5"}


def _bad(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)


def _auth(user: User, settings, org=None) -> AuthOut:
    return AuthOut(token=create_token(user.id, settings.secret_key, settings.token_ttl_minutes), user=UserOut.model_validate(user), org=org)


@router.post("/register", response_model=AuthOut, status_code=201, summary="Регистрация (с организацией — Trial 30 дней)")
def register(body: RegisterIn, db: DB, settings: AppConfig, today: Today):
    name, email = body.name.strip(), body.email.strip().lower()
    if not name:
        raise _bad("Введите имя")
    if not EMAIL_RE.match(email):
        raise _bad("Введите корректный email")
    if len(body.password) < 8:
        raise _bad("Пароль — минимум 8 символов")
    if body.is_biz and not body.org_name.strip():
        raise _bad("Введите название организации")
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Этот email уже зарегистрирован")

    user = User(id=new_id("u"), name=name, email=email, role="business" if body.is_biz else "user",
                password_hash=hash_password(body.password), created=today)
    db.add(user)
    db.flush()
    org = create_org(db, user, body.org_name, body.org_cat, today) if body.is_biz else None
    db.commit()
    return _auth(user, settings, biz_full(db, org, today) if org else None)


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, db: DB, settings: AppConfig):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    if user.blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Аккаунт заблокирован администратором")
    return _auth(user, settings)


@router.post("/demo/{role}", response_model=AuthOut, summary="Демо-вход по роли (только AG_DEMO_MODE=true)")
def demo_login(role: str, db: DB, settings: AppConfig):
    if not settings.demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    if role not in ROLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Неизвестная роль")
    user = db.get(User, DEMO_USERS[role])
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Демо-пользователь не найден")
    return _auth(user, settings)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: MePatch, user: CurrentUser, db: DB):
    user.name = body.name.strip()
    db.commit()
    return user
