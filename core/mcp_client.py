"""
MCP (Model Context Protocol) client for the massage AI system.

Connects to the local MCP server (core/mcp_server.py) via stdio transport
and exposes its tools to the ADK agent system.

This demonstrates the MCP protocol pattern:
1. MCP server runs as subprocess
2. Client connects via stdio JSON-RPC transport
3. Tool discovery (list_tools) and invocation (call_tool) use MCP protocol

For the Kaggle capstone, this shows MCP Server integration as an ADK tool.
"""
import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class ProphetMCPClient:
    """
    MCP client that connects to the massage AI server via stdio transport.

    Launches the server as a subprocess and communicates using the
    Model Context Protocol (JSON-RPC over stdio).
    """

    def __init__(self):
        self.session: ClientSession | None = None
        self._process: subprocess.Popen | None = None
        self._connected = False

    async def connect(self) -> bool:
        """
        Start the MCP server subprocess and establish a session.

        The server (core/mcp_server.py) is started as a child process.
        Communication uses MCP's stdio transport — the client writes
        JSON-RPC requests to the server's stdin and reads responses from stdout.

        Returns:
            True if connection succeeded, False otherwise
        """
        if self._connected:
            return True

        try:
            # Locate the server script relative to this file
            server_path = Path(__file__).parent / "mcp_server.py"
            if not server_path.exists():
                logger.error(f"MCP server not found at {server_path}")
                return False

            # Configure stdio transport parameters
            # The server process communicates via stdin/stdout
            server_params = StdioServerParameters(
                command=sys.executable,  # same Python interpreter
                args=[str(server_path)],
                env=None,  # inherit parent environment
            )

            # Open stdio connection and initialize MCP session
            # stdio_client returns (read_stream, write_stream)
            read, write = await stdio_client(server_params)

            # Create MCP client session over the streams
            # This handles the JSON-RPC message framing
            self.session = await ClientSession(read, write).__aenter__()
            await self.session.initialize()

            self._connected = True
            logger.info("MCP server connected successfully")
            return True

        except Exception as e:
            logger.error(f"MCP server connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Close the MCP session and stop the server process."""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception:
                pass
            self.session = None
        self._connected = False
        logger.info("MCP server disconnected")

    async def list_tools(self) -> list[dict]:
        """
        List all tools exposed by the MCP server.

        Uses MCP's tools/list method to discover available tools.
        Each tool has a name, description, and input schema.

        Returns:
            List of tool descriptors (name, description, inputSchema)
        """
        if not self._connected:
            await self.connect()
        if not self.session:
            return []

        try:
            result = await self.session.list_tools()
            tools = []
            for tool in result.tools:
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                })
            return tools
        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """
        Call a tool on the MCP server.

        Uses MCP's tools/call method to invoke the tool with the given args.
        The server processes the request and returns text content.

        Args:
            tool_name: Name of the tool to call (e.g., 'fetch_url', 'search_massage_knowledge')
            arguments: Dict of arguments matching the tool's input schema
        Returns:
            Text result from the tool
        """
        if not self._connected:
            ok = await self.connect()
            if not ok:
                return f"[MCP Error: Could not connect to server]"

        try:
            result = await self.session.call_tool(tool_name, arguments)
            if result and result.content:
                # Extract text from MCP content items
                texts = []
                for item in result.content:
                    if hasattr(item, 'text'):
                        texts.append(item.text)
                return "\n".join(texts) if texts else f"[MCP: Tool '{tool_name}' returned no text]"
            return f"[MCP: Tool '{tool_name}' returned empty result]"
        except Exception as e:
            logger.error(f"MCP call_tool({tool_name}) failed: {e}")
            return f"[MCP Error calling {tool_name}: {e}]"


# Singleton client instance — shared across the application
mcp_client = ProphetMCPClient()
