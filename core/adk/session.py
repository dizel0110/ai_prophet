import logging
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService

logger = logging.getLogger(__name__)

_session_service = None
_memory_service = None


def get_session_service() -> InMemorySessionService:
    global _session_service
    if _session_service is None:
        _session_service = InMemorySessionService()
        logger.info("InMemorySessionService created")
    return _session_service


def get_memory_service() -> InMemoryMemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = InMemoryMemoryService()
        logger.info("InMemoryMemoryService created")
    return _memory_service


def create_session(chat_id: int, session_name: str = "massage_consultation") -> str:
    """Create a new session synchronously.

    Args:
        chat_id: Telegram chat ID
        session_name: Name for the session

    Returns:
        Session ID string
    """
    svc = get_session_service()
    session = svc.create_session_sync(
        app_name="ai_prophet",
        user_id=str(chat_id),
        session_id=f"{chat_id}_{session_name}",
    )
    return session.id
