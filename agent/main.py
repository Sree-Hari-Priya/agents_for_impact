"""
FastAPI Server for Early Intervention Triage & Network-Audit Agent.
Exposes REST endpoints for the ADK agent, graph analysis, pathway routing, and equity audits.
Includes an interactive dashboard web UI for IDEA Part C coordinators.
"""

import datetime
import json
import os
import sys
import uuid
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import root_agent
from agent.tools import (
    trace_45day_breaches_and_bounce_hubs,
    find_compliant_toddler_pathway,
    run_equity_and_counterfactual_audit,
    format_bilingual_caregiver_note,
    get_state_geospatial_graph_data,
    simulate_single_network_fix,
    validate_pre_handoff_packet,
    resolve_geographic_location_and_nearest_clinics,
    execute_multi_agent_triage_with_traces,
    fetch_recent_bq_traces,
    log_agent_trace_to_bigquery,
)
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

app = FastAPI(
    title="Early Intervention Triage & Network-Audit Assistant",
    description="BigQuery Property Graph + ADK Agent for IDEA Part C Coordinators",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_service = InMemorySessionService()
runner = Runner(agent=root_agent, session_service=session_service, app_name="a4i_early_intervention")

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "coordinator_user"
    session_id: Optional[str] = None

class TriageRequest(BaseModel):
    child_age_months: int = 22
    census_tract_geoid: Optional[str] = "36005019700"
    requires_medicaid: bool = True
    requires_bilingual: bool = True
    max_wait_days: int = 45

@app.get("/health")
def health():
    return {"status": "healthy", "service": "Early Intervention Triage Assistant"}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    user_id = req.user_id or "coordinator_user"
    if not req.session_id:
        session = await session_service.create_session(app_name="a4i_early_intervention", user_id=user_id)
        session_id = session.id
    else:
        session_id = req.session_id

    content = types.Content(role="user", parts=[types.Part.from_text(text=req.message)])
    full_response = ""
    async for event in runner.run_async(session_id=session_id, user_id=user_id, new_message=content):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    full_response += part.text

    # Trace log chat interaction to BigQuery
    try:
        log_agent_trace_to_bigquery([{
            "trace_id": str(uuid.uuid4()),
            "session_id": session_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "child_age_months": None,
            "census_tract_geoid": None,
            "requires_medicaid": None,
            "requires_bilingual": None,
            "agent_name": "milestone_navigator_agent",
            "event_type": "CHAT_INTERACTION",
            "status": "SUCCESS",
            "latency_ms": 0.0,
            "details_json": json.dumps({"user_prompt": req.message[:120], "response_preview": full_response[:120]}),
        }])
    except Exception:
        pass

    return {
        "session_id": session_id,
        "response": full_response
    }

@app.get("/api/graph/breaches")
def get_breaches(min_wait_days: int = 45, limit: int = 10, state_code: str = "NY"):
    return trace_45day_breaches_and_bounce_hubs(min_wait_days=min_wait_days, limit=limit, state_code=state_code)

class GeoResolveRequest(BaseModel):
    query: str = "10451"
    state_code: str = "NY"
    top_n: int = 3

@app.post("/api/geo/resolve")
def geo_resolve(req: GeoResolveRequest):
    return resolve_geographic_location_and_nearest_clinics(
        query=req.query,
        state_code=req.state_code,
        top_n=req.top_n
    )

@app.post("/api/triage/route")
def triage_route(req: TriageRequest):
    return execute_multi_agent_triage_with_traces(
        child_age_months=req.child_age_months,
        census_tract_geoid=req.census_tract_geoid or "36005019700",
        requires_medicaid=req.requires_medicaid,
        requires_bilingual=req.requires_bilingual,
        max_wait_days=req.max_wait_days,
        state_code="NY",
    )

@app.get("/api/traces/recent")
def get_recent_traces(limit: int = 25):
    return {
        "status": "success",
        "traces": fetch_recent_bq_traces(limit=limit)
    }

@app.get("/api/audit/equity")
def equity_audit():
    return run_equity_and_counterfactual_audit()

class PacketValidateRequest(BaseModel):
    child_age_months: int = 22
    primary_home_language: str = "Spanish"
    insurance_type: str = "Medicaid"
    target_coordinator_id: str = "SYN-PROV-NY-011"
    target_eval_hub_id: Optional[str] = "SYN-PROV-NY-019"
    screening_tool_administered: bool = True
    consent_signed: bool = True
    state_code: str = "NY"

@app.post("/api/packet/validate")
def validate_packet(req: PacketValidateRequest):
    return validate_pre_handoff_packet(
        child_age_months=req.child_age_months,
        primary_home_language=req.primary_home_language,
        insurance_type=req.insurance_type,
        target_coordinator_id=req.target_coordinator_id,
        target_eval_hub_id=req.target_eval_hub_id,
        screening_tool_administered=req.screening_tool_administered,
        consent_signed=req.consent_signed,
        state_code=req.state_code,
    )

class CaregiverNoteRequest(BaseModel):
    family_name: str = "Rivera"
    child_name: str = "Mateo"
    clinic_name: str = "Lockport Well-Child Pediatric Screening Group #01 [Synthetic]"
    coordinator_name: str = "Walton Regional Part C Intake & Service Coordination Desk #11 [Synthetic]"
    eval_hub_name: str = "Lockport Developmental-Behavioral & Speech Evaluation Center #19 [Synthetic]"
    vendor_name: str = "Malone Early Childhood Speech, Occupational & Physical Therapy Organization #28 [Synthetic]"
    estimated_total_days: int = 22

@app.post("/api/caregiver/note")
def generate_caregiver_note(req: CaregiverNoteRequest):
    return format_bilingual_caregiver_note(
        family_name=req.family_name,
        child_name=req.child_name,
        clinic_name=req.clinic_name,
        coordinator_name=req.coordinator_name,
        eval_hub_name=req.eval_hub_name,
        vendor_name=req.vendor_name,
        estimated_total_days=req.estimated_total_days,
    )

@app.get("/api/graph/map")
def get_map_graph(state_code: str = "NY"):
    return get_state_geospatial_graph_data(state_code=state_code)

@app.get("/api/network/simulate")
def simulate_network_fix(coordinator_id: Optional[str] = None, state_code: Optional[str] = "MS"):
    return simulate_single_network_fix(coordinator_id=coordinator_id, state_code=state_code)

@app.get("/", response_class=HTMLResponse)
def index():
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EarlyBridge - Early Intervention Triage & Network Audit</title>
  <!-- Google Fonts: Quicksand & Nunito (Warm Child-Saving Typography) -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <script type="text/javascript" src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      /* Warm, nurturing child-saving pastel palette */
      --pastel-sky: #f0f9ff;
      --pastel-sky-soft: #e0f2fe;
      --pastel-sky-accent: #38bdf8;
      --pastel-sky-dark: #0284c7;

      --pastel-mint: #f0fdf4;
      --pastel-mint-soft: #dcfce7;
      --pastel-mint-accent: #86efac;
      --pastel-mint-dark: #16a34a;

      --pastel-peach: #fff7ed;
      --pastel-peach-soft: #ffedd5;
      --pastel-peach-accent: #fdba74;
      --pastel-peach-dark: #ea580c;

      --pastel-rose: #fff1f2;
      --pastel-rose-soft: #ffe4e6;
      --pastel-rose-accent: #fda4af;
      --pastel-rose-dark: #e11d48;

      --pastel-lavender: #faf5ff;
      --pastel-lavender-soft: #f3e8ff;
      --pastel-lavender-accent: #d8b4fe;
      --pastel-lavender-dark: #9333ea;

      --pastel-butter: #fefce8;
      --pastel-butter-soft: #fef9c3;
      --pastel-butter-accent: #fde047;
      --pastel-butter-dark: #ca8a04;

      --primary-color: #0284c7;
      --card-radius: 1.25rem;
      --card-shadow: 0 8px 28px rgba(148, 163, 184, 0.12);
      --card-shadow-hover: 0 12px 36px rgba(148, 163, 184, 0.18);
    }
    body {
      background: linear-gradient(180deg, #fdfbf7 0%, #f0fdf4 30%, #faf5ff 65%, #f0f9ff 100%);
      font-family: 'Nunito', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #1e293b;
      min-height: 100vh;
    }
    h1, h2, h3, h4, h5, h6, .hero-title, .track-nav-btn {
      font-family: 'Quicksand', 'Nunito', sans-serif;
    }
    .hero {
      background: linear-gradient(135deg, #38bdf8 0%, #818cf8 35%, #f472b6 70%, #fb923c 100%);
      color: white;
      padding: 2.2rem 1.5rem 1.9rem;
      margin-bottom: 2rem;
      border-bottom: 5px solid rgba(254, 240, 138, 0.5);
      box-shadow: 0 10px 32px rgba(129, 140, 248, 0.25);
      position: relative;
      overflow: hidden;
    }
    .hero::before {
      content: "";
      position: absolute;
      top: -40%;
      right: -10%;
      width: 450px;
      height: 450px;
      background: radial-gradient(circle, rgba(255,255,255,0.22) 0%, transparent 70%);
      border-radius: 50%;
      pointer-events: none;
    }
    .hero::after {
      content: "";
      position: absolute;
      bottom: -30%;
      left: -5%;
      width: 350px;
      height: 350px;
      background: radial-gradient(circle, rgba(254,249,195,0.25) 0%, transparent 70%);
      border-radius: 50%;
      pointer-events: none;
    }
    .card {
      border-radius: var(--card-radius);
      border: 1px solid rgba(226, 232, 240, 0.85);
      box-shadow: var(--card-shadow);
      margin-bottom: 1.5rem;
      background: #ffffff;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .card:hover {
      box-shadow: var(--card-shadow-hover);
      transform: translateY(-2px);
    }
    .stat-badge {
      font-size: 1.7rem;
      font-weight: 800;
      letter-spacing: -0.5px;
    }
    .badge-breach { 
      background-color: #fb7185; 
      color: #881337; 
      border: 1px solid #fda4af;
      box-shadow: 0 2px 8px rgba(251, 113, 133, 0.25);
    }
    .badge-pass { 
      background-color: #86efac; 
      color: #14532d; 
      border: 1px solid #bbf7d0;
      box-shadow: 0 2px 8px rgba(134, 239, 172, 0.25);
    }
    .chat-box {
      height: 420px;
      overflow-y: auto;
      background: #fdfbf7;
      border: 1px solid #fed7aa;
      border-radius: 1.15rem;
      padding: 1.2rem;
    }
    .msg-user {
      background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%);
      color: #0369a1;
      border: 1px solid #7dd3fc;
      border-radius: 1.25rem 1.25rem 0.35rem 1.25rem;
      padding: 0.85rem 1.2rem;
      margin-bottom: 0.85rem;
      max-width: 82%;
      margin-left: auto;
      box-shadow: 0 4px 14px rgba(56, 189, 248, 0.18);
      font-weight: 600;
    }
    .msg-agent {
      background: #ffffff;
      color: #0f172a;
      border: 1px solid #e9d5ff;
      border-left: 5px solid #c084fc;
      border-radius: 1.25rem 1.25rem 1.25rem 0.35rem;
      padding: 0.95rem 1.25rem;
      margin-bottom: 0.85rem;
      max-width: 88%;
      white-space: pre-wrap;
      box-shadow: 0 4px 16px rgba(192, 132, 252, 0.1);
      line-height: 1.6;
    }
    .track-nav-btn {
      border-radius: 2rem !important;
      padding: 0.65rem 1.3rem;
      font-weight: 700;
      font-size: 0.92rem;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      border: 1px solid rgba(255, 255, 255, 0.45);
      background: rgba(255, 255, 255, 0.18);
      color: #ffffff;
      backdrop-filter: blur(6px);
    }
    .track-nav-btn:hover {
      background: rgba(255, 255, 255, 0.32);
      color: #ffffff;
      transform: translateY(-2px);
    }
    .track-nav-btn.active {
      background: #ffffff !important;
      color: #0284c7 !important;
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
      transform: translateY(-2px);
      border-color: #ffffff !important;
    }
    .track-pane {
      display: none;
      animation: fadeIn 0.25s ease-in-out;
    }
    .track-pane.active {
      display: block;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .kpi-card {
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      border-radius: 1.25rem;
    }
    .kpi-card:hover {
      transform: translateY(-4px);
    }
    .kpi-card-breach {
      background: linear-gradient(145deg, #fff1f2 0%, #ffffff 100%);
      border: 1px solid #fecdd3;
      box-shadow: 0 4px 16px rgba(244, 63, 94, 0.08);
    }
    .kpi-card-bounce {
      background: linear-gradient(145deg, #fff7ed 0%, #ffffff 100%);
      border: 1px solid #fed7aa;
      box-shadow: 0 4px 16px rgba(249, 115, 22, 0.08);
    }
    .kpi-card-saved {
      background: linear-gradient(145deg, #f0fdf4 0%, #ffffff 100%);
      border: 1px solid #bbf7d0;
      box-shadow: 0 4px 16px rgba(34, 197, 94, 0.08);
    }
    .kpi-card-pathway {
      background: linear-gradient(145deg, #f0f9ff 0%, #ffffff 100%);
      border: 1px solid #bae6fd;
      box-shadow: 0 4px 16px rgba(2, 132, 199, 0.08);
    }
    .table-custom th {
      background: #f8fafc;
      color: #475569;
      font-weight: 700;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border: none;
    }
    .form-control, .form-select {
      border-radius: 0.85rem;
      border-color: #cbd5e1;
      padding: 0.6rem 0.95rem;
      transition: all 0.2s ease;
    }
    .form-control:focus, .form-select:focus {
      border-color: #38bdf8;
      box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.22);
    }
    .btn-primary {
      background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%);
      border-color: #0284c7;
      border-radius: 0.85rem;
      box-shadow: 0 4px 14px rgba(2, 132, 199, 0.22);
      font-weight: 700;
      transition: all 0.2s ease;
    }
    .btn-primary:hover {
      background: linear-gradient(135deg, #0369a1 0%, #0284c7 100%);
      border-color: #0369a1;
      transform: translateY(-2px);
      box-shadow: 0 6px 18px rgba(2, 132, 199, 0.3);
    }
    .child-safety-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      background: rgba(254, 240, 138, 0.35);
      color: #854d0e;
      padding: 0.35rem 0.85rem;
      border-radius: 2rem;
      font-weight: 700;
      font-size: 0.82rem;
      border: 1px solid rgba(254, 240, 138, 0.6);
    }
    .pastel-pill-chip {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 2rem;
      padding: 0.32rem 0.85rem;
      font-size: 0.78rem;
      font-weight: 700;
      color: #334155;
      cursor: pointer;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      box-shadow: 0 2px 6px rgba(148, 163, 184, 0.1);
      text-decoration: none;
    }
    .pastel-pill-chip:hover {
      background: #f0fdf4;
      border-color: #86efac;
      color: #15803d;
      transform: translateY(-1px);
      box-shadow: 0 4px 10px rgba(34, 197, 94, 0.15);
    }
    .pastel-pill-chip:active,
    .pastel-pill-chip.active {
      background: #0284c7 !important;
      border-color: #0284c7 !important;
      color: #ffffff !important;
      box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35) !important;
      transform: translateY(0);
    }
  </style>
</head>
<body>
  <div class="hero">
    <div class="container">
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-3">
        <div class="d-flex align-items-center gap-3">
          <img
            src="https://images.unsplash.com/photo-1596464716127-f2a82984de30?auto=format&fit=crop&w=240&q=80"
            alt="Toddler stacking wooden milestone blocks (Illustrative Only — Zero Real Patient PII)"
            style="width: 82px; height: 82px; object-fit: cover; border-radius: 50%; border: 3.5px solid #fef9c3; box-shadow: 0 6px 20px rgba(0,0,0,0.2);"
          />
          <div>
            <div class="d-flex align-items-center gap-2 mb-1 flex-wrap">
              <span class="badge rounded-pill px-3 py-1 fw-bold shadow-xs" style="background:#fef9c3; color:#854d0e; border: 1px solid #fef08a;"><i class="fa-solid fa-shapes me-1 text-warning"></i>Saving Children's Milestones</span>
              <span class="badge rounded-pill px-3 py-1 fw-bold shadow-xs" style="background:rgba(255,255,255,0.25); color:#ffffff; border: 1px solid rgba(255,255,255,0.45); backdrop-filter: blur(4px);"><i class="fa-solid fa-shield-heart me-1 text-danger"></i>IDEA Part C 45-Day Statutory Protection</span>
              <span class="badge rounded-pill px-3 py-1 fw-bold shadow-xs" style="background:#dcfce7; color:#14532d; border: 1px solid #bbf7d0;"><i class="fa-solid fa-baby me-1 text-success"></i>Zero Lost Referrals</span>
            </div>
            <h1 class="h2 mb-1 fw-bold text-white" style="letter-spacing:-0.5px; text-shadow: 0 2px 8px rgba(0,0,0,0.15);">EarlyBridge: Triage &amp; Network-Audit</h1>
            <p class="mb-0 text-white-50 small" style="font-weight: 500;">Every infant and toddler deserves developmental evaluation within 45 days · BigQuery ISO GQL Graph · Vertex AI Gemini</p>
          </div>
        </div>
        <div class="text-end">
          <div class="d-inline-flex align-items-center gap-2 px-3 py-1 rounded-pill fw-bold small shadow-sm" style="background:#fef9c3; color:#713f12; border: 1px solid #fef08a;">
            <i class="fa-solid fa-location-dot text-danger"></i> Active State: New York (NY · FIPS 36)
          </div>
          <div class="small mt-1 text-white-50">89 Census Tracts · 30 CareNodes · 100% [Synthetic] Network</div>
        </div>
      </div>

      <!-- Functional Track Navigation Switcher -->
      <div class="mt-4 pt-3 border-top border-white border-opacity-25 d-flex flex-wrap justify-content-between align-items-center gap-3">
        <div class="d-flex align-items-center gap-2">
          <span class="small text-uppercase fw-bold text-white-50 me-2"><i class="fa-solid fa-child me-1"></i> Care Navigator:</span>
          <div class="btn-group" role="group" aria-label="Track Navigation">
            <button id="btnTrack1" type="button" class="btn btn-sm btn-light track-nav-btn active" onclick="activateTrack(1)">
              <i class="fa-solid fa-hands-holding-child me-1 text-primary"></i> Track 1: Today's Referral
            </button>
            <button id="btnTrack4" type="button" class="btn btn-sm btn-outline-light track-nav-btn fw-semibold" onclick="activateTrack(4)">
              🌱 Extra Credit: Simulator
            </button>
            <button id="btnTrack5" type="button" class="btn btn-sm btn-outline-light track-nav-btn" onclick="activateTrack(5)">
              <i class="fa-solid fa-list-check me-1"></i> 📡 Execution Traces &amp; Audit
            </button>
            <button id="btnTrack2" type="button" class="d-none" onclick="activateTrack(2)"></button>
            <button id="btnTrack3" type="button" class="d-none" onclick="activateTrack(3)"></button>
          </div>
        </div>
        <div id="trackBannerInfo" class="small text-white px-3 py-1 rounded-pill" style="background: rgba(255,255,255,0.2); backdrop-filter: blur(6px); border: 1px solid rgba(255,255,255,0.35);">
          <strong>Track 1:</strong> Route today's toddler referral (&le;45d compliant path with 36m age cliff guard).
        </div>
      </div>
    </div>
  </div>

  <div class="container pb-5">
    <!-- ========================================== -->
    <!-- TRACK 1 PANE: TODAY'S REFERRAL (TRIAGE & CHAT) -->
    <!-- ========================================== -->
    <div id="trackPane1" class="track-pane active">
      <div class="row g-4">
        <!-- Quick Triage Routing Panel -->
        <div class="col-lg-5">
          <div class="card p-4 h-100" style="background: linear-gradient(180deg, #fdfbf7 0%, #ffffff 100%); border-radius: 1.25rem;">
            <div class="d-flex align-items-center justify-content-between mb-2">
              <h5 class="card-title mb-0 fw-bold" id="triageCardTitle"><i class="fa-solid fa-compass text-primary me-2"></i>Today's Referral Navigator</h5>
              <div class="d-flex align-items-center gap-2">
                <div class="btn-group btn-group-sm" role="group" aria-label="Input Language Toggle">
                  <button type="button" id="btnLangEn" class="btn btn-xs btn-primary active py-0 px-2 fw-semibold" style="font-size:0.75rem; border-radius: 1rem 0 0 1rem;" onclick="setInterfaceLanguage('en')">🇺🇸 EN</button>
                  <button type="button" id="btnLangEs" class="btn btn-xs btn-outline-primary py-0 px-2 fw-semibold" style="font-size:0.75rem; border-radius: 0 1rem 1rem 0;" onclick="setInterfaceLanguage('es')">🇪🇸 ES</button>
                </div>
                <span class="badge bg-primary-subtle text-primary border border-primary-subtle rounded-pill px-2 py-1" id="triageStatutoryClockBadge">Statutory Clock: 45 Days</span>
              </div>
            </div>
            <p class="text-muted small mb-3" id="triageDescriptionText">
              Enter the child's natural geographic location (ZIP Code, City, or Census Tract GEOID) to resolve nearest screening centers and calculate a guaranteed &le;45d IDEA Part C pathway.
            </p>

            <!-- Natural Geographic Input -->
            <div class="mb-3 p-3 rounded-4 border" style="background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%); border-color: #e2e8f0 !important;">
              <label class="form-label small fw-bold mb-1 d-flex justify-content-between">
                <span id="geoInputLabel"><i class="fa-solid fa-map-location-dot text-danger me-1"></i>Location (ZIP, City, or Census GEOID)</span>
                <span id="geoMatchBadge" class="badge rounded-pill" style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-size:0.7rem;">Auto-Resolving</span>
              </label>
              <div class="input-group input-group-sm mb-2">
                <input type="text" id="geoInput" class="form-control" value="10451" placeholder="e.g. 10451, Bronx, Jamestown, Lockport, or 36005019700" oninput="debounceGeoResolve()" onchange="resolveLocationNow()" onkeydown="if(event.key==='Enter'){event.preventDefault();resolveLocationNow();}">
                <button class="btn btn-outline-primary" type="button" onclick="resolveLocationNow()">
                  <i class="fa-solid fa-magnifying-glass-location"></i>
                </button>
              </div>
              <div class="d-flex flex-wrap gap-1 mt-1 mb-1" style="font-size: 0.72rem;">
                <span class="text-muted me-1 align-self-center" id="quickSelectLabel">Quick Select:</span>
                <button type="button" class="pastel-pill-chip quick-select-btn active" data-zip="10451" onclick="setGeoLocation('10451')">10451 (Bronx)</button>
                <button type="button" class="pastel-pill-chip quick-select-btn" data-zip="10025" onclick="setGeoLocation('10025')">10025 (Manhattan)</button>
                <button type="button" class="pastel-pill-chip quick-select-btn" data-zip="14094" onclick="setGeoLocation('14094')">14094 (Lockport)</button>
                <button type="button" class="pastel-pill-chip quick-select-btn" data-zip="13617" onclick="setGeoLocation('13617')">13617 (Canton)</button>
                <button type="button" class="pastel-pill-chip quick-select-btn" data-zip="14701" onclick="setGeoLocation('14701')">14701 (Jamestown)</button>
                <button type="button" class="pastel-pill-chip quick-select-btn" data-zip="13856" onclick="setGeoLocation('13856')">13856 (Walton)</button>
                <button type="button" class="pastel-pill-chip quick-select-btn" data-zip="90210" style="color:#be123c; border-color:#fecdd3; background:#fff1f2;" onclick="setGeoLocation('90210')">90210 (Test OOS)</button>
              </div>
              <div class="mt-2">
                <label class="form-label small fw-semibold mb-1" style="font-size:0.75rem;" id="tractGeoidLabel">Census Tract GEOID</label>
                <input type="text" id="tractGeoid" class="form-control form-control-sm" value="36005019700" placeholder="e.g. 36005019700" onchange="runTriage()">
              </div>
              <div id="geoResolvedText" class="small text-primary fw-semibold mt-1" style="font-size:0.78rem;">
                📍 Resolved: ZIP 10451 — Bronx (Mott Haven) · Tract 36005019700
              </div>
            </div>

            <!-- Dynamic Closest Screening Centers Preview -->
            <div id="closestClinicsCard" class="card p-3 mb-3 border shadow-xs" style="font-size:0.78rem; background: linear-gradient(145deg, #f0f9ff 0%, #ffffff 100%); border-color: #bae6fd !important; border-radius: 1rem;">
              <div class="fw-bold text-dark mb-1 d-flex justify-content-between align-items-center">
                <span id="closestClinicsTitle">🏥 Nearest Screening Centers</span>
                <span class="badge rounded-pill" style="background:#e0f2fe; color:#0369a1; font-size:0.7rem;" id="closestClinicsSubtitle">Live Spatial Radius</span>
              </div>
              <div id="closestClinicsList">
                <div class="text-muted small">Resolving nearby pediatric screening centers...</div>
              </div>
            </div>

            <div class="row g-2 mb-3">
              <div class="col-12">
                <label class="form-label small fw-semibold mb-1" id="childAgeLabel">Child Age (Months)</label>
                <input type="number" id="childAge" class="form-control" value="22" min="1" max="48" onchange="runTriage()">
                <span class="text-muted" style="font-size:0.72rem;" id="childAgeHelp">Part C Cliff: 36 Months (Urgent alert triggers at 30+ months)</span>
              </div>
            </div>

            <div class="p-3 rounded-4 mb-3 border" style="background: linear-gradient(180deg, #faf5ff 0%, #ffffff 100%); border-color: #e9d5ff !important;">
              <div class="form-check form-switch mb-2">
                <input class="form-check-input" type="checkbox" id="reqMedicaid" checked onchange="runTriage()">
                <label class="form-check-label small fw-semibold" for="reqMedicaid" id="reqMedicaidLabel">Requires Medicaid Acceptance</label>
              </div>
              <div class="form-check form-switch mb-1">
                <input class="form-check-input" type="checkbox" id="reqBilingual" checked onchange="handleBilingualToggle()">
                <label class="form-check-label small fw-semibold" for="reqBilingual" id="reqBilingualLabel">Requires Bilingual Evaluator (Spanish)</label>
              </div>
              <div id="routingCriteriaNotice" class="mt-2 pt-2 border-top small" style="font-size: 0.76rem;">
                <span class="badge rounded-pill" style="background:#7c3aed; color:#fff;" id="bilingualBadge"><i class="fa-solid fa-language me-1"></i>Bilingual Spanish Mandate Active</span>
                <span class="text-muted d-block mt-1" id="bilingualNoticeText">Locks pathway to verified bilingual evaluation hubs (Lockport NY-019). Toggle off to allow standard English/monolingual hubs.</span>
              </div>
            </div>

            <button class="btn btn-primary w-100 fw-bold py-2 mb-3 shadow-sm" id="btnCalculatePathway" onclick="runTriage()" style="background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%); border: none; border-radius: 0.85rem;">
              <i class="fa-solid fa-route me-1"></i> Calculate Compliant Pathway (&le; 45d)
            </button>

            <!-- Triage Result Container -->
            <div id="triageResult" class="small text-muted border rounded-4 p-3 bg-white" style="min-height: 120px; box-shadow: inset 0 2px 6px rgba(0,0,0,0.02); border-color: #e2e8f0 !important;">
              <div class="text-center py-3 text-secondary">
                <i class="fa-regular fa-circle-question fa-2x mb-2 text-muted"></i>
                <div id="triageResultPrompt">Click above or toggle any switch to calculate optimal graph routing.</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Geographic Map & ReferralGraph Visualization Panel for Track 1 -->
        <div class="col-lg-7 d-flex flex-column gap-3">
          <!-- Physical Map of New York (NY) — GIS Provider Network -->
          <div class="card p-3 border shadow-sm" style="background: #ffffff; border-radius: 1.25rem;">
            <div class="d-flex flex-wrap justify-content-between align-items-center mb-2 gap-2">
              <div>
                <h6 id="mapCardTitle" class="card-title mb-0 fw-bold d-flex align-items-center text-dark" style="font-size:0.95rem;">
                  <i class="fa-solid fa-earth-americas text-primary me-2"></i>Physical Map of New York (NY) — GIS Provider Network
                  <span class="badge rounded-pill ms-2" style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-size:0.75rem;">Live Referral Overlay</span>
                </h6>
                <small class="text-muted" style="font-size:0.75rem;">30 CareNode providers &amp; 89 NY Census tracts (USGS National Map · 100% Public Domain US Gov)</small>
              </div>
              <div class="d-flex flex-wrap gap-1">
                <div class="btn-group btn-group-sm" role="group">
                  <button type="button" class="btn btn-xs btn-outline-primary active py-1 px-2" id="btnZoomState" onclick="zoomMapRegion('state', this)">🗺️ State</button>
                  <button type="button" class="btn btn-xs btn-outline-primary py-1 px-2" id="btnZoomBronx" onclick="zoomMapRegion('bronx', this)">🏙️ Bronx</button>
                  <button type="button" class="btn btn-xs btn-outline-primary py-1 px-2" id="btnZoomCatskills" onclick="zoomMapRegion('catskills', this)">⛰️ Upstate</button>
                  <button type="button" class="btn btn-xs btn-outline-secondary py-1 px-2" id="btnToggleTracts" onclick="toggleTractLayer(this)">📍 89 Tracts</button>
                </div>
              </div>
            </div>
            <div id="nyPhysicalMap" style="height: 360px; width: 100%; border-radius: 0.85rem; border: 1px solid #cbd5e1;"></div>
            <div class="d-flex flex-wrap justify-content-between align-items-center mt-2 small text-muted" style="font-size:0.75rem;">
              <div>
                <span class="badge" style="background:#38bdf8; color:#0f172a;">●</span> Clinic (8)
                <span class="badge ms-1" style="background:#f59e0b; color:#0f172a;">●</span> Coordinator (4)
                <span class="badge ms-1" style="background:#a855f7; color:#fff;">●</span> Eval Hub (8)
                <span class="badge ms-1" style="background:#10b981; color:#0f172a;">●</span> Therapy (10)
                <span class="badge ms-1" style="background:#f43f5e; color:#fff;">○</span> High Zero-Vehicle
              </div>
              <div class="font-monospace">
                <span style="color:#ef4444; font-weight:bold;">━━ Fax Bounce (70d)</span> &nbsp;|&nbsp;
                <span style="color:#22c55e; font-weight:bold;">━━ &le;45d Route (40d / 22d)</span>
              </div>
            </div>
          </div>

          <!-- Graph Viz Card: ReferralGraph Side-by-Side Pathway & 45-Day Statutory Clock -->
          <div class="card p-3 border shadow-sm" style="background: #ffffff; border-radius: 1.25rem;">
            <div class="d-flex flex-wrap justify-content-between align-items-center mb-2 gap-2">
              <div>
                <h6 id="graphCardTitle" class="card-title mb-0 fw-bold d-flex align-items-center text-dark" style="font-size:0.95rem;">
                  <i class="fa-solid fa-clock-rotate-left text-danger me-2"></i>ReferralGraph Side-by-Side Pathway &amp; 45-Day Statutory Clock
                </h6>
                <small id="graphCardSubtitle" class="text-muted" style="font-size:0.75rem;">
                  Comparing multi-hop paper-fax bounce loops vs. electronic e-referral routes from the regional coordinator desk.
                </small>
              </div>
              <div class="btn-group btn-group-sm" role="group">
                <button id="btn-mode-both" type="button" class="btn btn-xs btn-primary active py-1 px-2 fw-semibold" onclick="setSvgGraphMode('both')">Compare Bounce vs. &le;45d</button>
                <button id="btn-mode-bounce" type="button" class="btn btn-xs btn-outline-danger py-1 px-2 fw-semibold" onclick="setSvgGraphMode('bounce')">🚨 4-Hop Bounce</button>
                <button id="btn-mode-eval" type="button" class="btn btn-xs btn-outline-success py-1 px-2 fw-semibold" onclick="setSvgGraphMode('eval')">✅ 3-Hop E-Referral</button>
                <button id="btn-mode-fast" type="button" class="btn btn-xs btn-outline-info py-1 px-2 fw-semibold" onclick="setSvgGraphMode('fast')">⚡ 2-Hop Fast-Track</button>
              </div>
            </div>

            <div class="p-2 rounded-3 border mb-2" style="background-color: #0f172a; color: #f8fafc; box-shadow: inset 0 2px 6px rgba(0,0,0,0.4);">
              <svg id="svgReferralGraph" viewBox="0 0 760 235" style="width:100%; height:auto; display:block;"></svg>
            </div>
            <div id="svgClockCards" class="row g-2 mb-0"></div>
          </div>
        </div>
      </div>

      <!-- Live ADK Agent Interaction (Milestone Navigator) -->
      <div class="row mt-4">
        <div class="col-12">
          <div class="card p-4 border shadow-sm" style="background: linear-gradient(180deg, #fdfbf7 0%, #ffffff 100%); border-radius: 1.25rem;">
            <div class="d-flex align-items-center justify-content-between mb-3">
              <div>
                <h5 class="card-title mb-0 fw-bold"><i class="fa-solid fa-heart-pulse text-danger me-2"></i>Milestone Navigator</h5>
                <small class="text-muted" id="navigatorSubtitle">AI Casework Partner · Google ADK Multi-Agent System · BigQuery Property Graph</small>
              </div>
              <span class="badge bg-success-subtle text-success border border-success-subtle rounded-pill px-3 py-1" id="navigatorStatusBadge"><i class="fa-solid fa-circle text-success me-1" style="font-size: 7px;"></i>Navigator Online</span>
            </div>
            <div id="chatBox" class="chat-box mb-3">
              <div class="msg-agent" id="chatWelcomeMsg">👋 <strong>Hello Coordinator! I am Maya, your EarlyBridge Milestone Navigator.</strong>

I partner with you to ensure every infant and toddler reaches their developmental evaluation well within the federal 45-day statutory IFSP clock.

<strong>How can I assist today's casework?</strong>
• <strong>Natural Location Triage:</strong> <em>"Route a 22-month-old Spanish-speaking Medicaid toddler living in ZIP 10451."</em>
• <strong>Age Cliff Escalation:</strong> <em>"We just received a 32-month-old referral in Canton. What is the emergency fast-track sequence before they age out at 36 months?"</em>
• <strong>Caregiver Action Notes:</strong> <em>"Draft bilingual English and Spanish family action notes for the Rivera family and toddler Mateo."</em>
• <strong>Pre-Handoff Quality Audit:</strong> <em>"Check if referral packet for 22m Spanish toddler to coordinator SYN-PROV-NY-011 will bounce."</em>
• <strong>Transit Check:</strong> <em>"Does Bronx tract 36005019700 trigger the zero-vehicle transit guardrail?"</em></div>
            </div>

            <!-- Bilingual Quick Prompt Suggestions for Caseworkers -->
            <div class="d-flex flex-wrap gap-1 mb-2" id="chatQuickPrompts" style="font-size: 0.72rem;">
              <span class="text-muted small align-self-center me-1" id="chatPromptsLabel"><i class="fa-solid fa-bolt text-warning me-1"></i>Casework Prompts:</span>
              <button type="button" class="btn btn-xs py-1 px-2 rounded-pill fw-bold shadow-xs" style="background: #f0fdf4; border: 1px solid #86efac; color: #166534;" onclick="insertPrompt('Ruta para un niño de 22 meses que habla español con Medicaid en el código postal 10451')">🇪🇸 Ruta 22m Español (10451)</button>
              <button type="button" class="btn btn-xs py-1 px-2 rounded-pill fw-bold shadow-xs" style="background: #eff6ff; border: 1px solid #93c5fd; color: #1e40af;" onclick="insertPrompt('Redactar nota bilingüe en inglés y español para la familia Rivera y el niño Mateo')">🇪🇸 Nota Bilingüe Familia</button>
              <button type="button" class="btn btn-xs py-1 px-2 rounded-pill fw-bold shadow-xs" style="background: #faf5ff; border: 1px solid #d8b4fe; color: #6b21a8;" onclick="insertPrompt('Route a 22-month-old Spanish-speaking Medicaid toddler living in ZIP 10451.')">🇺🇸 Route 22m Medicaid</button>
              <button type="button" class="btn btn-xs py-1 px-2 rounded-pill fw-bold shadow-xs" style="background: #fff7ed; border: 1px solid #fdba74; color: #9a3412;" onclick="insertPrompt('What is the emergency fast-track sequence for a 32-month-old in Canton before they age out at 36 months?')">🇺🇸 32m Fast-Track</button>
            </div>

            <div class="input-group">
              <input type="text" id="userInput" class="form-control py-2" placeholder="Ask Maya (e.g. Find a pathway for a 20-month-old in ZIP 10451 on Medicaid)..." onkeydown="if(event.key==='Enter') sendMessage()" style="border-radius: 0.85rem 0 0 0.85rem;">
              <button class="btn btn-primary px-4 fw-bold" id="btnSendMessage" onclick="sendMessage()" style="border-radius: 0 0.85rem 0.85rem 0;"><i class="fa-solid fa-paper-plane me-1"></i> Send</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

    <!-- ========================================== -->
    <!-- EXTRA CREDIT: SINGLE NETWORK FIX SIMULATOR -->
    <!-- ========================================== -->
    <div id="trackPane4" class="track-pane row mt-2">
      <div class="col-12">
        <div class="card p-4 shadow-sm" style="border: 1px solid #bae6fd; border-radius: 1.25rem; background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%);">
          <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
            <div>
              <span class="badge rounded-pill mb-1 fw-bold" style="background:#fef9c3; color:#854d0e; border:1px solid #fef08a;"><i class="fa-solid fa-award me-1 text-warning"></i>Extra Credit: Challenge Requirement</span>
              <h5 class="card-title mb-1 fw-bold text-dark"><i class="fa-solid fa-seedling text-success me-2"></i>Extra Credit Simulator: Single Network Fix (Paper Fax &rarr; Electronic EHR Intake + Bilingual Pre-Check)</h5>
              <p class="text-muted small mb-0">
                Compute exactly how many breached toddler referral cases drop under the 45-day statutory limit when a regional Part C coordinator switches to electronic intake with pre-checked bilingual evaluator slots.
              </p>
            </div>
            <div class="d-flex align-items-center gap-2">
              <select id="simCoordSelect" class="form-select form-select-sm" style="width: auto; border-radius: 0.75rem;">
                <option value="SYN-PROV-NY-011" selected>Walton Regional Desk (SYN-PROV-NY-011)</option>
                <option value="SYN-PROV-NY-012">Bronx Regional Desk (SYN-PROV-NY-012)</option>
                <option value="SYN-PROV-NY-009">Canton Regional Desk (SYN-PROV-NY-009)</option>
                <option value="SYN-PROV-NY-010">Malone Regional Desk (SYN-PROV-NY-010)</option>
              </select>
              <button class="btn btn-primary btn-sm fw-bold px-3" onclick="runNetworkSimulation()" style="background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%); border: none; border-radius: 0.75rem;">Run Graph Simulation</button>
            </div>
          </div>

          <div id="simResultsArea" class="p-3 rounded-4 border" style="background:#fefce8; border-color:#fef08a !important;">
            <!-- Executive Summary Alert Banner -->
            <div class="alert d-flex align-items-center mb-3 p-3 rounded-4" style="background:linear-gradient(135deg, #dcfce7 0%, #ecfdf5 100%); border:1px solid #86efac; color:#14532d;">
              <div class="fs-2 me-3">🌱</div>
              <div>
                <h6 class="alert-heading mb-1 fw-bold"><i class="fa-solid fa-shield-heart me-1 text-success"></i>Network Fix Simulation Summary: Walton Regional Intake Desk (SYN-PROV-NY-011)</h6>
                <div id="simExecutiveSummary" class="small mb-0">
                  Switching <strong>Walton Regional Part C Intake Desk (SYN-PROV-NY-011)</strong> from <code>paper_fax</code> to <strong>electronic EHR intake</strong> with <strong>pre-checked bilingual evaluator slots</strong> rescues <strong>6 of 7 breached referral chains (85.7%)</strong> directly under the 45-day federal IFSP statutory limit. Average referral latency drops from <strong>74.3 days down to 36.3 days</strong>, slashing <strong>246 delayed child-days</strong> and decreasing statewide breaches by <strong>23.1% (from 26 down to 20)</strong>.
                </div>
              </div>
            </div>

            <div class="row g-3 text-center mb-3">
              <div class="col-md-3">
                <div class="p-3 bg-white shadow-xs" style="border: 1px solid #fecdd3; border-top: 4px solid #fb7185 !important; border-radius: 1rem;">
                  <div class="text-muted small text-uppercase fw-semibold">Coordinator Breaches</div>
                  <div id="simStatOrig" class="fw-bold text-danger fs-4 mt-1">7 Cases (&gt;45d)</div>
                  <div class="small text-muted">Baseline Fax Latency ~74.3d</div>
                </div>
              </div>
              <div class="col-md-3">
                <div class="p-3 bg-white shadow-xs" style="border: 1px solid #bbf7d0; border-top: 4px solid #10b981 !important; border-radius: 1rem;">
                  <div class="text-muted small text-uppercase fw-semibold">Cases Dropped &le;45d</div>
                  <div id="simStatRescued" class="fw-bold text-success fs-4 mt-1">6 Rescued (&le;45d)</div>
                  <div class="small text-success fw-bold">85.7% Hub Recovery Rate</div>
                </div>
              </div>
              <div class="col-md-3">
                <div class="p-3 bg-white shadow-xs" style="border: 1px solid #bae6fd; border-top: 4px solid #0284c7 !important; border-radius: 1rem;">
                  <div class="text-muted small text-uppercase fw-semibold">Statewide Impact</div>
                  <div id="simStatState" class="fw-bold text-primary fs-4 mt-1">26 &rarr; 20 (-23.1%)</div>
                  <div class="small text-muted">Across 44 Multi-Hop Chains</div>
                </div>
              </div>
              <div class="col-md-3">
                <div class="p-3 bg-white shadow-xs" style="border: 1px solid #bbf7d0; border-top: 4px solid #059669 !important; border-radius: 1rem;">
                  <div class="text-muted small text-uppercase fw-semibold">Delayed Child-Days Saved</div>
                  <div id="simStatDays" class="fw-bold text-success fs-4 mt-1">246 Child-Days</div>
                  <div class="small text-muted">Slashing Wait from 74.3d to 36.3d</div>
                </div>
              </div>
            </div>

            <!-- Mechanism Explanation -->
            <div class="card p-3 mb-3 border-0 bg-white shadow-sm" style="border-radius: 1rem;">
              <h6 class="fw-bold mb-2 text-dark">🔍 Counterfactual Mechanism: How One Fix Solves Breaches</h6>
              <div class="small text-muted">
                <ol class="mb-0 ps-3">
                  <li><strong>Hop 1 Channel Upgrade:</strong> Upgrades the initial clinic handoff from slow paper fax (14 days) to direct EHR push (~6-7 days), reclaiming a week upfront.</li>
                  <li><strong>Bilingual Pre-Check Elimination:</strong> The coordinator no longer bounces the referral into a monolingual evaluation center (which triggered an extra 31–38 day handoff loop). The child is routed directly to a verified bilingual evaluator.</li>
                  <li><strong>36-Month Cliff Protection:</strong> Prevents older toddlers (28–32 months) from irreversibly aging out of Part C coverage during administrative ping-pong handoffs.</li>
                </ol>
              </div>
            </div>

            <!-- Hub Comparison Table -->
            <h6 class="fw-bold mb-2">📋 Comparative Simulation Across Regional Intake Coordinators</h6>
            <div class="table-responsive">
              <table class="table table-sm table-hover align-middle mb-2 bg-white">
                <thead class="table-light">
                  <tr>
                    <th>Coordinator Desk</th>
                    <th>Breached Chains</th>
                    <th>Rescued (&le;45d)</th>
                    <th>Residual Breaches</th>
                    <th>Child-Days Saved</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody id="simRankingTbody">
                  <tr class="table-primary">
                    <td><strong>Walton Regional Part C Intake Desk (SYN-PROV-NY-011)</strong></td>
                    <td><span class="badge bg-danger">7 cases</span></td>
                    <td><span class="badge bg-success">6 cases dropped &le;45d</span></td>
                    <td>1 residual case</td>
                    <td><span class="text-success fw-bold">246 days</span></td>
                    <td><span class="badge bg-primary">Active Target</span></td>
                  </tr>
                  <tr>
                    <td><strong>Bronx Regional Part C Intake Desk (SYN-PROV-NY-012)</strong></td>
                    <td><span class="badge bg-danger">7 cases</span></td>
                    <td><span class="badge bg-success">6 cases dropped &le;45d</span></td>
                    <td>1 residual case</td>
                    <td><span class="text-success fw-bold">246 days</span></td>
                    <td><button class="btn btn-xs btn-outline-secondary py-0 px-2 small" onclick="simulateHub('SYN-PROV-NY-012')">Simulate</button></td>
                  </tr>
                  <tr>
                    <td><strong>Canton Regional Part C Intake Desk (SYN-PROV-NY-009)</strong></td>
                    <td><span class="badge bg-danger">6 cases</span></td>
                    <td><span class="badge bg-success">6 cases dropped &le;45d</span></td>
                    <td>0 residual cases</td>
                    <td><span class="text-success fw-bold">208 days</span></td>
                    <td><button class="btn btn-xs btn-outline-secondary py-0 px-2 small" onclick="simulateHub('SYN-PROV-NY-009')">Simulate</button></td>
                  </tr>
                  <tr>
                    <td><strong>Malone Regional Part C Intake Desk (SYN-PROV-NY-010)</strong></td>
                    <td><span class="badge bg-danger">6 cases</span></td>
                    <td><span class="badge bg-success">5 cases dropped &le;45d</span></td>
                    <td>1 residual case</td>
                    <td><span class="text-success fw-bold">208 days</span></td>
                    <td><button class="btn btn-xs btn-outline-secondary py-0 px-2 small" onclick="simulateHub('SYN-PROV-NY-010')">Simulate</button></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div id="simSummaryText" class="small text-muted mt-2">
              <strong>Outcome:</strong> Switching coordinator Walton Regional Part C Intake &amp; Service Coordination Desk #11 (SYN-PROV-NY-011) to electronic intake with pre-checked bilingual slots immediately rescues 6 of its 7 breached chains under the 45-day federal IFSP statutory limit, saving 246 total delayed child-days.
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ========================================== -->
    <!-- TRACK 2 PANE: THIS QUARTER'S AUDIT (HIDDEN) -->
    <!-- ========================================== -->
    <div id="trackPane2" class="track-pane" style="display: none !important;">
      <!-- Track 2 Header Banner & Diagnosis -->
      <div class="row mb-4">
        <div class="col-12">
          <div class="card p-4 border shadow-sm" style="background: linear-gradient(180deg, #fdfbf7 0%, #ffffff 100%); border-radius: 1.25rem;">
            <div class="d-flex flex-wrap justify-content-between align-items-center mb-2 gap-2">
              <div>
                <h5 class="card-title mb-1 fw-bold text-dark d-flex align-items-center">
                  <i class="fa-solid fa-network-wired text-primary me-2"></i>Quarterly Systemic Audit: Variable-Length GQL Analysis
                  <span class="badge rounded-pill ms-2" style="background:#fee2e2; color:#991b1b; border:1px solid #fecaca; font-size:0.75rem;">
                    ISO GQL: -[:TRANSFERS_TO*2..4]-&gt;
                  </span>
                </h5>
                <p class="text-muted small mb-0">
                  Exposing how flat waitlists at regional coordinator desks conceal downstream paper-fax loops that breach the federal 45-day Part C evaluation clock.
                </p>
              </div>
              <button class="btn btn-outline-primary btn-sm rounded-pill fw-semibold" onclick="activateTrack(1)">
                <i class="fa-solid fa-clock-rotate-left me-1"></i> View Interactive Clock Graph in Navigator &rarr;
              </button>
            </div>
            <div class="row g-3 mt-1">
              <div class="col-md-3">
                <div class="p-3 bg-white border rounded-3 text-center">
                  <div class="stat-badge text-danger" style="font-size:1.3rem; font-weight:800; color:#e11d48 !important;">26 of 35</div>
                  <div class="small fw-bold text-dark">Chains Breaching &le;45d</div>
                  <div class="text-muted" style="font-size:0.72rem;">Statewide statutory violations</div>
                </div>
              </div>
              <div class="col-md-3">
                <div class="p-3 bg-white border rounded-3 text-center">
                  <div class="stat-badge text-warning" style="font-size:1.3rem; font-weight:800; color:#d97706 !important;">5–6 Days</div>
                  <div class="small fw-bold text-dark">Deceptive Desk Wait</div>
                  <div class="text-muted" style="font-size:0.72rem;">Reported waitlist conceals bounce</div>
                </div>
              </div>
              <div class="col-md-3">
                <div class="p-3 bg-white border rounded-3 text-center">
                  <div class="stat-badge text-danger" style="font-size:1.3rem; font-weight:800; color:#b91c1c !important;">70.0 Days</div>
                  <div class="small fw-bold text-dark">Avg 4-Hop Fax Chain</div>
                  <div class="text-muted" style="font-size:0.72rem;">+25 days over legal limit</div>
                </div>
              </div>
              <div class="col-md-3">
                <div class="p-3 bg-white border rounded-3 text-center">
                  <div class="stat-badge text-success" style="font-size:1.3rem; font-weight:800; color:#15803d !important;">1,168 Days</div>
                  <div class="small fw-bold text-dark">Delay Days Saved</div>
                  <div class="text-muted" style="font-size:0.72rem;">Via electronic triage routing</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Coordinator "Bounce Hub" Summary Table -->
      <div class="row">
        <div class="col-12">
          <div class="card p-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
              <h5 id="bounceTableTitle" class="card-title mb-0 fw-bold"><i class="fa-solid fa-triangle-exclamation text-warning me-2"></i>Coordinator "Bounce Hub" Summary (Deceptive Waitlist vs Breaches)</h5>
              <span class="badge bg-danger-subtle text-danger border border-danger-subtle">Variable-Length ISO GQL Audit</span>
            </div>
            <p class="text-muted small mb-3">
              Flat directories show low internal coordinator waitlists (5–8 days), disguising downstream paper-fax handoffs that breach the 45-day federal clock.
            </p>
            <div class="table-responsive">
              <table class="table table-hover align-middle mb-0 table-custom">
                <thead>
                  <tr>
                    <th>Coordinator (Bounce Hub)</th>
                    <th>Internal Wait</th>
                    <th>Active Waitlist</th>
                    <th>Paper Fax Handoffs</th>
                    <th>Breached Chains Caused</th>
                    <th>Impact Assessment</th>
                  </tr>
                </thead>
                <tbody id="bounceTableBody">
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ========================================== -->
    <!-- TRACK 3 PANE: OUTREACH SEASON (HIDDEN) -->
    <!-- ========================================== -->
    <div id="trackPane3" class="track-pane" style="display: none !important;">
      <div class="row">
        <!-- Community Equity & Mobile Screening Priorities -->
        <div class="col-12">
          <div class="card p-4">
            <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
              <div>
                <h5 class="card-title mb-1 fw-bold"><i class="fa-solid fa-map-location-dot text-primary me-2"></i>Outreach Season: Community Screening &amp; Mobile Evaluation Priority</h5>
                <p class="text-muted small mb-0">
                  Combining <strong>ACS Under-5 Poverty</strong>, <strong>Vehicle Access Deficit</strong>, and <strong>HRSA NSCH Statewide Screening Baselines</strong> to pinpoint where mobile units and bilingual pop-up clinics must deploy.
                </p>
              </div>
              <button class="btn btn-outline-primary btn-sm" onclick="loadEquityAuditData()">
                <i class="fa-solid fa-rotate me-1"></i> Refresh Census Audit Data
              </button>
            </div>

            <div class="row g-3 mb-4">
              <div class="col-md-4">
                <div class="border rounded-4 p-3 bg-white h-100 shadow-sm" style="border-left: 4px solid #fb7185 !important; background: linear-gradient(145deg, #fff1f2 0%, #ffffff 100%);">
                  <div class="d-flex align-items-center justify-content-between mb-2">
                    <span class="badge rounded-pill bg-danger px-2 py-1"><i class="fa-solid fa-triangle-exclamation me-1"></i>Priority 1</span>
                    <span class="badge rounded-pill" style="background:#fee2e2; color:#991b1b;"><i class="fa-solid fa-baby me-1"></i>High Risk</span>
                  </div>
                  <strong class="d-block mb-1" style="font-size:0.95rem;">St. Lawrence County (Tract 36089491500)</strong>
                  <div class="text-muted small mb-1">Under-5 Poverty: <strong>25.4%</strong> • Zero-Vehicle: <strong>24.0%</strong></div>
                  <div class="text-muted small mb-2">Avg Referral Wait: <strong class="text-danger">77.0 Days</strong> (Multi-Hop Fax)</div>
                  <span class="badge rounded-pill px-3 py-1 text-white shadow-sm" style="background:#e11d48;"><i class="fa-solid fa-van-shuttle me-1"></i>Deploy: Mobile Dev Van + NEMT</span>
                </div>
              </div>
              <div class="col-md-4">
                <div class="border rounded-4 p-3 bg-white h-100 shadow-sm" style="border-left: 4px solid #f59e0b !important; background: linear-gradient(145deg, #fefce8 0%, #ffffff 100%);">
                  <div class="d-flex align-items-center justify-content-between mb-2">
                    <span class="badge rounded-pill bg-warning text-dark px-2 py-1"><i class="fa-solid fa-clock me-1"></i>Priority 2</span>
                    <span class="badge rounded-pill" style="background:#fef9c3; color:#854d0e;"><i class="fa-solid fa-route me-1"></i>Bounce Loop</span>
                  </div>
                  <strong class="d-block mb-1" style="font-size:0.95rem;">St. Lawrence County (Tract 36089491000)</strong>
                  <div class="text-muted small mb-1">Under-5 Poverty: <strong>13.4%</strong> • Zero-Vehicle: <strong>4.1%</strong></div>
                  <div class="text-muted small mb-2">Avg Referral Wait: <strong class="text-danger">77.0 Days</strong> (Bounce Loop)</div>
                  <span class="badge rounded-pill px-3 py-1 text-white shadow-sm" style="background:#0284c7;"><i class="fa-solid fa-calendar-check me-1"></i>Deploy: Community Screening Day 1</span>
                </div>
              </div>
              <div class="col-md-4">
                <div class="border rounded-4 p-3 bg-white h-100 shadow-sm" style="border-left: 4px solid #10b981 !important; background: linear-gradient(145deg, #f0fdf4 0%, #ffffff 100%);">
                  <div class="d-flex align-items-center justify-content-between mb-2">
                    <span class="badge rounded-pill bg-success px-2 py-1"><i class="fa-solid fa-shield-heart me-1"></i>Priority 3</span>
                    <span class="badge rounded-pill" style="background:#dcfce7; color:#166534;"><i class="fa-solid fa-bus me-1"></i>Transit Deficit</span>
                  </div>
                  <strong class="d-block mb-1" style="font-size:0.95rem;">Bronx County (Tract 36005019700)</strong>
                  <div class="text-muted small mb-1">Under-5 Poverty: <strong>21.2%</strong> • Zero-Vehicle: <strong class="text-danger">83.5% Deficit</strong></div>
                  <div class="text-muted small mb-2">Nearest Eval Hub: <strong class="text-danger">111.7 Miles</strong> (Cross-County Bounces)</div>
                  <span class="badge rounded-pill px-3 py-1 text-white shadow-sm" style="background:#059669;"><i class="fa-solid fa-laptop-medical me-1"></i>Deploy: Bilingual Tele-Assessment</span>
                </div>
              </div>
            </div>

            <div class="table-responsive">
              <table class="table table-hover align-middle mb-0 table-custom">
                <thead>
                  <tr>
                    <th>Census Tract GEOID</th>
                    <th>County</th>
                    <th>Under-5 Poverty Rate</th>
                    <th>Zero-Vehicle Deficit</th>
                    <th>Avg Case Wait</th>
                    <th>Breached Chains</th>
                    <th>Outreach Action</th>
                  </tr>
                </thead>
                <tbody id="equityTableBody">
                  <tr>
                    <td><code>36089491500</code></td>
                    <td>St. Lawrence County</td>
                    <td><span class="badge bg-light text-dark border">25.4%</span></td>
                    <td><span class="badge bg-warning text-dark">24.0% High Deficit</span></td>
                    <td><span class="badge bg-danger">77.0 days</span></td>
                    <td>1 / 1</td>
                    <td><span class="badge bg-danger">Mobile Evaluation Van</span></td>
                  </tr>
                  <tr>
                    <td><code>36089491000</code></td>
                    <td>St. Lawrence County</td>
                    <td><span class="badge bg-light text-dark border">13.4%</span></td>
                    <td>4.1%</td>
                    <td><span class="badge bg-danger">77.0 days</span></td>
                    <td>1 / 1</td>
                    <td><span class="badge bg-primary">Community Screening Day 1</span></td>
                  </tr>
                  <tr>
                    <td><code>36089490300</code></td>
                    <td>St. Lawrence County</td>
                    <td><span class="badge bg-light text-dark border">17.5%</span></td>
                    <td>9.5%</td>
                    <td><span class="badge bg-danger">76.0 days</span></td>
                    <td>1 / 1</td>
                    <td><span class="badge bg-primary">Community Screening Day 2</span></td>
                  </tr>
                  <tr>
                    <td><code>36005019700</code></td>
                    <td>Bronx County</td>
                    <td><span class="badge bg-light text-dark border">21.2%</span></td>
                    <td><span class="badge bg-warning text-dark">83.5% High Deficit</span></td>
                    <td><span class="badge bg-danger">70.0 days</span></td>
                    <td>1 / 1</td>
                    <td><span class="badge bg-success">Tele-Assessment + NEMT</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
    </div>

    <!-- ========================================== -->
    <!-- TRACK 5 PANE: MULTI-AGENT TRACES & AUDIT   -->
    <!-- ========================================== -->
    <div id="trackPane5" class="track-pane">
      <!-- Card 1: Multi-Agent Triage Execution Breakdown -->
      <div class="row mb-4">
        <div class="col-12">
          <div class="card p-4 border shadow-sm" style="background: linear-gradient(180deg, #fdfbf7 0%, #ffffff 100%); border-radius: 1.25rem;">
            <!-- Header -->
            <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 pb-2 border-bottom gap-2">
              <div>
                <h5 class="card-title mb-1 fw-bold text-dark d-flex align-items-center">
                  <i class="fa-solid fa-network-wired text-primary me-2"></i>Multi-Agent Triage Execution Breakdown
                  <span class="badge rounded-pill ms-2" style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-size:0.75rem;">
                    Google ADK Sequential Pipeline
                  </span>
                </h5>
                <p class="text-muted small mb-0">
                  Detailed inspection of what each specialized autonomous agent performed during this child's triage, including data inputs, algorithmic decisions, tools invoked, and clock compliance.
                </p>
              </div>
              <div class="d-flex align-items-center gap-2">
                <span class="badge bg-white text-secondary border p-2 rounded-pill shadow-xs" style="font-size: 0.76rem;">
                  <i class="fa-solid fa-fingerprint me-1 text-primary"></i>Trace ID: 
                  <span id="triageTraceIdBadge" class="font-monospace text-dark fw-bold">Live Execution Active</span>
                </span>
                <span id="overallTriageBadge" class="badge rounded-pill p-2" style="background:#dcfce7; color:#166534; border:1px solid #bbf7d0; font-size: 0.76rem;">
                  <i class="fa-solid fa-circle-check me-1"></i>All 4 Agents Completed
                </span>
              </div>
            </div>

            <!-- 4-Agent Pipeline Workflow Cards -->
            <div class="row g-3 row-cols-1 row-cols-md-2 row-cols-xl-4 mb-2">
              <!-- Agent 1: Pathway Router -->
              <div class="col">
                <div class="card h-100 p-3 bg-white shadow-xs position-relative" style="border: 1px solid #bae6fd !important; border-top: 4px solid #38bdf8 !important; border-radius: 1.15rem;">
                  <div class="d-flex justify-content-between align-items-start mb-2">
                    <span class="badge rounded-pill" style="background:#e0f2fe; color:#0284c7; border:1px solid #bae6fd; font-size: 0.72rem; font-weight:700;">Step 1 · Router</span>
                    <span id="agent1StatusBadge" class="badge bg-success-subtle text-success border border-success-subtle rounded-pill" style="font-size: 0.7rem;">COMPLETED</span>
                  </div>
                  <h6 class="fw-bold mb-1 text-dark" style="font-size: 0.9rem;">
                    <i class="fa-solid fa-compass text-primary me-1"></i>Pathway Router Agent
                  </h6>
                  <div class="text-secondary small mb-2" style="font-size: 0.72rem;"><code>pathway_router_agent</code></div>
                  
                  <div class="mb-2 p-2 rounded small" style="background: #f0f9ff; border: 1px solid #e0f2fe; font-size: 0.74rem;">
                    <strong class="text-dark d-block mb-1"><i class="fa-solid fa-screwdriver-wrench text-secondary me-1"></i>Tools Invoked:</strong>
                    <div class="text-primary font-monospace" style="font-size: 0.7rem;">• resolve_geographic_location_and_nearest_clinics</div>
                    <div class="text-primary font-monospace" style="font-size: 0.7rem;">• find_compliant_toddler_pathway</div>
                  </div>

                  <div class="small mb-2" style="font-size: 0.74rem;">
                    <strong class="text-dark d-block mb-1"><i class="fa-solid fa-list-check text-secondary me-1"></i>What This Agent Did:</strong>
                    <ul class="ps-3 mb-1 text-muted" id="agent1ActionsList">
                      <li>Geocoded location to Census Tract GEOID and resolved nearest screening clinics.</li>
                      <li>Audited 36m Part C statutory age cliff (flagging fast-track if 30+ months).</li>
                      <li>Traversed BigQuery care graph for optimal ≤45d pathway with Medicaid & Spanish capacity.</li>
                    </ul>
                  </div>

                  <div class="mt-auto pt-2 border-top small" style="font-size: 0.72rem;">
                    <div class="d-flex justify-content-between text-muted">
                      <span>Latency: <strong id="agent1Latency" class="text-dark">18.2ms</strong></span>
                      <span id="agent1ResultHop" class="text-success fw-bold">≤ 45d Guaranteed</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Agent 2: Network Bottleneck Auditor -->
              <div class="col">
                <div class="card h-100 p-3 bg-white shadow-xs position-relative" style="border: 1px solid #fef08a !important; border-top: 4px solid #fde047 !important; border-radius: 1.15rem;">
                  <div class="d-flex justify-content-between align-items-start mb-2">
                    <span class="badge rounded-pill" style="background:#fef9c3; color:#854d0e; border:1px solid #fef08a; font-size: 0.72rem; font-weight:700;">Step 2 · Pre-Audit</span>
                    <span id="agent2StatusBadge" class="badge bg-success-subtle text-success border border-success-subtle rounded-pill" style="font-size: 0.7rem;">COMPLETED</span>
                  </div>
                  <h6 class="fw-bold mb-1 text-dark" style="font-size: 0.9rem;">
                    <i class="fa-solid fa-shield-halved text-warning me-1"></i>Network Audit Agent
                  </h6>
                  <div class="text-secondary small mb-2" style="font-size: 0.72rem;"><code>network_audit_agent</code></div>
                  
                  <div class="mb-2 p-2 rounded small" style="background: #fefce8; border: 1px solid #fef9c3; font-size: 0.74rem;">
                    <strong class="text-dark d-block mb-1"><i class="fa-solid fa-screwdriver-wrench text-secondary me-1"></i>Tools Invoked:</strong>
                    <div class="text-warning-emphasis font-monospace" style="font-size: 0.7rem;">• trace_45day_breaches_and_bounce_hubs</div>
                    <div class="text-warning-emphasis font-monospace" style="font-size: 0.7rem;">• validate_pre_handoff_packet</div>
                  </div>

                  <div class="small mb-2" style="font-size: 0.74rem;">
                    <strong class="text-dark d-block mb-1"><i class="fa-solid fa-list-check text-secondary me-1"></i>What This Agent Did:</strong>
                    <ul class="ps-3 mb-1 text-muted" id="agent2ActionsList">
                      <li>Audited Hop-2 coordinator channels to bypass deceptive 5-day paper-fax bounce hubs.</li>
                      <li>Validated pre-handoff packet completeness (parental consent + ASQ-3 screening).</li>
                      <li>Locked pathway to direct electronic EHR intake desk (eliminating 38d loop).</li>
                    </ul>
                  </div>

                  <div class="mt-auto pt-2 border-top small" style="font-size: 0.72rem;">
                    <div class="d-flex justify-content-between text-muted">
                      <span>Latency: <strong id="agent2Latency" class="text-dark">9.4ms</strong></span>
                      <span id="agent2PacketStatus" class="text-success fw-bold">Packet Validated</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Agent 3: Equity Auditor -->
              <div class="col">
                <div class="card h-100 p-3 bg-white shadow-xs position-relative" style="border: 1px solid #bbf7d0 !important; border-top: 4px solid #86efac !important; border-radius: 1.15rem;">
                  <div class="d-flex justify-content-between align-items-start mb-2">
                    <span class="badge rounded-pill" style="background:#dcfce7; color:#166534; border:1px solid #bbf7d0; font-size: 0.72rem; font-weight:700;">Step 3 · Demographics</span>
                    <span id="agent3StatusBadge" class="badge bg-success-subtle text-success border border-success-subtle rounded-pill" style="font-size: 0.7rem;">COMPLETED</span>
                  </div>
                  <h6 class="fw-bold mb-1 text-dark" style="font-size: 0.9rem;">
                    <i class="fa-solid fa-scale-balanced text-success me-1"></i>Equity Audit Agent
                  </h6>
                  <div class="text-secondary small mb-2" style="font-size: 0.72rem;"><code>equity_audit_agent</code></div>
                  
                  <div class="mb-2 p-2 rounded small" style="background: #f0fdf4; border: 1px solid #dcfce7; font-size: 0.74rem;">
                    <strong class="text-dark d-block mb-1"><i class="fa-solid fa-screwdriver-wrench text-secondary me-1"></i>Tools Invoked:</strong>
                    <div class="text-success font-monospace" style="font-size: 0.7rem;">• run_equity_and_counterfactual_audit</div>
                  </div>

                  <div class="small mb-2" style="font-size: 0.74rem;">
                    <strong class="text-dark d-block mb-1"><i class="fa-solid fa-list-check text-secondary me-1"></i>What This Agent Did:</strong>
                    <ul class="ps-3 mb-1 text-muted" id="agent3ActionsList">
                      <li>Audited Census tract under-5 poverty and zero-vehicle household demographics.</li>
                      <li>Assessed transit burden; deployed transportation assistance guardrail if zero-vehicle >15%.</li>
                      <li>Calculated counterfactual days saved (+23d to +38d) vs legacy paper fax.</li>
                    </ul>
                  </div>

                  <div class="mt-auto pt-2 border-top small" style="font-size: 0.72rem;">
                    <div class="d-flex justify-content-between text-muted">
                      <span>Latency: <strong id="agent3Latency" class="text-dark">6.1ms</strong></span>
                      <span id="agent3TransitStatus" class="text-success fw-bold">Guardrail Active</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Agent 4: Caregiver Note Agent -->
              <div class="col">
                <div class="card h-100 p-3 bg-white shadow-xs position-relative" style="border: 1px solid #e9d5ff !important; border-top: 4px solid #d8b4fe !important; border-radius: 1.15rem;">
                  <div class="d-flex justify-content-between align-items-start mb-2">
                    <span class="badge rounded-pill" style="background:#f3e8ff; color:#7c3aed; border:1px solid #e9d5ff; font-size: 0.72rem; font-weight:700;">Step 4 · Caregiver</span>
                    <span id="agent4StatusBadge" class="badge bg-success-subtle text-success border border-success-subtle rounded-pill" style="font-size: 0.7rem;">COMPLETED</span>
                  </div>
                  <h6 class="fw-bold mb-1 text-dark" style="font-size: 0.9rem;">
                    <i class="fa-solid fa-language me-1" style="color:#7c3aed;"></i>Caregiver Note Agent
                  </h6>
                  <div class="text-secondary small mb-2" style="font-size: 0.72rem;"><code>caregiver_note_agent</code></div>
                  
                  <div class="mb-2 p-2 rounded small" style="background: #faf5ff; border: 1px solid #f3e8ff; font-size: 0.74rem;">
                    <strong class="text-dark d-block mb-1"><i class="fa-solid fa-screwdriver-wrench text-secondary me-1"></i>Tools Invoked:</strong>
                    <div class="font-monospace" style="color:#7c3aed; font-size: 0.7rem;">• format_bilingual_caregiver_note</div>
                  </div>

                  <div class="small mb-2" style="font-size: 0.74rem;">
                    <strong class="text-dark d-block mb-1"><i class="fa-solid fa-list-check text-secondary me-1"></i>What This Agent Did:</strong>
                    <ul class="ps-3 mb-1 text-muted" id="agent4ActionsList">
                      <li>Synthesized clinical handoff data into plain-language, jargon-free parent action steps.</li>
                      <li>Drafted synchronized dual-language English and Spanish letters with coordinator direct lines.</li>
                      <li>Incorporated 34 CFR § 303.310 statutory 45-day evaluation guarantee rights.</li>
                    </ul>
                  </div>

                  <div class="mt-auto pt-2 border-top small" style="font-size: 0.72rem;">
                    <div class="d-flex justify-content-between text-muted">
                      <span>Latency: <strong id="agent4Latency" class="text-dark">4.9ms</strong></span>
                      <span id="agent4NoteStatus" class="fw-bold" style="color:#7c3aed;">Bilingual Ready</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Card 3: BigQuery Trace Telemetry Audit Log Table -->
      <div class="row">
        <div class="col-12">
          <div class="card p-4 border shadow-sm" style="background: #ffffff; border-radius: 1.25rem;">
            <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
              <div>
                <h5 class="card-title mb-1 fw-bold text-dark d-flex align-items-center">
                  <i class="fa-solid fa-database text-primary me-2"></i>BigQuery Trace Audit Log
                  <span class="badge rounded-pill ms-2" style="background:#fef9c3; color:#713f12; border:1px solid #fef08a; font-size:0.72rem;">
                    Telemetry Stream (a4i_early_intervention.triage_agent_execution_traces)
                  </span>
                </h5>
                <p class="text-muted small mb-0">
                  Live streaming execution trace events captured across all 4 autonomous sub-agents during triage queries.
                </p>
              </div>
              <button class="btn btn-outline-primary btn-sm rounded-pill fw-semibold" onclick="loadRecentTraces()">
                <i class="fa-solid fa-rotate me-1"></i> Refresh Traces
              </button>
            </div>
            <div class="table-responsive">
              <table class="table table-hover align-middle mb-0 table-custom">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Trace ID</th>
                    <th>Agent Name</th>
                    <th>Event Type</th>
                    <th>Status</th>
                    <th class="text-end">Latency</th>
                  </tr>
                </thead>
                <tbody id="bqTracesTableBody">
                  <tr>
                    <td colspan="6" class="text-center text-muted py-3">Click Refresh Traces to inspect live BigQuery execution logs.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal: Bilingual Caregiver Action Note -->
  <div class="modal fade" id="caregiverModal" tabindex="-1" aria-labelledby="caregiverModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header bg-primary text-white">
          <h5 class="modal-title" id="caregiverModalLabel"><i class="fa-solid fa-file-signature me-2"></i>Bilingual Caregiver Action Note (English &amp; Spanish)</h5>
          <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <ul class="nav nav-tabs mb-3" id="caregiverTabs" role="tablist">
            <li class="nav-item" role="presentation">
              <button class="nav-link active fw-bold" id="en-tab" data-bs-toggle="tab" data-bs-target="#en-pane" type="button" role="tab">English Plain-Language Note</button>
            </li>
            <li class="nav-item" role="presentation">
              <button class="nav-link fw-bold" id="es-tab" data-bs-toggle="tab" data-bs-target="#es-pane" type="button" role="tab">Nota en Español para la Familia</button>
            </li>
          </ul>
          <div class="tab-content" id="caregiverTabContent">
            <div class="tab-pane fade show active" id="en-pane" role="tabpanel">
              <div class="p-3 bg-light rounded border font-monospace small" id="caregiverNoteEn" style="white-space: pre-wrap;"></div>
            </div>
            <div class="tab-pane fade" id="es-pane" role="tabpanel">
              <div class="p-3 bg-light rounded border font-monospace small" id="caregiverNoteEs" style="white-space: pre-wrap;"></div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
          <button type="button" class="btn btn-outline-primary" onclick="window.print()"><i class="fa-solid fa-print me-1"></i> Print / Save PDF</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    let sessionId = null;
    let activeState = "NY";

    const STATE_DATA = {
      NY: {
        name: "New York (NY)",
        county: "Bronx County",
        tract: "36005019700",
        nodes: [
          { id: "SYN-PROV-NY-007", short: "NY-007 (Lockport Clinic)", wait: 6, x: 75, y: 115, color: "#38bdf8" },
          { id: "SYN-PROV-NY-011", short: "NY-011 (Walton Bounce Hub)", wait: 5, x: 265, y: 115, color: "#f59e0b", bounceHub: true },
          { id: "SYN-PROV-NY-015", short: "NY-015 (Canton Saturated)", wait: 34, x: 470, y: 52, color: "#ef4444" },
          { id: "SYN-PROV-NY-019", short: "NY-019 (Lockport Bilingual)", wait: 7, x: 470, y: 145, color: "#a855f7" },
          { id: "SYN-PROV-NY-028", short: "NY-028 (Malone Therapy)", wait: 6, x: 675, y: 52, color: "#10b981" },
          { id: "SYN-PROV-NY-027", short: "NY-027 (Canton Therapy)", wait: 10, x: 675, y: 145, color: "#10b981" },
          { id: "SYN-PROV-NY-026", short: "NY-026 (Jamestown Therapy)", wait: 8, x: 675, y: 205, color: "#10b981" }
        ],
        paths: {
          bounce: {
            id: "CHAIN-NY-023",
            title: "🚨 CHAIN-NY-023: 4-Hop Paper-Fax Bounce (70 Days — Breaches 45d Limit!)",
            subtitle: "32-month-old toddler (4 mos from 36m Part C aging-out cliff!) • Autism/Speech Screen",
            total: 70,
            color: "#ef4444",
            edges: [
              { from: "SYN-PROV-NY-007", to: "SYN-PROV-NY-011", hop: 1, days: 12, chan: "paper_fax", dy: -12 },
              { from: "SYN-PROV-NY-011", to: "SYN-PROV-NY-015", hop: 2, days: 20, chan: "paper_fax", dy: -8 },
              { from: "SYN-PROV-NY-015", to: "SYN-PROV-NY-019", hop: 3, days: 22, chan: "paper_fax", dy: 0 },
              { from: "SYN-PROV-NY-019", to: "SYN-PROV-NY-028", hop: 4, days: 16, chan: "ehr_portal", dy: -8 }
            ]
          },
          eval: {
            id: "CHAIN-NY-007",
            title: "✅ CHAIN-NY-007: 3-Hop Electronic Bilingual Route (40 Days — Saves 30 Days!)",
            subtitle: "Same Clinic (NY-007) & Same Coordinator (NY-011), routed via EHR directly to NY-019",
            total: 40,
            color: "#22c55e",
            edges: [
              { from: "SYN-PROV-NY-007", to: "SYN-PROV-NY-011", hop: 1, days: 9, chan: "ehr_portal", dy: 14 },
              { from: "SYN-PROV-NY-011", to: "SYN-PROV-NY-019", hop: 2, days: 14, chan: "ehr_portal", dy: 10 },
              { from: "SYN-PROV-NY-019", to: "SYN-PROV-NY-027", hop: 3, days: 17, chan: "ehr_portal", dy: 10 }
            ]
          },
          fast: {
            id: "CHAIN-NY-031",
            title: "⚡ CHAIN-NY-031: 2-Hop Electronic Fast-Track (22 Days — Saves 48 Days!)",
            subtitle: "Direct Fast-Track IFSP Placement for eligible NY toddlers via EHR Portal",
            total: 22,
            color: "#38bdf8",
            edges: [
              { from: "SYN-PROV-NY-007", to: "SYN-PROV-NY-011", hop: 1, days: 8, chan: "ehr_portal", dy: 18 },
              { from: "SYN-PROV-NY-011", to: "SYN-PROV-NY-026", hop: 2, days: 14, chan: "ehr_portal", dy: 14 }
            ]
          }
        },
        hubs: [
          { name: "Walton Regional Intake Desk (SYN-PROV-NY-011)", wait: "5 days", list: 24, fax: "5 handoffs", breaches: "7 breaches (70+ days)", note: "Hidden bottleneck; low waitlist conceals paper-fax dropoffs." },
          { name: "Bronx Regional Intake Desk (SYN-PROV-NY-012)", wait: "6 days", list: 29, fax: "5 handoffs", breaches: "7 breaches (70+ days)", note: "Urban high-volume re-referral hub with paper-fax delays." },
          { name: "Canton Regional Intake Desk (SYN-PROV-NY-009)", wait: "8 days", list: 14, fax: "4 handoffs", breaches: "6 breaches (70+ days)", note: "North Country cross-county bounces into backlogged eval hubs." }
        ]
      }
    };

    let svgGraphNodes = STATE_DATA.NY.nodes;
    let svgGraphPaths = STATE_DATA.NY.paths;

    function setActiveState(st) {
      activeState = st;
      const cfg = STATE_DATA[st];
      svgGraphNodes = cfg.nodes;
      svgGraphPaths = cfg.paths;
      const btnNY = document.getElementById('btnStateNY');
      if (btnNY) btnNY.className = st === 'NY' ? 'btn btn-warning fw-bold text-dark' : 'btn btn-outline-light';
      const btnMS = document.getElementById('btnStateMS');
      if (btnMS) btnMS.className = st === 'MS' ? 'btn btn-warning fw-bold text-dark' : 'btn btn-outline-light';
      const tractInput = document.getElementById('tractGeoid');
      if (tractInput) tractInput.value = cfg.tract;
      document.getElementById('graphCardTitle').innerHTML = `🕸️ ReferralGraph (${st}) Side-by-Side Pathway &amp; 45-Day Statutory Clock`;
      document.getElementById('graphCardSubtitle').innerHTML = `Comparing the <strong>${cfg.paths.bounce.total}-day 4-hop paper-fax bounce loop (${cfg.paths.bounce.id}, 32m toddler)</strong> vs. the <strong>${cfg.paths.eval.total}-day 3-hop e-referral route (${cfg.paths.eval.id})</strong> &amp; <strong>${cfg.paths.fast.total}-day 2-hop fast-track (${cfg.paths.fast.id})</strong> from the exact same ${st} clinic &amp; coordinator.`;
      document.getElementById('bounceTableTitle').innerText = `📊 ${cfg.name} Coordinator "Bounce Hub" Summary (Deceptive Waitlist vs Breaches)`;
      document.getElementById('bounceTableBody').innerHTML = cfg.hubs.map(h => `
        <tr>
          <td><strong>${h.name}</strong></td>
          <td><span class="badge bg-success">${h.wait}</span></td>
          <td>${h.list}</td>
          <td>${h.fax}</td>
          <td><span class="badge badge-breach">${h.breaches}</span></td>
          <td>${h.note}</td>
        </tr>
      `).join('');
      document.getElementById('trackBannerInfo').innerHTML = `Ready to route a 20-month-old Spanish-speaking Medicaid referral in ${cfg.county}, ${st} (Tract ${cfg.tract}).`;
      const mapTitle = document.getElementById('mapCardTitle');
      if (mapTitle) {
        mapTitle.innerHTML = `<i class="fa-solid fa-earth-americas text-primary me-2"></i>Physical Map of ${cfg.name} — ReferralGraph &amp; Census Tracts Overlay`;
      }
      renderSvgComparisonGraph();
      loadStatePhysicalMap(st);
    }

    function activateTrack(trackNum) {
      // Toggle button active states and pane visibility
      for (let i = 1; i <= 5; i++) {
        const btn = document.getElementById('btnTrack' + i);
        const pane = document.getElementById('trackPane' + i);
        if (btn) {
          if (btn.classList.contains('d-none')) {
            // Keep hidden buttons invisible
          } else if (i === trackNum) {
            btn.className = 'btn btn-sm btn-light track-nav-btn active';
          } else {
            btn.className = 'btn btn-sm btn-outline-light track-nav-btn';
          }
        }
        if (pane) {
          if (i === trackNum) {
            pane.classList.add('active');
          } else {
            pane.classList.remove('active');
          }
        }
      }

      const info = document.getElementById('trackBannerInfo');
      const input = document.getElementById('userInput');
      const cfg = STATE_DATA[activeState];

      if (trackNum === 1) {
        if (info) info.innerHTML = "<strong>Track 1 Active:</strong> Route today's toddler referral (&le;45d compliant path with 36m age cliff guard).";
        if (input) input.value = `Route a 20-month-old Spanish-speaking Medicaid toddler in ${cfg.county} tract ${cfg.tract}.`;
      } else if (trackNum === 2) {
        if (info) info.innerHTML = "<strong>Track 2 Active:</strong> Variable-length GQL exposes systemic paper-fax bounce hubs breaking federal clock.";
        if (input) input.value = `Trace 3-to-4 hop referral chains breaching 45 days in ${activeState} and identify the regional bounce hubs.`;
      } else if (trackNum === 3) {
        if (info) info.innerHTML = "<strong>Track 3 Active:</strong> Combine ACS under-5 poverty & NSCH screening baselines to deploy mobile screening days.";
        if (input) input.value = `Where should community developmental screening outreach days go first in ${cfg.name}?`;
        if (typeof loadEquityAuditData === 'function') loadEquityAuditData();
      } else if (trackNum === 4) {
        if (info) info.innerHTML = "<strong>Extra Credit Active:</strong> Graph Simulation — Compute how many breached cases drop &le;45d when converting one paper-fax coordinator to electronic intake + bilingual pre-checking.";
        if (input) input.value = "Simulate network fix: how many breached cases drop under 45 days if Walton Regional Desk (SYN-PROV-NY-011) switches to electronic intake with pre-checked bilingual slots?";
        const simEl = document.getElementById('simResultsArea');
        if (simEl) simEl.scrollIntoView({ behavior: 'smooth' });
      } else if (trackNum === 5) {
        if (info) info.innerHTML = "<strong>Execution Traces Active:</strong> Multi-agent execution pipeline breakdown and BigQuery streaming execution trace audit log.";
        if (input) input.value = "Inspect BigQuery multi-agent execution traces for active New York care network.";
        if (typeof loadRecentTraces === 'function') loadRecentTraces();
      }
      if (leafletMap) {
        setTimeout(() => leafletMap.invalidateSize(), 150);
      }
    }

    async function loadRecentTraces() {
      const tbody = document.getElementById('bqTracesTableBody');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3"><i class="fa-solid fa-spinner fa-spin me-1"></i> Streaming BigQuery execution traces...</td></tr>';
      try {
        const res = await fetch('/api/traces/recent?limit=15');
        const data = await res.json();
        if (data.traces && data.traces.length > 0) {
          tbody.innerHTML = data.traces.map(t => {
            const isBreach = t.status === 'BREACH' || t.status === 'ERROR';
            const isSuccess = t.status === 'SUCCESS' || t.status === 'OK' || t.status === 'COMPLIANT';
            const badgeClass = isBreach ? 'badge bg-danger' : (isSuccess ? 'badge bg-success' : 'badge bg-info');
            const shortTrace = t.trace_id ? (t.trace_id.length > 12 ? t.trace_id.substring(0, 12) + '...' : t.trace_id) : 'N/A';
            const timeStr = t.timestamp ? t.timestamp.substring(11, 19) : '--:--:--';
            return `<tr>
              <td class="font-monospace small">${timeStr}</td>
              <td><span class="font-monospace small text-primary fw-bold">${shortTrace}</span></td>
              <td><span class="badge rounded-pill" style="background:#f1f5f9; color:#334155; border:1px solid #cbd5e1; font-size:0.72rem;">${t.agent_name || 'agent'}</span></td>
              <td class="small">${t.event_type || 'triage_event'}</td>
              <td><span class="${badgeClass}">${t.status || 'OK'}</span></td>
              <td class="font-monospace small text-end">${t.latency_ms ? t.latency_ms + 'ms' : '<10ms'}</td>
            </tr>`;
          }).join('');
        } else {
          tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No traces recorded yet. Calculate a pathway or query Maya to generate execution traces.</td></tr>';
        }
      } catch (err) {
        console.error('Failed to load traces', err);
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger py-3"><i class="fa-solid fa-triangle-exclamation me-1"></i> Failed to connect to BigQuery telemetry stream.</td></tr>';
      }
    }

    window.addEventListener('DOMContentLoaded', () => {
      setActiveState('NY');
      renderSvgComparisonGraph();
      // Initialize Track 1 location resolution and triage route
      resolveLocationNow();
    });

    let svgCurrentMode = "both";

    function setSvgGraphMode(mode) {
      svgCurrentMode = mode;
      ["both", "bounce", "eval", "fast"].forEach(m => {
        const btn = document.getElementById("btn-mode-" + m);
        if (!btn) return;
        btn.classList.toggle("active", m === mode);
      });
      renderSvgComparisonGraph();
      renderPhysicalMapOverlay();
    }

    let leafletMap = null;
    let mapGraphLayer = null;
    let mapTractLayer = null;
    let mapStateData = null;
    let showTractsOnMap = true;

    function initPhysicalMap() {
      if (leafletMap) return;
      const el = document.getElementById('nyPhysicalMap');
      if (!el || typeof L === 'undefined') return;
      leafletMap = L.map('nyPhysicalMap', { preferCanvas: true }).setView([42.65, -75.4], 7);
      window.leafletMap = leafletMap;
      // 100% Public Domain US Federal Government Basemap (USGS National Map — zero OpenStreetMap ODbL)
      L.tileLayer(
        'https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}',
        {
          maxZoom: 16,
          attribution: 'Map: USGS National Map &amp; US Census TIGER/Line (Public Domain US Gov)'
        }
      ).addTo(leafletMap);
      mapTractLayer = L.layerGroup().addTo(leafletMap);
      mapGraphLayer = L.layerGroup().addTo(leafletMap);
      setTimeout(() => { if (leafletMap) leafletMap.invalidateSize(); }, 200);
    }

    async function loadStatePhysicalMap(st) {
      initPhysicalMap();
      if (!leafletMap) return;
      try {
        const res = await fetch(`/api/graph/map?state_code=${st}`);
        mapStateData = await res.json();
        renderPhysicalMapOverlay();
        zoomMapRegion('state');
      } catch (err) {
        console.error('Failed to load physical map data', err);
      }
    }

    function zoomMapRegion(region, btnEl) {
      if (!leafletMap) return;
      if (btnEl) {
        ['btnZoomState', 'btnZoomBronx', 'btnZoomCatskills'].forEach(id => {
          const b = document.getElementById(id);
          if (b) b.classList.remove('active');
        });
        btnEl.classList.add('active');
      }
      if (activeState === 'MS') {
        leafletMap.setView([33.35, -90.45], region === 'state' ? 8 : 10);
        leafletMap.invalidateSize();
        return;
      }
      if (region === 'bronx') {
        leafletMap.setView([40.848, -73.895], 12);
      } else if (region === 'catskills') {
        leafletMap.setView([42.22, -74.88], 9);
      } else {
        leafletMap.setView([42.65, -75.5], 7);
      }
      leafletMap.invalidateSize();
    }

    function toggleTractLayer(btnEl) {
      showTractsOnMap = !showTractsOnMap;
      if (btnEl) {
        btnEl.classList.toggle('active', showTractsOnMap);
        btnEl.classList.toggle('btn-outline-secondary', !showTractsOnMap);
        btnEl.classList.toggle('btn-secondary', showTractsOnMap);
      }
      renderPhysicalMapOverlay();
    }

    function locateClinicOnMap(lat, lon, name) {
      if (leafletMap || window.leafletMap) {
        const m = leafletMap || window.leafletMap;
        const mapEl = document.getElementById('nyPhysicalMap');
        if (mapEl) mapEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        m.flyTo([lat, lon], 13, { animate: true, duration: 1.0 });
        L.popup().setLatLng([lat, lon]).setContent(`<strong>${name}</strong><br><span class="badge bg-primary">Nearest Screening Center</span>`).openOn(m);
      }
    }

    function renderPhysicalMapOverlay() {
      if (!leafletMap || !mapStateData) return;
      mapTractLayer.clearLayers();
      mapGraphLayer.clearLayers();

      if (showTractsOnMap && mapStateData.tracts) {
        mapStateData.tracts.forEach(t => {
          const isHighNoVeh = t.no_vehicle_pct >= 25.0;
          const circle = L.circleMarker([t.lat, t.lon], {
            radius: Math.max(4, Math.min(9, t.under5 / 80)),
            fillColor: isHighNoVeh ? '#f43f5e' : '#64748b',
            color: '#0f172a',
            weight: 1,
            opacity: 0.65,
            fillOpacity: 0.38
          });
          circle.bindPopup(
            `<strong>Census Tract ${t.geoid}</strong> (${t.county})<br>` +
            `Children Under 5: <strong>${t.under5}</strong><br>` +
            `Poverty Rate: <strong>${t.poverty_pct}%</strong><br>` +
            `Zero-Vehicle Households: <strong>${t.no_vehicle_pct}%</strong>`
          );
          circle.addTo(mapTractLayer);
        });
      }

      const cfg = STATE_DATA[activeState] || STATE_DATA.NY;
      const activePaths = svgCurrentMode === 'both'
        ? [cfg.paths.bounce, cfg.paths.eval]
        : [cfg.paths[svgCurrentMode]];

      const provById = {};
      (mapStateData.providers || []).forEach(p => { provById[p.id] = p; });

      const activeNodeIds = new Set();
      activePaths.forEach(p => {
        p.edges.forEach(e => {
          activeNodeIds.add(e.from);
          activeNodeIds.add(e.to);
          const u = provById[e.from];
          const v = provById[e.to];
          if (u && v) {
            const isFax = e.chan === 'paper_fax';
            const line = L.polyline([[u.lat, u.lon], [v.lat, v.lon]], {
              color: p.color,
              weight: isFax ? 4.5 : 4,
              opacity: 0.92,
              dashArray: isFax ? '8, 6' : null
            });
            line.bindTooltip(
              `<strong>${p.id} Hop ${e.hop}:</strong> ${u.id.split('-').pop()} → ${v.id.split('-').pop()} (+${e.days}d via ${e.chan})`,
              { sticky: true }
            );
            line.addTo(mapGraphLayer);
          }
        });
      });

      const roleColors = {
        'Screening_Pediatric_Clinic': '#38bdf8',
        'Part_C_Intake_Coordinator': '#f59e0b',
        'Multidisciplinary_Eval_Hub': '#a855f7',
        'EI_Therapy_Vendor': '#10b981'
      };

      (mapStateData.providers || []).forEach(p => {
        const isActive = activeNodeIds.has(p.id);
        const isBounceHub = p.id.endsWith('-011') || p.id.endsWith('-012');
        const marker = L.circleMarker([p.lat, p.lon], {
          radius: isActive ? 10 : 6.5,
          fillColor: roleColors[p.role] || '#38bdf8',
          color: isBounceHub ? '#ef4444' : '#0f172a',
          weight: isBounceHub ? 3 : (isActive ? 2.5 : 1.5),
          opacity: isActive ? 1.0 : 0.72,
          fillOpacity: isActive ? 0.95 : 0.65
        });
        marker.bindPopup(
          `<strong>${p.id}</strong><br>${p.name}<br>` +
          `Role: <code>${p.role}</code><br>` +
          `Internal Wait: <strong>${p.wait_days} days</strong> | Waitlist: ${p.waitlist}<br>` +
          `Medicaid: ${p.medicaid ? 'Yes' : 'No'} | Bilingual: ${p.bilingual ? 'Yes' : 'No'}`
        );
        if (isActive) {
          marker.bindTooltip(`${p.id.split('-').slice(-2).join('-')} (${p.wait_days}d)`, {
            permanent: true,
            direction: 'top',
            offset: [0, -8],
            className: 'small fw-bold'
          });
        }
        marker.addTo(mapGraphLayer);
      });
    }

    function renderSvgComparisonGraph() {
      const svg = document.getElementById("svgReferralGraph");
      if (!svg) return;
      const activeList = svgCurrentMode === "both" ? [svgGraphPaths.bounce, svgGraphPaths.eval] : [svgGraphPaths[svgCurrentMode]];
      const nodeById = id => svgGraphNodes.find(n => n.id === id);

      let html = `
        <defs>
          <marker id="arr-red" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#ef4444"/>
          </marker>
          <marker id="arr-green" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#22c55e"/>
          </marker>
          <marker id="arr-blue" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8"/>
          </marker>
        </defs>
      `;

      const headers = [
        { x: 75, label: "1. Screening Clinic" },
        { x: 265, label: "2. Part C Coordinator" },
        { x: 470, label: "3. Multidisciplinary Eval Hub" },
        { x: 675, label: "4. EI Therapy Vendor" }
      ];
      headers.forEach(h => {
        html += `<text x="${h.x}" y="18" text-anchor="middle" font-size="10.5" font-weight="600" fill="#cbd5e1">${h.label}</text>`;
      });

      activeList.forEach(p => {
        const markerId = p.color === "#ef4444" ? "arr-red" : (p.color === "#22c55e" ? "arr-green" : "arr-blue");
        p.edges.forEach(e => {
          const u = nodeById(e.from);
          const v = nodeById(e.to);
          const dash = e.chan === "paper_fax" ? 'stroke-dasharray="5,3"' : "";
          const mx = (u.x + v.x) / 2 + (u.x === v.x ? 42 : 0);
          const my = (u.y + v.y) / 2 + (e.dy || 0);
          html += `
            <path d="M ${u.x} ${u.y} Q ${mx} ${my} ${v.x} ${v.y}" fill="none" stroke="${p.color}" stroke-width="3" ${dash} marker-end="url(#${markerId})" opacity="0.95"/>
            <rect x="${mx - 46}" y="${my - 9}" width="92" height="16" rx="4" fill="#1e293b" stroke="${p.color}" stroke-width="1"/>
            <text x="${mx}" y="${my + 2}" text-anchor="middle" font-size="9.5" font-family="monospace" fill="#f8fafc">H${e.hop}: +${e.days}d (${e.chan === 'paper_fax' ? 'FAX' : 'EHR'})</text>
          `;
        });
      });

      const usedIds = new Set();
      activeList.forEach(p => p.edges.forEach(e => { usedIds.add(e.from); usedIds.add(e.to); }));

      svgGraphNodes.forEach(n => {
        const op = usedIds.has(n.id) ? "1.0" : "0.3";
        const r = n.bounceHub ? 17 : 14;
        const stroke = n.bounceHub ? "#ef4444" : "#0f172a";
        html += `
          <g opacity="${op}">
            <circle cx="${n.x}" cy="${n.y}" r="${r}" fill="${n.color}" stroke="${stroke}" stroke-width="${n.bounceHub ? 3 : 2}"/>
            <text x="${n.x}" y="${n.y + 3}" text-anchor="middle" font-size="8.5" font-weight="700" fill="#0f172a">${n.id.split('-').pop()}</text>
            <text x="${n.x}" y="${n.y + r + 13}" text-anchor="middle" font-size="10" font-weight="600" fill="#f8fafc">${n.short}</text>
            <text x="${n.x}" y="${n.y + r + 24}" text-anchor="middle" font-size="9" fill="#94a3b8">internal wait: ${n.wait}d</text>
          </g>
        `;
      });

      svg.innerHTML = html;

      const cardsDiv = document.getElementById("svgClockCards");
      if (cardsDiv) {
        cardsDiv.innerHTML = activeList.map(p => {
          const pct = Math.min(100, Math.round((p.total / 80) * 100));
          const limitPct = Math.round((45 / 80) * 100);
          const badge = p.total > 45
            ? `<span class="badge badge-breach">+${p.total - 45}d BREACH</span>`
            : `<span class="badge badge-pass">${45 - p.total}d UNDER 45d LIMIT</span>`;
          return `
            <div class="col-md-6">
              <div class="border rounded p-3 bg-white h-100">
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <strong class="small">${p.title}</strong>
                  ${badge}
                </div>
                <div class="text-muted small mb-2">${p.subtitle}</div>
                <div class="position-relative w-100 rounded overflow-hidden mb-2" style="height: 14px; background: #e2e8f0;">
                  <div style="width:${pct}%; height:100%; background:${p.color};"></div>
                  <div style="position:absolute; top:0; bottom:0; left:${limitPct}%; border-left: 2px dashed #d97706;" title="45-Day Statutory Ceiling"></div>
                </div>
                <div class="small font-monospace text-muted">
                  ${p.edges.map(e => `H${e.hop}: ${e.from.split('-').pop()}→${e.to.split('-').pop()} (+${e.days}d ${e.chan})`).join(" • ")}
                </div>
              </div>
            </div>
          `;
        }).join("");
      }
    }

    async function sendMessage() {
      const input = document.getElementById('userInput');
      const text = input.value.trim();
      if (!text) return;

      const chatBox = document.getElementById('chatBox');
      chatBox.innerHTML += `<div class="msg-user">${text}</div>`;
      input.value = '';
      chatBox.scrollTop = chatBox.scrollHeight;

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId })
      });
      const data = await res.json();
      sessionId = data.session_id;

      chatBox.innerHTML += `<div class="msg-agent">${data.response}</div>`;
      chatBox.scrollTop = chatBox.scrollHeight;
    }

    let geoDebounceTimer = null;
    function debounceGeoResolve() {
      clearTimeout(geoDebounceTimer);
      geoDebounceTimer = setTimeout(() => {
        resolveLocationNow();
      }, 400);
    }

    function setGeoLocation(val, btnEl) {
      clearTimeout(geoDebounceTimer);
      document.querySelectorAll('.quick-select-btn').forEach(b => b.classList.remove('active'));
      if (btnEl) {
        btnEl.classList.add('active');
      } else {
        const matchingBtn = document.querySelector(`.quick-select-btn[data-zip="${val}"]`);
        if (matchingBtn) matchingBtn.classList.add('active');
      }
      document.getElementById('geoInput').value = val;
      resolveLocationNow();
    }

    async function resolveLocationNow() {
      const q = document.getElementById('geoInput').value.trim();
      if (!q) return;

      const badge = document.getElementById('geoMatchBadge');
      badge.className = 'badge bg-warning text-dark';
      badge.innerText = 'Resolving...';

      try {
        const res = await fetch('/api/geo/resolve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q, state_code: 'NY', top_n: 3 })
        });
        const data = await res.json();
        if (data.status === 'success') {
          const loc = data.resolved_location;
          document.getElementById('tractGeoid').value = loc.census_tract_geoid;
          document.getElementById('geoResolvedText').innerHTML =
            `📍 <strong>Resolved:</strong> ${loc.display_name} · Tract <code>${loc.census_tract_geoid}</code>`;
          badge.className = 'badge bg-success';
          badge.innerText = data.match_type.replace('_', ' ');

          // Render closest screening centers list with instant map locator buttons
          const listDiv = document.getElementById('closestClinicsList');
          if (data.nearest_screening_clinics && data.nearest_screening_clinics.length > 0) {
            listDiv.innerHTML = data.nearest_screening_clinics.map((c, i) => `
              <div class="d-flex justify-content-between align-items-center py-1 border-bottom ${i === 0 ? 'bg-light px-1 rounded' : ''}">
                <div>
                  <strong>${i === 0 ? '⭐ ' : ''}${c.name.replace(' [Synthetic]', '')}</strong>
                  <div class="text-muted" style="font-size:0.7rem;">
                    Wait: ${c.internal_wait_days}d · ${c.bilingual_services_listed ? 'Bilingual ✅' : 'English only'} · ${c.accepts_medicaid ? 'Medicaid ✅' : 'No Medicaid'}
                  </div>
                </div>
                <div class="d-flex align-items-center gap-1">
                  <span class="badge bg-primary-subtle text-primary border">${c.distance_miles} mi</span>
                  <button type="button" class="btn btn-xs btn-outline-primary py-0 px-2 rounded-pill" onclick="locateClinicOnMap(${c.latitude || 40.81}, ${c.longitude || -73.92}, '${c.name.replace(/'/g, "\\'")}')" title="Locate on Map">
                    <i class="fa-solid fa-location-crosshairs"></i>
                  </button>
                </div>
              </div>
            `).join('');
          }

          // Pan/Zoom Leaflet map smoothly to resolved location
          const m = leafletMap || window.leafletMap;
          if (m && loc.latitude && loc.longitude) {
            m.flyTo([loc.latitude, loc.longitude], 12, { animate: true, duration: 0.8 });
            setTimeout(() => m.invalidateSize(), 150);
          }

          // Run pathway triage automatically
          runTriage();
        } else {
          currentTriageRequestId++;
          window.currentTriagePathway = null;
          // Explicit error handling for out-of-state ZIP / Tract / City or unrecognized location
          const errCode = data.error_code || 'LOCATION_ERROR';
          badge.className = 'badge bg-danger';
          badge.innerText = errCode === 'OUT_OF_STATE_ZIP' ? 'Outside NY State' :
                            errCode === 'OUT_OF_STATE_TRACT' ? 'Non-NY Census Tract' :
                            errCode === 'OUT_OF_STATE_CITY' ? 'Outside NY State' : 'Not Found in NY';

          document.getElementById('geoResolvedText').innerHTML =
            `<div class="alert alert-danger p-2 mb-0 mt-1 small">
              <i class="fa-solid fa-triangle-exclamation me-1"></i>
              <strong>Out of Jurisdiction:</strong> ${data.message || 'Location could not be verified in New York State.'}
            </div>`;

          const listDiv = document.getElementById('closestClinicsList');
          if (listDiv) {
            listDiv.innerHTML = `
              <div class="p-2 text-danger small">
                <i class="fa-solid fa-ban me-1"></i>
                <strong>No NY screening clinics:</strong> Location is outside New York IDEA Part C jurisdiction (FIPS 36).
              </div>
            `;
          }

          const triageRes = document.getElementById('triageResult');
          if (triageRes) {
            triageRes.innerHTML = `
              <div class="alert alert-warning p-3 small mb-0">
                <h6 class="alert-heading fw-bold mb-1"><i class="fa-solid fa-shield-halved text-warning me-1"></i>Routing Suspended: Out-of-State Jurisdiction</h6>
                <div>${data.message || 'Entered location is outside New York State.'}</div>
                <div class="mt-2 text-muted">Please enter a valid 5-digit New York ZIP code (10001–14925), New York city/borough, or an 11-digit NY Census Tract GEOID (beginning with 36).</div>
              </div>
            `;
          }

          const graphCard = document.getElementById('triageGraphCard');
          if (graphCard) graphCard.style.display = 'none';
        }
      } catch (err) {
        badge.className = 'badge bg-danger';
        badge.innerText = 'Resolve Error';
        console.warn('Geo resolve failed:', err);
      }
    }

    const UI_TRANSLATIONS = {
      en: {
        triageTitle: '<i class="fa-solid fa-compass text-primary me-2"></i>Today&#39;s Referral Navigator',
        statutoryClock: 'Statutory Clock: 45 Days',
        description: 'Enter the child&#39;s natural geographic location (ZIP Code, City, or Census Tract GEOID) to resolve nearest screening centers and calculate a guaranteed &le;45d IDEA Part C pathway.',
        geoLabel: '<i class="fa-solid fa-map-location-dot text-danger me-1"></i>Location (ZIP, City, or Census GEOID)',
        geoPlaceholder: 'e.g. 10451, Bronx, Jamestown, Lockport, or 36005019700',
        quickSelect: 'Quick Select:',
        tractLabel: 'Census Tract GEOID',
        closestTitle: '🏥 Nearest Screening Centers',
        closestSubtitle: 'Live Spatial Radius',
        childAgeLabel: 'Child Age (Months)',
        childAgeHelp: 'Part C Cliff: 36 Months (Urgent alert triggers at 30+ months)',
        reqMedicaid: 'Requires Medicaid Acceptance',
        reqBilingual: 'Requires Bilingual Evaluator (Spanish)',
        bilingualActive: '<i class="fa-solid fa-language me-1"></i>Bilingual Spanish Mandate Active',
        bilingualInactive: '<i class="fa-solid fa-globe me-1"></i>Standard Monolingual / English Capacity',
        bilingualNoticeActive: 'Locks pathway to verified bilingual evaluation hubs (Lockport NY-019). Toggle off to allow standard English/monolingual hubs.',
        bilingualNoticeInactive: 'Allows standard regional evaluation hubs without Spanish specialization requirement.',
        btnCalculate: '<i class="fa-solid fa-route me-1"></i> Calculate Compliant Pathway (&le; 45d)',
        resultPrompt: 'Click above or toggle any switch to calculate optimal graph routing.',
        chatWelcome: `👋 <strong>Hello Coordinator! I am Maya, your Milestone Navigator.</strong><br><br>I partner with you to ensure every infant and toddler reaches their developmental evaluation well within the federal 45-day statutory IFSP clock.<br><br><strong>How can I assist today's casework?</strong><br>• <strong>Natural Location Triage:</strong> <em>"Route a 22-month-old Spanish-speaking Medicaid toddler living in ZIP 10451."</em><br>• <strong>Age Cliff Escalation:</strong> <em>"We just received a 32-month-old referral in Canton. What is the emergency fast-track sequence before they age out at 36 months?"</em><br>• <strong>Caregiver Action Notes:</strong> <em>"Draft bilingual English and Spanish family action notes for the Rivera family and toddler Mateo."</em><br>• <strong>Pre-Handoff Quality Audit:</strong> <em>"Check if referral packet for 22m Spanish toddler to coordinator SYN-PROV-NY-011 will bounce."</em><br>• <strong>Transit Check:</strong> <em>"Does Bronx tract 36005019700 trigger the zero-vehicle transit guardrail?"</em>`,
        chatPlaceholder: 'Ask Maya (e.g. Find a pathway for a 20-month-old in ZIP 10451 on Medicaid)...',
        btnSend: '<i class="fa-solid fa-paper-plane me-1"></i> Send',
        chatPromptsLabel: '<i class="fa-solid fa-bolt text-warning me-1"></i>Casework Prompts:'
      },
      es: {
        triageTitle: '<i class="fa-solid fa-compass text-primary me-2"></i>Navegador de Derivaciones de Hoy',
        statutoryClock: 'Reloj Legal: 45 Días',
        description: 'Ingrese la ubicación geográfica del menor (Código Postal, Ciudad o GEOID de Tracto Censal) para ubicar los centros de detección más cercanos y calcular una ruta garantizada de &le;45 días de IDEA Parte C.',
        geoLabel: '<i class="fa-solid fa-map-location-dot text-danger me-1"></i>Ubicación (Código Postal, Ciudad o GEOID)',
        geoPlaceholder: 'ej. 10451, El Bronx, Jamestown, Lockport o 36005019700',
        quickSelect: 'Selección Rápida:',
        tractLabel: 'GEOID de Tracto Censal (11 dígitos)',
        closestTitle: '🏥 Centros de Detección Más Cercanos',
        closestSubtitle: 'Radio Espacial en Vivo',
        childAgeLabel: 'Edad del Menor (Meses)',
        childAgeHelp: 'Límite Parte C: 36 Meses (Alerta urgente para 30+ meses)',
        reqMedicaid: 'Requiere Aceptación de Medicaid',
        reqBilingual: 'Requiere Evaluador Bilingüe (Español)',
        bilingualActive: '<i class="fa-solid fa-language me-1"></i>Mandato Bilingüe en Español Activo',
        bilingualInactive: '<i class="fa-solid fa-globe me-1"></i>Capacidad Estándar en Inglés / Monolingüe',
        bilingualNoticeActive: 'Restringe la ruta a centros de evaluación bilingües certificados (Lockport NY-019). Desactive para permitir centros generales en inglés.',
        bilingualNoticeInactive: 'Permite centros de evaluación regionales estándar sin requisito de español.',
        btnCalculate: '<i class="fa-solid fa-route me-1"></i> Calcular Ruta Conforme (&le; 45d)',
        resultPrompt: 'Haga clic arriba o active cualquier opción para calcular el enrutamiento óptimo.',
        chatWelcome: `👋 <strong>¡Hola Coordinador(a)! Soy Maya, su Navegadora de Hitos del Desarrollo.</strong><br><br>Colaboro con usted para garantizar que cada lactante y niño pequeño complete su evaluación del desarrollo dentro del plazo legal federal de 45 días para el IFSP (34 CFR § 303.310).<br><br><strong>¿Cómo puedo asistirle en los casos de hoy?</strong><br>• <strong>Enrutamiento Geográfico:</strong> <em>"Ruta para un niño de 22 meses que habla español con Medicaid en el código postal 10451."</em><br>• <strong>Urgencia Límite de 36 Meses:</strong> <em>"Recibimos una derivación de 32 meses en Canton. ¿Cuál es la ruta de emergencia antes de que cumpla 36 meses?"</em><br>• <strong>Notas Bilingües para la Familia:</strong> <em>"Redactar nota bilingüe en inglés y español para la familia Rivera y el niño Mateo."</em><br>• <strong>Auditoría Pre-Derivación:</strong> <em>"Verificar si el paquete para el coordinador SYN-PROV-NY-011 será rechazado por fax."</em><br>• <strong>Tránsito y SDOH:</strong> <em>"¿El tracto 36005019700 del Bronx activa la regla de transporte sin vehículo?"</em>`,
        chatPlaceholder: 'Pregunte a Maya (ej. Buscar una ruta para un niño de 22 meses en CP 10451 con Medicaid)...',
        btnSend: '<i class="fa-solid fa-paper-plane me-1"></i> Enviar',
        chatPromptsLabel: '<i class="fa-solid fa-bolt text-warning me-1"></i>Consultas Rápidas:'
      }
    };

    let currentInterfaceLang = 'en';
    let currentGraphLang = 'en';

    function setInterfaceLanguage(lang) {
      currentInterfaceLang = lang;
      currentGraphLang = lang;

      const btnEn = document.getElementById('btnLangEn');
      const btnEs = document.getElementById('btnLangEs');
      if (btnEn) btnEn.className = lang === 'en' ? 'btn btn-xs btn-primary active py-0 px-2 fw-semibold' : 'btn btn-xs btn-outline-primary py-0 px-2 fw-semibold';
      if (btnEs) btnEs.className = lang === 'es' ? 'btn btn-xs btn-primary active py-0 px-2 fw-semibold' : 'btn btn-xs btn-outline-primary py-0 px-2 fw-semibold';

      // Update Graph Lang buttons too
      const btnGEn = document.getElementById('btnGraphLangEn');
      const btnGEs = document.getElementById('btnGraphLangEs');
      if (btnGEn) btnGEn.className = lang === 'en' ? 'btn btn-xs btn-primary active py-0 px-2 fw-bold' : 'btn btn-xs btn-outline-secondary py-0 px-2 fw-bold';
      if (btnGEs) btnGEs.className = lang === 'es' ? 'btn btn-xs btn-primary active py-0 px-2 fw-bold' : 'btn btn-xs btn-outline-secondary py-0 px-2 fw-bold';

      const t = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS.en;
      if (document.getElementById('triageCardTitle')) document.getElementById('triageCardTitle').innerHTML = t.triageTitle;
      if (document.getElementById('triageStatutoryClockBadge')) document.getElementById('triageStatutoryClockBadge').innerText = t.statutoryClock;
      if (document.getElementById('triageDescriptionText')) document.getElementById('triageDescriptionText').innerHTML = t.description;
      if (document.getElementById('geoInputLabel')) document.getElementById('geoInputLabel').innerHTML = t.geoLabel;
      if (document.getElementById('geoInput')) document.getElementById('geoInput').placeholder = t.geoPlaceholder;
      if (document.getElementById('quickSelectLabel')) document.getElementById('quickSelectLabel').innerText = t.quickSelect;
      if (document.getElementById('tractGeoidLabel')) document.getElementById('tractGeoidLabel').innerText = t.tractLabel;
      if (document.getElementById('closestClinicsTitle')) document.getElementById('closestClinicsTitle').innerText = t.closestTitle;
      if (document.getElementById('closestClinicsSubtitle')) document.getElementById('closestClinicsSubtitle').innerText = t.closestSubtitle;
      if (document.getElementById('childAgeLabel')) document.getElementById('childAgeLabel').innerText = t.childAgeLabel;
      if (document.getElementById('childAgeHelp')) document.getElementById('childAgeHelp').innerText = t.childAgeHelp;
      if (document.getElementById('reqMedicaidLabel')) document.getElementById('reqMedicaidLabel').innerText = t.reqMedicaid;
      if (document.getElementById('reqBilingualLabel')) document.getElementById('reqBilingualLabel').innerText = t.reqBilingual;
      if (document.getElementById('btnCalculatePathway')) document.getElementById('btnCalculatePathway').innerHTML = t.btnCalculate;
      if (document.getElementById('userInput')) document.getElementById('userInput').placeholder = t.chatPlaceholder;
      if (document.getElementById('btnSendMessage')) document.getElementById('btnSendMessage').innerHTML = t.btnSend;
      if (document.getElementById('chatPromptsLabel')) document.getElementById('chatPromptsLabel').innerHTML = t.chatPromptsLabel;

      const reqBi = document.getElementById('reqBilingual') ? document.getElementById('reqBilingual').checked : true;
      const badge = document.getElementById('bilingualBadge');
      const notice = document.getElementById('bilingualNoticeText');
      if (badge) badge.innerHTML = reqBi ? t.bilingualActive : t.bilingualInactive;
      if (notice) notice.innerText = reqBi ? t.bilingualNoticeActive : t.bilingualNoticeInactive;

      // Update welcome message if chat hasn't had messages
      const chatBox = document.getElementById('chatBox');
      const welcome = document.getElementById('chatWelcomeMsg');
      if (welcome && chatBox && chatBox.children.length === 1) {
        welcome.innerHTML = t.chatWelcome;
      }

      // Re-render pathway graph if child pathway is loaded
      if (window.currentTriagePathway) {
        renderPathwayGraph(window.currentTriagePathway);
      }
    }

    function setGraphLanguage(lang) {
      currentGraphLang = lang;
      const btnEn = document.getElementById('btnGraphLangEn');
      const btnEs = document.getElementById('btnGraphLangEs');
      if (btnEn) btnEn.className = lang === 'en' ? 'btn btn-xs btn-primary active py-0 px-2 fw-bold' : 'btn btn-xs btn-outline-secondary py-0 px-2 fw-bold';
      if (btnEs) btnEs.className = lang === 'es' ? 'btn btn-xs btn-primary active py-0 px-2 fw-bold' : 'btn btn-xs btn-outline-secondary py-0 px-2 fw-bold';
      if (window.currentTriagePathway) {
        renderPathwayGraph(window.currentTriagePathway);
      }
    }

    function handleBilingualToggle() {
      const reqBi = document.getElementById('reqBilingual').checked;
      const t = UI_TRANSLATIONS[currentInterfaceLang] || UI_TRANSLATIONS.en;
      const badge = document.getElementById('bilingualBadge');
      const notice = document.getElementById('bilingualNoticeText');
      if (reqBi) {
        if (badge) { badge.innerHTML = t.bilingualActive; badge.style.background = '#7c3aed'; }
        if (notice) notice.innerText = t.bilingualNoticeActive;
      } else {
        if (badge) { badge.innerHTML = t.bilingualInactive; badge.style.background = '#64748b'; }
        if (notice) notice.innerText = t.bilingualNoticeInactive;
      }
      runTriage();
    }

    function insertPrompt(text) {
      const el = document.getElementById('userInput');
      if (el) {
        el.value = text;
        el.focus();
      }
    }

    function renderPathwayGraph(p) {
      const card = document.getElementById('triageGraphCard');
      const svg = document.getElementById('svgTriagePathway');
      if (!p || !card || !svg) return;

      card.style.display = 'block';

      const isEs = currentGraphLang === 'es';

      // Update card title and map button in graph header
      const graphTitle = document.getElementById('triageGraphTitle');
      if (graphTitle) {
        graphTitle.innerHTML = isEs
          ? '<i class="fa-solid fa-diagram-project text-info me-2"></i> Mapa de Flujo de Agentes — Derivación de Cuidados'
          : '<i class="fa-solid fa-diagram-project text-info me-2"></i> Agent Flow Map — Care Pathway Handoffs';
      }
      const btnMap = document.getElementById('btnGraphViewMap');
      if (btnMap) {
        btnMap.innerHTML = isEs
          ? '<i class="fa-solid fa-location-crosshairs me-1"></i> Ver en el Mapa'
          : '<i class="fa-solid fa-location-crosshairs me-1"></i> View on Map';
      }

      svg.setAttribute('viewBox', '0 0 540 330');

      // 4 stages arranged VERTICALLY from top to bottom
      const nodes = [
        { label: isEs ? "Clínica de Detección" : "Screening Clinic", step: isEs ? "Paso 1" : "Stage 1", name: p.screening_clinic.replace(' [Synthetic]', ''), days: p.clinic_wait, y: 38, color: "#7dd3fc" },
        { label: isEs ? "Coordinador Parte C" : "Part C Coordinator", step: isEs ? "Paso 2" : "Stage 2", name: p.intake_coordinator.replace(' [Synthetic]', ''), days: p.coord_wait, y: 104, color: "#fde047" },
        { label: isEs ? (p.eval_bilingual ? "Centro Eval. Bilingüe" : "Centro de Evaluación") : "Multidisc. Eval Hub", step: isEs ? "Paso 3" : "Stage 3", name: p.eval_hub.replace(' [Synthetic]', ''), days: p.eval_wait, y: 170, color: p.eval_bilingual ? "#c084fc" : "#93c5fd" },
        { label: isEs ? "Proveedor de Terapia" : "Direct Therapy Vendor", step: isEs ? "Paso 4" : "Stage 4", name: p.therapy_vendor.replace(' [Synthetic]', ''), days: p.vendor_wait, y: 236, color: "#86efac" }
      ];

      let svgHtml = `
        <defs>
          <marker id="arrow-flow-v" viewBox="0 0 10 10" refX="5" refY="8" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 0 0 L 10 0 L 5 8 z" fill="#38bdf8"/>
          </marker>
        </defs>
      `;

      // Draw vertical connector lines and hop badges between stages
      for (let i = 0; i < 3; i++) {
        const u = nodes[i];
        const v = nodes[i + 1];
        const midY = (u.y + v.y) / 2 + 3;
        const hopLabel = isEs ? `Salto EHR ${i + 1}` : `EHR Hop ${i + 1}`;
        svgHtml += `
          <line x1="42" y1="${u.y + 17}" x2="42" y2="${v.y - 17}" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow-flow-v)"/>
          <text x="56" y="${midY}" fill="#38bdf8" font-size="8.5" font-family="monospace" font-weight="bold">▼ ${hopLabel} (+${nodes[i].days}d)</text>
        `;
      }

      // Draw stage circles and stage info cards
      nodes.forEach((n, idx) => {
        svgHtml += `
          <g>
            <!-- Vertical Stage Circle -->
            <circle cx="42" cy="${n.y}" r="17" fill="${n.color}" stroke="#ffffff" stroke-width="2.2" filter="drop-shadow(0px 2px 4px rgba(0,0,0,0.4))"/>
            <text x="42" y="${n.y + 4}" fill="#0f172a" font-size="10" font-weight="900" text-anchor="middle">${idx + 1}</text>

            <!-- Stage Card -->
            <rect x="70" y="${n.y - 21}" width="455" height="42" rx="8" fill="#1e293b" stroke="${n.color}" stroke-width="1.2"/>
            <text x="84" y="${n.y - 5}" fill="${n.color}" font-size="9.5" font-weight="bold">${n.step} · ${n.label}</text>
            <text x="84" y="${n.y + 12}" fill="#f8fafc" font-size="10.5" font-weight="600">${n.name.substring(0, 42)}</text>
            
            <!-- Wait Days Badge -->
            <rect x="440" y="${n.y - 13}" width="72" height="24" rx="6" fill="#0f172a" stroke="#38bdf8" stroke-width="1"/>
            <text x="476" y="${n.y + 3}" fill="#38bdf8" font-size="10" font-family="monospace" font-weight="bold" text-anchor="middle">+${n.days}d</text>
          </g>
        `;
      });

      // Total clock summary tag at bottom
      const clockSummary = isEs
        ? `❤️ Protección de Plazo Legal 45d: ${p.total_estimated_wait_days} Días (${45 - p.total_estimated_wait_days}d bajo el límite)`
        : `❤️ 45-Day Statutory Protection: ${p.total_estimated_wait_days} Total Days (${45 - p.total_estimated_wait_days}d under federal limit)`;
      svgHtml += `
        <rect x="18" y="278" width="504" height="34" rx="8" fill="#064e3b" stroke="#34d399" stroke-width="1.5"/>
        <text x="270" y="299" fill="#ecfdf5" font-size="10.8" font-weight="bold" text-anchor="middle">${clockSummary}</text>
      `;

      svg.innerHTML = svgHtml;
    }

    function centerMapOnCurrentPathway() {
      activateTrack(5);
      setTimeout(() => {
        const m = leafletMap || window.leafletMap;
        if (m) {
          const mapEl = document.getElementById('nyPhysicalMap');
          if (mapEl) {
            mapEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
          const geoid = document.getElementById('tractGeoid') ? document.getElementById('tractGeoid').value.trim() : '';
          if (geoid.startsWith('36005')) {
            zoomMapRegion('bronx');
          } else if (geoid.startsWith('36089') || geoid.startsWith('36063')) {
            zoomMapRegion('catskills');
          } else {
            zoomMapRegion('state');
          }
          m.invalidateSize();
        }
      }, 100);
    }

    let currentTriageRequestId = 0;

    async function runTriage() {
      const geoid = document.getElementById('tractGeoid') ? document.getElementById('tractGeoid').value.trim() : '';
      if (!geoid || !geoid.startsWith('36')) {
        const graphCard = document.getElementById('triageGraphCard');
        if (graphCard) graphCard.style.display = 'none';
        return;
      }

      const reqId = ++currentTriageRequestId;
      const resultDiv = document.getElementById('triageResult');
      resultDiv.innerHTML = '<div class="text-center py-2"><i class="fa-solid fa-spinner fa-spin me-1"></i> Computing optimal graph pathway...</div>';

      const payload = {
        child_age_months: parseInt(document.getElementById('childAge').value),
        census_tract_geoid: geoid,
        requires_medicaid: document.getElementById('reqMedicaid').checked,
        requires_bilingual: document.getElementById('reqBilingual').checked,
        max_wait_days: 45
      };

      try {
        const res = await fetch('/api/triage/route', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (reqId !== currentTriageRequestId) return;

        if (data.recommended_pathways && data.recommended_pathways.length > 0) {
          const p = data.recommended_pathways[0];
          let alertHtml = '';
          if (data.age_warning) {
            alertHtml += `<div class="alert alert-danger p-2 mb-2">${data.age_warning}</div>`;
          }
          if (data.zero_vehicle_travel_guardrail && data.zero_vehicle_travel_guardrail.alert) {
            alertHtml += `<div class="alert alert-warning p-2 mb-2">🚐 <strong>${data.zero_vehicle_travel_guardrail.alert}</strong></div>`;
          }
          window.currentTriagePathway = p;
          const isEs = currentInterfaceLang === 'es';
          resultDiv.innerHTML = `
            ${alertHtml}
            <div class="border rounded p-2 bg-light mb-2">
              <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="fw-bold text-success"><i class="fa-solid fa-circle-check me-1"></i>${isEs ? `Ruta Conforme: ${p.total_estimated_wait_days} Días Totales` : `Compliant Pathway: ${p.total_estimated_wait_days} Total Days`}</span>
                <span class="badge bg-success">&le; 45d ${isEs ? 'Reloj Federal' : 'Federal Clock'}</span>
              </div>
              <ol class="ps-3 mt-1 mb-2" style="font-size:0.8rem;">
                <li><strong>${isEs ? 'Clínica' : 'Clinic'}:</strong> ${p.screening_clinic} (${p.clinic_wait}d)</li>
                <li><strong>${isEs ? 'Coordinador Parte C' : 'Coordinator'}:</strong> ${p.intake_coordinator} (${p.coord_wait}d)</li>
                <li><strong>${isEs ? 'Centro de Evaluación' : 'Eval Hub'}:</strong> ${p.eval_hub} (${p.eval_wait}d, ${isEs ? 'Bilingüe' : 'Bilingual'}: ${p.eval_bilingual ? (isEs ? 'Sí' : 'Yes') : 'No'})</li>
                <li><strong>${isEs ? 'Proveedor de Terapia' : 'Therapy Vendor'}:</strong> ${p.therapy_vendor} (${p.vendor_wait}d)</li>
              </ol>
              <div class="small text-muted mb-2">
                <strong>${isEs ? 'Proximidad de Tránsito' : 'Transit Proximity'}:</strong> ${p.total_travel_miles || '7.2'} ${isEs ? 'millas totales' : 'total route miles'}
              </div>
              <button type="button" class="btn btn-sm btn-outline-primary w-100 fw-bold" onclick="showCaregiverModal()">
                <i class="fa-solid fa-file-signature me-1"></i> ${isEs ? 'Ver / Imprimir Nota Bilingüe para la Familia (EN/ES)' : 'View / Print Bilingual Caregiver Action Note (EN/ES)'}
              </button>
            </div>
          `;

          // Render the 4-stage handoff SVG graph
          renderPathwayGraph(p);
        } else {
          const graphCard = document.getElementById('triageGraphCard');
          if (graphCard) graphCard.style.display = 'none';
          resultDiv.innerHTML = `
            ${data.age_warning ? `<div class="alert alert-danger p-2 mb-2">${data.age_warning}</div>` : ''}
            <span class="text-danger fw-bold">No Part C pathway available.</span>
            ${data.part_b_preschool_transition ? `<div class="alert alert-info p-2 mt-2"><strong>${data.part_b_preschool_transition.mandate}:</strong> ${data.part_b_preschool_transition.required_action}</div>` : ''}
          `;
        }

        // Update Multi-Agent Execution Breakdown
        if (data.agent_breakdown) {
          renderAgentExecutionBreakdown(data.agent_breakdown, data.trace_id);
        }
      } catch (err) {
        resultDiv.innerHTML = `<span class="text-danger">Routing failed: ${err.message}</span>`;
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function renderAgentExecutionBreakdown(breakdown, traceId) {
      if (!breakdown) return;

      const tId = traceId || breakdown.trace_id;
      if (tId) {
        const badge = document.getElementById('triageTraceIdBadge');
        if (badge) {
          badge.innerText = tId.substring(0, 13) + '...';
          badge.title = tId;
        }
      }

      const agents = breakdown.agents || [];
      // Agent 1: pathway_router_agent
      if (agents[0]) {
        const a1 = agents[0];
        const statusEl = document.getElementById('agent1StatusBadge');
        if (statusEl) {
          statusEl.innerText = a1.status;
          statusEl.className = a1.status === 'COMPLETED'
            ? 'badge bg-success-subtle text-success border border-success-subtle'
            : 'badge bg-warning-subtle text-warning border border-warning-subtle';
        }
        const latEl = document.getElementById('agent1Latency');
        if (latEl) latEl.innerText = (a1.latency_ms || 0) + 'ms';
        const hopEl = document.getElementById('agent1ResultHop');
        if (hopEl && a1.output && a1.output.total_estimated_wait_days) {
          hopEl.innerText = a1.output.total_estimated_wait_days + 'd Total Wait';
        }
        const listEl = document.getElementById('agent1ActionsList');
        if (listEl && a1.decisions) {
          listEl.innerHTML = a1.decisions.map(d => `<li>${escapeHtml(d)}</li>`).join('');
        }
      }

      // Agent 2: network_audit_agent
      if (agents[1]) {
        const a2 = agents[1];
        const statusEl = document.getElementById('agent2StatusBadge');
        if (statusEl) {
          statusEl.innerText = a2.status;
          statusEl.className = a2.status === 'COMPLETED'
            ? 'badge bg-success-subtle text-success border border-success-subtle'
            : 'badge bg-warning-subtle text-warning border border-warning-subtle';
        }
        const latEl = document.getElementById('agent2Latency');
        if (latEl) latEl.innerText = (a2.latency_ms || 0) + 'ms';
        const packetEl = document.getElementById('agent2PacketStatus');
        if (packetEl && a2.output) {
          packetEl.innerText = a2.output.packet_validation_status || 'Packet Validated';
        }
        const listEl = document.getElementById('agent2ActionsList');
        if (listEl && a2.decisions) {
          listEl.innerHTML = a2.decisions.map(d => `<li>${escapeHtml(d)}</li>`).join('');
        }
      }

      // Agent 3: equity_audit_agent
      if (agents[2]) {
        const a3 = agents[2];
        const statusEl = document.getElementById('agent3StatusBadge');
        if (statusEl) {
          statusEl.innerText = a3.status;
          statusEl.className = a3.status === 'COMPLETED'
            ? 'badge bg-success-subtle text-success border border-success-subtle'
            : 'badge bg-warning-subtle text-warning border border-warning-subtle';
        }
        const latEl = document.getElementById('agent3Latency');
        if (latEl) latEl.innerText = (a3.latency_ms || 0) + 'ms';
        const transEl = document.getElementById('agent3TransitStatus');
        if (transEl && a3.output) {
          transEl.innerText = a3.output.transit_guardrail_triggered ? 'Transit Van Req.' : 'Transit Normal';
        }
        const listEl = document.getElementById('agent3ActionsList');
        if (listEl && a3.decisions) {
          listEl.innerHTML = a3.decisions.map(d => `<li>${escapeHtml(d)}</li>`).join('');
        }
      }

      // Agent 4: caregiver_note_agent
      if (agents[3]) {
        const a4 = agents[3];
        const statusEl = document.getElementById('agent4StatusBadge');
        if (statusEl) {
          statusEl.innerText = a4.status;
          statusEl.className = a4.status === 'COMPLETED'
            ? 'badge bg-success-subtle text-success border border-success-subtle'
            : 'badge bg-warning-subtle text-warning border border-warning-subtle';
        }
        const latEl = document.getElementById('agent4Latency');
        if (latEl) latEl.innerText = (a4.latency_ms || 0) + 'ms';
        const noteEl = document.getElementById('agent4NoteStatus');
        if (noteEl && a4.output) {
          noteEl.innerText = (a4.output.languages_generated || ['English', 'Spanish']).join('/') + ' Ready';
        }
        const listEl = document.getElementById('agent4ActionsList');
        if (listEl && a4.decisions) {
          listEl.innerHTML = a4.decisions.map(d => `<li>${escapeHtml(d)}</li>`).join('');
        }
      }
    }

    // BigQuery traces are logged directly on the backend during multi-agent triage execution.

    async function showCaregiverModal() {
      const p = window.currentTriagePathway;
      if (!p) return;
      try {
        const res = await fetch('/api/caregiver/note', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            family_name: "Rivera",
            child_name: "Mateo",
            clinic_name: p.screening_clinic,
            coordinator_name: p.intake_coordinator,
            eval_hub_name: p.eval_hub,
            vendor_name: p.therapy_vendor,
            estimated_total_days: p.total_estimated_wait_days
          })
        });
        const noteData = await res.json();
        document.getElementById('caregiverNoteEn').innerText = noteData.english_note || '';
        document.getElementById('caregiverNoteEs').innerText = noteData.spanish_note || '';
        const modalEl = document.getElementById('caregiverModal');
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
      } catch (err) {
        console.error('Failed to load caregiver note:', err);
      }
    }

    async function loadEquityAuditData() {
      const tbody = document.getElementById('equityTableBody');
      if (!tbody) return;
      try {
        const res = await fetch('/api/audit/equity');
        const data = await res.json();
        if (data.post_output_equity_audit && data.post_output_equity_audit.length > 0) {
          tbody.innerHTML = data.post_output_equity_audit.map((row, idx) => {
            const povPct = (row.poverty_rate * 100).toFixed(1) + '%';
            const vehDeficit = (row.no_vehicle_rate * 100).toFixed(1) + '%';
            const isHighVeh = (row.no_vehicle_rate * 100) >= 15.0;
            const actionBadge = isHighVeh
              ? '<span class="badge bg-success">Tele-Assessment + NEMT</span>'
              : (idx === 0 ? '<span class="badge bg-primary">Community Screening Day 1</span>' :
                (idx === 1 ? '<span class="badge bg-primary">Community Screening Day 2</span>' :
                '<span class="badge bg-info text-dark">Mobile Eval Van</span>'));
            return `
              <tr>
                <td><code>${row.census_tract_geoid}</code></td>
                <td><strong>${row.county_name}</strong></td>
                <td><span class="badge bg-light text-dark border">${povPct}</span></td>
                <td>${isHighVeh ? `<span class="badge bg-warning text-dark">${vehDeficit} High Deficit</span>` : vehDeficit}</td>
                <td><span class="badge bg-danger">${row.avg_chain_wait_days} days</span></td>
                <td>${row.breached_chains} / ${row.total_chains}</td>
                <td>${actionBadge}</td>
              </tr>
            `;
          }).join('');
        }
      } catch (err) {
        console.warn('Could not load dynamic equity audit rows:', err);
      }
    }

    async function runNetworkSimulation() {
      const coordId = document.getElementById('simCoordSelect').value;
      await simulateHub(coordId);
    }

    async function simulateHub(coordId) {
      document.getElementById('simCoordSelect').value = coordId;
      document.getElementById('simSummaryText').innerHTML = '<em>Running graph simulation over referral chains...</em>';

      try {
        const res = await fetch(`/api/network/simulate?coordinator_id=${encodeURIComponent(coordId)}&state_code=NY`);
        const data = await res.json();
        if (data.status === 'success') {
          const t = data.target_coordinator;
          const pct = Math.round((t.breached_cases_dropped_under_45d / (t.originally_breached_chains || 1)) * 100);
          const execBanner = document.getElementById('simExecutiveSummary');
          if (execBanner) {
            execBanner.innerHTML = `Switching <strong>${t.coordinator_name}</strong> from <code>paper_fax</code> to <strong>electronic EHR intake</strong> with <strong>pre-checked bilingual evaluator slots</strong> rescues <strong>${t.breached_cases_dropped_under_45d} of ${t.originally_breached_chains} breached referral chains (${pct}%)</strong> directly under the 45-day federal IFSP statutory limit, saving <strong>${t.total_child_days_saved} delayed child-days</strong> and shifting statewide breaches ${t.statewide_breach_drop}.`;
          }
          document.getElementById('simStatOrig').innerText = `${t.originally_breached_chains} Cases (>45d)`;
          document.getElementById('simStatRescued').innerText = `${t.breached_cases_dropped_under_45d} Rescued (<=45d)`;
          document.getElementById('simStatState').innerText = t.statewide_breach_drop;
          document.getElementById('simStatDays').innerText = `${t.total_child_days_saved} Child-Days`;
          document.getElementById('simSummaryText').innerHTML = `<strong>Outcome:</strong> ${data.key_takeaway}`;

          const tbody = document.getElementById('simRankingTbody');
          if (data.all_coordinators_simulation_ranking) {
            tbody.innerHTML = data.all_coordinators_simulation_ranking.map(r => {
              const isTarget = r.coordinator_id === coordId;
              const residual = r.originally_breached - r.breaches_dropped_under_45d;
              return `
                <tr class="${isTarget ? 'table-primary' : ''}">
                  <td><strong>${r.coordinator_name}</strong></td>
                  <td><span class="badge bg-danger">${r.originally_breached} cases</span></td>
                  <td><span class="badge bg-success">${r.breaches_dropped_under_45d} cases dropped &le;45d</span></td>
                  <td>${residual} residual case${residual === 1 ? '' : 's'}</td>
                  <td><span class="text-success fw-bold">${r.child_days_saved} days</span></td>
                  <td>
                    ${isTarget ? '<span class="badge bg-primary">Active Target</span>' : `<button class="btn btn-xs btn-outline-secondary py-0 px-2 small" onclick="simulateHub('${r.coordinator_id}')">Simulate</button>`}
                  </td>
                </tr>
              `;
            }).join('');
          }
        }
      } catch (err) {
        document.getElementById('simSummaryText').innerHTML = `<span class="text-danger">Simulation failed: ${err.message}</span>`;
      }
    }
  </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), reload=False)
