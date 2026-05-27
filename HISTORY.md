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

## 2026-05-27: Dynamic Specialist Chat (Phase 2) — Mini App Chat UI + Fixes
- **FastAPI endpoints**: Added `/api/specialist/chat`, `/list`, `/create` (accepts optional `name`), `/delete`.
- **Mini App Chat tab**: Dedicated chat page (`#chat`) with:
  - 5 preset specialist profiles + created specialists combined in one list
  - Search filter (matched by name or role)
  - Magic buttons: ✨ generate from name (auto-create + open chat), 🎲 random specialist
  - Create modal with separate name + role fields
  - Chat modal with message history, typing indicator, Enter-to-send
  - **Switch specialist** button (🔄) in chat header — closes chat, returns to list
- **SpecialistFactory.chat()**: Swapped to **Gemini first** — Gemini follows system prompt much better than Qwen for persona-based responses. HF fallback still works.
- **Bug fixes**:
  - `user_settings.setdefault(str(chat_id), {})` — prevents `KeyError` for new users
  - Specialist chat logging + `try/except` in both `handle_text` and voice handler
  - Presets always render synchronously; `loadChatList()` populates in two phases
  - All DOM access null-safe via helper functions
  - JSON response parsing fallback in API calls
  - **F-string SyntaxError** in `agent_factory.py:99` — replaced f-string with plain string concat
- **Event delegation** — replaced fragile inline `onclick` with `data-*` attributes and delegated click listeners on container elements (`.sp-item`). Fixes escaping issues in template literals.
- **Final Expert fix** — removed `questionnaire_text[:300]` truncation for vision/video agents in `orchestrator.py:45,53`. Final Expert now receives full questionnaire data.
---
