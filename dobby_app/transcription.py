from __future__ import annotations

from pathlib import Path

from aiogram import Bot
from aiogram.types import Message
from openai import AsyncOpenAI

from dobby_app.config import settings


async def download_voice(message: Message, bot: Bot) -> Path:
    if not message.voice:
        raise ValueError("Message does not contain a voice attachment")
    file = await bot.get_file(message.voice.file_id)
    suffix = Path(file.file_path or "").suffix or ".oga"
    destination = settings.media_root / "voice_messages" / f"voice_{message.message_id}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    await bot.download_file(file.file_path, destination=destination)
    return destination


async def transcribe_audio(path: Path) -> str:
    if not settings.openai_api_key:
        return "[voice message received, but OPENAI_API_KEY is not configured]"
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    with path.open("rb") as audio:
        result = await client.audio.transcriptions.create(
            model=settings.transcription_model,
            file=audio,
        )
    return result.text
