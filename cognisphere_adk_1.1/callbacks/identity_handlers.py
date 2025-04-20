# cognisphere_adk/callbacks/identity_handlers.py
"""
Callback handlers for identity management in Cognisphere.
"""

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from typing import Optional


def get_identity_instruction(identity_data):
    """
    Generate custom instruction based on identity.

    Args:
        identity_data: Dictionary containing identity information

    Returns:
        Instruction string for the identity
    """
    if not identity_data:
        return ""

    base = f"""You are now operating as {identity_data['name']}. 
    {identity_data.get('instruction', '')}

    Key characteristics:
    - {identity_data.get('characteristics', {}).get('background', 'No specific background')}
    - Personality: {identity_data.get('personality', 'balanced')}
    - Tone: {identity_data.get('tone', 'neutral')}

    When responding, maintain this identity consistently.
    """
    return base


def identity_context_checker(callback_context: CallbackContext):
    """
    Checks for identity context at the start of each turn.

    Args:
        callback_context: The callback context

    Returns:
        None to allow normal processing
    """
    # Check if the active identity exists and is valid
    active_id = callback_context.state.get("active_identity_id")
    if active_id:
        # Load identity-specific customizations that will affect this turn
        identity_data = callback_context.state.get(f"identity:{active_id}")
        if identity_data:
            callback_context.state["current_turn_identity"] = identity_data
        else:
            # Invalid identity ID, reset to default
            callback_context.state["active_identity_id"] = "default"
            callback_context.state["current_turn_identity"] = {
                "name": "Cupcake",
                "type": "system",
                "instruction": "You are Cupcake, the default identity."
            }
    else:
        # Default to the system identity if none is active
        callback_context.state["active_identity_id"] = "default"
        callback_context.state["current_turn_identity"] = {
            "name": "Cupcake",
            "type": "system",
            "instruction": "You are Cupcake, the default identity."
        }

    # Let the turn proceed normally
    return None


def before_model_identity_handler(callback_context: CallbackContext, llm_request: LlmRequest):
    """
    Injects identity context into the LLM request.

    Args:
        callback_context: The callback context
        llm_request: The LLM request to be modified

    Returns:
        None to allow the request to proceed with modifications
    """
    # Check if we have an active identity
    active_id = callback_context.state.get("active_identity_id")
    if not active_id:
        return None  # No identity override

    # Get identity data
    identity_data = callback_context.state.get(f"identity:{active_id}")
    if not identity_data:
        return None  # Invalid identity, no override

    # Get custom instruction for this identity
    identity_instruction = get_identity_instruction(identity_data)

    # Prepare to modify the system instruction
    original_instruction = llm_request.config.system_instruction

    # If no system instruction exists, create one
    if not original_instruction:
        original_instruction = types.Content(role="system", parts=[types.Part(text="")])
    elif not isinstance(original_instruction, types.Content):
        # Convert string to Content if necessary
        original_instruction = types.Content(role="system", parts=[types.Part(text=original_instruction)])

    # Ensure parts list exists
    if not original_instruction.parts:
        original_instruction.parts = [types.Part(text="")]

    # Combine identity instruction with existing instruction
    # Preserve any existing instruction content
    current_text = original_instruction.parts[0].text or ""
    combined_text = f"{identity_instruction}\n\n{current_text}"
    original_instruction.parts[0].text = combined_text

    # Update the request
    llm_request.config.system_instruction = original_instruction

    # Track that we modified the instruction
    callback_context.state["identity_instruction_applied"] = True

    return None  # Allow request to proceed with modified instruction


def after_agent_response_processor(callback_context: CallbackContext):
    """
    Processes the response to ensure consistency with the active identity.

    Args:
        callback_context: The callback context

    Returns:
        None (allows the original response to be used)
    """
    # No direct access to response content in after_agent_callback
    # This function is called after the agent generates its response

    # We could update state or logs here if needed
    active_id = callback_context.state.get("active_identity_id")
    if active_id:
        # Record that this identity was used for a response
        callback_context.state[f"identity:{active_id}:response_count"] = \
            callback_context.state.get(f"identity:{active_id}:response_count", 0) + 1

    # We return None to indicate no modification to the response
    return None