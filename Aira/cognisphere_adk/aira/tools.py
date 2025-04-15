"""
Cognisphere AIRA Tools
----------------------
Tools for interacting with agents on the AIRA network from Cognisphere.
Provides both tools for Cognisphere to expose its capabilities and to consume tools from other agents.
"""

import json
from typing import Dict, List, Any, Optional
from google.adk.tools import BaseTool, FunctionTool
from google.adk.tools.tool_context import ToolContext

# Import the AIRA client
from .client import CognisphereAiraClient

# Global client instance that will be initialized by setup_aira_client
aira_client = None


def setup_aira_client(hub_url: str, agent_url: str, agent_name: str = "Cognisphere"):
    """
    Initialize the global AIRA client.

    Args:
        hub_url: URL of the AIRA hub
        agent_url: URL where this agent is accessible
        agent_name: Name of this agent
    """
    global aira_client
    aira_client = CognisphereAiraClient(
        hub_url=hub_url,
        agent_url=agent_url,
        agent_name=agent_name
    )
    return aira_client


# ======== Tools for consuming AIRA agents ========

async def discover_aira_agents(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Discover agents on the AIRA network.

    Args:
        tool_context: Tool context from ADK

    Returns:
        Dictionary with discovered agents
    """
    if not aira_client:
        return {"error": "AIRA client not initialized. Call setup_aira_client first."}

    try:
        agents = await aira_client.discover_agents()

        # Format results for readability
        agent_info = []
        for agent in agents:
            agent_info.append({
                "name": agent.get("name", "Unknown"),
                "url": agent.get("url", ""),
                "description": agent.get("description", ""),
                "status": agent.get("status", "unknown")
            })

        # Store in session state for later use
        if tool_context:
            tool_context.state["aira_discovered_agents"] = {a["url"]: a for a in agent_info}

        return {
            "status": "success",
            "count": len(agent_info),
            "agents": agent_info
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error discovering agents: {str(e)}"
        }


async def discover_aira_tools(agent_url: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Discover tools offered by a specific agent on the AIRA network.

    Args:
        agent_url: URL of the agent to discover tools from
        tool_context: Tool context from ADK

    Returns:
        Dictionary with discovered tools
    """
    if not aira_client:
        return {"error": "AIRA client not initialized. Call setup_aira_client first."}

    try:
        tools = await aira_client.discover_agent_tools(agent_url)

        # Store in session state for later use
        if tool_context:
            if "aira_discovered_tools" not in tool_context.state:
                tool_context.state["aira_discovered_tools"] = {}
            tool_context.state["aira_discovered_tools"][agent_url] = tools

        agent_name = "Unknown"
        if agent_url in aira_client.discovered_agents:
            agent_name = aira_client.discovered_agents[agent_url].get("name", "Unknown")

        return {
            "status": "success",
            "agent_name": agent_name,
            "agent_url": agent_url,
            "count": len(tools),
            "tools": tools
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error discovering tools: {str(e)}"
        }


async def invoke_aira_tool(
        agent_url: str,
        tool_name: str,
        parameters: Dict[str, Any],
        tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Invoke a tool from an agent on the AIRA network.

    Args:
        agent_url: URL of the agent
        tool_name: Name of the tool to invoke
        parameters: Parameters for the tool
        tool_context: Tool context from ADK

    Returns:
        Result from the tool
    """
    if not aira_client:
        return {"error": "AIRA client not initialized. Call setup_aira_client first."}

    try:
        result = await aira_client.invoke_agent_tool(agent_url, tool_name, parameters)

        # Store last invocation result in session state
        if tool_context:
            tool_context.state["aira_last_invocation"] = {
                "agent_url": agent_url,
                "tool_name": tool_name,
                "parameters": parameters,
                "result": result
            }

        # Format result structure
        return {
            "status": "success",
            "agent_url": agent_url,
            "tool_name": tool_name,
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error invoking tool: {str(e)}"
        }


async def get_aira_hubs(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Get available AIRA hubs.

    Args:
        tool_context: Tool context from ADK

    Returns:
        Dictionary with available hubs
    """
    if not aira_client:
        return {"error": "AIRA client not initialized. Call setup_aira_client first."}

    try:
        hubs = await aira_client.get_available_hubs()

        # Store in session state
        if tool_context:
            tool_context.state["aira_available_hubs"] = hubs

        return {
            "status": "success",
            "count": len(hubs),
            "hubs": hubs,
            "current_hub": aira_client.hub_url
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error getting hubs: {str(e)}"
        }


async def switch_aira_hub(hub_url: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Switch to a different AIRA hub.

    Args:
        hub_url: URL of the new hub
        tool_context: Tool context from ADK

    Returns:
        Result of the switch operation
    """
    if not aira_client:
        return {"error": "AIRA client not initialized. Call setup_aira_client first."}

    try:
        await aira_client.switch_hub(hub_url)

        # Clear and update state
        if tool_context:
            tool_context.state["aira_discovered_agents"] = {}
            tool_context.state["aira_discovered_tools"] = {}

            # Get available hubs again to update statuses
            hubs = await aira_client.get_available_hubs()
            tool_context.state["aira_available_hubs"] = hubs

        return {
            "status": "success",
            "message": f"Switched to AIRA hub at {hub_url}",
            "new_hub": hub_url
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error switching hub: {str(e)}"
        }


# ======== Create ADK tools ========

# Tool for discovering AIRA agents
discover_agents_tool = FunctionTool(discover_aira_agents)

# Tool for discovering tools from an agent
discover_tools_tool = FunctionTool(discover_aira_tools)

# Tool for invoking a tool from an agent
invoke_tool_tool = FunctionTool(invoke_aira_tool)

# Tool for getting available AIRA hubs
get_hubs_tool = FunctionTool(get_aira_hubs)

# Tool for switching AIRA hub
switch_hub_tool = FunctionTool(switch_aira_hub)

# List of all AIRA tools
aira_tools = [
    discover_agents_tool,
    discover_tools_tool,
    invoke_tool_tool,
    get_hubs_tool,
    switch_hub_tool
]


# ======== Functions to expose Cognisphere tools to AIRA ========

def register_memory_tools_with_aira():
    """Register Cognisphere memory tools with AIRA."""
    if not aira_client:
        return

    # Import Cognisphere memory tools
    from ..tools.memory_tools import recall_memories, create_memory

    # Example adapter for recall_memories
    async def aira_recall_memories(params):
        query = params.get("query", "")
        limit = params.get("limit", 5)
        include_all_identities = params.get("include_all_identities", False)

        # We need to create a mock ToolContext
        # In a real implementation, you'd use a proper context or session state
        class MockToolContext:
            def __init__(self):
                self.state = {}

        mock_context = MockToolContext()

        # Call the actual tool
        result = await recall_memories(mock_context, query, limit, None, None, include_all_identities)
        return result

    # Register the tool with AIRA
    aira_client.add_local_tool({
        "name": "recall_memories",
        "description": "Recall memories based on a query",
        "implementation": aira_recall_memories,
        "parameters": {
            "query": "The search query for finding memories",
            "limit": "Maximum number of memories to return",
            "include_all_identities": "Whether to include memories from all identities"
        }
    })

    # Example adapter for create_memory
    async def aira_create_memory(params):
        content = params.get("content", "")
        memory_type = params.get("memory_type", "explicit")
        emotion_type = params.get("emotion_type", "neutral")
        emotion_score = params.get("emotion_score", 0.5)

        # Mock tool context
        class MockToolContext:
            def __init__(self):
                self.state = {}

        mock_context = MockToolContext()

        # Call the actual tool
        result = await create_memory(mock_context, content, memory_type, emotion_type, emotion_score)
        return result

    # Register the tool with AIRA
    aira_client.add_local_tool({
        "name": "create_memory",
        "description": "Create a new memory in the Cognisphere system",
        "implementation": aira_create_memory,
        "parameters": {
            "content": "The content of the memory",
            "memory_type": "Type of memory (explicit, emotional, flashbulb, etc.)",
            "emotion_type": "The primary emotion associated with the memory",
            "emotion_score": "Intensity of the emotion (0.0-1.0)"
        }
    })


def register_narrative_tools_with_aira():
    """Register Cognisphere narrative tools with AIRA."""
    if not aira_client:
        return

    # Import Cognisphere narrative tools
    from ..tools.narrative_tools import (
        create_narrative_thread,
        add_thread_event,
        get_active_threads,
        generate_narrative_summary
    )

    # Adapter for create_narrative_thread
    async def aira_create_narrative_thread(params):
        title = params.get("title", "")
        theme = params.get("theme", "general")
        description = params.get("description", "")

        # Mock tool context
        class MockToolContext:
            def __init__(self):
                self.state = {}

        mock_context = MockToolContext()

        # Call the actual tool
        result = await create_narrative_thread(title, theme, description, None, mock_context)
        return result

    # Register the tool with AIRA
    aira_client.add_local_tool({
        "name": "create_narrative_thread",
        "description": "Create a new narrative thread in Cognisphere",
        "implementation": aira_create_narrative_thread,
        "parameters": {
            "title": "The title of the narrative thread",
            "theme": "The theme/category of the thread",
            "description": "A description of the thread"
        }
    })

    # Adapter for add_thread_event
    async def aira_add_thread_event(params):
        thread_id = params.get("thread_id", "")
        content = params.get("content", "")
        emotion = params.get("emotion", "neutral")
        impact = params.get("impact", 0.5)

        # Mock tool context
        class MockToolContext:
            def __init__(self):
                self.state = {}

        mock_context = MockToolContext()

        # Call the actual tool
        result = await add_thread_event(thread_id, content, emotion, impact, None, mock_context)
        return result

    # Register the tool with AIRA
    aira_client.add_local_tool({
        "name": "add_thread_event",
        "description": "Add an event to a narrative thread in Cognisphere",
        "implementation": aira_add_thread_event,
        "parameters": {
            "thread_id": "ID of the thread to add to",
            "content": "Content of the event",
            "emotion": "Emotional context of the event",
            "impact": "Impact/significance score (0.0-1.0)"
        }
    })

    # Adapter for get_active_threads
    async def aira_get_active_threads(params):
        limit = params.get("limit", 5)

        # Mock tool context
        class MockToolContext:
            def __init__(self):
                self.state = {}

        mock_context = MockToolContext()

        # Call the actual tool
        result = await get_active_threads(limit, None, mock_context)
        return result

    # Register the tool with AIRA
    aira_client.add_local_tool({
        "name": "get_active_threads",
        "description": "Get active narrative threads from Cognisphere",
        "implementation": aira_get_active_threads,
        "parameters": {
            "limit": "Maximum number of threads to return"
        }
    })

    # Adapter for generate_narrative_summary
    async def aira_generate_narrative_summary(params):
        thread_id = params.get("thread_id")

        # Mock tool context
        class MockToolContext:
            def __init__(self):
                self.state = {}

        mock_context = MockToolContext()

        # Call the actual tool
        result = await generate_narrative_summary(thread_id, None, mock_context)
        return result

    # Register the tool with AIRA
    aira_client.add_local_tool({
        "name": "generate_narrative_summary",
        "description": "Generate a summary of a narrative thread in Cognisphere",
        "implementation": aira_generate_narrative_summary,
        "parameters": {
            "thread_id": "ID of the thread to summarize"
        }
    })


def register_emotion_tools_with_aira():
    """Register Cognisphere emotion tools with AIRA."""
    if not aira_client:
        return

    # Import Cognisphere emotion tools
    from ..tools.emotion_tools import analyze_emotion

    # Adapter for analyze_emotion
    def aira_analyze_emotion(params):
        text = params.get("text", "")

        # Call the actual tool
        result = analyze_emotion(text)
        return result

    # Register the tool with AIRA
    aira_client.add_local_tool({
        "name": "analyze_emotion",
        "description": "Analyze the emotional content of text",
        "implementation": aira_analyze_emotion,
        "parameters": {
            "text": "The text to analyze"
        }
    })


def register_all_cognisphere_tools_with_aira():
    """Register all Cognisphere tools with AIRA."""
    register_memory_tools_with_aira()
    register_narrative_tools_with_aira()
    register_emotion_tools_with_aira()

    print(f"Registered {len(aira_client.local_tools)} Cognisphere tools with AIRA")
