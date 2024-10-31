from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from config.db import get_db, redis
from models.users import User, UserMatch
from schemas.users import UserCreate, UserResponse, UserMatch as UserMatchSchema
from services.service import process_avatar
from services.email_service import send_email
from services.auth import create_access_token, authenticate_user, get_current_user
from geopy.distance import great_circle
from datetime import datetime, timedelta, timezone
import json
from hashlib import md5

router = APIRouter()

LIKES_LIMIT_PER_DAY = 5


@router.post("/api/clients/create", response_model=UserResponse)
async def register_user(
        first_name: str = Form(...),
        last_name: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        gender: str = Form(...),
        latitude: float = Form(...),
        longitude: float = Form(...),
        avatar: UploadFile | None = None,
        db: AsyncSession = Depends(get_db)
):
    # Проверка уникальности email
    user_exists = await db.execute(select(User).filter(User.email == email))
    if user_exists.scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    # Обработка аватара с водяным знаком
    processed_avatar_path = None
    if avatar:
        watermark_path = "images/watermark.jpg"
        processed_avatar_path = await process_avatar(avatar, watermark_path)

    # Создание пользователя
    user = User(
        avatar=processed_avatar_path,
        first_name=first_name,
        last_name=last_name,
        email=email,
        gender=gender,
        latitude=latitude,
        longitude=longitude,
    )
    user.set_password(password)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.post("/api/login")
async def login(email: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(email, password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/api/clients/{id}/match", response_model=dict)
async def match_user(
        match_data: UserMatchSchema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # Получаем целевого пользователя
    target_user = await db.get(User, match_data.target_user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Проверка количества симпатий за последние 24 часа
    last_24_hours = datetime.now(timezone.utc) - timedelta(days=1)
    likes_in_last_24_hours = await db.execute(
        select(UserMatch)
        .where(UserMatch.user_id == current_user.id, UserMatch.created_at >= last_24_hours)
    )
    likes_count = likes_in_last_24_hours.scalars().all()

    if len(likes_count) >= LIKES_LIMIT_PER_DAY:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily like limit reached")

    # Проверка взаимной симпатии
    existing_match = await db.execute(
        select(UserMatch).where(UserMatch.user_id == target_user.id, UserMatch.target_user_id == current_user.id)
    )
    if existing_match.scalar():
        # Индивидуальные сообщения для обоих пользователей
        user_message = f"Вам понравился {target_user.first_name}! Почта участника: {target_user.email}"
        target_user_message = f"Вам понравился {current_user.first_name}! Почта участника: {current_user.email}"

        # Отправка сообщений
        await send_email(current_user.email, "Взаимная симпатия!", user_message)
        await send_email(target_user.email, "Взаимная симпатия!", target_user_message)

        return {"message": "Взаимная симпатия: уведомления отправлены"}

    # Если взаимной симпатии нет, добавляем текущий лайк
    new_match = UserMatch(user_id=current_user.id, target_user_id=target_user.id)
    db.add(new_match)
    await db.commit()

    return {"message": "User liked"}


@router.get("/api/list", response_model=List[UserResponse])
async def get_users(
        gender: str | None = None,
        name: str | None = None,
        surname: str | None = None,
        distance_km: float | None = None,
        order_by_date: str | None = None,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    cache_key = md5(f"{gender}_{name}_{surname}_{distance_km}_{order_by_date}".encode()).hexdigest()

    cached_result = await redis.get(cache_key)

    if cached_result:
        return json.loads(cached_result)

    query = select(User)

    if gender:
        query = query.filter(User.gender == gender)
    if name:
        query = query.filter(User.first_name.ilike(f"%{name}%"))
    if surname:
        query = query.filter(User.last_name.ilike(f"%{surname}%"))

    # Условие сортировки по дате регистрации
    if order_by_date == "asc":
        query = query.order_by(User.created_at.asc())
    elif order_by_date == "desc":
        query = query.order_by(User.created_at.desc())

    result = await db.execute(query)
    users = result.scalars().all()

    # Фильтрация по расстоянию
    if distance_km is not None and current_user.latitude and current_user.longitude:
        user_location = (current_user.latitude, current_user.longitude)
        users = [
            user for user in users
            if user.latitude and user.longitude and
               great_circle(user_location, (user.latitude, user.longitude)).km <= distance_km
        ]

    return users