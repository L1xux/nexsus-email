from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    from app.models.user import User
    from sqlalchemy import select
    
    if settings.app_env == "development" and not token:
        result = await db.execute(select(User).where(User.email == "dev@nexusmail.local"))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                email="dev@nexusmail.local",
                name="Dev User",
                picture=None,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        if settings.app_env == "development":
            result = await db.execute(select(User).where(User.email == "dev@nexusmail.local"))
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    email="dev@nexusmail.local",
                    name="Dev User",
                    picture=None,
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
            return user
        raise credentials_exception
    
    payload = decode_token(token)
    if payload is None:
        if settings.app_env == "development":
            result = await db.execute(select(User).where(User.email == "dev@nexusmail.local"))
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    email="dev@nexusmail.local",
                    name="Dev User",
                    picture=None,
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
            return user
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    return user
