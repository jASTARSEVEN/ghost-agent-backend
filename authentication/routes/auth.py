from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone
from authentication.models import User, UserToken, Role
from common.dependencies import security, get_db, require_authenticated_user
from authentication.schemas import (
    UserCreate,
    UserOut,
    PasswordChange,
    RefreshTokenRequest,
    TokenSchema,
    LoginRequest,
    LoginResponse,
)
from authentication.utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from common.dependencies import get_db, require_authenticated_user
from common.response_handler import ResponseHandler
from common.config import settings

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/register", response_model=UserOut)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    # Check if user already exists
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        return ResponseHandler.bad_request(
            message="User with this email already exists"
        )

    # Create new user
    db_user = User(
        email=user_data.email,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        password=hash_password(user_data.password),
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return ResponseHandler.created(
        message="User registered successfully",
        data=db_user
    )


@auth_router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Login and get JWT tokens"""
    # Get user with roles and permissions eagerly loaded
    stmt = select(User).options(
        selectinload(User.roles).selectinload(Role.permissions)
    ).where(User.email == payload.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Verify user and password
    if not user or not verify_password(payload.password, user.password):
        return ResponseHandler.unauthorized("Invalid email or password")

    # Check if user is active
    if not user.is_active:
        return ResponseHandler.forbidden("User account is inactive")

    # Update last login
    user.last_login = datetime.now(timezone.utc)

    # Create tokens with user_id in payload (matching your structure)
    access_token = create_access_token({"user_id": user.id})
    refresh_token = create_refresh_token({"user_id": user.id})
    
    # Calculate expiry
    access_token_expiry = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # Check if token record exists for this user
    stmt = select(UserToken).where(UserToken.user_id == user.id)
    result = await db.execute(stmt)
    token_record = result.scalar_one_or_none()

    if not token_record:
        # Create new token record
        token_record = UserToken(
            user_id=user.id,
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expiry=access_token_expiry,
            is_revoked=False
        )
        db.add(token_record)
    else:
        # Update existing token record
        token_record.access_token = access_token
        token_record.refresh_token = refresh_token
        token_record.access_token_expiry = access_token_expiry
        token_record.is_revoked = False

    await db.commit()
    await db.refresh(user)

    # Build socket URL
    socket_protocol = "wss" if request.url.scheme == "https" else "ws"
    socket_url = f"{socket_protocol}://{request.url.netloc}/ws/{user.id}"

    # Prepare response
    user_data = UserOut.model_validate(user)
    token_data = TokenSchema(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        socket_url=socket_url
    )

    response_payload = LoginResponse(
        user=user_data,
        token=token_data
    )

    return ResponseHandler.ok("Login successful", data=response_payload)


@auth_router.post("/refresh")
async def refresh_access_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    # Decode refresh token
    try:
        payload = decode_token(refresh_data.refresh_token)
        user_id = payload.get("sub")
        if not user_id:
            return ResponseHandler.unauthorized(message="Invalid token")
    except HTTPException:
        return ResponseHandler.unauthorized(message="Invalid or expired refresh token")

    # Find token in database
    stmt = select(UserToken).where(
        UserToken.refresh_token == refresh_data.refresh_token,
        UserToken.is_revoked == False
    )
    result = await db.execute(stmt)
    token_record = result.scalar_one_or_none()

    if not token_record:
        return ResponseHandler.unauthorized(
            message="Refresh token is invalid or has been revoked"
        )

    # Create new access token
    new_access_token = create_access_token(data={"sub": user_id})
    new_expiry = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # Update token record
    token_record.access_token = new_access_token
    token_record.access_token_expiry = new_expiry
    await db.commit()

    return ResponseHandler.ok(
        message="Token refreshed successfully",
        data={
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


@auth_router.post("/logout")
async def logout(
    current_user: User = Depends(require_authenticated_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Logout user by revoking all tokens"""
    token = credentials.credentials
    
    # Revoke current token
    stmt = update(UserToken).where(
        UserToken.access_token == token
    ).values(is_revoked=True)
    await db.execute(stmt)
    await db.commit()

    return ResponseHandler.ok(message="Logged out successfully")




@auth_router.get("/me", response_model=UserOut)
async def get_my_profile(
    current_user: User = Depends(require_authenticated_user)
):
    """Get current user's profile"""
    return ResponseHandler.ok(
        message="Profile retrieved successfully",
        data=current_user
    )


@auth_router.put("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    # Verify old password
    if not verify_password(password_data.old_password, current_user.password):
        return ResponseHandler.bad_request(message="Incorrect old password")

    # Update password
    current_user.password = hash_password(password_data.new_password)
    
    # Revoke all existing tokens
    stmt = update(UserToken).where(
        UserToken.user_id == current_user.id
    ).values(is_revoked=True)
    await db.execute(stmt)
    
    await db.commit()

    return ResponseHandler.ok(
        message="Password changed successfully. Please login again."
    )