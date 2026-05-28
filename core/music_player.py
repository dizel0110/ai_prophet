import logging
import requests
import json
import os
import time
from typing import List, Optional

logger = logging.getLogger(__name__)

GENRES = {
    "ambient": {"name": "Ambient", "icon": "🌿", "query": "ambient relaxation massage music"},
    "classic": {"name": "Классика", "icon": "🎹", "query": "classical piano relaxation massage music"},
    "nature": {"name": "Природа", "icon": "🌊", "query": "nature sounds water forest relaxation massage"},
    "jazz": {"name": "Jazz", "icon": "🎷", "query": "smooth jazz relaxation massage music"},
    "spa": {"name": "Спа", "icon": "💆", "query": "spa relaxation meditation massage music"},
    "thai": {"name": "Тайский", "icon": "🧘", "query": "thai massage relaxation traditional music"},
    "acoustic": {"name": "Акустика", "icon": "🎸", "query": "acoustic guitar instrumental relaxation massage music"},
    "binaural": {"name": "Бины", "icon": "🧘", "query": "binaural beats relaxation meditation alpha waves"},
}

CACHE_FILE = os.path.join("temp", "music_cache.json")
CACHE_TTL = 3600  # 1 hour


def _load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(data: dict):
    os.makedirs("temp", exist_ok=True)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save music cache: {e}")


def _parse_duration(val) -> int:
    """Parse duration from various formats (seconds int, 'MM:SS', 'HH:MM:SS') to seconds."""
    if not val:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        val = val.strip()
        # Try MM:SS or HH:MM:SS
        parts = val.split(":")
        if len(parts) == 2:
            try:
                return int(parts[0]) * 60 + int(parts[1])
            except ValueError:
                return 0
        elif len(parts) == 3:
            try:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except ValueError:
                return 0
        # Try plain number
        try:
            return int(float(val))
        except ValueError:
            return 0
    return 0


def _clean_title(name: str, item_title: str) -> str:
    """Clean track title: remove number prefixes, UUIDs, file extensions."""
    name = name.replace(".mp3", "").strip()
    import re
    # Remove leading UUID patterns (8-4-4-4-12, 4-4-4-12, or plain 32-hex)
    name = re.sub(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\.?[\s-]*", "", name)
    name = re.sub(r"^[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\.?[\s-]*", "", name)
    name = re.sub(r"^[0-9a-fA-F]{32}\.?[\s-]*", "", name)
    # Remove leading number prefixes like "01-", "02_", "01 ", "1."
    name = re.sub(r"^\d+[-_\.\s/]+", "", name)
    # Remove leading year prefixes like "2022-"
    name = re.sub(r"^20\d{2}[-_\.\s]+", "", name)
    # Remove leading artist prefix pattern "1234567-Artist Name-Track Title" → "Track Title"
    name = re.sub(r"^\d+-[\w\s]*-", "", name)
    # Remove trailing pointless suffixes like "⎪" or "|" and everything after
    name = re.sub(r"\s*[⎪│|].*$", "", name)
    # Replace underscores with spaces
    name = name.replace("_", " ").replace("/", " - ").strip()
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name)
    # If result is just hex/dashes (UUID leftovers), use item title
    if re.match(r"^[0-9a-fA-F-]{10,}$", name.replace(" ", "")):
        return item_title
    if len(name) < 5 and " " not in name:
        return item_title
    if len(name) < 3:
        return item_title
    # Capitalize first letter
    name = name[0].upper() + name[1:] if name else item_title
    return name.strip()


def _search_ia(query: str, max_items: int = 5) -> List[dict]:
    """Search Internet Archive for items matching the query, return list of tracks with direct MP3 URLs."""
    try:
        r = requests.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": f"mediatype:audio AND ({query}) AND (format:VBR MP3 OR format:128kbps MP3 OR format:64kbps MP3 OR format:MP3)",
                "fl[]": ["identifier", "title", "creator", "downloads"],
                "rows": max_items,
                "page": 1,
                "output": "json",
                "sort[]": ["downloads desc"],
            },
            timeout=30,
        )
        if r.status_code != 200:
            logger.warning(f"IA search error: {r.status_code}")
            return []

        docs = r.json().get("response", {}).get("docs", [])
        tracks = []
        for doc in docs:
            ident = doc.get("identifier", "")
            if not ident:
                continue
            item_tracks = _get_item_tracks(ident, doc.get("title", "Unknown"), doc.get("creator", ""))
            tracks.extend(item_tracks)

        logger.info(f"Found {len(tracks)} playable tracks from IA for '{query}'")
        # Filter out very long tracks (> 3600s = 1hr, these are usually full albums)
        tracks = [t for t in tracks if t["duration"] < 3600 or t["duration"] == 0]
        return tracks[:15]  # max 15 tracks total
    except Exception as e:
        logger.warning(f"IA search error: {e}")
        return []


def _get_item_tracks(identifier: str, item_title: str, creator: str) -> List[dict]:
    """Fetch metadata for a single IA item and return its MP3 files as track dicts."""
    try:
        r = requests.get(f"https://archive.org/metadata/{identifier}", timeout=10)
        if r.status_code != 200:
            return []

        data = r.json()
        files = data.get("files", [])
        mp3_files = [
            f for f in files
            if f.get("name", "").endswith(".mp3") and f.get("format") in ("VBR MP3", "128kbps MP3", "64kbps MP3", "MP3")
        ]

        tracks = []
        for f in mp3_files:
            name = f.get("name", "")
            title = _clean_title(name, item_title)
            duration = _parse_duration(f.get("length"))

            tracks.append({
                "title": title,
                "artist": creator or item_title,
                "url": f"https://archive.org/download/{identifier}/{name}",
                "duration": duration,
                "source": "internet_archive",
                "item": item_title,
            })
        return tracks
    except Exception as e:
        logger.warning(f"IA item metadata error for {identifier}: {e}")
        return []


def get_tracks(genre: str, chat_id: int = 0) -> List[dict]:
    """
    Get playable tracks for a genre.
    Returns list of {title, artist, url, duration, source, item}.
    """
    genre_info = GENRES.get(genre)
    if not genre_info:
        return []

    cache = _load_cache()
    cache_key = f"genre_{genre}"
    cached = cache.get(cache_key)
    if cached and time.time() - cached.get("ts", 0) < CACHE_TTL:
        logger.info(f"Using cached tracks for '{genre}' ({len(cached.get('tracks', []))} tracks)")
        return cached.get("tracks", [])

    tracks = _search_ia(genre_info["query"])

    # If IA returns nothing, try broader search
    if not tracks:
        broad_query = genre_info["query"].split("massage")[0].strip()
        tracks = _search_ia(broad_query, max_items=3)

    # If still nothing, try even broader
    if not tracks and genre in ("jazz", "acoustic"):
        fallback = {
            "jazz": "jazz instrumental",
            "acoustic": "acoustic guitar instrumental",
        }.get(genre, "")
        if fallback:
            tracks = _search_ia(fallback, max_items=3)

    # Cache results
    cache[cache_key] = {"ts": time.time(), "tracks": tracks}
    _save_cache(cache)

    return tracks


def search_tracks(query: str, max_results: int = 15) -> List[dict]:
    """
    Search for tracks by arbitrary text query (not limited to massage genres).
    Uses Internet Archive.
    """
    import re
    clean = re.sub(r'[<>:"/\\|?*]', ' ', query).strip()
    if not clean:
        return []

    cache = _load_cache()
    cache_key = f"search_{clean.lower()[:50]}"
    cached = cache.get(cache_key)
    if cached and time.time() - cached.get("ts", 0) < CACHE_TTL:
        return cached.get("tracks", [])

    tracks = _search_ia(clean, max_items=min(max_results, 8))
    tracks = tracks[:max_results]

    cache[cache_key] = {"ts": time.time(), "tracks": tracks}
    _save_cache(cache)

    return tracks


def ai_search_tracks(query: str) -> List[dict]:
    """
    Use AI to interpret a free-text music request and find matching tracks.
    Uses HF Router (no Gemini quota consumed) to generate search queries,
    then searches IA for each.
    """
    import re
    clean = re.sub(r'[<>:"/\\|?*]', ' ', query).strip()
    if not clean:
        return []

    # Try AI interpretation
    try:
        from core.ai_engine import get_hf_response
        ai_prompt = (
            f"Пользователь хочет найти музыку. Его запрос: \"{clean}\"\n\n"
            f"Напиши 3-5 поисковых запросов на английском для поиска на Internet Archive.\n"
            f"Каждый запрос с новой строки. Без номеров, без пояснений, только запросы.\n"
            f"Пример: ambient relaxation ocean sounds\n"
            f"Пример: rock guitar instrumental energetic"
        )
        ai_result = get_hf_response(ai_prompt)
        if ai_result:
            lines = [l.strip() for l in ai_result.split('\n') if l.strip() and len(l.strip()) > 5]
            queries = lines[:5]
        else:
            queries = [clean]
    except Exception as e:
        logger.warning(f"AI music search error: {e}")
        queries = [clean]

    # Fallback: just use the cleaned query
    if not queries:
        queries = [clean]

    # Search IA for each query, deduplicate
    seen_urls = set()
    all_tracks = []
    for q in queries:
        tracks = _search_ia(q, max_items=3)
        for t in tracks:
            url = t.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_tracks.append(t)

    return all_tracks[:20]


def get_tracks_duration(tracks: List[dict]) -> int:
    """Return total duration in seconds for a list of tracks."""
    return sum(t.get("duration", 0) or 0 for t in tracks)


def get_all_genres() -> dict:
    """Return all genre definitions (without tracks)."""
    return {k: {"name": v["name"], "icon": v["icon"]} for k, v in GENRES.items()}
