# Cognisphere AIRA Integration

AIRA REPO: https://github.com/IhateCreatingUserNames2/Aira
#
AIRA (Agent Interoperability and Resource Access) enables AI agents built with different frameworks to discover and communicate with each other using a standardized protocol. It bridges the gap between the Agent-to-Agent (A2A) protocol and the Model Context Protocol (MCP) to create a unified ecosystem where AI tools and resources can be shared across different agent implementations.

## Overview

This module provides integration between Cognisphere and the AIRA (Agent Interoperability and Resource Access) network, bridging the gap between the Agent-to-Agent (A2A) protocol and the Model Context Protocol (MCP).

With this integration, Cognisphere can:

1. Register as an agent on the AIRA hub
2. Discover other agents and their capabilities on the network
3. Invoke tools from other agents
4. Expose its own tools (memory, narrative, and emotion tools) to other agents

## Quick Start

The AIRA integration is included in the Cognisphere web UI. To use it:

1. Navigate to the Cognisphere web UI (typically at http://localhost:5000)
2. In the right sidebar, find the "AIRA Network" section
3. Enter the AIRA Hub URL (e.g., http://localhost:8000) and your Cognisphere Agent URL (e.g., http://localhost:5000)
4. Click "Connect to AIRA Hub"
5. Once connected, you can use the "Discover Agents" button to find other agents on the network
6. For each discovered agent, you can view and invoke their available tools

## Architecture

The AIRA integration consists of several components:

1. **CognisphereAiraClient**: Core client for connecting to AIRA hubs and managing agent discovery
2. **AIRA Tools**: ADK tools for discovering and invoking other agents' tools
3. **Tool Adapters**: Adapters that expose Cognisphere tools to the AIRA network
4. **Web API Routes**: Flask routes for managing AIRA connections and tool invocation

## Running the AIRA Hub

To use the AIRA integration, you need a running AIRA hub. You can start one using:

```bash
# Clone the AIRA repository
git clone https://github.com/IhateCreatingUserNames2/aira.git
cd aira-hub

# Install dependencies
pip install -r requirements.txt

# Start the hub
python airahub.py
```

The hub will be available at http://localhost:8000 by default.

## Programmatic Usage

You can also use the AIRA integration programmatically in your code:

```python
import asyncio
from cognisphere_adk.aira import (
    setup_aira_client, 
    register_all_cognisphere_tools_with_aira
)

async def main():
    # Initialize AIRA client
    aira_client = setup_aira_client(
        hub_url="http://localhost:8000",
        agent_url="http://localhost:5000",
        agent_name="MyCognisphere"
    )
    
    # Start the client and register with hub
    await aira_client.start()
    
    # Register Cognisphere tools with AIRA
    register_all_cognisphere_tools_with_aira()
    
    # Discover agents on the network
    agents = await aira_client.discover_agents()
    print(f"Discovered {len(agents)} agents")
    
    # For the first agent, discover tools
    if agents:
        agent_url = agents[0]["url"]
        tools = await aira_client.discover_agent_tools(agent_url)
        print(f"Discovered {len(tools)} tools from {agents[0]['name']}")
        
        # Invoke a tool if available
        if tools:
            tool_name = tools[0]["name"]
            result = await aira_client.invoke_agent_tool(
                agent_url=agent_url,
                tool_name=tool_name,
                params={"example_param": "value"}
            )
            print(f"Tool result: {result}")
    
    # Keep running to handle requests
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
```

## Available Tool Adapters

The following Cognisphere tools are automatically exposed to the AIRA network:

### Memory Tools
- `recall_memories`: Recall memories based on a query
- `create_memory`: Create a new memory in the system

### Narrative Tools
- `create_narrative_thread`: Create a new narrative thread
- `add_thread_event`: Add an event to a narrative thread
- `get_active_threads`: Retrieve active narrative threads
- `generate_narrative_summary`: Generate a summary of a narrative thread

### Emotion Tools
- `analyze_emotion`: Analyze the emotional content of text

## Available ADK Tools

The following ADK tools are provided for interacting with the AIRA network:

- `discover_agents_tool`: Discover agents on the AIRA network
- `discover_tools_tool`: Discover tools from an agent
- `invoke_tool_tool`: Invoke a tool from an agent
- `get_hubs_tool`: Get available AIRA hubs
- `switch_hub_tool`: Switch to a different AIRA hub

## Web API Routes

The following API routes are available for AIRA integration:

- `POST /api/aira/connect`: Connect to an AIRA hub
- `POST /api/aira/disconnect`: Disconnect from the AIRA hub
- `GET /api/aira/status`: Get current AIRA connection status
- `GET /api/aira/hubs`: Get available AIRA hubs
- `POST /api/aira/switch-hub`: Switch to a different AIRA hub
- `GET /api/aira/discover/agents`: Discover agents on the AIRA network
- `GET /api/aira/discover/tools`: Discover tools from an agent
- `POST /api/aira/invoke`: Invoke a tool from an agent
- `POST /api/aira/a2a`: Handle A2A requests from other agents
- `GET /.well-known/agent.json`: Serve the agent card for A2A discovery

## Troubleshooting

If you encounter issues with the AIRA integration, check the following:

1. Make sure the AIRA hub is running and accessible
2. Verify that your Cognisphere URL is reachable from the AIRA hub
3. Check the Flask logs for any error messages
4. Ensure that you have the necessary dependencies installed (aiohttp, etc.)
