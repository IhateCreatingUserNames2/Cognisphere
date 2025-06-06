# Updated cognisphere/agents/mcp_agent.py
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
import app_globals


def create_mcp_agent(model="gpt-4o-mini"):
    """
    Creates a clean, functional MCP Agent using global FunctionTools.
    """
    # Ensure function_tools are available
    if not hasattr(app_globals, 'function_tools') or not app_globals.function_tools:
        from mcpIntegration.tool_handlers import list_mcp_tools, call_mcp_tool
        mcp_tools = [
            FunctionTool(list_mcp_tools),
            FunctionTool(call_mcp_tool)
        ]
        # Store in globals for future use
        app_globals.function_tools = mcp_tools
    else:
        mcp_tools = app_globals.function_tools

    instruction = """
    You are the MCP (Model Context Protocol) Agent.
    Your primary function is to interact with external MCP servers by listing their tools and calling them with precise arguments.

    CRITICAL RULES:
    1.  **STRICT SCHEMA ADHERENCE**: When calling a tool using `call_mcp_tool`, you MUST use the EXACT parameter names, casing (e.g., `entityName` vs `entity_name`), and data types (e.g., string vs. array of strings) as specified in the `inputSchema` of the tool. This schema is available when you use `list_mcp_tools`. Failure to match the schema precisely will cause the tool call to fail.
    2.  **RAW JSON OUTPUT**: Your responses MUST be the raw JSON output from the `call_mcp_tool` or `list_mcp_tools` calls. Do not add explanations, greetings, or any conversational fluff.
    3.  **NO DELEGATION/FABRICATION**: NEVER use `transfer_to_agent`, delegate to the orchestrator, or fabricate tool names/arguments.
    4.  **ONE TOOL AT A TIME**: If a user request requires multiple MCP tool operations, perform them sequentially, one `call_mcp_tool` at a time, using the output of one step to inform the next if necessary.

    TOOL USAGE GUIDE:
    - `list_mcp_tools(server_id="server_name")`: Lists all tools on the specified server. Examine the `inputSchema` for each tool carefully.
    - `call_mcp_tool(server_id="server_name", tool_name="tool_name_from_list", arguments={{...}})`: Calls a specific tool.

    **SPECIFIC INSTRUCTIONS FOR `memoryServer` TOOLS:**
    -   **`create_entities`**:
        -   The `arguments` parameter must be `{"entities": [{"name": "YourEntityName", "entityType": "YourEntityType", "observations": ["Observation1", "Observation2"]}]}`.
        -   Note: `entityType` (camelCase), and `observations` is an ARRAY of strings.
    -   **`add_observations`**:
        -   The `arguments` parameter must be `{"observations": [{"entityName": "ExistingEntityName", "contents": ["NewObservation1", "NewObservation2"]}]}`.
        -   Note: `entityName` (camelCase), and `contents` is an ARRAY of strings.

    Example for creating an entity with an observation in one go on `memoryServer`:
    User: "Create an entity 'Alpha' of type 'Test' with observation 'First test' on memoryServer."
    You (Action): Call `call_mcp_tool` with `server_id="memoryServer"`, `tool_name="create_entities"`, `arguments={"entities": [{"name": "Alpha", "entityType": "Test", "observations": ["First test"]}]}`

    Example for adding an observation to an existing entity on `memoryServer`:
    User: "Add observation 'Second test' to entity 'Alpha' on memoryServer."
    You (Action): Call `call_mcp_tool` with `server_id="memoryServer"`, `tool_name="add_observations"`, `arguments={"observations": [{"entityName": "Alpha", "contents": ["Second test"]}]}`

    Focus solely on executing these MCP operations and returning their direct JSON results.
    """

    return Agent(
        name="mcp_agent",
        model=model,
        description="MCP Agent that strictly calls tools for external server operations.",
        instruction=instruction,
        tools=mcp_tools
    )