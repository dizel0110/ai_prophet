import logging
import requests
import os
import time
import random
import asyncio
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
    """Ищет видео на YouTube через yt-dlp 2026"""
    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'default_search': f'ytsearch{max_results}',
            'extract_flat': True,
            # TV Embedded клиент для обхода блокировок
            'extractor_args': {
                'youtube': {
                    'player_client': ['tv_embedded'],
                }
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            if res and 'entries' in res:
                results = []
                for entry in res['entries']:
                    if entry and entry.get('id'):
                        video_id = entry.get('id', '')
                        results.append({
                            'title': entry.get('title', 'Unknown'),
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'id': video_id,
                            'duration': entry.get('duration', 0),
                            'thumbnail': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                            'source': 'youtube'
                        })
                logger.info(f"✅ YouTube: найдено {len(results)} треков для '{query}'")
                return results
    except ImportError:
        logger.error("❌ yt-dlp не установлен")
    except Exception as e:
        logger.error(f"❌ YouTube Search Error: {e}")

    # Fallback: DuckDuckGo Video Search
    try:
        logger.info(f"🦆 Пробуем DDG Video Search для: {query}")
        with DDGS() as ddgs:
            results = list(ddgs.videos(query, max_results=max_results))
            normalized = []
            for r in results:
                url = r.get('watchUrl') or r.get('content', '')
                if 'youtube.com' in url or 'youtu.be' in url:
                    video_id = ""
                    if "v=" in url:
                        video_id = url.split("v=")[1].split("&")[0]
                    elif "youtu.be/" in url:
                        video_id = url.split("youtu.be/")[-1].split("?")[0]
                    
                    normalized.append({
                        'title': r.get('title', 'Unknown'),
                        'url': url,
                        'id': video_id,
                        'duration': 0,
                        'thumbnail': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else "",
                        'source': 'duckduckgo'
                    })
            if normalized:
                logger.info(f"✅ DDG: найдено {len(normalized)} треков")
                return normalized
    except Exception as e:
        logger.error(f"❌ DDG Video Search Error: {e}")

    return []

def search_jamendo(query: str, max_results: int = 5):
    """
    Поиск бесплатной музыки на Jamendo (API v3.0).
    
    Jamendo — лицензионно чистая музыка от независимых артистов.
    API: https://api.jamendo.com/v3.0/
    
    Args:
        query: Поисковый запрос
        max_results: Максимум результатов
    
    Returns:
        List[dict]: [{title, url, duration, thumbnail, source}, ...]
    """
    try:
        # Бесплатный API ключ (публичный для open-source проектов)
        client_id = "b2c62f47"  # Jamendo public key
        url = "https://api.jamendo.com/v3.0/tracks/"
        params = {
            "client_id": client_id,
            "search": query,
            "limit": max_results,
            "audioformat": "mp32",  # MP3 128 kbps
            "include": "musicinfo"
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for track in data.get("results", []):
                results.append({
                    "title": track.get("name", "Unknown"),
                    "url": track.get("audio", ""),
                    "duration": track.get("duration", 0),
                    "thumbnail": track.get("image", ""),
                    "source": "jamendo",
                    "audioformat": "mp32"
                })
            
            logger.info(f"🎵 Jamendo: найдено {len(results)} треков для '{query}'")
            return results[:max_results]
    
    except Exception as e:
        logger.error(f"❌ Jamendo Search Error: {e}")
    
    return []


def search_internet_archive(query: str, max_results: int = 5):
    """
    Поиск аудио в Internet Archive.
    
    Internet Archive — огромная библиотека свободного контента.
    API: https://archive.org/help/advanced_search.php
    
    Args:
        query: Поисковый запрос
        max_results: Максимум результатов
    
    Returns:
        List[dict]: [{title, url, duration, thumbnail, source}, ...]
    """
    try:
        url = "https://archive.org/advancedsearch.php"
        params = {
            "q": f"(mediatype:audio OR collection:etree) AND ({query})",
            "fl[]": ["identifier", "title", "creator", "duration"],
            "rows": max_results,
            "page": 1,
            "output": "json",
            "sort[]": ["downloads desc"]
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for doc in data.get("response", {}).get("docs", []):
                identifier = doc.get("identifier", "")
                results.append({
                    "title": doc.get("title", "Unknown"),
                    "url": f"https://archive.org/download/{identifier}",
                    "duration": int(float(doc.get("duration", 0))) if doc.get("duration") else 0,
                    "thumbnail": "",
                    "source": "internet_archive",
                    "creator": doc.get("creator", "")
                })
            
            logger.info(f"🏛️ Internet Archive: найдено {len(results)} треков для '{query}'")
            return results[:max_results]
    
    except Exception as e:
        logger.error(f"❌ Internet Archive Search Error: {e}")
    
    return []


def search_soundcloud(query: str, max_results: int = 5):
    """
    Ищет треки на SoundCloud через yt-dlp (scsearch:).
    
    SoundCloud официально поддерживается в yt-dlp:
    - soundcloud:search (scsearch: префикс)
    - Меньше блокируется, чем YouTube
    - Прямые аудиопотоки
    
    Args:
        query: Поисковый запрос
        max_results: Максимум результатов
    
    Returns:
        List[dict]: [{title, url, duration, thumbnail, source}, ...]
    """
    try:
        import yt_dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'extract_flat': True,  # Быстрый поиск без деталей
        }

        # scsearch: — официальный префикс для поиска SoundCloud
        search_query = f"scsearch{max_results}:{query}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(search_query, download=False)
            
            if res and 'entries' in res:
                entries = []
                for e in res['entries']:
                    if e and e.get('url'):
                        entries.append({
                            'title': e.get('title', 'Unknown'),
                            'url': e.get('url', ''),
                            'duration': e.get('duration', 0),
                            'thumbnail': e.get('thumbnail', ''),
                            'source': 'soundcloud',
                            'extractor': e.get('extractor', 'soundcloud')
                        })
                
                logger.info(f"🎵 SoundCloud: найдено {len(entries)} треков для '{query}'")
                return entries[:max_results]
                
    except Exception as e:
        logger.error(f"❌ SoundCloud Search Error: {e}")
    
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
                    auto_count = min(count, 15)
                    speed_label = "⚡ быстро"
                elif duration <= 1800 and size <= 50:
                    # Баланс
                    auto_count = min(count, 10)
                    speed_label = "⚖️ нормально"
                else:
                    # Максимум — меньше результатов (долгая загрузка)
                    auto_count = min(count, 5)
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
        queries = [
            f"{query} {media_type}",
            f"{query} lyrics",
            f"Best {query} songs",
        ]
    else:
        queries = [
            f"{query} official video",
            f"{query} music video",
            f"{query} hd",
        ]

    # Если просили 1 трек, берем самый точный запрос
    if count == 1:
        queries = [queries[0]]
    else:
        queries = random.sample(queries, min(2, len(queries)))

    # 2. ГИБРИДНЫЙ ПОИСК — все источники параллельно (максимальная надёжность)
    logger.info(f"🔄 Запуск гибридного поиска ({count} треков)...")
    
    # SoundCloud — приоритет для аудио
    if media_type == 'audio':
        try:
            logger.info(f"🎵 SoundCloud: поиск для '{query}'...")
            sc_results = search_soundcloud(query, max_results=count)
            all_videos.extend(sc_results)
            logger.info(f"✅ SoundCloud: {len(sc_results)}/{count} треков")
        except Exception as e:
            logger.error(f"❌ SoundCloud поиск прерван: {e}")
    
    # Jamendo — лицензионно чистая музыка
    if media_type == 'audio' and len(all_videos) < count:
        try:
            logger.info(f"🎸 Jamendo: поиск для '{query}'...")
            jam_results = search_jamendo(query, max_results=count - len(all_videos))
            all_videos.extend(jam_results)
            logger.info(f"✅ Jamendo: {len(jam_results)} треков")
        except Exception as e:
            logger.error(f"❌ Jamendo поиск прерван: {e}")
    
    # Internet Archive — свободный контент
    if media_type == 'audio' and len(all_videos) < count:
        try:
            logger.info(f"🏛️ Internet Archive: поиск для '{query}'...")
            ia_results = search_internet_archive(query, max_results=count - len(all_videos))
            all_videos.extend(ia_results)
            logger.info(f"✅ Internet Archive: {len(ia_results)} треков")
        except Exception as e:
            logger.error(f"❌ Internet Archive поиск прерван: {e}")
    
    # YouTube — если ещё мало
    if len(all_videos) < count:
        try:
            logger.info(f"📺 YouTube: поиск для '{query}' ({count - len(all_videos)} треков)...")
            yt_results = search_youtube_videos(query, max_results=count - len(all_videos))
            all_videos.extend(yt_results)
            logger.info(f"✅ YouTube: {len(yt_results)} треков")
        except Exception as e:
            logger.error(f"❌ YouTube поиск прерван: {e}")
    
    # DuckDuckGo — fallback
    if len(all_videos) < count:
        try:
            logger.info(f"🦆 DuckDuckGo: fallback поиск для '{query}'...")
            for q in queries:
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.videos(q, max_results=count - len(all_videos)))
                        if results:
                            all_videos.extend(results)
                            break
                except Exception as e:
                    logger.error(f"❌ DDG Video Search Error for '{q}': {e}")
        except Exception as e:
            logger.error(f"❌ DuckDuckGo поиск прерван: {e}")
    
    logger.info(f"📊 Всего найдено: {len(all_videos)} треков")

    # 3. Дедупликация
    unique_videos = {}
    for v in all_videos:
        # Пытаемся взять URL из разных возможных полей
        url = v.get('url') or v.get('content') or v.get('click_url')
        if url:
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
        url = video.get('url') or video.get('content') or video.get('click_url')
        
        if not url:
            continue

        # Пытаемся извлечь duration из URL или ставим 0
        duration = 0
        thumbnail = ""
        
        # Извлекаем video_id для thumbnail ТОЛЬКО для YouTube
        url_str = str(url)
        if 'youtu' in url_str:
            parsed = urlparse(url_str)
            video_id = parse_qs(parsed.query).get('v', [None])[0]
            if not video_id:
                # Пробуем из короткой ссылки youtu.be
                video_id = str(parsed.path).strip('/')
            
            if video_id and len(video_id) < 15: # Типичный ID YouTube ~11 символов
                thumbnail = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

        tracks.append({
            "title": title,
            "url": url_str,
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
    import asyncio
    import random
    import time
    from aiogram.types import FSInputFile
    
    result = {
        "sent": 0,
        "failed": 0,
        "tracks": []
    }
    
    total = len(tracks)
    total_duration = 0
    total_size = 0
    
    for i, track in enumerate(tracks, 1):
        if not isinstance(track, dict):
            result["failed"] += 1
            continue

        if track.get("is_fallback"):
            result["failed"] += 1
            continue
        
        # Колбек для прогресса конкретного трека
        last_update = 0
        async def progress_update(percent, speed, eta):
            nonlocal last_update
            now = time.time()
            if status_msg and now - last_update > 1.5: # Не чаще раза в 1.5 сек
                last_update = now
                try:
                    bar_len = 10
                    filled = int(float(percent.strip('%')) / 100 * bar_len)
                    bar = "⏳ " + "▓" * filled + "░" * (bar_len - filled)
                    await status_msg.edit_text(
                        f"📥 *Загрузка плейлиста ({i}/{total})*\n"
                        f"🎵 {track['title']}\n"
                        f"{bar} {percent}\n"
                        f"🚀 {speed} | 🏁 {eta}",
                        parse_mode="Markdown"
                    )
                except: pass
            return True

        try:
            # Скачиваем в отдельном потоке, чтобы не блокировать цикл событий
            file_path, title, duration = await asyncio.to_thread(
                download_audio,
                track['url'], 
                chat_id=chat_id_str,
                title_hint=track.get('title'),
                progress_callback=lambda p, s, t: asyncio.run_coroutine_threadsafe(progress_update(p, s, t), asyncio.get_event_loop())
            )
            
            if file_path and os.path.exists(file_path):
                # Считаем размер
                size = os.path.getsize(file_path)
                total_size += size
                total_duration += (duration or 0)
                
                audio_file = FSInputFile(file_path)
                
                await bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    title=title or track['title'],
                    performer="AI Prophet",
                    caption=f"🎧 {track['title']}"
                )
                
                os.remove(file_path)
                result["sent"] += 1
                result["tracks"].append(track)
            else:
                result["failed"] += 1
        except Exception as e:
            logger.error(f"❌ Ошибка трека {track.get('title')}: {e}")
            result["failed"] += 1

    # Финальный аккорд
    if status_msg:
        # Форматирование длительности
        if total_duration < 60:
            dur_text = f"{total_duration} сек"
        elif total_duration < 3600:
            dur_text = f"{total_duration // 60} мин {total_duration % 60} сек"
        else:
            dur_text = f"{total_duration // 3600} ч {(total_duration % 3600) // 60} мин"

        # Форматирование размера
        size_mb = total_size / (1024 * 1024)
        if size_mb < 1:
            size_text = f"{total_size / 1024:.1f} KB"
        else:
            size_text = f"{size_mb:.1f} MB"

        aura = random.choice([
            "Мощная энергия", "Меланхоличный вайб", "Чистый драйв", 
            "Космическое спокойствие", "Ностальгия", "Мистический поток",
            "Гармония сфер", "Голос бездны", "Свет предков"
        ])
        
        summary_text = (
            f"✅ *Ритуал завершен!*\n\n"
            f"📦 Отправлено: `{result['sent']}` из `{total}` треков\n"
            f"⏱ Общая длительность: `{dur_text}`\n"
            f"💾 Общий вес: `{size_text}`\n"
            f"✨ Аура подборки: *{aura}*\n\n"
            "_Наслаждайся звуком, путник._"
        )
        try: await status_msg.edit_text(summary_text, parse_mode="Markdown")
        except: await bot.send_message(chat_id, summary_text, parse_mode="Markdown")
    
    return result

def download_audio(url: str, chat_id: str = None, title_hint: str = None, max_duration_sec: int = None, max_filesize_mb: int = None, progress_callback=None):
    """
    Скачивает аудио с поддержкой callback-функции для отслеживания прогресса.
    """
    import os
    import yt_dlp
    import time
    import json
    from config import TEMP_DIR

    def yt_dlp_hook(d):
        if progress_callback and d['status'] == 'downloading':
            try:
                # Извлекаем данные для индикатора
                p = d.get('_percent_str', '0%').replace(' ', '')
                s = d.get('_speed_str', '0KB/s')
                t = d.get('_eta_str', '00:00')
                
                # Если callback вернул False - прерываем
                if progress_callback(p, s, t) is False:
                    raise Exception("USER_CANCEL")
            except Exception as e:
                if str(e) == "USER_CANCEL": raise e
                pass

    # ... (загрузка лимитов и подготовка путей остается прежней)

    if not url:
        logger.error("❌ download_audio: пустой URL")
        return None, None, None

    # Загрузка лимитов
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
        except Exception as e:
            logger.warning(f"⚠️ Failed to load user limits: {e}")

    if max_duration_sec is None:
        max_duration_sec = 1800
    if max_filesize_mb is None:
        max_filesize_mb = 100

    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    import uuid
    import re
    import glob
    
    # Очистка названия для имени файла
    safe_title = "audio"
    if title_hint:
        safe_title = re.sub(r'[^\w\-_\. ]', '_', title_hint)[:50].strip()
    
    # --- КЭШ ПРОВЕРКА: Если файл уже есть в temp ---
    existing_files = glob.glob(os.path.join(TEMP_DIR, f"{safe_title}_*.mp3"))
    if existing_files:
        # Нашли похожий файл, берем самый свежий
        latest_file = max(existing_files, key=os.path.getmtime)
        logger.info(f"♻️ Использую существующий файл из кэша: {latest_file}")
        return latest_file, title_hint or "Cached Track", 0
        
    sys_filename = f"{safe_title}_{uuid.uuid4().hex[:4]}"
    output_template = os.path.join(TEMP_DIR, f"{sys_filename}.%(ext)s")

    # Определяем источник
    is_soundcloud = 'soundcloud.com' in url
    is_jamendo = 'jamendo.com' in url
    is_archive = 'archive.org' in url
    is_youtube = 'youtube.com' in url or 'youtu.be' in url

    source_name = "SoundCloud" if is_soundcloud else "Jamendo" if is_jamendo else "Internet Archive" if is_archive else "YouTube" if is_youtube else "Unknown"

    start_time = time.time()
    logger.info(f"⬇️ Скачиваю аудио: {url} ({source_name})")

    import shutil
    has_ffmpeg = shutil.which('ffmpeg') is not None or shutil.which('ffprobe') is not None

    # === yt-dlp 2026: оптимальные настройки ===
    ydl_opts = {
        'format': 'bestaudio/best', # Пытаемся взять лучшее аудио
        'outtmpl': output_template,
        'nopart': True,
        'nopaylist': True,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': max_filesize_mb * 1024 * 1024,
        'fixup': 'warn', 
        'socket_timeout': 30,
        'retries': 5,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'progress_hooks': [yt_dlp_hook],
    }

    if has_ffmpeg:
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    
    if is_youtube:
        # Улучшенная совместимость для YouTube 2026
        ydl_opts['extractor_args'] = {'youtube': {'player_client': ['web', 'ios', 'tv_embedded']}}
        # Если аудио формата нет, берем любое и ffmpeg сам достанет звук
        ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Сначала извлекаем инфо
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Audio Track')
            duration = info.get('duration', 0)
            
            # Проверяем все возможные расширения, которые мог создать yt-dlp
            # (особенно если ffmpeg не сработал)
            for ext in ['mp3', 'm4a', 'webm', 'opus', 'aac', 'ogg']:
                test_path = output_template.replace('.%(ext)s', f'.{ext}')
                if os.path.exists(test_path):
                    clean_title = title.split('(')[0].split('[')[0].strip()
                    logger.info(f"✅ Успешно скачано: {test_path}")
                    return test_path, clean_title, duration

    except Exception as e:
        logger.warning(f"⚠️ Ошибка при загрузке (но проверяем файлы): {e}")
        # РЕЖИМ СПАСЕНИЯ: Если файл на диске есть, отдаем его даже при ошибке пост-процессинга
        for ext in ['mp3', 'm4a', 'webm', 'opus', 'aac', 'ogg']:
            test_path = output_template.replace('.%(ext)s', f'.{ext}')
            if os.path.exists(test_path):
                logger.info(f"🆘 Файл найден после ошибки: {test_path}")
                return test_path, "Скачанный трек", 0

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
