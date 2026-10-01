"""Constrained human-in-the-loop brochure layout commands via OpenRouter."""

import json

from .. import config
from . import llm


DEFAULT_LAYOUT_SETTINGS = {
    "hotel_image_alignment": "center",
    "hotel_image_width_percent": 45,
    "restaurant_map_width_percent": 100,
    "keep_restaurant_cards_together": True,
    "restaurant_heading_gap_pt": 14,
    "restaurant_card_gap_pt": 12,
}

_LAYOUT_TOOL = {
    "type": "function",
    "function": {
        "name": "update_brochure_layout",
        "description": (
            "Apply a small, safe brochure-layout adjustment. Use only fields needed "
            "by the user's request and retain all other current values."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "hotel_image_alignment": {
                    "type": "string",
                    "enum": ["center", "left", "right"],
                    "description": "Horizontal alignment for the hotel photo.",
                },
                "hotel_image_width_percent": {
                    "type": "integer",
                    "minimum": 25,
                    "maximum": 100,
                    "description": "Hotel photo width as a percentage of page width.",
                },
                "restaurant_map_width_percent": {
                    "type": "integer",
                    "minimum": 50,
                    "maximum": 100,
                    "description": "Restaurant-map width as a percentage of page width.",
                },
                "keep_restaurant_cards_together": {
                    "type": "boolean",
                    "description": "Keep an individual restaurant card on one page when it fits.",
                },
                "restaurant_heading_gap_pt": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 48,
                    "description": "Blank vertical space between a restaurant-type heading and its first card, in points.",
                },
                "restaurant_card_gap_pt": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 48,
                    "description": "Vertical space between complete restaurant cards, in points.",
                },
                "summary": {
                    "type": "string",
                    "description": "Brief, user-facing summary of the applied change.",
                },
            },
            "required": ["summary"],
            "additionalProperties": False,
        },
    },
}


def normalize_layout_settings(settings: dict | None) -> dict:
    """Return the supported layout settings with safe defaults and bounds."""
    source = settings if isinstance(settings, dict) else {}
    normalized = dict(DEFAULT_LAYOUT_SETTINGS)

    alignment = source.get("hotel_image_alignment")
    if alignment in {"center", "left", "right"}:
        normalized["hotel_image_alignment"] = alignment

    for key, minimum, maximum in (
        ("hotel_image_width_percent", 25, 100),
        ("restaurant_map_width_percent", 50, 100),
        ("restaurant_heading_gap_pt", 0, 48),
        ("restaurant_card_gap_pt", 0, 48),
    ):
        value = source.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            normalized[key] = max(minimum, min(maximum, round(value)))

    keep_together = source.get("keep_restaurant_cards_together")
    if isinstance(keep_together, bool):
        normalized["keep_restaurant_cards_together"] = keep_together

    return normalized


def apply_layout_request(message: str, current_settings: dict | None) -> tuple[dict, str]:
    """Interpret one layout request through a forced, validated tool call."""
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is required for brochure layout chat")
    if not message or not message.strip():
        raise ValueError("Enter a brochure layout request")

    current = normalize_layout_settings(current_settings)
    system_prompt = (
        "You are a brochure layout assistant. Interpret common document-layout commands. "
        "Always call update_brochure_layout. Do not write Typst, LaTeX, Markdown, code, "
        "or explanations outside the tool call. Do not modify textual brochure content. "
        "Page breaks are edited manually in the Markdown editor as visible \\newpage lines; do not manage "
        "page breaks. Supported changes include spacing after restaurant headings or between cards, "
        "card splitting, and hotel/map image alignment or width. "
        "The renderer already centers the hotel image and keeps restaurant cards together by default; "
        "preserve defaults unless the user explicitly requests a change."
    )
    user_prompt = (
        f"Current layout settings: {json.dumps(current)}\n\n"
        f"User request: {message.strip()}"
    )

    response = llm._get_client().chat.completions.create(
        model=config.OPENROUTER_LAYOUT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=[_LAYOUT_TOOL],
        tool_choice={"type": "function", "function": {"name": "update_brochure_layout"}},
        max_completion_tokens=300,
    )
    tool_calls = response.choices[0].message.tool_calls or []
    if not tool_calls or tool_calls[0].function.name != "update_brochure_layout":
        raise RuntimeError("The layout assistant did not return a valid layout operation")

    try:
        update = json.loads(tool_calls[0].function.arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The layout assistant returned invalid layout data") from exc

    merged = {**current, **{key: value for key, value in update.items() if key in current}}
    summary = str(update.get("summary", "Layout updated.")).strip()[:240] or "Layout updated."
    return normalize_layout_settings(merged), summary