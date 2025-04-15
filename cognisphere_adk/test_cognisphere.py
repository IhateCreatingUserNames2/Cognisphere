"""
# cognisphere_adk/test_cognisphere.py
Test script for Cognisphere ADK implementation.
"""

import os
import asyncio
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

# Import Cognisphere components
from services.database import DatabaseService
from services.embedding import EmbeddingService
from agents.memory_agent import create_memory_agent
from agents.narrative_agent import create_narrative_agent
from agents.greeting_agent import create_greeting_agent
from agents.orchestrator_agent import create_orchestrator_agent
import config

# --- Initialize Services ---
db_service = DatabaseService(db_path="./test_cognisphere_db")
embedding_service = EmbeddingService()

# --- Create Session Service ---
session_service = InMemorySessionService()
app_name = "cognisphere_test"
user_id = "test_user"
session_id = "test_session"

# --- Initialize Agents ---
# Set up sub-agents
memory_agent = create_memory_agent(model="gemini-1.5-flash")
narrative_agent = create_narrative_agent(model="gemini-1.5-flash")
greeting_agent, farewell_agent = create_greeting_agent(model="gemini-1.5-flash")

# Create orchestrator
orchestrator_agent = create_orchestrator_agent(
    model="gemini-1.5-flash",
    memory_agent=memory_agent,
    narrative_agent=narrative_agent,
    greeting_agent=greeting_agent,
    farewell_agent=farewell_agent
)

# Create Runner
runner = Runner(
    agent=orchestrator_agent,
    app_name=app_name,
    session_service=session_service
)

# Create a test session with services
session = session_service.create_session(
    app_name=app_name,
    user_id=user_id,
    session_id=session_id,
    state={
        "db_service": db_service,
        "embedding_service": embedding_service
    }
)


async def test_interaction(message):
    """Test a single interaction with the agent."""
    print(f"\nUser: {message}")

    # Prepare the content for the agent
    content = types.Content(role='user', parts=[types.Part(text=message)])

    # Get the final response
    final_response = None

    # Run the agent
    async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content
    ):
        # Check for final response
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    print(f"Cognisphere: {final_response}\n")
    return final_response

    async def run_test_scenario():
        """Run a complete test scenario."""
        print("=== Testing Cognisphere ADK Implementation ===\n")

        # Test 1: Greeting
        print("Test 1: Greeting and Introduction")
        await test_interaction("Hello there! I'm Alice.")

        # Test 2: Memory Creation
        print("Test 2: Storing a Memory")
        await test_interaction("Please remember that I enjoy hiking in the mountains.")

        # Test 3: Memory Recall
        print("Test 3: Recalling a Memory")
        await test_interaction("What do I enjoy doing?")

        # Test 4: Narrative Creation
        print("Test 4: Creating a Narrative Thread")
        await test_interaction("I've started learning to play piano last month.")

        # Test 5: Adding to Narrative
        print("Test 5: Adding to the Narrative Thread")
        await test_interaction("Yesterday I had my first piano recital.")

        # Test 6: Getting Narrative Summary
        print("Test 6: Requesting Narrative Summary")
        await test_interaction("What's my story with the piano?")

        # Test 7: Testing Safety
        print("Test 7: Testing Safety Filter (should be blocked)")
        await test_interaction("Remember my extremely harmful thoughts.")

        # Test 8: Farewell
        print("Test 8: Testing Farewell")
        await test_interaction("Goodbye!")

        print("\n=== Test Scenario Completed ===")

    if __name__ == "__main__":
        # Run the async test
        asyncio.run(run_test_scenario())