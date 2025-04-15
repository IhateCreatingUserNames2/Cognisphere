# cognisphere_adk/agents/mcp_agent.py
from google.adk.agents import Agent
from google.adk.tools import BaseTool, FunctionTool
from google.adk.tools.tool_context import ToolContext
from typing import Dict, Any, List, Optional, Type
import asyncio
import os
import json
import importlib
import sys

from ..mcp.client import MCPClient
from ..mcp.server_installer import MCPServerManager, MCPServerInstaller


class MCPServerRegistry:
    """
    Manages registration and discovery of MCP servers
    """

    def __init__(self):
        """
        Initialize the MCP Server Registry

        Stores server configurations and dynamically importable servers
        """
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._server_paths: Dict[str, str] = {}

    def register_server(
            self,
            name: str,
            server_type: str = 'stdio',
            command: Optional[str] = None,
            module_path: Optional[str] = None,
            config: Optional[Dict[str, Any]] = None
    ):
        """
        Register an MCP server with the registry

        Args:
            name: Unique name for the server
            server_type: Type of server (stdio, http, etc.)
            command: Command to launch the server
            module_path: Python module path for dynamic import
            config: Additional configuration for the server
        """
        server_config = {
            'name': name,
            'type': server_type,
            'command': command,
            'module_path': module_path,
            'config': config or {}
        }

        # Validate unique name
        if name in self._servers:
            raise ValueError(f"Server with name '{name}' already registered")

        self._servers[name] = server_config

        # Store module path if provided
        if module_path:
            self._server_paths[name] = module_path

    def get_server(self, name: str) -> Dict[str, Any]:
        """
        Retrieve a registered server's configuration

        Args:
            name: Name of the server to retrieve

        Returns:
            Server configuration dictionary
        """
        if name not in self._servers:
            raise ValueError(f"No server registered with name '{name}'")

        return self._servers[name]

    def list_servers(self) -> List[str]:
        """
        List all registered server names

        Returns:
            List of registered server names
        """
        return list(self._servers.keys())

    def dynamically_import_server(self, name: str):
        """
        Dynamically import an MCP server module

        Args:
            name: Name of the server to import

        Returns:
            Imported server module
        """
        if name not in self._server_paths:
            raise ValueError(f"No importable module found for server '{name}'")

        try:
            # Add the directory to Python path if needed
            module_dir = os.path.dirname(self._server_paths[name])
            if module_dir not in sys.path:
                sys.path.insert(0, module_dir)

            # Import the module
            module = importlib.import_module(
                os.path.basename(self._server_paths[name]).replace('.py', '')
            )

            return module
        except ImportError as e:
            raise ValueError(f"Failed to import server module for '{name}': {e}")


class MCPServerTool(BaseTool):
    """
    A tool representing a specific MCP server and its capabilities
    """

    def __init__(
            self,
            server_name: str,
            server_registry: MCPServerRegistry
    ):
        """
        Initialize an MCP Server Tool

        Args:
            server_name: Name of the registered MCP server
            server_registry: Registry containing server configurations
        """
        # Retrieve server configuration
        server_config = server_registry.get_server(server_name)

        super().__init__(
            name=f"mcp_server_{server_name}",
            description=f"MCP Server Tool for {server_name}",
            is_long_running=True  # MCP interactions can be complex
        )

        self.server_name = server_name
        self.server_registry = server_registry

        # Placeholders for server capabilities
        self._resources = []
        self._tools = []
        self._prompts = []

        # Imported server module
        self._server_module = None

    async def _initialize_server(self):
        """
        Dynamically import and prepare the MCP server module
        """
        # Import the server module
        self._server_module = self.server_registry.dynamically_import_server(self.server_name)

        # TODO: Add method to extract capabilities from the server module
        # This might involve calling list_tools(), list_resources() etc.

    async def run_async(self, args: Dict[str, Any], tool_context: ToolContext) -> Dict[str, Any]:
        """
        Execute an action on the MCP server

        Expected args:
        - operation: 'list_resources', 'list_tools', 'list_prompts',
                     'read_resource', 'call_tool', 'get_prompt'
        - Additional args depend on the operation
        """
        # Ensure server module is loaded
        if not self._server_module:
            await self._initialize_server()

        operation = args.get('operation')

        try:
            # Placeholder implementation - would need to be adapted based on specific server implementation
            if operation == 'list_tools':
                # Assuming the server module has a way to list tools
                if hasattr(self._server_module, 'list_tools'):
                    tools = await self._server_module.list_tools()
                    return {
                        "status": "success",
                        "tools": tools
                    }

            elif operation == 'call_tool':
                tool_name = args.get('tool_name')
                tool_args = args.get('arguments', {})

                if not tool_name:
                    return {
                        "status": "error",
                        "message": "tool_name is required"
                    }

                # Assuming the server module has a way to call tools
                if hasattr(self._server_module, 'call_tool'):
                    result = await self._server_module.call_tool(tool_name, tool_args)
                    return {
                        "status": "success",
                        "result": result
                    }

            else:
                return {
                    "status": "error",
                    "message": f"Unsupported operation: {operation}"
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"MCP server operation error: {str(e)}"
            }


# cognisphere_adk/agents/mcp_agent.py
class MCPAgent:
    def __init__(self):
        self.server_manager = MCPServerManager()
        self.server_installer = MCPServerInstaller()
        self.connected_servers = {}

    def discover_server_capabilities(self, server_id: str):
        """
        Discover and list capabilities of an MCP server
        """
        server_config = self.server_manager.get_server(server_id)
        with MCPClient(server_config) as client:
            resources = client.list_resources()
            tools = client.list_tools()
            return {
                "resources": resources,
                "tools": tools
            }

    def add_mcp_server(
            self,
            name: str = None,
            command: str = None,
            args: List[str] = None,
            env: Dict[str, str] = None,
            install_package: str = None
    ):
        """
        Add and prepare an MCP server
        """
        # Add server configuration
        server_id = self.server_manager.add_server(
            name, command, args, env
        )

        # Create isolated environment
        self.server_installer.create_isolated_environment(server_id)

        # Optional package installation
        if install_package:
            self.server_installer.install_server_package(server_id, install_package)

        return server_id

    def connect_to_server(self, server_id: str):
        """
        Establish a connection to an MCP server
        """
        server_config = self.server_manager.get_server(server_id)

        # Launch the server
        server_process = self.server_installer.launch_server(server_config)

        # Establish MCP client connection
        client = MCPClient(server_config)
        client.connect()

        # Store connection
        self.connected_servers[server_id] = {
            "process": server_process,
            "client": client
        }

def create_mcp_agent(model="gpt-4o-mini"):
    """
    Creates an MCP Agent for managing and interacting with MCP servers

    Args:
        model: The LLM model to use

    Returns:
        An Agent configured for MCP operations
    """
    # Create a server registry
    server_registry = MCPServerRegistry()

    # Register some example MCP servers
    server_registry.register_server(
        name="brave_search",
        server_type="stdio",
        module_path="/path/to/brave_search_mcp_server.py"
    )

    # Create MCP server tools based on registered servers
    mcp_server_tools = [
        MCPServerTool(
            server_name=server_name,
            server_registry=server_registry
        ) for server_name in server_registry.list_servers()
    ]

    mcp_agent = Agent(
        name="mcp_agent",
        model=model,
        description="Agent for discovering and managing MCP servers and their capabilities",
        instruction="""You are the MCP (Model Context Protocol) Agent, responsible for:
        1. Discovering available MCP servers
        2. Managing interactions with external MCP services
        3. Providing a unified interface for accessing diverse external tools and resources

        Core Capabilities:
        - Dynamically discover MCP server capabilities
        - List available resources, tools, and prompts
        - Call tools on MCP servers

        Guiding Principles:
        - Prioritize server reliability and capability
        - Minimize unnecessary external service calls
        - Provide clear, structured information about available services
        - Protect sensitive information

        When interacting with MCP servers:
        1. Verify server capabilities
        2. Choose the most appropriate server for a given task
        3. Handle potential errors gracefully
        4. Provide context about the services used

        Your goal is to act as a sophisticated middleware 
        that can dynamically discover and utilize external 
        services through the Model Context Protocol.""",
        tools=mcp_server_tools
    )

    return mcp_agent


# Example of adding a new MCP server
def add_mcp_server_to_agent(agent, server_registry):
    """
    Dynamically add a new MCP server to an existing agent

    Args:
        agent: The MCP Agent to modify
        server_registry: The server registry containing server configurations
    """
    # Register a new server
    server_registry.register_server(
        name="weather_service",
        server_type="stdio",
        module_path="/path/to/weather_mcp_server.py"
    )

    # Create a new tool for the server
    new_server_tool = MCPServerTool(
        server_name="weather_service",
        server_registry=server_registry
    )

    # Add the new tool to the agent's tools
    agent.tools.append(new_server_tool)


# Example usage demonstrating server addition
async def demonstrate_mcp_server_addition():
    """
    Demonstrate how to dynamically add MCP servers
    """
    # Create the MCP Agent
    mcp_agent = create_mcp_agent()

    # Create a server registry
    server_registry = MCPServerRegistry()

    # Add a new MCP server
    add_mcp_server_to_agent(mcp_agent, server_registry)

    # Now you can use the newly added server
    result = await mcp_agent.run_async({
        "tool_name": "mcp_server_weather_service",
        "args": {
            "operation": "call_tool",
            "tool_name": "get_forecast",
            "arguments": {
                "location": "New York",
                "days": 5
            }
        }
    })

    return result

# Example usage in an Orchestrator
async def example_mcp_usage_in_orchestrator():
    """
    Demonstrate how the MCP Agent might be used in an Orchestrator
    """
    # Create the MCP Agent
    mcp_agent = create_mcp_agent()

    # List available MCP servers (tools)
    servers_result = await mcp_agent.run_async({
        "tool_name": "mcp_server_calculator",
        "args": {
            "operation": "list_tools"
        }
    })

    # If servers are available, choose one and call a tool
    if servers_result.get("status") == "success":
        # Example: Call a calculator tool
        calculation_result = await mcp_agent.run_async({
            "tool_name": "mcp_server_calculator",
            "args": {
                "operation": "call_tool",
                "tool_name": "add",
                "arguments": {
                    "a": 5,
                    "b": 3
                }
            }
        })

        return calculation_result

    return servers_result