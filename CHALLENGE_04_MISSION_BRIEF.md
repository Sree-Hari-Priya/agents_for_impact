# Challenge 04: Early Intervention Triage ("First Milestones")

**Early Intervention & Developmental Screening Triage for Infants and Toddlers**

Federal law gives states **forty-five calendar days** from the moment a toddler is referred for a developmental concern to an initial family service plan. Under Part C of the Individuals with Disabilities Education Act (IDEA), that clock exists because speech, motor, or autism therapy before the age of 2 years changes a child's trajectory far more than the same support at age five. Yet across rural and high-poverty regions, thousands of two-year-olds wait far longer than forty-five days without ever seeing an evaluator.

---

## 1. The Challenge & Mission

### The Challenge
Regional Early Intervention programs know their 45-day compliance rate is slipping in the abstract. What they cannot see from a flat provider directory is where this child's referral chain actually breaks — a paper fax to an intake hub, a forward to a backlogged evaluator, and a third bounce when a Medicaid or Spanish-language credential is missing — or who to ask when a referral changes at the last minute.

### Your Mission
Build a triage and routing assistant for an Early Intervention intake coordinator — not a static dashboard, and not a single query with a chat box on it. An agent that an intake coordinator with the Department of Developmental Services can hold a working conversation with, that reaches for real neighborhood demographics and a live referral graph to answer.

---

## 2. Pick Your Track

| Track | Persona & Core Question | Primary Action | Key Data / Graph Signal Used |
| :--- | :--- | :--- | :--- |
| **🧭 Track 1: Today's Referral**<br>*(Active Case Routing)* | **Part C Intake Coordinator:** *"A 20-month-old needs bilingual developmental evaluation under Medicaid. Which provider path clears the 45-day clock from their neighborhood?"* | Route a live toddler referral (`Clinic ➔ Coordinator ➔ Eval Hub ➔ Therapy Vendor`) in **`<= 45` days** while checking `accepts_medicaid`, `bilingual_services_listed`, `child_age_months` (36-month cliff), and travel distance (`ST_DISTANCE`) for zero-vehicle families. | Prospective variable-length GQL traversal (`-{2,3}->`) over `ReferralGraph` + spatial distance from `acs_under5_tract_demographics`. |
| **🕸️ Track 2: This Quarter's Audit**<br>*(Systemic Bottleneck Fix)* | **Regional Part C Quality Lead:** *"Across two-to-four-hop referral chains, which single bottleneck hub is silently breaking the 45-day mandate for an entire region?"* | Expose the hidden **Bounce Hub** (`Part_C_Intake_Coordinator` with a 5-day internal wait that looks healthy in flat SQL, but whose `paper_fax` handoffs trigger 72-day 4-hop bounces) + simulate the counterfactual fix (**+10 bonus pts**). | Historical episode GQL traversal (`-[hops:ReferralHandoff]->{2,4}`) correlated on `case_chain_id` (`COUNT(DISTINCT h.case_chain_id) = 1`). |
| **📋 Track 3: This Outreach Season**<br>*(Community Screening Placement)* | **Early-Childhood Coalition Lead:** *"Combining under-five neighborhood poverty and statewide screening gaps, where should community developmental screening days go first?"* | Rank underserved under-5 census tracts (`children_under_5_count`, `poverty_rate`, `no_vehicle_rate`) **only after verifying** a downstream `<= 45`-day evaluation pathway exists. | Joins `acs_under5_tract_demographics` + `nsch_developmental_screening_survey` (avoiding the 6x statewide grain trap & `limited_english_rate = 0.0` trap) + GQL capacity check. |

> **Recommended Strategy — Combine Track 1 + Track 2 (with Track 3 Equity Audit built into the pipeline):**
> The required deliverable (**45-Day Pathway & Bottleneck Brief**) asks for all five outputs together: traced multi-hop paths, a recommended `<= 45`-day route, the regional bounce hub to fix first, the post-output equity audit, and the bilingual caregiver action note.

---

## 3. Core Judging Criteria & Final Deliverable

### Required Differentiator: BigQuery Property Graphs
A single handoff is a SQL join; a three-to-four-hop re-referral bounce loop is a graph (`CREATE OR REPLACE PROPERTY GRAPH` + variable-length ISO GQL) that exposes the bottleneck hub in the middle.

### You in Hand (Final Deliverable): A 45-Day Pathway & Bottleneck Brief
1. **Traced Multi-Hop Referral Paths:** Explicitly shown step-by-step (e.g., `Clinic A -> Intake Hub B -> Evaluator C -> Therapy Vendor D`) with transmission channels and wait days rather than merely described.
2. **Recommended `<= 45`-Day Route:** A compliant, credential-verified route (`accepts_medicaid`, `bilingual_services_listed`, `part_c_vendor_enrolled`) for an incoming referral.
3. **Regional Bounce Hub to Fix First:** Identification of the primary bottleneck node breaking regional compliance (and counterfactual child-days saved if upgraded from `paper_fax` to `ehr_electronic_portal`).
4. **Post-Output Equity Audit:** Analysis of which neighborhood demographics (`poverty_rate`, `no_vehicle_rate`, `audit_*` shares) the bottlenecks land on.
5. **Plain-Language Caregiver Action Note:** An accessible, family-ready summary and next-step guide in **English and Spanish**.

---

## 4. Proposed ADK + BigQuery Property Graph Architecture

```text
root_agent (dds_intake_coordinator)
├── BigQueryToolset               — Standard SQL for neighborhood demographics & views
├── trace_referral_graph_gql()    — Custom Python tool running variable-length ISO GQL
└── SequentialAgent (brief_generator_pipeline)
    ├── pathway_router_agent      — Selects optimal <=45-day bilingual/Medicaid route
    ├── equity_audit_agent        — Runs post-output demographic impact audit
    └── caregiver_note_agent      — Drafts plain-language English/Spanish family note
```

### Implementation Checklist
- [ ] **Step 1:** Clone the starter template repo (`Bornism/A4I2026-challenge-early-intervention`) into the workspace.
- [ ] **Step 2:** Inspect the BigQuery tables and define `CREATE OR REPLACE PROPERTY GRAPH` over provider/hub nodes (`CareNode`) and referral handoff edges (`ReferralHandoff`).
- [ ] **Step 3:** Write variable-length ISO GQL queries (`MATCH (a:CareNode)-[hops:ReferralHandoff]->{2,4}(b:CareNode)`) correlated on `case_chain_id` to expose bounce loops and cumulative wait times.
- [ ] **Step 4:** Wire GQL & demographic queries into ADK tools inside `agent/agent.py` and test multi-turn conversations in `adk web`.
- [ ] **Step 5:** Configure output formatting so every triage run produces the complete **45-Day Pathway & Bottleneck Brief**.

---

## 5. BigQuery Property Graph DDL & ISO GQL Reference (For Data & Agent Lanes)

### Step A: Declare the Property Graph (`a4i_early_intervention.ReferralGraph`)
*(Keep table names inside `NODE TABLES` and `EDGE TABLES` unbackticked, and exclude `provider_geom` so all vertex properties are scalar GQL types.)*

```sql
CREATE OR REPLACE PROPERTY GRAPH a4i_early_intervention.ReferralGraph
  NODE TABLES (
    a4i_early_intervention.pediatric_and_ei_provider_directory AS CareNode
      KEY (provider_id)
      LABEL CareNode
      PROPERTIES ALL COLUMNS EXCEPT (provider_geom)
  )
  EDGE TABLES (
    a4i_early_intervention.deidentified_part_c_referral_logs AS ReferralHandoff
      KEY (referral_event_id)
      SOURCE KEY (source_provider_id) REFERENCES CareNode (provider_id)
      DESTINATION KEY (target_provider_id) REFERENCES CareNode (provider_id)
      LABEL ReferralHandoff
      PROPERTIES ALL COLUMNS
  );
```

### Step B: Variable-Length ISO GQL Traversal (`-{2,4}->`)
```sql
GRAPH a4i_early_intervention.ReferralGraph
MATCH (clinic:CareNode {node_role: 'Screening_Pediatric_Clinic'})
      -[hops:ReferralHandoff]->{2,4}
      (vendor:CareNode {node_role: 'EI_Therapy_Vendor'})
WHERE ARRAY_LENGTH(hops) >= 3
  AND (SELECT COUNT(DISTINCT h.case_chain_id) FROM UNNEST(hops) AS h) = 1
LET total_hops = ARRAY_LENGTH(hops),
    chain_id = hops[OFFSET(0)].case_chain_id,
    chain_wait_days = (SELECT SUM(h.handoff_wait_days) FROM UNNEST(hops) AS h),
    fax_hops = (SELECT COUNTIF(h.transmission_channel = 'paper_fax') FROM UNNEST(hops) AS h)
FILTER chain_wait_days > 45
RETURN
  chain_id,
  clinic.synthetic_organization_name AS origin_clinic,
  hops[OFFSET(0)].target_provider_id AS intake_coordinator_id,
  vendor.synthetic_organization_name AS final_vendor,
  total_hops,
  fax_hops,
  chain_wait_days
ORDER BY chain_wait_days DESC
LIMIT 15;
```

---

## 6. Referral Dataset Findings & Rubric Guardrails

### Key Empirical Findings (`data/deidentified_part_c_referral_logs.parquet`)
* **149 directed `ReferralHandoff` edges across 44 `case_chain_id` episodes per state** (`MS`, `AL`, `GA`, `TX`, `CA`, `NY`):
  * **2-hop chains (`9`/state):** `16–24` days (avg `20.3d`) — **0% breach 45 days** (`100% ehr_electronic_portal`).
  * **3-hop chains (`9`/state):** `35–43` days (avg `38.3d`) — **0% breach 45 days** (`100% ehr_electronic_portal`).
  * **4-hop bounce chains (`26`/state):** `67–78` days (avg `72.1d`) — **100% breach 45 days** (`avg 2.69 paper_fax hops`).
* **Transmission Channel Penalty:**
  * `ehr_electronic_portal`: **13.3 days** mean wait, **10.1%** family drop-off.
  * `paper_fax`: **19.5 days** mean wait (+47% slower), **24.3%** family drop-off (2.4x higher attrition).
* **Two Bounce Causes at Hop 3/4:**
  * `Re-Referral Bounce: Evaluator Waitlist Saturation / Bilingual Slot Unavailable` (`18` chains/state — 69% of breaches).
  * `Re-Referral Bounce: Therapy Cap / Medicaid Credential Hold` (`8` chains/state — 31% of breaches).
* **36-Month Aging-Out Cliff Signal:** Every state has a **32-month-old toddler** trapped in a **73-day 4-hop chain**, reaching **34.4 months** before therapy starts.

### Four Mandatory Rubric Guardrails (25 Points)
1. **100% `[Synthetic]` Disclosure:** Explicitly state in agent outputs, UI, and deck that `SYN-PROV-*`, `SYN-PARTC-*`, and referral logs are **100% `[Synthetic]`** (so no real clinicians are defamed), while ACS under-5 counts are real US Census data.
2. **All-Zero `limited_english_rate` Trap:** `acs_under5_tract_demographics.limited_english_rate` is `0.0` in all rows. Do not filter or weight by it; use `nsch_developmental_screening_survey.primary_home_language` and `pediatric_and_ei_provider_directory.bilingual_services_listed`.
3. **6x Statewide NSCH Grain Trap:** `nsch_developmental_screening_survey` has 6 statewide strata per state (`geographic_level = 'Statewide'`). Never join to census tracts on `state_code` without filtering or aggregating first.
4. **Post-Output Equity Audit (`audit_*` Exclusion):** Never use `audit_black_share`, `audit_hispanic_share`, `audit_asian_share`, `audit_indigenous_share`, or `audit_white_share` inside routing logic. Join them strictly **post-output** alongside `poverty_rate` and `no_vehicle_rate`.
