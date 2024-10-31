from pydantic import BaseModel, EmailStr
from fastapi import UploadFile

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    gender: str
    latitude: float | None = None
    longitude: float | None = None
    avatar: UploadFile | None = None  # Поле для загрузки аватара

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: int
    avatar: str | None = None  # Поле для отображения обработанного аватара
    first_name: str
    last_name: str
    email: EmailStr
    gender: str

    class Config:
        from_attributes = True

class UserMatch(BaseModel):
    target_user_id: int

    class Config:
        from_attributes = True