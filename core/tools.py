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
    """
    import random
    import json

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

    Алгоритм (Февраль 2026):
    1. Cobalt API (стабильно, без блокировок)
    2. Invidious API (fallback)
    3. yt-dlp (локально, где нет блокировок)

    chat_id: ID чата для загрузки пользовательских лимитов
    max_duration_sec: максимальная длительность (по умолчанию из настроек пользователя или 1800 сек = 30 мин)
    max_filesize_mb: максимальный размер файла (по умолчанию из настроек пользователя или 100 MB)
    """
    import os
    from config import TEMP_DIR
    import yt_dlp
    import time
    import json
    import requests

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

    # Извлекаем video_id из URL
    video_id = url.split('v=')[-1].split('&')[0].split('?')[0] if 'v=' in url else url.split('/')[-1].split('?')[0]

    start_time = time.time()
    logger.info(f"⬇️ Скачиваю аудио: {url} (video_id: {video_id})")

    # === ПОПЫТКА 1: Cobalt API (стабильно, Февраль 2026) ===
    try:
        logger.info("📡 Cobalt API: запрос...")
        cobalt_url = "https://api.cobalt.tools/api/json"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "url": url,
            "isAudioOnly": True,
            "filenamePattern": "simple",
        }

        response = requests.post(cobalt_url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "")

            if status == "stream" or status == "redirect":
                download_url = data.get("url")
                if download_url:
                    logger.info(f"🎵 Cobalt: найден поток {download_url[:50]}...")

                    # Скачиваем аудио
                    output_path = os.path.join(TEMP_DIR, f"{sys_filename}.mp3")
                    audio_response = requests.get(download_url, timeout=120)

                    if audio_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            f.write(audio_response.content)

                        download_time = time.time() - start_time
                        logger.info(f"✅ Cobalt: скачано за {download_time:.1f} сек")
                        return output_path, f"Audio_{video_id}"
                    else:
                        logger.warning(f"⚠️ Cobalt: ошибка скачивания {audio_response.status_code}")
            elif status == "error":
                logger.warning(f"⚠️ Cobalt error: {data.get('text', 'unknown')}")
            else:
                logger.warning(f"⚠️ Cobalt status: {status}")
        else:
            logger.warning(f"⚠️ Cobalt HTTP error: {response.status_code}")

    except Exception as e:
        logger.warning(f"⚠️ Cobalt API failed: {e}")

    # === ПОПЫТКА 2: Invidious API (fallback) ===
    invidious_instances = [
        "https://inv.tux.pizza",
        "https://invidious.io.lol",
        "https://yewtu.be",
    ]

    for instance in invidious_instances:
        try:
            logger.info(f"📡 Invidious: {instance}")
            api_url = f"{instance}/api/v1/videos/{video_id}"

            response = requests.get(api_url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                title = data.get('title', 'Audio Track')
                duration = data.get('lengthSeconds', 0)

                audio_streams = data.get('adaptiveFormats', [])
                audio_stream = None
                for fmt in audio_streams:
                    if 'audio' in fmt.get('type', ''):
                        audio_stream = fmt
                        break

                if audio_stream:
                    audio_url = audio_stream.get('url')
                    output_path = os.path.join(TEMP_DIR, f"{sys_filename}.m4a")
                    audio_response = requests.get(audio_url, timeout=60)

                    if audio_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            f.write(audio_response.content)

                        clean_title = title.replace('(Official Video)', '').strip()
                        download_time = time.time() - start_time
                        logger.info(f"✅ Invidious: {clean_title} за {download_time:.1f} сек")
                        return output_path, clean_title

        except Exception as inst_error:
            logger.warning(f"⚠️ Invidious failed: {inst_error}")
            continue

    # === ПОПЫТКА 3: yt-dlp (локально) ===
    logger.warning("⚠️ Online сервисы не сработали, пробуем yt-dlp...")

    output_template = os.path.join(TEMP_DIR, f"{sys_filename}.%(ext)s")
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': max_filesize_mb * 1024 * 1024,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = info.get('title', 'Audio Track')
            clean_title = title.replace('(Official Video)', '').strip()

            download_time = time.time() - start_time
            logger.info(f"✅ yt-dlp: {clean_title} за {download_time:.1f} сек")
            return filename, clean_title

    except Exception as e:
        logger.error(f"❌ Все методы не сработали: {e}")
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
