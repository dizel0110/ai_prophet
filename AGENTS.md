# AGENTS.md — AI Prophet

## 🧭 Главный принцип проекта

**Кратчайший путь клиента.** Любая фича, любой запрос реализуется так, чтобы пользователь дошёл до результата за минимальное число действий. Не создавай лишних шагов, не прячь функционал.

Всё, что добавляется в проект — это **фича AI Prophet**, а не отдельный продукт. Массажный салон, музыка, поиск — всё это возможности главного ИИ-проводника, а не самостоятельные сервисы.

## 📈 Принцип масштабирования (Scale‑Ready)

Любой код пишется так, чтобы приложение можно было расширить на большую аудиторию **без переписывания**:

1. **Платформенная независимость** — не хардкодить `SPACE_ID`, `localhost` или конкретный URL. Использовать `PLATFORM` env var (`hf` | `render` | `local`) и `get_base_url()`.
2. **Расширение = новые инстансы, не новый код** — при росте нагрузки добавляются Replica на Render / Worker на Fly.io / VPS, а не меняется логика.
3. **Stateless по умолчанию** — состояние пользователя в файлах `temp/` (потеря при рестарте). При расширении — замена на Redis/Postgres без изменения хендлеров.
4. **Split-архитектура** — Mini App (статический UI) на HF Spaces, бот (polling) на Render.com. При росте — единая платформа (Render Pro / свой VPS).

## Project

Telegram bot + Telegram Mini App ("AI Prophet") — multimodal AI agent with chat, voice transcription, image analysis, music playlist generation, and web search.

**Split-архитектура:**
- **Hugging Face Spaces** — Mini App (статический HTML) + API health
- **Render.com** — polling бот (FastAPI + aiogram)

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
- Both local, Render, and HF modes use **polling** (webhook is blocked by HF without a proxy)

## Architecture

```
main.py
├── FastAPI (uvicorn) — health check, static files, webhook routes on HF
│   └── static/ — Telegram Mini App HTML (massage salon, prophet)
└── aiogram Dispatcher (polling)
    ├── handlers/vip.py        — VIP mode, admin commands, password auth
    ├── handlers/limits.py     — per-user download duration/size limits
    ├── handlers/massage.py    — 🖐 Массажный салон + AI-консультация (/massage, ШММ-анкета 16+ полей)
    └── handlers/messages.py   — all user-facing: text, photo, voice, playlists, settings

core/
├── ai_engine.py   — Gemini client (google-genai SDK) + HF router (requests) + transcription
├── tools.py       — web search (DDG), media search (YT/Jamendo/SC/Archive), download
├── agents/        — 🆕 Мульти-агентная система ИИ-специалистов
│   ├── agent_base.py      — Базовый класс агента (HF + Gemini fallback)
│   ├── registry.py        — Реестр агентов (3 группы, 5 специалистов)
│   ├── orchestrator.py    — Оркестратор: запуск специалистов → синтез
│   └── music_db.py        — Кураторская база проверенной музыки для массажа
├── questionnaire.py — Модель анкеты (ШММ, JSON-конфиг, 16 обязательных + опциональные)
├── network.py       — DNS patch (no-op in current code)
└── mcp_client.py    — MCP client (unused/stub)
```

### Dynamic Specialist System (core/agents/agent_factory.py)

Пользователь может динамически создавать собственных ИИ-специалистов под любую задачу.

**Как работает:**
1. Пользователь пишет роль (например, "эксперт по стоун-терапии")
2. `SpecialistFactory.create()` генерирует имя + системный промпт через Gemini (HF fallback)
3. Специалист сохраняется в `temp/specialists.json`
4. Пользователь может общаться со специалистом — его сообщения перехватываются в `handle_text` (messages.py) через `specialist_chat` флаг в `user_settings.json`
5. Специалиста можно удалить через `/dismiss`

**Команды:**
- `/specialist <роль>` — создать и начать диалог со специалистом
- `/specialists` — список созданных специалистов
- `/dismiss <имя>` — удалить специалиста
- `/exit_specialist` — выйти из диалога со специалистом

**Auto-detection:** Gemini получает в system prompt инструкцию использовать `create_specialist` function call, когда клиенту нужен профильный эксперт. Функция объявлена в `tools.py` как `FunctionDeclaration`, обрабатывается в цикле function calling `messages.py:1236`.

**Интеграция с массажем:** В `/massage` добавлена кнопка "Создать специалиста", которая открывает список активных специалистов (+ создание/удаление). Режим `massage_step == "create_specialist"` перехватывается через `InQuestionnaireFilter`.

**HF-first:** SpecialistFactory использует HF Router (Qwen) для общения, Gemini — только для генерации системного промпта и как fallback.

### Мульти-агентная система (core/agents/)

Запускается из `/massage` → "AI-консультация".

**Стратегия AI:** HF Router first (бесплатно, мультимодально) → Gemini fallback.
- Текст: `Qwen/Qwen2.5-7B-Instruct` (HF Router)
- Vision: `meta-llama/Llama-3.2-11B-Vision-Instruct` (HF Router)
- Видео: извлечение кадров через ffmpeg → анализ через Vision

**Группы агентов** (определены в `registry.py`):

| Группа | Агент | Модель | Вход |
|--------|-------|--------|------|
| **Диагносты** | Визуальный Диагност | vision | Фото спины/осанки |
| | Специалист по движениям | vision (из видео) | Видео походки/наклонов |
| **Аналитики** | Анкетолог | text | Текст анкеты (12 шагов) |
| **Эксперты** | Эксперт по техникам | text | Данные всех специалистов |
| | Финальный Эксперт | text | Все данные → заключение |

**Pipeline:** Анкета → Анкетолог → (Фото → Диагност) → (Видео → кадры → Движения) → Техники → Финальный эксперт

**Добавить/удалить/изменить агента:** редактировать `registry.py` → группы `AGENT_GROUPS`.

### Анкетирование (core/questionnaire.py + config/questionnaire_steps.json)

**Data-driven**: шаги анкеты загружаются из `config/questionnaire_steps.json` при старте. Каждый шаг имеет поля: `key`, `question`, `type`, `required`, `group`, `source`.

**Всё по ШММ (Школа Мастеров Массажа)** — 16 обязательных полей из карты клиента + опциональные.

**Типы шагов:**
- `text` / `number` — свободный ввод
- `choice` — один вариант из списка
- `multi_choice` — несколько чекбоксов
- `group` — группа подполей (имя + возраст + пол + телефон = один шаг с подвопросами)
- `consent` — чекбокс информированного согласия

**Обязательные (16):**
ФИО, возраст, пол, телефон, рост, вес, жалобы, локация, тип боли, длительность, иррадиация, хронические заболевания (расш. список), аллергии, лекарства, АД+пульс+температура, абсолютные противопоказания (16 пунктов), временные состояния (беременность/лихорадка/воспаление/операции), информированное согласие.

**Опциональные:** работа, график, физ.активность, шаги/день, сон, стресс, травмы/операции, порог боли, зоны щекотки, кожа, сосуды, вдовий горбик, диагноз врача.

**Как редактировать:** правишь `config/questionnaire_steps.json` — порядок, обязательность, текст вопросов — без изменения кода Python. Добавить поле = новый блок в JSON.

**Два способа заполнения:**
1. **В боте** — пошагово: сначала обязательные, потом кнопка "➕ Добавить детали" → опциональные
2. **В Mini App** — форма рендерится с `GET /api/questionnaire/steps_full`, отправка через `tg.sendData()`

### Музыка для массажа (core/agents/music_db.py)

Кураторская база **проверенных YouTube-ссылок** для 8 жанров массажной музыки:
Ambient, Классика, Природа, Jazz, Спа, Тайский, Акустика, Бины.

**Как работает:** ссылки не скачаны заранее — это внешние YouTube-треки, по которым бот:
1. Показывает ссылки (кликабельные — открываются в YouTube)
2. Запускает параллельный поиск через `search_media_content()` (Jamendo/SoundCloud/YouTube) для скачивания MP3-плейлиста

Гарантированно работающие ссылки + fallback-поиск.

- Router registration order in `main.py`: `vip` → `limits` → `massage` → `messages` (matters for command precedence)
- User state stored in `temp/user_settings.json` (in-memory dict persisted to file; **lost on restart**)
- User limits stored in `temp/user_limits.json`
- All UI text is in Russian

## AI Engines

**Primary**: Gemini via `google-genai` SDK with function calling (`web_search`, `search_media_content`)
- Model fallback chain: `gemini-3.5-flash` → `gemini-3.1-flash` → `gemini-3-flash-preview` → `gemini-2.5-flash` → `gemini-2.5-pro`
- Primary model is updated when new Gemini versions release (check [Google AI blog](https://blog.google/technology/ai/) and [AI Studio pricing](https://ai.google.dev/gemini-api/docs/pricing))

**Fallback**: Hugging Face Inference API via `router.huggingface.co` (OpenAI-compatible endpoints)
- Text: `Qwen/Qwen2.5-7B-Instruct`
- Vision: `meta-llama/Llama-3.2-11B-Vision-Instruct`
- Audio: `openai/whisper-large-v3-turbo`
- Reasoning: `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B` (stub, unused)

User can switch engine per-chat: auto (Gemini→HF), Gemini only, HF only.

## Design System

Mini App UI/UX правила, палитра, анимации, производительность: `DESIGN_SYSTEM.md`

## Key Conventions

- **FREE-FIRST**: all services must use free tiers by default (`DEVELOPMENT_PRINCIPLES.md`)
- `config.py` loads env via `python-dotenv`; never hardcode secrets
- `TEMP_DIR` ("temp/") is cleaned on bot start; per-user files use `task_{chat_id}_*` and `audio_{chat_id}_*` patterns
- Media markers in AI responses: `[MEDIA: query, type, count]` triggers automatic search/download
- Step markers in Gemini responses: `ШАГ: [text]` become inline keyboard buttons
- Telegram callback data limited to 64 bytes; Cyrillic is 2 bytes/char in UTF-8

## Model Version Updates

When a new Gemini model is released, update these files:
1. **`config.py`** — add new model to `FALLBACK_MODELS` (first position), update `SYSTEM_PROMPT`
2. **`handlers/messages.py`** — update status message text (search for "Подключение к Gemini")
3. **`handlers/vip.py`** — update VIP menu description text
4. **`AGENTS.md`** — update fallback chain in AI Engines section
5. **`HISTORY.md`** — add entry with release date and model details

Check for new models at:
- [Google AI Blog](https://blog.google/technology/ai/)
- [Gemini API Models page](https://ai.google.dev/gemini-api/docs/models)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing) — shows free tier limits

## CI/CD

`.github/workflows/sync_hf.yml` — on **any branch push**, force-pushes to HF Spaces `dizel0110/ai_prophet`. No PR gate. `main` branch push = production deploy.

Render.com подхватывает `main` ветку автоматически через Git-интеграцию (Manual Deploy → Deploy from Branch).

## Docker

`Dockerfile` based on `python:3.11-slim`, installs `ffmpeg` and `dnsutils`. CMD: `python main.py`.
`.dockerignore` excludes `venv/`, `temp/`, `*.md` (except README), `test_*.py`, `internal/`.

## System Dependencies

- **ffmpeg** required for audio conversion (OGG→WAV) and yt-dlp post-processing
- Without ffmpeg, audio falls back to raw OGG and yt-dlp skips post-processing

## HF Spaces Resource Constraints

HF Spaces **CPU Basic** (бесплатный):
- 1 vCPU, 8GB RAM, 50GB storage
- Python + deps занимают ~3-5GB → остаётся ~45GB для временных файлов
- **transformers + torch** (~2GB) отключены в `requirements.txt` — не влезают
- **Вся AI-логика** — внешние API (HF Router, Gemini), не локальные модели
- **Тяжёлые операции** (извлечение кадров из видео → 2 кадра на HF вместо 3)
- **temp/** чистится: при старте бота, при старте/отмене/завершении консультации
- yt-dlp скачивает MP3 во временную папку → сразу отправляет → удаляет
- Логи ротируются ежедневно в `logs/`

## Testing

**pytest** in `tests/` (gitignored, not deployed). Run before any push:

```bash
pip install pytest
python -m pytest tests/ -v
```

Test pattern: unit tests mock all network calls (`@patch`), test core logic only (parsing, caching, genre data). No tests that hit real APIs or Telegram.

### Push Policy
| Change Type | Action |
|-------------|--------|
| 🐛 Bug fix, text/copy change, config/dep update, refactoring | Work autonomously → **ask to push** |
| ✨ New feature, API change, architecture change, breaking change | Work autonomously → **ask to push** |
| 🚑 Hotfix (prod broken) | Fix + push immediately, then report |

**Workflow:**
1. Работаю безостановочно — код, тесты, итерации, без лишних вопросов
2. `pytest` проходит → `git add/commit` (но не push)
3. **Спрашиваю "Пушить?"** — ты решаешь, когда едет в прод
4. Если молчишь → жду твоего сигнала

**Исключение:** прод сломан — чиню и пушу сразу, потом докладываю.

### Оценка времени (Estimations)
Перед задачей >5 мин — пишу `≈N мин/ч`. После — `(факт: Nм)` если расхождение >20%. Итоги длинных задач (>1ч) — в HISTORY.md.

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
| `OWNER_USERNAME` | No | Default `dizel0110` |
| `GEM_BOT_URL` | No | External GEM-bot link (not committed to git) |
| `MINI_APP_URL` | No | Custom Mini App base URL (default: GitHub Pages or ngrok) |
| `PLATFORM` | No | `hf` / `render` / `local` (auto: local) |
| `TELEGRAM_API_URL` | No | Cloudflare Worker URL — обход блокировки Telegram на HF Spaces |

## Context Management

- **When context fills up (>70%)**: save key decisions, bug fixes, and architecture changes to `HISTORY.md` before continuing.
- **New conventions or gotchas discovered**: add them to this file (`AGENTS.md`) immediately.
- **Unfinished tasks**: note them at the bottom of `HISTORY.md` so the next session picks up where this one left off.
- This ensures continuity across sessions — treat `HISTORY.md` as the project's persistent memory.

## Cloudflare Worker (Telegram API Proxy)

`cloudflare-worker/index.js` — прокси для обхода блокировки Telegram API на HF Spaces.

**Деплой:** Cloudflare Dashboard → Workers & Pages → Create Worker → вставить код → Deploy
**Бесплатно:** 100k запросов/день, без карты
**На HF Spaces:** установить `TELEGRAM_API_URL` = URL воркера в Secrets

## Client-Side AI (future)

Возможность подгружать легковесные нейронки на устройство клиента (с согласия):

| Технология | Модели | Размер | Требования |
|-----------|--------|--------|-----------|
| **WebLLM (MLC)** | Llama/Qwen 7B (int4) | ~3-4GB | WebGPU (Chrome 113+, Edge) |
| **Transformers.js** | Whisper-tiny, distill-bert | ~150MB | Браузер с Web Workers |
| **llama.cpp (WASM)** | TinyLlama 1.1B | ~1GB | SharedArrayBuffer |

**Когда имеет смысл:**
- Клиент на десктопе с WebGPU → можно запустить 7B-модель локально
- Офлайн-режим (Whisper-tiny для транскрибации)
- Снятие нагрузки с сервера

**Пока не реализовано** — требует определения устройства клиента (+ User-Agent / navigator), загрузки ~ГБ весов, и UI для согласия.

## MCP (Model Context Protocol)

Playwright MCP сервер установлен для opencode. Конфигурация: `~/.config/opencode/opencode.jsonc`

Доступные инструменты агенту:
- `browser_navigate` / `browser_snapshot` / `browser_screenshot`
- `browser_click` / `browser_fill` / `browser_select`
- Поддержка headless-режима (браузер без GUI)

Детальный гайд: `MCP_GUIDE.md`

**Playwright >> webfetch** — webfetch только GET-запросы (статический HTML), Playwright — полноценный браузер с JS, кликами, формами, скриншотами.

## Key Gotchas for the Agent System

- **Agents use `generate_content()` NOT chat sessions** — каждый агент создаёт свой запрос, не использует `get_ai_chat()`. Это важно — агенты одноразовые, а не диалоговые.
- **Custom Filter `InQuestionnaireFilter`** — текст от пользователя во время анкетирования перехватывается кастомным фильтром, который проверяет `massage_step == "questionnaire"` в `user_settings.json`. Это не даёт catch-all handler в messages.py перехватить ввод. Для создания специалиста тоже используется этот фильтр (проверка `massage_step == "create_specialist"`).
- **Callback data (64 bytes)** — Telegram жёстко режет callback_data длиннее 64 байт (сервер, не клиент). Cyrillic — 2 байта/символ, так что длинные опции в `mc_q_toggle:{текст}` легко вылетают за лимит. **Решение:** передавать индекс опции вместо полного текста: `mc_q_toggle:{i}`. Код сам достаёт текст из `step["options"][i]`.
- **Music DB — fallback** — `music_db.py` содержит проверенные ссылки, но всегда запускает и `search_media_content()` как fallback.
- **Orchestrator synchronous calls** — AI вызовы синхронные (`requests.post`, `genai.Client.models.generate_content`), обёрнуты в `asyncio.to_thread()`.
- **Temp files (massage photos/videos)** — сохраняются как `massage_photo_{chat_id}_{file_id}.ext` и `massage_video_{chat_id}_{file_id}.ext`. Удаляются после анализа.
- **`F.web_app_data` handler** — массажный роутер перехватывает WebApp данные (`tg.sendData`) до того, как их получит messages.py.
- **HF first strategy** — агенты сначала пробуют HF Router (бесплатно, `router.huggingface.co`), только при ошибке падают на Gemini. Это экономит квоту Gemini.
- **Event delegation (sp-items)** — Mini App uses `data-name`/`data-role`/`data-exists` attributes on `.sp-item` divs, NOT inline `onclick`. Container-level click listeners in `renderChatList()` and on `#specialist-list` handle clicks via `e.target.closest('.sp-item')`. This avoids JS escaping issues and template-literal breakage.
- **Chat opens after create** — both `createSpecialist()` (form) and `createAndOpen()` (preset/generated) call `openSpecialistChat(d.name)` after successful creation.
- **No duplicate listeners** — `_chatListHandler` is a module-level variable; old handler is removed before adding new one in `renderChatList()`.
- **Final Expert always runs** — `orchestrator.py` runs Final Expert unconditionally (lines 63-65). `_build_context` with `include_all=True` passes all results including `technique_expert`. The `[:300]` truncation for questionnaire text passed to vision/video agents was removed — Final Expert now gets full data.
- **`orchestrator.py` synchronous AI calls** — wrapped in `asyncio.to_thread()` for compatibility with aiogram handlers.

## Master Consultant Actions (ACTION System)

Мастер-консультант (MC) — единственный агент, который может выполнять действия в Mini App через `[ACTION: ...]` маркеры в ответе AI.

**Доступные действия:**
- `[ACTION: open_specialist, "Имя"]` — закрыть чат MC, открыть чат с другим специалистом
- `[ACTION: play_music, "жанр"]` — перейти на вкладку Музыка, загрузить треки жанра
- `[ACTION: start_consultation]` — открыть форму анкетирования (AI-диагностика)
- `[ACTION: go_booking]` — перейти на страницу записи

**Как работает:**
1. MC system prompt (agent_factory.py) содержит инструкцию с примерами маркеров
2. AI генерирует ответ с `[ACTION: ...]` в конце
3. Frontend (`sendSpecialistMessage()` в index.html) парсит маркеры через `parseActions()`
4. Маркеры удаляются из отображаемого текста (`stripMarkdown()`)
5. Действия выполняются через 600ms после отображения ответа

**Почему только MC:**
- Остальные агенты — узкие профи (Диагност, Анкетолог и т.д.). Их задача — делать свою работу, не перенаправлять.
- MC — единая точка входа и навигации. Граф поведения клиента: MC → нужный агент → (опционально 🔄 к MC).
- Зацикленные переходы между агентами запутывают пользователя.

**Возврат к MC:**
- Кнопка 🔄 в шапке чата (`closeSpecialistChat(); navigate('chat'); loadChatList()`) — возвращает к списку специалистов, откуда можно снова открыть MC.
- История диалога с MC сохраняется в `spMessages[uid]` и восстанавливается при повторном открытии.

## 🚫 HF Spaces Binary Rejection Rule

HF Spaces rejects **any git push containing binary files** (PNG, ZIP, pickles, etc.) with error:
```
Your push was rejected because it contains binary files.
Please use https://huggingface.co/docs/hub/xet to store binary files.
```

**Решение:** любые бинарники, необходимые в рантайме, кодировать в base64 → хранить как текстовый JSON в git → декодировать на старте сервера (`main.py:decode_certs()`).

**Правило:** ни один бинарный файл не должен попадать в git-историю HF Spaces. Если файл нужен на сервере — base64 в JSON + декод при старте.

## Certificate Management (Сертификаты/Дипломы)

PNG-файлы сертификатов хранятся в `static/massage/certificates/`, но **не через git** — HF Spaces блокирует бинарники.

**Механизм:** base64-кодирование → `certs.json` (текстовый файл, проходит через git) → декодирование в PNG при старте сервера (`main.py:decode_certs()`).

**Добавить новый:**
1. Положить PNG рядом — я скопирую в `static/massage/certificates/`
2. Добавить `<div class="cert-item">` в HTML в блок `.cert-grid`
3. Вписать короткую подпись в `cert-label`
4. **Запустить encode:** `python -c "import base64,json; d=open(r'static/massage/certificates/новый.png','rb').read(); c=json.load(open(r'static/massage/certificates/certs.json')); c['новый.png']=base64.b64encode(d).decode(); json.dump(c, open(r'static/massage/certificates/certs.json','w'),ensure_ascii=False,indent=2)"`
5. Коммит + пуш → прод

**Удалить устаревший:**
1. Убрать `<div class="cert-item">` из HTML
2. Удалить запись из `certs.json` (`del c['старый.png']`)
3. `git rm` не нужен — PNG в `.gitignore`
4. Коммит + пуш

**Заменить (новое оформление):**
1. Удалить старый PNG и HTML-блок + запись в `certs.json`
2. Добавить новый PNG и HTML-блок + запись в `certs.json`
3. Коммит + пуш

## Gotchas & Known Issues

- **HF Spaces blocks outgoing Telegram API** — polling requires `PROXY_URL` secret on HF. Without it, bot crashes with `ClientConnectorError`.
- **google-genai SDK 2.x** requires `genai_types.FunctionDeclaration` for tools, NOT raw dicts with `parameters`. Use `inputSchema` format via `genai_types.Schema`.
- **Duplicate text handlers** — `@router.message()` (catch-all) and `@router.message(F.text)` both fire on text. Only use `@router.message()` in `handle_text`; the `F.text` handler was removed.
- **HF fallback must `return`** — after `get_hf_response()` succeeds, code must return. Otherwise it falls through to Gemini loop (429) → back to HF → duplicate response.
- **Logs** go to `logs/bot_YYYYMMDD.log` — excluded from git and Docker.
- **Two python processes** on local run: FastAPI (uvicorn) + aiogram polling. This is normal.
- **`app.py` is stale** — references `start_bot` which doesn't exist. Only `main.py` works.
- **Gemini quota exhaustion** — free tier hits 429 quickly. HF fallback handles it, but session creation is retried across all 5 models before giving up.
- **`SpecialistFactory.chat()` и `create()` — синхронные, блокируют event loop** — в async-хендлерах всегда оборачивать через `await asyncio.to_thread(...)`. Без этого «Печатает...» висит вечно. Добавлять `asyncio.wait_for(..., timeout=120)` для защиты от зависаний Gemini.
- **Русская запятая в number-полях** — пользователи пишут «36,6» вместо «36.6». В Python `float("36,6")` падает. В `massage.py:on_mc_text_input` делать `text.replace(",", ".")` перед парсингом числа.
- **Music recommendation format is free-text** — Final Expert outputs in natural language (not structured JSON). `_parse_music_recommendation()` uses regex to extract genre, duration, and track count from any text format. Must cover both English (`ambient`) and Russian (`эмбиент`) genre names.

## Feature Spec #6: Музыкальный плеер / Музыкальная система

Музыка — **сквозная функция** AI Prophet, проходящая через все фазы взаимодействия с клиентом.

### Фазы музыки в проекте

| Фаза | Где сейчас | Статус |
|------|-----------|--------|
| **1. Поиск** — найти треки по запросу, жанру, типу массажа | `core/tools.py` — `search_media_content()` (4 источника); `core/music_player.py` — IA + AI-поиск через HF Router | ✅ Built |
| **2. Скачивание** — загрузить MP3 через yt-dlp с FFmpeg | `core/tools.py` — `download_audio()` + `send_playlist()` | ✅ Built |
| **3. Каталог** — кураторская база проверенных ссылок | `core/agents/music_db.py` — 8 жанров × 3 ссылки; `music_player.py` — 8 жанров из IA | ✅ Built |
| **4. Рекомендация** — AI подбирает музыку под тип массажа/клиента | 🤖 кнопка в плеере: естественный язык → HF Router → IA поиск | ✅ Built |
| **5. Воспроизведение** — встроенный плеер в Mini App | HTML `<audio>` с play/pause/next/prev/shuffle/repeat/progress | ✅ Built |
| **6. Встроенный плеер** — вкладка Музыка 🎵 в Mini App | Жанры → треки → плеер. Поиск 🔍, AI 🤖, загрузка своей музыки 📤, экспорт/импорт 📤📥 | ✅ Built |
| **7. Интеграция с консультацией** — музыку на выходе из `/massage` | Final Expert → `_parse_music_recommendation` → кнопка «🎵 Собрать плейлист» в модале результатов (Mini App) / в «Что дальше?» (бот) | ✅ Built |

### Что нужно для #6 (Music Player)

**Суть:** дать пользователю возможность **слушать музыку не выходя из Mini App**, а не переходить в бота или YouTube.

**Компоненты:**

#### Фаза A: Вкладка «Музыка» в Mini App
- Новая 8-я вкладка 🎵 в таб-баре `index.html`
- Сетка 8 жанров (иконки + название)
- При выборе жанра:
  - Показывает список треков (из `music_db.py` + результаты поиска)
  - Каждый трек: название + кнопка **Play/Пауза**
  - Встроенный аудиоплеер (HTML `<audio>`)
  - Плейлист (очередь, следующий/предыдущий)
- API endpoint: `GET /api/music/{chat_id}/{genre}` → возвращает треки

#### Фаза B: `/music` команда в Telegram
- Пока не сделана (в GUIDE.md упоминается, но хендлера нет)
- Должна показывать те же 8 жанров + поиск
- Интегрировать в `/massage` flow (после заключения)

#### Фаза C: Рекомендательная система
- После AI-консультации (/massage): Final Expert рекомендует жанр/конкретную музыку
- Автоматический поиск и плейлист под тип массажа
- Связь: `music_db.py` + результат `Final Expert` → `search_media_content()` → очередь треков

#### Фаза D: Плеер в Telegram (альтернатива)
- Inline-клавиатура с кнопками: ⏮ ⏯ ⏭ 🔊 (управление через callback)
- Очередь: много треков подряд без ручного запуска каждого
- Прогресс-бар (длительность, позиция)

### Как это коррелирует с проектом

```
massage.py (консультация) ──→ music_db.py (жанры/ссылки)
       │                            │
       ▼                            ▼
  Final Expert ──→ search_media_content() ──→ download_audio()
       │                                            │
       ▼                                            ▼
  [🎵 Музыка для сеанса]                send_playlist() → бот отправляет MP3
       │
       ▼
  Mini App: вкладка Музыка 🎵
       │
       ▼
  index.html + API → HTML Audio Player
```

**Принцип «кратчайшего пути»:**
- Сейчас: нажать «🎵 Музыка» → открыть Telegram → `/playlist жанр 5` → ждать скачивания → открыть файл
- Цель: нажать жанр → треки загрузились в плеер → нажать Play → слушать

### Зависимости
- `index.html` + новый JS-код для плеера (не внешние библиотеки — HF Spaces ограничен)
- `main.py`: новый endpoint `/api/music/{chat_id}/{genre}`
- `messages.py`: новый хендлер `/music`
- `handlers/massage.py`: доработка пост-консультации (авто-музыка)
- `music_db.py`: расширение (больше треков на жанр)
- `agent_base.py`: доработка Final Expert prompt для рекомендации музыки

### Приоритет реализации
1. **A** — вкладка + плеер в Mini App (самый заметный эффект)
2. **B** — `/music` команда (быстрая, простой хендлер)
3. **C** — рекомендации (глубокая интеграция, но высокий impact)
4. **D** — плеер в Telegram (низкий приоритет, только если пользователи просят)

## Админ-панель (⚙️ Mini App)

### Как работает
1. **ADMIN_IDS** в `.env` — `ADMIN_IDS=123456789,987654321` (через запятую, без пробелов)
2. При старте сервера загружаются из env + из `data/admin_ids_extras.json` (добавляется через `/give_access`)
3. Когда админ открывает Mini App, сервер проверяет `chat_id` по `TG.initDataUnsafe.user.id` через `GET /api/admin/identify?chat_id=...`
4. Если админ — появляется шестерёнка ⚙️ в правом верхнем углу
5. Тап → тоггл между **👤 Клиент** и **⚙️ Админ** режимами
6. В админ-режиме появляется вкладка «Админ» в таб-баре
7. **Состояние сохраняется** на сервере (`admin_mode_persist.json`) — переоткрытие Mini App восстанавливает режим

### Как узнать chat_id
- Напиши `/id` боту — бот ответит твоим chat_id
- Или используй [@userinfobot](https://t.me/userinfobot) в Telegram
- Или зайди в бота → открой Mini App → в консоли: `window.Telegram.WebApp.initDataUnsafe.user.id`

### Как дать доступ другому (партнёру, коллеге)
1. Попроси человека написать боту любое сообщение
2. Напиши в боте: `/give_access @его_username`
3. Когда человек в следующий раз напишет боту — его chat_id добавится в `ADMIN_IDS` (runtime, переживает рестарт)
4. Можно также вручную добавить ID в `.env` (`ADMIN_IDS=...`) — для жены/партнёра

### Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/admin/identify?chat_id=X` | GET | Проверка админа + текущий режим |
| `/api/admin/mode` | POST | Переключить режим client/admin |
| `/api/admin/clients?chat_id=X` | GET | Список клиентов (только с анкетой) |
| `/api/admin/client/{chat_id}?admin_chat=X` | GET | Полные данные клиента |

### Приоритет
1. 📋 Список клиентов + просмотр анкеты и результатов ✅
2. 📊 Дашборд (статистика) — следующий шаг
3. 🧑‍⚕️ Список ИИ-специалистов — после дашборда
