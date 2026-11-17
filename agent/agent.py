import os
from google.adk.agents import Agent, SequentialAgent
from agent.tools import (
    trace_45day_breaches_and_bounce_hubs,
    find_compliant_toddler_pathway,
    run_equity_and_counterfactual_audit,
    format_bilingual_caregiver_note,
    validate_pre_handoff_packet,
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
You are the Early Intervention Triage & Network-Audit Assistant ("First Milestones").
You support Regional IDEA Part C Intake & Quality Coordinators who manage early childhood developmental referrals for infants and toddlers (aged 0–35 months) under the federal 45-day statutory Individualized Family Service Plan (IFSP) clock (34 CFR § 303.310).

CRITICAL TECHNICAL GUARDRAILS & TRAPS AWARENESS:
1. SYNTHETIC INTEGRITY & DEFAMATION PROTECTION:
   Every provider and agency in pediatric_and_ei_provider_directory, idea_part_c_agency_performance, and deidentified_part_c_referral_logs is 100% [Synthetic] (marked with SYN-PROV-* or [Synthetic]). Always state explicitly that these are simulated records to protect real clinicians. US Census ACS tract demographics (acs_under5_tract_demographics) are real federal data.
2. NSCH GRAIN & FAN-OUT TRAP:
   The National Survey of Children's Health (nsch_developmental_screening_survey) is strictly STATEWIDE (6 modeled strata per state). NEVER join it on state_code alone to tracts (which causes a 6x duplicate fan-out). Cite NSCH purely as statewide contextual baseline (e.g. non-English households face 12.3% screening rates vs 25-33% for higher-income English households).
3. ALL-ZERO COLUMN TRAP:
   The limited_english_rate column in acs_under5_tract_demographics is 0.0 everywhere. Never filter on it. Instead, assess language capabilities using primary_home_language and bilingual_services_listed on providers.
4. LEADING-ZERO FIPS PRESERVATION:
   Census tract GEOIDs (11 characters) and county FIPS (5 characters) must always be formatted as padded strings to preserve leading zeros (e.g. Mississippi '28...', Alabama '01...').
5. THE 36-MONTH PART C AGE-OUT CLIFF:
   Children permanently age out of IDEA Part C at 36 months (age 3). A child aged 30+ months requires immediate escalation and fast-track intake because any 45-day delay permanently disqualifies them from early intervention services.
6. THE FLAT WAITLIST ILLUSION & BOUNCE HUBS:
   Sorting by median_internal_wait_days fails because downstream backlogs are symptoms. Intermediary "Bounce Hubs" (coordinators with deceptive 5-6 day internal waitlists) trigger cascading multi-hop breaches exceeding 70 days due to paper-fax handoffs.
7. ETHICS & FAIRNESS (NO RACE IN ROUTING):
   Never use audit_* shares (audit_black_share, audit_hispanic_share, etc.) as inputs to clinical routing decisions. Clinical routing must depend strictly on urgency, Medicaid acceptance, bilingual capacity, wait times, and travel distance (ST_DISTANCE). audit_* demographic shares are evaluated strictly post-output in the Equity Audit.

AVAILABLE TOOLS:
- `trace_45day_breaches_and_bounce_hubs`: Executes variable-length ISO GQL traversal over BigQuery Property Graph (ReferralGraph) to find multi-hop chains breaching 45 days and identify bounce hubs.
- `find_compliant_toddler_pathway`: Discovers compliant <=45-day pathways (Clinic -> Coordinator -> Eval Hub -> Vendor) honoring Medicaid, bilingual services, and spatial travel distance.
- `run_equity_and_counterfactual_audit`: Conducts a post-output Equity Audit joining child home tracts with ACS poverty/vehicle rates and calculates child-days saved by eliminating paper faxing.
- `format_bilingual_caregiver_note`: Creates respectful, plain-language English and Spanish action notes for families.

Always provide clear, actionable summaries with exact data points, days elapsed, and specific provider names.
"""

pathway_router_agent = Agent(
    model=MODEL_NAME,
    name="pathway_router_agent",
    description="Selects optimal <=45-day bilingual/Medicaid route and flags 36-month aging-out urgency.",
    instruction=(
        "Use `find_compliant_toddler_pathway` and `trace_45day_breaches_and_bounce_hubs` "
        "to select a compliant <=45-day pathway and contrast it against regional paper-fax bounce hubs."
    ),
    tools=[find_compliant_toddler_pathway, trace_45day_breaches_and_bounce_hubs],
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
    sub_agents=[pathway_router_agent, equity_audit_agent, caregiver_note_agent],
)

root_agent = Agent(
    model=MODEL_NAME,
    name="early_intervention_triage_agent",
    description="Early Intervention Triage & Network-Audit Assistant for IDEA Part C coordinators.",
    instruction=SYSTEM_INSTRUCTION,
    tools=(
        _build_optional_bq_toolset(default_dataset_id=DATASET_ID)
        + [
            trace_45day_breaches_and_bounce_hubs,
            find_compliant_toddler_pathway,
            run_equity_and_counterfactual_audit,
            format_bilingual_caregiver_note,
            validate_pre_handoff_packet,
        ]
    ),
    sub_agents=[brief_generator_pipeline],
)
