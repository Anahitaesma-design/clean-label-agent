# Clean Label Agent
### An AI agent that tells you whether your food, cookware, skincare, and cleaning products are safe — and refuses to guess when it doesn't know.

**Track: Agents for Good**

---

## The Problem

Walk into any store and pick up a product — a snack, a face cream, a non-stick pan, a bottle of cleaning spray. Turn it over. The ingredient label is a wall of chemistry: INCI names, E-numbers, polysyllabic preservatives, and coatings identified only by acronym. For the average person, it is unreadable. And yet these are the products we eat, rub into our skin, cook our food on, and spray around our children every single day.

The information needed to judge safety *does* exist. Food additives are catalogued in open databases. Cosmetic ingredients are registered in the EU's CosIng system. The hazard profile of nearly every known chemical is documented by the U.S. National Library of Medicine. But this information is fragmented across separate systems, written in technical language, and completely inaccessible at the one moment a person actually needs it: standing in the aisle, holding the product, trying to decide whether to buy it.

We set out to close that gap. The **Clean Label Agent** takes any consumer product — by barcode, name, photo, or raw ingredient list — and returns a clear **SAFE / CAUTION / UNSAFE** verdict, explains the reasoning in plain English, cites its sources, and offers a safer alternative. It does this in seconds, and critically, it does it *honestly*: it never invents a hazard, and it tells you when it doesn't know.

## Why This Needs an Agent

It would be tempting to build this as a simple lookup script — barcode in, safety rating out. But that approach fails immediately, because answering "is this safe?" is not a lookup. It is a chain of dependent decisions:

The system must first figure out *what the product even is* before it can know which database to consult. Cookware, cosmetics, and food live in entirely different data sources. It must then retrieve the ingredient list, look up each ingredient's hazard data in a separate chemical database, and — this is the subtle part — interpret that hazard *in the context of how the product is actually used*, not as a raw industrial chemical. It must judge its own confidence and ask a human when it is unsure. And above all, it must refuse to make any claim it cannot trace back to real evidence.

That sequence — perceive, plan, retrieve, verify, judge, explain — is precisely what an agentic architecture exists to handle. An agent can orchestrate multiple tools, delegate specialized reasoning to a sub-agent, hold itself accountable to a verification rule, and know when to stop and ask. A static function can do none of these. The agent's ability to reason across tools and refuse unverified conclusions is not a nice-to-have here; it is the entire product.

## How It Works

The Clean Label Agent runs a classic **perceive → plan → act → observe → iterate** loop, implemented in `src/agent.py`.

**Perceive.** The agent accepts input in four forms: a barcode, a product name, a photo of the label, or a raw ingredient list. This flexibility matters — sometimes you have a barcode, sometimes you only have the product in your hand.

**Plan.** An LLM examines all available evidence — database matches, web-search results, and, if a photo is supplied, the label read directly via vision — and determines two things: what the product is, and which category it belongs to (food, skincare, cookware, or cleaning). This identification step drives everything downstream, because it selects both the correct database and the correct safety-interpretation logic.

**Act — Layer 1 (product → ingredients).** Based on the identified category, the agent queries the matching open database through the Model Context Protocol: Open Food Facts for food, Open Beauty Facts for skincare, and Open Products Facts for cookware and cleaning. All three share a common API structure, so a single configurable client serves all of them.

**Act — Layer 2 (ingredient → hazard).** For every ingredient retrieved, the agent queries **PubChem PUG-REST**, the National Library of Medicine's chemical database, for that substance's GHS hazard classification and toxicity data. This is the agent's factual bedrock. Every safety claim the agent makes must originate here — not from the LLM's memory.

**Observe.** A toxicology sub-agent assesses the combined hazard data, and the hallucination guard verifies that every chemical the agent names actually appears in the retrieved source data.

**Iterate.** If confidence is low, sources conflict, or a claim cannot be verified, the agent loops back — re-querying, asking the human, or returning UNKNOWN rather than guessing.

Below is the state graph representing the agent's complete operational routing workflow:

![Clean Label Agent State Graph Flowchart](architecture.png)

## The Two Design Decisions That Define the Agent

Two architectural choices separate this project from a naive safety scanner, and both emerged from real failures we caught during development.

### 1. LLM identifies; databases decide safety.

Early on, we let the agent's language model reason too freely about safety, and it produced confident, alarming, and *wrong* verdicts — flagging benign ingredients as dangerous because it was pattern-matching on chemical names. The fix was a strict division of labor: **the LLM is allowed to identify and categorize a product, but it is never allowed to assert safety from its own knowledge.** Safety facts come exclusively from the databases. The LLM's role is to reason about *what the product is* and to *explain* the retrieved facts — not to invent them.

This is enforced by the **hallucination guard**, the single most important safety feature in the system. The guard applies one rule: every chemical hazard the agent reports must be traceable to the raw JSON returned by a database. If the model's draft verdict cites a chemical that does not appear — by name or known synonym — in the retrieved data, validation fails and the agent is forced back into its loop rather than returning the unverified claim. The agent literally cannot make up a hazard.

### 2. Raw-chemical hazard is not consumer risk.

Our most instructive bug involved a sunscreen. Scanned early in development, the agent labeled it **UNSAFE** and warned it was "fatal if swallowed," flagging citric acid, stearic acid, and glyceryl laurate as chemicals of concern. Every one of those is a standard, safe cosmetic ingredient.

The root cause was a category error baked into the data itself: PubChem's GHS hazard statements describe the **pure, bulk, industrial form** of a chemical — a drum of concentrated material in a warehouse — not that same ingredient at safe concentration in a finished consumer product. A "harmful if swallowed" note on industrial citric acid says nothing about the trace amount stabilizing a face cream.

We rebuilt the verdict logic to make this distinction explicit. The agent now separates the *intrinsic hazard of a raw chemical* from the *actual risk of that ingredient in a finished product at normal use*, and it routes interpretation by category: ingestion risk matters for food, skin-absorption and allergen risk for skincare, off-gassing and contact risk for cleaning and cookware. After the fix, the same sunscreen scans correctly as **SAFE**, with an explanation that openly notes the raw-material warnings and states plainly that they do not apply to consumers at these concentrations. The agent went from confidently wrong to correctly cautious — which is exactly the behavior a health tool must have.

## Human-in-the-Loop, Where It Matters

Because the agent makes health-adjacent claims, it pauses for human oversight at two points — but only when it genuinely needs to, so the experience stays fast.

The first checkpoint is at **identification**: if the agent's confidence in what the product is falls below threshold, it stops and asks the user to confirm the category rather than proceeding on a guess. The second is at the **verdict**: before presenting a high-stakes result, a "Vibe Diff" checkpoint shows the raw database findings side by side with the agent's interpreted summary, so a human can confirm that nothing was exaggerated or downplayed. Both decisions are recorded in the agent's trace, making its human interactions fully observable.

## Course Concepts Applied

The capstone asked for at least three of the six key concepts. The Clean Label Agent demonstrates all six.

**Agent / Multi-agent system (ADK).** The core loop orchestrates a dedicated toxicology sub-agent through agent-to-agent delegation, keeping specialized hazard assessment cleanly separated from the main reasoning loop.

**MCP Server.** The agent connects to four independent public data sources through the Model Context Protocol — three product databases and PubChem — using a unified client.

**Antigravity.** The entire agent was vibe-coded in Gemini Antigravity, working spec-first and directing the tool through natural-language prompts (demonstrated in the video).

**Security features.** The hallucination guard and the two human-in-the-loop checkpoints together enforce a hard rule against unverified claims and against alarmist misinterpretation of raw-chemical data.

**Agent skills.** Four progressively disclosed SKILL.md files — food, cookware, skincare, and cleaning — let a single agent flex into the correct specialist role at runtime, loading only the relevant skill's guidance into the prompt.

**Deployability.** The agent is packaged for Google Cloud Run, with reproducible setup documented in the repository.

## How We Built It

We worked as a two-person team using a discipline that eliminated merge conflicts entirely: we split ownership **by file** rather than by feature. The Lead owned the core agent loop, the MCP client, the hallucination guard, observability, and semantic skill routing; the Specialist owned the four skills, the toxicology sub-agent, the safety-card interface, the Vibe Diff checkpoint, the commerce module, and the test suite. Because no two people ever edited the same file, integration was a matter of importing clean functions rather than untangling conflicts. Only the Lead edited the central `agent.py`, wiring in each of the Specialist's modules as they were completed.

Development was spec-first. Before writing implementation code, we defined the agent's required behavior as Gherkin scenarios — a food item with a banned additive returns UNSAFE; a PFOA-coated pan returns UNSAFE with a safer alternative; a clean skincare product returns SAFE; an unidentifiable product returns UNKNOWN; a high-risk verdict requires human approval. These scenarios became the source of truth and generated the test suite, so the code was always measured against defined behavior rather than vibes alone.

## Evaluation

Because an agent making health claims cannot be validated by unit tests alone, we built an **LLM-as-Judge evaluation suite** on the ADK eval framework — the approach the course recommends for scoring behavior that deterministic rules can't capture. We assembled a golden dataset of twelve real products, three per category, spanning SAFE, CAUTION, and UNSAFE outcomes. Each product is run through the live agent, and a Gemini judge scores the result against a four-part rubric: correct category, correct verdict, cited sources, and — critically — a non-alarmist explanation that separates raw-chemical hazard from finished-product risk. Following the course's guidance, every case is judged twice with the reference and actual outputs swapped to neutralize ordering bias. All twelve product safety verdicts were classified correctly across every evaluation case; the LLM judge scored the explanations at 7–10 out of 10, passing all cases under neutralized order bias. (The score range reflects the nature of LLM-as-Judge evaluation — a language model returns slightly different numeric scores for the same output across runs — while the underlying verdicts were stable and correct every time.) This gave us measurable confidence that the agent is not just working, but working *honestly*.

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

The most valuable part of building this agent was not the features that worked on the first try — it was the failures we caught and corrected. The sunscreen that was called "fatal food," the barcode that routed to the wrong database, the product name the agent honestly could not find. Each of these forced a design decision that made the agent more trustworthy: separate identification from safety judgment, interpret hazards by context, and above all, never guess.

That last principle is what we are proudest of. When the agent encounters a product it cannot fully identify, it does not fabricate a plausible-sounding name to look complete. It says "Unknown Product," explains why, and still delivers an accurate safety verdict from the ingredients it *can* verify. In a domain where a confident wrong answer can genuinely harm someone, an agent that knows the limits of its own knowledge is not a weaker product — it is the entire point.

## Impact and What's Next

The Clean Label Agent turns hours of scattered ingredient research into a ten-second answer a person can actually trust — because it cites every source, interprets hazards honestly, and refuses to overstate risk. As an Agents-for-Good project, its value is direct and human: helping ordinary people make safer choices about what they bring into their homes and put on their bodies.

The natural next steps are broadening database coverage for the long tail of niche products, adding barcode-scanning directly from a phone camera for true in-store use, and expanding the safer-alternative commerce layer into a curated marketplace of verified clean products. But even in its current form, the agent delivers on its core promise: an honest, source-backed second opinion on the safety of the products in your life.

---

*Built with Gemini Antigravity for the Google × Kaggle 5-Day AI Agents Capstone.*

<!-- WORD COUNT NOTE: This Writeup is approximately 1,750 words, comfortably under the 2,500 limit. You have room to add: (1) a specific PFOA-cookware walkthrough, (2) more detail on the OpenTelemetry tracing, or (3) a short section on the AP2/UCP commerce flow, if you want to use the remaining budget. -->

<!-- BEFORE SUBMITTING:
  1. Add your cover image to the Media Gallery (required)
  2. Attach your YouTube video (required)
  3. Attach your public project/repo link
  4. Fill in team names and Kaggle usernames
  5. Select the "Agents for Good" track in the Writeup settings
-->
