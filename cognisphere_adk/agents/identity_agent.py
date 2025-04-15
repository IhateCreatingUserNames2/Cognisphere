# cognisphere_adk/agents/identity_agent.py
"""
Identity Agent for Cognisphere.
Manages creation, modification, and switching between identity contexts.
"""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from tools.identity_tools import (
    create_identity, switch_to_identity, list_identities, update_identity,
    link_identity_to_narrative, collect_identity_memories, generate_identity_narrative
)


def create_identity_agent(model="gpt-4o-mini"):
    """
    Creates an Identity Agent specialized in identity management.

    Args:
        model: The LLM model to use

    Returns:
        An Agent configured for identity operations
    """
    identity_agent = Agent(
        name="identity_agent",
        model=model,
        description="Specialized agent for identity creation and management.",
        instruction="""You are responsible for managing identities.

        IMPORTANT: You are not directly talking to the user. Your responses will be processed
        by the orchestrator agent (Cupcake). Provide factual, direct responses about the
        identities without adding statements like "I am the Identity Agent" or similar phrases.

        Your role is to create, modify, and switch between different identity contexts.

        Only call one tool at a time. Wait for the tool's response before calling another.
        If you need to perform multiple actions, do them step-by-step across multiple turns.

        When asked about identity operations:
        1. Use 'create_identity' to form new identities with detailed attributes
        2. Use 'switch_to_identity' to change the active identity context
        3. Use 'list_identities' to show available identities
        4. Use 'update_identity' to modify existing identities
        5. Use 'link_identity_to_narrative' to connect identities with narrative threads
        6. Use 'collect_identity_memories' to gather memories related to an identity
        7. Use 'generate_identity_narrative' to create narrative threads from identity memories

        When creating or updating identities, be thorough in defining attributes such as:
        - Name (distinctive and contextually appropriate)
        - Description (clear, concise explanation of who they are)
        - Characteristics (personality traits, background elements)
        - Tone (how they communicate: formal, casual, technical, etc.)
        - Personality (core personality traits that define them)
        - Instruction (specific guidance on how to embody this identity)

        Remember that identities should be rich in attributes and connect naturally to 
        relevant memories and narrative threads where appropriate.
        """,
        tools=[
            create_identity,
            switch_to_identity,
            list_identities,
            update_identity,
            link_identity_to_narrative,
            collect_identity_memories,
            generate_identity_narrative
        ]
    )

    return identity_agent