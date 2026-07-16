"""
LLM Configuration - Ollama (local, gratuito)

Usage:
    from lib.llm import get_llm

    llm = get_llm()  # Usa Ollama por padrão
    response = llm.generate("Hello!")
"""

import os
import requests
from typing import Optional

# Default to Ollama for local/testing
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "llama3.2"
DEFAULT_BASE_URL = "http://localhost:11434"


class LLMClient:
    """
    Simple LLM client for Ollama.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048
    ) -> str:
        """
        Generate response from Ollama.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Returns:
            Generated text response
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
        except Exception as e:
            return f"Error: {e}"

    def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


# Singleton instance
_llm_client: Optional[LLMClient] = None


def get_llm(
    base_url: Optional[str] = None,
    model: Optional[str] = None
) -> LLMClient:
    """
    Get the global LLM client instance.

    Uses environment variables if available:
    - OLLAMA_BASE_URL (default: http://localhost:11434)
    - OLLAMA_MODEL (default: llama3.2)
    """
    global _llm_client

    if _llm_client is None:
        _llm_client = LLMClient(
            base_url=base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL),
            model=model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
            api_key=os.getenv("OLLAMA_API_KEY")
        )

    return _llm_client


def reset_llm():
    """Reset the LLM client (useful for testing)."""
    global _llm_client
    _llm_client = None
