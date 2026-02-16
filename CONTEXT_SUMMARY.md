# 🧠 AI Prophet — Context Summary для Нового Чата

**Дата:** 2026-02-17
**Ветка:** `dev-phase3`
**Статус:** ✅ Работает на HF Spaces
**Последний коммит:** ce05f30

---

## 📦 Краткая Сводка Проекта

**AI Prophet** — Telegram бот с мультимодальным ИИ:
- 🎙 Голосовые сообщения (транскрибация + ответ)
- 🖼 Анализ фото (Gemini Vision + HF fallback)
- 🎵 Поиск и скачивание музыки (YouTube, 4 источника)
- ⚙️ Настройки движка (Gemini/HF/Auto)
- 🎛 Лимиты аудио (длительность/размер файла)

---

## 🔧 Ключевые Изменения (Сессия Февраль 2026)

### 1. Транскрибация Аудио
**Проблема:** HF не транскрибировал голосовые.
**Решение:**
- `transcribe_with_gemini()` — таймаут через threading, перебор MIME types
- `get_hf_response(task="audio")` — Whisper API
- Симметричный fallback: hf ↔ gemini

**Файлы:**
- `core/ai_engine.py`
- `handlers/messages.py`

---

### 2. Интерактивные Лимиты
**Функционал:**
- Кнопка "🎛 Лимиты" в главном меню
- Прогресс-бары (длительность/размер)
- Пресеты: ⚡ Быстро / ⚖️ Баланс / 🐢 Максимум
- Кастомный ввод (FSM)
- Влияние на поиск: больше лимит → меньше результатов

**Файлы:**
- `handlers/limits.py` (новый)
- `core/tools.py` — `search_media_content(chat_id)`
- `handlers/messages.py` — интеграция

---

### 3. Скачивание Музыки (4 Источника)
**Проблема:** YouTube блокирует серверные IP (HF Spaces).

**Решение (каскад):**
1. **ytmusicapi** — YouTube Music API (стабильнее на серверах)
2. **Cobalt API** — публичный API без авторизации
3. **Invidious API** — альтернативные фронтенды
4. **yt-dlp** — локально (fallback)

**Возврат:** `(file_path, title, duration)`

**Файлы:**
- `requirements.txt` — `ytmusicapi`
- `core/tools.py` — `download_audio()`

---

### 4. Production Bug Fixes
**Ошибки:**
- `TelegramBadRequest: message is not modified`
- `NameError: name 'os' is not defined`

**Исправления:**
- `handlers/limits.py` — try/except для `edit_text`
- `core/tools.py` — `import os`

---

## 📁 Структура Проекта

```
ai_prophet/
├── core/
│   ├── ai_engine.py      # Gemini + HF транскрибация
│   └── tools.py          # Поиск медиа, скачивание, web search
├── handlers/
│   ├── messages.py       # Основная логика бота
│   ├── limits.py         # Настройки лимитов (новый)
│   └── vip.py            # VIP функционал
├── config.py             # Конфигурация, токены
├── main.py               # Точка входа (FastAPI + Aiogram)
├── requirements.txt      # ytmusicapi, yt-dlp, ddgs...
├── HISTORY.md            # Летопись проекта
├── CONTEXT_SUMMARY.md    # Это файл (саммари для чата)
└── internal/             # Внутренняя документация
```

---

## 🚀 Как Запустить

### Локально (Windows)
```bash
cd d:\ai\ai_prophet
venv\Scripts\activate
python main.py
```

### HF Spaces (Production)
Автоматически деплоится при `git push origin dev-phase3`

---

## 🎛 Команды для Разработки

```bash
# Проверка изменений
git status
git diff HEAD

# Коммит и пуш
git add .
git commit -m "fix: описание"
git push origin dev-phase3

# Логи
git log --oneline -10
```

---

## 🐛 Известные Проблемы

| Проблема | Статус | Решение |
|----------|--------|---------|
| YouTube блокирует HF Spaces | 🔴 Критично | Все 4 источника блокируются (ytmusicapi, Cobalt, Invidious, yt-dlp) |
| Telegram: message not modified | ✅ Исправлено | try/except в `update_limits_message()` |
| ValueError: too many values | ✅ Исправлено | `download_audio()` возвращает 3 значения |
| HF Whisper 410 ошибка | ✅ Исправлено | fallback на Gemini |
| Gemini 429 quota | ✅ Исправлено | fallback на HF |
| NameError: os not defined | ✅ Исправлено | добавлен import os |

---

## 🔧 Актуальные Задачи

### 1. Скачать музыку на HF Spaces (КРИТИЧНО)
**Проблема:** YouTube блокирует все серверные IP (HF Spaces, Docker, облака).

**Текущий статус:**
- ❌ ytmusicapi — нет доступных потоков
- ❌ Cobalt API — HTTP 400
- ❌ Invidious — таймауты (блокируются)
- ❌ yt-dlp — требует авторизации

**Возможные решения:**
1. **Прокси/VPN** — обход блокировок по IP
2. **Cookies** — экспорт из браузера, передача в yt-dlp
3. **Спонсируемые API** — платные сервисы (RapidAPI)
4. **Локальный сервер** — запуск дома, HF как фронтенд
5. **Альтернативы** — SoundCloud, Deezer (30 сек превью)

**Временное решение:**
- Локальный запуск работает ✅
- HF Spaces — только текстовые запросы

---

## 📊 Технологический Стек

| Компонент | Технология |
|-----------|------------|
| Bot Framework | aiogram 3.x |
| Core AI | Google Gemini 2.5/3 Flash |
| Fallback AI | Hugging Face (Qwen, Llama, Whisper) |
| Music Search | DuckDuckGo Videos + ytmusicapi |
| Music Download | Cobalt API + Invidious + yt-dlp |
| Web Server | FastAPI + Uvicorn |
| Deployment | Docker, Hugging Face Spaces |

---

## 📝 Последние Коммиты

```
ce05f30 docs: обновлена HISTORY.md + CONTEXT_SUMMARY.md для нового чата
217e2c2 feat: ytmusicapi + длительность трека (полные треки)
70ba508 fix: критические ошибки на проде (os import + TelegramBadRequest)
d3c89c8 fix: удалить несуществующий импорт Modal (aiogram 3.x)
40c2e5d feat: плавные лимиты с интеграцией в поиск музыки
```

---

## 📝 Следующие Шаги (Roadmap)

- [ ] MCP интеграция (Model Context Protocol)
- [ ] Авто-исправление багов через self-analysis
- [ ] Расширение Mini App (панель управления ИИ)
- [ ] Поддержка Spotify/Apple Music API
- [ ] Голосовые команды (распознавание + действия)

---

## 🔑 Контакты и Доступы

**GitHub:** https://github.com/dizel0110/ai_prophet
**Telegram Bot:** @ai_prophet_io_bot
**HF Spaces:** https://huggingface.co/spaces/dizel0110/ai_prophet

**Ветка:** `dev-phase3` (основная для разработки)

---

*Этот документ для быстрого погружения в проект. Полная история в `HISTORY.md`.*
