import asyncio
from PIL import Image
from fastapi import UploadFile

async def process_avatar(avatar: UploadFile, watermark_path: str) -> str:
    # Асинхронное выполнение с использованием run_in_executor
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sync_process_avatar, avatar, watermark_path)

def sync_process_avatar(avatar: UploadFile, watermark_path: str) -> str:
    avatar_image = Image.open(avatar.file)
    watermark = Image.open(watermark_path).convert("RGBA")
    avatar_image.paste(watermark, (0, 0), watermark)
    output_path = f"images/processed_{avatar.filename}"
    avatar_image.save(output_path, format="PNG")
    return output_path