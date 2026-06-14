# FitFindr — planning.md

> Spec and agent diagram used to direct implementation. See `implementation_plan.md`
> for the live status tracker.

## Tools

---
### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Searches the mock secondhand listings dataset for items matching free-text keywords, an
optional size, and an optional price ceiling. Pure Python — no LLM. Scores each listing by
keyword overlap and returns the matches ranked best-first.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): keywords describing the desired item (e.g. "vintage graphic tee").
- `size` (str | None): size to filter by, case-insensitive substring match (e.g. "M"
  matches "S/M"). `None` skips size filtering.
- `max_price` (float | None): inclusive maximum price. `None` skips price filtering.

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
A `list[dict]` of matching listings sorted by relevance score (highest first). Each dict has:
`id, title, description, category, style_tags, size, condition, price, colors, brand,
platform`. Returns `[]` when nothing matches — never raises.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
If the initial pass returns `[]`, activate **retry-with-fallback**: drop the `size`
constraint (keep keywords + price) and re-run. If the fallback finds matches, they are
returned and the agent records that a fallback was used. If still empty, return `[]` and the
agent terminates the workflow safely with a user-facing error.

---
### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Given a thrifted item and the user's wardrobe, asks the LLM to propose 1–2 complete outfits
pairing the new item with named wardrobe pieces.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): the listing the user is considering buying.
- `wardrobe` (dict): wardrobe with an `items` list of wardrobe-item dicts. May be empty.

**What it returns:**
<!-- Describe the return value -->
A non-empty `str` styling guide. With a populated wardrobe it references specific pieces by
name; with an empty wardrobe it gives general styling advice for the item.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the prompt switches to a general-styling variant so the
model still returns useful text instead of crashing or returning an empty string.

---
### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Generates a short, shareable OOTD-style social caption for the thrifted find, based on the
outfit suggestion and the item details.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): the outfit suggestion string from `suggest_outfit`.
- `new_item` (dict): the listing dict for the thrifted item.

**What it returns:**
<!-- Describe the return value -->
A 2–4 sentence casual caption string. Uses a higher temperature (0.9) so repeated calls vary.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If `outfit` is missing/whitespace, or the LLM call errors, the tool catches it and returns a
deterministic fallback caption built from the item's raw attributes (title, price, platform)
— it never raises.

---

## Planning Loop
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

**How does your agent decide which tool to call next?**
The loop is fixed-order and condition-gated. It parses the query, then runs
`search_listings`. If results are empty (even after fallback), it sets `session["error"]`
and stops — downstream tools never run on empty input. On a match it selects the top result,
runs `suggest_outfit`, then `create_fit_card`. Each step is gated on the previous step
producing usable output. The run is "done" when `create_fit_card` returns or an error
short-circuits it.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
A single `session` dict (created by `_new_session`) is the source of truth. The parsed query
lands in `session["parsed"]`; search output in `session["search_results"]`; the chosen
listing in `session["selected_item"]`; the styling text in `session["outfit_suggestion"]`;
the caption in `session["fit_card"]`. `session["error"]` holds any early-termination message
and `session["notes"]` records non-fatal events such as "size constraint dropped via
fallback". Each tool reads only the session fields it needs and writes its own result back.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Retry with `size` dropped; if still empty, set `session["error"]` and stop before downstream tools |
| suggest_outfit | Wardrobe is empty | Switch to general-styling prompt; still return non-empty advice text |
| create_fit_card | Outfit input is missing or incomplete | Return a fallback caption built from the item's raw attributes; never raise |

---

## Architecture
<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```text
User query + wardrobe choice
        │
        ▼
  run_agent (agent.py)
        │  parse query → session["parsed"]
        ▼
  search_listings ──[empty]──► drop size, retry ──[still empty]──► session["error"] → STOP
        │ [match]                     │ [match → note fallback]
        ▼                             ▼
  session["selected_item"]  ◄─────────┘
        │
        ▼
  suggest_outfit ──[empty wardrobe]──► general styling prompt
        │
        ▼
  session["outfit_suggestion"]
        │
        ▼
  create_fit_card ──[empty/error outfit]──► fallback caption from item attrs
        │
        ▼
  session["fit_card"] → return session
```

---

## AI Tool Plan
<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->
**Milestone 3 — Individual tool implementations:**
Use Claude with each Tool spec above (inputs, return type, failure mode) plus the listing and
wardrobe schemas. `search_listings` is generated as pure Python over `load_listings()` and
verified against the example queries (graphic tee, track jacket size M, the no-results
ballgown). The two LLM tools are generated against the Groq `llama-3.3-70b-versatile` model;
each is run once to confirm non-empty, on-style output and that the empty-input branches
return text rather than raising.

**Milestone 4 — Planning loop and state management:**
Give Claude the Planning Loop + State Management sections and the session schema, and ask it
to implement `run_agent` so each tool call reads/writes the session and the early-exit and
fallback-note paths match this doc. Verify with the happy path and the no-results path from
`agent.py`'s `__main__`, then wire `handle_query` and confirm the three panels populate.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy
jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
`run_agent` parses the query into `description="vintage graphic tee"`,
`size=None`, `max_price=30.0` and stores it in `session["parsed"]`.

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
`search_listings("vintage graphic tee", None, 30.0)` scores listings by keyword
overlap and price; the Y2K butterfly baby tee ($18) and 2003 bootleg graphic tee ($24) rank
top. Results land in `session["search_results"]`; the top one becomes
`session["selected_item"]`.

**Step 3:** 
<!-- Continue until the full interaction is complete -->
`suggest_outfit(selected_item, example_wardrobe)` returns styling text pairing the
tee with the baggy jeans and chunky sneakers; stored in `session["outfit_suggestion"]`.

**Step 4:** 
<!-- What does the user actually see at the end? -->
`create_fit_card(outfit, selected_item)` returns a casual caption naming the item,
its price, and platform; stored in `session["fit_card"]`.

**Final output to user:**
<!-- What does the user actually see at the end? -->
 Three panels — the matched listing details, the outfit idea, and
the shareable fit card caption.