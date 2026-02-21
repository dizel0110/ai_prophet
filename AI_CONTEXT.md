# 🤖 AI Assistant Context — AI Prophet

> **Для любой AI-модели**, которая будет помогать с этим проектом.

---

## 📌 Проект: AI Prophet

**Telegram-бот** с мультимодальным ИИ (текст, фото, голос, музыка).

**Репозиторий:** `dizel0110/ai_prophet`  
**Ветка разработки:** `dev-phase3`  
**Прод:** `main` (автодеплой на Hugging Face Spaces)

---

## 🏗 Архитектура

```
ai_prophet/
├── main.py              # Точка входа (запускает бота + FastAPI)
├── bot.py               # Обёртка для main.py
├── config.py            # Конфигурация (TOKEN, KEY, PATH)
│
├── core/
│   ├── ai_engine.py     # LLM-движки (Gemini, HF)
│   ├── tools.py         # Инструменты (поиск, музыка, плейлисты)
│   ├── mcp_client.py    # MCP-интеграция (планируется)
│   └── network.py       # DNS-патчи
│
├── handlers/
│   ├── messages.py      # Основные сообщения, команды, музыка
│   ├── vip.py           # VIP-команды
│   └── limits.py        # Лимиты пользователей
│
├── temp/                # Временные файлы (аудио, фото)
└── .env                 # Переменные окружения (не в git)
```

---

## 🛠 Технологический стек

| Компонент | Технология |
|-----------|------------|
| Бот | Aiogram 3.x |
| LLM (основной) | Google Gemini 2.5 Flash |
| LLM (fallback) | Hugging Face (Qwen 2.5, Whisper) |
| Поиск | DuckDuckGo (DDGS) |
| Музыка | yt-dlp + ffmpeg |
| Веб-сервер | FastAPI + Uvicorn |
| Деплой | Hugging Face Spaces (Docker) |

---

## 📋 Последние изменения (Февраль 2026)

### ✅ Реализовано (Phase 3):

1. **Плейлисты** — отправка нескольких треков подряд:
   - `core/tools.py`: `search_media_content()` → `List[dict]`
   - `core/tools.py`: `send_playlist()` — отправка серии аудио
   - `handlers/messages.py`: `/playlist` команда
   - `handlers/messages.py`: кнопка "Скачать всё"
   - `handlers/messages.py`: `handle_playlist_callback()`

2. **Команда `/help`** — полная справка по боту

3. **Обновлённое `/start`** — описание возможностей

### ⏳ Ожидает тестирования:
- Отправка плейлистов (3-5 треков подряд)
- Обработка ошибок для длинных треков (30+ мин)

### 📅 Следующий этап (Phase 4):
- Долгосрочная память (SQLite)
- `core/memory.py` — `MemoryManager`
- Инструмент `save_fact()` для LLM

---

## 🔑 Ключевые файлы для изменений

| Файл | Что содержит |
|------|--------------|
| `core/tools.py` | Поиск музыки, плейлисты, веб-поиск |
| `handlers/messages.py` | Команды бота, обработка сообщений |
| `core/ai_engine.py` | Взаимодействие с LLM (Gemini, HF) |
| `config.py` | Переменные окружения, константы |

---

## 🧪 Тестирование

```bash
# Локальный запуск
python main.py

# Тест музыки
/playlist Pink Floyd 3

# Тест справки
/help
```

---

## 📁 Документация проекта

| Файл | Описание |
|------|----------|
| `README.md` | Общее описание проекта |
| `NEXT_STEPS.md` | План разработки (Phase 3, 4) |
| `PLAYLIST_IMPLEMENTATION.md` | Детали реализации плейлистов |
| `DEVELOPMENT_PRINCIPLES.md` | Принципы разработки (FREE-FIRST) |
| `VENV_SETUP_GUIDE.md` | Настройка виртуального окружения |
| `AI_CONTEXT.md` | **Этот файл** — контекст для AI |

---

## 🚀 Деплой

1. Пуш в `main` → автодеплой на Hugging Face Spaces
2. Переменные окружения настраиваются в Space settings:
   - `TELEGRAM_TOKEN`
   - `GEMINI_API_KEY`
   - `HF_TOKEN`

---

## ⚠️ Важно для AI-помощников

1. **Не переводить код** — все комментарии и строки на русском/английском как есть
2. **Стиль кода** — следовать существующим паттернам в проекте
3. **Проверять импорты** — после изменений запускать `python -m py_compile`
4. **Коммиты** — писать осмысленные сообщения (что и зачем изменено)
5. **Бесплатные ресурсы** — приоритет FREE-FIRST (см. `DEVELOPMENT_PRINCIPLES.md`)

---

## 📞 Контакты

**Владелец:** dizel0110  
**Telegram:** @ai_prophet_io_bot  
**HF Space:** https://huggingface.co/spaces/dizel0110/ai-prophet

---

*Последнее обновление: 20 февраля 2026*  
*Создано для предотвращения неразберихи между AI-агентами*
