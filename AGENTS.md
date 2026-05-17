# AGENTS.md — AI Prophet

## Project

Telegram bot + Telegram Mini App ("AI Prophet") — multimodal AI agent with chat, voice transcription, image analysis, music playlist generation, and web search. Deployed on Hugging Face Spaces.

## Entry Points

| File | Purpose |
|------|---------|
| `main.py` | **Primary entry point** — run this for local dev and Docker |
| `bot.py` | Redirector only — calls `main.py`, do not edit |
| `app.py` | Stale HF Spaces entry — references `start_bot` which does not exist; ignore |
| `webhook_only.py` | Webhook routes for HF Spaces (requires `PROXY_URL` to work) |

## Run

```bash
# 1. Copy env
cp .env.example .env   # fill in TELEGRAM_TOKEN, GEMINI_API_KEY, HF_TOKEN

# 2. Install deps (requires ffmpeg on system)
pip install -r requirements.txt

# 3. Run
python main.py
```

- Runs two processes: FastAPI on `PORT` (default 7860) + aiogram polling bot
- Auto-restarts on crash with 15s delay
- `IS_HF_SPACE` is detected via `SPACE_ID` env var
- Both local and HF modes use **polling** (webhook is blocked by HF without a proxy)

## Architecture

```
main.py
├── FastAPI (uvicorn) — health check + webhook routes on HF
└── aiogram Dispatcher (polling)
    ├── handlers/vip.py      — VIP mode, admin commands, password auth
    ├── handlers/limits.py   — per-user download duration/size limits
    └── handlers/messages.py — all user-facing: text, photo, voice, playlists, settings

core/
├── ai_engine.py   — Gemini client (google-genai SDK) + HF router (requests) + transcription
├── tools.py       — web search (DuckDuckGo), media search (YouTube/Jamendo/SoundCloud/Archive), download
├── network.py     — DNS patch (no-op in current code)
└── mcp_client.py  — MCP client (unused/stub)
```

- Router registration order in `main.py`: `vip` → `limits` → `messages` (matters for command precedence)
- User state stored in `temp/user_settings.json` (in-memory dict persisted to file; **lost on restart**)
- User limits stored in `temp/user_limits.json`
- All UI text is in Russian

## AI Engines

**Primary**: Gemini via `google-genai` SDK with function calling (`web_search`, `search_media_content`)
- Model fallback chain: `gemini-3.1-flash` → `gemini-3-flash-preview` → `gemini-2.5-flash` → `gemini-2.5-pro`

**Fallback**: Hugging Face Inference API via `router.huggingface.co` (OpenAI-compatible endpoints)
- Text: `Qwen/Qwen2.5-7B-Instruct`
- Vision: `meta-llama/Llama-3.2-11B-Vision-Instruct`
- Audio: `openai/whisper-large-v3-turbo`

User can switch engine per-chat: auto (Gemini→HF), Gemini only, HF only.

## Key Conventions

- **FREE-FIRST**: all services must use free tiers by default (`DEVELOPMENT_PRINCIPLES.md`)
- `config.py` loads env via `python-dotenv`; never hardcode secrets
- `TEMP_DIR` ("temp/") is cleaned on bot start; per-user files use `task_{chat_id}_*` and `audio_{chat_id}_*` patterns
- Media markers in AI responses: `[MEDIA: query, type, count]` triggers automatic search/download
- Step markers in Gemini responses: `ШАГ: [text]` become inline keyboard buttons
- Telegram callback data limited to 64 bytes; Cyrillic is 2 bytes/char in UTF-8

## CI/CD

`.github/workflows/sync_hf.yml` — on **any branch push**, force-pushes to HF Spaces `dizel0110/ai_prophet`. No PR gate. `main` branch push = production deploy.

## Docker

`Dockerfile` based on `python:3.11-slim`, installs `ffmpeg` and `dnsutils`. CMD: `python main.py`.
`.dockerignore` excludes `venv/`, `temp/`, `*.md` (except README), `test_*.py`, `internal/`.

## System Dependencies

- **ffmpeg** required for audio conversion (OGG→WAV) and yt-dlp post-processing
- Without ffmpeg, audio falls back to raw OGG and yt-dlp skips post-processing

## Testing

No test framework configured. Test files (`test_*.py`) are manual scripts excluded from Docker.

## Env Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `TELEGRAM_TOKEN` | Yes | Bot token from BotFather |
| `GEMINI_API_KEY` | Yes | Google AI Studio key |
| `HF_TOKEN` | Yes | Hugging Face token (needs `write` scope) |
| `PORT` | No | Default 7860 (HF Spaces standard) |
| `PROXY_URL` | No | HTTP proxy for Telegram API on HF Spaces |
| `VIP_PASSWORD` | No | Default `prophet2026` |
| `VIP_RESET_PASSWORD` | No | Default `reset2026` |

## Gotchas & Known Issues

- **HF Spaces blocks outgoing Telegram API** — polling requires `PROXY_URL` secret on HF. Without it, bot crashes with `ClientConnectorError`.
- **google-genai SDK 2.x** requires `genai_types.FunctionDeclaration` for tools, NOT raw dicts with `parameters`. Use `inputSchema` format via `genai_types.Schema`.
- **Duplicate text handlers** — `@router.message()` (catch-all) and `@router.message(F.text)` both fire on text. Only use `@router.message()` in `handle_text`; the `F.text` handler was removed.
- **HF fallback must `return`** — after `get_hf_response()` succeeds, code must return. Otherwise it falls through to Gemini loop (429) → back to HF → duplicate response.
- **Logs** go to `logs/bot_YYYYMMDD.log` — excluded from git and Docker.
- **Two python processes** on local run: FastAPI (uvicorn) + aiogram polling. This is normal.
- **`app.py` is stale** — references `start_bot` which doesn't exist. Only `main.py` works.
- **Gemini quota exhaustion** — free tier hits 429 quickly. HF fallback handles it, but session creation is retried across all 4 models before giving up.
