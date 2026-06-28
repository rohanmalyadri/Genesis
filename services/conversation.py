import redis.asyncio as redis
import json
from typing import List
from datetime import datetime
from app.config import settings
from app.models import Message

class ConversationMemory:
    def __init__(self):
        self.redis = None
        self.local_mem = {} # session_id -> List[Message]
        self.is_connected = False
        
        try:
            self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception as e:
            print(f"ConversationMemory: Failed to init Redis: {e}")

    async def _check_conn(self):
        if self.is_connected:
            return True
        if not self.redis:
            return False
        try:
            await self.redis.ping()
            self.is_connected = True
            return True
        except Exception:
            self.is_connected = False
            return False

    async def add_message(self, session_id: str, message: Message):
        if await self._check_conn():
            try:
                key = f"conv:{session_id}"
                await self.redis.zadd(key, {message.model_dump_json(): message.timestamp.timestamp()})
                await self.redis.zremrangebyrank(key, 0, -11) # Keep last 10
                await self.redis.expire(key, 3600)
            except Exception as e:
                print(f"ConversationMemory add_message error: {e}")
        
        if session_id not in self.local_mem:
            self.local_mem[session_id] = []
        self.local_mem[session_id].append(message)
        self.local_mem[session_id] = self.local_mem[session_id][-10:]

    async def get_context(self, session_id: str, last_n: int = 3) -> List[Message]:
        if await self._check_conn():
            try:
                key = f"conv:{session_id}"
                data = await self.redis.zrange(key, -last_n, -1)
                return [Message(**json.loads(m)) for m in data]
            except Exception as e:
                print(f"ConversationMemory get_context error: {e}")
        
        return self.local_mem.get(session_id, [])[-last_n:]

    async def rewrite_query(self, session_id: str, query: str) -> str:
        """Rewrite the query to be self-contained based on conversation context."""
        context = await self.get_context(session_id, last_n=3)
        if not context:
            return query
            
        import google.generativeai as genai
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        
        context_str = "\n".join([f"{m.role}: {m.content}" for m in context])
        prompt = f"""Given the following conversation history and a new query, rewrite the query to be a standalone search query that contains all necessary context from the conversation. 
If the query is already standalone, return it as is.
DO NOT answer the query, just rewrite it.

History:
{context_str}

New Query: {query}
Standalone Query:"""

        try:
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
            rewritten = response.text.strip()
            print(f"ConversationMemory: Rewrote '{query}' -> '{rewritten}'")
            return rewritten
        except Exception as e:
            print(f"ConversationMemory: Rewrite error: {e}")
            return query

conversation_memory = ConversationMemory()
