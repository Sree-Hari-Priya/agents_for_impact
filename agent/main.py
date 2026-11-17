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
    census_tract_geoid: Optional[str] = "28083950200"
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
def get_breaches(min_wait_days: int = 45, limit: int = 10):
    return trace_45day_breaches_and_bounce_hubs(min_wait_days=min_wait_days, limit=limit)

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
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    body { background-color: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .hero { background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%); color: white; padding: 2.5rem 1.5rem; margin-bottom: 2rem; border-radius: 0 0 1rem 1rem; }
    .card { border-radius: 0.75rem; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.06); margin-bottom: 1.5rem; }
    .stat-badge { font-size: 1.5rem; font-weight: 700; color: #1a73e8; }
    .badge-breach { background-color: #ea4335; color: white; }
    .badge-pass { background-color: #34a853; color: white; }
    .chat-box { height: 380px; overflow-y: auto; background: white; border: 1px solid #e0e0e0; border-radius: 0.5rem; padding: 1rem; }
    .msg-user { background-color: #e8f0fe; color: #1967d2; border-radius: 0.5rem; padding: 0.6rem 1rem; margin-bottom: 0.5rem; max-width: 80%; margin-left: auto; }
    .msg-agent { background-color: #f1f3f4; color: #202124; border-radius: 0.5rem; padding: 0.6rem 1rem; margin-bottom: 0.5rem; max-width: 85%; white-space: pre-wrap; }
  </style>
</head>
<body>
  <div class="hero">
    <div class="container">
      <div class="d-flex align-items-center justify-content-between">
        <div class="d-flex align-items-center gap-3">
          <img
            src="https://images.unsplash.com/photo-1596464716127-f2a82984de30?auto=format&fit=crop&w=240&q=80"
            alt="Toddler stacking wooden milestone blocks (Illustrative Only — Zero Real Patient PII)"
            style="width: 76px; height: 76px; object-fit: cover; border-radius: 50%; border: 3px solid rgba(255,255,255,0.85); box-shadow: 0 4px 10px rgba(0,0,0,0.2);"
          />
          <div>
            <span class="badge bg-light text-dark mb-2">Challenge 04 · Early Intervention &amp; Developmental Screening Triage</span>
            <h1 class="h2 mb-1 font-weight-bold">First Milestones: IDEA Part C Triage &amp; Network-Audit</h1>
            <p class="mb-0 opacity-75">BigQuery Property Graph (ISO GQL) · Google ADK Agent · Vertex AI Gemini 2.5 Flash</p>
          </div>
        </div>
        <div class="text-end">
          <span class="badge bg-warning text-dark px-3 py-2">State: Mississippi (MS)</span>
          <div class="small mt-1 text-light">100% [Synthetic] Provider Topology · Illustrative Photo</div>
        </div>
      </div>
      <!-- Interactive Track Mode Switcher -->
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mt-3 pt-3 border-top border-light border-opacity-25">
        <div class="d-flex align-items-center gap-2">
          <span class="small text-uppercase fw-bold opacity-75 me-1">Working Track Mode:</span>
          <div class="btn-group" role="group">
            <button id="btnTrack1" type="button" class="btn btn-sm btn-light fw-semibold text-primary active" onclick="activateTrack(1)">
              Track 1: Today's Referral (<=45d Route)
            </button>
            <button id="btnTrack2" type="button" class="btn btn-sm btn-outline-light fw-semibold" onclick="activateTrack(2)">
              Track 2: Quarterly Audit (Bounce Hubs)
            </button>
            <button id="btnTrack3" type="button" class="btn btn-sm btn-outline-light fw-semibold" onclick="activateTrack(3)">
              Track 3: Outreach Season (Screening Days)
            </button>
          </div>
        </div>
        <div id="trackBannerInfo" class="small text-white-50">
          Ready to route a 20-month-old Spanish-speaking Medicaid referral in Leflore County.
        </div>
      </div>
    </div>
  </div>

  <div class="container pb-5">
    <!-- Top Stats -->
    <div class="row g-3 mb-4">
      <div class="col-md-3">
        <div class="card p-3 text-center">
          <div class="stat-badge text-danger">26 / 35</div>
          <div class="text-muted small">Multi-Hop Chains Breaching 45d</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card p-3 text-center">
          <div class="stat-badge text-primary">5 - 6 Days</div>
          <div class="text-muted small">Deceptive "Bounce Hub" Internal Wait</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card p-3 text-center">
          <div class="stat-badge text-success">1,168 Days</div>
          <div class="text-muted small">Saved by Upgrading Paper-Fax to EHR</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card p-3 text-center">
          <div class="stat-badge text-info">22 Days</div>
          <div class="text-muted small">Graph-Optimized Toddler Pathway</div>
        </div>
      </div>
    </div>

    <!-- Coordinator Chat & Triage -->
    <div class="row">
      <!-- Live ADK Agent Interaction -->
      <div class="col-lg-7">
        <div class="card p-4">
          <h5 class="card-title mb-3">💬 Conversational Coordinator Assistant (ADK + Gemini)</h5>
          <div id="chatBox" class="chat-box mb-3">
            <div class="msg-agent">Hello Coordinator. I am your Early Intervention Triage Assistant. You can ask me to:
• "Trace 3-to-4 hop referral chains breaching 45 days and show bounce hubs."
• "Route a 22-month-old Spanish-speaking Medicaid toddler near tract 28083950200."
• "Perform an Equity Audit on multi-hop delays and counterfactual e-fax savings."
• "Generate bilingual caregiver action notes."</div>
          </div>
          <div class="input-group">
            <input type="text" id="userInput" class="form-control" placeholder="Ask your question (e.g. Find a <=45d path for today's toddler)..." onkeydown="if(event.key==='Enter') sendMessage()">
            <button class="btn btn-primary" onclick="sendMessage()">Send</button>
          </div>
        </div>
      </div>

      <!-- Quick Triage Routing Panel -->
      <div class="col-lg-5">
        <div class="card p-4">
          <h5 class="card-title mb-3">🧭 Quick Triage & Route Optimizer</h5>
          <div class="mb-2">
            <label class="form-label small mb-1">Child Age (Months)</label>
            <input type="number" id="childAge" class="form-control form-control-sm" value="22" min="1" max="35">
          </div>
          <div class="mb-2">
            <label class="form-label small mb-1">Census Tract GEOID</label>
            <input type="text" id="tractGeoid" class="form-control form-control-sm" value="28083950200">
          </div>
          <div class="form-check form-switch mb-2">
            <input class="form-check-input" type="checkbox" id="reqMedicaid" checked>
            <label class="form-check-label small" for="reqMedicaid">Requires Medicaid Acceptance</label>
          </div>
          <div class="form-check form-switch mb-3">
            <input class="form-check-input" type="checkbox" id="reqBilingual" checked>
            <label class="form-check-label small" for="reqBilingual">Requires Bilingual Evaluator (Spanish)</label>
          </div>
          <button class="btn btn-outline-primary btn-sm w-100" onclick="runTriage()">Find Compliant Pathway (<= 45d)</button>
          <hr>
          <div id="triageResult" class="small text-muted">Click above to calculate optimal route.</div>
        </div>
      </div>
    </div>

    <!-- Interactive Graph Visualization of Referral Handoff Hops -->
    <div class="row mt-4">
      <div class="col-12">
        <div class="card p-4">
          <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
            <div>
              <h5 class="card-title mb-1">🕸️ ReferralGraph Side-by-Side Pathway &amp; 45-Day Statutory Clock</h5>
              <p class="text-muted small mb-0">
                Comparing the <strong>75-day 4-hop paper-fax bounce loop (CHAIN-MS-023, 32m toddler)</strong> vs. the <strong>37-day 3-hop e-referral route (CHAIN-MS-007)</strong> &amp; <strong>17-day 2-hop fast-track (CHAIN-MS-031)</strong> from the exact same clinic &amp; coordinator.
              </p>
            </div>
            <div class="btn-group btn-group-sm" role="group">
              <button id="btn-mode-both" type="button" class="btn btn-primary" onclick="setSvgGraphMode('both')">Compare Bounce vs. &le;45d Route</button>
              <button id="btn-mode-bounce" type="button" class="btn btn-outline-danger" onclick="setSvgGraphMode('bounce')">🚨 4-Hop Fax Bounce (75d)</button>
              <button id="btn-mode-eval" type="button" class="btn btn-outline-success" onclick="setSvgGraphMode('eval')">✅ 3-Hop E-Referral (37d)</button>
              <button id="btn-mode-fast" type="button" class="btn btn-outline-info" onclick="setSvgGraphMode('fast')">⚡ 2-Hop Fast-Track (17d)</button>
            </div>
          </div>

          <div class="p-2 rounded border mb-3" style="background-color: #0f172a; color: #f8fafc;">
            <svg id="svgReferralGraph" viewBox="0 0 760 235" style="width:100%; height:auto; display:block;"></svg>
          </div>
          <div id="svgClockCards" class="row g-3 mb-4"></div>

          <hr>
          <div class="d-flex justify-content-between align-items-center mb-2 mt-3">
            <div>
              <h6 class="mb-1 fw-bold">🔍 Live BigQuery ISO GQL Case-Chain Inspector (All 26 Breached Chains)</h6>
              <p class="text-muted small mb-0">
                Select any individual breached chain returned by <code>GRAPH a4i_early_intervention.ReferralGraph MATCH (c:CareNode)-[hops:ReferralHandoff]-&gt;{2,4}(v:CareNode)</code>:
              </p>
            </div>
            <div class="d-flex align-items-center gap-2">
              <label class="form-label small mb-0 fw-bold">Select Breached Case Chain:</label>
              <select id="chainSelector" class="form-select form-select-sm w-auto" onchange="renderSelectedChain()">
                <option value="">Loading graph chains...</option>
              </select>
            </div>
          </div>
          <div id="chainMetrics" class="mb-2 small"></div>
          <div id="graphNetwork" style="height: 340px; border: 1px solid #dee2e6; border-radius: 0.5rem; background-color: #fafbfc;"></div>
          <div class="d-flex justify-content-between align-items-center mt-2 small text-muted">
            <div>
              <span class="badge bg-primary me-1">&nbsp;</span> Screening Clinic
              <span class="badge bg-warning text-dark mx-1">&nbsp;</span> Part C Intake Coordinator (Bounce Hub)
              <span class="badge bg-info text-dark mx-1">&nbsp;</span> Multidisciplinary Eval Hub
              <span class="badge bg-success ms-1">&nbsp;</span> EI Therapy Vendor
            </div>
            <div>
              <span style="color:#e65100; font-weight:bold;">--- Paper Fax Handoff</span> |
              <span style="color:#0288d1; font-weight:bold;">— EHR Portal / Phone</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Graph Audit Findings Table -->
    <div class="row mt-2">
      <div class="col-12">
        <div class="card p-4">
          <h5 class="card-title">📊 Coordinator "Bounce Hub" Summary (Deceptive Waitlist vs Breaches)</h5>
          <div class="table-responsive">
            <table class="table table-sm table-striped">
              <thead class="table-light">
                <tr>
                  <th>Coordinator (Bounce Hub)</th>
                  <th>Internal Wait</th>
                  <th>Active Waitlist</th>
                  <th>Paper Fax Handoffs</th>
                  <th>Breached Chains Caused</th>
                  <th>Impact Assessment</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Indianola Regional Intake Desk (SYN-PROV-MS-011)</strong></td>
                  <td><span class="badge bg-success">5 days</span></td>
                  <td>24</td>
                  <td>5 handoffs</td>
                  <td><span class="badge badge-breach">7 breaches (70+ days)</span></td>
                  <td>Hidden bottleneck; low waitlist conceals paper-fax dropoffs.</td>
                </tr>
                <tr>
                  <td><strong>Jackson Regional Intake Desk (SYN-PROV-MS-012)</strong></td>
                  <td><span class="badge bg-success">6 days</span></td>
                  <td>29</td>
                  <td>5 handoffs</td>
                  <td><span class="badge badge-breach">7 breaches (70+ days)</span></td>
                  <td>Systemic re-referral hub lacking bilingual coordinator handoffs.</td>
                </tr>
                <tr>
                  <td><strong>Cleveland Regional Intake Desk (SYN-PROV-MS-009)</strong></td>
                  <td><span class="badge bg-success">8 days</span></td>
                  <td>14</td>
                  <td>4 handoffs</td>
                  <td><span class="badge badge-breach">6 breaches (70+ days)</span></td>
                  <td>Cross-county bounces into backlogged eval hubs.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let sessionId = null;
    let graphChains = [];
    let networkInstance = null;

    async function loadGraphChains() {
      try {
        const res = await fetch('/api/graph/breaches');
        const data = await res.json();
        graphChains = data.breached_chains_sample || [];
        
        const selector = document.getElementById('chainSelector');
        selector.innerHTML = '';
        graphChains.forEach((c, idx) => {
          const opt = document.createElement('option');
          opt.value = idx;
          opt.textContent = `${c.chain_id} - ${c.chain_wait_days}d (${c.total_hops} hops, ${c.fax_hops} fax hops)`;
          selector.appendChild(opt);
        });

        if (graphChains.length > 0) {
          renderSelectedChain();
        }
      } catch (err) {
        console.error('Failed to load graph chains', err);
      }
    }

    function activateTrack(trackNum) {
      document.getElementById('btnTrack1').className = trackNum === 1 ? 'btn btn-sm btn-light fw-semibold text-primary active' : 'btn btn-sm btn-outline-light fw-semibold';
      document.getElementById('btnTrack2').className = trackNum === 2 ? 'btn btn-sm btn-light fw-semibold text-primary active' : 'btn btn-sm btn-outline-light fw-semibold';
      document.getElementById('btnTrack3').className = trackNum === 3 ? 'btn btn-sm btn-light fw-semibold text-primary active' : 'btn btn-sm btn-outline-light fw-semibold';

      const info = document.getElementById('trackBannerInfo');
      const input = document.getElementById('userInput');

      if (trackNum === 1) {
        info.innerHTML = "<strong>Track 1 Active:</strong> Route today's toddler referral (&le;45d compliant path with 36m age cliff guard).";
        input.value = "Route a 20-month-old Spanish-speaking Medicaid toddler in Leflore County tract 28083950200.";
        document.getElementById('childAge').scrollIntoView({ behavior: 'smooth' });
      } else if (trackNum === 2) {
        info.innerHTML = "<strong>Track 2 Active:</strong> Variable-length GQL exposes systemic paper-fax bounce hubs breaking federal clock.";
        input.value = "Trace 3-to-4 hop referral chains breaching 45 days and identify the regional bounce hubs.";
        setSvgGraphMode('both');
        document.getElementById('svgReferralGraph').scrollIntoView({ behavior: 'smooth' });
      } else if (trackNum === 3) {
        info.innerHTML = "<strong>Track 3 Active:</strong> Combine ACS under-5 poverty & NSCH screening baselines to deploy mobile screening days.";
        input.value = "Where should community developmental screening outreach days go first in Mississippi?";
        document.getElementById('chatBox').scrollIntoView({ behavior: 'smooth' });
      }
    }

    function renderSelectedChain() {
      const selector = document.getElementById('chainSelector');
      const idx = parseInt(selector.value);
      if (isNaN(idx) || !graphChains[idx]) return;

      const chain = graphChains[idx];
      const metricsDiv = document.getElementById('chainMetrics');
      const breachDays = chain.chain_wait_days - 45;

      metricsDiv.innerHTML = `
        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 w-100 p-2 bg-white rounded border">
          <div>
            <span class="badge bg-dark font-monospace me-2">${chain.chain_id}</span>
            <span class="text-danger fw-bold"><i class="fa-solid fa-clock"></i> Total Wait: ${chain.chain_wait_days} Days</span>
            <span class="badge bg-danger ms-2">+${breachDays}d Over Statutory Clock</span>
          </div>
          <div class="small text-muted">
            <span class="me-3">Hops: <strong>${chain.total_hops}</strong></span>
            <span class="text-danger fw-bold"><i class="fa-solid fa-fax"></i> Paper Fax Handoffs: ${chain.fax_hops}</span>
          </div>
        </div>
      `;

      // Enhanced Vis.js Nodes styling with icons and hierarchy
      const roleThemes = {
        'Screening_Pediatric_Clinic': { bg: '#1a73e8', icon: '🩺', border: '#1557b0' },
        'Part_C_Intake_Coordinator': { bg: '#f29900', icon: '📋', border: '#b06000' },
        'Multidisciplinary_Eval_Hub': { bg: '#00acc1', icon: '🧠', border: '#00838f' },
        'EI_Therapy_Vendor': { bg: '#1e8e3e', icon: '🧸', border: '#137333' }
      };

      const nodes = chain.nodes.map((n, i) => {
        const theme = roleThemes[n.role] || { bg: '#5f6368', icon: '🏢', border: '#3c4043' };
        const cleanName = n.label.replace(' [Synthetic]', '');
        return {
          id: n.id,
          label: `${theme.icon} Hop ${i+1}\n${cleanName}\n(${n.id})`,
          shape: 'box',
          margin: 12,
          color: {
            background: theme.bg,
            border: theme.border,
            highlight: { background: '#d93025', border: '#b31412' }
          },
          font: { color: '#ffffff', size: 12, bold: true, face: '-apple-system, BlinkMacSystemFont, Segoe UI' },
          shadow: { enabled: true, color: 'rgba(0,0,0,0.18)', size: 5, x: 2, y: 3 },
          title: `Provider: ${cleanName}\nRole: ${n.role}\nID: ${n.id}`
        };
      });

      // Enhanced Vis.js Edges styling with high-visibility friction markers
      const edges = chain.edges.map(e => {
        const isFax = e.channel === 'paper_fax';
        return {
          from: e.from,
          to: e.to,
          label: `${isFax ? '📠 FAX' : '💻 EHR'}\n+${e.wait_days}d`,
          arrows: { to: { enabled: true, scaleFactor: 1.1 } },
          color: { color: isFax ? '#d93025' : '#1a73e8', highlight: '#b31412' },
          dashes: isFax ? [8, 5] : false,
          width: isFax ? 3.5 : 2.5,
          font: { size: 11, face: 'monospace', align: 'top', background: '#ffffff', strokeWidth: 0, color: isFax ? '#c5221f' : '#174ea6' },
          smooth: { type: 'cubicBezier', roundness: 0.2 }
        };
      });

      const container = document.getElementById('graphNetwork');
      const data = {
        nodes: new vis.DataSet(nodes),
        edges: new vis.DataSet(edges)
      };

      const options = {
        layout: {
          hierarchical: {
            direction: 'LR',
            sortMethod: 'directed',
            levelSeparation: 250,
            nodeSpacing: 110
          }
        },
        physics: false,
        interaction: { hover: true, zoomView: true, dragView: true }
      };

      if (networkInstance) {
        networkInstance.destroy();
      }
      networkInstance = new vis.Network(container, data, options);
    }

    // Load graph chains on page ready
    window.addEventListener('DOMContentLoaded', () => {
      renderSvgComparisonGraph();
      loadGraphChains();
    });

    const svgGraphNodes = [
      { id: "SYN-PROV-MS-007", short: "MS-007 (Clinic)", wait: 6, x: 75, y: 115, color: "#38bdf8" },
      { id: "SYN-PROV-MS-011", short: "MS-011 (Bounce Hub)", wait: 5, x: 265, y: 115, color: "#f59e0b", bounceHub: true },
      { id: "SYN-PROV-MS-015", short: "MS-015 (Saturated Eval)", wait: 34, x: 470, y: 52, color: "#ef4444" },
      { id: "SYN-PROV-MS-019", short: "MS-019 (Bilingual Eval)", wait: 7, x: 470, y: 145, color: "#a855f7" },
      { id: "SYN-PROV-MS-028", short: "MS-028 (Therapy)", wait: 6, x: 675, y: 52, color: "#10b981" },
      { id: "SYN-PROV-MS-027", short: "MS-027 (Therapy)", wait: 10, x: 675, y: 145, color: "#10b981" },
      { id: "SYN-PROV-MS-026", short: "MS-026 (Therapy)", wait: 8, x: 675, y: 205, color: "#10b981" }
    ];

    const svgGraphPaths = {
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
    };

    let svgCurrentMode = "both";

    function setSvgGraphMode(mode) {
      svgCurrentMode = mode;
      ["both", "bounce", "eval", "fast"].forEach(m => {
        const btn = document.getElementById("btn-mode-" + m);
        if (!btn) return;
        btn.classList.toggle("active", m === mode);
      });
      renderSvgComparisonGraph();
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
          alertHtml = `<div class="alert alert-danger p-2 mb-2">${data.age_warning}</div>`;
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
  </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), reload=False)
