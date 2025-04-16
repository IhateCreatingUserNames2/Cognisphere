![image](https://github.com/user-attachments/assets/c3feda1f-f341-46d7-ab45-5cd37600db22)
# Cognisphere ADK: A Cognitive Architecture Framework






## Overview

Cognisphere ADK is an  AI agent development framework built on Google's Agent Development Kit (ADK) that provides a sophisticated cognitive architecture with multiple specialized components:

- **Memory Management**: Advanced memory storage and retrieval
- **Narrative Threading**: Creating and managing interconnected story threads
- **Identity System**: Dynamic identity creation and switching
- **A2A & MCP Integration**: Seamless interaction with external agents

## Key Components

### 1. Memory Blossom 🧠

The memory system goes beyond traditional storage:

- **Memory Types**: 
  - Explicit memories
  - Emotional memories
  - Flashbulb memories
  - Procedural memories
  - Liminal memories

- **Key Features**:
  - Emotion-weighted recall
  - Multi-dimensional indexing
  - Dynamic memory transformation

![image](https://github.com/user-attachments/assets/fe418f8d-3e5d-43f2-91b0-dd7d7de386d3)
### 2. Narrative Weaver 📖

Create and manage complex narrative threads:

- Automatically identifies thematic connections
- Tracks story development
- Monitors narrative tension and resolution
- Detects recurring themes

![image](https://github.com/user-attachments/assets/8cccb848-067a-472f-b493-5472897b6da8)

### 3. Identity System 🎭

A flexible identity management system:

- Create multiple identities
- Switch between identities dynamically
- Link identities to memories and narratives
- Customize tone, personality, and instructions

![image](https://github.com/user-attachments/assets/aed332e7-f9dc-474d-8824-74c8f3e96b36)
## A2A (Agent2Agent) Protocol Integration

Cognisphere supports the A2A protocol for seamless agent interoperability:

### Key A2A Features:

- Discover agents across different frameworks
- Connect to external agents
- Share capabilities
- Negotiate interactions

Use A2A to build a network of Agents, or to connect to Remote Networks of agents and use their Tools or MCP Servers, Concept: https://github.com/IhateCreatingUserNames2/Aira 
![image](https://github.com/user-attachments/assets/559e5b5f-fd48-494a-8a65-0f5103e5490d)
## MCP (Model Context Protocol) Integration

Advanced tool and context management:

- Connect to external MCP servers
- Discover and use tools from different sources
- Standardized communication between AI systems

## Getting Started

### Installation

```bash
# Clone the repository
git clone https://github.com/IhateCreatingUserNames2/cognisphere-adk.git

# Install dependencies
pip install -r requirements.txt

# Set up OpenRouter API key
export OPENROUTER_API_KEY=your_api_key_here
```

### Running the Application

```bash
# Start the Flask application
python app.py
```

## Adding New Agents

### 1. Create an Agent

```python
from google.adk.agents import Agent

def create_my_agent():
    my_agent = Agent(
        name="my_custom_agent",
        model="gpt-4o-mini",
        instruction="Your agent's specific instructions",
        tools=[...]  # Add custom tools
    )
    return my_agent
```

### 2. Add to Orchestrator

Update `orchestrator_agent.py` to include your new agent in the `sub_agents` list.

## Using Identities

```python
# Create a new identity
tool_context.create_identity(
    name="Explorer",
    description="Curious and adventurous persona",
    tone="enthusiastic",
    personality="curious"
)

# Switch identities
tool_context.switch_to_identity("explorer_id")
```

## Using Narratives

```python
# Create a narrative thread
tool_context.create_narrative_thread(
    title="My Adventure",
    theme="exploration",
    description="A journey of discovery"
)

# Add events to the narrative
tool_context.add_thread_event(
    thread_id="adventure_thread_id",
    content="Started the journey at dawn",
    emotion="excitement"
)
```

## Adding MCP Servers

1. Use the web interface to add MCP servers
2. Configure server details:
   - Server Name
   - Command
   - Arguments
   - Environment Variables

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

Project Link: [https://github.com/IhateCreatingUserNames2/cognisphere-adk](https://github.com/IhateCreatingUserNames2/cognisphere-adk)

---

**Note**: This project is a conceptual implementation leveraging Google's Agent Development Kit. Capabilities and implementation may evolve.
