"""
Comprehensive #congsphere_adk/config.py Configuration Management for Cognisphere
"""

import os
from typing import Dict, Any, Optional

# Import OpenRouter configuration
from services.openrouter_config import openrouter_config

# Database configuration
DATABASE_CONFIG: Dict[str, Any] = {
    "path": os.environ.get("COGNISPHERE_DB_PATH", "./cognisphere_data"),
    "collections": {
        "memories": "cognisphere_memories",
        "threads": "cognisphere_narrative_threads",
        "entities": "cognisphere_entities",
        "embeddings": "cognisphere_embeddings"
    }
}

# Model Configuration (dynamically sourced from OpenRouter)
MODEL_CONFIG: Dict[str, str] = {
    "orchestrator": openrouter_config.get_model_config("orchestrator"),
    "memory": openrouter_config.get_model_config("memory"),
    "narrative": openrouter_config.get_model_config("narrative"),
    "embedding": openrouter_config.get_model_config("embedding"),
    "greeting": openrouter_config.get_model_config("orchestrator")  # Use orchestrator model as default
}

# Memory System Configuration
MEMORY_CONFIG: Dict[str, float] = {
    "emotional_decay_rate": float(os.environ.get("COGNISPHERE_EMOTIONAL_DECAY_RATE", 0.05)),
    "recency_weight": float(os.environ.get("COGNISPHERE_RECENCY_WEIGHT", 0.4)),
    "emotional_weight": float(os.environ.get("COGNISPHERE_EMOTIONAL_WEIGHT", 0.3)),
    "semantic_weight": float(os.environ.get("COGNISPHERE_SEMANTIC_WEIGHT", 0.3)),
    "self_reference_boost": float(os.environ.get("COGNISPHERE_SELF_REFERENCE_BOOST", 0.15))
}

# Narrative System Configuration
NARRATIVE_CONFIG: Dict[str, Any] = {
    "max_active_threads": int(os.environ.get("COGNISPHERE_MAX_THREADS", 7)),
    "thread_importance_decay": float(os.environ.get("COGNISPHERE_THREAD_DECAY", 0.01)),
    "auto_theme_detection": os.environ.get("COGNISPHERE_AUTO_THEME", "true").lower() == "true"
}

# Safety Configuration
SAFETY_CONFIG: Dict[str, Any] = {
    "enable_content_filter": os.environ.get("COGNISPHERE_CONTENT_FILTER", "true").lower() == "true",
    "enable_tool_validation": os.environ.get("COGNISPHERE_TOOL_VALIDATION", "true").lower() == "true",
    "blocked_keywords": [
        word.strip()
        for word in os.environ.get(
            "COGNISPHERE_BLOCKED_KEYWORDS",
            "extremely harmful,illegal weapons,explicit content"
        ).split(",")
    ],
    "sensitive_topics": [
        topic.strip()
        for topic in os.environ.get(
            "COGNISPHERE_SENSITIVE_TOPICS",
            "password,credit card,social security,private key"
        ).split(",")
    ]
}

# Logging Configuration
LOGGING_CONFIG: Dict[str, Any] = {
    "level": os.environ.get("COGNISPHERE_LOG_LEVEL", "INFO"),
    "format": os.environ.get(
        "COGNISPHERE_LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ),
    "file_path": os.environ.get("COGNISPHERE_LOG_FILE", "./logs/cognisphere.log")
}


def get_config(config_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve specific configuration or full configuration dictionary.

    Args:
        config_type: Optional configuration section to retrieve

    Returns:
        Configuration dictionary or specific section
    """
    config_map = {
        "database": DATABASE_CONFIG,
        "models": MODEL_CONFIG,
        "memory": MEMORY_CONFIG,
        "narrative": NARRATIVE_CONFIG,
        "safety": SAFETY_CONFIG,
        "logging": LOGGING_CONFIG
    }

    if config_type:
        return config_map.get(config_type, {})

    return {
        "database": DATABASE_CONFIG,
        "models": MODEL_CONFIG,
        "memory": MEMORY_CONFIG,
        "narrative": NARRATIVE_CONFIG,
        "safety": SAFETY_CONFIG,
        "logging": LOGGING_CONFIG
    }


# Optional: Create a default .env file if it doesn't exist
def create_default_env():
    """
    Create a default .env file with example configurations.
    """
    env_path = os.path.join(os.getcwd(), '.env')
    if not os.path.exists(env_path):
        default_env_content = """
# OpenRouter Configuration
OPENROUTER_API_KEY=YOUR-OPENROUTER-API-KEY

# Model Specific Configurations
OPENROUTER_ORCHESTRATOR_MODEL=openrouter/openai/gpt-4o-mini
OPENROUTER_MEMORY_MODEL=openrouter/openai/gpt-4o-mini
OPENROUTER_NARRATIVE_MODEL=openrouter/openai/gpt-4o-mini

# Cognisphere Configurations
COGNISPHERE_DB_PATH=./cognisphere_data
COGNISPHERE_MAX_THREADS=7
COGNISPHERE_CONTENT_FILTER=true

# Logging Configuration
COGNISPHERE_LOG_LEVEL=INFO
COGNISPHERE_LOG_FILE=./logs/cognisphere.log
"""

        try:
            with open(env_path, 'w') as f:
                f.write(default_env_content)
            print(f"Created default .env file at {env_path}")
        except Exception as e:
            print(f"Error creating default .env file: {e}")


# Create default .env if not exists
create_default_env()