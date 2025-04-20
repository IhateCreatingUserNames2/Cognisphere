"""
Cognisphere AIRA Integration
---------------------------
cognisphere/aira/__init__.py
Provides integration between Cognisphere and the AIRA (Agent Interoperability and Resource Access) network.

This module enables Cognisphere to:
1. Register as an agent on the AIRA network
2. Discover other agents and their capabilities
3. Invoke tools from other agents
4. Expose its own tools to other agents
"""

from .client import CognisphereAiraClient
from .tools import (
    setup_aira_client,
    register_all_cognisphere_tools_with_aira,
    register_memory_tools_with_aira,
    register_narrative_tools_with_aira,
    register_emotion_tools_with_aira,
    aira_tools
)

__all__ = [
    'CognisphereAiraClient',
    'setup_aira_client',
    'register_all_cognisphere_tools_with_aira',
    'register_memory_tools_with_aira',
    'register_narrative_tools_with_aira',
    'register_emotion_tools_with_aira',
    'aira_tools'
]