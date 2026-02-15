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

def create_music_playlist(genre: str, mood: str, count: int = 5):
    """Формирует музыкальный плейлист (заглушка для MCP)"""
    logger.info(f"🎵 Формирую плейлист: {genre}, настроение: {mood}, треков: {count}")
    
    # Генерируем фейковые треки для демонстрации
    tracks = []
    for i in range(1, count + 1):
        tracks.append(f"{i}. {genre} Track #{i} - {mood} Vibes")
    
    tracks_list = "\n".join(tracks)
    
    result = (
        f"🎵 *Плейлист '{genre} — {mood}'*\n\n"
        f"{tracks_list}\n\n"
        f"📊 Всего треков: {count}\n"
        f"🎧 Готов к воспроизведению!"
    )
    
    return result

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
            "name": "create_music_playlist",
            "description": "Создает музыкальный плейлист на основе жанра и настроения.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "genre": {"type": "STRING", "description": "Жанр музыки (например, Cyberpunk, Ambient)"},
                    "mood": {"type": "STRING", "description": "Настроение (например, Концентрация, Энергия)"}
                },
                "required": ["genre", "mood"]
            }
        }
    ]

AVAILABLE_FUNCTIONS = {
    "web_search": web_search,
    "create_music_playlist": create_music_playlist
}
