# Telegram Bot CLI

Small command-line app for one Telegram bot talking to one configured user.

## Setup

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_USER_ID=123456789
OPENAI_API_KEY=
TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
```

## Usage

From this folder:

```bash
python3 telegram_app.py retrieve
python3 telegram_app.py send "hello from the bot"
```

`retrieve` prints new messages from the configured user and stores the Telegram update offset in `.telegram_offset` so repeated runs only show newer updates.

Use `--peek` if you want to inspect updates without advancing the saved offset:

```bash
python3 telegram_app.py retrieve --peek
```

## Media Messages

Voice, photo, and video messages are shown by `retrieve` as typed entries. Captions are printed with the media entry when present.

To save the original Telegram voice files:

```bash
python3 telegram_app.py retrieve --download-voice
```

Files are saved in `voice_messages/`.

To save Telegram photos and videos:

```bash
python3 telegram_app.py retrieve --download-media
```

Photos are saved in `media_messages/photos/`. Videos are saved in `media_messages/videos/`.

You can also request only one media type:

```bash
python3 telegram_app.py retrieve --download-photos
python3 telegram_app.py retrieve --download-videos
```

To transcribe voice messages, set `OPENAI_API_KEY` in `.env`, then run:

```bash
python3 telegram_app.py retrieve --transcribe
```

Telegram voice messages are OGG/Opus files, so the app converts them to mp3 with `ffmpeg` before sending them to OpenAI transcription.
