import os
import json
import httpx
from typing import Optional, Dict, Any, List

class LLMClient:
    """Hybrid LLM provider: Supports Gemini API, OpenAI-compatible APIs, local Ollama, or heuristic fallback."""

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    @property
    def is_available(self) -> bool:
        return bool(self.gemini_key or self.openai_key)

    async def generate_executive_pulse(self, topic: str, verified_items_summary: str) -> Optional[str]:
        """Synthesize a high-level executive pulse across all verified technologies."""
        prompt = (
            f"You are a Principal Software Architect. Synthesize a 3-bullet Executive Pulse on the latest developments in '{topic}'.\n\n"
            f"Verified findings:\n{verified_items_summary}\n\n"
            "Format exactly as 3 punchy bullet points starting with '* ' highlighting: "
            "1) Major architectural pattern, 2) Most significant project/breakthrough, 3) Actionable recommendation."
        )

        return await self._call_llm(prompt)

    async def analyze_technical_differentiator(self, title: str, snippet: str, category: str) -> Optional[str]:
        """Explain why a specific technology matters and what makes it distinct."""
        prompt = (
            f"Analyze this new technology candidate in category '{category}':\n"
            f"Title: {title}\n"
            f"Description: {snippet}\n\n"
            "In 1-2 concise sentences, state the core engineering value proposition and architectural trade-off. "
            "Avoid marketing buzzwords. Focus on mechanics."
        )

        return await self._call_llm(prompt)

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Route prompt to configured LLM provider, or return None for graceful heuristic fallback."""
        if self.gemini_key:
            return await self._call_gemini(prompt)
        elif self.openai_key:
            return await self._call_openai(prompt)
        return None

    async def _call_gemini(self, prompt: str) -> Optional[str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400}
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
        except Exception:
            pass
        return None

    async def _call_openai(self, prompt: str) -> Optional[str]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.openai_key}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 400
        }
        try:
            async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
        except Exception:
            pass
        return None
