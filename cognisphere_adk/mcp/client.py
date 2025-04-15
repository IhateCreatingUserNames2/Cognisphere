# cognisphere_adk/mcp/client.py
from typing import Any, Dict, List, Optional
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


class MCPClient:
    """
    A comprehensive MCP (Model Context Protocol) Client for interacting with MCP servers
    """

    def __init__(
            self,
            server_command: str,
            server_args: List[str] = None,
            env: Optional[Dict[str, str]] = None
    ):
        """
        Initialize an MCP Client

        Args:
            server_command: Command to launch the MCP server
            server_args: Optional arguments for the server
            env: Optional environment variables
        """
        self.server_params = StdioServerParameters(
            command=server_command,
            args=server_args or [],
            env=env
        )

        # Placeholders for session and connection
        self._session = None
        self._read_stream = None
        self._write_stream = None

    async def connect(self, sampling_callback: Optional[callable] = None):
        """
        Establish a connection to the MCP server

        Args:
            sampling_callback: Optional callback for message sampling
        """
        # Open stdio client connection
        self._read_stream, self._write_stream = await stdio_client(self.server_params).__aenter__()

        # Create client session
        self._session = await ClientSession(
            self._read_stream,
            self._write_stream,
            sampling_callback=sampling_callback
        ).__aenter__()

        # Initialize the connection
        await self._session.initialize()

    async def list_resources(self) -> List[types.Resource]:
        """
        List available resources in the MCP server

        Returns:
            List of available resources
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first.")

        return await self._session.list_resources()

    async def list_tools(self) -> List[types.Tool]:
        """
        List available tools in the MCP server

        Returns:
            List of available tools
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first.")

        return await self._session.list_tools()

    async def list_prompts(self) -> List[types.Prompt]:
        """
        List available prompts in the MCP server

        Returns:
            List of available prompts
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first.")

        return await self._session.list_prompts()

    async def read_resource(self, resource_uri: str) -> tuple:
        """
        Read a specific resource from the MCP server

        Args:
            resource_uri: URI of the resource to read

        Returns:
            Tuple of (content, mime_type)
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first.")

        return await self._session.read_resource(resource_uri)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a specific tool in the MCP server

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments for the tool

        Returns:
            Result of the tool call
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first.")

        return await self._session.call_tool(tool_name, arguments)

    async def get_prompt(self, prompt_name: str, arguments: Optional[Dict[str, str]] = None) -> types.GetPromptResult:
        """
        Retrieve a specific prompt from the MCP server

        Args:
            prompt_name: Name of the prompt
            arguments: Optional arguments for the prompt

        Returns:
            Prompt result
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first.")

        return await self._session.get_prompt(prompt_name, arguments)

    async def close(self):
        """
        Close the connection to the MCP server
        """
        if self._session:
            await self._session.__aexit__(None, None, None)

        if self._read_stream and self._write_stream:
            await self._read_stream.close()
            await self._write_stream.close()

    # Context manager support
    async def __aenter__(self):
        """Support async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support async context manager exit"""
        await self.close()


# Example usage
async def example_mcp_client_usage():
    """
    Demonstrate MCP Client usage
    """
    # Example of connecting to a hypothetical MCP server
    async with MCPClient(
            server_command="python",
            server_args=["example_mcp_server.py"]
    ) as client:
        # List available resources
        resources = await client.list_resources()
        print("Available Resources:", resources)

        # List available tools
        tools = await client.list_tools()
        print("Available Tools:", tools)

        # Read a specific resource
        try:
            content, mime_type = await client.read_resource("config://app")
            print("Resource Content:", content)
        except Exception as e:
            print("Error reading resource:", e)

        # Call a tool
        try:
            result = await client.call_tool("calculate_bmi", {
                "weight_kg": 70,
                "height_m": 1.75
            })
            print("BMI Calculation Result:", result)
        except Exception as e:
            print("Error calling tool:", e)


# Optional: Run the example if this script is executed directly
if __name__ == "__main__":
    import asyncio

    asyncio.run(example_mcp_client_usage())