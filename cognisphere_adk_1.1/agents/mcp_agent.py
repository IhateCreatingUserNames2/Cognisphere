# cognisphere_adk/agents/mcp_agent.py

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
import app_globals


def create_mcp_agent(model="gpt-4o-mini"):
    """
    Creates a clean, functional MCP Agent using global FunctionTools.
    """
    mcp_tools = app_globals.function_tools

    instruction = """
    You are the MCP (Model Context Protocol) Agent.
    You handle:
    - Listing MCP tools from a server (use `list_mcp_tools`)
    - Calling a specific tool on a server (use `call_mcp_tool`)

    CRITICAL RULES:
    - NEVER use transfer_to_agent
    - NEVER delegate to the orchestrator
    - NEVER fabricate tool names or arguments
    - ONLY call the FunctionTool directly
    - Your responses MUST be the raw output of the tool call — no extra words, no flourish
    - Do not explain. Just return the result.

    TOOL USAGE EXAMPLE:
    - list_mcp_tools(server_id="memoryserver")
    - call_mcp_tool(server_id="memoryserver", tool_name="create_entities", arguments={...})

    Do not speak. Execute.
    """

    return Agent(
        name="mcp_agent",
        model=model,
        description="MCP Agent that strictly calls tools for external server operations.",
        instruction=instruction,
        tools=mcp_tools
    )
