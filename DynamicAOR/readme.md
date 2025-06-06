# Cognisphere ADK - Recent Modifications 06.06.25

This document outlines recent significant changes and improvements made to the Cognisphere ADK project, focusing on enhancing agent orchestration, MCP integration, and overall system robustness.

## Key Changes and Enhancements:

### 1. Dynamic Agent Orchestration (Interim Approach)

**Goal:** To enable more flexible and intelligent routing of user requests to specialized agents.

**Implemented Components:**

*   **Agent Registry (`services/agent_registry_service.py` & `data_models/registered_agent.py`):**
    *   Introduced a `RegisteredAgent` data model to define agent configurations, including name, description, capabilities, module paths, creation functions, default models, and initial instruction prompts.
    *   Implemented an `AgentRegistryService` for CRUD operations on these agent configurations, storing them as JSON files in `./cognisphere_data/registered_agents/`.
    *   Integrated the registry into `services_container.py` and `app.py`.
    *   `app.py` now registers default specialist agents (Memory, Narrative, Identity, MCP) into the registry at startup if it's empty.

*   **Routing Tools (`tools/routing_tools.py`):**
    *   `classify_and_route_query_tool`:
        *   This tool now performs keyword-based matching of the user query against the `capabilities` listed in the `AgentRegistryService`.
        *   It returns a status (`route_found`, `multiple_routes_found`, `no_route_found`), target agent details (if a single route is found), or candidate agent details (if multiple match).
        *   The output is designed for the `OrchestratorAgent`'s LLM to make the final routing decision.
    *   `invoke_specialist_agent_tool`:
        *   Primarily prepares for agent transfer by validating the target agent ID and returning necessary information. The Orchestrator is then expected to use `actions.transfer_to_agent`.
        *   Includes experimental fallback logic for direct dynamic invocation (simulating a mini-runner), though not the primary path.

*   **OrchestratorAgent (`agents/orchestrator_agent.py`):**
    *   The `OrchestratorAgent` (Cupcake) is now an `LlmAgent`.
    *   **Pre-loading of Specialist Agents:** At startup, the `OrchestratorAgent` now dynamically instantiates all agents found in the `AgentRegistryService` and includes them in its `sub_agents` list. This enables dynamic *routing* to a dynamically configured set of *pre-loaded* agents.
    *   **Updated Instruction Prompt:** The orchestrator's LLM is now explicitly instructed to:
        1.  First call `classify_and_route_query_tool`.
        2.  Based on the tool's output, decide which pre-loaded specialist agent to delegate to.
        3.  Use the ADK action `actions.transfer_to_agent = "TARGET_AGENT_NAME"` to perform the delegation.
        4.  Handle cases where no route is found or multiple routes are suggested.

**Outcome:** This achieves dynamic routing to a set of agents whose configurations are managed externally in the agent registry. New agents can be made available by adding their configuration and restarting the application.

### 2. MCP Integration Enhancements & Bug Fixes

**Goal:** Improve the reliability and correctness of interactions with MCP servers, particularly the `memoryServer`.

*   **MCPAgent Prompt Refinement (`agents/mcp_agent.py`):**
    *   The instruction prompt for the `MCPAgent` has been significantly enhanced.
    *   **Explicit Schema Adherence:** It now strongly emphasizes the need to use exact parameter names, casing, and data types as specified in the MCP tool's `inputSchema`.
    *   **Specific Instructions for `memoryServer`:** Added explicit examples and schema details for `memoryServer` tools like `create_entities` and `add_observations`, highlighting correct parameter names (`entityName`, `entityType`, `contents`) and data structures (e.g., `observations` and `contents` as arrays).
    *   Reinforced that the MCPAgent should only return raw JSON output from tool calls.

*   **Tool Call Success:**
    *   With the improved MCPAgent prompt, the agent is now able to correctly format arguments for the `memoryServer`.
    *   Successfully demonstrated creating an entity with an observation in a single `create_entities` call to the `memoryServer`, as shown in recent successful test logs.
    *   This resolves previous issues where the MCPAgent was sending malformed arguments (e.g., `entity_name` instead of `entityName`, `observation` string instead of `contents` array) to `add_observations`, leading to "Entity with name undefined not found" errors.

### 3. General Code Improvements

*   **MCP Manager (`mcpIntegration/mcp_manager.py`):** Refinements to server connection logic, error handling, and tool discovery. It now correctly uses the `MCPServerManager` to get configurations and correctly processes discovered tools into ADK-compatible `MCPTool` instances.
*   **Tool Handlers (`mcpIntegration/tool_handlers.py`):** The `call_mcp_tool` handler now relies more directly on the `MCPManager`'s capabilities.
*   **Startup Initialization (`app.py`):**
    *   Improved logging during initialization.
    *   More robust initialization of the `AgentRegistryService` and default agents.
    *   Corrected MCP server auto-connection logic to use `MCPManager.discover_and_connect_servers` with configurations from `MCPServerManager`.
*   **Session Management:** Addressed some timestamp and event appending issues in `_append_safe` and `_process_message_async` to improve reliability.

## Impact:

*   **More Intelligent Agent Delegation:** The Orchestrator can now route tasks more dynamically based on registered agent capabilities.
*   **Reliable MCP Tool Usage:** The MCPAgent can now correctly interact with complex MCP tools like those on the `memoryServer` by adhering to their schemas.
*   **Extensibility:** The agent registry makes it easier to define and add new specialist agents to the system without modifying core orchestrator code directly.
*   **Improved Debuggability:** Enhanced logging provides better insight into agent interactions and tool calls.

## Future Considerations (Not Yet Implemented from Plan):

*   True dynamic loading of agents at runtime (without needing a restart for `transfer_to_agent` to recognize them beyond the initially pre-loaded set).
*   LLM-based intent classification *within* the `classify_and_route_query_tool`.


This set of changes significantly advances the modularity and intelligence of the Cognisphere ADK.
