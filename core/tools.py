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
