"""
Cognisphere AIRA Client
-----------------------
Connects Cognisphere agents to the AIRA network, enabling discovery and consumption
of tools from other agents using A2A and MCP protocols.
"""

import os
import json
import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import urllib.parse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cognisphere_aira")


class CognisphereAiraClient:
    """
    Client for connecting Cognisphere to AIRA network.

    This client enables Cognisphere to:
    1. Register with an AIRA hub
    2. Discover other agents and their tools
    3. Invoke tools from other agents
    4. Expose Cognisphere tools to other agents
    """

    def __init__(
            self,
            hub_url: str,
            agent_url: str,
            agent_name: str = "Cognisphere",
            agent_description: str = "Advanced cognitive architecture with sophisticated memory and narrative capabilities"
    ):
        """
        Initialize the AIRA client for Cognisphere.

        Args:
            hub_url: URL of the AIRA hub
            agent_url: URL where this agent is accessible
            agent_name: Name of this agent
            agent_description: Description of this agent
        """
        self.hub_url = hub_url.rstrip('/')
        self.agent_url = agent_url
        self.agent_name = agent_name
        self.agent_description = agent_description
        self.session = aiohttp.ClientSession()
        self.registered = False
        self._heartbeat_task = None
        self.discovered_agents = {}
        self.discovered_tools = {}
        self.local_tools = []

    async def start(self):
        """Start the AIRA client and register with the hub."""
        await self.register_with_hub()
        logger.info(f"Cognisphere registered with AIRA hub at {self.hub_url}")

    async def stop(self):
        """Stop the AIRA client and clean up resources."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        await self.session.close()
        logger.info(f"Cognisphere disconnected from AIRA hub")

    async def register_with_hub(self):
        """Register this agent with the AIRA hub."""
        # Generate agent capabilities from local tools
        agent_card = self._generate_agent_card()

        # Create registration payload
        payload = {
            "url": self.agent_url,
            "name": self.agent_name,
            "description": self.agent_description,
            "skills": agent_card.get("skills", []),
            "shared_resources": [],
            "aira_capabilities": ["a2a"],
            "auth": {},
            "tags": ["cognisphere", "memory", "narrative"]
        }

        try:
            # Send registration request
            async with self.session.post(f"{self.hub_url}/register", json=payload) as resp:
                if resp.status == 201:  # Success status for registration
                    result = await resp.json()
                    logger.info(f"Successfully registered with hub: {result}")
                    self.registered = True
                    self._start_heartbeat()
                    return result
                else:
                    error_text = await resp.text()
                    logger.error(f"Registration failed with status {resp.status}: {error_text}")
                    raise ValueError(f"Registration failed with status {resp.status}: {error_text}")
        except Exception as e:
            logger.error(f"Error registering with hub {self.hub_url}: {str(e)}")
            raise ValueError(f"Failed to register with hub: {str(e)}")

    def _start_heartbeat(self):
        """Start the heartbeat background task."""
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to the hub."""
        while True:
            try:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                if not self.registered:
                    continue

                # URL encode properly to avoid 404 errors
                encoded_url = urllib.parse.quote(self.agent_url, safe='')

                async with self.session.post(f"{self.hub_url}/heartbeat/{encoded_url}") as resp:
                    if resp.status != 200:
                        logger.warning(f"Heartbeat failed: {await resp.text()}")
                        # If heartbeat failed, try to re-register
                        self.registered = False
                        await self.register_with_hub()
                    else:
                        logger.debug("Heartbeat sent successfully")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying

    def _generate_agent_card(self):
        """Generate the agent card for A2A protocol."""
        # Convert local tools to skills
        skills = []
        for tool in self.local_tools:
            skills.append({
                "id": f"tool-{tool.get('name')}",
                "name": tool.get('name'),
                "description": tool.get('description', ''),
                "tags": ["cognisphere", "tool"]
            })

        return {
            "name": self.agent_name,
            "description": self.agent_description,
            "url": self.agent_url,
            "skills": skills
        }

    def add_local_tool(self, tool: Dict[str, Any]):
        """
        Add a local tool to be exposed via AIRA.

        Args:
            tool: Dictionary with tool name, description, and implementation
        """
        self.local_tools.append(tool)
        logger.info(f"Added local tool: {tool.get('name')}")

    async def discover_agents(self):
        """Discover agents from the hub."""
        try:
            async with self.session.get(f"{self.hub_url}/agents") as resp:
                if resp.status == 200:
                    agents = await resp.json()
                    logger.info(f"Discovered {len(agents)} agents")

                    # Filter out self
                    agents = [a for a in agents if a.get("url") != self.agent_url]

                    # Store for later use
                    for agent in agents:
                        self.discovered_agents[agent.get("url")] = agent

                    return agents
                else:
                    error_text = await resp.text()
                    logger.warning(f"Failed to discover agents: {error_text}")
                    return []
        except Exception as e:
            logger.error(f"Error discovering agents: {str(e)}")
            return []

    async def discover_agent_capabilities(self, agent_url: str):
        """
        Discover the capabilities of a specific agent.

        Args:
            agent_url: URL of the agent to discover

        Returns:
            Agent card with capabilities
        """
        try:
            # Normalize URL
            normalized_url = agent_url
            if normalized_url.endswith('/'):
                normalized_url = normalized_url[:-1]

            # Get agent card
            async with self.session.get(f"{normalized_url}/.well-known/agent.json") as resp:
                if resp.status == 200:
                    agent_card = await resp.json()
                    logger.info(f"Discovered capabilities for agent at {agent_url}")
                    return agent_card
                else:
                    error_text = await resp.text()
                    logger.warning(f"Failed to get agent card: {error_text}")
                    return {}
        except Exception as e:
            logger.error(f"Error discovering agent capabilities: {str(e)}")
            return {}

    async def discover_agent_tools(self, agent_url: str):
        """
        Discover tools provided by a specific agent.

        Args:
            agent_url: URL of the agent to discover tools from

        Returns:
            List of tools with their metadata
        """
        agent_card = await self.discover_agent_capabilities(agent_url)

        if not agent_card:
            logger.warning(f"No agent card found for {agent_url}")
            return []

        agent_name = agent_card.get("name", "Unknown Agent")
        skills = agent_card.get("skills", [])

        tools = []
        for skill in skills:
            if "tool" in skill.get("tags", []):
                tool_name = skill.get("name")
                tool_description = skill.get("description", "")
                tool_parameters = skill.get("parameters", {})

                tools.append({
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": tool_parameters
                })

                logger.info(f"Discovered tool: {tool_name} from {agent_name}")

        # Store for later use
        self.discovered_tools[agent_url] = tools
        return tools

    async def invoke_agent_tool(self, agent_url: str, tool_name: str, params: Dict[str, Any]):
        """
        Invoke a tool on another agent.

        Args:
            agent_url: URL of the agent
            tool_name: Name of the tool to invoke
            params: Parameters for the tool

        Returns:
            Tool result
        """
        try:
            # Create a tasks/send request
            task_id = f"task-{int(datetime.now().timestamp())}"

            # Format the request for A2A protocol
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

            # Ensure the URL ends with /a2a
            if not agent_url.endswith('/a2a'):
                if agent_url.endswith('/'):
                    agent_url = agent_url + 'a2a'
                else:
                    agent_url = agent_url + '/a2a'

            logger.info(f"Invoking tool '{tool_name}' on agent at {agent_url}")

            # Send the request
            async with self.session.post(agent_url, json=request) as resp:
                if resp.status == 200:
                    result = await resp.json()

                    # Extract the result from the artifacts
                    if "result" in result:
                        task_result = result["result"]
                        artifacts = task_result.get("artifacts", [])

                        if artifacts:
                            # Get the text part from the first artifact
                            parts = artifacts[0].get("parts", [])
                            text_part = next((p for p in parts if p.get("type") == "text"), None)

                            if text_part and "text" in text_part:
                                try:
                                    # Try to parse as JSON
                                    return json.loads(text_part["text"])
                                except:
                                    # Return as plain text if not JSON
                                    return text_part["text"]

                    return result
                else:
                    error_text = await resp.text()
                    logger.warning(f"Failed to invoke tool: {error_text}")
                    return {"error": f"Failed to invoke tool: {error_text}"}
        except Exception as e:
            logger.error(f"Error invoking agent tool: {str(e)}")
            return {"error": f"Error invoking tool: {str(e)}"}

    async def get_available_hubs(self):
        """
        Get a list of known AIRA hubs.

        This is a placeholder method - in a real implementation, you might
        have a directory of known hubs or a discovery mechanism.
        """
        # In a real implementation, you might query a directory or use a discovery service
        # For now, we'll return a static list including the configured hub
        return [
            {
                "url": self.hub_url,
                "name": "Primary AIRA Hub",
                "status": "connected" if self.registered else "disconnected"
            },
            {
                "url": "http://example.com/aira",
                "name": "Example AIRA Hub",
                "status": "available"
            }
        ]

    async def switch_hub(self, new_hub_url: str):
        """
        Switch to a different AIRA hub.

        Args:
            new_hub_url: URL of the new hub
        """
        # Stop current connection
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Update hub URL
        self.hub_url = new_hub_url.rstrip('/')
        self.registered = False

        # Reset discovered agents and tools
        self.discovered_agents = {}
        self.discovered_tools = {}

        # Register with new hub
        await self.register_with_hub()
        logger.info(f"Switched to new AIRA hub at {self.hub_url}")

    async def handle_a2a_request(self, request_body: str):
        """
        Handle an incoming A2A request.

        Args:
            request_body: JSON-RPC request body

        Returns:
            JSON-RPC response
        """
        try:
            request = json.loads(request_body)
            method = request.get("method")

            if method == "tasks/send":
                return await self._handle_tasks_send(request)
            elif method == "tasks/get":
                return await self._handle_tasks_get(request)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method {method} not supported"
                    }
                }
        except Exception as e:
            logger.error(f"Error handling A2A request: {str(e)}")
            return {
                "jsonrpc": "2.0",
                "id": request.get("id", None),
                "error": {
                    "code": -32000,
                    "message": f"Error handling request: {str(e)}"
                }
            }

    async def _handle_tasks_send(self, request):
        """
        Handle the tasks/send method.

        Args:
            request: JSON-RPC request object

        Returns:
            JSON-RPC response object
        """
        params = request.get("params", {})
        task_id = params.get("id")
        message = params.get("message", {})

        if message.get("role") != "user" or not message.get("parts"):
            return self._create_error_response("Invalid message format", request.get("id"))

        # Extract the message text
        text_part = next((p for p in message.get("parts", []) if p.get("type") == "text"), None)
        if not text_part or not text_part.get("text"):
            return self._create_error_response("No text content found", request.get("id"))

        text = text_part.get("text")

        # Parse the message to identify tool request
        tool_name = None
        params = {}

        # Simple parsing - in a real implementation, you'd use a more sophisticated parser
        for tool in self.local_tools:
            if tool.get("name", "").lower() in text.lower():
                tool_name = tool.get("name")
                # Extract parameters if JSON structure is present
                try:
                    json_start = text.find('{')
                    if json_start != -1:
                        json_part = text[json_start:]
                        params = json.loads(json_part)
                except:
                    # Simple parameter extraction fallback
                    if "memory" in tool_name.lower() and "query" in text.lower():
                        import re
                        query_match = re.search(r'query[:\s]+([^\n]+)', text, re.IGNORECASE)
                        if query_match:
                            params["query"] = query_match.group(1).strip()
                break

        if not tool_name:
            # No tool identified, return help message
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "id": task_id,
                    "sessionId": params.get("sessionId", f"session-{task_id}"),
                    "status": {"state": "completed"},
                    "artifacts": [{
                        "parts": [{
                            "type": "text",
                            "text": f"I'm not sure which tool you want to use. Available tools: {', '.join(t.get('name') for t in self.local_tools)}"
                        }]
                    }]
                }
            }

        # Find the tool implementation
        tool_impl = next((t.get("implementation") for t in self.local_tools if t.get("name") == tool_name), None)
        if not tool_impl:
            return self._create_error_response(f"Tool '{tool_name}' implementation not found", request.get("id"))

        # Execute the tool
        try:
            if asyncio.iscoroutinefunction(tool_impl):
                result = await tool_impl(params)
            else:
                result = tool_impl(params)

            # Format the result as an A2A task response
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "id": task_id,
                    "sessionId": params.get("sessionId", f"session-{task_id}"),
                    "status": {"state": "completed"},
                    "artifacts": [{
                        "parts": [{
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }]
                    }]
                }
            }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return self._create_error_response(f"Error executing tool: {str(e)}", request.get("id"))

    async def _handle_tasks_get(self, request):
        """
        Handle the tasks/get method.

        Args:
            request: JSON-RPC request object

        Returns:
            JSON-RPC response object
        """
        params = request.get("params", {})
        task_id = params.get("id")

        # In a real implementation, you would retrieve the task state
        # Here we just return a simple response
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "id": task_id,
                "sessionId": f"session-{task_id}",
                "status": {"state": "completed"},
                "artifacts": [],
                "history": []
            }
        }

    def _create_error_response(self, message, req_id):
        """
        Create a JSON-RPC error response.

        Args:
            message: Error message
            req_id: Request ID

        Returns:
            JSON-RPC error response
        """
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32000,
                "message": message
            }
        }
