from typing import Optional, Generator
import hashlib
from groq import Groq
from config.settings import settings
from utils.logger import logger

LLM_CACHE = {}
MAX_CACHE_SIZE = 1000


class LLMService:
    def __init__(self):
        self.api_key = settings.groq_api_key
        if not self.api_key:
            logger.error("Groq API key not set for LLM")
        self.client = Groq(api_key=self.api_key)
        self.model = settings.llm_model

    def _get_cache_key(self, query: str, context: str) -> str:
        combined = f"{query}:{context}"
        return hashlib.md5(combined.encode()).hexdigest()

    def generate_answer(self, query: str, context: str) -> Optional[str]:
        cache_key = self._get_cache_key(query, context)
        
        if cache_key in LLM_CACHE:
            logger.info(f"Cache hit for query")
            return LLM_CACHE[cache_key]
        
        if not self.api_key:
            logger.error("API key not available for LLM generation")
            return None

        prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {query}

Answer:
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1
            )
            answer = response.choices[0].message.content.strip()
            
            if len(LLM_CACHE) >= MAX_CACHE_SIZE:
                LLM_CACHE.clear()
            LLM_CACHE[cache_key] = answer
            
            return answer
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return None

    def stream_answer(self, query: str, context: str) -> Generator[str, None, None]:
        cache_key = self._get_cache_key(query, context)
        
        if cache_key in LLM_CACHE:
            logger.info(f"Cache hit for query")
            yield LLM_CACHE[cache_key]
            return
        
        if not self.api_key:
            logger.error("API key not available for LLM generation")
            return

        prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {query}

Answer:
"""

        try:
            full_answer = ""
            for chunk in self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1,
                stream=True
            ):
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_answer += content
                    yield content
            
            if full_answer and cache_key not in LLM_CACHE:
                if len(LLM_CACHE) >= MAX_CACHE_SIZE:
                    LLM_CACHE.clear()
                LLM_CACHE[cache_key] = full_answer
                
        except Exception as e:
            logger.error(f"Error streaming answer: {e}")