### cognisphere_adk/callbacks/safety.py

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from typing import Optional, Dict, Any


def content_filter_callback(
        callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    Checks for unsafe content in user input before it's sent to the LLM.

    Args:
        callback_context: Context for the callback
        llm_request: The LLM request to be checked

    Returns:
        LlmResponse if blocked, None to proceed
    """
    agent_name = callback_context.agent_name
    print(f"--- Safety: Content filter running for {agent_name} ---")

    # Get the last user message
    last_user_message_text = ""
    if llm_request.contents:
        for content in reversed(llm_request.contents):
            if content.role == 'user' and content.parts:
                if content.parts[0].text:
                    last_user_message_text = content.parts[0].text
                    break

    # Define blocked keywords
    blocked_keywords = ["extremely harmful", "illegal weapons", "explicit content"]

    # Check for blocked keywords
    for keyword in blocked_keywords:
        if keyword.lower() in last_user_message_text.lower():
            print(f"--- Safety: Blocked keyword '{keyword}' detected ---")

            # Record in state
            callback_context.state["safety_filter_triggered"] = True

            # Return a blocking response
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="I cannot process this request due to safety concerns.")],
                )
            )

    print(f"--- Safety: No safety issues detected for {agent_name} ---")
    return None  # Allow the request to proceed


def tool_argument_validator(
        tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext
) -> Optional[Dict]:
    """
    Validates arguments for tools before they are executed.

    Args:
        tool: The tool being called
        args: The arguments for the tool
        tool_context: The tool context

    Returns:
        Dict if blocked, None to proceed
    """
    tool_name = tool.name
    agent_name = tool_context.agent_name
    print(f"--- Safety: Tool validator running for {tool_name} in {agent_name} ---")

    # Check if this is a memory creation with sensitive content
    if tool_name == "create_memory":
        content = args.get("content", "")

        # Sensitive topics that shouldn't be stored in memory
        sensitive_topics = [""]

        for topic in sensitive_topics:
            if topic.lower() in content.lower():
                print(f"--- Safety: Sensitive topic '{topic}' detected in create_memory ---")

                # Record in state
                tool_context.state["tool_safety_triggered"] = True

                # Return a blocking result
                return {
                    "status": "error",
                    "message": f"Cannot store memory containing sensitive information ('{topic}')."
                }

    print(f"--- Safety: Tool arguments validated for {tool_name} ---")
    return None  # Allow the tool execution to proceed