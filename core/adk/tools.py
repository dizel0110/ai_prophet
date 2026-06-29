import asyncio
import logging
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# MCP (Model Context Protocol) tool — connects to local MCP server via stdio
#
# Demonstrates MCP Server integration for the Kaggle capstone (6th concept).
# The MCP server runs as a subprocess and exposes tools over JSON-RPC.
# This wrapper makes those tools available to ADK agents as FunctionTool.
#
# Protocol flow:
#   1. ADK agent requests tool call
#   2. This wrapper calls ProphetMCPClient.call_tool()
#   3. Client sends JSON-RPC request to server via stdin
#   4. Server processes and returns result via stdout
#   5. Client passes result back to agent
# ---------------------------------------------------------------------------
async def _mcp_fetch_url(url: str) -> str:
    """Fetch web content via the MCP server for technique research.

    The MCP server runs fetch_url tool which makes HTTP requests
    and returns page text content. Used by Technique Expert to
    research massage modalities, verify contraindications, etc.

    Args:
        url: Full URL to fetch (http/https only)
    Returns:
        Page text content or error message
    """
    from core.mcp_client import mcp_client
    try:
        result = await mcp_client.call_tool("fetch_url", {"url": url})
        return result
    except Exception as e:
        return f"[MCP fetch_url error: {e}]"


async def _mcp_search_knowledge(query: str) -> str:
    """Search massage therapy knowledge base via the MCP server.

    The MCP server's search_massage_knowledge tool queries a curated
    knowledge base covering techniques, contraindications, anatomy,
    and treatment protocols.

    Args:
        query: Search query about massage techniques or conditions
    Returns:
        Knowledge base entries matching the query
    """
    from core.mcp_client import mcp_client
    try:
        result = await mcp_client.call_tool("search_massage_knowledge", {"query": query})
        return result
    except Exception as e:
        return f"[MCP search_massage_knowledge error: {e}]"


# Wrap MCP client calls as ADK FunctionTool instances
# These are passed to ADK agents via the tools= parameter
mcp_fetch_url_tool = FunctionTool(func=_mcp_fetch_url)
mcp_search_knowledge_tool = FunctionTool(func=_mcp_search_knowledge)


def _web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information about massage techniques, conditions, or contraindications.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default 5)

    Returns:
        Formatted search results as text
    """
    try:
        from core.tools import web_search as real_search
        return real_search(query, max_results)
    except Exception as e:
        logger.warning(f"Web search fallback (mock): {e}")
        return (
            f"Mock web search results for: {query}\n"
            f"1. Massage benefits for {query}\n"
            f"2. Contraindications for massage with {query}\n"
            f"3. Recommended techniques for {query}"
        )


def search_media(query: str, media_type: str = "audio", max_count: int = 5) -> str:
    """Search for music or video content suitable for massage sessions.

    Args:
        query: Genre or mood description (e.g. 'relaxing ambient massage music')
        media_type: Type of media ('audio' or 'video', default 'audio')
        max_count: Maximum number of results (default 5)

    Returns:
        List of found media with titles and URLs
    """
    try:
        from core.tools import search_media_content
        from core.agents.music_db import MASSAGE_MUSIC_GENRES
        genre_map = {
            "ambient": "ambient",
            "classical": "classical",
            "nature": "nature",
            "jazz": "jazz",
            "spa": "spa",
            "thai": "thai",
            "acoustic": "acoustic",
            "binaural": "binaural_beats",
        }
        genre_items = []
        for keyword, genre_key in genre_map.items():
            if keyword in query.lower():
                genre_data = MASSAGE_MUSIC_GENRES.get(genre_key, {})
                tracks = genre_data.get("tracks", [])
                for t in tracks[:3]:
                    genre_items.append(f"- {t.get('title', 'Track')}: {t.get('url', '#')}")
                break
        if genre_items:
            return "Found music:\n" + "\n".join(genre_items[:max_count])
        results = search_media_content(query, media_type, max_count)
        if results:
            return results
    except Exception as e:
        logger.warning(f"Media search fallback: {e}")

    return (
        f"Mock media results for '{query}':\n"
        f"1. Relaxing Spa Music (60 min) - https://youtube.com/watch?v=example1\n"
        f"2. Thai Massage Background - https://youtube.com/watch?v=example2\n"
        f"3. Deep Tissue Workout Mix - https://youtube.com/watch?v=example3"
    )


def _analyze_questionnaire(questionnaire_text: str) -> dict:
    """Analyze a massage client questionnaire for completeness and key indicators.

    Extracts and validates: age, gender, complaints, pain location, pain type,
    duration, chronic conditions, contraindications, vital signs.

    Args:
        questionnaire_text: Full text of the completed questionnaire

    Returns:
        Dict with analysis results including completeness score and key findings
    """
    import re
    completeness = 0
    indicators = []
    fields_found = []

    checks = {
        "возраст|лет|age": "age",
        "пол|gender|муж|жен|male|female": "gender",
        "жалоб|complaint|боль|pain|problem": "complaints",
        "лока|locat|где|where": "location",
        "тип|type|характер|nature": "pain_type",
        "длитель|duration|как долго|when": "duration",
        "хронич|chronic|заболев|disease|condition": "chronic",
        "аллерг|allerg": "allergies",
        "лекарств|medic|drug|medication": "medications",
        "давлен|pressure|blood|pressure|ад|АД": "blood_pressure",
        "температур|temp|temperature": "temperature",
        "противопоказан|contraind": "contraindications",
    }
    for pattern, field in checks.items():
        if re.search(pattern, questionnaire_text, re.IGNORECASE):
            fields_found.append(field)
            completeness += 1

    has_contraindications = re.search(
        r"(опухол|tumor|cancer|тромб|thromb|беремен|pregnant|"
        r"психическ|psych|туберкул|tuberc|ВИЧ|HIV|СПИД|AIDS|"
        r"gangrene|гангрен|аневризм|aneurysm)",
        questionnaire_text, re.IGNORECASE
    )
    contraindication_flag = has_contraindications is not None

    return {
        "completeness": min(100, int(completeness / len(checks) * 100)),
        "fields_found": fields_found,
        "has_red_flags": contraindication_flag,
        "summary": f"Found {len(fields_found)}/{len(checks)} key fields. "
                   f"{'⚠️ Contraindications detected' if contraindication_flag else '✅ No red flags detected'}",
    }


web_search_tool = FunctionTool(func=_web_search)
search_media_tool = FunctionTool(func=search_media)
question_analyzer_tool = FunctionTool(func=_analyze_questionnaire)

tools_list = [web_search_tool, search_media_tool, question_analyzer_tool]
