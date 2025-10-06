# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from datetime import datetime, timezone, timedelta
# from . import models, schemas, utils
# from .response_handler import ResponseHandler
# from database import get_db
#
# router = APIRouter(prefix="/auth", tags=["Authentication"])
#
# @router.post("/login")
# def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
#     user = db.query(models.User).filter(models.User.email == payload.email).first()
#     if not user or not utils.verify_password(payload.password, user.password):
#         return ResponseHandler.unauthorized("Invalid email or password")
#
#     user.last_login = datetime.now(timezone.utc)
#     db.add(user)
#     db.commit()
#
#     access_token = utils.create_access_token({"user_id": user.id})
#     refresh_token = utils.create_refresh_token({"user_id": user.id})
#     expiry = datetime.now(timezone.utc) + timedelta(minutes=utils.ACCESS_TOKEN_EXPIRE_MINUTES)
#
#     token = db.query(models.UserToken).filter(models.UserToken.user_id == user.id).first()
#     if not token:
#         token = models.UserToken(user_id=user.id, refresh_token=refresh_token, access_token=access_token, access_token_expiry=expiry)
#     else:
#         token.access_token = access_token
#         token.refresh_token = refresh_token
#         token.access_token_expiry = expiry
#     db.add(token)
#     db.commit()
#
#     return ResponseHandler.ok("Login successful", {
#         "user": schemas.UserSchema.from_orm(user),
#         "access_token": access_token,
#         "refresh_token": refresh_token
#     })
#
#
# @router.post("/refresh-token")
# def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
#     payload = utils.decode_token(refresh_token)
#     user = db.query(models.User).filter(models.User.id == payload.get("user_id")).first()
#     if not user:
#         return ResponseHandler.unauthorized("Invalid refresh token")
#
#     token = db.query(models.UserToken).filter(models.UserToken.user_id == user.id, models.UserToken.refresh_token == refresh_token).first()
#     if not token:
#         return ResponseHandler.unauthorized("Invalid refresh token")
#
#     new_access = utils.create_access_token({"user_id": user.id})
#     token.access_token = new_access
#     token.access_token_expiry = datetime.now(timezone.utc) + timedelta(minutes=utils.ACCESS_TOKEN_EXPIRE_MINUTES)
#     db.commit()
#
#     return ResponseHandler.ok("Access token refreshed", {"access_token": new_access})
#
#
# @router.get("/logout")
# def logout(user: models.User = Depends(utils.decode_token), db: Session = Depends(get_db)):
#     try:
#         db.query(models.UserToken).filter(models.UserToken.user_id == user["user_id"]).delete()
#         db.commit()
#         return ResponseHandler.ok("Logout successful")
#     except Exception as e:
#         return ResponseHandler.response("Logout failed", errors=str(e), status_code=500)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from . import models, schemas, utils
from .auth import get_current_user
from response_handler import ResponseHandler
from database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def register_user(payload: schemas.UserCreateRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user:
        return ResponseHandler.bad_request("User with this email already exists.")

    hashed_password = utils.hash_password(payload.password)
    new_user = models.User(
        email=payload.email,
        password=hashed_password,
        first_name=payload.first_name,
        last_name=payload.last_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return ResponseHandler.ok("User registered successfully", schemas.UserSchema.from_orm(new_user).dict())


@router.post("/login")
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
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
        token_record = models.UserToken(user_id=user.id, refresh_token=refresh_token, access_token=access_token,
                                        access_token_expiry=expiry)
    else:
        token_record.access_token = access_token
        token_record.refresh_token = refresh_token
        token_record.access_token_expiry = expiry
    db.add(token_record)
    db.commit()

    return ResponseHandler.ok("Login successful", {
        "user": schemas.UserSchema.from_orm(user).dict(),
        "access_token": access_token,
        "refresh_token": refresh_token
    })


@router.get("/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    user_data = schemas.UserSchema.from_orm(current_user)
    return ResponseHandler.ok("User profile fetched successfully", user_data.dict())
