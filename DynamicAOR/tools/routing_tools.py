# cognisphere_adk/tools/routing_tools.py
import json
import traceback
import uuid
from typing import Dict, Any, List, Optional
from google.adk.tools.tool_context import ToolContext
from google.adk.models.lite_llm import LiteLlm  # For direct LLM call if needed
from services_container import get_agent_registry_service
import config
import importlib
from google.adk.agents import Agent
from google.adk.runners import Runner # Might be needed for direct invocation
from google.adk.sessions import InMemorySessionService # For temporary runner
from google.adk.models.lite_llm import LiteLlm
from google.genai import types as adk_types # Renamed to avoid conflict


async def classify_and_route_query_tool(
        user_query: str,
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Classifies the user's query intent and suggests a specialist agent.
    Also prepares the input for the target agent.
    """
    agent_registry = get_agent_registry_service()
    if not agent_registry:
        return {"status": "error", "message": "AgentRegistryService not available."}

    # 1. Intent Classification (LLM-based)
    # We'll use the orchestrator's LLM model for this classification task.
    # We need a way to make a direct LLM call.
    # For now, let's assume the orchestrator agent itself will make this LLM call
    # or we could instantiate a temporary LiteLlm model here.

    # Option: Direct LLM call within the tool (can be resource-intensive per tool call)
    # For this example, let's define the prompt and assume the orchestrator's LLM will use it.
    # A more advanced system might have a dedicated intent classification model/service.

    registered_agents = agent_registry.list_agents()
    agent_capabilities_summary = []
    for agent in registered_agents:
        capabilities_str = ", ".join(agent.capabilities)
        agent_capabilities_summary.append(
            f"- {agent.name} (ID: {agent.agent_id}): Specializes in {agent.description}. Handles: {capabilities_str}")

    capabilities_list_str = "\n".join(agent_capabilities_summary)

    # This prompt will be used by the OrchestratorAgent's LLM when it calls this tool.
    # The tool itself doesn't make an LLM call to classify, it *provides the info* for the Orchestrator to classify.
    # The actual classification decision comes from the Orchestrator's LLM *after* this tool runs.

    # This tool's job is to find agents based on keywords in the query matching agent capabilities.
    # The Orchestrator LLM then uses this tool's output + its own reasoning to pick the best agent.

    found_agents = []
    query_lower = user_query.lower()

    for agent_config in registered_agents:
        for capability in agent_config.capabilities:
            if capability.lower() in query_lower:
                if agent_config not in found_agents:  # Avoid duplicates
                    found_agents.append(agent_config)
                # Could add more sophisticated matching here (e.g., TF-IDF, embeddings)

    if not found_agents:
        return {
            "status": "no_route_found",
            "message": "No specialist agent found based on query keywords matching capabilities.",
            "user_query": user_query
        }

    # If multiple agents match, for now, we return all of them.
    # The Orchestrator's LLM will need to decide among them.
    # Or, implement more sophisticated ranking here.

    # For simplicity, let's just pick the first matched agent.
    # A better approach would be to let the Orchestrator's LLM choose from the list.
    # Or, add ranking logic here based on how many capabilities match, or confidence.

    if len(found_agents) > 1:
        # Prepare information for the orchestrator LLM to decide
        candidate_agents_info = []
        for agent in found_agents:
            candidate_agents_info.append({
                "agent_id": agent.agent_id,
                "name": agent.name,
                "description": agent.description,
                "capabilities": agent.capabilities
            })
        return {
            "status": "multiple_routes_found",
            "message": "Multiple specialist agents match the query. Orchestrator should decide.",
            "candidate_agents": candidate_agents_info,
            "user_query": user_query,
            "prepared_input_for_agent": user_query  # Default input
        }

    target_agent_config = found_agents[0]

    # For now, the input for the agent is just the original query.
    # More advanced parsing could extract entities or rephrase the query.
    prepared_input = user_query

    return {
        "status": "route_found",
        "target_agent_id": target_agent_config.agent_id,
        "target_agent_name": target_agent_config.name,
        "target_agent_description": target_agent_config.description,
        "input_for_agent": prepared_input,
        "user_query": user_query
    }


async def invoke_specialist_agent_tool(
        agent_id: str,
        input_for_agent: str,  # This could be a string or a dict for more structured input
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Dynamically loads and invokes a specialist agent.
    This version will attempt to use tool_context.actions.transfer_to_agent.
    """
    agent_registry = get_agent_registry_service()
    if not agent_registry:
        return {"status": "error", "message": "AgentRegistryService not available."}

    agent_config = agent_registry.get_agent_config(agent_id)
    if not agent_config:
        return {"status": "error", "message": f"Agent config for ID '{agent_id}' not found."}

    # The ADK framework's runner needs to be aware of the agent it's transferring to.
    # How this dynamic registration happens is key.
    # For now, we assume the ADK runner can handle it if the agent_id is known.
    # This is the preferred ADK way if `transfer_to_agent` can work with
    # agents that were not part of the initial `sub_agents` list of the Orchestrator.
    # This might require modifications to how the main Runner in app.py is initialized
    # or if the Runner itself can register new agents at runtime.

    # If tool_context and tool_context.actions are available, try to use transfer_to_agent
    if tool_context and hasattr(tool_context, 'actions') and tool_context.actions:
        # We need to ensure the main runner in `app.py` knows about this agent_id
        # and can instantiate it. This is the part that needs ADK framework support
        # for truly dynamic agents not pre-listed as sub_agents.

        # For the `transfer_to_agent` to work, the target agent (`agent_id`)
        # must be known to the Runner that is currently executing the Orchestrator.
        # This implies that either:
        # 1. All potential specialist agents are instantiated at startup and passed to the Orchestrator's Runner.
        #    (This is the "Interim Simpler Approach" from your plan - not truly dynamic loading, but dynamic routing).
        # 2. The Runner has a mechanism to dynamically load/register new agent instances by ID.

        # Let's proceed with the assumption that the ADK `Runner`
        # needs to have the agent pre-registered/instantiated for `transfer_to_agent` to work.
        # So, this tool will primarily return the necessary info for the Orchestrator's LLM
        # to make the `transfer_to_agent` call itself.

        # This tool's primary responsibility shifts: it validates and prepares for transfer.
        # The Orchestrator's LLM will then make the actual `transfer_to_agent` call.
        # Therefore, this tool will not "invoke" but rather "prepare_for_specialist_transfer"

        # This simplified tool now just confirms the agent is valid and returns its details.
        # The orchestrator will handle the actual transfer_to_agent.
        return {
            "status": "transfer_prepared",
            "target_agent_id": agent_config.agent_id,
            "target_agent_name": agent_config.name,
            "input_for_agent": input_for_agent,
            "message": f"Prepared to transfer to agent {agent_config.name} (ID: {agent_config.agent_id})."
        }

    else:  # Fallback or direct invocation (more complex and less ADK-idiomatic for sub-agent flow)
        # This block represents a more direct (but potentially less integrated) invocation
        # if transfer_to_agent is not viable for truly dynamic, non-pre-registered agents.
        print(f"Attempting direct dynamic invocation for agent: {agent_config.name}")
        try:
            module = importlib.import_module(agent_config.module_path)
            creation_func = getattr(module, agent_config.creation_function)

            # Instantiate the agent
            # We need to pass the model. Use agent's default_model or orchestrator's as fallback.
            model_name_for_specialist = agent_config.default_model or config.MODEL_CONFIG.get("orchestrator")
            specialist_agent_instance: Agent = creation_func(model=LiteLlm(model=model_name_for_specialist))

            # --- Direct Invocation (Simplified Runner Simulation) ---
            # This is a simplified simulation. A robust solution would be more involved.
            # Create a temporary session and runner for this specialist agent.
            temp_session_service = InMemorySessionService()
            temp_user_id = tool_context.session.user_id if tool_context and tool_context.session else "temp_dyn_user"
            temp_session_id = f"dyn_agent_{agent_id}_{str(uuid.uuid4())[:8]}"

            # Pass relevant state from the current tool_context if possible
            initial_state = tool_context.state if tool_context else {}

            temp_session = temp_session_service.create_session(
                app_name="cognisphere_dynamic_agent",
                user_id=temp_user_id,
                session_id=temp_session_id,
                state=initial_state  # Pass current state
            )

            # We need to set the initial instruction prompt for the specialist agent
            if agent_config.initial_instruction_prompt:
                # This is tricky. The ADK Agent's instruction is usually set at init.
                # For LiteLlm, we can try to pass it via llm_request.config.system_instruction
                # but that's less direct than having the agent initialized with it.
                # The create_xxx_agent functions should ideally take an instruction param.
                # For now, we'll assume the default instruction set in RegisteredAgent is sufficient
                # or the create_xxx_agent function handles it.
                pass

            specialist_runner = Runner(
                agent=specialist_agent_instance,
                app_name="cognisphere_dynamic_runner",
                session_service=temp_session_service
            )

            # Prepare input content for the specialist agent
            if isinstance(input_for_agent, str):
                agent_input_content = adk_types.Content(role="user", parts=[adk_types.Part(text=input_for_agent)])
            elif isinstance(input_for_agent, dict) and "text" in input_for_agent:  # Assuming simple dict with text
                agent_input_content = adk_types.Content(role="user",
                                                        parts=[adk_types.Part(text=input_for_agent["text"])])
            else:
                return {"status": "error", "message": "Invalid input_for_agent format."}

            final_response_text = f"Error: No response from {agent_config.name}"
            async for event in specialist_runner.run_async(
                    user_id=temp_user_id,
                    session_id=temp_session_id,
                    new_message=agent_input_content
            ):
                if event and event.is_final_response() and event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text
                    break

            return {
                "status": "success_direct_invoke",
                "agent_id": agent_config.agent_id,
                "agent_name": agent_config.name,
                "response": final_response_text
            }

        except Exception as e:
            print(f"Error during direct dynamic agent invocation for {agent_config.name}: {e}")
            traceback.print_exc()
            return {"status": "error", "message": f"Failed to invoke specialist agent {agent_config.name}: {str(e)}"}