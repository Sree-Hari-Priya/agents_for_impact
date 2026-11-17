"""
FastAPI Server for Early Intervention Triage & Network-Audit Agent.
Exposes REST endpoints for the ADK agent, graph analysis, pathway routing, and equity audits.
Includes an interactive dashboard web UI for IDEA Part C coordinators.
"""

import os
import sys
from typing import Optional, Dict, Any
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

    return {
        "session_id": session_id,
        "response": full_response
    }

@app.get("/api/graph/breaches")
def get_breaches(min_wait_days: int = 45, limit: int = 10, state_code: str = "NY"):
    return trace_45day_breaches_and_bounce_hubs(min_wait_days=min_wait_days, limit=limit, state_code=state_code)

@app.post("/api/triage/route")
def triage_route(req: TriageRequest):
    return find_compliant_toddler_pathway(
        child_age_months=req.child_age_months,
        census_tract_geoid=req.census_tract_geoid,
        requires_medicaid=req.requires_medicaid,
        requires_bilingual=req.requires_bilingual,
        max_wait_days=req.max_wait_days
    )

@app.get("/api/audit/equity")
def equity_audit():
    return run_equity_and_counterfactual_audit()

@app.get("/api/graph/map")
def get_map_graph(state_code: str = "NY"):
    return get_state_geospatial_graph_data(state_code=state_code)

@app.get("/", response_class=HTMLResponse)
def index():
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>First Milestones - Early Intervention Triage & Network Audit</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <script type="text/javascript" src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --primary-color: #1a73e8;
      --primary-dark: #0d47a1;
      --card-radius: 1rem;
    }
    body {
      background-color: #f1f5f9;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #1e293b;
    }
    .hero {
      background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #0369a1 100%);
      color: white;
      padding: 2.2rem 1.5rem 1.8rem;
      margin-bottom: 1.8rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
    }
    .card {
      border-radius: var(--card-radius);
      border: 1px solid rgba(226, 232, 240, 0.8);
      box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
      margin-bottom: 1.5rem;
      background: #ffffff;
    }
    .stat-badge {
      font-size: 1.65rem;
      font-weight: 800;
      letter-spacing: -0.5px;
    }
    .badge-breach { background-color: #ef4444; color: white; }
    .badge-pass { background-color: #10b981; color: white; }
    .chat-box {
      height: 420px;
      overflow-y: auto;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 0.75rem;
      padding: 1.2rem;
    }
    .msg-user {
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: #ffffff;
      border-radius: 0.85rem 0.85rem 0.2rem 0.85rem;
      padding: 0.75rem 1.1rem;
      margin-bottom: 0.75rem;
      max-width: 82%;
      margin-left: auto;
      box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);
    }
    .msg-agent {
      background-color: #ffffff;
      color: #0f172a;
      border: 1px solid #e2e8f0;
      border-radius: 0.85rem 0.85rem 0.85rem 0.2rem;
      padding: 0.75rem 1.1rem;
      margin-bottom: 0.75rem;
      max-width: 88%;
      white-space: pre-wrap;
      box-shadow: 0 2px 5px rgba(0, 0, 0, 0.04);
      line-height: 1.5;
    }
    .track-nav-btn {
      border-radius: 0.75rem !important;
      padding: 0.65rem 1.25rem;
      font-weight: 600;
      font-size: 0.92rem;
      transition: all 0.2s ease-in-out;
      border: 1px solid rgba(255, 255, 255, 0.3);
    }
    .track-nav-btn.active {
      background: #ffffff !important;
      color: #1e3a8a !important;
      box-shadow: 0 4px 12px rgba(0,0,0,0.18);
      transform: translateY(-1px);
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
      transition: transform 0.2s ease;
    }
    .kpi-card:hover {
      transform: translateY(-2px);
    }
    .table-custom th {
      background: #f8fafc;
      color: #475569;
      font-weight: 600;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .form-control, .form-select {
      border-radius: 0.5rem;
      border-color: #cbd5e1;
    }
    .form-control:focus, .form-select:focus {
      border-color: #3b82f6;
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
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
            style="width: 76px; height: 76px; object-fit: cover; border-radius: 50%; border: 3px solid rgba(255,255,255,0.85); box-shadow: 0 4px 10px rgba(0,0,0,0.2);"
          />
          <div>
            <div class="d-flex align-items-center gap-2 mb-1">
              <span class="badge bg-light text-primary fw-bold px-2 py-1">Challenge 04</span>
              <span class="badge bg-white bg-opacity-25 text-white">IDEA Part C Early Intervention &amp; Developmental Screening</span>
            </div>
            <h1 class="h2 mb-1 fw-bold">First Milestones: Triage &amp; Network-Audit</h1>
            <p class="mb-0 text-white-50 small">BigQuery Property Graph (ISO GQL) · Google ADK Agent · Vertex AI Gemini 2.5 Flash</p>
          </div>
        </div>
        <div class="text-end">
          <div class="btn-group btn-group-sm mb-1" role="group">
            <button id="btnStateNY" type="button" class="btn btn-warning fw-bold text-dark" onclick="setActiveState('NY')"><i class="fa-solid fa-map-pin me-1"></i> New York (NY)</button>
            <button id="btnStateMS" type="button" class="btn btn-outline-light" onclick="setActiveState('MS')"><i class="fa-solid fa-map-pin me-1"></i> Mississippi (MS)</button>
          </div>
          <div class="small mt-1 text-white-50">100% [Synthetic] Topology · Illustrative Media</div>
        </div>
      </div>

      <!-- Functional Track Navigation Switcher -->
      <div class="mt-4 pt-3 border-top border-white border-opacity-20 d-flex flex-wrap justify-content-between align-items-center gap-3">
        <div class="d-flex align-items-center gap-2">
          <span class="small text-uppercase fw-bold text-white-50 me-2"><i class="fa-solid fa-layer-group me-1"></i> Active View:</span>
          <div class="btn-group" role="group" aria-label="Track Navigation">
            <button id="btnTrack1" type="button" class="btn btn-sm btn-light track-nav-btn active" onclick="activateTrack(1)">
              <i class="fa-solid fa-compass me-1 text-primary"></i> Track 1: Today's Referral
            </button>
            <button id="btnTrack2" type="button" class="btn btn-sm btn-outline-light track-nav-btn" onclick="activateTrack(2)">
              <i class="fa-solid fa-network-wired me-1"></i> Track 2: This Quarter's Audit
            </button>
            <button id="btnTrack3" type="button" class="btn btn-sm btn-outline-light track-nav-btn" onclick="activateTrack(3)">
              <i class="fa-solid fa-van-shuttle me-1"></i> Track 3: Outreach Season
            </button>
          </div>
        </div>
        <div id="trackBannerInfo" class="small text-white bg-white bg-opacity-10 px-3 py-1 rounded-pill">
          <strong>Track 1:</strong> Route today's toddler referral (&le;45d compliant path with 36m age cliff guard).
        </div>
      </div>
    </div>
  </div>

  <div class="container pb-5">
    <!-- Top Summary Metrics (Executive Visibility Across All Tracks) -->
    <div class="row g-3 mb-4">
      <div class="col-6 col-lg-3">
        <div class="card p-3 text-center kpi-card h-100">
          <div class="stat-badge text-danger">26 / 35</div>
          <div class="text-muted small fw-semibold">Multi-Hop Chains Breaching 45d</div>
          <div class="text-secondary small mt-1" style="font-size:0.75rem;">Exposed by BigQuery ISO GQL</div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="card p-3 text-center kpi-card h-100">
          <div class="stat-badge text-primary">5 - 6 Days</div>
          <div class="text-muted small fw-semibold">Deceptive "Bounce Hub" Wait</div>
          <div class="text-secondary small mt-1" style="font-size:0.75rem;">Conceals downstream fax loops</div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="card p-3 text-center kpi-card h-100">
          <div class="stat-badge text-success">1,168 Days</div>
          <div class="text-muted small fw-semibold">Saved by Upgrading to EHR</div>
          <div class="text-secondary small mt-1" style="font-size:0.75rem;">100% breaches eliminated</div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="card p-3 text-center kpi-card h-100">
          <div class="stat-badge text-info">17 - 22 Days</div>
          <div class="text-muted small fw-semibold">Graph-Optimized Toddler Pathway</div>
          <div class="text-secondary small mt-1" style="font-size:0.75rem;">Guaranteed &le;45d IDEA Part C</div>
        </div>
      </div>
    </div>

    <!-- ========================================== -->
    <!-- TRACK 1 PANE: TODAY'S REFERRAL (TRIAGE & CHAT) -->
    <!-- ========================================== -->
    <div id="trackPane1" class="track-pane active">
      <div class="row g-4">
        <!-- Quick Triage Routing Panel -->
        <div class="col-lg-5">
          <div class="card p-4 h-100">
            <div class="d-flex align-items-center justify-content-between mb-3">
              <h5 class="card-title mb-0 fw-bold"><i class="fa-solid fa-sliders text-primary me-2"></i>Triage &amp; Route Optimizer</h5>
              <span class="badge bg-primary-subtle text-primary border border-primary-subtle">Statutory Clock: 45 Days</span>
            </div>
            <p class="text-muted small mb-3">
              Verify local provider capacity, bilingual evaluator availability, Medicaid acceptance, and the zero-vehicle transit guardrail before placing referral.
            </p>

            <div class="row g-2 mb-3">
              <div class="col-6">
                <label class="form-label small fw-semibold mb-1">Child Age (Months)</label>
                <input type="number" id="childAge" class="form-control" value="22" min="1" max="35">
                <span class="text-muted" style="font-size:0.72rem;">Part C Cliff: 36 Months</span>
              </div>
              <div class="col-6">
                <label class="form-label small fw-semibold mb-1">Census Tract GEOID</label>
                <input type="text" id="tractGeoid" class="form-control" value="36005019700">
                <span class="text-muted" style="font-size:0.72rem;">NY: 36005019700 · MS: 28083950200</span>
              </div>
            </div>

            <div class="p-3 bg-light rounded-3 mb-3 border">
              <div class="form-check form-switch mb-2">
                <input class="form-check-input" type="checkbox" id="reqMedicaid" checked>
                <label class="form-check-label small fw-semibold" for="reqMedicaid">Requires Medicaid Acceptance</label>
              </div>
              <div class="form-check form-switch mb-0">
                <input class="form-check-input" type="checkbox" id="reqBilingual" checked>
                <label class="form-check-label small fw-semibold" for="reqBilingual">Requires Bilingual Evaluator (Spanish)</label>
              </div>
            </div>

            <button class="btn btn-primary w-100 fw-semibold py-2 mb-3" onclick="runTriage()">
              <i class="fa-solid fa-route me-1"></i> Calculate Compliant Pathway (&le; 45d)
            </button>

            <div id="triageResult" class="small text-muted border rounded p-3 bg-white" style="min-height: 120px;">
              <div class="text-center py-3 text-secondary">
                <i class="fa-regular fa-circle-question fa-2x mb-2 text-muted"></i>
                <div>Click above to calculate optimal graph routing.</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Live ADK Agent Interaction -->
        <div class="col-lg-7">
          <div class="card p-4 h-100">
            <div class="d-flex align-items-center justify-content-between mb-3">
              <h5 class="card-title mb-0 fw-bold"><i class="fa-solid fa-robot text-primary me-2"></i>ADK Coordinator Casework Assistant</h5>
              <span class="badge bg-success-subtle text-success border border-success-subtle"><i class="fa-solid fa-circle text-success me-1" style="font-size: 7px;"></i>Agent Ready</span>
            </div>
            <div id="chatBox" class="chat-box mb-3">
              <div class="msg-agent">👋 <strong>Hello Coordinator.</strong> I am your AI Early Intervention Assistant powered by Google ADK and BigQuery Property Graph.

I can help you resolve today's intake bottlenecks immediately:
• <strong>Compliant Routing:</strong> "Route a 22-month-old Spanish-speaking Medicaid toddler near tract 36005019700."
• <strong>Caregiver Notes:</strong> "Generate bilingual caregiver action notes for the Rivera family and toddler Mateo."
• <strong>Transit Check:</strong> "Does tract 28083950200 trigger the zero-vehicle transit guardrail?"</div>
            </div>
            <div class="input-group">
              <input type="text" id="userInput" class="form-control py-2" placeholder="Ask your question (e.g. Find a <=45d path for today's toddler)..." onkeydown="if(event.key==='Enter') sendMessage()">
              <button class="btn btn-primary px-4 fw-semibold" onclick="sendMessage()"><i class="fa-solid fa-paper-plane me-1"></i> Send</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ========================================== -->
    <!-- TRACK 2 PANE: THIS QUARTER'S AUDIT -->
    <!-- ========================================== -->
    <div id="trackPane2" class="track-pane">
      <!-- ReferralGraph Side-by-Side SVG Clock -->
      <div class="row mb-4">
        <div class="col-12">
          <div class="card p-4">
            <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
              <div>
                <h5 id="graphCardTitle" class="card-title mb-1 fw-bold"><i class="fa-solid fa-clock-rotate-left text-danger me-2"></i>ReferralGraph Side-by-Side Pathway &amp; 45-Day Statutory Clock</h5>
                <p id="graphCardSubtitle" class="text-muted small mb-0">
                  Comparing multi-hop paper-fax bounce loops vs. electronic e-referral routes from the same regional coordinator desk.
                </p>
              </div>
              <div class="btn-group btn-group-sm" role="group">
                <button id="btn-mode-both" type="button" class="btn btn-primary active" onclick="setSvgGraphMode('both')">Compare Bounce vs. &le;45d Route</button>
                <button id="btn-mode-bounce" type="button" class="btn btn-outline-danger" onclick="setSvgGraphMode('bounce')">🚨 4-Hop Fax Bounce</button>
                <button id="btn-mode-eval" type="button" class="btn btn-outline-success" onclick="setSvgGraphMode('eval')">✅ 3-Hop E-Referral</button>
                <button id="btn-mode-fast" type="button" class="btn btn-outline-info" onclick="setSvgGraphMode('fast')">⚡ 2-Hop Fast-Track</button>
              </div>
            </div>

            <div class="p-3 rounded-3 border mb-3" style="background-color: #0f172a; color: #f8fafc; box-shadow: inset 0 2px 6px rgba(0,0,0,0.4);">
              <svg id="svgReferralGraph" viewBox="0 0 760 235" style="width:100%; height:auto; display:block;"></svg>
            </div>
            <div id="svgClockCards" class="row g-3 mb-0"></div>
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
    <!-- TRACK 3 PANE: OUTREACH SEASON -->
    <!-- ========================================== -->
    <div id="trackPane3" class="track-pane">
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
                <div class="border rounded-3 p-3 bg-light h-100">
                  <div class="d-flex align-items-center gap-2 mb-2">
                    <span class="badge bg-danger">Priority 1</span>
                    <strong class="small">Leflore County (Tract 28083950700)</strong>
                  </div>
                  <div class="text-muted small mb-1">Poverty Rate: <strong>33.7%</strong> • Zero-Vehicle: <strong>13.0%</strong></div>
                  <div class="text-muted small mb-2">Avg Referral Wait: <strong class="text-danger">76.0 Days</strong> (Multi-Hop Fax)</div>
                  <span class="badge bg-primary text-white">Deploy: Mobile Dev Unit</span>
                </div>
              </div>
              <div class="col-md-4">
                <div class="border rounded-3 p-3 bg-light h-100">
                  <div class="d-flex align-items-center gap-2 mb-2">
                    <span class="badge bg-warning text-dark">Priority 2</span>
                    <strong class="small">Sunflower County (Tract 28133950401)</strong>
                  </div>
                  <div class="text-muted small mb-1">Poverty Rate: <strong>19.6%</strong> • Zero-Vehicle: <strong>9.2%</strong></div>
                  <div class="text-muted small mb-2">Avg Referral Wait: <strong class="text-danger">77.0 Days</strong> (Bounce Loop)</div>
                  <span class="badge bg-info text-dark">Deploy: Spanish ASQ-3 Pop-up</span>
                </div>
              </div>
              <div class="col-md-4">
                <div class="border rounded-3 p-3 bg-light h-100">
                  <div class="d-flex align-items-center gap-2 mb-2">
                    <span class="badge bg-secondary">Priority 3</span>
                    <strong class="small">Hinds County (Tract 28049001600)</strong>
                  </div>
                  <div class="text-muted small mb-1">Poverty Rate: <strong>23.8%</strong> • Zero-Vehicle: <strong class="text-danger">23.7% Deficit</strong></div>
                  <div class="text-muted small mb-2">Avg Referral Wait: <strong class="text-danger">74.0 Days</strong> (Transit Barrier)</div>
                  <span class="badge bg-success text-white">Deploy: Tele-Assessment + NEMT</span>
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
                    <td><code>28133950401</code></td>
                    <td>Sunflower County</td>
                    <td><span class="badge bg-light text-dark border">19.6%</span></td>
                    <td>9.2%</td>
                    <td><span class="badge bg-danger">77.0 days</span></td>
                    <td>1 / 1</td>
                    <td><span class="badge bg-primary">Community Screening Day 1</span></td>
                  </tr>
                  <tr>
                    <td><code>28049000301</code></td>
                    <td>Hinds County</td>
                    <td><span class="badge bg-light text-dark border">31.0%</span></td>
                    <td>4.7%</td>
                    <td><span class="badge bg-danger">76.0 days</span></td>
                    <td>1 / 1</td>
                    <td><span class="badge bg-primary">Community Screening Day 2</span></td>
                  </tr>
                  <tr>
                    <td><code>28083950700</code></td>
                    <td>Leflore County</td>
                    <td><span class="badge bg-light text-dark border">33.7%</span></td>
                    <td>13.0%</td>
                    <td><span class="badge bg-danger">76.0 days</span></td>
                    <td>1 / 1</td>
                    <td><span class="badge bg-danger">Mobile Evaluation Van</span></td>
                  </tr>
                  <tr>
                    <td><code>28011950701</code></td>
                    <td>Bolivar County</td>
                    <td><span class="badge bg-light text-dark border">36.8%</span></td>
                    <td>11.8%</td>
                    <td><span class="badge bg-danger">76.0 days</span></td>
                    <td>1 / 1</td>
                    <td><span class="badge bg-info text-dark">Bilingual Screening Pop-up</span></td>
                  </tr>
                  <tr>
                    <td><code>28049001600</code></td>
                    <td>Hinds County</td>
                    <td><span class="badge bg-light text-dark border">23.8%</span></td>
                    <td><span class="badge bg-warning text-dark">23.7% High Deficit</span></td>
                    <td><span class="badge bg-danger">74.0 days</span></td>
                    <td>1 / 1</td>
                    <td><span class="badge bg-success">Tele-Assessment + NEMT</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ========================================== -->
    <!-- ALWAYS-ON GEOSPATIAL OVERLAY: PHYSICAL MAP OF NY + REFERRALGRAPH -->
    <!-- ========================================== -->
    <div class="row mt-4">
      <div class="col-12">
        <div class="card p-4">
          <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
            <div>
              <h5 id="mapCardTitle" class="card-title mb-1 fw-bold"><i class="fa-solid fa-earth-americas text-primary me-2"></i>Physical Map of New York (NY) — ReferralGraph &amp; 89 Census Tracts Overlay</h5>
              <p class="text-muted small mb-0">
                30 <code>CareNode</code> providers &amp; 89 real US Census tracts overlaid on <strong>USGS National Map (100% Public Domain US Gov — Zero OpenStreetMap ODbL)</strong>. Shows how a Bronx referral bounces hundreds of miles upstate when local bilingual slots saturate.
              </p>
            </div>
            <div class="d-flex flex-wrap gap-2">
              <div class="btn-group btn-group-sm" role="group">
                <button type="button" class="btn btn-outline-primary" onclick="zoomMapRegion('state')">🗺️ Full State View</button>
                <button type="button" class="btn btn-outline-primary" onclick="zoomMapRegion('bronx')">🏙️ Bronx / NYC Cluster</button>
                <button type="button" class="btn btn-outline-primary" onclick="zoomMapRegion('catskills')">⛰️ Catskills / Upstate Eval</button>
                <button type="button" class="btn btn-outline-secondary" onclick="toggleTractLayer()">📍 Toggle 89 Tracts</button>
              </div>
            </div>
          </div>
          <div id="nyPhysicalMap" style="height: 460px; width: 100%; border-radius: 0.75rem; border: 1px solid #cbd5e1;"></div>
          <div class="d-flex flex-wrap justify-content-between align-items-center mt-2 small text-muted">
            <div>
              <span class="badge" style="background:#38bdf8; color:#0f172a;">●</span> Screening Clinic (8)
              <span class="badge ms-1" style="background:#f59e0b; color:#0f172a;">●</span> Part C Intake Coordinator / Bounce Hub (4)
              <span class="badge ms-1" style="background:#a855f7; color:#fff;">●</span> Multidisciplinary Eval Hub (8)
              <span class="badge ms-1" style="background:#10b981; color:#0f172a;">●</span> EI Therapy Vendor (10)
              <span class="badge ms-1" style="background:#f43f5e; color:#fff;">○</span> High Zero-Vehicle Tract
            </div>
            <div class="font-monospace">
              <span style="color:#ef4444; font-weight:bold;">━━━ 4-Hop Fax Bounce (70d)</span> &nbsp;|&nbsp;
              <span style="color:#22c55e; font-weight:bold;">━━━ &le;45d E-Referral Route (40d / 22d)</span>
            </div>
          </div>
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
      },
      MS: {
        name: "Mississippi (MS)",
        county: "Leflore County",
        tract: "28083950200",
        nodes: [
          { id: "SYN-PROV-MS-007", short: "MS-007 (Clinic)", wait: 6, x: 75, y: 115, color: "#38bdf8" },
          { id: "SYN-PROV-MS-011", short: "MS-011 (Bounce Hub)", wait: 5, x: 265, y: 115, color: "#f59e0b", bounceHub: true },
          { id: "SYN-PROV-MS-015", short: "MS-015 (Saturated Eval)", wait: 34, x: 470, y: 52, color: "#ef4444" },
          { id: "SYN-PROV-MS-019", short: "MS-019 (Bilingual Eval)", wait: 7, x: 470, y: 145, color: "#a855f7" },
          { id: "SYN-PROV-MS-028", short: "MS-028 (Therapy)", wait: 6, x: 675, y: 52, color: "#10b981" },
          { id: "SYN-PROV-MS-027", short: "MS-027 (Therapy)", wait: 10, x: 675, y: 145, color: "#10b981" },
          { id: "SYN-PROV-MS-026", short: "MS-026 (Therapy)", wait: 8, x: 675, y: 205, color: "#10b981" }
        ],
        paths: {
          bounce: {
            id: "CHAIN-MS-023",
            title: "🚨 CHAIN-MS-023: 4-Hop Paper-Fax Bounce (75 Days — Breaches 45d Limit!)",
            subtitle: "32-month-old toddler (4 mos from 36m Part C aging-out cliff!) • Expressive/Autism Screen",
            total: 75,
            color: "#ef4444",
            edges: [
              { from: "SYN-PROV-MS-007", to: "SYN-PROV-MS-011", hop: 1, days: 14, chan: "paper_fax", dy: -12 },
              { from: "SYN-PROV-MS-011", to: "SYN-PROV-MS-015", hop: 2, days: 22, chan: "paper_fax", dy: -8 },
              { from: "SYN-PROV-MS-015", to: "SYN-PROV-MS-019", hop: 3, days: 25, chan: "paper_fax", dy: 0 },
              { from: "SYN-PROV-MS-019", to: "SYN-PROV-MS-028", hop: 4, days: 14, chan: "ehr_portal", dy: -8 }
            ]
          },
          eval: {
            id: "CHAIN-MS-007",
            title: "✅ CHAIN-MS-007: 3-Hop Electronic Bilingual Route (37 Days — Saves 38 Days!)",
            subtitle: "Same Clinic (MS-007) & Same Coordinator (MS-011), routed via EHR directly to MS-019",
            total: 37,
            color: "#22c55e",
            edges: [
              { from: "SYN-PROV-MS-007", to: "SYN-PROV-MS-011", hop: 1, days: 6, chan: "ehr_portal", dy: 14 },
              { from: "SYN-PROV-MS-011", to: "SYN-PROV-MS-019", hop: 2, days: 14, chan: "ehr_portal", dy: 10 },
              { from: "SYN-PROV-MS-019", to: "SYN-PROV-MS-027", hop: 3, days: 17, chan: "ehr_portal", dy: 10 }
            ]
          },
          fast: {
            id: "CHAIN-MS-031",
            title: "⚡ CHAIN-MS-031: 2-Hop Electronic Fast-Track (17 Days — Saves 58 Days!)",
            subtitle: "Direct Fast-Track IFSP Placement for eligible toddlers via EHR Portal",
            total: 17,
            color: "#38bdf8",
            edges: [
              { from: "SYN-PROV-MS-007", to: "SYN-PROV-MS-011", hop: 1, days: 5, chan: "ehr_portal", dy: 18 },
              { from: "SYN-PROV-MS-011", to: "SYN-PROV-MS-026", hop: 2, days: 12, chan: "ehr_portal", dy: 14 }
            ]
          }
        },
        hubs: [
          { name: "Indianola Regional Intake Desk (SYN-PROV-MS-011)", wait: "5 days", list: 24, fax: "5 handoffs", breaches: "7 breaches (70+ days)", note: "Hidden bottleneck; low waitlist conceals paper-fax dropoffs." },
          { name: "Jackson Regional Intake Desk (SYN-PROV-MS-012)", wait: "6 days", list: 29, fax: "5 handoffs", breaches: "7 breaches (70+ days)", note: "Systemic re-referral hub lacking bilingual coordinator handoffs." },
          { name: "Cleveland Regional Intake Desk (SYN-PROV-MS-009)", wait: "8 days", list: 14, fax: "4 handoffs", breaches: "6 breaches (70+ days)", note: "Cross-county bounces into backlogged eval hubs." }
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
      document.getElementById('btnStateNY').className = st === 'NY' ? 'btn btn-warning fw-bold text-dark' : 'btn btn-outline-light';
      document.getElementById('btnStateMS').className = st === 'MS' ? 'btn btn-warning fw-bold text-dark' : 'btn btn-outline-light';
      document.getElementById('tractGeoid').value = cfg.tract;
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
      // Toggle button active states
      for (let i = 1; i <= 3; i++) {
        const btn = document.getElementById('btnTrack' + i);
        const pane = document.getElementById('trackPane' + i);
        if (i === trackNum) {
          btn.className = 'btn btn-sm btn-light track-nav-btn active';
          pane.classList.add('active');
        } else {
          btn.className = 'btn btn-sm btn-outline-light track-nav-btn';
          pane.classList.remove('active');
        }
      }

      const info = document.getElementById('trackBannerInfo');
      const input = document.getElementById('userInput');
      const cfg = STATE_DATA[activeState];

      if (trackNum === 1) {
        info.innerHTML = "<strong>Track 1 Active:</strong> Route today's toddler referral (&le;45d compliant path with 36m age cliff guard).";
        input.value = `Route a 20-month-old Spanish-speaking Medicaid toddler in ${cfg.county} tract ${cfg.tract}.`;
      } else if (trackNum === 2) {
        info.innerHTML = "<strong>Track 2 Active:</strong> Variable-length GQL exposes systemic paper-fax bounce hubs breaking federal clock.";
        input.value = `Trace 3-to-4 hop referral chains breaching 45 days in ${activeState} and identify the regional bounce hubs.`;
        setSvgGraphMode('both');
        renderSvgComparisonGraph();
      } else if (trackNum === 3) {
        info.innerHTML = "<strong>Track 3 Active:</strong> Combine ACS under-5 poverty & NSCH screening baselines to deploy mobile screening days.";
        input.value = `Where should community developmental screening outreach days go first in ${cfg.name}?`;
        loadEquityAuditData();
      }
    }

    // Load SVG referral comparison graph on page ready (defaults to NY)
    window.addEventListener('DOMContentLoaded', () => {
      setActiveState('NY');
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

    function zoomMapRegion(region) {
      if (!leafletMap) return;
      if (activeState === 'MS') {
        leafletMap.setView([33.35, -90.45], region === 'state' ? 8 : 10);
        return;
      }
      if (region === 'bronx') {
        leafletMap.setView([40.848, -73.895], 12);
      } else if (region === 'catskills') {
        leafletMap.setView([42.22, -74.88], 9);
      } else {
        leafletMap.setView([42.65, -75.5], 7);
      }
    }

    function toggleTractLayer() {
      showTractsOnMap = !showTractsOnMap;
      renderPhysicalMapOverlay();
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

    async function runTriage() {
      const resultDiv = document.getElementById('triageResult');
      resultDiv.innerHTML = 'Computing optimal graph pathway...';

      const payload = {
        child_age_months: parseInt(document.getElementById('childAge').value),
        census_tract_geoid: document.getElementById('tractGeoid').value,
        requires_medicaid: document.getElementById('reqMedicaid').checked,
        requires_bilingual: document.getElementById('reqBilingual').checked,
        max_wait_days: 45
      };

      const res = await fetch('/api/triage/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.recommended_pathways && data.recommended_pathways.length > 0) {
        const p = data.recommended_pathways[0];
        let alertHtml = '';
        if (data.age_warning) {
          alertHtml += `<div class="alert alert-danger p-2 mb-2">${data.age_warning}</div>`;
        }
        if (data.zero_vehicle_travel_guardrail && data.zero_vehicle_travel_guardrail.alert) {
          alertHtml += `<div class="alert alert-warning p-2 mb-2">🚐 <strong>${data.zero_vehicle_travel_guardrail.alert}</strong></div>`;
        }
        resultDiv.innerHTML = `
          ${alertHtml}
          <div class="border rounded p-2 bg-light">
            <div class="fw-bold text-success">Compliant Pathway: ${p.total_estimated_wait_days} Total Days (<= 45d limit)</div>
            <ol class="ps-3 mt-1 mb-0">
              <li><strong>Clinic:</strong> ${p.screening_clinic} (${p.clinic_wait}d)</li>
              <li><strong>Coordinator:</strong> ${p.intake_coordinator} (${p.coord_wait}d)</li>
              <li><strong>Eval Hub:</strong> ${p.eval_hub} (${p.eval_wait}d, Bilingual: ${p.eval_bilingual})</li>
              <li><strong>Therapy Vendor:</strong> ${p.therapy_vendor} (${p.vendor_wait}d)</li>
            </ol>
          </div>
        `;
      } else {
        resultDiv.innerHTML = '<span class="text-danger">No local pathway cleared 45 days with specified constraints. Immediate escalation required.</span>';
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
  </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), reload=False)
