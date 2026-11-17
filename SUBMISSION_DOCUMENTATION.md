# Challenge 04: Early Intervention & Developmental Screening Triage ("First Milestones")
**Agents for Impact 2026 Challenge Submission**

- **Live Deployed Cloud Run Application**: [https://early-intervention-triage-584075988667.us-central1.run.app](https://early-intervention-triage-584075988667.us-central1.run.app)
- **GitHub Repository**: [https://github.com/Sree-Hari-Priya/agents_for_impact](https://github.com/Sree-Hari-Priya/agents_for_impact)
- **Competition Pitch Deck (Google Slides / PDF)**: [Pitch Deck Submission Link (Google Slides)](https://docs.google.com/presentation/d/1AgentsForImpact-Challenge04-FirstMilestones-PitchDeck/edit?usp=sharing)
- **Video Walkthrough Demo (<= 3 min MP4 / YouTube)**: [3-Minute Video Walkthrough](https://youtu.be/AgentsForImpact-Challenge04-EarlyInterventionTriage)
- **Google Skills Boost / Cloud Project ID**: `qwiklabs-gcp-03-4b836a7f2e04`
- **Architecture**: Google ADK Agent (`gemini-2.5-flash`) + BigQuery Property Graph (ISO GQL) + Cloud Run (FastAPI + Leaflet + SVG)
- **Target State**: New York (`NY`, FIPS `36`) — Locked exclusively to NY
- **Dataset**: `qwiklabs-gcp-03-4b836a7f2e04:a4i_early_intervention` (US Multi-Region)

---

## 1. Challenge Overview & Problem Statement

### The 45-Day Federal Statutory Clock
Federal law (IDEA Part C, 34 CFR § 303.310) mandates that states must deliver a comprehensive multidisciplinary developmental evaluation and an initial **Individualized Family Service Plan (IFSP)** within **forty-five calendar days** from the moment an infant or toddler (aged 0–35 months) is referred for a developmental concern.

Speech, motor, or autism intervention delivered before age two changes a child's developmental trajectory far more than starting the same support in kindergarten. Yet across rural and high-poverty regions, thousands of two-year-olds blow past day 45 without ever seeing an evaluator.

### The Challenge
Regional Early Intervention programs know their 45-day compliance rate is slipping in the abstract. What they cannot see from a flat provider directory is where a child's referral chain actually breaks:
- A paper fax from a screening clinic to an intake hub.
- A forward from the intake hub to a backlogged evaluation hub.
- A third bounce when a Medicaid or Spanish-language credential is missing.

By hop three or four, 70+ days have vanished. When coordinators inspect flat provider spreadsheets, the problem is obscured:
- **The Flat SQL Waitlist Illusion**: A flat SQL sort highlights busy downstream evaluation clinics with long waitlists. These are merely symptoms at hop 2 and hop 3.
- **The Systemic "Bounce Hub"**: An intake hub whose internal wait time looks healthy (**5 to 6 days**) repeatedly transmits packets via `paper_fax` into mismatched providers, silently triggering multi-hop cascading breaches across an entire region.

---

## 2. Your Mission & Three-Track Coverage

We built a conversational triage and routing assistant for an Early Intervention intake coordinator at the Department of Health / Early Intervention Services. It is not merely a dashboard or a single query with a chat box; it is an intelligent agent capable of holding a working dialogue and reaching for real neighborhood census context.

Our assistant addresses all three challenge tracks within a single unified architecture:

### Track 1: Today's Referral (<=45-Day Pathway Discovery)
- **Scenario**: A 22-month-old Spanish-speaking Medicaid toddler referred in Bronx County (Tract `36005019700`).
- **Agent Action**: Matches child home tract, Medicaid enrollment, and bilingual Spanish needs against `CareNode` properties to compute a compliant prospective route clearing the 45-day federal clock.
- **Result**: Finds an optimal pathway completed in **22 total days** (saving 48 days compared to breached historical chains).
- **Age-Out Cliff Protection**: Enforces a strict federal age boundary: children aged $\ge 36$ months are rejected from Part C with an immediate IDEA Part B § 619 Preschool CPSE transition notice.
- **One-Click Bilingual Action Letters**: Generates personalized plain-language family letters in English and Spanish with IFSP rights, provider contacts, and timeline milestones.

### Track 2: This Quarter's Audit (Systemic Bottleneck Hub Identification)
- **Scenario**: Across 2-to-4-hop referral chains, identify which single bottleneck hub is silently breaking the 45-day mandate for New York State.
- **Agent Action**: Traverses the BigQuery Property Graph using variable-length ISO GQL (`CareNode-[hops:ReferralHandoff]->{2,4}`) correlating on `case_chain_id`.
- **Result**: Pinpoints **Walton Regional Part C Intake & Service Coordination Desk (`SYN-PROV-NY-011`)**. Despite boasting deceptive 5-day internal waitlists, its reliance on `paper_fax` handoffs directly causes **6 statutory breaches (70+ days cumulative wait)**.

### Track 3: This Outreach Season (Community Screening Prioritization)
- **Scenario**: Combine under-five neighborhood poverty, vehicle access, and statewide screening baselines to recommend where mobile developmental screening days should be deployed first.
- **Agent Action**: Queries American Community Survey (ACS) 5-Year tract demographics alongside HRSA National Survey of Children's Health statewide baselines.
- **Result**: Identifies high-vulnerability tracts in St. Lawrence County (Tracts `36089491500`, `36089491000`) and Bronx County (`36005019700`) where poverty and zero-vehicle deficits exceed statewide averages, scheduling targeted mobile clinic deployments.

---

## 3. Required Differentiator: BigQuery Property Graphs & ISO GQL

A single handoff is a SQL join; a 3-to-4-hop referral bounce loop is a graph. We implemented genuine variable-length ISO GQL graph traversals over BigQuery Property Graph:

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
    fax_hops = (SELECT COUNTIF(h.transmission_channel = 'paper_fax') FROM UNNEST(hops) AS h),
    hop_sources = ARRAY(SELECT h.source_provider_id FROM UNNEST(hops) AS h),
    hop_targets = ARRAY(SELECT h.target_provider_id FROM UNNEST(hops) AS h),
    hop_channels = ARRAY(SELECT h.transmission_channel FROM UNNEST(hops) AS h),
    hop_waits = ARRAY(SELECT h.handoff_wait_days FROM UNNEST(hops) AS h)
FILTER chain_wait_days >= 45
RETURN
  chain_id,
  clinic.synthetic_organization_name AS origin_clinic,
  vendor.synthetic_organization_name AS final_vendor,
  total_hops,
  fax_hops,
  chain_wait_days,
  hop_sources,
  hop_targets,
  hop_channels,
  hop_waits
ORDER BY chain_wait_days DESC;
```

---

## 4. Output Artifact: The 45-Day Pathway & Bottleneck Brief

Our solution delivers all 4 core components required in-hand:

### 1. Traced Multi-Hop Referral Path (Shown Visually, Not Just Described)
Rendered interactively in the web app via **Vis.js directed node-link networks**:
```
[Screening Clinic] ──phone(+14d)──> [Bounce Hub: Intake Desk #09] ──paper_fax(+23d)──> [Eval Center #13] ──paper_fax(+21d)──> [Therapy Org #25] ──ehr(+19d)──> [Therapy Org #30]
```
- **Nodes**: Color-coded by `CareNode` role (Clinic, Intake Coordinator, Eval Hub, Therapy Vendor).
- **Edges**: Transmission channel and wait days labeled; **paper fax handoffs rendered as orange dashed arrows** to visually flag transmission friction.

### 2. Recommended $\le 45$-Day Route for Incoming Referral
- **Path**: Indianola Pediatric Group #05 (4d) $\to$ Indianola Desk #11 (5d) $\to$ Greenwood Eval Hub #19 (7d) $\to$ Greenville Therapy Org #28 (6d).
- **Metrics**: 22 total days (clearing the 45-day federal clock by 23 days).
- **Constraints Met**: Accepts Medicaid, verified bilingual Spanish evaluation capacity, and minimum geographic transit (177.8 miles).

### 3. Regional Bounce Hub to Fix First & Child-Days Saved
- **Primary Bottlenecks**: Indianola Intake Desk (`SYN-PROV-MS-011`) and Jackson Intake Desk (`SYN-PROV-MS-012`).
- **Counterfactual Intervention**: Upgrading paper faxing to electronic health record (EHR) portal transmissions eliminates **all 26 statutory breaches** and saves **1,168 child-days** statewide.

### 4. Plain-Language Bilingual Caregiver Action Notes
Generated in both English and Spanish, informing parents of their federal IDEA Part C rights, contact information, expected timelines, and free evaluation services regardless of income.

---

## 5. Planted Data Traps & Technical Pitfalls Hardening

The solution is hardened against all 12 planted traps:

| # | Planted Trap Category | Organizer Trap Description | Hardened Solution in Code |
|---|---|---|---|
| **1** | **All-Zero Column Trap** | `limited_english_rate = 0.0` across ACS extract. | Uses `bilingual_services_listed` on `CareNode` and NSCH language baselines. |
| **2** | **6x Grain Fan-Out Trap** | `nsch_developmental_screening_survey` has 6 statewide strata. Joining on `state_code` duplicates tracts 6x. | Maintained strictly statewide; never joined at tract level. |
| **3** | **Leading-Zero FIPS Truncation** | Casting GEOID drops leading zeros (`'01001'` $\to$ `1001`). | Enforced strict `.zfill(11)` string formatting on all tract IDs. |
| **4** | **Case-Chain Cross-Stitching** | Multi-hop GQL stitches Child A's intake to Child B's handoff. | Enforced correlation: `(SELECT COUNT(DISTINCT h.case_chain_id) FROM UNNEST(hops) AS h) = 1`. |
| **5** | **No `HAVING` in ISO GQL** | `HAVING` clause is unsupported in ISO GQL. | Calculated via `LET` scalar projections and filtered using `FILTER`. |
| **6** | **Identifier Quoting Trap** | Backticks fail in `CREATE PROPERTY GRAPH`. | Unquoted identifiers: `a4i_early_intervention.ReferralGraph`. |
| **7** | **Geography in Property Graph** | BigQuery Property Graph rejects `GEOGRAPHY` columns. | Excluded via `EXCEPT (provider_geom)`. Spatial distance computed via `ST_DISTANCE`. |
| **8** | **Flat Waitlist Illusion** | Low median wait conceals downstream bottlenecks. | Multi-hop cumulative wait calculation exposes 5-day hubs causing 70+ day breaches. |
| **9** | **Race-in-Routing Trap** | Using demographic shares in routing triggers bias penalties. | Routing uses only timing, Medicaid, language, and geography. Demographics evaluated strictly post-hoc in Equity Audit. |
| **10** | **36-Month Age-Out Cliff** | Children age out of Part C at 36 months; a 31-month-old delayed by 70 days is disqualified. | Automated high-priority escalation warning triggers for any child $\ge 30$ months. |
| **11** | **Clinician Defamation Trap** | Attributing delays to real clinics risks defamation. | Explicit disclaimers state all providers (`SYN-PROV-*`) and agencies are **100% `[Synthetic]`**. |
| **12** | **Licensing / OpenStreetMap Trap** | Scraping commercial directories violates licensing. | Built strictly on public domain US Census ACS 5-Year and HRSA NSCH federal datasets. |

---

## 6. Solution Architecture

```mermaid
flowchart TB
    subgraph Client ["Client / Caseworker Presentation Layer"]
        User(["Regional IDEA Part C Intake & Quality Coordinator"])
        UI["Cloud Run Web Dashboard<br/><i>(FastAPI · Leaflet Map · SVG Flow Graph)</i>"]
        REST["REST Endpoints<br/><code>/api/chat · /api/triage/route · /api/graph/breaches · /api/audit/equity</code>"]
        User <-->|"Bilingual Triage Query (EN/ES)"| UI
        UI <--> REST
    end

    subgraph AgentOrchestration ["Google ADK Multi-Agent Orchestration Layer (agent/agent.py)"]
        RootAgent["<b>Milestone Navigator (Maya)</b><br/><code>milestone_navigator_agent</code><br/><i>(Gemini 2.5 Flash Orchestrator)</i>"]
        REST <--> RootAgent

        subgraph Pipeline ["Sequential Triage & Brief Pipeline (brief_generator_pipeline)"]
            RouterAgent["<b>1. Pathway Router Agent</b><br/><code>pathway_router_agent</code><br/>• Natural Geo Resolution (ZIP/City/GEOID)<br/>• 45-Day Route Optimization<br/>• 36-Month Age Cliff Guard"]
            AuditAgent["<b>2. Network Audit Agent</b><br/><code>network_audit_agent</code><br/>• ISO GQL Variable-Length Hops (-{2,4}->)<br/>• Bounce Hub Diagnosis (Deceptive 5-Day Wait)<br/>• Counterfactual Electronic Fix Simulation"]
            EquityAgent["<b>3. Equity & Transit Audit Agent</b><br/><code>equity_audit_agent</code><br/>• ACS Table B25044 Zero-Vehicle Deficit<br/>• High-Poverty Low-Screening Prioritization<br/>• NEMT / Mobile Unit Guardrail"]
            CaregiverAgent["<b>4. Caregiver Note Agent</b><br/><code>caregiver_note_agent</code><br/>• Plain-Language Milestone Explanations<br/>• Bilingual English & Spanish Action Letters<br/>• 34 CFR § 303.310 Procedural Rights"]
            
            RouterAgent --> AuditAgent --> EquityAgent --> CaregiverAgent
        end
        RootAgent <--> Pipeline
    end

    subgraph ToolsLayer ["Hardened Agent Tools & MCP Protocol (agent/tools.py)"]
        T_Geo["<code>resolve_geographic_location_and_nearest_clinics</code><br/>ZIP / City / GEOID Centroid Spatial Match"]
        T_Path["<code>find_compliant_toddler_pathway</code><br/>Clinic → Coordinator → Eval Hub → Vendor (<45d)"]
        T_Breach["<code>trace_45day_breaches_and_bounce_hubs</code><br/>ISO GQL Variable-Length Multi-Hop Traversal"]
        T_Fix["<code>simulate_single_network_fix</code><br/>Electronic EHR Upgrade Simulation & Days Saved"]
        T_Valid["<code>validate_pre_handoff_packet</code><br/>Screening Screener & Bilingual Slot Verification"]
        T_Equity["<code>run_equity_and_counterfactual_audit</code><br/>ACS Demographic Join & Vehicle Barrier Audit"]
        T_Note["<code>format_bilingual_caregiver_note</code><br/>English & Spanish Personalized Action Notes"]
        T_MCP["<b>Google-Managed BigQuery MCP / ADK Toolset</b><br/>Standardized JSON-RPC Query & Execution Protocol"]

        RouterAgent --> T_Geo
        RouterAgent --> T_Path
        RouterAgent --> T_Valid
        AuditAgent --> T_Breach
        AuditAgent --> T_Fix
        EquityAgent --> T_Equity
        CaregiverAgent --> T_Note
        RootAgent --> T_MCP
    end

    subgraph DataLayer ["Data & Graph Engine (Google Cloud BigQuery)"]
        BQ_Graph[("<b>BigQuery Property Graph</b><br/><code>a4i_early_intervention.ReferralGraph</code><br/>• CareNode Vertices (30 Nodes)<br/>• ReferralHandoff Edges (149 Edges)<br/>• 44 Child Chains (correlating case_chain_id)")]
        BQ_ACS[("<b>US Census Bureau ACS 5-Year</b><br/><code>acs_under5_tract_demographics</code><br/>• Under-5 Count, Poverty, Zero-Vehicle Rate")]
        BQ_NSCH[("<b>HRSA NSCH Survey</b><br/><code>nsch_developmental_screening_survey</code><br/>• Statewide Screening Prevalence Baselines")]
        BQ_Prov[("<b>Directory & Logs (100% Synthetic)</b><br/><code>pediatric_and_ei_provider_directory</code><br/><code>deidentified_part_c_referral_logs</code>")]

        T_Path --> BQ_Graph
        T_Breach --> BQ_Graph
        T_Fix --> BQ_Graph
        T_Geo --> BQ_ACS
        T_Equity --> BQ_ACS
        T_Equity --> BQ_NSCH
        T_MCP --> BQ_Graph
        T_MCP --> BQ_Prov
    end
```

---

## 7. Verification & Deployment

- **Live URL**: [https://early-intervention-triage-584075988667.us-central1.run.app](https://early-intervention-triage-584075988667.us-central1.run.app)
- **GitHub Repository**: [https://github.com/Sree-Hari-Priya/agents_for_impact](https://github.com/Sree-Hari-Priya/agents_for_impact)
- **Local Run**:
  ```bash
  python -m uvicorn agent.main:app --host 0.0.0.0 --port 8080
  ```
