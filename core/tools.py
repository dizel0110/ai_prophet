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

def search_media_content(query: str, media_type: str = 'audio', count: int = 5):
    """
    Универсальный поиск медиа (аудио/видео) на YouTube/DDG.
    query: Что искать (жанр, исполнитель, название)
    media_type: 'audio' (музыка) или 'video' (клипы/видео)
    count: количество результатов
    """
    import random
    
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
    
    # 4. Формируем ответ
    tracks = []
    if final_playlist:
        for i, video in enumerate(final_playlist, 1):
            title = video.get('title', 'Unknown Track')
            url = video.get('content') or video.get('click_url')
            
            # Иконка зависит от типа
            icon = "🎵" if media_type == 'audio' else "🎬"
            tracks.append(f"{i}. {icon} [{title}]({url})")
            
        status_line = f"✨ Найдено {len(tracks)} рез. по запросу: {query}"
    else:
        # Fallback (DDG ссылки на поиск)
        status_line = "⚠️ Прямой поток недоступен, вот поисковая выдача:"
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        tracks.append(f"1. 🔍 [Найти '{query}' на YouTube]({search_url})")

    tracks_list = "\n".join(tracks)
    
    header = f"🎧 *Аудио-поток: {query}*" if media_type == 'audio' else f"📺 *Видео-поток: {query}*"
    
    result = (
        f"{header}\n\n"
        f"{tracks_list}\n\n"
        f"{status_line}"
    )
    
    return result

def download_audio(url: str, chat_id: str = None, max_duration_sec: int = None, max_filesize_mb: int = None):
    """
    Скачивает аудио из YouTube видео (m4a/mp3) во временную папку.
    Возвращает (путь_к_файлу, название_трека).

    chat_id: ID чата для загрузки пользовательских лимитов
    max_duration_sec: максимальная длительность (по умолчанию из настроек пользователя или 1800 сек = 30 мин)
    max_filesize_mb: максимальный размер файла (по умолчанию из настроек пользователя или 100 MB)
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
    logger.info(f"⬇️ Скачиваю аудио: {url} (макс. {max_duration_sec} сек, {max_filesize_mb} MB)")

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': max_filesize_mb * 1024 * 1024,  # MB → bytes
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Информация о файле
            duration = info.get('duration', 0)
            filesize = info.get('filesize', 0)
            title = info.get('title', 'Audio Track')

            # Проверки (предупреждения, но не блокировка)
            if duration and duration > max_duration_sec:
                logger.warning(f"⚠️ Длительное аудио: {duration} сек (рекомендуется до {max_duration_sec} сек)")

            if filesize and filesize > max_filesize_mb * 1024 * 1024:
                logger.warning(f"⚠️ Большой файл: {filesize / 1024 / 1024:.1f} MB (макс. {max_filesize_mb} MB)")

            filename = ydl.prepare_filename(info)
            clean_title = title.replace('(Official Video)', '').replace('[Official Audio]', '').replace('(Lyrics)', '').strip()

            download_time = time.time() - start_time
            logger.info(f"✅ Скачано: {clean_title} ({duration} сек, {filesize / 1024 / 1024:.1f} MB) за {download_time:.1f} сек")

            return filename, clean_title

    except Exception as e:
        error_msg = str(e)

        # Анализ ошибки
        if "max_duration" in error_msg.lower():
            logger.warning(f"⚠️ Превышена максимальная длительность")
        elif "max_filesize" in error_msg.lower():
            logger.warning(f"⚠️ Превышен максимальный размер файла")
        elif "Sign in to confirm" in error_msg or "bot" in error_msg.lower():
            logger.warning("⚠️ YouTube требует авторизацию (защита от ботов)")
        elif "JavaScript runtime" in error_msg:
            logger.warning("⚠️ Не найден JavaScript runtime. Установите Node.js или добавьте --js-runtimes")
        elif "HTTP Error 429" in error_msg:
            logger.warning("⚠️ YouTube заблокировал запрос (слишком много запросов). Попробуйте позже.")

        logger.error(f"❌ Audio Download Error: {e}")
        return None, None

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
