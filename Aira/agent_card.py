# cognisphere_adk/a2a/agent_card.py
"""Define o Agent Card do Cognisphere para o protocolo A2A."""

def get_agent_card():
    """Retorna o Agent Card do Cognisphere."""
    return {
        "name": "Cognisphere",
        "description": "Advanced cognitive architecture with sophisticated memory and narrative capabilities",
        "version": "1.0.0",
        "endpoint": "/a2a",  # Endpoint relativo à base URL
        "capabilities": ["streaming"],
        "skills": [
            {
                "id": "memory-management",
                "name": "Memory Management",
                "description": "Store, retrieve, and analyze memories of different types and emotional significance"
            },
            {
                "id": "narrative-weaving",
                "name": "Narrative Weaving",
                "description": "Create and manage narrative threads that organize experiences into meaningful stories"
            },
            {
                "id": "emotion-analysis",
                "name": "Emotion Analysis",
                "description": "Analyze emotional content and context of interactions"
            }
        ],
        "auth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }