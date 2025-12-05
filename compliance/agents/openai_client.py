"""
Azure OpenAI client for async LLM operations.
Provides a wrapper around Azure OpenAI API for policy extraction.
"""
import asyncio
import logging
from typing import Optional
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from common.config import settings

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Async client for Azure OpenAI API."""
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        api_version: Optional[str] = None,
        deployment_name: Optional[str] = None
    ):
        """
        Initialize Azure OpenAI client.
        
        Args:
            api_key: Azure OpenAI API key (defaults to settings.AZURE_OPENAI_API_KEY)
            endpoint: Azure OpenAI endpoint (defaults to settings.AZURE_OPENAI_ENDPOINT)
            api_version: API version (defaults to settings.AZURE_API_VERSION)
            deployment_name: Deployment name (defaults to settings.AZURE_DEPLOYMENT_NAME)
        """
        self.api_key = api_key or settings.AZURE_OPENAI_API_KEY
        self.endpoint = endpoint or settings.AZURE_OPENAI_ENDPOINT
        self.api_version = api_version or settings.AZURE_API_VERSION
        self.deployment_name = deployment_name or settings.AZURE_DEPLOYMENT_NAME
        
        if not self.api_key:
            raise ValueError("AZURE_OPENAI_API_KEY is required. Set it in environment variables or .env file")
        if not self.endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is required. Set it in environment variables or .env file")
        
        logger.info(f"Initializing Azure OpenAI client with endpoint: {self.endpoint}")
        logger.info(f"Using deployment: {self.deployment_name}")
    
    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        use_json_mode: bool = True
    ) -> str:
        """
        Generate content from Azure OpenAI API asynchronously.
        
        Args:
            prompt: The user prompt/input text
            system_instruction: Optional system instruction/context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (None for default)
            timeout: Request timeout in seconds
            use_json_mode: Whether to use JSON mode for structured output
            
        Returns:
            Generated text content
            
        Raises:
            ValueError: If API key is missing or request fails
            TimeoutError: If request times out
        """
        try:
            # Initialize the LLM
            model_kwargs = {}
            if use_json_mode:
                model_kwargs["response_format"] = {"type": "json_object"}
            
            llm = AzureChatOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint,
                azure_deployment=self.deployment_name,
                temperature=temperature,
                max_tokens=max_tokens,
                model_kwargs=model_kwargs
            )
            
            # Build messages
            messages = []
            if system_instruction:
                messages.append(SystemMessage(content=system_instruction))
            if prompt:
                messages.append(HumanMessage(content=prompt))
            
            # If both are empty, use a default prompt
            if not messages:
                messages.append(HumanMessage(content="Please provide a response."))
            
            # Call API with timeout
            result = await asyncio.wait_for(
                llm.ainvoke(messages),
                timeout=timeout
            )
            
            if not result.content:
                raise ValueError("Empty response from Azure OpenAI API")
            
            return result.content
            
        except asyncio.TimeoutError:
            logger.error(f"Azure OpenAI API request timed out after {timeout}s")
            raise TimeoutError(f"Azure OpenAI API request timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Azure OpenAI API error: {str(e)}")
            raise ValueError(f"Failed to generate content from Azure OpenAI API: {str(e)}")
    
    async def generate_content_with_retry(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        use_json_mode: bool = True,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ) -> str:
        """
        Generate content with automatic retry on failure.
        
        Args:
            prompt: The user prompt/input text
            system_instruction: Optional system instruction/context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            use_json_mode: Whether to use JSON mode
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
            
        Returns:
            Generated text content
            
        Raises:
            ValueError: If all retry attempts fail
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await self.generate_content(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    use_json_mode=use_json_mode
                )
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed")
        
        raise ValueError(f"Failed after {max_retries} attempts. Last error: {str(last_error)}")


# Global client instance (lazy initialization)
_client: Optional[OpenAIClient] = None


def get_openai_client() -> OpenAIClient:
    """
    Get or create the global OpenAI client instance.
    
    Returns:
        OpenAIClient instance
    """
    global _client
    if _client is None:
        _client = OpenAIClient()
    return _client

