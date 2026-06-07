from __future__ import annotations

import asyncio
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
    settings.media_root.mkdir(parents=True, exist_ok=True)
    destination = settings.media_root / "voice_messages" / f"voice_{message.message_id}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    await bot.download_file(file.file_path, destination=destination)
    return destination


async def transcribe_audio(path: Path) -> str:
    if not settings.openai_api_key:
        return "[voice message received, but OPENAI_API_KEY is not configured]"
    audio_path = await _ensure_supported_audio(path)
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    with audio_path.open("rb") as audio:
        result = await client.audio.transcriptions.create(
            model=settings.transcription_model,
            file=audio,
        )
    return result.text


async def _ensure_supported_audio(path: Path) -> Path:
    if path.suffix.lower() not in {".oga", ".ogg", ".opus"}:
        return path

    output = path.with_suffix(".mp3")
    if output.exists() and output.stat().st_size > 0:
        return output

    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "4",
        str(output),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg could not convert Telegram voice message: {detail}")
    return output
