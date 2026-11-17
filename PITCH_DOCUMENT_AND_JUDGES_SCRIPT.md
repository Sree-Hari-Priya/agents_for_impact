# Milestone Navigator: Triage & Network-Audit for Infants & Toddlers
## Challenge 04: Early Intervention & Developmental Screening (IDEA Part C)
### Google Cloud Agents for Impact Hackathon · Official Presentation Pitch & Live Demo Script

---

# PART 1: The Executive Pitch Document (1-Pager for Judges)

### Project Overview
* **Application Title:** First Milestones: Triage & Network-Audit (*Milestone Navigator*)
* **Live Production URL:** [https://early-intervention-triage-584075988667.us-central1.run.app/](https://early-intervention-triage-584075988667.us-central1.run.app/)
* **GitHub Repository:** [https://github.com/Sree-Hari-Priya/agents_for_impact](https://github.com/Sree-Hari-Priya/agents_for_impact)
* **Core Technologies:** Google Agent Development Kit (ADK), Vertex AI Gemini 2.5 Flash, BigQuery Property Graph (ISO GQL), BigQuery Geospatial GIS, Census TIGER/Line, USGS National Map.

---

### The Real-World Problem: The "Flat Waitlist Illusion"
Federal law under Part C of the **Individuals with Disabilities Education Act (IDEA)** dictates that states have exactly **45 calendar days** from referral to an Initial Individualized Family Service Plan (IFSP). Early intervention speech or autism therapy before age 2 alters neurological trajectories far more than the same therapy at age 5.

Yet across high-poverty urban and rural communities, thousands of toddlers wait 60 to 90+ days without ever seeing an evaluator. Why?
* State directories list providers **flatly**: An intake desk advertises an internal wait of "5 days," appearing completely open.
* In reality, referrals are **multi-hop graph cascades**: A clinic faxes an intake desk (+12d), which faxes a saturated evaluation hub (+20d), which rejects the child for lack of Spanish bilingual slots (+22d), forcing a third handoff (+16d).
* **Result:** A 70-day breach. At 36 months, toddlers hit the catastrophic "aging-out cliff," losing Part C toddler entitlements entirely.

---

### The Innovation: What We Built
Instead of a static directory or a naive LLM chat, **First Milestones** is an autonomous, graph-native multi-agent casework partner:

1. **BigQuery Property Graph (ISO GQL Variable-Length Traversal):**
   * Pre-indexed 30 CareNodes and 89 Census Tracts into an ISO GQL Graph: `MATCH -[e:HANDED_OFF_TO*3..4]->`.
   * Unmasks the "hidden bounce hubs" where paper fax dropoffs and language mis-matches conceal massive downstream delays.

2. **Google ADK Multi-Agent Team (Milestone Navigator - "Maya"):**
   * **Root Orchestrator (`milestone_navigator_agent`):** Manages conversational triage and enforces the 45-day statutory clock.
   * **Pathway Router Agent:** Takes natural geographic inputs (ZIP code, city name, or Census GEOID), calculates nearest screening clinics via spatial radius (`ST_DISTANCE`), and routes a guaranteed $\le 45$-day multi-hop path.
   * **Network Audit Agent:** Evaluates systemic bottlenecks across all referral chains and runs interventions.
   * **Equity & Transit Audit Agent:** Automatically inspects American Community Survey (ACS) 5-year Table B25044 (Zero-Vehicle households). When a child in the South Bronx (83.5% zero-vehicle rate) is routed to an upstate bilingual hub, the agent automatically triggers a **Zero-Vehicle Transit Guardrail Alert** recommending Tele-Assessment or Non-Emergency Medical Transport (NEMT).
   * **Caregiver Note Agent:** Translates complex clinical pathways into compassionate, bilingual (English & Spanish) family action notes.

3. **Single Network Fix Simulator:**
   * Demonstrates the macro-economic payoff: Upgrading just **one single regional coordinator** (Walton Intake #11) from paper fax to electronic EHR intake with pre-checked bilingual slots rescues **100% of its breached cases (7 of 7)** under the 45-day statutory limit and saves **336 delayed child-days**.

---

### Key Differentiators & Compliance
* **100% Synthetic Healthcare Data:** Strict HIPAA compliance with realistic clinical and geographical grain.
* **100% Public Domain Geospatial Basemaps:** Uses the USGS National Map and US Census TIGER/Line data (0% OpenStreetMap ODbL contamination risk).
* **Instant Natural Geocoding:** Type `10451` or `Bronx` or `Jamestown` — resolves in milliseconds to the exact Census Tract centroid.

---
---

# PART 2: 3-Minute Live Presentation Script (Word-for-Word for Judges)

> **Speaker Note:** Open the live link on a laptop/projector: `https://early-intervention-triage-584075988667.us-central1.run.app/`. Ensure your screen is zoomed to 100% or 110%.

---

### [0:00 – 0:45] Minute 1: The Hook & The Problem
*(Pointing to the New York Skyline Banner & Challenge 04 Badge)*

"Judges, welcome to **First Milestones**. 

Under federal law (IDEA Part C), when a pediatrician flags a 20-month-old toddler for speech delay or autism, the state has exactly **forty-five calendar days** to evaluate that child and put an Individualized Family Service Plan into action. Brain plasticity before age two is immense. Every week lost is development that child can never get back.

Yet in New York and across the country, over **70% of multi-hop referral chains breach this 45-day federal clock**. 

Why? Because caseworkers rely on flat directories. An intake coordinator advertises a wait time of only **5 days**. That looks fast! But what that flat directory conceals is the **multi-hop paper-fax cascade**: clinic to coordinator, coordinator to an evaluator who doesn't speak Spanish, a rejected fax bounce back, and a second re-referral. Total wait: **70 days**. The child turns 36 months old and ages out of early intervention entirely."

---

### [0:45 – 1:45] Minute 2: Live Demo — Track 1: Today's Referral & Natural Geo
*(Click into Track 1 on the screen, show the Location input bar)*

"To solve this, we built **Milestone Navigator** (*Maya*), powered by Google ADK, Vertex AI Gemini 2.5 Flash, and BigQuery Property Graph.

Let's look at **Track 1: Today's Referral**. As an intake coordinator, I don't know complex Census tract numbers. I just have a family's ZIP code: **10451** in the South Bronx.

*(Type `10451` into the location box or click the quick pill)*

Watch what happens: In milliseconds, our agentic spatial tool resolves ZIP `10451` to Bronx County and calculates the exact spatial distance to the nearest pediatric screening centers. 

Notice the switches:
* This child is 22 months old.
* They require **Medicaid acceptance**.
* And crucially, they require a **Bilingual Spanish evaluator**.

*(Click 'Calculate Compliant Pathway (<= 45d)')*

Look at the result:
1. **The Graph Engine** computes a guaranteed **22-day compliant pathway** through verified bilingual hubs, well under the 45-day ceiling.
2. **The Equity Guardrail Alert:** It detected that Census Tract `36005019700` has an **83.5% zero-vehicle rate**. Because the bilingual hub is regional, the agent automatically flags a **Transit Guardrail Alert**, prescribing a Mobile Evaluation Unit or an NEMT transit voucher so this family doesn't miss their appointment.
3. **The In-Pane Pathway Graph:** Below, you can see the interactive 4-stage handoff graph — showing each hop, the transmission channel, and the wait days.
4. **Caregiver Action Notes:** With one click on *'View / Print Bilingual Caregiver Action Note'*, our ADK Caregiver Note Agent generates personalized, compassionate action notes in both English and Spanish for the family."

---

### [1:45 – 2:30] Minute 3: Network Audit & The "Single Fix" Simulation
*(Click on 'Track 4: Simulator' in the top switcher)*

"Now, what about the macro level? Can leadership fix this broken system?

Let's switch to **Track 4: Network Fix Simulator**. 

Using BigQuery ISO GQL variable-length graph queries, our Network Audit Agent analyzed every referral chain statewide. Look at this simulation table:

If we invest in upgrading just **one single regional intake coordinator** — Walton Intake Desk #11 — from paper-fax to electronic EHR intake with pre-checked bilingual slots:
* **7 out of 7 breached cases (100%)** drop immediately below the 45-day statutory limit!
* It saves **336 delayed child-days** for that coordinator alone, reducing statewide breaches by 27%!

Our graph shows administrators *exactly* where a targeted single intervention has the highest return on investment for child outcomes."

---

### [2:30 – 3:00] Wrap-Up & Vision
*(Return to Track 1 or the Hero banner)*

"To summarize:
1. **Google ADK Multi-Agent Team** acts as an autonomous clinical co-pilot.
2. **BigQuery Property Graph** shatters the flat waitlist illusion.
3. **Census & ACS GIS Data** guarantees equity for zero-vehicle and bilingual families.

We are not just calculating wait times; we are ensuring that no toddler in America ages out of early intervention waiting on a paper fax.

Thank you, and we welcome your questions!"

---
---

# PART 3: Judges Q&A Cheat Sheet (Anticipated Questions & Winning Answers)

#### Q1: "How is this different from a standard database query or shortest-path algorithm?"
> **Answer:** "A shortest-path algorithm optimizes for a single metric like physical distance. In IDEA Part C triage, paths are constrained by **multi-hop regulatory and clinical requirements**: Medicaid acceptance at stage 1, bilingual evaluator accreditation at stage 3, zero-vehicle transit feasibility, and a hard 45-day statutory ceiling across all 4 hops combined. BigQuery Property Graph (ISO GQL) allows us to query complex path patterns (`MATCH (c)-[:HANDED_OFF_TO*3..4]->(v)`) and filter across node attributes and edge transition channels simultaneously."

#### Q2: "Why do you use Google ADK multi-agent architecture instead of a single prompt?"
> **Answer:** "A single LLM prompt suffers from hallucination and lack of deterministic regulatory compliance. Under our Google ADK architecture:
> * The **Root Orchestrator** manages user intent and clinical guardrails.
> * The **Pathway Router Agent** strictly executes deterministic BigQuery queries.
> * The **Equity Audit Agent** deterministically calculates ACS vehicle deficits.
> * The **Caregiver Note Agent** handles linguistic translation and empathy.
> Each agent has dedicated tools, schemas, and verification boundaries, preventing clinical errors."

#### Q3: "What data did you use, and is there any privacy or licensing risk?"
> **Answer:** "There is zero privacy risk and zero licensing risk:
> 1. All provider and child referral data is **100% synthetic**, strictly modeled after New York State Part C Early Intervention programmatic data.
> 2. All demographic data is real **US Census Bureau ACS 5-Year Data (Table B25044)**.
> 3. All map basemaps are **USGS National Map (Public Domain US Government)**, completely free of OpenStreetMap ODbL viral share-alike licensing restrictions."

#### Q4: "How does this scale to an entire state or nationwide?"
> **Answer:** "Our data model is already built on Google Cloud BigQuery and Vertex AI, which easily scales to millions of nodes. In production:
> * Ingestion connects to state HL7 FHIR and electronic referral feeds.
> * The ADK agents connect via Model Context Protocol (MCP) to existing state Early Intervention portals (like New York's NYEIS).
> * The natural geocoding connects to the Google Maps Geocoding API for all 50 states."
