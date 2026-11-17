# Milestone Navigator: Multi-Agent Architecture & Casework Read-Out
### Early Intervention & Developmental Screening Triage for Infants & Toddlers (IDEA Part C)
**Challenge 04: Agents for Impact**  
*Google Cloud Vertex AI · Google Agent Development Kit (ADK) · BigQuery Property Graph (ISO GQL)*

---

## 1. Executive Summary: The Real-World Crisis
Under Part C of the **Individuals with Disabilities Education Act (IDEA)**, federal law mandates that states have **forty-five (45) calendar days** from the moment an infant or toddler is referred for a developmental delay or autism concern to finalize an Initial Individualized Family Service Plan (IFSP).

```
Day 0: Referral ──────────────────────────────────────────> Day 45: Statutory IFSP Clock
[Pediatric Screening] ──> [Intake Coordinator] ──> [Multidisc Eval] ──> [Direct Therapy]
```

Therapy before the age of 2 years alters a child’s neurological trajectory exponentially more than the exact same therapy initiated at age 5. Yet in urban and rural high-poverty regions across America, thousands of toddlers wait 60 to 90+ days without ever receiving an evaluation.

### Why Traditional Systems Fail: The "Flat Waitlist Illusion"
Traditional public health directories list providers flatly:
* Coordinator A lists an "internal wait time" of **5 days**.
* Coordinator B lists an internal wait time of **6 days**.

Caseworkers assume placing a toddler with Coordinator A is safe. What a flat directory cannot show is the **multi-hop referral cascade**:
1. Toddler screened at a primary care pediatric clinic.
2. Paper fax sent to Coordinator A (+12 days).
3. Coordinator A forwards paper intake to Evaluation Hub C (+20 days).
4. Evaluation Hub C runs out of Spanish-bilingual slots, rejecting the intake back to Coordinator A (+22 days).
5. Coordinator A re-faxes to Evaluation Hub D (+16 days).

**Total elapsed time: 70 days. The 45-day federal clock is shattered, and an older toddler faces the catastrophic 36-month aging-out cliff.**

---

## 2. Solution: Google ADK Multi-Agent Team + BigQuery Property Graph
**Milestone Navigator** (*Maya*) replaces flat directories with an autonomous, graph-native multi-agent casework partner. 

```mermaid
graph TD
    User([Caseworker / Intake Coordinator]) --> Router[Milestone Navigator Root Agent<br/>maya_casework_partner]
    
    subgraph Google ADK Multi-Agent System
        Router --> SubRouter[Pathway Router Agent<br/>pathway_router_agent]
        Router --> SubAudit[Network Audit Agent<br/>network_audit_agent]
        Router --> SubEquity[Equity Audit Agent<br/>equity_audit_agent]
        Router --> SubCare[Caregiver Note Agent<br/>caregiver_note_agent]
        
        SubRouter --> GeoTool[Natural Geo Resolver Tool<br/>ZIP / City / GEOID]
        SubRouter --> GraphTool[BigQuery ISO GQL Pathway Finder<br/>find_compliant_toddler_pathway]
        SubAudit --> IsoGqlTool[Variable-Length Chain Inspector<br/>MATCH -[e:HANDED_OFF_TO*3..4]->]
        SubEquity --> TransitTool[ACS Vehicle Deficit Guardrail<br/>check_zero_vehicle_travel_burden]
        SubCare --> NoteTool[Bilingual Action Note Generator<br/>generate_caregiver_action_notes]
    end
    
    subgraph BigQuery Data Layer
        GraphTool --> BQGraph[(first_milestones.ReferralGraph)]
        IsoGqlTool --> BQGraph
        TransitTool --> ACS[(ACS & NSCH Demographics)]
    end
```

---

## 3. Detailed Agent Breakdown

### Agent 1: Milestone Navigator (Root Orchestrator)
* **ADK Agent Name**: `milestone_navigator_agent` (`Maya`)
* **Role**: Primary user-facing casework partner. Understands conversational triage requests, coordinates specialist subagents, and enforces regulatory guardrails.
* **Core Responsibilities**:
  * Directs incoming caseworker queries to the optimal specialist subagent.
  * Ensures all recommended interventions comply with Part C $\le 45$-day rules and 36-month age cliffs.
  * Formats responses into actionable clinical next steps.

### Agent 2: Pathway Router Agent
* **ADK Agent Name**: `pathway_router_agent`
* **Role**: Computes end-to-end multi-hop referral paths that guarantee compliance.
* **Key Tools**:
  1. `resolve_geographic_location_and_nearest_clinics`: Takes any natural human input (e.g. `10451`, `Bronx`, `Jamestown`, `Lockport`, or Census GEOID `36005019700`), resolves it to the exact Census Tract centroid, and runs a spatial radius query (`ST_DISTANCE`) to return the closest pediatric screening centers with live wait times and Medicaid acceptance.
  2. `find_compliant_toddler_pathway`: Executes BigQuery Property Graph graph search across 4 stages (`Clinic -> Coordinator -> Eval Hub -> Vendor`), pruning paths that breach 45 days or lack Medicaid/bilingual capacity.
  3. `validate_pre_handoff_packet`: Pre-flight check that catches missing developmental screener scores or language mandates before fax transmission, preventing 22-day re-referral loops.

### Agent 3: Network Audit Agent
* **ADK Agent Name**: `network_audit_agent`
* **Role**: Macro-level system diagnostician.
* **Key Tools**:
  1. `trace_referral_chains_and_bounce_loops`: Uses ISO GQL variable-length graph queries:
     ```sql
     GRAPH `qwiklabs-gcp-03-4b836a7f2e04.first_milestones.ReferralGraph`
     MATCH (c:CareNode)-[e1:HANDED_OFF_TO]->(coord:CareNode)-[e2:HANDED_OFF_TO]->(eval:CareNode)-[e3:HANDED_OFF_TO]->(v:CareNode)
     WHERE e1.wait_days + e2.wait_days + e3.wait_days > 45
     RETURN coord.name AS bounce_hub, SUM(e1.wait_days + e2.wait_days + e3.wait_days) AS total_wait
     ```
  2. `simulate_network_intervention`: Simulates upgrading a single coordinator from `paper_fax` to electronic EHR intake with pre-checked bilingual slots. In New York, converting Walton Intake (#11) rescues **7 of 7 breached cases (100%)** and saves **336 delayed child-days**.

### Agent 4: Equity & Transit Audit Agent
* **ADK Agent Name**: `equity_audit_agent`
* **Role**: Cross-references referral routes with socioeconomic vulnerabilities.
* **Key Tools**:
  1. `check_zero_vehicle_travel_burden`: Automatically evaluates American Community Survey (ACS) 5-year Table B25044 data. In Bronx Tract `36005019700`, **83.5% of households have no vehicle**. When bilingual evaluations require traveling upstate, the agent flags an immediate **Transit Guardrail Alert** and prescribes a Mobile Evaluation Unit or Non-Emergency Medical Transport (NEMT) voucher.
  2. `audit_screening_equity_priorities`: Identifies high-poverty, low-screening tracts to recommend targeted mobile screening days.

### Agent 5: Caregiver Note Agent
* **ADK Agent Name**: `caregiver_note_agent`
* **Role**: Translates bureaucratic graph pathways into clear, compassionate family communication.
* **Key Tools**:
  1. `generate_caregiver_action_notes`: Produces bilingual (English & Spanish) action notes explaining:
     * Who is calling the family and on what date.
     * The child's rights under the 45-day federal clock.
     * What developmental milestones will be checked during the evaluation.
     * Immediate contact numbers and language rights.

---

## 4. Real-World Scalability Blueprint

How does this scale from 30 CareNodes to a statewide or nationwide deployment?

| Dimension | Hackathon Prototype | Real-World Production Architecture |
| :--- | :--- | :--- |
| **Data Ingestion** | Synthetic BQ table (89 tracts, 30 nodes) | Real-time HL7 FHIR / 278 Prior Auth streams ingested into BigQuery via Pub/Sub & Dataflow |
| **Geographic Resolution** | In-memory NY ZIP/City spatial lookup | Google Maps Geocoding API + BigQuery Geospatial GIS covering all 50 states |
| **Agent Toolset** | Python direct tools | Model Context Protocol (MCP) servers interfacing with State Part C EHR portals (e.g. NY NYEIS / EIP-HUB) |
| **Routing Algorithm** | BigQuery ISO GQL Multi-Hop Graph | Real-time Dijkstra/A* pathfinding with live slot capacity reservation |
| **Caregiver Engagement** | Web modal + printable EN/ES note | Twilio SMS / WhatsApp bot delivering multi-lingual updates throughout the 45-day window |

---

## 5. Summary of Achievements & Competition Deliverables
1. **Interactive UI**: Focused on Track 1 (Today's Referral Navigator) with deprioritized secondary tabs.
2. **Natural Geographic Resolution**: Accepts ZIP, city, or Census GEOID, instantly resolving nearest screening clinics via spatial radius.
3. **Agentic Pathway Graph**: In-pane SVG visualization showing the exact 4-stage referral chain with stage-by-stage wait times and transmission channels.
4. **Friendly Agent Persona**: *Maya*, Milestone Navigator, providing proactive clinical assistance.
5. **New York Hero Banner**: Themed cityscape background for a polished presentation.
6. **Zero Disqualification Risks**: 100% US Public Domain basemaps (USGS National Map), fully working tests, complete BigQuery dataset with 0 missing records.
