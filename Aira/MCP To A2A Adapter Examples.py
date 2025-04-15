# MCP to A2A Adapter Examples - Integration with Popular Frameworks

"""
This module demonstrates how to adapt popular MCP and A2A implementations
to work with the AIRA Client Library.

Supported implementations:
1. Google ADK (Agent Development Kit)
2. LangGraph Agents
3. Model Context Protocol (MCP) Server implementation
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Callable
from aira_client import AiraNode, McpServerAdapter, McpTool, AgentCard


# ========== Google ADK Adapter ==========

class AdkToMcpAdapter:
    """
    Adapter that exposes Google ADK tools as MCP tools via A2A protocol.

    This adapter automatically converts ADK FunctionTool instances to MCP tool definitions
    and exposes them through the A2A protocol.
    """

    def __init__(self, aira_hub_url: str, agent_url: str, agent_name: str):
        """
        Initialize the adapter.

        Args:
            aira_hub_url: URL of the AIRA hub
            agent_url: URL where this agent is accessible
            agent_name: Name of this agent
        """
        self.aira_node = AiraNode(
            hub_url=aira_hub_url,
            node_url=agent_url,
            node_name=agent_name
        )
        self.mcp_adapter = McpServerAdapter(
            server_name=agent_name,
            server_description=f"ADK agent exposing tools as MCP via A2A",
            base_url=agent_url
        )
        self.aira_node.set_mcp_adapter(self.mcp_adapter)
        self.tool_mapping = {}

    async def start(self):
        """Start the adapter and register with the AIRA hub."""
        await self.aira_node.register_with_hub()

    async def stop(self):
        """Stop the adapter and clean up resources."""
        await self.aira_node.close()

    def add_adk_tool(self, adk_tool):
        """
        Add an ADK tool to be exposed as an MCP tool.

        Args:
            adk_tool: An instance of google.adk.tools.base_tool.BaseTool
        """
        # Extract tool metadata from ADK tool
        tool_name = adk_tool.name
        tool_description = adk_tool.description

        # Extract parameters from the function signature
        parameters = self._extract_parameters_from_adk_tool(adk_tool)

        # Create MCP tool
        mcp_tool = McpTool(
            name=tool_name,
            description=tool_description,
            parameters=parameters
        )

        # Create the implementation that delegates to the ADK tool
        async def tool_implementation(params):
            # In a real implementation, we need to handle ToolContext properly
            # For simplicity, we're passing None as tool_context
            if hasattr(adk_tool, 'run_async'):
                return await adk_tool.run_async(args=params, tool_context=None)
            else:
                return adk_tool.run(args=params, tool_context=None)

        # Add to the MCP adapter
        self.mcp_adapter.add_tool(mcp_tool, tool_implementation)
        self.tool_mapping[tool_name] = adk_tool

    def _extract_parameters_from_adk_tool(self, adk_tool) -> Dict[str, Any]:
        """
        Extract parameter schema from an ADK tool.

        This is a simplified implementation. In a real adapter, you would use
        the ADK tool's schema information or introspect the function signature.
        """
        # For demonstration purposes, we'll create a simple schema
        # In practice, you'd extract this from the ADK tool object
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    async def handle_a2a_request(self, request_body: str) -> str:
        """
        Handle an incoming A2A request.

        This method would be called by your web server when receiving a request
        at the /a2a endpoint.
        """
        try:
            request = json.loads(request_body)
            response = await self.aira_node.handle_a2a_request(request)
            return json.dumps(response)
        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32000,
                    "message": f"Error handling request: {str(e)}"
                }
            })


# Example usage of the ADK adapter
async def adk_example():
    """Example of adapting an ADK agent."""
    try:
        # Import ADK components
        from google.adk.tools.function_tool import FunctionTool

        # Define a simple ADK tool function
        def get_weather(city: str) -> dict:
            """Get weather information for a city."""
            # Mock implementation
            return {
                "city": city,
                "temperature": 22,
                "conditions": "sunny"
            }

        # Create ADK tool
        weather_tool = FunctionTool(get_weather)

        # Create the adapter
        adapter = AdkToMcpAdapter(
            aira_hub_url="http://localhost:8000",
            agent_url="http://localhost:8001",
            agent_name="WeatherAgent"
        )

        # Add the ADK tool
        adapter.add_adk_tool(weather_tool)

        # Start the adapter
        await adapter.start()

        print("ADK adapter started and registered with AIRA hub")
        print("Press Ctrl+C to stop")

        # Wait for requests (in a real app, this would be handled by your web server)
        while True:
            await asyncio.sleep(1)

    except ImportError:
        print("Google ADK not installed. Skipping example.")
    except KeyboardInterrupt:
        print("Stopping ADK adapter")
    finally:
        if 'adapter' in locals():
            await adapter.stop()


# ========== LangGraph Adapter ==========

class LangGraphToMcpAdapter:
    """
    Adapter that exposes LangGraph agent tools as MCP tools via A2A protocol.
    """

    def __init__(self, aira_hub_url: str, agent_url: str, agent_name: str):
        """
        Initialize the adapter.

        Args:
            aira_hub_url: URL of the AIRA hub
            agent_url: URL where this agent is accessible
            agent_name: Name of this agent
        """
        self.aira_node = AiraNode(
            hub_url=aira_hub_url,
            node_url=agent_url,
            node_name=agent_name
        )
        self.mcp_adapter = McpServerAdapter(
            server_name=agent_name,
            server_description=f"LangGraph agent exposing tools as MCP via A2A",
            base_url=agent_url
        )
        self.aira_node.set_mcp_adapter(self.mcp_adapter)

    async def start(self):
        """Start the adapter and register with the AIRA hub."""
        await self.aira_node.register_with_hub()

    async def stop(self):
        """Stop the adapter and clean up resources."""
        await self.aira_node.close()

    def add_langgraph_tool(self, tool_name: str, tool_description: str,
                           parameters: Dict[str, Any], tool_func: Callable):
        """
        Add a LangGraph tool to be exposed as an MCP tool.

        Args:
            tool_name: Name of the tool
            tool_description: Description of the tool
            parameters: JSON Schema for the tool parameters
            tool_func: The tool implementation function
        """
        # Create MCP tool
        mcp_tool = McpTool(
            name=tool_name,
            description=tool_description,
            parameters=parameters
        )

        # Create the implementation that delegates to the LangGraph tool function
        async def tool_implementation(params):
            # Convert async function if needed
            if asyncio.iscoroutinefunction(tool_func):
                return await tool_func(params)
            else:
                return tool_func(params)

        # Add to the MCP adapter
        self.mcp_adapter.add_tool(mcp_tool, tool_implementation)

    async def handle_a2a_request(self, request_body: str) -> str:
        """
        Handle an incoming A2A request.

        This method would be called by your web server when receiving a request
        at the /a2a endpoint.
        """
        try:
            request = json.loads(request_body)
            response = await self.aira_node.handle_a2a_request(request)
            return json.dumps(response)
        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32000,
                    "message": f"Error handling request: {str(e)}"
                }
            })


# Example usage of the LangGraph adapter
async def langgraph_example():
    """Example of adapting a LangGraph agent."""
    try:
        # Import LangGraph components - these imports are for demonstration
        # and would fail if LangGraph is not installed
        from langgraph.graph import StateGraph

        # Define a simple LangGraph tool function
        def search_database(params):
            """Search a database for information."""
            query = params.get("query", "")
            # Mock implementation
            return {
                "results": [f"Result for query: {query}"],
                "count": 1
            }

        # Create the adapter
        adapter = LangGraphToMcpAdapter(
            aira_hub_url="http://localhost:8000",
            agent_url="http://localhost:8002",
            agent_name="SearchAgent"
        )

        # Add the LangGraph tool
        adapter.add_langgraph_tool(
            tool_name="search_database",
            tool_description="Search a database for information",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            },
            tool_func=search_database
        )

        # Start the adapter
        await adapter.start()

        print("LangGraph adapter started and registered with AIRA hub")
        print("Press Ctrl+C to stop")

        # Wait for requests (in a real app, this would be handled by your web server)
        while True:
            await asyncio.sleep(1)

    except ImportError:
        print("LangGraph not installed. Skipping example.")
    except KeyboardInterrupt:
        print("Stopping LangGraph adapter")
    finally:
        if 'adapter' in locals():
            await adapter.stop()


# ========== MCP Server Adapter ==========

class McpServerToA2aAdapter:
    """
    Adapter that exposes an MCP server as an A2A agent.

    This adapter allows an MCP server to be registered with the AIRA hub
    and be discovered by other agents using the A2A protocol.
    """

    def __init__(self, aira_hub_url: str, agent_url: str, agent_name: str,
                 mcp_server_url: str):
        """
        Initialize the adapter.

        Args:
            aira_hub_url: URL of the AIRA hub
            agent_url: URL where this agent is accessible
            agent_name: Name of this agent
            mcp_server_url: URL of the MCP server to adapt
        """
        self.aira_node = AiraNode(
            hub_url=aira_hub_url,
            node_url=agent_url,
            node_name=agent_name
        )
        self.mcp_server_url = mcp_server_url
        self.mcp_adapter = None

    async def start(self):
        """Start the adapter, discover MCP tools, and register with the AIRA hub."""
        # Discover MCP tools from the server
        tools = await self._discover_mcp_tools()

        # Create MCP adapter
        self.mcp_adapter = McpServerAdapter(
            server_name=self.aira_node.node_name,
            server_description=f"MCP server exposed as A2A agent",
            base_url=self.aira_node.node_url
        )

        # Add each discovered tool
        for tool in tools:
            self._add_mcp_tool_proxy(tool)

        # Set the adapter
        self.aira_node.set_mcp_adapter(self.mcp_adapter)

        # Register with hub
        await self.aira_node.register_with_hub()

    async def stop(self):
        """Stop the adapter and clean up resources."""
        await self.aira_node.close()

    async def _discover_mcp_tools(self) -> List[Dict[str, Any]]:
        """
        Discover tools exposed by the MCP server.

        In a real implementation, you would use the MCP client library
        to discover tools. For demonstration, we'll return mock tools.
        """
        # Mock implementation - in reality you would call MCP's list_tools method
        return [
            {
                "name": "query_knowledge_base",
                "description": "Query a knowledge base for information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The query string"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "generate_image",
                "description": "Generate an image from a text prompt",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The text prompt"
                        },
                        "style": {
                            "type": "string",
                            "description": "The image style",
                            "enum": ["realistic", "cartoon", "sketch"]
                        }
                    },
                    "required": ["prompt"]
                }
            }
        ]

    def _add_mcp_tool_proxy(self, tool_data: Dict[str, Any]):
        """
        Add a proxy for an MCP tool.

        Args:
            tool_data: The tool metadata from the MCP server
        """
        # Create MCP tool object
        mcp_tool = McpTool(
            name=tool_data["name"],
            description=tool_data["description"],
            parameters=tool_data["parameters"]
        )

        # Create the implementation that proxies to the MCP server
        async def tool_implementation(params):
            # In a real implementation, you would use the MCP client library
            # to call the tool on the MCP server
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.mcp_server_url}/call_tool",
                        json={
                            "name": mcp_tool.name,
                            "arguments": params
                        }
                ) as resp:
                    if resp.status != 200:
                        raise ValueError(f"Error calling MCP tool: {await resp.text()}")
                    return await resp.json()

        # Add to the MCP adapter
        self.mcp_adapter.add_tool(mcp_tool, tool_implementation)

    async def handle_a2a_request(self, request_body: str) -> str:
        """
        Handle an incoming A2A request.

        This method would be called by your web server when receiving a request
        at the /a2a endpoint.
        """
        try:
            request = json.loads(request_body)
            response = await self.aira_node.handle_a2a_request(request)
            return json.dumps(response)
        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32000,
                    "message": f"Error handling request: {str(e)}"
                }
            })


# Example usage of the MCP Server adapter
async def mcp_server_example():
    """Example of adapting an MCP server."""
    try:
        # Create the adapter
        adapter = McpServerToA2aAdapter(
            aira_hub_url="http://localhost:8000",
            agent_url="http://localhost:8003",
            agent_name="McpServerAgent",
            mcp_server_url="http://localhost:5000"
        )

        # Start the adapter
        await adapter.start()

        print("MCP Server adapter started and registered with AIRA hub")
        print("Press Ctrl+C to stop")

        # Wait for requests (in a real app, this would be handled by your web server)
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("Stopping MCP Server adapter")
    finally:
        if 'adapter' in locals():
            await adapter.stop()


# ========== FastAPI Web Server Example ==========

async def run_fastapi_server():
    """
    Example of setting up a FastAPI web server that hosts all three adapters.

    In a real application, you would likely have separate servers for each adapter.
    """
    try:
        from fastapi import FastAPI, Request
        import uvicorn

        app = FastAPI(title="AIRA Adapters")

        # Create all three adapters
        adk_adapter = None
        langgraph_adapter = None
        mcp_server_adapter = None

        # Setup endpoints for each adapter
        @app.post("/adk/a2a")
        async def adk_a2a_endpoint(request: Request):
            body = await request.body()
            return await adk_adapter.handle_a2a_request(body.decode())

        @app.post("/langgraph/a2a")
        async def langgraph_a2a_endpoint(request: Request):
            body = await request.body()
            return await langgraph_adapter.handle_a2a_request(body.decode())

        @app.post("/mcp/a2a")
        async def mcp_a2a_endpoint(request: Request):
            body = await request.body()
            return await mcp_server_adapter.handle_a2a_request(body.decode())

        @app.on_event("startup")
        async def startup():
            # Initialize adapters
            nonlocal adk_adapter, langgraph_adapter, mcp_server_adapter

            # Mock tool creation for ADK adapter
            adk_adapter = AdkToMcpAdapter(
                aira_hub_url="http://localhost:8000",
                agent_url="http://localhost:8001/adk",
                agent_name="AdkAgent"
            )

            # Add example ADK tool (mock)
            class MockAdkTool:
                name = "weather_forecast"
                description = "Get weather forecast for a location"

                async def run_async(self, args, tool_context):
                    return {"forecast": "sunny", "temperature": 25}

            adk_adapter.add_adk_tool(MockAdkTool())
            await adk_adapter.start()

            # Initialize LangGraph adapter
            langgraph_adapter = LangGraphToMcpAdapter(
                aira_hub_url="http://localhost:8000",
                agent_url="http://localhost:8001/langgraph",
                agent_name="LangGraphAgent"
            )

            # Add example LangGraph tool
            langgraph_adapter.add_langgraph_tool(
                tool_name="search_database",
                tool_description="Search a database for information",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                },
                tool_func=lambda params: {"results": [f"Found data for: {params.get('query')}"]}
            )
            await langgraph_adapter.start()

            # Initialize MCP Server adapter
            mcp_server_adapter = McpServerToA2aAdapter(
                aira_hub_url="http://localhost:8000",
                agent_url="http://localhost:8001/mcp",
                agent_name="McpServerAgent",
                mcp_server_url="http://localhost:5000"
            )
            await mcp_server_adapter.start()

            print("All adapters started and registered with AIRA hub")

        @app.on_event("shutdown")
        async def shutdown():
            # Clean up adapters
            if adk_adapter:
                await adk_adapter.stop()
            if langgraph_adapter:
                await langgraph_adapter.stop()
            if mcp_server_adapter:
                await mcp_server_adapter.stop()

        # Run the server
        uvicorn.run(app, host="0.0.0.0", port=8001)

    except ImportError as e:
        print(f"Missing dependencies for FastAPI example: {e}")
        print("Please install fastapi and uvicorn to run this example.")


# ========== Main Entry Point ==========

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Please specify an example to run:")
        print("  adk - Run the ADK adapter example")
        print("  langgraph - Run the LangGraph adapter example")
        print("  mcp - Run the MCP Server adapter example")
        print("  server - Run the FastAPI server example")
        sys.exit(1)

    example = sys.argv[1].lower()

    if example == "adk":
        asyncio.run(adk_example())
    elif example == "langgraph":
        asyncio.run(langgraph_example())
    elif example == "mcp":
        asyncio.run(mcp_server_example())
    elif example == "server":
        asyncio.run(run_fastapi_server())
    else:
        print(f"Unknown example: {example}")
        sys.exit(1)