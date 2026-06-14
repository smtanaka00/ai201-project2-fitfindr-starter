"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

# Single model used for both LLM-backed tools.
_MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """

    def _run_match(apply_size_filter: bool) -> list[dict]:
        """Score and filter listings. `apply_size_filter` lets the caller re-run
        without the size constraint for the fallback pass."""
        # Tokenize the free-text query into lowercase keywords; ignore very short
        # tokens (e.g. "a", "of") so they don't inflate every listing's score.
        keywords = [w for w in re.findall(r"[a-z0-9]+", description.lower()) if len(w) > 2]

        results = []
        for listing in load_listings():
            # Strict price ceiling — drop anything above max_price before scoring.
            if max_price is not None and listing["price"] > max_price:
                continue

            # Case-insensitive substring size match (e.g. "M" matches "S/M").
            if apply_size_filter and size:
                if size.lower() not in listing["size"].lower():
                    continue

            # Relevance = number of query keywords found anywhere in the listing's
            # searchable text (title + description + style tags + category).
            haystack = " ".join([
                listing["title"],
                listing["description"],
                " ".join(listing["style_tags"]),
                listing["category"],
            ]).lower()
            score = sum(1 for kw in keywords if kw in haystack)

            # Skip listings with no keyword overlap at all.
            if score == 0:
                continue

            results.append((score, listing))

        # Highest score first; the original order is otherwise preserved.
        results.sort(key=lambda pair: pair[0], reverse=True)
        return [listing for _, listing in results]

    # Primary pass honours every supplied constraint.
    matches = _run_match(apply_size_filter=True)

    # Retry-with-fallback: if nothing matched and a size filter was in play, drop
    # the size constraint (keeping keywords + price) and try once more.
    if not matches and size:
        matches = _run_match(apply_size_filter=False)

    return matches


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()

    # Compact, readable summary of the new item for the prompt.
    item_summary = (
        f"{new_item.get('title', 'item')} "
        f"(category: {new_item.get('category', 'n/a')}, "
        f"style: {', '.join(new_item.get('style_tags', [])) or 'n/a'}, "
        f"colors: {', '.join(new_item.get('colors', [])) or 'n/a'})"
    )

    items = wardrobe.get("items", []) if wardrobe else []

    # Two prompt variants: one when we have wardrobe pieces to pair against, and
    # a general-styling variant when the wardrobe is empty.
    if items:
        wardrobe_lines = "\n".join(
            f"- {it['name']} ({it['category']}; {', '.join(it.get('style_tags', []))})"
            for it in items
        )
        prompt = (
            f"A shopper is considering this secondhand item:\n{item_summary}\n\n"
            f"Their current wardrobe:\n{wardrobe_lines}\n\n"
            "Suggest 1-2 complete outfits that pair the new item with specific pieces "
            "from their wardrobe. Name the wardrobe pieces you use. Keep it concise and "
            "practical."
        )
    else:
        prompt = (
            f"A shopper is considering this secondhand item:\n{item_summary}\n\n"
            "They have not entered a wardrobe yet. Give general styling advice: what kinds "
            "of pieces pair well with it, what vibe it suits, and how to wear it. Keep it "
            "concise and practical."
        )

    response = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    title = new_item.get("title", "this find")
    price = new_item.get("price")
    platform = new_item.get("platform", "secondhand")

    # Deterministic fallback used whenever we can't produce a real caption — built
    # purely from the item's raw attributes so it never depends on the LLM.
    price_text = f"${price:g}" if isinstance(price, (int, float)) else "a steal"
    fallback = (
        f"Thrifted gem alert: the {title} for {price_text} on {platform}. "
        "Secondhand never looked this good. ✨"
    )

    # Guard against a missing or whitespace-only outfit before spending an LLM call.
    if not outfit or not outfit.strip():
        return fallback

    prompt = (
        f"Item: {title} (${price_text}, found on {platform}).\n"
        f"Outfit: {outfit}\n\n"
        "Write a short, casual OOTD-style caption (2-4 sentences) for a social post about "
        "this thrifted find. Mention the item name, price, and platform naturally, once "
        "each. Capture the outfit vibe in specific terms. Sound like a real person, not a "
        "product listing. Return only the caption text."
    )

    # Higher temperature for variety across repeated calls; any LLM/transport error
    # degrades gracefully to the attribute-based fallback rather than raising.
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )
        caption = response.choices[0].message.content
        return caption.strip() if caption and caption.strip() else fallback
    except Exception:
        return fallback
