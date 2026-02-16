# 🧠 AI Prophet — Context Summary для Нового Чата

**Дата:** 2026-02-17  
**Ветка:** `dev-phase3`  
**Статус:** ✅ Работает на HF Spaces

---

## 📦 Краткая Сводка Проекта

**AI Prophet** — Telegram бот с мультимодальным ИИ:
- 🎙 Голосовые сообщения (транскрибация + ответ)
- 🖼 Анализ фото (Gemini Vision + HF fallback)
- 🎵 Поиск и скачивание музыки (YouTube)
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
1. **ytmusicapi** — YouTube Music API
2. **Cobalt API** — публичный API
3. **Invidious API** — альтернативные фронтенды
4. **yt-dlp** — локально (fallback)

**Возврат:** `(file_path, title, duration)`

**Файлы:**
- `requirements.txt` — `ytmusicapi`
- `core/tools.py` — `download_audio()`

---

### 4. Production Fixes
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
└── HISTORY.md            # Полная летопись проекта
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
| YouTube блокирует HF Spaces | ⚠️ Частично | ytmusicapi + Cobalt + Invidious |
| Telegram: message not modified | ✅ Исправлено | try/except в `update_limits_message()` |
| HF Whisper 410 ошибка | ✅ Исправлено | fallback на Gemini |
| Gemini 429 quota | ✅ Исправлено | fallback на HF |

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
