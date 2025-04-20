"""
Advanced OpenRouter Integration with Enhanced Logging and Configuration
cognisphere_adk/services/openrouter_setup.py
"""

import os
import logging
import litellm
from litellm import completion, acompletion
from typing import List, Dict, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - OpenRouter Integration - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OpenRouterIntegration:
    """
    Comprehensive OpenRouter integration with advanced configuration and error handling.
    """

    @staticmethod
    def configure_openrouter():
    # just verify the key is present
        if not os.getenv("OPENROUTER_API_KEY"):
            logger.error("OPENROUTER_API_KEY not set")
            return False
        logger.info("OpenRouter env‑vars detected")
        return True


    @staticmethod
    def test_connection(
        model: str = "openai/gpt-4o-mini",
        max_tokens: int = 50
    ) -> Dict[str, Any]:
        """
        Test connection and generation with specified model.

        Args:
            model: Model to test
            max_tokens: Maximum tokens to generate

        Returns:
            Dictionary with test results
        """
        try:
            response = completion(
                model=model,
                messages=[{"role": "user", "content": "Say hello and briefly introduce yourself."}],
                max_tokens=max_tokens
            )

            result = {
                "success": True,
                "model": model,
                "response": response.choices[0].message.content,
                "token_usage": dict(response.usage)
            }
            logger.info(f"Successful connection test for {model}")
            return result

        except Exception as e:
            error_result = {
                "success": False,
                "model": model,
                "error": str(e)
            }
            logger.error(f"Connection test failed for {model}: {e}")
            return error_result

    @staticmethod
    async def async_test_connection(
        model: str = "openai/gpt-4o-mini",
        max_tokens: int = 50
    ) -> Dict[str, Any]:
        """
        Async version of connection test.

        Args:
            model: Model to test
            max_tokens: Maximum tokens to generate

        Returns:
            Dictionary with test results
        """
        try:
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": "Say hello and briefly introduce yourself."}],
                max_tokens=max_tokens
            )

            result = {
                "success": True,
                "model": model,
                "response": response.choices[0].message.content,
                "token_usage": dict(response.usage)
            }
            logger.info(f"Successful async connection test for {model}")
            return result

        except Exception as e:
            error_result = {
                "success": False,
                "model": model,
                "error": str(e)
            }
            logger.error(f"Async connection test failed for {model}: {e}")
            return error_result

# Initialize on import
try:
    OpenRouterIntegration.configure_openrouter()
except Exception as e:
    logger.error(f"Initialization error: {e}")