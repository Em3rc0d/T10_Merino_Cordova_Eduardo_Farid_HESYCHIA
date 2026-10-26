"""Optional browser E2E QA. pip install playwright==1.55.0; playwright install chromium.

Runs server and browser in the same process environment. No external dataset or API.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from web_server import create_server


def verify(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    server = create_server("127.0.0.1", 0, output_root=ROOT/"outputs"/"pi9_pi10_browser",
                           dataset_root=ROOT/"data"/"not_mounted_for_browser_QA",
                           evidence_root=ROOT/"outputs"/"pi9_pi10_browser"/"isolated_status")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report = {"scope": "local browser engineering QA; not scientific validation",
              "browser": "Chromium", "steps": [], "page_errors": []}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda e: report["page_errors"].append(str(e)))
            page.goto(f"http://127.0.0.1:{server.server_address[1]}")
            page.wait_for_function("document.querySelector('#healthText').textContent==='Servicio operativo'")
            page.screenshot(path=str(out/"01_overview.png"), full_page=True)
            page.locator('[data-page="deep"]').click()
            page.wait_for_function("document.querySelector('#m4State').textContent.includes('Checkpoint verificado')")
            assert page.locator("#m4Info").inner_text().find("236833") >= 0
            page.screenshot(path=str(out/"02_m4.png"), full_page=True)
            report["steps"].append({"id": "architecture", "passed": True})
            page.locator('[data-page="attenuation"]').click()
            page.locator("#engine").select_option("cnn_experimental")
            page.locator("#runAttBtn").click()
            page.locator("#attResults").wait_for(state="visible", timeout=60000)
            assert "cnn_experimental / cnn_experimental" in page.locator("#policyBox").inner_text()
            assert "checkpoint.pt" in page.locator("#artifactRows").inner_text()
            page.screenshot(path=str(out/"03_cnn.png"), full_page=True)
            report["steps"].append({"id": "E1_CNN_UI", "passed": True,
                                    "run": page.locator("#policyBox").inner_text()})
            page.locator("#compareBtn").click()
            page.locator("#comparisonResults").wait_for(state="visible", timeout=60000)
            page.locator("#verifyComparisonBtn").click()
            page.wait_for_function("document.querySelector('#comparisonIntegrity').textContent.includes('ÍNTEGRA')")
            page.evaluate("scrollTo(0,0)")
            page.screenshot(path=str(out/"04_comparison.png"), full_page=True)
            report["steps"].append({"id": "E2_PAIRED_UI", "passed": True,
                                    "identity": page.locator("#comparisonIdentity").inner_text(),
                                    "metrics": page.locator("#comparisonRows").inner_text()})
            page.locator("#demoTarget").select_option("siren_synthetic")
            page.locator("#runAttBtn").click()
            page.locator("#attResults").wait_for(state="visible", timeout=60000)
            assert "mandatory_protected_signal" in page.locator("#policyBox").inner_text()
            assert "cnn_experimental / bypass" in page.locator("#policyBox").inner_text()
            assert page.locator("#kpiTarget").inner_text() == "0.000 dB"
            page.screenshot(path=str(out/"05_siren_block.png"), full_page=True)
            report["steps"].append({"id": "E3_SIREN_BLOCK_UI", "passed": True})
            page.locator('[data-page="evidence"]').click()
            page.locator('#runRows button', has_text="Verificar").first.click()
            page.wait_for_function("document.querySelector('#runRows').textContent.includes('ÍNTEGRO')")
            page.screenshot(path=str(out/"06_integrity.png"), full_page=True)
            report["steps"].append({"id": "E4_INTEGRITY_UI", "passed": True})
            page.set_viewport_size({"width": 390, "height": 844})
            for tab in ("overview", "deep", "attenuation", "evidence", "edge"):
                page.locator(f'[data-page="{tab}"]').click()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), tab
            page.locator('[data-page="deep"]').click()
            page.screenshot(path=str(out/"07_mobile.png"), full_page=True)
            report["steps"].append({"id": "mobile_390_no_page_overflow", "passed": True})
            assert not report["page_errors"], report["page_errors"]
            report["passed"] = True
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        (out/"browser_qa.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="../../05_evidence/pi9_pi10_2026-10-26/browser")
    args = p.parse_args()
    print(json.dumps(verify(args.out), indent=2, ensure_ascii=False))
