# Clean Label Agent
### An AI agent that tells you whether your food, cookware, skincare, and cleaning products are safe — teaching you why in plain English, and refusing to guess when it doesn't know.

**Track: Agents for Good**

---

## The Problem

Walk into any store and pick up a product — a snack, a face cream, a non-stick pan, a bottle of cleaning spray. Turn it over. The ingredient label is a wall of chemistry: INCI names, E-numbers, polysyllabic preservatives, coatings identified only by acronym. For the average person, it is unreadable — yet these are products we eat, rub into our skin, cook on, and spray around our children every day.

The information needed to judge safety *does* exist: food additives catalogued in open databases, cosmetic ingredients registered in the EU's CosIng system, the hazard profile of nearly every known chemical documented by the U.S. National Library of Medicine. But it is fragmented across separate systems, written in technical language, and inaccessible at the one moment a person needs it: standing in the aisle, holding the product, deciding whether to buy it.

We set out to close that gap. The **Clean Label Agent** takes any consumer product — by barcode, name, photo, or raw ingredient list — and returns a clear **SAFE / CAUTION / UNSAFE** verdict, explains the reasoning in plain English, cites its sources, and offers a safer alternative. It does this in seconds, and critically, it does it *honestly*: it never invents a hazard, and it tells you when it doesn't know.

This is a public health problem hiding in plain sight. Chronic, low-level exposure to endocrine disruptors, carcinogens, and persistent chemicals in everyday products is a genuine population-level health concern — invisible to the person standing in the aisle, because the knowledge needed to see it lives in registries, not in the hands of the public. Closing that gap is public health protection delivered one shopper at a time, and education every time the agent explains *why*.

## Why This Needs an Agent

It would be tempting to build this as a simple lookup script — barcode in, safety rating out. But answering "is this safe?" is not a lookup; it is a chain of dependent decisions. The system must first figure out *what the product even is*, since cookware, cosmetics, and food live in entirely different data sources. It must then retrieve the ingredient list, look up each ingredient's hazard data, and — the subtle part — interpret that hazard *in the context of how the product is actually used*, not as a raw industrial chemical. It must judge its own confidence and ask a human when unsure, and above all, refuse to make any claim it cannot trace back to real evidence.

That sequence — perceive, plan, retrieve, verify, judge, explain — is precisely what an agentic architecture exists to handle. An agent can orchestrate multiple tools, delegate specialized reasoning to a sub-agent, hold itself accountable to a verification rule, and know when to stop and ask. A static function can do none of these. The agent's ability to reason across tools and refuse unverified conclusions is not a nice-to-have here; it is the entire product.

## How It Works

The Clean Label Agent runs a classic **perceive → plan → act → observe → iterate** loop, implemented in `src/agent.py`.

**Perceive.** The agent accepts a barcode, a product name, a photo of the label, or a raw ingredient list — flexibility that matters, since sometimes you have a barcode and sometimes only the product in hand.

**Plan.** An LLM examines all available evidence — database matches, web search, and, if supplied, a photo read via vision — and determines what the product is and which category it belongs to (food, skincare, cookware, cleaning). This selects both the correct database and the correct safety-interpretation logic downstream.

**Act — Layer 1 (product → ingredients).** Based on the identified category, the agent queries the matching open database via the Model Context Protocol: Open Food Facts, Open Beauty Facts, or Open Products Facts. All three share a common API structure, served by one configurable client.

**Act — Layer 2 (ingredient → hazard).** For every ingredient, the agent queries **PubChem PUG-REST**, the National Library of Medicine's chemical database, for GHS hazard classification and toxicity. This is the agent's factual bedrock — every safety claim must originate here, not from the LLM's memory.

**Observe.** A toxicology sub-agent assesses the combined hazard data, and the hallucination guard verifies every named chemical actually appears in the retrieved source data.

**Iterate.** If confidence is low, sources conflict, or a claim can't be verified, the agent loops back — re-querying, asking the human, or returning UNKNOWN rather than guessing.

Below is the state graph representing the agent's complete operational routing workflow:

![Clean Label Agent State Graph Flowchart](architecture.png)

## The Two Design Decisions That Define the Agent

Two architectural choices separate this project from a naive safety scanner, and both emerged from real failures we caught during development.

### 1. LLM identifies; databases decide safety.

Early on, we let the agent's language model reason too freely about safety, and it produced confident, alarming, and *wrong* verdicts — flagging benign ingredients as dangerous because it was pattern-matching on chemical names. The fix was a strict division of labor: **the LLM is allowed to identify and categorize a product, but it is never allowed to assert safety from its own knowledge.** Safety facts come exclusively from the databases. The LLM's role is to reason about *what the product is* and to *explain* the retrieved facts — not to invent them.

This is enforced by the **hallucination guard**, the single most important safety feature in the system. The guard applies one rule: every chemical hazard the agent reports must be traceable to the raw JSON returned by a database. If the model's draft verdict cites a chemical that does not appear — by name or known synonym — in the retrieved data, validation fails and the agent is forced back into its loop rather than returning the unverified claim. The agent literally cannot make up a hazard.

This same guard is also the agent's education engine. When it tells a user a Teflon pan is UNSAFE "because of PFOA, a persistent bioaccumulative toxin linked to cancer and reproductive harm," it isn't reciting a scary label — it's teaching that person, in one sentence, what PFOA is and why regulators care, something most people never learn otherwise. Because every claim is sourced, that education is never a guess dressed up as fact.

### 2. Raw-chemical hazard is not consumer risk.

Our most instructive bug involved a sunscreen. Scanned early in development, the agent labeled it **UNSAFE** and warned it was "fatal if swallowed," flagging citric acid, stearic acid, and glyceryl laurate — all standard, safe cosmetic ingredients — as chemicals of concern.

The root cause: PubChem's GHS hazard statements describe the **pure, bulk, industrial form** of a chemical — a drum of concentrated material in a warehouse — not that same ingredient at safe concentration in a finished consumer product. A "harmful if swallowed" note on industrial citric acid says nothing about the trace amount stabilizing a face cream.

We rebuilt the verdict logic to separate the *intrinsic hazard of a raw chemical* from the *actual risk of that ingredient in a finished product at normal use*, routing interpretation by category: ingestion risk for food, skin-absorption and allergen risk for skincare, off-gassing and contact risk for cleaning and cookware. After the fix, the same sunscreen scans correctly as **SAFE**, with an explanation that openly notes the raw-material warnings and states plainly they don't apply at these concentrations. The agent went from confidently wrong to correctly cautious — exactly the behavior a health tool must have.

## Human-in-the-Loop, Where It Matters

Because the agent makes health-adjacent claims, it pauses for human oversight at two points — only when it genuinely needs to, so the experience stays fast.

The first checkpoint is at **identification**: if confidence in what the product is falls below threshold, it stops and asks the user to confirm the category rather than guessing. The second is at the **verdict**: before presenting a high-stakes result, a "Vibe Diff" checkpoint shows the raw database findings side by side with the agent's interpreted summary, so a human can confirm nothing was exaggerated or downplayed. Both decisions are recorded in the agent's trace.

## Course Concepts Applied

The capstone asked for at least three of six key concepts. The Clean Label Agent demonstrates all six.

**Agent / Multi-agent system (ADK).** The core loop orchestrates a dedicated toxicology sub-agent via agent-to-agent delegation, keeping hazard assessment separated from the main reasoning loop.

**MCP Server.** The agent connects to four independent public data sources through the Model Context Protocol — three product databases and PubChem — via a unified client.

**Antigravity.** The entire agent was vibe-coded in Gemini Antigravity, spec-first, directed through natural-language prompts (demonstrated in the video).

**Security features.** The hallucination guard and two human-in-the-loop checkpoints enforce a hard rule against unverified claims and alarmist misinterpretation of raw-chemical data.

**Agent skills.** Four progressively disclosed SKILL.md files — food, cookware, skincare, cleaning — let one agent flex into the correct specialist role at runtime.

**Deployability.** The agent is packaged for Google Cloud Run, with reproducible setup documented in the repository.

## How We Built It

We worked as a two-person team, splitting ownership **by file** rather than by feature to eliminate merge conflicts entirely: the Lead owned the core agent loop, MCP client, hallucination guard, observability, and skill routing; the Specialist owned the four skills, the toxicology sub-agent, the safety-card interface, the Vibe Diff checkpoint, the commerce module, and the test suite. Because no two people ever edited the same file, integration meant importing clean functions, not untangling conflicts.

Development was spec-first: before writing implementation code, we defined the agent's required behavior as Gherkin scenarios — a banned additive returns UNSAFE, a PFOA-coated pan returns UNSAFE with a safer alternative, an unidentifiable product returns UNKNOWN, a high-risk verdict requires human approval. These scenarios generated the test suite, so the code was always measured against defined behavior rather than vibes alone.

## Evaluation

Because an agent making health claims cannot be validated by unit tests alone, we built an **LLM-as-Judge evaluation suite** on the ADK eval framework — the approach the course recommends for scoring behavior that deterministic rules can't capture. We assembled a golden dataset of twelve real products, three per category, spanning SAFE, CAUTION, and UNSAFE outcomes, and scored each result against a four-part rubric: correct category, correct verdict, cited sources, and — critically — a non-alarmist explanation that separates raw-chemical hazard from finished-product risk. Following the course's guidance, every case is judged twice with the reference and actual outputs swapped to neutralize ordering bias. All twelve verdicts were classified correctly across every run; the judge scored explanations at 7–10 out of 10 — the range reflecting normal LLM-as-Judge variance in scoring, not any instability in the underlying verdicts, which were correct every time.

| Product | Barcode / Input | Category | Expected | Actual | Result |
|---------|-----------------|----------|----------|--------|--------|
| Quaker Old Fashioned Rolled Oats | 030000010204 | food | SAFE | SAFE | PASS |
| Coca-Cola Classic | 049000006346 | food | CAUTION | CAUTION | PASS |
| Oscar Mayer Bacon | 044700000632 | food | UNSAFE | UNSAFE | PASS |
| Vanicream Moisturizing Cream | 345334300168 | skincare | SAFE | SAFE | PASS |
| Bath & Body Works Fragrance Lotion | name only | skincare | CAUTION | CAUTION | PASS |
| Suave Lotion (DMDM hydantoin) | name only | skincare | UNSAFE | UNSAFE | PASS |
| Dr. Bronner's Pure-Castile Liquid Soap | 018787771259 | cleaning | SAFE | SAFE | PASS |
| Method All-Purpose Cleaner | name only | cleaning | CAUTION | CAUTION | PASS |
| Clorox Regular Bleach | 044600324135 | cleaning | UNSAFE | UNSAFE | PASS |
| All-Clad D3 Stainless Steel Fry Pan | name only | cookware | SAFE | SAFE | PASS |
| T-fal PFOA-Free Non-Stick Pan | name only | cookware | CAUTION | CAUTION | PASS |
| Classic Teflon Pan (PFOA) | name only | cookware | UNSAFE | UNSAFE | PASS |

*All 12 verdicts classified correctly; all barcodes resolved; judge explanation scores 7–10/10.*

## The Journey

The most valuable part of building this agent was not the features that worked on the first try — it was the failures we caught and corrected: a sunscreen wrongly called dangerous, a barcode routed to the wrong database, a product name the agent honestly couldn't find. Each forced the same lesson: separate identification from safety judgment, interpret hazards by context, and above all, never guess.

That last principle is what we are proudest of. When the agent cannot fully identify a product, it says "Unknown Product" and explains why, rather than fabricating a plausible name to look complete — while still delivering an accurate verdict from the ingredients it *can* verify. In a domain where a confident wrong answer can genuinely harm someone, an agent that knows the limits of its own knowledge is not a weaker product; it is the entire point.

## Impact and What's Next

The Clean Label Agent turns hours of scattered ingredient research into a ten-second answer a person can actually trust — because it cites every source, interprets hazards honestly, and refuses to overstate risk. As an Agents-for-Good project, it serves the track's mission on two fronts at once, not one.

**Managing public health.** Chronic exposure to substances like PFOA, phthalates, and formaldehyde-releasing preservatives is a real, population-scale concern that accumulates silently through thousands of small, uninformed purchases. An honest verdict at the moment of purchase turns an invisible, systemic risk into a visible, individual choice — with a safer alternative right there, so the safer choice is also the easy one.

**Advancing education.** Every verdict is also a lesson. Someone who learns "citric acid is only hazardous in its raw industrial form, not in this lotion" walks away understanding a real distinction in toxicology — the same one our hallucination guard was engineered to respect. Over enough scans, the agent builds a person's ability to read *any* label more critically, app in hand or not — public health and education reinforcing each other, exactly where this track asks agents to help.

The natural next steps are broadening database coverage, adding barcode-scanning from a phone camera for true in-store use, and expanding the safer-alternative commerce layer into a curated marketplace. But even in its current form, the agent delivers on its promise: an honest, source-backed second opinion — and a small chemistry lesson — on the safety of the products in your life.

---

*Built with Gemini Antigravity for the Google × Kaggle 5-Day AI Agents Capstone.*

<!-- WORD COUNT: ~2,488 words, under the 2,500 limit. Re-verify against Kaggle's own counter before final save, since counting methods can differ slightly (tables, headers, etc.). -->

<!-- BEFORE RESAVING:
  1. Confirm cover image, video, and repo link are still attached (editing shouldn't remove them, but check)
  2. Confirm the "Agents for Good" track is still selected
  3. Re-check Kaggle's own word counter shows under 2,500
-->
