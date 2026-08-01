from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.auth.jwt import verify_password, create_access_token
from app.auth.deps import get_current_user, require_admin
from app.services.audit import record_audit_log

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        await record_audit_log(
            db,
            action="auth.login",
            actor=user,
            actor_username=None if user else form_data.username,
            target_type="user",
            target_id=user.id if user else form_data.username,
            result="failure",
            request=request,
            change_summary={"reason": "invalid_credentials"},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        await record_audit_log(
            db,
            action="auth.login",
            actor=user,
            target_type="user",
            target_id=user.id,
            result="failure",
            request=request,
            change_summary={"reason": "account_disabled"},
            commit=True,
        )
        raise HTTPException(status_code=403, detail="账号已禁用")

    await record_audit_log(
        db,
        action="auth.login",
        actor=user,
        target_type="user",
        target_id=user.id,
        request=request,
        change_summary={"method": "local"},
        commit=True,
    )
    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token, role=user.role, username=user.username)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    from app.auth.jwt import hash_password
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    await db.flush()
    await record_audit_log(
        db,
        action="user.create",
        actor=current,
        target_type="user",
        target_id=user.id,
        request=request,
        change_summary={
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
        },
    )
    await db.commit()
    await db.refresh(user)
    return user


class PasswordReset(BaseModel):
    new_password: str


class UserRoleUpdate(BaseModel):
    role: str  # "admin" 或 "viewer"


@router.patch("/users/{user_id}/toggle", response_model=UserOut)
async def toggle_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == current.id:
        raise HTTPException(400, "不能禁用自己")
    previous_state = user.is_active
    user.is_active = not user.is_active
    await record_audit_log(
        db,
        action="user.toggle",
        actor=current,
        target_type="user",
        target_id=user.id,
        request=request,
        change_summary={
            "username": user.username,
            "before": {"is_active": previous_state},
            "after": {"is_active": user.is_active},
        },
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/reset-password", response_model=UserOut)
async def reset_user_password(
    user_id: int,
    body: PasswordReset,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    """管理员强制重置用户密码"""
    from app.auth.jwt import hash_password
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if len(body.new_password) < 6:
        raise HTTPException(400, "密码长度至少 6 位")
    user.password_hash = hash_password(body.new_password)
    await record_audit_log(
        db,
        action="user.reset_password",
        actor=current,
        target_type="user",
        target_id=user.id,
        request=request,
        change_summary={
            "username": user.username,
            "authentication_updated": True,
        },
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/role", response_model=UserOut)
async def update_user_role(
    user_id: int,
    body: UserRoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    """管理员修改用户角色"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == current.id:
        raise HTTPException(400, "不能修改自己的角色")
    if body.role not in ("admin", "viewer"):
        raise HTTPException(400, "角色只能是 admin 或 viewer")
    previous_role = user.role
    user.role = body.role
    await record_audit_log(
        db,
        action="user.role_update",
        actor=current,
        target_type="user",
        target_id=user.id,
        request=request,
        change_summary={
            "username": user.username,
            "before": {"role": previous_role},
            "after": {"role": user.role},
        },
    )
    await db.commit()
    await db.refresh(user)
    return user
