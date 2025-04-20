![image](https://github.com/user-attachments/assets/c3feda1f-f341-46d7-ab45-5cd37600db22)
# Cognisphere ADK: A Cognitive Architecture Framework
![image](https://github.com/user-attachments/assets/ad4dfd48-8c73-4b84-b30e-67ea8eb88390)


Cognisphere is an advanced cognitive architecture built with Google's Agent Development Kit (ADK). It features sophisticated memory, narrative, and identity capabilities, allowing for context-aware conversations with persistent state across sessions.

## 🧠 Overview

Cognisphere implements a multi-agent architecture with specialized components:

- **Orchestrator Agent**: Coordinates all sub-agents and handles user interaction
- **Memory Agent**: Stores and retrieves memories of different types 
- **Narrative Agent**: Creates and manages narrative threads for experiences
- **Identity Agent**: Manages different identities/personas the system can adopt
- **MCP Agent**: Integrates with Model Context Protocol servers for extended capabilities
- **AIRA Network**: Enables agent-to-agent communication

## 🔄 Chat History and Session Management

Cognisphere maintains conversation history across sessions through a sophisticated system of session management, state persistence, and memory retrieval.

### How Session Management Works

1. **Session Service**: 
   - The application uses `DatabaseSessionService` for persistent storage of sessions
   - Each session has a unique ID, and is associated with a user ID
   - Sessions store both the conversation history (events) and state variables

2. **State Management**:
   - Session state is used to track context across conversations
   - Different state prefixes have different scopes:
     - No prefix: Session-specific state (current conversation only)
     - `user:` prefix: User-specific state (shared across all sessions for that user)
     - `app:` prefix: Application-wide state (shared across all users)
     - `temp:` prefix: Temporary state (discarded after processing)

3. **Memory Processing**:
   - After each conversation, the `process_session_memory` function extracts key moments
   - These are analyzed for emotional content and significance
   - Important memories are stored in the database with embeddings for later retrieval

4. **Session Continuity**:
   - When a new conversation starts, the system can recall relevant memories from previous sessions
   - This is done by the `_process_message_async` function which searches previous sessions for context
   - Memories are retrieved based on relevance to the current query

### User Interface for Sessions

The UI provides features for managing sessions:

- View all conversation sessions
- Switch between existing sessions
- Create new conversations
- Each session maintains its own state and history

## 🧩 Core Components

### Services

- **Database Service** (`DatabaseService`): Persistent storage for memories and narratives
- **Embedding Service** (`EmbeddingService`): Generates vector embeddings for semantic search
- **Session Service** (`DatabaseSessionService`): Manages conversation sessions and state
- **Identity Store** (`IdentityStore`): Handles identity creation and persistence
![image](https://github.com/user-attachments/assets/8afc787e-cc62-4814-a1bd-f67bc9fcd7bb)

### Data Models

- **Memory**: Stores information with emotion and relevance scoring
- **Narrative Thread**: Organizes experiences into coherent storylines
- **Identity**: Represents different personas the system can embody

### Integration Capabilities

- **MCP Integration**: Connects with Model Context Protocol servers for extended tools
- ![image](https://github.com/user-attachments/assets/cea2372c-043c-475d-893c-1be74bf207c0)![image](https://github.com/user-attachments/assets/9e7432ab-5b53-4d2d-9a9d-44ffa7fedd1a)


- **AIRA Network**: Enables discovery and communication with other AI agents
![image](https://github.com/user-attachments/assets/c36fded1-adc0-4a91-9ae5-345f74888356)

## 🛠️ API Endpoints

### Session Management
- `/api/sessions/all`: Get all sessions for a user
- `/api/sessions/create`: Create a new session
- `/api/sessions`: Get recent sessions for a user
- `/api/session/messages`: Get messages for a specific session

### Chat
- `/api/chat`: Process a user message through the orchestrator

### Memory & Narrative
- `/api/memories`: Get recalled memories for the current context
- `/api/narratives`: Get active narrative threads

### Identity
- `/api/identities`: Get available identities
- `/api/identities/switch`: Switch to a different identity

### System
- `/api/status`: Get system status information

### Integrations
- `/api/mcp/*`: MCP server management endpoints
- `/api/aira/*`: AIRA network endpoints

## 📂 Code Structure

Cognisphere follows a modular architecture:

- `agents/`: Agent implementations (orchestrator, memory, narrative, identity)
- `data_models/`: Data structures for memory, narrative, and identity
- `services/`: Core services (database, embedding, etc.)
- `web/`: Web routes for API endpoints
- `tools/`: Tool implementations for agents
- `callbacks/`: Callback functions for agent behavior
- `mcpIntegration/`: Model Context Protocol integration
- `a2a/`: Agent-to-agent communication

## 🔧 Session Management Implementation Details

The session management system has these key components:

1. **Session Initialization**:
   ```python
   def ensure_session(user_id: str, session_id: str) -> Session:
       """
       Ensure a session exists and is initialized with service objects.
       """
       session = session_service.get_session(
           app_name=app_name,
           user_id=user_id,
           session_id=session_id
       )

       if not session:
           # Create a new session with initialized state
           initial_state = {
               "user_preference_temperature_unit": "Celsius"
           }

           session = session_service.create_session(
               app_name=app_name,
               user_id=user_id,
               session_id=session_id,
               state=initial_state
           )

           # Ensure identity catalog is loaded into session state
           initialize_identity_state(session)

       return session
   ```

2. **Message Processing with Context**:
   ```python
   async def _process_message_async(user_id: str, session_id: str, message: str):
       # Retrieve previous session's context
       previous_sessions = session_service.list_sessions(
           app_name=app_name,
           user_id=user_id
       )

       # Get memories from previous sessions to inject context
       for prev_session in sorted_sessions[:3]:  # Limit to last 3 sessions
           try:
               memories_result = recall_memories(
                   tool_context=ToolContext(
                       state={},
                       agent_name="memory_agent"
                   ),
                   query=message,
                   limit=3,
                   identity_filter=None,
                   include_all_identities=False
               )

               # Check if memories_result is a valid dictionary with memories
               if isinstance(memories_result, dict) and "memories" in memories_result:
                   context_memories.extend(memories_result.get("memories", []))
           except Exception as memory_error:
               print(f"Error recalling memories for session {prev_session.id}: {memory_error}")
               continue
   ```

3. **Frontend Session Management**:
   ```javascript
   // Switch to a different session
   async function switchToSession(sessionId) {
       console.log(`Switching to session: ${sessionId}`);

       if (sessionId === currentSessionId) {
           console.log('Already on this session');
           return;
       }

       try {
           // Update the current session ID
           currentSessionId = sessionId;

           // Save to localStorage
           localStorage.setItem('currentSessionId', currentSessionId);

           // Load messages for this session
           await loadSessionMessages(sessionId);

           // Update UI to show which session is active
           document.querySelectorAll('.session-item').forEach(item => {
               if (item.dataset.id === sessionId) {
                   item.classList.add('active');
               } else {
                   item.classList.remove('active');
               }
           });

           // Also refresh related data for this session
           updateMemories();
           updateNarrativeThreads();

           console.log(`Successfully switched to session: ${sessionId}`);
       } catch (error) {
           console.error('Error switching sessions:', error);
           addMessageToChat('assistant', `Error loading session: ${error.message}`);
       }
   }
   ```

## 🔄 Memory Processing

After each conversation, Cognisphere extracts important memories:

```python
def process_session_memory(session, identity_id):
    """
    Transform session into meaningful memories by analyzing emotional content,
    extracting significant moments, and connecting them to identities.
    """
    # Extract user messages
    user_messages = []
    for event in session.events:
        if event.author == "user" and event.content and event.content.parts:
            text = event.content.parts[0].text
            if text:
                user_messages.append(text)

    # Analyze emotional content
    combined_text = " ".join(user_messages)
    emotion_data = analyze_emotion(combined_text)

    # Extract key moments (most emotionally significant or newest)
    key_moments = []
    
    # Always include the most recent message
    if user_messages:
        key_moments.append({"content": user_messages[-1], "importance": 1.0})

    # Include high-emotion messages
    if len(user_messages) > 1:
        for msg in user_messages[:-1]:
            msg_emotion = analyze_emotion(msg)
            if msg_emotion["score"] > 0.7:
                key_moments.append({"content": msg, "importance": msg_emotion["score"]})

    # Create memories for each key moment
    for moment in key_moments:
        # Determine memory type based on content and emotion
        if emotion_data["emotion_type"] in ["joy", "excitement", "curiosity"]:
            memory_type = "emotional"
        elif emotion_data["score"] > 0.8:
            memory_type = "flashbulb"  # Highly significant memories
        else:
            memory_type = "explicit"  # Regular factual memories

        # Store memory in database with embedding
        memory = Memory(
            content=moment["content"],
            memory_type=memory_type,
            emotion_data=emotion_data,
            source="session",
            identity_id=identity_id,
            source_identity=identity_id
        )
        
        embedding = embedding_service.encode(moment["content"])
        if embedding:
            db_service.add_memory(memory, embedding)
```

## 🚀 Getting Started

1. Install dependencies:
   ```bash
   pip install google-adk litellm google-genai sentence-transformers flask openai
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Access the UI at `http://localhost:8095`

## 🔧 Troubleshooting Session Management

If chat history is not persisting between sessions:

1. Check that `DatabaseSessionService` is correctly initialized
2. Verify that session IDs are being properly passed between requests
3. Ensure the localStorage mechanism in the frontend is working correctly
4. Check backend logs for any errors during session retrieval or storage
5. Verify that the `/api/sessions/all` endpoint is correctly identifying user sessions
6. Make sure session switching in the UI is properly updating session history

## 📝 Future Improvements

- Enhance memory processing for better context retrieval ( The Memory Agent needs to be Linked Correctly with the Narrative Agent ) 
- Implement more sophisticated narrative creation 
- Enhance frontend session management with search capabilities
- Add metadata display for memories and narrative connections
- Better UI
- Attachments
- Artifacts
  


## 📝 Know Issues:
- Async issues
- Deprecated libs
- MCP sometimes fails
- AiraHub Needs to be Updated for auth or use the old AiraHub code. 
- Invalid Date in Sessions
