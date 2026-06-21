from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from fairflow_api import main as api


ARTIFACTS = {
    "walkthrough_pdf": ROOT / "output" / "pdf" / "fairflow_guardian_complete_walkthrough.pdf",
    "video_deck": ROOT / "output" / "presentation" / "fairflow_2_minute_video_deck.pptx",
    "video_script": ROOT / "output" / "presentation" / "fairflow_2_minute_video_script.txt",
    "deck_contact_sheet": ROOT / "output" / "presentation" / "fairflow_2min_video_contact_sheet.png",
    "desktop_screenshot": ROOT / "tmp" / "assets" / "fairflow_dashboard_latest.png",
}


def get_json(client: TestClient, path: str) -> dict[str, Any]:
    response = client.get(path)
    if response.status_code != 200:
        raise AssertionError(f"{path} returned {response.status_code}: {response.text[:300]}")
    return response.json()


def assert_artifact(name: str, path: Path, min_bytes: int) -> None:
    if not path.exists():
        raise AssertionError(f"{name} missing: {path}")
    size = path.stat().st_size
    if size < min_bytes:
        raise AssertionError(f"{name} looks too small: {path} has {size} bytes")


def main() -> None:
    client = TestClient(api.app)
    health = get_json(client, "/api/health")
    calm = get_json(client, "/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm")
    manipulated = get_json(client, "/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated")

    if calm["status"] != "approved":
        raise AssertionError(f"Calm demo should be approved, got {calm['status']}")
    if manipulated["final_action"] != "NO_TRADE":
        raise AssertionError(f"Manipulated demo should be NO_TRADE, got {manipulated['final_action']}")

    audit_hash = calm["audit_hash"]
    readiness = get_json(client, f"/api/audits/{audit_hash}/hackathon-readiness")
    submission = get_json(client, f"/api/audits/{audit_hash}/submission-kit")
    evidence = get_json(client, f"/api/audits/{audit_hash}/evidence-pack")
    router = get_json(client, f"/api/audits/{audit_hash}/execution-router")
    watchlist = get_json(
        client,
        "/api/watchlist?symbols=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT,ADAUSDT,DOGEUSDT&category=linear&scenario=calm",
    )

    if readiness["readiness_score"] < 80:
        raise AssertionError(f"Readiness score too low for final demo: {readiness['readiness_score']}")
    if evidence["verification_score"] < 85:
        raise AssertionError(f"Evidence score too low for final demo: {evidence['verification_score']}")
    if len(evidence["included_reports"]) < 8:
        raise AssertionError("Evidence pack is missing expected report bundle")
    if submission["total_runtime_seconds"] != 120 or len(submission["video_segments"]) != 6:
        raise AssertionError("Submission kit no longer matches the 2-minute, 6-slide deck")
    if not any("Competition Runway" in segment["narration"] for segment in submission["video_segments"]):
        raise AssertionError("Submission kit does not mention Competition Runway")
    if not any("no-trade" in item["label"].lower() for item in submission["final_checklist"]):
        raise AssertionError("Submission kit does not frame no-trade as a success state")
    if len(watchlist["items"]) < 8:
        raise AssertionError("Watchlist scanner did not return the full demo universe")

    assert_artifact("walkthrough_pdf", ARTIFACTS["walkthrough_pdf"], 500_000)
    assert_artifact("video_deck", ARTIFACTS["video_deck"], 900_000)
    assert_artifact("video_script", ARTIFACTS["video_script"], 900)
    assert_artifact("deck_contact_sheet", ARTIFACTS["deck_contact_sheet"], 100_000)
    assert_artifact("desktop_screenshot", ARTIFACTS["desktop_screenshot"], 100_000)

    script = ARTIFACTS["video_script"].read_text()
    word_count_line = next((line for line in script.splitlines() if line.startswith("Voiceover word count:")), "")
    word_count = int(word_count_line.rsplit(" ", 1)[-1])
    if word_count > 180:
        raise AssertionError(f"Voiceover is too rushed for 2 minutes: {word_count} words")

    result = {
        "status": "pass",
        "health": health,
        "audit_hash": audit_hash[:12],
        "calm": f"{calm['status']} / {calm['final_action']}",
        "manipulated": f"{manipulated['status']} / {manipulated['final_action']}",
        "readiness_score": round(readiness["readiness_score"], 1),
        "evidence_score": round(evidence["verification_score"], 1),
        "evidence_reports": len(evidence["included_reports"]),
        "router": router["recommended_route"],
        "watchlist_items": len(watchlist["items"]),
        "voiceover_words": word_count,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
