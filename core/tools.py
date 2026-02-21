import logging
import requests
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

def web_search(query: str, max_results: int = 5):
    """Выполняет поиск в сети через DuckDuckGo"""
    try:
        logger.info(f"🔎 Поиск в сети по запросу: {query}")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
            if not results:
                return "Поиск не дал результатов."
            
            formatted_results = []
            for i, r in enumerate(results, 1):
                formatted_results.append(f"{i}. {r['title']}\n{r['body']}\nURL: {r['href']}")
            
            return "\n\n".join(formatted_results)
    except Exception as e:
        logger.error(f"❌ Ошибка поиска: {e}")
        return f"К сожалению, я не смог подключиться к информационному полю: {e}"

def search_youtube_videos(query: str, max_results: int = 5):
    """Ищет видео на YouTube через yt-dlp"""
    try:
        import yt_dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': False, # Включаем логи yt-dlp для дебага
            'ignoreerrors': True, # Не падать при ошибках видео
            'default_search': f'ytsearch{max_results}',
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(query, download=False)
            if 'entries' in res:
                return res['entries']
    except ImportError:
        logger.error("❌ yt-dlp не установлен. Установите: pip install yt-dlp")
        return []
    except Exception as e:
        logger.error(f"❌ YouTube Search Error: {e}")
    
    # Fallback: DuckDuckGo Video Search
    try:
        logger.info(f"🦆 Пробуем DDG Video Search для: {query}")
        with DDGS() as ddgs:
            # Ищем видео
            results = list(ddgs.videos(query, max_results=max_results))
            if results:
                # Приводим к формату yt-dlp (примерно)
                normalized = []
                for r in results:
                    normalized.append({
                        'title': r.get('title'),
                        'url': r.get('content'), # DDG возвращает ссылку в 'content' или 'click_url'
                        'id': 'unknown'
                    })
                return normalized
    except Exception as e:
        logger.error(f"❌ DDG Video Search Error: {e}")

    return []

def search_media_content(query: str, media_type: str = 'audio', count: int = 5, chat_id: str = None):
    """
    Универсальный поиск медиа (аудио/видео) на YouTube/DDG.

    query: Что искать (жанр, исполнитель, название)
    media_type: 'audio' (музыка) или 'video' (клипы/видео)
    count: количество результатов (по умолчанию 5)
    chat_id: ID чата для загрузки пользовательских лимитов
    
    Returns:
        dict: {
            "query": str,
            "media_type": str,
            "tracks": List[dict],  # каждый dict: {title, url, duration, thumbnail}
            "count": int,
            "text": str  # отформатированный текст для отправки пользователю
        }
    """
    import os
    import random
    import json
    from urllib.parse import parse_qs, urlparse

    # Загрузка лимитов пользователя
    limits_file = "temp/user_limits.json"
    if chat_id and os.path.exists(limits_file):
        try:
            with open(limits_file, 'r', encoding='utf-8') as f:
                all_limits = json.load(f)
                user_limits = all_limits.get(str(chat_id), {})

                # Определяем количество результатов на основе лимитов
                duration = user_limits.get("duration", 1800)
                size = user_limits.get("size", 50)

                if duration <= 300 and size <= 10:
                    # Быстрый режим — можно больше результатов
                    auto_count = min(count, 10)
                    speed_label = "⚡ быстро"
                elif duration <= 1800 and size <= 50:
                    # Баланс
                    auto_count = min(count, 5)
                    speed_label = "⚖️ нормально"
                else:
                    # Максимум — меньше результатов (долгая загрузка)
                    auto_count = min(count, 3)
                    speed_label = "🐢 долго"

                logger.info(f"🎛 Лимиты: {duration} сек, {size} MB → {auto_count} рез. ({speed_label})")
                count = auto_count

        except Exception as e:
            logger.warning(f"Failed to load user limits: {e}")

    # Нормализуем тип
    media_type = media_type.lower()
    if media_type not in ['audio', 'video']: media_type = 'audio'

    logger.info(f"📹 Поиск медиа: query='{query}', type={media_type}, count={count}")

    all_videos = []
    queries = []

    # 1. Формируем умные запросы
    if media_type == 'audio':
        # Для музыки ищем треки с текстом или аудио (чтобы не клипы)
        queries = [
            f"{query} {media_type}",
            f"{query} lyrics",
            f"Best {query} songs",
        ]
    else:
        # Для видео ищем клипы или официальные видео
        queries = [
            f"{query} official video",
            f"{query} music video",
            f"{query} hd",
        ]

    # Если просили 1 трек, берем самый точный запрос
    if count == 1:
        queries = [queries[0]]
    else:
        # Иначе миксуем для разнообразия
        queries = random.sample(queries, min(2, len(queries)))

    # 2. Ищем через DDG Video Search (он работает надежнее)
    for q in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.videos(q, max_results=count))
                if results:
                    all_videos.extend(results)
        except Exception as e:
            logger.error(f"❌ DDG Video Search Error for '{q}': {e}")

    # 3. Дедупликация и рандом
    unique_videos = {}
    for v in all_videos:
        # DDG возвращает 'content' как ссылку
        url = v.get('content') or v.get('click_url')
        if url and 'youtube.com' in url: # Фильтруем только YouTube
            unique_videos[url] = v

    final_playlist = list(unique_videos.values())

    # Если это плейлист (>1), перемешиваем
    if count > 1:
        random.shuffle(final_playlist)

    # Обрезаем
    final_playlist = final_playlist[:count]

    # 4. Формируем структурированный результат
    tracks = []
    for i, video in enumerate(final_playlist, 1):
        title = video.get('title', 'Unknown Track')
        url = video.get('content') or video.get('click_url')
        
        # Пытаемся извлечь duration из URL или ставим 0
        duration = 0
        thumbnail = ""
        
        # Извлекаем video_id для thumbnail
        parsed = urlparse(url)
        video_id = parse_qs(parsed.query).get('v', [None])[0]
        if not video_id:
            # Пробуем из короткой ссылки youtu.be
            video_id = parsed.path.strip('/')
        
        if video_id:
            thumbnail = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

        tracks.append({
            "title": title,
            "url": url,
            "duration": duration,
            "thumbnail": thumbnail,
            "index": i
        })

    # Формируем текстовое представление
    tracks_text = []
    if tracks:
        for track in tracks:
            icon = "🎵" if media_type == 'audio' else "🎬"
            tracks_text.append(f"{track['index']}. {icon} [{track['title']}]({track['url']})")
        status_line = f"✨ Найдено {len(tracks)} рез. по запросу: {query}"
    else:
        # Fallback (DDG ссылки на поиск)
        status_line = "⚠️ Прямой поток недоступен, вот поисковая выдача:"
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        tracks_text.append(f"1. 🔍 [Найти '{query}' на YouTube]({search_url})")
        # Добавляем fallback трек
        tracks.append({
            "title": f"Search: {query}",
            "url": search_url,
            "duration": 0,
            "thumbnail": "",
            "index": 1,
            "is_fallback": True
        })

    header = f"🎧 *Аудио-поток: {query}*" if media_type == 'audio' else f"📺 *Видео-поток: {query}*"

    tracks_joined = '\n'.join(tracks_text)
    text_result = (
        f"{header}\n\n"
        f"{tracks_joined}\n\n"
        f"{status_line}"
    )

    return {
        "query": query,
        "media_type": media_type,
        "tracks": tracks,
        "count": len(tracks),
        "text": text_result
    }

async def send_playlist(
    bot,
    chat_id: int,
    tracks: list,
    status_msg=None,
    chat_id_str: str = None
):
    """
    Последовательно скачивает и отправляет треки в Telegram.
    
    bot: Bot instance
    chat_id: ID чата
    tracks: Список словарей [{title, url, duration, thumbnail}, ...]
    status_msg: Сообщение для обновления статуса
    chat_id_str: строковое представление chat_id для лимитов
    
    Returns:
        dict: {
            "sent": int,  # количество отправленных треков
            "failed": int,  # количество неудач
            "tracks": list  # отправленные треки
        }
    """
    import os
    from aiogram.types import FSInputFile
    
    result = {
        "sent": 0,
        "failed": 0,
        "tracks": []
    }
    
    total = len(tracks)
    
    for i, track in enumerate(tracks, 1):
        # Пропускаем fallback треки (это просто ссылки на поиск)
        if track.get("is_fallback"):
            logger.warning(f"⚠️ Пропуск fallback трека: {track['title']}")
            result["failed"] += 1
            continue
        
        # Обновляем статус
        if status_msg:
            try:
                await status_msg.edit_text(
                    f"⬇️ Трек {i}/{total}: {track['title']}..."
                )
            except Exception:
                pass  # Игнорируем ошибки обновления сообщения
        
        logger.info(f"🎵 Скачивание трека {i}/{total}: {track['title']}")
        
        try:
            # Скачиваем аудио
            file_path, title, duration = download_audio(
                track['url'], 
                chat_id=chat_id_str
            )
            
            if file_path and os.path.exists(file_path):
                # Отправляем аудио
                audio_file = FSInputFile(file_path)
                duration_text = f" ({duration} сек)" if duration else ""
                
                await bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    title=title or track['title'],
                    performer="AI Prophet",
                    caption=f"🎧 {track['title']}{duration_text}"
                )
                
                # Удаляем файл
                os.remove(file_path)
                logger.info(f"✅ Отправлен трек: {track['title']}")
                
                result["sent"] += 1
                result["tracks"].append(track)
            else:
                logger.error(f"❌ Не удалось скачать трек: {track['title']}")
                result["failed"] += 1
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки трека {track['title']}: {e}")
            result["failed"] += 1
    
    return result

def download_audio(url: str, chat_id: str = None, max_duration_sec: int = None, max_filesize_mb: int = None):
    """
    Скачивает аудио из YouTube/SoundCloud (m4a/mp3) во временную папку.
    Возвращает (путь_к_файлу, название_трека, длительность).

    Использует yt-dlp с эмуляцией браузера для обхода блокировок.

    chat_id: ID чата для загрузки пользовательских лимитов
    max_duration_sec: максимальная длительность (по умолчанию 1800 сек = 30 мин)
    max_filesize_mb: максимальный размер файла (по умолчанию 100 MB)
    """
    import os
    from config import TEMP_DIR
    import yt_dlp
    import time
    import json

    # Загрузка пользовательских лимитов
    limits_file = "temp/user_limits.json"
    if chat_id and os.path.exists(limits_file):
        try:
            with open(limits_file, 'r', encoding='utf-8') as f:
                all_limits = json.load(f)
                user_limits = all_limits.get(str(chat_id), {})
                if max_duration_sec is None:
                    max_duration_sec = user_limits.get("duration", 1800)
                if max_filesize_mb is None:
                    max_filesize_mb = user_limits.get("size", 100)
        except Exception:
            pass

    # Значения по умолчанию
    if max_duration_sec is None:
        max_duration_sec = 1800
    if max_filesize_mb is None:
        max_filesize_mb = 100

    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    # Генерируем уникальное имя
    import uuid
    sys_filename = f"audio_{uuid.uuid4().hex[:8]}"
    output_template = os.path.join(TEMP_DIR, f"{sys_filename}.%(ext)s")

    start_time = time.time()
    logger.info(f"⬇️ Скачиваю аудио: {url}")

    # === yt-dlp с эмуляцией браузера (как локально) ===
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': max_filesize_mb * 1024 * 1024,

        # Эмуляция браузера для обхода блокировок
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'referer': 'https://www.youtube.com/',

        # Обход блокировок YouTube - используем все доступные клиенты
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'web', 'web_embedded', 'tv_embedded'],
                'player_skip': ['webpage'],
            }
        },
        
        # Пробуем разные экстракторы
        'extract_flat': False,
        'ignoreerrors': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = info.get('title', 'Audio Track')
            duration = info.get('duration', 0)
            clean_title = title.replace('(Official Video)', '').replace('[Official Audio]', '').strip()

            download_time = time.time() - start_time
            logger.info(f"✅ Скачано: {clean_title} ({duration} сек) за {download_time:.1f} сек")
            return filename, clean_title, duration

    except Exception as e:
        error_msg = str(e)

        # Анализ ошибки
        if "Sign in to confirm" in error_msg or "bot" in error_msg.lower():
            logger.error("❌ YouTube требует авторизацию (блокировка серверных IP)")
            logger.info("💡 Решение:")
            logger.info("   1. Локальный запуск (домашний IP работает)")
            logger.info("   2. SoundCloud (не блокируется)")
            logger.info("   3. Cookies файл: temp/youtube_cookies.txt")
        elif "HTTP Error 429" in error_msg:
            logger.warning("⚠️ YouTube заблокировал запрос (слишком много запросов)")
        else:
            logger.error(f"❌ Ошибка: {e}")

        return None, None, None

def get_prophet_tools_spec():
    """Спецификация инструментов в формате, который 100% поймет Pydantic в SDK 2026"""
    return [
        {
            "name": "web_search",
            "description": "Поиск свежей информации в интернете (новости, факты, цены).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Поисковый запрос"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "search_media_content",
            "description": "Поиск музыки или видео на YouTube/Интернет.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Что искать (жанр, исполнитель, название трека)"},
                    "media_type": {"type": "STRING", "description": "'audio' или 'video'"},
                    "count": {"type": "INTEGER", "description": "Количество результатов (по умолчанию 5)"}
                },
                "required": ["query", "media_type"]
            }
        }
    ]

AVAILABLE_FUNCTIONS = {
    "web_search": web_search,
    "search_media_content": search_media_content
}
