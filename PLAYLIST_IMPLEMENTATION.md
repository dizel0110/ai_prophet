# 🎵 Реализация Плейлистов для AI Prophet

## 📌 Цель
Научить бота отправлять **несколько аудиофайлов подряд** (плейлисты/альбомы), чтобы треки играли один за другим в Telegram.

---

## 📋 Текущее состояние (AS IS)

### Что работает сейчас:
1. ✅ Поиск музыки через `search_media_content()` — находит 1-5 треков
2. ✅ Отправка текста со ссылками на YouTube
3. ✅ Скачивание **одного** трека через `download_audio()`
4. ✅ Кнопки `⬇️ 1`, `⬇️ 2`... для скачивания по одному треку

### Проблемы:
- ❌ Бот отправляет только **текстовый список** треков
- ❌ Пользователь должен нажимать кнопку для **каждого трека отдельно**
- ❌ Нет команды для автоматической отправки **всего плейлиста сразу**

---

## 🎯 План реализации (TO BE)

### Этап 1: Модификация `search_media_content` (Task #1)

**Задача:** Изменить функцию для возврата структурированного списка вместо текста.

**Текущий возврат:**
```python
return """
🎧 Аудио-поток: Pink Floyd

1. 🎵 [Comfortably Numb](https://youtube.com/...)
2. 🎵 [Wish You Were Here](https://youtube.com/...)

✨ Найдено 2 рез.
"""
```

**Новый возврат:**
```python
return {
    "query": "Pink Floyd best songs",
    "media_type": "audio",
    "tracks": [
        {
            "title": "Comfortably Numb",
            "url": "https://youtube.com/watch?v=...",
            "duration": 382,  # секунды (если доступно)
            "thumbnail": "https://i.ytimg.com/vi/.../hqdefault.jpg"
        },
        {
            "title": "Wish You Were Here",
            "url": "https://youtube.com/watch?v=...",
            "duration": 334,
            "thumbnail": "..."
        }
    ],
    "count": 2
}
```

**Где изменить:**
- Файл: `core/tools.py`
- Функция: `search_media_content()` (строки ~60-180)

---

### Этап 2: Создание `send_playlist` (Task #2)

**Задача:** Функция для отправки серии аудио в Telegram.

**Прототип:**
```python
async def send_playlist(
    bot: Bot,
    chat_id: int,
    tracks: List[dict],
    status_msg: types.Message = None
):
    """
    Последовательно скачивает и отправляет треки.
    
    tracks: Список словарей [{title, url, duration}, ...]
    """
    from aiogram.types import FSInputFile
    
    for i, track in enumerate(tracks, 1):
        # Обновляем статус
        if status_msg:
            await status_msg.edit_text(
                f"⬇️ Трек {i}/{len(tracks)}: {track['title']}..."
            )
        
        # Скачиваем
        file_path, title, duration = download_audio(
            track['url'], 
            chat_id=str(chat_id)
        )
        
        if file_path:
            # Отправляем аудио
            audio_file = FSInputFile(file_path)
            await bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                title=title,
                performer=f"AI Prophet #{i}",
                caption=f"🎧 {title} ({duration} сек)"
            )
            
            # Удаляем файл
            os.remove(file_path)
```

**Где создать:**
- Файл: `core/tools.py` (новая функция)
- Или: `handlers/music.py` (если выделим музыку в отдельный модуль)

---

### Этап 3: Обновление парсинга `[MEDIA: ...]` (Task #3)

**Задача:** Поддержка `count > 1` для автоматической отправки плейлистов.

**Текущий формат:**
```
[MEDIA: Pink Floyd, audio, 5]
```

**Логика:**
- Если `count == 1` → скачиваем и отправляем **один трек сразу**
- Если `count > 1` → показываем список с кнопками **ИЛИ** отправляем плейлист

**Где изменить:**
- Файл: `handlers/messages.py`
- Функция: `parse_and_execute_tools()` (строки ~109-145)

**Новая логика:**
```python
def parse_and_execute_tools(text, chat_id: str = None):
    # ... парсинг [MEDIA: ...] ...
    
    if count == 1:
        # Скачиваем один трек немедленно
        result = download_audio(url, chat_id=chat_id)
        return clean_text, {"type": "single_audio", "data": result}
    else:
        # Возвращаем список для плейлиста
        result = search_media_content(query, media_type, count, chat_id)
        return clean_text, {"type": "playlist", "data": result}
```

---

### Этап 4: Команда `/playlist` (Task #4)

**Задача:** Явный запрос плейлиста пользователем.

**Примеры использования:**
```
/playlist Pink Floyd rock
/playlist ambient для сна
/playlist рок 80х 10
```

**Реализация:**
```python
@router.message(Command("playlist"))
async def cmd_playlist(message: types.Message, bot: Bot):
    # Парсим аргументы
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer(
            "🎵 *Использование:*\n"
            "`/playlist <жанр/исполнитель> [количество]`\n\n"
            "Примеры:\n"
            "`/playlist Pink Floyd 5`\n"
            "`/playlist рок 80х`"
        )
        return
    
    query = args[1]
    count = int(args[2]) if len(args) > 2 else 5
    
    # Запускаем ритуал поиска
    status_msg = await message.answer(f"🎵 *Ищу плейлист: {query}*...")
    await conduct_ai_ritual(message, bot, f"Найди {count} треков: {query}", status_msg)
```

**Где создать:**
- Файл: `handlers/messages.py`
- После: `@router.message(CommandStart())`

---

### Этап 5: Обновление `handle_download_callback` (Task #5)

**Задача:** Поддержка кнопок для плейлистов.

**Текущие кнопки:**
```
[⬇️ 1] [⬇️ 2] [⬇️ 3] [⬇️ 4] [⬇️ 5]
```

**Новые кнопки:**
```
[⬇️ 1] [⬇️ 2] [⬇️ 3] [⬇️ 4] [⬇️ 5]
[🎧 Скачать всё (плейлист)]
```

**Изменения:**
- В `handle_download_callback` добавить проверку на `dl_playlist:`
- Создать `handle_playlist_callback` для массовой загрузки

---

### Этап 6: Тестирование (Task #6)

**Чек-лист тестов:**
- [ ] Отправка 1 трека (быстро, <5 мин)
- [ ] Отправка 3 треков (средне, 5-15 мин)
- [ ] Отправка 5 треков (долго, 15+ мин)
- [ ] Обработка ошибок (недоступное видео)
- [ ] Очистка временных файлов
- [ ] Работа с лимитами пользователя

---

## 📁 Структура файлов (после изменений)

```
ai_prophet/
├── core/
│   ├── tools.py              # search_media_content, send_playlist, download_audio
│   └── ai_engine.py
├── handlers/
│   ├── messages.py           # handle_download_callback, cmd_playlist
│   └── music.py              # (опционально) выделение музыки в отдельный модуль
├── temp/
│   ├── audio_*.m4a          # временные файлы
│   └── user_limits.json     # лимиты пользователей
└── PLAYLIST_IMPLEMENTATION.md # этот файл
```

---

## ⚠️ Потенциальные проблемы

### 1. Лимиты Telegram
- **Проблема:** Telegram ограничивает размер файла (50 MB для обычных, 2 GB для Premium)
- **Решение:** Проверять размер перед отправкой, использовать `user_limits`

### 2. Время загрузки
- **Проблема:** 5 треков по 10 мин = 50+ минут загрузки
- **Решение:** 
  - Показывать прогресс (`Трек 3/5...`)
  - Предупреждать пользователя о времени
  - Предлагать «быстрый режим» (1-2 трека)

### 3. Блокировки YouTube
- **Проблема:** YouTube блокирует серверные IP
- **Решение:** 
  - Использовать cookies (файл `temp/youtube_cookies.txt`)
  - Fallback на SoundCloud
  - Локальный запуск (домашний IP)

---

## 🚀 Следующие шаги после реализации

1. **Голосовые плейлисты** — распознавание команд типа _"Включи 5 треков Pink Floyd"_
2. **Жанровые пресеты** — `/playlist rock`, `/playlist lofi`
3. **История плейлистов** — сохранение последних запросов
4. **Шаринг** — возможность поделиться плейлистом с другом

---

## 📝 Хронология реализации

| Дата | Задача | Статус |
|------|--------|--------|
| 20.02.2026 | Создание плана | ✅ Выполнено |
| 20.02.2026 | Task #1: Модификация search_media_content | ✅ Выполнено |
| 20.02.2026 | Task #2: Создание send_playlist | ✅ Выполнено |
| 20.02.2026 | Task #3: Обновление парсинга | ✅ Выполнено |
| 20.02.2026 | Task #4: Команда /playlist | ✅ Выполнено |
| 20.02.2026 | Task #5: Обновление callback | ✅ Выполнено |
| 20.02.2026 | Task #6: Тестирование | ⏳ Ожидает |
| 20.02.2026 | Task #7: Обновление документации | ✅ Выполнено |

---

*Документ создан: 20 февраля 2026*
*Последнее обновление: 20 февраля 2026*
