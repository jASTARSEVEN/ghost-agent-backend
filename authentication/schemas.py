from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str
    last_name: str

class UserSchema(BaseModel):
    id: str
    email: EmailStr
    first_name: str
    last_name: str
    profile_photo: str | None = None
    last_login: datetime | None = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
