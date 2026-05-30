# 📜 Летопись AI Prophet (Development History)

## 🌌 Начало (Январь - Февраль 2026)
Проект зародился как идея создания интеллектуального проводника в Telegram. Первые шаги включали настройку базового бота на `aiogram` и интеграцию с Gemini API.

### 🔹 Веха 1: Пробуждение Разума
- Реализована база: `main.py`, `core/ai_engine.py`.
- Настроена система `Fallback`: бот научился переключаться между разными версиями Gemini при ошибках лимитов.
- Внедрен «Пророческий стиль» общения.

### 🔹 Веха 2: Обретение Чувств (Зрение и Слух)
- **Vision**: Бот научился анализировать фото. Мы прошли через ошибки `429` и `Disconnected`, внедрив локальное сохранение в `temp/` и повторные попытки через разные модели.
- **Audio**: Интегрирована модель `Whisper` через Hugging Face. Пророк начал слышать и понимать голосовые сообщения.
- **Resilience**: Реализован «мост» к Hugging Face. Если Google молчит, отвечают `Qwen` или `Llama`.
- **Infrastructure**: Настроен продвинутый CI/CD. Любая ветка синхронизируется с HF Spaces.

### 🔹 Веха 3: Стабилизация и Унификация (Февраль 2026) 🧿
- **Победа над Конфликтами**: Решена проблема `TelegramConflictError` при деплое. Внедрена стратегия очистки эфира (`drop_pending_updates=True`).
- **Gemini 3 Flash**: Подтверждена стабильная работа `gemini-3-flash-preview`.
- **Интерфейс Настроек**: В меню добавлена кнопка «⚙️ Настройки» для выбора Оракула.
- **Vision HF**: Теперь зрение работает и в режиме «Только Hugging Face», минуя Gemini.
- **Voice Fix**: Обновлен аудио-движок для стабильной транскрипции (Whisper V3 Turbo).

## 2026-02-15: Media Search 2.0 & Audio Download
- **Universal Media Search**: Заменили `create_music_playlist` на `search_media_content`.
    - Поддержка `[MEDIA: query, type, count]`.
    - Умный поиск через DuckDuckGo Videos (работает даже если YouTube блокирует).
    - Разделение логики поиска для `audio` (ищем песни/lyrics) и `video` (клипы).
- **Audio Download Feature**:
    - Добавлена кнопка `[⬇️ Скачать MP3]` для каждого найденного трека.
    - Реализована функция `download_audio` через `yt-dlp` (качает m4a/mp3).
    - Автоматическое извлечение **реального названия трека** и отправка файла с корректными метаданными.
    - Многокнопочный интерфейс: `[⬇️ 1] [⬇️ 2] [⬇️ 3]...`

## 2026-02-15: Fixes & Cleanup
- **Начало MCP**: Инициализация архитектуры Model Context Protocol для связи с внешним миром.
- **Музыкальный горизонт**: Проектирование системы управления плейлистами и интеграция с плеерами (Spotify/Local).
- **Синхронизация**: Настройка «магического» деплоя через одну команду для всех веток.

## 2026-05-20: Gemini 3.5 Flash Update
- **Google I/O 2026**: Вышел Gemini 3.5 Flash — лучшая модель для агентов и кодинга.
  - 4x быстрее других frontier-моделей, 1M контекст, 64k output tokens.
  - Free tier: 15 RPM / 1500 RPD, токены бесплатно.
  - Outperforms 3.1 Pro на Terminal-Bench 2.1 (76.2%) и GDPval-AA.
- **FALLBACK_MODELS**: `gemini-3.5-flash` добавлен как ПЕРВЫЙ в цепочке.
- **SYSTEM_PROMPT**: Обновлён — «Твой разум опирается на мощь Gemini 3.5 Flash».
- **UI**: Статус-сообщения и VIP-меню обновлены под новую модель.
- Цепочка теперь: `gemini-3.5-flash` → `gemini-3.1-flash` → `gemini-3-flash-preview` → `gemini-2.5-flash` → `gemini-2.5-pro`

## 2026-05-17: Переход на OpenCode & AGENTS.md
- **OpenCode**: Перешёл с Cursor/других AI-редакторов на **opencode** — CLI-инструмент для разработки с ИИ.
- **Причина**: opencode работает прямо в терминале, не привязан к IDE, даёт полный контроль над сессиями. Можно запускать несколько терминалов параллельно.
- **AGENTS.md**: Создал файл инструкций для AI-агентов opencode, чтобы будущие сессии сразу понимали архитектуру проекта, команды запуска, конвенции и типичные ошибки. Без этого каждый новый агент тратил время на разбирательство с нуля.

## 2026-05-17: Фиксы локального запуска
- **Задвоение ответов**: Удалён дублирующий хендлер `@router.message(F.text)` (`handle_text_message`), который конфликтовал с основным `@router.message()` (`handle_text`). Одно сообщение обрабатывалось дважды.
- **HF fallback без `return`**: После успешного ответа HF код проваливался в Gemini-цикл (429) → снова HF → дублирующий ответ. Добавлен `return` после HF-ответа.
- **google-genai SDK 2.x**: Обновлена спецификация инструментов — вместо сырых dict теперь `genai_types.FunctionDeclaration` с `genai_types.Schema`.
- **Логи**: Создана папка `logs/`, логи пишутся по дням (`bot_YYYYMMDD.log`). Добавлена в `.gitignore` и `.dockerignore`.
- **HF Spaces proxy**: Добавлена поддержка прокси для polling-бота на HF Spaces (требует `PROXY_URL`).

## 2026-05-25: Playwright MCP Setup
- **Playwright MCP установлен** для opencode (глобальный `~/.config/opencode/opencode.jsonc`).
- **Причина**: webfetch не умеет JS, клики, скриншоты, формы. Playwright — полноценный браузер.
- Установлен пакет `@playwright/mcp` в проект (`npm install @playwright/mcp`).
- Установлен Chromium для headless-режима (`npx playwright install chromium`).
- **Документация**: создан `MCP_GUIDE.md` с подробным описанием установки, настройки и сравнением с webfetch.
- **ngrok**: установлен глобально (`npm install -g ngrok`) для локального HTTPS-тестирования Mini App.
- **План для бота**: интеграция Playwright как команды `/browse` и `/screenshot` (TODO).

## 2026-05-25: Massage Mini App &amp; Static Serving
- **Массажный Mini App**: Создан полноценный Telegram Mini App для массажного салона (`static/massage/index.html`).
  - Каталог услуг с ценами, описание, контакты, кнопка записи.
  - Telegram WebApp API (expand, haptic, theme).
  - Автоопределение URL: на HF Spaces раздаётся FastAPI, локально — GitHub Pages.
- **FastAPI Static Files**: FastAPI теперь раздаёт статику через `/static/` — основа для всех будущих Mini App.
- **Handler массажа**: Добавлен `handlers/massage.py` с командой `/massage` и отдельной клавиатурой.
- **Config**: Добавлены `GEM_BOT_URL`, `MINI_APP_URL`, `get_base_url()`.
- **Router order**: `vip` → `limits` → `massage` → `messages`.

---
### 🛠 PHASE 4: Autonomous Agent (FUTURE)
- [ ] **🔴 Playwright MCP (приоритет)** — для меня (opencode) и для бота:
  - Для меня: открывать сайты, скриншоты, клики, формы.
  - Для бота: поиск контента, проверка ссылок, скрейпинг Mini App.
- [ ] **🔴 Auto-deploy Cloudflare Worker** — Git-интеграция воркера с репозиторием (CI/CD).
- [ ] Интеграция MCP для работы с файлами, БД.
- [ ] Автоматическое исправление багов через самоанализ кода.
- [ ] Расширение Mini App до полноценной панели управления состоянием ИИ.

## 2026-05-27: Cloudflare Worker Proxy — Telegram API на HF Spaces
- **Проблема**: HF Spaces блокирует исходящие к `api.telegram.org`. Render.com требует банковскую карту.
- **Решение**: Cloudflare Workers (бесплатно, без карты, 100k req/день) — прокси для Telegram API.
- **Создан**: `cloudflare-worker/index.js` + `wrangler.toml` — простой forward proxy до `api.telegram.org`.
- **main.py**: Поддержка `TELEGRAM_API_URL` через `TelegramAPIServer.from_base()` — aiogram ходит напрямую к Cloudflare Worker, минуя api.telegram.org.
- **main.py**: `Dispatcher` вынесен на уровень модуля (один раз на lifecycle) — исправлен crash recovery ("Router already attached").
- **webhook_only.py**: Рефакторинг — `dp` и `include_router` внутри `setup_webhook_routes()`, не на уровне модуля.
- **Фикс порядка**: dp создаётся ДО импорта webhook_only — роутеры больше не воруются.
- **Вывод**: HF Spaces (Mini App) + Cloudflare Worker (прокси) — два бесплатных сервиса, бот работает 24/7.
---

## 2026-05-27: Dynamic Specialist Chat — Mini App Chat UI, Event Delegation, Fixes
- **FastAPI endpoints**: `/api/specialist/chat`, `/list`, `/create`, `/delete`
- **Mini App Chat tab**: 5 presets + created specialists, search filter, create modal (name+role), magic buttons (✨🎲), chat modal with switch (🔄)
- **SpecialistFactory.chat()**: Gemini first (better persona), HF fallback
- **Bug fixes**: `user_settings.setdefault` KeyError, specialist logging, `agent_factory.py:99` f-string SyntaxError, duplicate click listeners (module-level `_chatListHandler`), `createSpecialist()` now opens chat after creation, Final Expert `[:300]` truncation removed
- **Event delegation**: replaced inline `onclick` with `data-*` attributes + delegated click listeners

## 2026-05-30: Critical Bug Fixes & Mini App Analyze Flow
- **🐛 Bot buttons not responding**: `@router.message()` decorator was on wrong function (`_extract_questions` instead of `handle_text`). Fixed in `messages.py:885-893`.
- **🐛 Prophet Mini App ignored by massage router**: `F.web_app_data` handler in `massage.py` caught all WebApp data. Added `_handle_prophet_action()` to route `daily_prediction`/`vision_info` correctly.
- **🐛 Questionnaire hangs at Q17**: Two root causes fixed:
  - Russian comma in `body_temperature` (`36,6` → `36.6`) — `text.replace(",", ".")` in `massage.py:523-531`
  - Callback data >64B for long multi_choice options — switched from `mc_q_toggle:{text}` to `mc_q_toggle:{index}` (always ≤14B). Full option texts restored in `questionnaire_steps.json`.
- **🐛 AI agents eternal "Печатает..."**: `SpecialistFactory.chat()`/`create()` are synchronous, blocked the event loop. Wrapped in `asyncio.to_thread()` + `asyncio.wait_for(timeout=120)` across `messages.py` and `main.py`.
- **📸 Photo/video upload in Mini App**: New `POST /api/massage/upload` (format/size validation, save to temp/, update `massage_photos`/`massage_videos`). Upload buttons on AI page with status indicators and counters.

## 2026-05-30: End-to-End Photo→AI Agents in Mini App
- **`POST /api/massage/analyze`**: Runs orchestrator (5 AI agents), saves results to `user_settings`, returns formatted JSON
- **`GET /api/massage/results/{chat_id}`**: Re-view results from previous analysis
- **Mini App**: "🧑‍⚕️ Запустить анализ" button on AI page → loading indicator → results modal with markdown→HTML rendering
- **Auto-load**: `loadMassageResults()` runs on AI page navigation — shows "📋 Посмотреть результаты" if analysis exists
- **`renderMarkdown(t)`**: Converts Telegram Markdown to HTML for safe display in Mini App (`*bold*`, `_italic_`, links, code blocks)

## 2026-05-30: Phone Validation with Country Flags (Mini App only)
- **15 countries** with flags in a compact button row: 🇷🇺🇪🇬🇺🇸🇬🇧🇩🇪🇫🇷🇮🇹🇪🇸🇹🇷🇦🇪🇸🇦🇺🇦🇧🇾🇰🇿🇬🇪
- Click a flag → country code auto-selected (+7, +20, etc.)
- Preview line below input: `🇷🇺 +7 9xx-xxx-xx-xx` (updates on input)
- Supports home/landline phones — no strict mask, only country code hint
- On revisit: country code restored from saved answer (`+77` vs `+7` collision fixed via `startsWith(code + ' ')`)
- Telegram bot unchanged (no fancy UI possible there)

## 2026-05-30: Informed Consent (Step 20) — Interactive Link
- **Mini App**: "📄 Ознакомиться с полным текстом" button → full-screen modal with 8-point consent (contraindications, data processing, voluntary agreement) → "← Вернуться к анкете"
- **Telegram bot**: "📄 Ознакомиться" inline button → sends full consent text via Markdown message
- Consent text covers: 16 absolute contraindications, 7 temporary contraindications, data processing, voluntary nature, post-surgery states

## 2026-05-30: Semantic Matching for Questionnaire Answers
- **`YES_WORDS`/`NO_WORDS`/`UNCLEAR_WORDS`** sets: `ага`, `угу`, `неа`, `конечно`, `разумеется`, `неет` etc.
- **`semantic_normalize(text)`**: Returns `(canonical, is_binary, original)` — maps casual to canonical without altering stored data
- **Telegram bot**: On informal answer → confirms: *«Понял. Твой ответ → **да/нет**»*
- **Mini App**: Same normalization with `tg.showAlert()` confirmation
- **Principle**: Original text preserved (legal audit trail), user gets understanding confirmation

## 2026-05-30: Consultation Export to JSON
- **`GET /api/massage/export/{chat_id}`**: Returns JSON file download: questionnaire + photos/videos + analysis results + specialists
- **Mini App results modal**: "📤 Экспорт JSON" button → downloads file via Blob
- **Telegram bot**: "📤 Экспорт JSON" button in post-analysis message → sends JSON file
- **Export format**: `{ exported_at, chat_id, questionnaire, photos, videos, analysis_results, specialists }`

## 2026-05-30: Clear Post-Questionnaire Flow (no more "Открой чат с ботом")
- **Before**: questionnaire → `tg.sendData()` → "✅ Открой чат с ботом" — user forced to leave Mini App
- **After**: questionnaire → API save (`/api/questionnaire/submit`) + `tg.sendData()` (bot notification) → gold card "✅ Анкета заполнена! Что дальше?" with 4 numbered steps:
  1. Upload back/ posture photos
  2. Upload gait video
  3. Start AI analysis
  4. Talk to specialists
- **"📤 Перейти к загрузке"** button → smooth scroll to upload section
- **Persistence**: On re-entry, `checkQuestionnaireStatus()` via export endpoint detects existing data and shows the card

## 2026-05-30: Music Recommendation from Final Expert (Massage → Music Integration)
- **🔥 UX principle**: Show recommendation + one-tap "🎵 Собрать плейлист" button (not auto-apply, not buried in menus)
- **Final Expert prompt** (`agent_factory.py`): Added пункт 7) МУЗЫКА — genre (ambient/classic/nature/jazz/spa/thai/acoustic/binaural) + track count based on session duration (4-5 min/track)
- **Orchestrator hint** (`orchestrator.py:97`): Reminded to include duration + music in final output
- **`_parse_music_recommendation(final_text)`** (`massage.py`): Extracts `{session_duration, genre, track_count}` via regex from any text format — supports both English and Russian genre aliases
- **`get_tracks_by_duration(genre, target_minutes)`** (`music_player.py`): Filters track list to fit within target duration (first N tracks that sum to ≤ target)
- **`GET /api/music/recommendation/{chat_id}`** (`main.py`): Returns saved music recommendation from `user_settings`
- **`/api/massage/analyze`** (`main.py`): Now also returns `music_recommendation` in response body
- **Mini App results modal** (`index.html`): New `#music-rec-bar` with genre/duration/track count + "🎵 Собрать плейлист" button → closes modal → opens Music tab → loads recommended genre tracks
- **Mini App** `loadMassageResults()`: Parallel fetch of recommendation to show bar on "Посмотреть результаты" re-entry
- **Telegram bot**: `on_mc_analyze` saves `massage_music_recommendation` to `user_settings` and shows recommendation in "Что дальше?" card
- **Tests**: 12 new tests (4 × `get_tracks_by_duration`, 8 × `_parse_music_recommendation` with Russian/English/reduced coverage)
- **Total tests**: 69 ✅

## 2026-05-30: Questionnaire Resume After App Close (🔥 Простота)
- **Problem**: User closes Mini App mid-questionnaire → all answers lost (`consultFormAnswers` in-memory)
- **Solution**: Auto-save partial progress to server on every step change
- **New endpoints** (`main.py`):
  - `POST /api/questionnaire/save_progress` — saves `{answers, step_index, showing_optional}` to `user_settings["massage_questionnaire_progress"]`
  - `GET /api/questionnaire/progress/{chat_id}` — returns saved progress (or `{completed: true}` if already submitted)
  - `POST /api/questionnaire/clear_progress` — clears after successful submit
- **Mini App** (`index.html`):
  - `saveConsultProgress()` — debounced (500ms) auto-save on every: step advance, back, choice select, multi-choice toggle, text input leave
  - `checkQuestionnaireProgress()` — called on AI page enter → shows `btn-resume-consult` («📋 Продолжить анкету») with gold border
  - `resumeConsultForm(data)` — restores `consultFormAnswers`, `consultStepIndex`, `consultShowingOptional` → opens modal at saved position
  - Cleared on submit via `POST /api/questionnaire/clear_progress`
- **/api/questionnaire/submit** — also clears progress (`_set_user_data(..., "massage_questionnaire_progress", None)`)
