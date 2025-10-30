from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from . import models, schemas, utils
from authentication.schemas import UserSchema, TokenSchema, LoginRequest, UserCreateRequest, RefreshTokenRequest, RefreshTokenResponse
from .auth import get_current_user
from common.response_handler import ResponseHandler
from database import get_db
from common.constants import SOCKET_URL

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/register")
def register(payload: UserCreateRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user:
        return ResponseHandler.bad_request("User with this email already exists.")

    hashed_password = utils.hash_password(payload.password)

    # Create new user
    new_user = models.User(
        email=payload.email,
        password=hashed_password,
        first_name=payload.first_name,
        last_name=payload.last_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    user_data = UserSchema.model_validate(new_user).model_dump()
    return ResponseHandler.ok("User registered successfully", data=user_data)


@auth_router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not utils.verify_password(payload.password, user.password):
        return ResponseHandler.unauthorized("Invalid email or password")

    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()

    access_token = utils.create_access_token({"user_id": user.id})
    refresh_token = utils.create_refresh_token({"user_id": user.id})

    expiry = datetime.now(timezone.utc) + timedelta(minutes=utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_record = db.query(models.UserToken).filter(models.UserToken.user_id == user.id).first()
    if not token_record:
        token_record = models.UserToken(
            user_id=user.id,
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expiry=expiry
        )
    else:
        token_record.access_token = access_token
        token_record.refresh_token = refresh_token
        token_record.access_token_expiry = expiry
    db.add(token_record)
    db.commit()

    user_data = UserSchema.model_validate(user)
    token_data = TokenSchema(
        access_token=access_token,
        refresh_token=refresh_token,
        socket_url=SOCKET_URL.format(protocol="wss" if request.url.scheme == "https" else "ws", 
                                    domain=request.url.hostname,
                                    user_id=user.id)
    )

    response_payload = {
        "user": user_data,
        "token": token_data
    }

    return ResponseHandler.ok("Login successful", data=response_payload)



@auth_router.post("/refresh-token")
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    token_record = db.query(models.UserToken).filter(
        models.UserToken.refresh_token == payload.refresh_token
    ).first()

    if not token_record:
        return ResponseHandler.unauthorized("Invalid refresh token")

    user_id = token_record.user_id
    access_token = utils.create_access_token({"user_id": user_id})
    refresh_token = utils.create_refresh_token({"user_id": user_id})

    expiry = datetime.now(timezone.utc) + timedelta(minutes=utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_record.access_token = access_token
    token_record.refresh_token = refresh_token
    token_record.access_token_expiry = expiry
    db.add(token_record)
    db.commit()

    response_payload = RefreshTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

    return ResponseHandler.ok("Token refreshed successfully", data=response_payload)

@auth_router.post("/logout")
def logout(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logs out the currently authenticated user by deleting their active token record.
    """
    try:
        token_record = (
            db.query(models.UserToken)
            .filter(models.UserToken.user_id == current_user.id)
            .first()
        )
        if not token_record:
            return ResponseHandler.bad_request(
                message="No active session found for this user."
            )
        db.delete(token_record)
        db.commit()

        return ResponseHandler.ok("User logged out successfully")

    except Exception as e:
        db.rollback()
        return ResponseHandler.bad_request(
            message=f"Error during logout: {str(e)}"
        )
    

user_router = APIRouter(prefix="/users", tags=["User"])

@user_router.get("/")
def get_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    user_data = [UserSchema.model_validate(user).model_dump() for user in users]
    return ResponseHandler.ok("User profiles fetched successfully", data=user_data)

@user_router.get("/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    user_data = schemas.UserSchema.model_validate(current_user)
    return ResponseHandler.ok("User profile fetched successfully", data=user_data)