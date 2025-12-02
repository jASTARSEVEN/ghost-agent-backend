"""
Gemini API client for async LLM operations.
Provides a wrapper around Google's Gemini API for policy extraction.
"""
import asyncio
import logging
from typing import Optional
import google.generativeai as genai
from common.config import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """Async client for Google Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Gemini API key (defaults to settings.GEMINI_API_KEY)
            model_name: Model name to use (defaults to settings.GEMINI_MODEL)
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required. Set it in environment variables or .env file")
        
        # Configure the API
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
    
    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0
    ) -> str:
        """
        Generate content from Gemini API asynchronously.
        
        Args:
            prompt: The user prompt/input text
            system_instruction: Optional system instruction/context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (None for default)
            timeout: Request timeout in seconds
            
        Returns:
            Generated text content
            
        Raises:
            ValueError: If API key is missing or request fails
            TimeoutError: If request times out
        """
        try:
            # Run the synchronous API call in a thread executor
            def _generate_sync():
                generation_config = {
                    "temperature": temperature,
                }
                if max_tokens:
                    generation_config["max_output_tokens"] = max_tokens
                
                # Build the full prompt with system instruction if provided
                full_prompt = prompt
                if system_instruction:
                    full_prompt = f"{system_instruction}\n\n{prompt}"
                
                response = self.model.generate_content(
                    full_prompt,
                    generation_config=generation_config
                )
                
                if not response.text:
                    raise ValueError("Empty response from Gemini API")
                
                return response.text
            
            # Run in executor with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(_generate_sync),
                timeout=timeout
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Gemini API request timed out after {timeout}s")
            raise TimeoutError(f"Gemini API request timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise ValueError(f"Failed to generate content from Gemini API: {str(e)}")
    
    def generate_content_sync(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate content from Gemini API synchronously (for testing/debugging).
        
        Args:
            prompt: The user prompt/input text
            system_instruction: Optional system instruction/context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (None for default)
            
        Returns:
            Generated text content
        """
        generation_config = {
            "temperature": temperature,
        }
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens
        
        full_prompt = prompt
        if system_instruction:
            full_prompt = f"{system_instruction}\n\n{prompt}"
        
        response = self.model.generate_content(
            full_prompt,
            generation_config=generation_config
        )
        
        if not response.text:
            raise ValueError("Empty response from Gemini API")
        
        return response.text


# Global client instance (lazy initialization)
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """
    Get or create the global Gemini client instance.
    
    Returns:
        GeminiClient instance
    """
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client

