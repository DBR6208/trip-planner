"""LLM interaction via OpenRouter API."""

from openai import OpenAI

from .. import config

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
        )
    return _client


def generate(
    prompt: str,
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int = 4000,
) -> str:
    """Generate text via OpenRouter/LLM.

    Args:
        prompt: The user message / main instruction.
        system_prompt: Optional system-level instruction.
        model: Model override (default from config).
        max_tokens: Max completion tokens.

    Returns:
        Generated text string.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = _get_client().chat.completions.create(
            model=model or config.OPENROUTER_MODEL,
            messages=messages,
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"Error generating response: {e}"


def generate_with_search(
    prompt: str,
    search_context: str,
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int = 2000,
) -> str:
    """Generate text with web search context injected."""
    full_prompt = f"""QUESTION:
{prompt}

WEB RESEARCH CONTEXT:
{search_context}

Provide a high-quality synthesized answer using the context above."""
    return generate(full_prompt, system_prompt=system_prompt, model=model, max_tokens=max_tokens)