"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
        "notes": [],                 # non-fatal events (e.g. fallback used)
    }


# ── query parsing ───────────────────────────────────────────────────────────--

def _parse_query(query: str) -> dict:
    """
    Extract a description, optional size, and optional max_price from the raw
    free-text query. Uses regex rather than an LLM call so parsing is fast and
    deterministic (see planning.md, State Management).

    Returns a dict: {"description": str, "size": str | None, "max_price": float | None}
    """
    working = query

    # Price: "under $30", "below 40", "$30" — capture the first number that follows
    # a price cue (or a bare "$N"). Strip the matched phrase from the description.
    max_price = None
    price_match = re.search(r"(?:under|below|less than|max)\s*\$?\s*(\d+(?:\.\d+)?)", working, re.I)
    if not price_match:
        price_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", working)
    if price_match:
        max_price = float(price_match.group(1))
        working = working.replace(price_match.group(0), " ")

    # Size: only when stated explicitly via "size X" / "in size X" — the dataset uses
    # mixed formats so we don't guess sizes from arbitrary tokens.
    size = None
    size_match = re.search(r"\bsize\s+([A-Za-z0-9/.]+)", working, re.I)
    if size_match:
        size = size_match.group(1)
        working = working.replace(size_match.group(0), " ")

    # Whatever remains, with filler price/size words cleaned up, is the description.
    description = re.sub(r"\s+", " ", working).strip(" ,.-")

    return {"description": description, "size": size, "max_price": max_price}


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: fresh session — single source of truth for this interaction.
    session = _new_session(query, wardrobe)

    # Step 2: parse the free-text query into structured search parameters.
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: search. search_listings runs its own size-drop fallback internally,
    # so an empty result here means nothing matched even after loosening.
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    # Early-exit on no match — do NOT run downstream LLM tools on empty input.
    if not results:
        session["error"] = (
            "No listings matched your search — try fewer keywords, a higher price, "
            "or dropping the size."
        )
        return session

    # If a size was requested but the top result doesn't satisfy it, the match came
    # from the fallback pass. Record that so the UI can surface it to the user.
    if parsed["size"] and parsed["size"].lower() not in results[0]["size"].lower():
        session["notes"].append(
            f"No exact match for size '{parsed['size']}' — showing the closest "
            "results with the size filter relaxed."
        )

    # Step 4: select the top-ranked listing for styling.
    session["selected_item"] = results[0]

    # Step 5: outfit suggestion (handles empty wardrobe internally).
    session["outfit_suggestion"] = suggest_outfit(session["selected_item"], wardrobe)

    # Step 6: fit card, gated on having an outfit suggestion to caption.
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 7: return the completed session.
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
