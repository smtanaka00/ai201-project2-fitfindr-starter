# FitFindr — Implementation Plan & Tracker

This document is the **feature definition** and **implementation tracker** for the FitFindr
multi-tool agent. It mirrors the project milestones and records what is done, in progress,
and still pending. Update the status table as work lands.

**Decisions locked for this build:**
- **UI input model:** single freeform query box (existing `app.py` layout preserved).
  `agent.py` parses the query into `description` / `size` / `max_price`.
- **Tests:** Milestone 5 tests make **real Groq API calls** (need a live `GROQ_API_KEY`
  and network). Kept minimal and assertion-light to limit quota/flakiness.
- **Model:** `llama-3.3-70b-versatile` on Groq for both LLM tools.

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Done — implemented and smoke-tested |
| 🟡 | In progress |
| ⬜ | Not started |

---

## Milestone Status Overview

| Milestone | Feature | File(s) | Status |
|-----------|---------|---------|--------|
| M1 & M2 | Tool specs, state paths, planning-loop docs | `planning.md` | ✅ |
| M3.1 | `search_listings` keyword + price + size match | `tools.py` | ✅ |
| M3.1 | `search_listings` retry/fallback (drop size) | `tools.py` | ✅ |
| M3.2 | `suggest_outfit` (Groq, wardrobe-aware) | `tools.py` | ✅ |
| M3.2 | `suggest_outfit` empty-wardrobe handler | `tools.py` | ✅ |
| M3.3 | `create_fit_card` (Groq, temp 0.9) | `tools.py` | ✅ |
| M3.3 | `create_fit_card` empty-outfit fallback | `tools.py` | ✅ |
| M4.1 | `run_agent` planning loop + session state | `agent.py` | ✅ |
| M4.1 | Query parsing (description/size/max_price) | `agent.py` | ✅ |
| M4.1 | Early-exit on empty search + `notes` on fallback | `agent.py` | ✅ |
| M4.2 | `handle_query` input cleaning + panel mapping | `app.py` | ✅ |
| M5 | Happy-path search test | `tests/test_tools.py` | ✅ |
| M5 | Fallback execution test | `tests/test_tools.py` | ✅ |
| M5 | Empty-wardrobe handler test | `tests/test_tools.py` | ✅ |
| M5 | Empty-output guard test | `tests/test_tools.py` | ✅ |
| M6 | README (all required sections) | `README.md` | ✅ |
| M6 | Demo video script | `script.md` | ✅ |
| M6 | App verified running at :7860 | `app.py` | ✅ |
| M6 | Forked repo + push to smtanaka00 | GitHub | 🟡 |
| M6 | Record demo video | — | ⬜ (user) |

---

## System Architecture

```text
User Request Input (freeform query + wardrobe choice)
    │
    ▼
Planning Loop Execution (agent.py)
    │
    ├─► Parse query → {description, size, max_price}  →  session["parsed"]
    │
    ├─► Step 1: search_listings(description, size, max_price)
    │       ├──► [No match] → fallback: drop size, re-run (keywords + price kept)
    │       │       └──► still empty? → session["error"], terminate early
    │       └──► [Match] → session["selected_item"]  (+ session["notes"] if fallback used)
    │
    ├─► Step 2: suggest_outfit(selected_item, wardrobe)
    │       ├──► [Empty wardrobe] → general LLM styling advice
    │       └──► session["outfit_suggestion"]
    │
    └─► Step 3: create_fit_card(outfit, selected_item)
            ├──► [Empty/failed outfit] → fallback card from raw item attributes
            └──► session["fit_card"]
                                        │
                                        ▼
                            Return session state object
```

---

## Milestones 1 & 2 — Architectural Specs (`planning.md`)

Document tool specs, state management, and conditional planning loops before code generation.

### Tool 1: `search_listings`
- **Inputs:** `description` (str), `size` (str | None), `max_price` (float | None)
- **Returns:** `list[dict]` sorted by relevance, best first
- **Failure / stretch:** empty result → drop `size`, keep keywords + price, re-run.
  Flag fallback in session state. Still empty → stop safely (return `[]`).

### Tool 2: `suggest_outfit`
- **Inputs:** `new_item` (dict), `wardrobe` (dict)
- **Returns:** `str` styling guide pairing the item with wardrobe pieces
- **Failure:** empty wardrobe → LLM general styling heuristics for `new_item`.

### Tool 3: `create_fit_card`
- **Inputs:** `outfit` (str), `new_item` (dict)
- **Returns:** `str` casual social-media micro-caption
- **Failure:** missing/error outfit → fallback card built from raw item attributes.

---

## Milestone 3 — Isolated Tool Implementation (`tools.py`)

1. **`search_listings`** — keyword overlap scoring against listing fields, strict price
   filter, case-insensitive size substring filter, fallback that drops size when empty.
   Never raises; returns `[]` when truly nothing matches.
2. **`suggest_outfit`** — Groq `llama-3.3-70b-versatile`, structured prompt with item +
   wardrobe context, distinct prompt branch for empty wardrobe.
3. **`create_fit_card`** — Groq `llama-3.3-70b-versatile`, temperature `0.9`, short casual
   caption, guarded fallback when outfit is missing/whitespace.

---

## Milestone 4 — Planning Loop Orchestration (`agent.py` & `app.py`)

1. **`run_agent`** — init session (incl. `notes`), parse query, run `search_listings`,
   early-exit to `session["error"]` on empty, record fallback in `session["notes"]`,
   run `suggest_outfit` then `create_fit_card` conditionally on prior success.
2. **`handle_query`** — clean raw inputs (empty → `None`), select wardrobe, call
   `run_agent`, map session keys onto the three UI panels; route `error` to panel 1.

---

## Milestone 5 — Tests (`tests/test_tools.py`, pytest, real Groq calls)

1. **Happy-path search** — matching keywords return non-empty, well-formed listings.
2. **Fallback execution** — impossible size + valid text triggers retry and returns data.
3. **Empty-wardrobe handler** — empty wardrobe yields non-empty styling text, no crash.
4. **Empty-output guard** — empty/invalid outfit yields safe fallback card text.

---

## Open Items / Notes

- `session` schema gains a `notes` field (added to `_new_session`) to record fallback use.
- `tests/` directory does not exist yet — created in Milestone 5.
- Size matching is case-insensitive substring (e.g. `"M"` matches `"S/M"`), since the
  dataset uses mixed formats (`S/M`, `XL (oversized)`, `W30 L30`, `US 8`).
