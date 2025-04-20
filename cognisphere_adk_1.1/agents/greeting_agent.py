# cognisphere_adk/agents/greetings_agent.py
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm


def say_hello(name: str = "there") -> str:
    """Provides a simple greeting, optionally addressing the user by name."""
    print(f"--- Tool: say_hello called with name: {name} ---")
    return f"Hello, {name}!"


def say_goodbye() -> str:
    """Provides a simple farewell message to conclude the conversation."""
    print(f"--- Tool: say_goodbye called ---")
    return "Goodbye! Have a great day."


def create_greeting_agent(model="gemini-1.5-flash"):
    """
    Creates a Greeting Agent specialized in greetings and farewells.

    Args:
        model: The LLM model to use

    Returns:
        An Agent configured for greetings and farewells
    """
    greeting_agent = Agent(
        name="greeting_agent",
        model=model,
        description="Handles simple greetings and hellos using the 'say_hello' tool.",
        instruction="""You are the Greeting Agent. Your ONLY task is to provide a friendly greeting to the user.
        Use the 'say_hello' tool to generate the greeting.
        If the user provides their name, make sure to pass it to the tool.
        Do not engage in any other conversation or tasks.""",
        tools=[say_hello]
    )

    farewell_agent = Agent(
        name="farewell_agent",
        model=model,
        description="Handles simple farewells and goodbyes using the 'say_goodbye' tool.",
        instruction="""You are the Farewell Agent. Your ONLY task is to provide a polite goodbye message.
        Use the 'say_goodbye' tool when the user indicates they are leaving or ending the conversation
        (e.g., using words like 'bye', 'goodbye', 'thanks bye', 'see you').
        Do not perform any other actions.""",
        tools=[say_goodbye]
    )

    return greeting_agent, farewell_agent