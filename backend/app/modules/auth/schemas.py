from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=200, description="Staff email or student PRN")
    password: str = Field(..., min_length=1, max_length=200)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=1, max_length=200)


class SetupRequest(BaseModel):
    setup_token: str = Field(..., min_length=1, max_length=200)
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=200)
