"""OpenAI-compatible LLM client.

Responsibilities:
- Construct the DashScope/OpenAI-compatible client once from config.
- Provide a small ``chat_completion`` wrapper used by planner, repair, and summary code.

Used by:
- ``core.planner``, ``core.executor``, and ``render.summary``.
"""

from openai import OpenAI

from vega_agent.config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_TIMEOUT_SECONDS, MODEL_NAME


client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
)


def chat_completion(
    messages: list,
    temperature: float = 0.1,
    model: str | None = None,
    timeout: float | None = None,
    max_tokens: int | None = None,
) -> str:
    kwargs = {
        "model": model or MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "timeout": timeout or LLM_TIMEOUT_SECONDS,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    response = client.chat.completions.create(
        **kwargs
    )
    return response.choices[0].message.content.strip()
