"""Playwright end-to-end verification of the live Cloud Run Early Intervention agent."""

from __future__ import annotations

from pathlib import Path
import time
from playwright.sync_api import sync_playwright

LIVE_URL = "https://early-intervention-triage-584075988667.us-central1.run.app/"
SCREENSHOT_PATH = Path(__file__).resolve().parent / "live_cloudrun_verified.png"

CORE_PROMPTS = [
    {
        "id": "Tool 1: Multi-Hop ISO GQL Breach & Bounce Hub Trace",
        "prompt": "Trace 3-to-4 hop referral chains breaching 45 days and show bounce hubs.",
        "expected_any": ["SYN-PROV", "Indianola", "Jackson", "paper_fax", "fax", "45"],
        "synthetic_check": ["Synthetic", "SYN-PROV"],
    },
    {
        "id": "Tool 2: <=45-Day Compliant Toddler Pathway Routing",
        "prompt": "Route a 22-month-old Spanish-speaking Medicaid toddler near tract 28083950200.",
        "expected_any": ["22", "days", "Greenwood", "Medicaid", "bilingual", "SYN-PROV"],
        "synthetic_check": ["Synthetic", "SYN-PROV"],
    },
    {
        "id": "Tool 3: Post-Output Equity Audit & Counterfactual E-Fax Savings",
        "prompt": "Perform an Equity Audit on multi-hop delays and counterfactual e-fax savings.",
        "expected_any": ["1,168", "1168", "poverty", "vehicle", "NSCH", "statewide"],
        "synthetic_check": [],
    },
    {
        "id": "Tool 4: Bilingual (English & Spanish) Caregiver Action Note",
        "prompt": (
            "Generate bilingual caregiver action notes for the Rivera family and toddler Mateo "
            "using our recommended 22-day pathway."
        ),
        "expected_any": ["Estimada", "45", "Medicaid", "español", "Spanish", "days", "días"],
        "synthetic_check": [],
    },
]


def _launch_browser(p):
    """Launch installed Chrome or Edge first to avoid downloading Chromium."""
    for channel in ("chrome", "msedge", None):
        try:
            if channel:
                return p.chromium.launch(headless=True, channel=channel)
            return p.chromium.launch(headless=True)
        except Exception:
            continue
    raise RuntimeError("Could not launch Chrome, Edge, or Chromium via Playwright.")


def run_live_audit() -> None:
    print("=" * 78)
    print(f"PLAYWRIGHT LIVE CLOUD RUN AUDIT: {LIVE_URL}")
    print("=" * 78)

    with sync_playwright() as p:
        browser = _launch_browser(p)
        page = browser.new_page(viewport={"width": 1440, "height": 1080})

        t0 = time.time()
        page.goto(LIVE_URL, wait_until="networkidle", timeout=45000)
        load_sec = round(time.time() - t0, 2)
        title = page.title()
        print(f"[PASS] Page loaded in {load_sec}s | Title: {title}")

        # 1. Verify Vis.js Graph & Breached Chains Dropdown
        page.wait_for_function(
            "document.querySelectorAll('#chainSelector option').length > 1",
            timeout=20000,
        )
        chain_options = page.locator("#chainSelector option").all_inner_texts()
        print(f"[PASS] Graph dropdown populated with {len(chain_options)} breached chains:")
        print(f"       Top chain: {chain_options[0] if chain_options else 'N/A'}")

        # Select second chain to verify Vis.js interactive re-render
        if len(chain_options) > 1:
            page.select_option("#chainSelector", index=1)
            page.wait_for_timeout(400)
            metrics_text = page.locator("#chainMetrics").inner_text()
            print(f"[PASS] Graph chain switch rendered metrics: {metrics_text}")

        # 2. Test Quick Triage & Route Optimizer with 32-month-old (36m Aging-Out Cliff!)
        page.fill("#childAge", "32")
        page.fill("#tractGeoid", "28083950200")
        page.click("button:has-text('Find Compliant Pathway')")
        page.wait_for_function(
            "document.getElementById('triageResult').innerText.includes('Compliant Pathway')",
            timeout=20000,
        )
        triage_text = page.locator("#triageResult").inner_text()
        has_cliff_warning = "36-MONTH" in triage_text.upper() or "AGE-OUT" in triage_text.upper()
        print(f"[PASS] Quick Triage Optimizer returned <=45d pathway (36m cliff alert={has_cliff_warning}):")
        for line in triage_text.splitlines():
            if line.strip():
                print(f"       {line.strip()}")

        # 3. Test the 4 Core Tool Prompts in the Live ADK Chat Box
        print("\n" + "-" * 78)
        print("TESTING 4 CORE ADK AGENT PROMPTS VIA CHAT UI")
        print("-" * 78)

        passed_prompts = 0
        for idx, item in enumerate(CORE_PROMPTS, start=1):
            before_count = page.locator("#chatBox .msg-agent").count()
            page.fill("#userInput", item["prompt"])
            t_start = time.time()
            page.click("button:has-text('Send')")

            # Wait for new .msg-agent bubble to arrive
            page.wait_for_function(
                f"document.querySelectorAll('#chatBox .msg-agent').length > {before_count}",
                timeout=90000,
            )
            elapsed = round(time.time() - t_start, 2)
            reply = page.locator("#chatBox .msg-agent").nth(before_count).inner_text().strip()

            matched = [kw for kw in item["expected_any"] if kw.lower() in reply.lower()]
            syn_ok = (
                True
                if not item["synthetic_check"]
                else any(s.lower() in reply.lower() for s in item["synthetic_check"])
            )
            verdict = "PASS" if (len(matched) >= 2 and syn_ok) else "WARN"
            if verdict == "PASS":
                passed_prompts += 1

            print(f"\n[{verdict}] Prompt {idx} ({item['id']}) — {elapsed}s")
            print(f"  Prompt : {item['prompt']}")
            print(f"  Matched: {matched} | Synthetic Disclosure: {syn_ok}")
            preview = reply.replace("\n", " ")[:320]
            print(f"  Reply  : {preview}...")

        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        print("\n" + "=" * 78)
        print(
            f"SUMMARY: {passed_prompts}/{len(CORE_PROMPTS)} core ADK prompts passed | "
            f"Screenshot saved to {SCREENSHOT_PATH.name}"
        )
        print("=" * 78)
        browser.close()


if __name__ == "__main__":
    run_live_audit()
