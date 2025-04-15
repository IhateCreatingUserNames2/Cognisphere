"""
AIRA Client Library: Adapter for A2A and MCP Implementations

This library provides a standardized way to bridge Agent-to-Agent (A2A) protocol
with Model Context Protocol (MCP), allowing agents to share and discover tools across
different frameworks and implementations.
"""

import asyncio
import aiohttp
import json
import time
import uuid
import logging
from typing import Dict, List, Any, Optional, Union, Callable, AsyncIterable, Tuple
from dataclasses import dataclass, field, asdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("aira_client")


# ==================== DATA MODELS ====================

@dataclass
class AgentCard:
    """A2A Agent Card representation."""
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    provider: Dict[str, str] = field(default_factory=lambda: {})
    capabilities: Dict[str, bool] = field(default_factory=lambda: {"streaming": False, "pushNotifications": False})
    authentication: Dict[str, Any] = field(default_factory=dict)
    defaultInputModes: List[str] = field(default_factory=lambda: ["text/plain"])
    defaultOutputModes: List[str] = field(default_factory=lambda: ["text/plain"])
    skills: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class McpTool:
    """MCP Tool representation."""
    name: str
    description: str
    parameters: Dict[str, Any]
    return_type: str = "string"
    is_async: bool = True

    def to_a2a_skill(self) -> Dict[str, Any]:
        """Convert MCP tool to an A2A skill definition."""
        return {
            "id": f"mcp-tool-{self.name}",
            "name": self.name,
            "description": self.description,
            "tags": ["mcp", "tool"],
            "examples": [],
            "parameters": self.parameters
        }


@dataclass
class McpResource:
    """MCP Resource representation."""
    uri: str
    description: str
    mime_type: str = "text/plain"
    version: str = "1.0.0"

    def to_a2a_skill(self) -> Dict[str, Any]:
        """Convert MCP resource to an A2A skill definition."""
        return {
            "id": f"mcp-resource-{self.uri.replace('://', '-').replace('/', '-')}",
            "name": f"Access {self.uri}",
            "description": self.description,
            "tags": ["mcp", "resource"],
            "inputModes": [self.mime_type],
            "outputModes": [self.mime_type]
        }


@dataclass
class Task:
    """A2A Task representation."""
    id: str
    status: Dict[str, Any]
    sessionId: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ==================== ADAPTERS ====================

class McpServerAdapter:
    """Adapter for MCP servers to expose their tools and resources via A2A protocol."""

    def __init__(self, server_name: str, server_description: str, base_url: str):
        self.server_name = server_name
        self.server_description = server_description
        self.base_url = base_url
        self.tools: List[McpTool] = []
        self.resources: List[McpResource] = []
        self.tool_implementations: Dict[str, Callable] = {}

    def add_tool(self, tool: McpTool, implementation: Callable) -> None:
        """Add an MCP tool with its implementation."""
        self.tools.append(tool)
        self.tool_implementations[tool.name] = implementation

    def add_resource(self, resource: McpResource) -> None:
        """Add an MCP resource."""
        self.resources.append(resource)

    def generate_agent_card(self) -> AgentCard:
        """Generate an A2A Agent Card from registered MCP tools and resources."""
        skills = []

        # Convert tools to skills
        for tool in self.tools:
            skills.append(tool.to_a2a_skill())

        # Convert resources to skills
        for resource in self.resources:
            skills.append(resource.to_a2a_skill())

        return AgentCard(
            name=self.server_name,
            description=self.server_description,
            url=self.base_url,
            skills=skills
        )

    async def handle_a2a_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an A2A protocol request by routing to the appropriate MCP implementation."""
        method = req.get("method")

        if method == "tasks/send":
            return await self._handle_tasks_send(req.get("params", {}))
        elif method == "tasks/get":
            return await self._handle_tasks_get(req.get("params", {}))
        else:
            return {
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method {method} not supported"
                }
            }

    async def _handle_tasks_send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle A2A tasks/send method by invoking the appropriate MCP tool."""
        task_id = params.get("id")
        message = params.get("message", {})

        if message.get("role") != "user" or not message.get("parts"):
            return self._create_error_response("Invalid message format")

        # Extract the message text
        text_part = next((p for p in message.get("parts", []) if p.get("type") == "text"), None)
        if not text_part or not text_part.get("text"):
            return self._create_error_response("No text content found")

        # Parse the message to identify tool request
        text = text_part.get("text")
        tool_name = None
        params = {}

        # Simple parsing - in a real implementation, you'd use an LLM or parser
        for tool in self.tools:
            if tool.name.lower() in text.lower():
                tool_name = tool.name
                # Extract parameters - this is simplified
                # In a real implementation, you'd use structured parsing
                break

        if not tool_name or tool_name not in self.tool_implementations:
            # Return error or help message
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": task_id,
                    "sessionId": params.get("sessionId", str(uuid.uuid4())),
                    "status": {"state": "completed"},
                    "artifacts": [{
                        "parts": [{
                            "type": "text",
                            "text": f"I'm not sure which tool you want to use. Available tools: {', '.join(t.name for t in self.tools)}"
                        }]
                    }]
                }
            }

        # Execute the tool
        try:
            tool_func = self.tool_implementations[tool_name]
            result = await tool_func(params) if asyncio.iscoroutinefunction(tool_func) else tool_func(params)

            # Format the result as an A2A task response
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": task_id,
                    "sessionId": params.get("sessionId", str(uuid.uuid4())),
                    "status": {"state": "completed"},
                    "artifacts": [{
                        "parts": [{
                            "type": "text",
                            "text": str(result)
                        }]
                    }]
                }
            }
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}")
            return self._create_error_response(f"Error executing tool: {str(e)}")

    async def _handle_tasks_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle A2A tasks/get method."""
        task_id = params.get("id")

        # In a real implementation, you'd retrieve the task state
        # Here we just return a simple response
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "id": task_id,
                "sessionId": str(uuid.uuid4()),
                "status": {"state": "completed"},
                "artifacts": [],
                "history": []
            }
        }

    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """Create a JSON-RPC error response."""
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32000,
                "message": message
            }
        }


class A2aClientAdapter:
    """Adapter for A2A clients to discover and use tools exposed via MCP."""

    def __init__(self, client_name: str):
        self.client_name = client_name
        self.session = aiohttp.ClientSession()
        self.discovery_cache: Dict[str, Any] = {}
        self.cache_time = 0
        self.cache_ttl = 300  # 5 minutes

    async def close(self):
        """Close the HTTP session."""
        await self.session.close()

    async def discover_agent_card(self, agent_url: str) -> AgentCard:
        """Discover an agent's card via A2A protocol."""
        try:
            async with self.session.get(f"{agent_url}/.well-known/agent.json") as resp:
                if resp.status != 200:
                    raise ValueError(f"Failed to get agent card: {await resp.text()}")
                data = await resp.json()
                return AgentCard(**data)
        except Exception as e:
            logger.exception(f"Error discovering agent card at {agent_url}")
            raise ValueError(f"Failed to discover agent at {agent_url}: {str(e)}")

    async def discover_mcp_tools(self, agent_url: str) -> List[McpTool]:
        """Discover MCP tools exposed by an A2A agent."""
        agent_card = await self.discover_agent_card(agent_url)

        # Filter for skills tagged as MCP tools
        mcp_tools = []
        for skill in agent_card.skills:
            if "mcp" in skill.get("tags", []) and "tool" in skill.get("tags", []):
                mcp_tools.append(McpTool(
                    name=skill.get("name", ""),
                    description=skill.get("description", ""),
                    parameters=skill.get("parameters", {})
                ))

        return mcp_tools

    async def invoke_mcp_tool(self, agent_url: str, tool_name: str, params: Dict[str, Any]) -> Any:
        """Invoke an MCP tool exposed by an A2A agent."""
        # Create a task/send request
        task_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "id": task_id,
                "message": {
                    "role": "user",
                    "parts": [{
                        "type": "text",
                        "text": f"Use the {tool_name} tool with parameters: {json.dumps(params)}"
                    }]
                }
            }
        }

        # Send the request
        try:
            async with self.session.post(f"{agent_url}/a2a", json=request) as resp:
                if resp.status != 200:
                    raise ValueError(f"Failed to invoke tool: {await resp.text()}")

                data = await resp.json()
                if "error" in data:
                    raise ValueError(f"Tool invocation error: {data['error'].get('message')}")

                # Extract the result from the artifacts
                task_result = data.get("result", {})
                artifacts = task_result.get("artifacts", [])
                if not artifacts:
                    return None

                # Get the text part from the first artifact
                parts = artifacts[0].get("parts", [])
                text_part = next((p for p in parts if p.get("type") == "text"), None)
                if not text_part:
                    return None

                return text_part.get("text")

        except Exception as e:
            logger.exception(f"Error invoking tool {tool_name} at {agent_url}")
            raise ValueError(f"Failed to invoke tool: {str(e)}")


# ==================== AIRA NODE ====================

class AiraNode:
    """
    Main AIRA client that connects to an AIRA hub and enables
    communication between A2A and MCP implementations.
    """

    def __init__(self, hub_url: str, node_url: str, node_name: str, private_key: Optional[str] = None):
        self.hub_url = hub_url.rstrip('/')
        self.node_url = node_url
        self.node_name = node_name
        self.private_key = private_key
        self.session = aiohttp.ClientSession()
        self.mcp_adapter = None
        self.a2a_adapter = A2aClientAdapter(node_name)
        self.mcp_tools: List[McpTool] = []
        self.registered = False
        self._heartbeat_task = None

    async def close(self):
        """Clean up resources."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        await self.session.close()
        if self.a2a_adapter:
            await self.a2a_adapter.close()

    def set_mcp_adapter(self, adapter: McpServerAdapter) -> None:
        """Set the MCP Server adapter for exposing local tools."""
        self.mcp_adapter = adapter
        # Update the tools list
        self.mcp_tools = adapter.tools

    async def register_with_hub(self) -> Dict[str, Any]:
        """Register this node with the AIRA hub."""
        agent_card = None
        if self.mcp_adapter:
            agent_card = self.mcp_adapter.generate_agent_card()
        else:
            # Create a basic agent card
            agent_card = AgentCard(
                name=self.node_name,
                description=f"AIRA node for {self.node_name}",
                url=self.node_url,
                skills=[]
            )

        # Convert to skills list for registration
        payload = {
            "url": self.node_url,
            "name": self.node_name,
            "skills": agent_card.skills,
            "shared_resources": [
                {
                    "uri": f"mcp://tool/{tool.name}",
                    "description": tool.description,
                    "type": "mcp_tool",
                    "version": "1.0.0"
                } for tool in self.mcp_tools
            ],
            "aira_capabilities": ["a2a", "mcp"],
            "auth": agent_card.authentication
        }

        try:
            async with self.session.post(f"{self.hub_url}/register", json=payload) as resp:
                if resp.status != 200:
                    raise ValueError(f"Registration failed: {await resp.text()}")

                result = await resp.json()
                self.registered = True
                self._start_heartbeat()
                return result
        except Exception as e:
            logger.exception(f"Error registering with hub {self.hub_url}")
            raise ValueError(f"Failed to register with hub: {str(e)}")

    def _start_heartbeat(self) -> None:
        """Start the heartbeat background task."""
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to the hub."""
        while True:
            try:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                if not self.registered:
                    continue

                encoded_url = self.node_url.replace("://", "%3A%2F%2F").replace("/", "%2F")
                async with self.session.post(f"{self.hub_url}/heartbeat/{encoded_url}") as resp:
                    if resp.status != 200:
                        logger.warning(f"Heartbeat failed: {await resp.text()}")
                        # If heartbeat failed, try to re-register
                        self.registered = False
                        await self.register_with_hub()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in heartbeat loop: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying

    async def discover_agents(self, skill_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Discover agents from the hub with optional skill filter."""
        params = {}
        if skill_filter:
            params["skill"] = skill_filter

        try:
            async with self.session.get(f"{self.hub_url}/discover", params=params) as resp:
                if resp.status != 200:
                    raise ValueError(f"Discovery failed: {await resp.text()}")
                return await resp.json()
        except Exception as e:
            logger.exception(f"Error discovering agents: {str(e)}")
            raise ValueError(f"Failed to discover agents: {str(e)}")

    async def discover_mcp_tools_from_hub(self) -> Dict[str, List[McpTool]]:
        """Discover all MCP tools available from agents registered with the hub."""
        agents = await self.discover_agents()

        result = {}
        for agent in agents:
            agent_url = agent.get("url")
            if not agent_url or agent_url == self.node_url:
                continue  # Skip self or invalid URLs

            try:
                tools = await self.a2a_adapter.discover_mcp_tools(agent_url)
                if tools:
                    result[agent_url] = tools
            except Exception as e:
                logger.warning(f"Failed to discover MCP tools from {agent_url}: {str(e)}")

        return result

    async def invoke_remote_tool(self, agent_url: str, tool_name: str, params: Dict[str, Any]) -> Any:
        """Invoke an MCP tool exposed by a remote agent."""
        return await self.a2a_adapter.invoke_mcp_tool(agent_url, tool_name, params)

    async def handle_a2a_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming A2A protocol request."""
        if not self.mcp_adapter:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32000,
                    "message": "No MCP adapter configured to handle requests"
                }
            }

        return await self.mcp_adapter.handle_a2a_request(request)


# ==================== Helper Functions ====================

def create_mcp_tool(name: str, description: str, parameters: Dict[str, Any], implementation: Callable) -> Tuple[
    McpTool, Callable]:
    """Helper function to create an MCP tool with its implementation."""
    tool = McpTool(
        name=name,
        description=description,
        parameters=parameters
    )
    return tool, implementation


# ==================== Example Usage ====================

async def example():
    """Example of using the AIRA client library."""
    # Create an AIRA node
    node = AiraNode(
        hub_url="http://localhost:8000",
        node_url="http://myagent.example.com",
        node_name="MyAgent"
    )

    try:
        # Define a sample MCP tool
        async def calculate_sum(params):
            a = params.get("a", 0)
            b = params.get("b", 0)
            return a + b

        # Create an MCP adapter
        mcp_adapter = McpServerAdapter(
            server_name="Calculator Service",
            server_description="A simple calculator service",
            base_url="http://myagent.example.com"
        )

        # Add a tool to the MCP adapter
        sum_tool = McpTool(
            name="calculate_sum",
            description="Calculate the sum of two numbers",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        )
        mcp_adapter.add_tool(sum_tool, calculate_sum)

        # Set the MCP adapter
        node.set_mcp_adapter(mcp_adapter)

        # Register with the hub
        await node.register_with_hub()

        # Discover other agents
        agents = await node.discover_agents()
        print(f"Discovered {len(agents)} agents")

        # Discover MCP tools
        tools_by_agent = await node.discover_mcp_tools_from_hub()
        for agent_url, tools in tools_by_agent.items():
            print(f"Agent {agent_url} provides {len(tools)} MCP tools")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")

        # Keep the node running
        await asyncio.sleep(300)  # Run for 5 minutes

    finally:
        # Clean up
        await node.close()


if __name__ == "__main__":
    asyncio.run(example())