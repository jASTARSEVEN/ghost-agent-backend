from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=255)
    first_name: str
    last_name: str


class UserSchema(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    is_active: bool
    profile_photo: Optional[str] = None
    last_login: Optional[datetime] = None

    model_config = {
        "from_attributes": True  # Enables ORM conversion in Pydantic v2
    }

class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str
    socket_url: str

class LoginResponseSchema(BaseModel):
    user: UserSchema
    token: TokenSchema



class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str

class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str