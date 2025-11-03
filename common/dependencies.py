from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional, Callable
from authentication.models import User, UserToken, Role
from database import get_db
from authentication.utils import decode_token

security = HTTPBearer(auto_error=False)


async def get_current_user_from_token(
    token: str,
    db: AsyncSession
) -> Optional[User]:
    """Extract and validate user from JWT token"""
    if not token:
        return None

    # Decode token
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        return None

    # Check if token is revoked
    stmt = select(UserToken).where(
        UserToken.access_token == token,
        UserToken.is_revoked == False
    )
    result = await db.execute(stmt)
    token_record = result.scalar_one_or_none()
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked or is invalid"
        )

    # Get user with roles and permissions eagerly loaded
    stmt = select(User).options(
        selectinload(User.roles).selectinload(Role.permissions)
    ).where(User.id == int(user_id))
    
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    return user if user and user.is_active else None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token (optional)"""
    if not credentials:
        return None

    token = credentials.credentials
    if token.startswith('Bearer '):
        token = token[7:]

    return await get_current_user_from_token(token, db)


async def require_authenticated_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Require authenticated user"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_permission(permission: str) -> Callable:
    """
    Dependency factory for permission checking
    Usage: Depends(require_permission("user.assign-role"))
    """
    async def permission_checker(
        current_user: User = Depends(require_authenticated_user)
    ) -> User:
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required permission: {permission}"
            )
        return current_user

    return permission_checker


def require_any_permission(*permissions: str) -> Callable:
    """
    Require at least one of the specified permissions
    Usage: Depends(require_any_permission("user.view", "user.list"))
    """
    async def permission_checker(
        current_user: User = Depends(require_authenticated_user)
    ) -> User:
        if not any(current_user.has_permission(perm) for perm in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required one of: {', '.join(permissions)}"
            )
        return current_user

    return permission_checker