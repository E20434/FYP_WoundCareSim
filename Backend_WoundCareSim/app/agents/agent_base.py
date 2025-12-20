from abc import ABC
from typing import Optional

from openai import OpenAI

from app.core.config import (
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
)


class BaseAgent(ABC):
    """
    Base class for all evaluator agents.
    Handles ONLY LLM execution.
    No RAG, no scoring, no state logic.
    """

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_CHAT_MODEL

    async def run(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """
        Executes an OpenAI Responses API call.

        Args:
            system_prompt: Instructions defining evaluator role & constraints
            user_prompt: Concrete evaluation task + context
            temperature: Low temperature for deterministic evaluation

        Returns:
            Raw assistant text (structured, but not parsed here)
        """

        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=temperature,
        )

        # Extract assistant text safely
        output_text = ""

        for item in response.output:
            if item["type"] == "message":
                for content in item["content"]:
                    if content["type"] == "output_text":
                        output_text += content["text"]

        return output_text.strip()
