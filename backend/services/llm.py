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
    """Generate text via OpenRouter/LLM with automatic fallback on overload.

    Tries the requested model (or default from config). If the response is
    empty or the model is overloaded / rate-limited, retries once with
    FALLBACK_MODEL silently.

    Args:
        prompt: The user message / main instruction.
        system_prompt: Optional system-level instruction.
        model: Model override (default from config).
        max_tokens: Max completion tokens.

    Returns:
        Generated text string.
    """
    models_to_try = [
        model or config.OPENROUTER_MODEL,
        config.FALLBACK_MODEL,
    ]

    last_error = ""
    for attempt, m in enumerate(models_to_try):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = _get_client().chat.completions.create(
                model=m,
                messages=messages,
                max_completion_tokens=max_tokens,
            )
            content = (response.choices[0].message.content or "").strip()
            if content:
                if attempt > 0:
                    print(
                        f"[llm] Primary model '{models_to_try[0]}' failed; "
                        f"fell back to '{m}'"
                    )
                return content

            last_error = "empty response"

        except Exception as e:
            err = str(e).lower()
            # Fall through for transient provider/network failures.
            if any(
                token in err
                for token in [
                    "503", "overloaded", "overloaded_error",
                    "429", "rate limit", "rate_limit",
                    "502", "bad gateway",
                    "timeout", "timed out",
                    "connection error", "api connection error",
                    "connectionreset", "connection reset",
                    "dns", "name resolution",
                ]
            ):
                last_error = str(e)
                print(
                    f"[llm] Model '{m}' failed ({last_error}); "
                    f"trying fallback..."
                )
                continue  # try next model
            # Other errors (auth, bad request, etc.) — don't retry
            return f"Error generating response: {e}"

        # Empty content on a non-overloaded response — try fallback anyway
        if not content:
            last_error = "empty content"
            if attempt == 0:
                print(
                    f"[llm] Model '{m}' returned empty content; "
                    f"trying fallback..."
                )
                continue

    # Both models failed
    return f"Error generating response: {last_error}"


def generate_with_search(
    prompt: str,
    search_context: str,
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int = 2000,
) -> str:
    """Generate text with web search context injected."""
    if search_context and search_context.strip():
        full_prompt = f"""QUESTION:
{prompt}

WEB RESEARCH CONTEXT:
{search_context}

Provide a high-quality synthesized answer using the context above."""
    else:
        full_prompt = f"""QUESTION:
{prompt}

Answer concisely and factually. Do NOT ask for additional context, research material,
or information to be supplied — just answer based on what you know."""
    return generate(full_prompt, system_prompt=system_prompt, model=model, max_tokens=max_tokens)
