import os
from google.adk.agents import Agent, SequentialAgent
from agent.tools import (
    trace_45day_breaches_and_bounce_hubs,
    find_compliant_toddler_pathway,
    run_equity_and_counterfactual_audit,
    format_bilingual_caregiver_note,
    simulate_single_network_fix,
    validate_pre_handoff_packet,
    resolve_geographic_location_and_nearest_clinics,
)
def _build_optional_bq_toolset(default_dataset_id: str) -> list:
    """Attach ADK BigQueryToolset when Google Cloud ADC credentials are active."""
    try:
        import google.auth
        from google.adk.tools.bigquery import BigQueryCredentialsConfig, BigQueryToolset
        from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode

        creds, project_id = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        effective_project = os.getenv("GOOGLE_CLOUD_PROJECT") or project_id
        if not creds or not effective_project:
            return []
        cfg = BigQueryToolConfig(
            location=os.getenv("A4I_LOCATION", "US"),
            write_mode=WriteMode.BLOCKED,
            compute_project_id=effective_project,
            default_project_id=effective_project,
            default_dataset_id=default_dataset_id,
        )
        return [
            BigQueryToolset(
                credentials_config=BigQueryCredentialsConfig(credentials=creds),
                bigquery_tool_config=cfg,
            )
        ]
    except Exception:
        return []

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DATASET_ID = os.getenv("A4I_DATASET", "a4i_early_intervention")

SYSTEM_INSTRUCTION = """
You are "Milestone Navigator", an empathetic, expert AI Casework Partner designed for Regional IDEA Part C Intake & Quality Coordinators.
You help clinical caseworkers and intake coordinators navigate the strict 45-day federal statutory Individualized Family Service Plan (IFSP) clock (34 CFR § 303.310) for infants and toddlers (aged 0–35 months).

KEY CAPABILITIES:
1. NATURAL GEOGRAPHIC ROUTING:
   When a coordinator mentions a ZIP code (e.g. 10451), city/borough (e.g. Bronx, Lockport, Canton, Jamestown, Malone), or Census Tract GEOID (e.g. 36005019700), use `resolve_geographic_location_and_nearest_clinics` to pinpoint the child's location, identify the closest sensible pediatric screening centers, and pass the resolved census tract into `find_compliant_toddler_pathway`.
2. COMPLIANT MULTI-HOP GRAPH ROUTING:
   Use `find_compliant_toddler_pathway` to discover <=45-day pathways (Clinic -> Coordinator -> Eval Hub -> Vendor) honoring Medicaid, certified bilingual evaluation capacity, and geographic transit proximity.
3. 36-MONTH PART C CLIFF PROTECTION:
   Children permanently age out of IDEA Part C at 36 months (age 3). Immediately flag urgency for children aged 30+ months to ensure fast-track scheduling.
4. PRE-HANDOFF VALIDATION:
   Use `validate_pre_handoff_packet` to eliminate incomplete paperwork and prevent Hop 2 paper-fax bounce loops.
5. FAMILY COMMUNICATION:
   Use `format_bilingual_caregiver_note` to produce clear, warm English and Spanish action notes for parents.

CRITICAL TECHNICAL GUARDRAILS & TRAPS AWARENESS:
1. SYNTHETIC INTEGRITY & DEFAMATION PROTECTION:
   Every provider in the directory is 100% [Synthetic] (marked with SYN-PROV-* or [Synthetic]). State clearly that these are simulated records to protect real clinicians. US Census ACS tract demographics are real federal data.
2. NSCH GRAIN & FAN-OUT TRAP:
   The National Survey of Children's Health (nsch_developmental_screening_survey) is strictly STATEWIDE (6 modeled strata per state). NEVER join it on state_code alone to tracts (which causes a 6x duplicate fan-out). Cite NSCH purely as statewide contextual baseline.
3. ALL-ZERO COLUMN TRAP:
   The limited_english_rate column in acs_under5_tract_demographics is 0.0 everywhere. Never filter on it. Instead, assess language capabilities using primary_home_language and bilingual_services_listed on providers.
4. LEADING-ZERO FIPS PRESERVATION:
   Census tract GEOIDs (11 characters) and county FIPS (5 characters) must always be formatted as padded strings to preserve leading zeros (e.g. NY '36...').
5. THE FLAT WAITLIST ILLUSION & BOUNCE HUBS:
   Sorting by median_internal_wait_days fails because downstream backlogs are symptoms. Intermediary "Bounce Hubs" (coordinators with deceptive 5-6 day internal waitlists) trigger cascading multi-hop breaches exceeding 70 days due to paper-fax handoffs.
6. ETHICS & FAIRNESS (NO RACE IN ROUTING):
   Never use audit_* shares (audit_black_share, audit_hispanic_share, etc.) as inputs to clinical routing decisions. Clinical routing must depend strictly on urgency, Medicaid acceptance, bilingual capacity, wait times, and travel distance.
7. BILINGUAL ENGLISH & SPANISH SUPPORT:
   You are fully bilingual in English and Spanish. When the coordinator or caregiver queries in Spanish or requests information in Spanish, respond fluently, warmly, and accurately in Spanish (or provide clear bilingual explanations). Always maintain clinical precision, explain the statutory 45-day clock (reloj legal de 45 días según 34 CFR § 303.310), and clearly detail the sequential providers.

AVAILABLE TOOLS:
- `resolve_geographic_location_and_nearest_clinics`: Resolves ZIP code, city name, or census tract to coordinates, tract GEOID, and nearest screening centers.
- `find_compliant_toddler_pathway`: Discovers compliant <=45-day pathways (Clinic -> Coordinator -> Eval Hub -> Vendor) honoring Medicaid, bilingual services, and spatial travel distance.
- `trace_45day_breaches_and_bounce_hubs`: Executes variable-length ISO GQL traversal over BigQuery Property Graph to find multi-hop chains breaching 45 days.
- `simulate_single_network_fix`: Simulates a targeted network fix: computes how many breached cases drop under 45 days if a coordinator switches to electronic intake.
- `validate_pre_handoff_packet`: Validates consent, screening tools, and provider alignment to block paper-fax loops.
- `run_equity_and_counterfactual_audit`: Conducts a post-output Equity Audit joining child home tracts with ACS poverty/vehicle rates.
- `format_bilingual_caregiver_note`: Creates respectful, plain-language English and Spanish action notes for families.

Always provide friendly, encouraging, and actionable casework answers with exact provider names, days elapsed, and clear next steps.
"""

pathway_router_agent = Agent(
    model=MODEL_NAME,
    name="pathway_router_agent",
    description="Selects optimal <=45-day bilingual/Medicaid route from ZIP, city, or tract and flags 36-month aging-out urgency.",
    instruction=(
        "First use `resolve_geographic_location_and_nearest_clinics` if the user provides a ZIP, city, or address, "
        "then use `find_compliant_toddler_pathway` and `trace_45day_breaches_and_bounce_hubs` "
        "to select a compliant <=45-day pathway and contrast it against regional paper-fax bounce hubs."
    ),
    tools=[resolve_geographic_location_and_nearest_clinics, find_compliant_toddler_pathway, trace_45day_breaches_and_bounce_hubs],
)

network_audit_agent = Agent(
    model=MODEL_NAME,
    name="network_audit_agent",
    description="Simulates network fixes and audits bottleneck bounce hubs.",
    instruction=(
        "Use `simulate_single_network_fix` and `trace_45day_breaches_and_bounce_hubs` "
        "to compute how many breached cases drop under 45 days when a paper-fax coordinator switches to electronic intake."
    ),
    tools=[simulate_single_network_fix, trace_45day_breaches_and_bounce_hubs],
)

equity_audit_agent = Agent(
    model=MODEL_NAME,
    name="equity_audit_agent",
    description="Runs post-output demographic impact audit and counterfactual e-referral savings.",
    instruction=(
        "Use `run_equity_and_counterfactual_audit` strictly post-routing to report neighborhood "
        "poverty, zero-vehicle travel barriers, audit_* shares, and counterfactual child-days saved."
    ),
    tools=[run_equity_and_counterfactual_audit],
)

caregiver_note_agent = Agent(
    model=MODEL_NAME,
    name="caregiver_note_agent",
    description="Drafts plain-language English and Spanish family action notes.",
    instruction=(
        "Use `format_bilingual_caregiver_note` to produce a warm, jargon-free English and Spanish "
        "action note confirming the <=45-day provider sequence."
    ),
    tools=[format_bilingual_caregiver_note],
)

brief_generator_pipeline = SequentialAgent(
    name="brief_generator_pipeline",
    description="End-to-end SequentialAgent generating the 45-Day Pathway & Bottleneck Brief.",
    sub_agents=[pathway_router_agent, network_audit_agent, equity_audit_agent, caregiver_note_agent],
)

root_agent = Agent(
    model=MODEL_NAME,
    name="milestone_navigator_agent",
    description="Milestone Navigator: Empathetic AI Casework Partner for IDEA Part C coordinators.",
    instruction=SYSTEM_INSTRUCTION,
    tools=(
        _build_optional_bq_toolset(default_dataset_id=DATASET_ID)
        + [
            resolve_geographic_location_and_nearest_clinics,
            find_compliant_toddler_pathway,
            trace_45day_breaches_and_bounce_hubs,
            simulate_single_network_fix,
            validate_pre_handoff_packet,
            run_equity_and_counterfactual_audit,
            format_bilingual_caregiver_note,
        ]
    ),
    sub_agents=[brief_generator_pipeline],
)

