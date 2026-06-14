"""
tests/test_tools.py

Milestone 5 — graceful error and failure validation.

These tests assert that the three FitFindr tools behave gracefully at their
boundaries without crashing. The two LLM-backed tools (suggest_outfit,
create_fit_card) make REAL Groq API calls, so a valid GROQ_API_KEY and network
access are required to run the full suite.

Run with:
    pytest -q
"""

import os
import sys

import pytest

# Make the project root importable when pytest is run from inside tests/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools import search_listings, suggest_outfit, create_fit_card  # noqa: E402
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe  # noqa: E402

# LLM tests are skipped (not failed) when no key is configured, so the pure-logic
# tests still run in a keyless environment.
_HAS_KEY = bool(os.environ.get("GROQ_API_KEY"))
requires_groq = pytest.mark.skipif(not _HAS_KEY, reason="GROQ_API_KEY not set")


# ── 1. Happy-path search ──────────────────────────────────────────────────────

def test_happy_path_search_returns_matches():
    """Matching keywords return a non-empty, well-formed list of listings."""
    results = search_listings("vintage graphic tee", size=None, max_price=30.0)

    assert isinstance(results, list)
    assert len(results) > 0
    # Every match respects the price ceiling and carries the expected fields.
    for listing in results:
        assert listing["price"] <= 30.0
        assert "title" in listing and "platform" in listing


# ── 2. Stretch fallback execution ─────────────────────────────────────────────

def test_fallback_drops_size_when_no_exact_match():
    """An impossible size paired with valid keywords should trigger the size-drop
    fallback and still return data instead of an empty list."""
    # No listing is size "XXS", but "graphic tee" matches several items.
    results = search_listings("graphic tee", size="XXS", max_price=None)

    assert isinstance(results, list)
    assert len(results) > 0  # fallback recovered matches by dropping the size filter


def test_no_results_returns_empty_list_safely():
    """A genuinely impossible search returns [] rather than raising."""
    results = search_listings("designer ballgown", size="XXS", max_price=5.0)
    assert results == []


# ── 3. Empty-wardrobe handler ─────────────────────────────────────────────────

@requires_groq
def test_empty_wardrobe_returns_styling_text():
    """An empty wardrobe yields non-empty general styling advice, not a crash."""
    item = {
        "title": "Y2K Baby Tee — Butterfly Print",
        "category": "tops",
        "style_tags": ["y2k", "vintage"],
        "colors": ["white"],
        "price": 18.0,
        "platform": "depop",
    }
    advice = suggest_outfit(item, get_empty_wardrobe())

    assert isinstance(advice, str)
    assert advice.strip() != ""


@requires_groq
def test_populated_wardrobe_returns_styling_text():
    """A populated wardrobe also returns non-empty styling text."""
    item = {
        "title": "Y2K Baby Tee — Butterfly Print",
        "category": "tops",
        "style_tags": ["y2k", "vintage"],
        "colors": ["white"],
        "price": 18.0,
        "platform": "depop",
    }
    advice = suggest_outfit(item, get_example_wardrobe())

    assert isinstance(advice, str)
    assert advice.strip() != ""


# ── 4. Empty-output validation guard ──────────────────────────────────────────

def test_empty_outfit_falls_back_to_baseline_card():
    """An empty/whitespace outfit returns a safe fallback caption built from the
    item attributes — no LLM call, no crash."""
    item = {"title": "Vintage Band Tee", "price": 24.0, "platform": "depop"}

    for bad_outfit in ["", "   ", None]:
        card = create_fit_card(bad_outfit, item)
        assert isinstance(card, str)
        assert card.strip() != ""
        # Fallback references the item's raw attributes.
        assert "Vintage Band Tee" in card
        assert "depop" in card
