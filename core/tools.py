import logging
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

def download_audio(url: str):
    """
    Скачивает аудио из YouTube видео (m4a/mp3) во временную папку.
    Возвращает (путь_к_файлу, название_трека).

    Пробует: Invidious API → yt-dlp (если есть cookies)
    """
    import os
    from config import TEMP_DIR
    import subprocess
    import json

    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    # Генерируем уникальное имя
    import uuid
    sys_filename = f"audio_{uuid.uuid4().hex[:8]}"

    # Извлекаем video_id из URL
    video_id = url.split('v=')[-1].split('&')[0].split('?')[0] if 'v=' in url else url.split('/')[-1].split('?')[0]

    logger.info(f"⬇️ Скачиваю аудио: {url} (video_id: {video_id})")

    # === ПОПЫТКА 1: Invidious API (без авторизации) ===
    try:
        # Список Invidious инстансов
        invidious_instances = [
            "https://inv.tux.pizza",
            "https://invidious.io.lol",
            "https://yewtu.be",
            "https://invidious.projectsegfau.lt",
        ]

        for instance in invidious_instances:
            try:
                api_url = f"{instance}/api/v1/videos/{video_id}"
                logger.info(f"📡 Запрос к Invidious: {api_url}")

                response = requests.get(api_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    title = data.get('title', 'Audio Track')

                    # Находим лучший аудиопоток
                    audio_streams = data.get('adaptiveFormats', [])
                    audio_stream = None
                    for fmt in audio_streams:
                        if fmt.get('type') and 'audio' in fmt.get('type', ''):
                            audio_stream = fmt
                            break

                    if audio_stream:
                        audio_url = audio_stream.get('url')
                        logger.info(f"🎵 Найден аудиопоток: {audio_stream.get('type')}")

                        # Скачиваем аудио
                        output_path = os.path.join(TEMP_DIR, f"{sys_filename}.m4a")
                        audio_response = requests.get(audio_url, timeout=30)
                        if audio_response.status_code == 200:
                            with open(output_path, 'wb') as f:
                                f.write(audio_response.content)

                            clean_title = title.replace('(Official Video)', '').replace('[Official Audio]', '').replace('(Lyrics)', '').strip()
                            logger.info(f"✅ Скачано через Invidious: {clean_title}")
                            return output_path, clean_title
                        else:
                            logger.warning(f"⚠️ Не удалось скачать аудио: {audio_response.status_code}")
                    else:
                        logger.warning(f"⚠️ Нет аудиопотоков в ответе Invidious")
                else:
                    logger.warning(f"⚠️ Invidious API error: {response.status_code}")

            except Exception as inst_error:
                logger.warning(f"⚠️ Invidious instance failed: {inst_error}")
                continue

        logger.warning("⚠️ Все Invidious инстансы не сработали")

    except Exception as e:
        logger.error(f"❌ Invidious download failed: {e}")

    # === ПОПЫТКА 2: yt-dlp (может требовать cookies) ===
    try:
        import yt_dlp

        output_template = os.path.join(TEMP_DIR, f"{sys_filename}.%(ext)s")

        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'max_filesize': 50 * 1024 * 1024,
        }

        logger.info(f"🔄 Пробуем yt-dlp...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = info.get('title', 'Audio Track')
            clean_title = title.replace('(Official Video)', '').replace('[Official Audio]', '').replace('(Lyrics)', '').strip()

            logger.info(f"✅ Скачано через yt-dlp: {clean_title}")
            return filename, clean_title

    except Exception as e:
        logger.error(f"❌ yt-dlp download failed: {e}")

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
