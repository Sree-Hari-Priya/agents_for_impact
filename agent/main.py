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
        <div>
          <h1 class="h2 mb-1 font-weight-bold">First Milestones: IDEA Part C Triage & Network-Audit</h1>
          <p class="mb-0 opacity-75">BigQuery Property Graph (ISO GQL) · Google ADK Agent · Vertex AI Gemini</p>
        </div>
        <div class="text-end">
          <span class="badge bg-warning text-dark px-3 py-2">State: Mississippi (MS)</span>
          <div class="small mt-1 text-light">100% [Synthetic] Provider Topology</div>
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
          <div class="d-flex justify-content-between align-items-center mb-2">
            <div>
              <h5 class="card-title mb-1">🕸️ Interactive ISO GQL Multi-Hop Referral Path Graph</h5>
              <p class="text-muted small mb-0">
                Visualizing multi-hop referral handoffs traversed via BigQuery ISO GQL (<code>CareNode-[ReferralHandoff]->{2,4}</code>).
                Yellow dashed edges indicate <strong>paper fax handoffs</strong> causing downstream bounce backlogs.
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
          <div id="graphNetwork" style="height: 380px; border: 1px solid #dee2e6; border-radius: 0.5rem; background-color: #fafbfc;"></div>
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

    function renderSelectedChain() {
      const selector = document.getElementById('chainSelector');
      const idx = parseInt(selector.value);
      if (isNaN(idx) || !graphChains[idx]) return;

      const chain = graphChains[idx];
      const metricsDiv = document.getElementById('chainMetrics');
      metricsDiv.innerHTML = `
        <span class="badge badge-breach me-2">Chain: ${chain.chain_id}</span>
        <span class="text-danger fw-bold me-2">Cumulative Wait: ${chain.chain_wait_days} Days (Statutory Breach: +${chain.chain_wait_days - 45}d)</span> |
        <span class="text-muted ms-2">Hops: ${chain.total_hops} | Paper Fax Handoffs: ${chain.fax_hops}</span>
      `;

      // Build Vis.js Nodes
      const roleColors = {
        'Screening_Pediatric_Clinic': '#1a73e8',
        'Part_C_Intake_Coordinator': '#f29900',
        'Multidisciplinary_Eval_Hub': '#00acc1',
        'EI_Therapy_Vendor': '#2e7d32'
      };

      const nodes = chain.nodes.map(n => ({
        id: n.id,
        label: n.label.replace(' [Synthetic]', ''),
        shape: 'box',
        margin: 10,
        color: {
          background: roleColors[n.role] || '#5f6368',
          border: '#3c4043',
          highlight: { background: '#d93025', border: '#b31412' }
        },
        font: { color: '#ffffff', size: 12, bold: true },
        shadow: true
      }));

      // Build Vis.js Edges
      const edges = chain.edges.map(e => {
        const isFax = e.channel === 'paper_fax';
        return {
          from: e.from,
          to: e.to,
          label: `${e.channel}\n(+${e.wait_days}d)`,
          arrows: 'to',
          color: { color: isFax ? '#e65100' : '#1976d2' },
          dashes: isFax,
          width: isFax ? 3 : 2,
          font: { size: 11, align: 'top', background: '#ffffff', strokeWidth: 0 }
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
            levelSeparation: 220,
            nodeSpacing: 100
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
    window.addEventListener('DOMContentLoaded', loadGraphChains);

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
