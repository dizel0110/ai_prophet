import logging
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

class ProphetMCPClient:
    """
    Базовый клиент для связи Пророка с инструментами через MCP.
    Позволяет ИИ вызывать внешние функции (музыка, файлы, поиск).
    """
    def __init__(self):
        self.sessions = {}

    async def connect_to_server(self, server_name: str, command: str, args: list = None):
        """
        Устанавливает соединение с локальным MCP сервером.
        """
        try:
            server_params = StdioServerParameters(
                command=command,
                args=args or [],
                env=None
            )
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self.sessions[server_name] = session
                    logger.info(f"✅ Подключено к MCP серверру: {server_name}")
                    return session
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к MCP {server_name}: {e}")
            return None

    async def list_tools(self, server_name: str):
        """Возвращает список доступных инструментов сервера."""
        session = self.sessions.get(server_name)
        if session:
            return await session.list_tools()
        return []

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        """Вызывает конкретный инструмент."""
        session = self.sessions.get(server_name)
        if session:
            return await session.call_tool(tool_name, arguments)
        return None

# Глобальный клиент Пророка
mcp_client = ProphetMCPClient()
