#!/usr/bin/env python3
"""CLI for sending and retrieving messages with one Telegram bot/user pair."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(os.environ.get("DOBBY_ROOT", Path.cwd())).resolve()
ENV_PATH = PROJECT_ROOT / ".env"
OFFSET_PATH = PROJECT_ROOT / "storage" / "telegram_offset"
VOICE_DIR = PROJECT_ROOT / "storage" / "media" / "voice_messages"
MEDIA_DIR = PROJECT_ROOT / "storage" / "media" / "media_messages"
TELEGRAM_API_BASE = "https://api.telegram.org"
OPENAI_TRANSCRIPTIONS_URL = "https://api.openai.com/v1/audio/transcriptions"


class ConfigError(Exception):
    pass


class TelegramError(Exception):
    pass


class TranscriptionError(Exception):
    pass


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise ConfigError(f"Missing env file: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def get_config() -> tuple[str, int]:
    env_values = load_env(ENV_PATH)
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env_values.get("TELEGRAM_BOT_TOKEN", "")
    user_id_raw = os.environ.get("TELEGRAM_USER_ID") or env_values.get("TELEGRAM_USER_ID", "")

    if not token or token == "replace_with_bot_token":
        raise ConfigError("Set TELEGRAM_BOT_TOKEN in .env")
    if not user_id_raw or user_id_raw == "replace_with_numeric_user_id":
        raise ConfigError("Set TELEGRAM_USER_ID in .env")

    try:
        user_id = int(user_id_raw)
    except ValueError as exc:
        raise ConfigError("TELEGRAM_USER_ID must be a numeric Telegram user id") from exc

    return token, user_id


def get_optional_env(name: str, default: str = "") -> str:
    env_values = load_env(ENV_PATH)
    return os.environ.get(name) or env_values.get(name, default)


def telegram_request(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{TELEGRAM_API_BASE}/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise TelegramError(f"Telegram API HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise TelegramError(f"Telegram API request failed: {exc.reason}") from exc

    result = json.loads(body)
    if not result.get("ok"):
        raise TelegramError(result.get("description", "Telegram API returned ok=false"))
    return result


def telegram_download(token: str, file_path: str, destination: Path) -> None:
    url = f"{TELEGRAM_API_BASE}/file/bot{token}/{file_path}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            destination.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise TelegramError(f"Telegram file download HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise TelegramError(f"Telegram file download failed: {exc.reason}") from exc


def get_telegram_file_path(token: str, file_id: str) -> str:
    response = telegram_request(token, "getFile", {"file_id": file_id})
    file_path = response.get("result", {}).get("file_path")
    if not file_path:
        raise TelegramError("Telegram getFile response did not include file_path")
    return file_path


def read_offset() -> int | None:
    if not OFFSET_PATH.exists():
        return None
    raw_value = OFFSET_PATH.read_text(encoding="utf-8").strip()
    if not raw_value:
        return None
    return int(raw_value)


def write_offset(offset: int) -> None:
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_PATH.write_text(f"{offset}\n", encoding="utf-8")


def extract_message(update: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        message = update.get(key)
        if message:
            return message
    return None


def message_text(message: dict[str, Any]) -> str:
    if "text" in message:
        return message["text"]
    caption = message.get("caption")
    if "voice" in message:
        voice = message["voice"]
        duration = voice.get("duration")
        duration_text = f", {duration}s" if duration else ""
        label = f"[voice message{duration_text}]"
        return f"{label} {caption}" if caption else label
    if "photo" in message:
        sizes = message["photo"]
        size_count = len(sizes) if isinstance(sizes, list) else 0
        label = f"[photo message, {size_count} sizes]" if size_count else "[photo message]"
        return f"{label} {caption}" if caption else label
    if "video" in message:
        video = message["video"]
        duration = video.get("duration")
        width = video.get("width")
        height = video.get("height")
        details = []
        if duration:
            details.append(f"{duration}s")
        if width and height:
            details.append(f"{width}x{height}")
        detail_text = f", {', '.join(details)}" if details else ""
        label = f"[video message{detail_text}]"
        return f"{label} {caption}" if caption else label
    if caption:
        return caption

    content_keys = sorted(key for key in message.keys() if key not in {"from", "chat", "date", "message_id"})
    if not content_keys:
        return "[non-text message]"
    return f"[non-text message: {', '.join(content_keys)}]"


def voice_filename(message: dict[str, Any], file_path: str) -> str:
    message_id = message.get("message_id", "unknown")
    suffix = Path(file_path).suffix or ".oga"
    return f"voice_{message_id}{suffix}"


def media_filename(message: dict[str, Any], media_type: str, file_path: str) -> str:
    message_id = message.get("message_id", "unknown")
    suffix = Path(file_path).suffix
    if not suffix:
        suffix = ".jpg" if media_type == "photo" else ".mp4"
    return f"{media_type}_{message_id}{suffix}"


def largest_photo(message: dict[str, Any]) -> dict[str, Any] | None:
    photos = message.get("photo")
    if not isinstance(photos, list) or not photos:
        return None
    return max(
        photos,
        key=lambda photo: (
            int(photo.get("file_size") or 0),
            int(photo.get("width") or 0) * int(photo.get("height") or 0),
        ),
    )


def download_voice(token: str, message: dict[str, Any]) -> Path | None:
    voice = message.get("voice")
    if not voice:
        return None

    file_id = voice.get("file_id")
    if not file_id:
        raise TelegramError("Voice message did not include file_id")

    file_path = get_telegram_file_path(token, file_id)
    destination = VOICE_DIR / voice_filename(message, file_path)
    telegram_download(token, file_path, destination)
    return destination


def download_photo(token: str, message: dict[str, Any]) -> Path | None:
    photo = largest_photo(message)
    if not photo:
        return None

    file_id = photo.get("file_id")
    if not file_id:
        raise TelegramError("Photo message did not include file_id")

    file_path = get_telegram_file_path(token, file_id)
    destination = MEDIA_DIR / "photos" / media_filename(message, "photo", file_path)
    telegram_download(token, file_path, destination)
    return destination


def download_video(token: str, message: dict[str, Any]) -> Path | None:
    video = message.get("video")
    if not video:
        return None

    file_id = video.get("file_id")
    if not file_id:
        raise TelegramError("Video message did not include file_id")

    file_path = get_telegram_file_path(token, file_id)
    destination = MEDIA_DIR / "videos" / media_filename(message, "video", file_path)
    telegram_download(token, file_path, destination)
    return destination


def convert_audio_for_transcription(source: Path) -> Path:
    supported_suffixes = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
    if source.suffix.lower() in supported_suffixes:
        return source

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise TranscriptionError(f"{source.name} needs conversion before transcription, but ffmpeg was not found.")

    converted = source.with_suffix(".mp3")
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(source),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "3",
        str(converted),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise TranscriptionError(completed.stderr.strip() or "ffmpeg conversion failed")
    return converted


def multipart_form_data(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = "----telegram-bot-cli-boundary"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return b"".join(chunks), boundary


def transcribe_audio(audio_path: Path) -> str:
    api_key = get_optional_env("OPENAI_API_KEY")
    if not api_key:
        raise TranscriptionError("Set OPENAI_API_KEY in .env to transcribe voice messages")

    model = get_optional_env("TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
    upload_path = convert_audio_for_transcription(audio_path)
    body, boundary = multipart_form_data({"model": model}, "file", upload_path)
    request = urllib.request.Request(
        OPENAI_TRANSCRIPTIONS_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise TranscriptionError(f"OpenAI transcription HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise TranscriptionError(f"OpenAI transcription request failed: {exc.reason}") from exc

    text = result.get("text")
    if not isinstance(text, str):
        raise TranscriptionError("OpenAI transcription response did not include text")
    return text


def retrieve_messages(
    token: str,
    user_id: int,
    limit: int,
    peek: bool,
    download_voice_files: bool,
    download_photo_files: bool,
    download_video_files: bool,
    transcribe_voice_files: bool,
) -> int:
    payload: dict[str, Any] = {
        "limit": limit,
        "timeout": 0,
        "allowed_updates": json.dumps(["message", "edited_message"]),
    }
    offset = read_offset()
    if offset is not None:
        payload["offset"] = offset

    response = telegram_request(token, "getUpdates", payload)
    updates = response.get("result", [])
    next_offset = offset
    matched = 0
    transcription_enabled = bool(get_optional_env("OPENAI_API_KEY"))
    warned_transcription_off = False

    for update in updates:
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            next_offset = max(next_offset or 0, update_id + 1)

        message = extract_message(update)
        sender = message.get("from", {}) if message else {}
        if not message or sender.get("id") != user_id:
            continue

        matched += 1
        name = " ".join(part for part in (sender.get("first_name"), sender.get("last_name")) if part)
        username = f"@{sender['username']}" if sender.get("username") else ""
        label = " ".join(part for part in (name, username) if part) or str(user_id)
        print(f"{message.get('message_id', '?')} | {label}: {message_text(message)}")

        if message.get("voice") and (download_voice_files or transcribe_voice_files):
            voice_path = download_voice(token, message)
            if voice_path:
                print(f"  voice: {voice_path}")
                if transcribe_voice_files:
                    if transcription_enabled:
                        print(f"  transcript: {transcribe_audio(voice_path)}")
                    elif not warned_transcription_off:
                        print("  warning: OPENAI_API_KEY is not set; transcription is off.")
                        warned_transcription_off = True
        if message.get("photo") and download_photo_files:
            photo_path = download_photo(token, message)
            if photo_path:
                print(f"  photo: {photo_path}")
        if message.get("video") and download_video_files:
            video_path = download_video(token, message)
            if video_path:
                print(f"  video: {video_path}")

    if next_offset is not None and not peek:
        write_offset(next_offset)

    if matched == 0:
        print("No new messages from the configured user.")
    return 0


def send_message(token: str, user_id: int, text: str) -> int:
    response = telegram_request(
        token,
        "sendMessage",
        {
            "chat_id": user_id,
            "text": text,
            "disable_web_page_preview": "true",
        },
    )
    message = response["result"]
    print(f"Sent message {message.get('message_id', '?')} to {user_id}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send and retrieve Telegram bot messages for one configured user.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    retrieve_parser = subparsers.add_parser("retrieve", help="retrieve new messages from the configured user")
    retrieve_parser.add_argument("--limit", type=int, default=100, help="maximum Telegram updates to fetch")
    retrieve_parser.add_argument("--peek", action="store_true", help="do not advance the stored update offset")
    retrieve_parser.add_argument("--download-voice", action="store_true", help="download voice messages to storage/media/voice_messages/")
    retrieve_parser.add_argument("--download-photos", action="store_true", help="download photo messages to storage/media/media_messages/photos/")
    retrieve_parser.add_argument("--download-videos", action="store_true", help="download video messages to storage/media/media_messages/videos/")
    retrieve_parser.add_argument("--download-media", action="store_true", help="download photo and video messages")
    retrieve_parser.add_argument("--transcribe", action="store_true", help="download and transcribe voice messages")

    send_parser = subparsers.add_parser("send", help="send a message to the configured user")
    send_parser.add_argument("message", nargs="+", help="message text to send")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        token, user_id = get_config()
        if args.command == "retrieve":
            return retrieve_messages(
                token,
                user_id,
                args.limit,
                args.peek,
                args.download_voice,
                args.download_photos or args.download_media,
                args.download_videos or args.download_media,
                args.transcribe,
            )
        if args.command == "send":
            return send_message(token, user_id, " ".join(args.message))
    except (ConfigError, TelegramError, TranscriptionError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
