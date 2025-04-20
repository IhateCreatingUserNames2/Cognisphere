"""
 # cognisphere_adk/services/openrouter_config.py
OpenRouter Configuration Utility for Cognisphere
Manages model configurations, API keys, and provider settings
"""

import os
from typing import Dict, Any, Optional
import dotenv


class OpenRouterConfig:
    """
    Centralized configuration management for OpenRouter integration
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize OpenRouter configuration

        Args:
            config_path: Optional path to .env file.
                         Defaults to project root or user home directory
        """
        # Load environment variables
        if config_path:
            dotenv.load_dotenv(config_path)
        else:
            # Try multiple potential locations
            potential_paths = [
                os.path.join(os.getcwd(), '.env'),
                os.path.expanduser('~/.cognisphere/.env'),
                os.path.join(os.path.dirname(__file__), '..', '.env')
            ]
            for path in potential_paths:
                if os.path.exists(path):
                    dotenv.load_dotenv(path)
                    break

        # API Key Configuration
        self.api_key = self._get_api_key()

        # Default Model Configurations
        self.default_models: Dict[str, str] = {
            "orchestrator": os.environ.get(
                "OPENROUTER_ORCHESTRATOR_MODEL",
                "oopenai/gpt-4o-mini"
            ),
            "memory": os.environ.get(
                "OPENROUTER_MEMORY_MODEL",
                "openai/gpt-4o-mini"
            ),
            "narrative": os.environ.get(
                "OPENROUTER_NARRATIVE_MODEL",
                "openai/gpt-4o-mini"
            ),
            "embedding": os.environ.get(
                "OPENROUTER_EMBEDDING_MODEL",
                "openai/gpt-4o-mini"
            )
        }

        # Advanced Configuration Options
        self.config = {
            "site_url": os.environ.get("OPENROUTER_SITE_URL", ""),
            "site_name": os.environ.get("OPENROUTER_SITE_NAME", "Cognisphere"),
            "max_tokens": int(os.environ.get("OPENROUTER_MAX_TOKENS", 4096)),
            "temperature": float(os.environ.get("OPENROUTER_TEMPERATURE", 0.7)),
            "top_p": float(os.environ.get("OPENROUTER_TOP_P", 0.9))
        }

    def _get_api_key(self) -> str:
        """
        Retrieve OpenRouter API key with multiple fallback methods

        Returns:
            OpenRouter API key or raises ValueError
        """
        # Check environment variables with multiple possible names
        api_key_options = [
            os.environ.get("OPENROUTER_API_KEY", "YOUR-OPEN-ROUTER-API-KEY"),
            os.environ.get("OPENAI_API_KEY"),  # Fallback to OpenAI key
            os.environ.get("AI_API_KEY")  # Generic fallback
        ]

        # Return the first non-empty key
        for key in api_key_options:
            if key and key.strip():
                return key

        raise ValueError(
            "No OpenRouter API key found. "
            "Set OPENROUTER_API_KEY in environment variables."
        )

    def get_model_config(self, model_type: str) -> str:
        """
        Get model configuration for a specific type

        Args:
            model_type: Type of model (orchestrator, memory, narrative, etc.)

        Returns:
            Model name/path
        """
        return self.default_models.get(
            model_type,
            "openai/gpt-4o-mini"  # Fallback default
        )

    def update_model_config(self, model_type: str, model_name: str):
        """
        Update a specific model configuration

        Args:
            model_type: Type of model to update
            model_name: New model name/path
        """
        if model_type in self.default_models:
            self.default_models[model_type] = model_name
        else:
            raise ValueError(f"Invalid model type: {model_type}")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary for easy serialization

        Returns:
            Complete configuration dictionary
        """
        return {
            "api_key": "***" + self.api_key[-4:] if self.api_key else None,  # Mask API key
            "models": self.default_models,
            "config": self.config
        }

    def validate(self) -> bool:
        """
        Validate the current configuration

        Returns:
            Boolean indicating if configuration is valid
        """
        try:
            # Check API key
            if not self.api_key:
                return False

            # Validate model configurations
            for model_type, model_name in self.default_models.items():
                if not model_name:
                    return False

            # Additional validation can be added here
            return True
        except Exception:
            return False


# Create a singleton instance for easy import
openrouter_config = OpenRouterConfig()