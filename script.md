# FitFindr — Demo Video Script (~3.5 min)

Paced for relaxed, slower delivery. Read the **Say** lines at a natural pace; the
**Screen / Do** lines are stage directions, not spoken. Total spoken words are kept low on
purpose — pause between scenes, don't rush.

**Before you hit record:**
- App already running in a terminal: `python app.py`, browser open at the URL it printed
  (usually <http://localhost:7860>).
- A second terminal open in the project folder (for the state-passing moment in Scene 3).
- Query box empty, "Example wardrobe" selected.

---

## Scene 1 — Intro (~20 sec)

**Screen:** The FitFindr browser tab (the three empty panels visible).

**Say:**
> Hi — this is FitFindr, a multi-tool AI agent for secondhand shopping. You describe what
> you want in plain language, and it does three things in order: it searches thrift listings,
> it suggests an outfit using your own wardrobe, and it writes a shareable caption. Let me
> show you a full run.

---

## Scene 2 — Happy path, all three tools (~80 sec)

**Screen:** FitFindr app.
**Do:** Click the query box. Type: `vintage graphic tee under $30`. Leave "Example wardrobe"
selected. Click **Find it**. (While it runs, narrate.)

**Say:**
> I'm asking for a vintage graphic tee under thirty dollars, and I'm telling it to use my
> example wardrobe. When I hit "Find it," the agent first *parses* my sentence — it pulls out
> the keywords "vintage graphic tee" and a max price of thirty dollars.

**Do:** Results appear. Point at the **left panel** (the listing).

**Say:**
> That parsed request goes into the first tool, `search_listings`. It scored every listing by
> keyword overlap and price, and picked the top match — here, the Y2K Baby Tee, eighteen
> dollars, on Depop.

**Do:** Point at the **middle panel** (the outfit).

**Say:**
> That selected item then gets handed to the second tool, `suggest_outfit`, along with my
> wardrobe. Notice it's not generic — it names *my* pieces, like my baggy straight-leg jeans
> and chunky white sneakers.

**Do:** Point at the **right panel** (the fit card).

**Say:**
> And the outfit text feeds the third tool, `create_fit_card`, which writes this casual
> caption — naming the item, the price, and the platform. That's all three tools in one run.

---

## Scene 3 — State passing made visible (~40 sec)

**Screen:** Switch to your **second terminal**.
**Do:** Run: `python agent.py`

**Say:**
> I want to show how the data actually moves between those tools. Each run lives in one
> "session" object, and every tool reads from it and writes back to it. If I run the agent
> directly in the terminal...

**Do:** Point at the printed output (`Found:`, `Outfit:`, `Fit card:`).

**Say:**
> ...you can see the chain: the search result becomes the *selected item*, the selected item
> becomes the *outfit suggestion*, and the outfit becomes the *fit card*. Nothing is passed
> between tools except through that one session object.

---

## Scene 4 — Graceful failure: no results (~35 sec)

**Screen:** Back to the FitFindr browser tab.
**Do:** Clear the box. Type: `designer ballgown size XXS under $5`. Click **Find it**.

**Say:**
> Now let me deliberately break it. I'll ask for a designer ballgown, size XXS, under five
> dollars — nothing in the dataset matches that.

**Do:** Point at the **left panel** showing the error message; the other two panels stay empty.

**Say:**
> Instead of crashing, the agent stops cleanly. Search came back empty even after it tried
> relaxing the size, so it sets a friendly error message and — importantly — it does *not*
> run the two AI tools on empty input. The other panels stay blank on purpose.

---

## Scene 5 — Graceful degradation: the fallback (~35 sec)

**Screen:** FitFindr app.
**Do:** Clear the box. Type: `graphic tee size XXS under $30`. Click **Find it**.

**Say:**
> One more — a softer failure. I'll ask for a graphic tee but in size XXS, which doesn't
> exist either. This time the keywords *do* match real items.

**Do:** Point at the small note at the top of the **left panel** ("no exact match for size…").

**Say:**
> So instead of giving up, the agent drops just the size filter, keeps the keywords and price,
> and tells me it relaxed the search — then carries on and still gives me an outfit and a
> caption. That's the difference between a hard stop and a graceful recovery.

---

## Scene 6 — Close (~15 sec)

**Screen:** The full app, or your README.

**Say:**
> So that's FitFindr: a fixed, condition-gated planning loop over three tools, with state
> flowing through one session object, and graceful handling when a search comes up empty.
> Thanks for watching.

---

### Timing cheat-sheet
| Scene | Target |
|-------|--------|
| 1 Intro | 0:00–0:20 |
| 2 Happy path | 0:20–1:40 |
| 3 State passing | 1:40–2:20 |
| 4 No-results failure | 2:20–2:55 |
| 5 Fallback recovery | 2:55–3:30 |
| 6 Close | 3:30–3:45 |

If you're running long, Scene 5 is the one to trim — Scene 4 already satisfies the required
"triggered failure." Keep Scenes 2 and 3 no matter what; they cover "all three tools" and
"visible state passing."
