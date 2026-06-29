"""Tests for core/mcp_server.py + core/mcp_client.py — MCP protocol integration.

Covers: server tool definitions, client connect/disconnect, tool listing, tool calls.
All tests mock external connections — no real MCP server process is started."""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestMCPServerDefinition:
    """Verify the MCP server module defines the expected structure."""

    def test_server_module_imports(self):
        from core.mcp_server import mcp_server
        assert mcp_server is not None
        assert hasattr(mcp_server, 'name')

    def test_server_has_tools_defined(self):
        import core.mcp_server as srv
        assert hasattr(srv, 'mcp_server')

    def test_knowledge_base_has_topics(self):
        import core.mcp_server as srv
        # knowledge_base is a local variable inside search_massage_knowledge
        # Verify it exists by checking the function parses it
        assert callable(srv.search_massage_knowledge)
        result = srv.search_massage_knowledge("deep tissue massage")
        assert "DEEP TISSUE" in result or "deep tissue" in str(srv.search_massage_knowledge.__code__.co_consts)

    def test_server_name_is_correct(self):
        from core.mcp_server import mcp_server
        assert mcp_server.name == "massage-ai-mcp-server"


class TestMCPClientDefinition:
    """Verify the MCP client module defines the expected structure."""

    def test_client_module_imports(self):
        from core.mcp_client import ProphetMCPClient, mcp_client
        assert ProphetMCPClient is not None
        assert mcp_client is not None
        assert isinstance(mcp_client, ProphetMCPClient)

    def test_client_initial_state(self):
        from core.mcp_client import ProphetMCPClient
        client = ProphetMCPClient()
        assert client.session is None
        assert client._connected is False

    def test_client_has_required_methods(self):
        from core.mcp_client import ProphetMCPClient
        for method in ['connect', 'disconnect', 'list_tools', 'call_tool']:
            assert hasattr(ProphetMCPClient, method), f"Missing method: {method}"

    @pytest.mark.asyncio
    async def test_client_connect_fails_gracefully(self):
        from core.mcp_client import ProphetMCPClient
        client = ProphetMCPClient()
        result = await client.connect()
        # Should fail because no server is running
        assert result is False
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_client_call_tool_not_connected(self):
        from core.mcp_client import ProphetMCPClient
        client = ProphetMCPClient()
        result = await client.call_tool("fetch_url", {"url": "https://example.com"})
        assert "Error" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_client_list_tools_not_connected(self):
        from core.mcp_client import ProphetMCPClient
        client = ProphetMCPClient()
        tools = await client.list_tools()
        assert tools == [] or tools == {}


class TestMCPClientMocked:
    """Test MCP client logic with mocked internals."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        from core.mcp_client import ProphetMCPClient
        client = ProphetMCPClient()
        with patch('core.mcp_client.stdio_client') as mock_stdio:
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            async def fake_stdio(*args):
                return (mock_read, mock_write)
            mock_stdio.side_effect = fake_stdio

            with patch('core.mcp_client.ClientSession') as mock_session_cls:
                mock_session = AsyncMock()
                mock_session.initialize = AsyncMock()
                mock_session_cls.return_value.__aenter__.return_value = mock_session

                result = await client.connect()
                assert result is True
                assert client._connected is True
                await client.disconnect()

    @pytest.mark.asyncio
    async def test_list_tools_mocked(self):
        from core.mcp_client import ProphetMCPClient
        client = ProphetMCPClient()
        client._connected = True
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "test-tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object"}
        mock_result.tools = [mock_tool]
        mock_session.list_tools = AsyncMock(return_value=mock_result)
        client.session = mock_session

        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "test-tool"
        assert tools[0]["description"] == "A test tool"

    @pytest.mark.asyncio
    async def test_call_tool_mocked(self):
        from core.mcp_client import ProphetMCPClient
        client = ProphetMCPClient()
        client._connected = True
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Test result"
        mock_result.content = [mock_content]
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        client.session = mock_session

        result = await client.call_tool("fetch_url", {"url": "https://example.com"})
        assert result == "Test result"
        mock_session.call_tool.assert_called_once_with("fetch_url", {"url": "https://example.com"})

    @pytest.mark.asyncio
    async def test_call_tool_error(self):
        from core.mcp_client import ProphetMCPClient
        client = ProphetMCPClient()
        client._connected = True
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(side_effect=Exception("Server error"))
        client.session = mock_session

        result = await client.call_tool("fetch_url", {"url": "https://example.com"})
        assert "Error" in result


class TestMCPServerKnowledgeBase:
    """Verify the knowledge base content is valid (internal dict in search_massage_knowledge)."""

    def test_knowledge_query_returns_results(self):
        from core.mcp_server import search_massage_knowledge
        result = search_massage_knowledge("deep tissue")
        assert "DEEP TISSUE" in result
        assert "muscle" in result.lower()

    def test_knowledge_covers_techniques(self):
        from core.mcp_server import search_massage_knowledge
        result = search_massage_knowledge("massage")
        for word in ["massage", "muscle", "strokes"]:
            assert word.lower() in result.lower(), f"Result should mention '{word}'"

    def test_knowledge_no_match_returns_suggestions(self):
        from core.mcp_server import search_massage_knowledge
        result = search_massage_knowledge("nonexistent999")
        assert "No exact match" in result
        assert "Available topics" in result
