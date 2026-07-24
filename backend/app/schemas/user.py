from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
