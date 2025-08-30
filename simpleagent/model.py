from __future__ import annotations
import os
from typing import Optional
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

class LLM:
    def __init__(self, provider: str, model_name: str, max_tokens: int):
        self.provider = provider
        self.model_name = model_name
        self.max_tokens = max_tokens

        if provider in {"ollama", "local"}:
            base_url = (
                os.getenv("OLLAMA_BASE_URL")
                or "http://localhost:11434"
            )
            self.llm = ChatOllama(model=model_name, base_url=base_url)

        # Default to Anthropic
        self.llm = ChatAnthropic(model_name=model_name, max_tokens=max_tokens)

    def set_system_prompt(self, system_prompt: str):
        self.system_prompt = system_prompt

    def call_llm(self, prompt: str, temperature=0.2) -> str:
        msgs = [
            SystemMessage(
                content=(
                    self.system_prompt
                )
            ),
            HumanMessage(content=prompt),
        ]
        r = self.llm.with_config({"temperature": temperature}).invoke(msgs)
        txt = getattr(r, "content", "")
        if isinstance(txt, list):
            # Some LC message content may be list of chunks
            txt = "".join(getattr(c, "content", str(c)) for c in txt)
        return (txt or "").strip()


