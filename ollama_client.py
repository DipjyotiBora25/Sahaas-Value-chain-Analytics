"""
Ollama External API Client for Cloud Deployment
Handles connection to external Ollama server (RunPod, Lambda Labs, etc.)
for AI-powered features in Streamlit Cloud.
"""

import os
import requests
import streamlit as st
from typing import Optional, Generator
from dotenv import load_dotenv

# Load environment variables from .env file (local development)
load_dotenv()


class OllamaClient:
    """Client for interacting with external Ollama API servers."""
    
    def __init__(self):
        """Initialize Ollama client with API URL from environment or Streamlit secrets."""
        # Try Streamlit secrets first (production), then environment variables (local dev)
        try:
            self.api_url = st.secrets.get("OLLAMA_API_URL", os.getenv("OLLAMA_API_URL"))
        except:
            self.api_url = os.getenv("OLLAMA_API_URL")
        
        self.model = os.getenv("OLLAMA_MODEL", "llama2")
        self.timeout = 120  # seconds
        self.is_available = False
        
        if self.api_url:
            self._check_health()
    
    def _check_health(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            response = requests.get(
                f"{self.api_url}/api/tags",
                timeout=5
            )
            self.is_available = response.status_code == 200
            return self.is_available
        except Exception as e:
            st.warning(f"⚠️ Ollama server unreachable: {str(e)}")
            self.is_available = False
            return False
    
    def get_available_models(self) -> list:
        """Fetch list of available models from Ollama server."""
        if not self.is_available:
            return []
        
        try:
            response = requests.get(
                f"{self.api_url}/api/tags",
                timeout=10
            )
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            return models
        except Exception as e:
            st.error(f"Failed to fetch models: {str(e)}")
            return []
    
    def generate(self, prompt: str, model: Optional[str] = None, stream: bool = False) -> Optional[str]:
        """
        Generate response from Ollama.
        
        Args:
            prompt: Input text prompt
            model: Model name (uses default if not specified)
            stream: Whether to stream response
        
        Returns:
            Generated text or None if error
        """
        if not self.is_available:
            st.error("❌ Ollama server not available. Check configuration.")
            return None
        
        model = model or self.model
        
        try:
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": stream
                },
                timeout=self.timeout,
                stream=stream
            )
            
            if response.status_code != 200:
                st.error(f"API Error: {response.status_code}")
                return None
            
            if stream:
                # Return streaming response
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        data = eval(line)  # Parse JSON from each line
                        full_response += data.get("response", "")
                return full_response
            else:
                data = response.json()
                return data.get("response", "")
        
        except requests.Timeout:
            st.error("⏱️ Request timeout. Ollama server is slow or unresponsive.")
            return None
        except Exception as e:
            st.error(f"❌ Error generating response: {str(e)}")
            return None
    
    def generate_streaming(self, prompt: str, model: Optional[str] = None) -> Generator[str, None, None]:
        """
        Stream response from Ollama in real-time.
        
        Args:
            prompt: Input text prompt
            model: Model name (uses default if not specified)
        
        Yields:
            Chunks of generated text
        """
        if not self.is_available:
            st.error("❌ Ollama server not available.")
            return
        
        model = model or self.model
        
        try:
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": True
                },
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code != 200:
                st.error(f"API Error: {response.status_code}")
                return
            
            for line in response.iter_lines():
                if line:
                    try:
                        data = eval(line)  # Parse JSON
                        chunk = data.get("response", "")
                        if chunk:
                            yield chunk
                    except:
                        continue
        
        except requests.Timeout:
            st.error("⏱️ Request timeout.")
            return
        except Exception as e:
            st.error(f"❌ Streaming error: {str(e)}")
            return
    
    def health_check(self) -> dict:
        """Return health status for dashboard display."""
        return {
            "available": self.is_available,
            "api_url": self.api_url if self.api_url else "Not configured",
            "model": self.model,
            "models": self.get_available_models() if self.is_available else []
        }


# Global instance (cached)
@st.cache_resource
def get_ollama_client() -> OllamaClient:
    """Get or create global Ollama client instance."""
    return OllamaClient()


def query_ollama_with_context(
    prompt: str,
    context: str = "",
    system_prompt: str = None
) -> Optional[str]:
    """
    High-level function to query Ollama with optional context and system prompt.
    
    Args:
        prompt: User's question
        context: Additional context (e.g., data summary)
        system_prompt: Custom system instructions
    
    Returns:
        Generated response or None
    """
    client = get_ollama_client()
    
    if not client.is_available:
        return None
    
    # Build full prompt
    full_prompt = ""
    if system_prompt:
        full_prompt += f"System: {system_prompt}\n\n"
    
    if context:
        full_prompt += f"Context: {context}\n\n"
    
    full_prompt += f"User: {prompt}"
    
    return client.generate(full_prompt)
