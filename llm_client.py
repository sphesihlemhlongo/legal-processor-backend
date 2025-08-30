import os
import time
import asyncio
import logging
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI
from logger_config import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

class LLMClient:
    """Handles Novita LLM API calls with proper error handling, retry logic, and streaming support"""

    def __init__(self):
        # Defaults
        self.default_model = os.getenv("NOVITA_MODEL", "deepseek/deepseek-v3.1")
        self.max_retries = 3
        self.base_delay = 1  # seconds

        # Novita client setup
        NOVITA_API_KEY = os.getenv("NOVITA_OPENAI_API_KEY")
        NOVITA_BASE_URL = os.getenv("NOVITA_BASE_URL", "https://api.novita.ai/openai")

        if not NOVITA_API_KEY:
            raise ValueError("Missing NOVITA_OPENAI_API_KEY in environment")

        self.client = OpenAI(
            base_url=NOVITA_BASE_URL,
            api_key=NOVITA_API_KEY,
        )

    async def call_llm_async(
        self,
        prompt: str,
        model: Optional[str] = None,
        stream: bool = False,
        max_tokens: int = 1000,
    ) -> str:
        """Async wrapper for LLM API calls"""
        return await asyncio.to_thread(
            self.call_llm, prompt, model, stream, max_tokens
        )

    def call_llm(
        self,
        prompt: str,
        model: Optional[str] = None,
        stream: bool = False,
        max_tokens: int = 1000,
    ) -> str:
        """Make a call to the Novita API"""
        if not model:
            model = self.default_model

        logger.info(f"LLM API call with model: {model}")
        logger.debug(f"Prompt length: {len(prompt)} characters")

        try:
            response = self._call_novita(prompt, model, stream, max_tokens)
            logger.info("LLM API call successful")
            return response

        except Exception as e:
            logger.error(f"LLM API call failed: {str(e)}")
            return self._retry_llm_call(prompt, model, stream, max_tokens)

    def _call_novita(
        self, prompt: str, model: str, stream: bool, max_tokens: int
    ) -> str:
        """Direct Novita API call"""
        chat_completion_res = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=stream,
            max_tokens=max_tokens,
            extra_body={},
        )

        if stream:
            result = ""
            for chunk in chat_completion_res:
                piece = chunk.choices[0].delta.content or ""
                print(piece, end="", flush=True)  # live streaming print
                result += piece
            print()  # newline after streaming
            return result
        else:
            return chat_completion_res.choices[0].message.content

    def _retry_llm_call(
        self, prompt: str, model: str, stream: bool, max_tokens: int
    ) -> str:
        """Retry Novita call with exponential backoff"""
        for attempt in range(self.max_retries):
            try:
                delay = self.base_delay * (2 ** attempt)
                logger.info(
                    f"Retrying LLM call (attempt {attempt + 1}/{self.max_retries}) after {delay}s"
                )
                time.sleep(delay)

                return self._call_novita(prompt, model, stream, max_tokens)

            except Exception as e:
                logger.warning(f"Retry {attempt + 1} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise

        raise Exception("Max retries exceeded")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for prompt planning"""
        return len(text) // 4  # Rough approximation

    def check_token_limit(self, prompt: str, model: str = "deepseek/deepseek-r1-distill-llama-8b") -> bool:
        """Check if prompt exceeds model token limits"""
        estimated_tokens = self.estimate_tokens(prompt)

        limits = {
            "deepseek/deepseek-r1-distill-llama-8b": 8192,  # safe default
            "gpt-4": 8000,
            "gpt-3.5-turbo": 4000,
            "gpt-4-32k": 32000,
        }

        limit = limits.get(model, 4000)
        return estimated_tokens < limit * 0.8
