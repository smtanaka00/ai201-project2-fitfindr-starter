# FitFindr

FitFindr is a multi-tool AI agent that helps you shop secondhand. You describe what you
want in plain language ("vintage graphic tee under $30"), and the agent finds a matching
thrift listing, suggests how to style it against your existing wardrobe, and writes a
shareable "fit card" caption for it.

It runs a small, deterministic **planning loop** over three tools — a keyword search, an
LLM stylist, and an LLM caption writer — passing state between them through a single session
object.

---

## Setup & Running

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with a Groq API key
(free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=gsk_your_key_here
```

Run the app:

```bash
python app.py
```

Then open the URL printed in your terminal (usually <http://localhost:7860>, but check the
output — the port can differ).

Run the tests:

```bash
pytest -q
```

---

## Tool Inventory

The agent uses three tools, all defined in [`tools.py`](tools.py). The signatures below match
the actual function definitions.

### 1. `search_listings`
- **Inputs:**
  - `description` (str) — free-text keywords describing the desired item.
  - `size` (str | None) — size to filter by; case-insensitive substring match (e.g. `"M"`
    matches `"S/M"`). `None` skips size filtering.
  - `max_price` (float | None) — inclusive price ceiling. `None` skips price filtering.
- **Output:** `list[dict]` — matching listings sorted by relevance (best first). Each dict
  has `id, title, description, category, style_tags, size, condition, price, colors, brand,
  platform`. Returns `[]` when nothing matches; never raises.
- **Purpose:** Find candidate listings in the mock dataset. Pure Python (no LLM) — scores
  each listing by how many query keywords appear in its searchable text.

### 2. `suggest_outfit`
- **Inputs:**
  - `new_item` (dict) — the listing the user is considering.
  - `wardrobe` (dict) — a wardrobe with an `items` list. May be empty.
- **Output:** `str` — a styling guide. With a populated wardrobe it names specific pieces to
  pair; with an empty wardrobe it gives general styling advice.
- **Purpose:** Turn a candidate item into concrete outfit ideas grounded in what the user
  already owns. Uses Groq `llama-3.3-70b-versatile`.

### 3. `create_fit_card`
- **Inputs:**
  - `outfit` (str) — the styling text returned by `suggest_outfit`.
  - `new_item` (dict) — the listing dict for the item.
- **Output:** `str` — a casual 2–4 sentence OOTD-style caption.
- **Purpose:** Produce a shareable social-media caption for the find. Uses Groq
  `llama-3.3-70b-versatile` at temperature `0.9` so repeated runs vary.

---

## How the Planning Loop Works

The loop lives in [`agent.py`](agent.py) (`run_agent`). It is **fixed-order and
condition-gated** — the order of tools never changes, but *whether the next tool runs at all*
depends on the previous step's result. The agent's job is to decide when to stop, not which
tool comes next.

1. **Parse the query.** `_parse_query` uses regex to pull a `description`, an optional `size`
   (only when stated explicitly, e.g. "size M"), and an optional `max_price` (from "under
   $30", "below 40", or a bare "$30") out of the free-text query. Result → `session["parsed"]`.

2. **Search.** `search_listings` runs with those parameters. It has its own internal
   **retry-with-fallback**: if the first pass returns nothing *and* a size was given, it drops
   the size constraint and tries again with just keywords + price.

3. **Decision point — stop or continue.** If search still returns `[]`, the agent writes a
   user-facing message to `session["error"]` and **returns immediately**. The two LLM tools
   never run on empty input — this is the key conditional in the loop. If there are results,
   it selects the top-ranked one as `session["selected_item"]`.

4. **Detect a relaxed match.** If a size was requested but the top result doesn't satisfy it,
   the match must have come from the fallback pass, so the agent appends an explanatory note
   to `session["notes"]` (e.g. "no exact match for size 'XXS' — showing closest results").

5. **Style.** `suggest_outfit` runs on the selected item and the wardrobe. It branches
   internally on whether the wardrobe is empty.

6. **Caption.** `create_fit_card` runs on the outfit text and the selected item.

7. **Done.** The completed `session` is returned. The run is "finished" when `create_fit_card`
   returns, or earlier if the no-results branch short-circuited it.

---

## State Management

All state for one interaction lives in a single `session` dict, created by `_new_session`
in [`agent.py`](agent.py). It is the single source of truth — each tool reads only the fields
it needs and writes its own result back. Nothing is passed between tools except through this
dict.

| Field | Written by | Holds |
|-------|-----------|-------|
| `query` | `_new_session` | the original user query |
| `parsed` | step 2 | `{description, size, max_price}` extracted from the query |
| `search_results` | step 3 | full ranked list from `search_listings` |
| `selected_item` | step 4 | the top listing, passed into both LLM tools |
| `wardrobe` | `_new_session` | the user's wardrobe dict |
| `outfit_suggestion` | step 5 | styling text from `suggest_outfit` |
| `fit_card` | step 6 | caption from `create_fit_card` |
| `error` | no-results branch | early-termination message (otherwise `None`) |
| `notes` | fallback branch | list of non-fatal events (e.g. size relaxed) |

The flow of data is explicit: `parsed` feeds `search_results`, whose top entry becomes
`selected_item`, which feeds `outfit_suggestion`, which feeds `fit_card`. The UI
(`handle_query` in [`app.py`](app.py)) reads the finished session and maps `selected_item`,
`outfit_suggestion`, and `fit_card` onto the three output panels — or routes `error` to the
first panel when the run stopped early.

---

## Error Handling

Each tool degrades gracefully rather than raising. The agent's behavior depends on which
failure occurs.

| Tool | Failure mode | Response |
|------|-------------|----------|
| `search_listings` | No results match | Retry with `size` dropped (keywords + price kept). If still empty, the agent sets `session["error"]` and stops before any LLM tool runs. |
| `suggest_outfit` | Wardrobe is empty | Switches to a general-styling prompt so it still returns useful, non-empty advice. |
| `create_fit_card` | Outfit string missing / whitespace, or the LLM call errors | Returns a deterministic fallback caption built from the item's raw attributes (title, price, platform). Never raises. |

**Concrete example from testing.** Running the query `"graphic tee size XXS under $30"`
(no listing is size XXS) exercised two of these paths at once:

```
selected: Y2K Baby Tee — Butterfly Print
notes: ["No exact match for size 'XXS' — showing the closest results with the size filter relaxed."]
error: None
```

The first search pass returned `[]` because of the impossible size; the fallback dropped the
size, recovered 7 keyword matches, and the agent recorded a note explaining the relaxation
instead of failing. By contrast, `"designer ballgown size XXS under $5"` returns no matches
even after the fallback, so the agent set:

```
error: No listings matched your search — try fewer keywords, a higher price, or dropping the size.
```

…and `outfit_suggestion` / `fit_card` both stayed `None` — the LLM tools never ran.

---

## Spec Reflection

**One way the spec helped.** The architecture diagram and the explicit tool signatures gave
me a precise contract before writing any code. In particular, the rule "do NOT proceed to
`suggest_outfit` with empty input" made the central conditional of the planning loop
unambiguous — the loop's design fell directly out of that one constraint, and the
no-results path was correct on the first try.

**One way the implementation diverged.** The spec's architecture diagram lists "Description,
Size, Max Price" as separate user inputs. The starter `app.py`, however, ships with a single
freeform query box, and the project rule was to not alter the repository's structural layout.
So instead of adding separate UI fields, I kept the single box and moved the
description/size/price extraction into `_parse_query` in `agent.py`. This honored both the
"separate parameters" intent (the tools still receive three clean parameters) and the
"don't change the layout" constraint — the parsing just happens one layer deeper than the
diagram implied.

---

## AI Usage

I used **Claude (Claude Code)** as the implementation assistant. Two specific instances:

**1. Implementing `search_listings` with fallback.**
I gave Claude the Tool 1 spec from `planning.md` (parameter names/types, the `list[dict]`
return contract, and the "drop size on empty" failure rule) plus the listing schema from
`utils/data_loader.py`. It produced a keyword-overlap scorer with a price filter, a
case-insensitive size substring filter, and the retry-with-fallback pass. **What I changed:**
its first version scored every keyword equally, so short filler tokens like "the" inflated
matches; I had it drop tokens of 2 characters or fewer. I then verified the output against
the three example queries (graphic tee, track jacket size M, the impossible ballgown) before
trusting it.

**2. Implementing the planning loop in `run_agent`.**
I gave Claude the Planning Loop and State Management sections of `planning.md` plus the
session schema. It produced the ordered loop. **What I overrode:** I made the no-results
branch return *before* any LLM tool runs (the draft was willing to continue), and I added the
fallback-note detection — comparing the requested size against the top result's size to know
whether the match came from the relaxed pass — which wasn't in the first draft.

**Bonus instance — a real bug it caught.** During end-to-end testing the LLM tools returned a
`401 Invalid API Key`. Working through it with Claude surfaced that the `.env` key had a
stray leading character (`ygsk_…` instead of `gsk_…`); fixing the typo made all live calls
succeed.
