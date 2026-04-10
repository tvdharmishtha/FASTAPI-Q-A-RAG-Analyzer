from typing import Optional, Generator
import hashlib
import os
import pickle
from groq import Groq
from config.settings import settings
from utils.logger import logger

LLM_CACHE = {}
MAX_CACHE_SIZE = 1000
CACHE_FILE = "llm_cache.pkl"

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, 'rb') as f:
            LLM_CACHE = pickle.load(f)
    except Exception as e:
        logger.error(f"Failed to load LLM cache: {e}")


def clear_llm_cache() -> int:
    """Clear the LLM response cache from memory and disk."""
    entries_removed = len(LLM_CACHE)
    LLM_CACHE.clear()
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
    except Exception as e:
        logger.error(f"Failed to remove LLM cache file: {e}")
    return entries_removed


class LLMService:
    def __init__(self):
        self.api_key = settings.groq_api_key
        if not self.api_key:
            logger.error("Groq API key not set for LLM")
        self.client = Groq(api_key=self.api_key)
        self.model = settings.llm_model

    def _save_cache(self):
        try:
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(LLM_CACHE, f)
        except Exception as e:
            logger.error(f"Failed to save LLM cache: {e}")

    def _get_cache_key(self, query: str, context: str) -> str:
        combined = f"{query}:{context}"
        return hashlib.md5(combined.encode()).hexdigest()

    def generate_answer(self, query: str, context: str) -> Optional[str]:
        cache_key = self._get_cache_key(query, context)

        if cache_key in LLM_CACHE:
            logger.info(f"Cache hit for query")
            return "⚡ [Loaded from Cache] " + LLM_CACHE[cache_key]

        if not self.api_key:
            logger.error("API key not available for LLM generation")
            return None

        prompt = f"""Based on the following context, answer the question accurately and concisely.

Context:
{context}

Question: {query}

Instructions:
1. If the context does not contain relevant information or the question is completely unrelated, you MUST reply EXACTLY with "I don't know based on the provided documents" and nothing else.
2. If you do find relevant information, provide a clear, accurate answer based only on the provided context. Do not add external knowledge or assumptions.
3. Keep your answer concise but complete.
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
            self._save_cache()

            return answer
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return None

    def stream_answer(self, query: str, context: str) -> Generator[str, None, None]:
        cache_key = self._get_cache_key(query, context)

        if cache_key in LLM_CACHE:
            logger.info(f"Cache hit for query")
            yield "⚡ [Loaded from Cache] " + LLM_CACHE[cache_key]
            return

        if not self.api_key:
            logger.error("API key not available for LLM generation")
            return

        prompt = f"""Based on the following context, answer the question accurately and concisely.

Context:
{context}

Question: {query}

Instructions:
1. If the context does not contain relevant information or the question is completely unrelated, you MUST reply EXACTLY with "I don't know based on the provided documents" and nothing else.
2. If you do find relevant information, provide a clear, accurate answer based only on the provided context. Do not add external knowledge or assumptions.
3. Keep your answer concise but complete.
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
                self._save_cache()

        except Exception as e:
            logger.error(f"Error streaming answer: {e}")
            yield f"Error: Failed to generate answer due to {str(e)}"
