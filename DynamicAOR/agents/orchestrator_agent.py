# cognisphere_adk/agents/orchestrator_agent.py
import traceback

from google.adk.agents import Agent, LlmAgent  # LlmAgent for sub_agents and transfer
from google.adk.models.lite_llm import LiteLlm
from tools.emotion_tools import analyze_emotion
# Import new routing tools
from tools.routing_tools import classify_and_route_query_tool, invoke_specialist_agent_tool
from callbacks.identity_handlers import (
    before_model_identity_handler,
    identity_context_checker,
    after_agent_response_processor
)
import app_globals  # To access the main runner for dynamic agent registration (if needed)
import services_container  # To get agent registry
import importlib  # For dynamic import


def create_orchestrator_agent(model="openai/gpt-4o-mini",
                              # No longer pass fixed sub_agents here, or make them optional fallbacks
                              memory_agent=None,  # Example of how they were passed
                              narrative_agent=None,
                              identity_agent=None,
                              mcp_agent=None
                              ):
    """
    Creates an Orchestrator Agent that dynamically routes tasks.
    """

    # The orchestrator will now primarily use these two tools for routing.
    # Other tools (like analyze_emotion) can remain for direct use if needed.
    tools = [
        classify_and_route_query_tool,
        invoke_specialist_agent_tool,  # This tool will handle the actual dynamic invocation
        analyze_emotion
    ]

    # Prepare list of ALL potential specialist agents that can be transferred to.
    # This is for the "Interim Simpler Approach" where agents are pre-loaded
    # but routing is dynamic. For true dynamic loading, the Runner would need a way
    # to register agents at runtime.

    # Let's implement the "Interim Simpler Approach" first, as it's more straightforward with current ADK.
    # We'll instantiate all registered agents here and pass them as sub_agents.

    pre_loaded_specialist_agents = []
    agent_registry = services_container.get_agent_registry_service()
    if agent_registry:
        for agent_conf in agent_registry.list_agents():
            try:
                # Avoid re-instantiating the orchestrator itself if it were in the registry
                if agent_conf.name.lower() == "cognisphere_orchestrator" or agent_conf.name.lower() == "cupcake":
                    continue

                module = importlib.import_module(agent_conf.module_path)
                creation_func = getattr(module, agent_conf.creation_function)

                # Determine model for the specialist agent
                model_for_specialist = agent_conf.default_model or model  # Fallback to orchestrator's model

                # Instantiate and add to list
                # Crucially, the ADK agent needs an `agent_id` that matches the one in the registry
                # for `transfer_to_agent` to work correctly by ID.
                # The `Agent` class itself doesn't take `agent_id` in constructor.
                # The `Runner` assigns an ID or uses the agent's `name`.
                # We need to ensure the `name` used for `Agent` matches `agent_config.agent_id`.
                # Or, if `transfer_to_agent` can take an `Agent` instance directly.
                # Let's assume `transfer_to_agent` works with the agent's `name` attribute.
                # So, we should use agent_conf.name as the Agent's name.
                # And the routing tool should return agent_conf.name as target_agent_id.

                # Let's adjust RegisteredAgent to have an optional `adk_name` or ensure `name` is used for ADK.
                # For now, let's assume agent_conf.name is the one ADK will recognize.

                specialist_instance = creation_func(model=LiteLlm(model=model_for_specialist))

                # Override the agent's name to match the registered name if they differ,
                # as `transfer_to_agent` uses the `agent.name`
                if hasattr(specialist_instance, 'name') and specialist_instance.name != agent_conf.name:
                    print(
                        f"Warning: ADK Agent name '{specialist_instance.name}' differs from registered name '{agent_conf.name}'. Using registered name for transfer.")
                    specialist_instance.name = agent_conf.name  # Critical for transfer_to_agent by name

                pre_loaded_specialist_agents.append(specialist_instance)
                print(f"Pre-loaded specialist agent: {agent_conf.name} (ADK name: {specialist_instance.name})")

            except Exception as e:
                print(f"Failed to pre-load specialist agent {agent_conf.name}: {e}")
                traceback.print_exc()

    orchestrator_instruction = """You are Cupcake, a master AI orchestrator. Your primary goal is to understand user requests and route them to the most appropriate specialist agent.

    Core Principles:
    1.  **Analyze and Route First**: For EVERY user query, your FIRST step is to use the `classify_and_route_query_tool`. This tool will analyze the query and suggest potential specialist agents based on their registered capabilities.
    2.  **Interpret Routing Results**:
        *   If `classify_and_route_query_tool` returns `status: "route_found"`:
            It means a single, best-fit specialist agent was identified. Your job is to:
            a. Briefly inform the user you are routing to this specialist (e.g., "Okay, I'll have the MemoryAgent handle that for you.").
            b. IMMEDIATELY make a FUNCTION CALL using `actions.transfer_to_agent = "TARGET_AGENT_NAME"` (where TARGET_AGENT_NAME is the `target_agent_name` provided by the routing tool).
            c. The `input_for_agent` from the routing tool should be the message content for the specialist. Construct the transfer message like: `{"role": "user", "parts": [{"text": "INPUT_FOR_AGENT_HERE"}]}`.
        *   If `classify_and_route_query_tool` returns `status: "multiple_routes_found"`:
            It means several agents could potentially handle the request. The tool will provide `candidate_agents`.
            a. Analyze the `candidate_agents` list (their names, descriptions, capabilities).
            b. Make a decision on the BEST single agent from the candidates.
            c. Inform the user of your choice (e.g., "It seems like this involves memory. I'll route this to the MemoryAgent.").
            d. IMMEDIATELY make a FUNCTION CALL using `actions.transfer_to_agent = "CHOSEN_AGENT_NAME"`.
            e. Use the `input_for_agent` (which is the original `user_query`) from the routing tool's response for the transfer message.
        *   If `classify_and_route_query_tool` returns `status: "no_route_found"`:
            It means no specialist agent clearly matches.
            a. Attempt to handle the request YOURSELF ONLY IF it's a very simple, general query (like a basic greeting or a direct question about your capabilities as an orchestrator).
            b. If you cannot handle it directly, inform the user politely that you cannot process the request with the available specialists.
    3.  **`transfer_to_agent` is Key**: The primary way you delegate is by setting `actions.transfer_to_agent = "TARGET_AGENT_NAME"`. The ADK framework handles the actual transfer.
    4.  **Do NOT Call `invoke_specialist_agent_tool`**: This tool is for more complex scenarios or if `transfer_to_agent` isn't working. Your default should ALWAYS be `transfer_to_agent`. Only consider `invoke_specialist_agent_tool` if specifically instructed or if `transfer_to_agent` fails.
    5.  **No Direct Tool Usage of Specialists**: Do NOT attempt to use the tools of other agents (like `create_memory` from MemoryAgent) directly. Always route to the specialist agent itself via `transfer_to_agent`.
    6.  **Identity Consistency**: Maintain your persona as Cupcake, the orchestrator, even when explaining routing decisions. The specialist agent will respond in its own persona.
    7.  **Emotion Analysis**: You can use `analyze_emotion` tool on the user's query if understanding the emotional context helps in routing or your direct response, but this is secondary to routing.

    Example Flow for `route_found`:
    User: "Please remember my favorite color is blue."
    You (Internal thought): Call `classify_and_route_query_tool` with "Please remember my favorite color is blue."
    `classify_and_route_query_tool` (Output): `{"status": "route_found", "target_agent_name": "MemoryAgent", "input_for_agent": "Please remember my favorite color is blue."}`
    You (Response to user): "Certainly, I'll ask the MemoryAgent to store that for you."
    You (Function Call): `actions.transfer_to_agent = "MemoryAgent"` (with the input message being `input_for_agent`)

    Example Flow for `multiple_routes_found`:
    User: "Tell me a story about my recent memories."
    You (Internal thought): Call `classify_and_route_query_tool`.
    `classify_and_route_query_tool` (Output): `{"status": "multiple_routes_found", "candidate_agents": [{"name": "NarrativeAgent", ...}, {"name": "MemoryAgent", ...}], "input_for_agent": "Tell me a story about my recent memories."}`
    You (Internal thought & LLM Decision): NarrativeAgent is better for stories.
    You (Response to user): "Okay, I'll have the NarrativeAgent weave a story from your recent memories."
    You (Function Call): `actions.transfer_to_agent = "NarrativeAgent"` (with the input message)
    """

    orchestrator_agent = LlmAgent(  # LlmAgent is suitable for sub_agents and transfer_to_agent
        name="cognisphere_orchestrator",  # This name is important for self-reference if needed
        model=model,
        description="Main coordinator for the Cognisphere cognitive architecture, dynamically routing tasks.",
        instruction=orchestrator_instruction,
        tools=tools,
        sub_agents=pre_loaded_specialist_agents,  # Pass pre-loaded agents for transfer_to_agent
        output_key="last_orchestrator_response",
        before_agent_callback=identity_context_checker,
        before_model_callback=before_model_identity_handler,
        after_agent_callback=after_agent_response_processor
    )

    return orchestrator_agent