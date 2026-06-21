from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from fairflow_api import main as api


OUT = ROOT / "output" / "pdf" / "fairflow_guardian_judge_live_demo_walkthrough.pdf"
SUBMISSION_OUT = ROOT / "submission" / "docs" / "FairFlow_Guardian_judge_live_demo_walkthrough.pdf"
VOICEOVER_OUT = ROOT / "submission" / "video" / "FairFlow_Guardian_judge_live_demo_walkthrough_voiceover_male.txt"
PAYLOAD_OUT = ROOT / "tmp" / "judge_live_demo_walkthrough" / "payload.json"
ASSET_DIR = ROOT / "tmp" / "judge_live_demo_walkthrough"

SCREENSHOT = ROOT / "submission" / "screenshots" / "FairFlow_Guardian_dashboard_desktop.png"

PAGE_W = 13.333 * inch
PAGE_H = 7.5 * inch

BG = colors.HexColor("#06100D")
PANEL = colors.HexColor("#0B1B18")
PANEL_2 = colors.HexColor("#10251F")
PANEL_3 = colors.HexColor("#12202A")
MINT = colors.HexColor("#54F7B2")
MINT_DARK = colors.HexColor("#17A77A")
GOLD = colors.HexColor("#E5C451")
RED = colors.HexColor("#F37C72")
RED_DARK = colors.HexColor("#6B2423")
BLUE = colors.HexColor("#58B8FF")
WHITE = colors.HexColor("#F5FFF9")
MUTED = colors.HexColor("#A9B9B2")
LINE = colors.HexColor("#25433A")


def hex_color(value: str) -> colors.Color:
    return colors.HexColor(value)


def get_json(client: TestClient, path: str) -> dict[str, Any]:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def collect_payload() -> dict[str, Any]:
    client = TestClient(api.app)
    calm = get_json(client, "/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm")
    manipulated = get_json(client, "/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated")
    audit_hash = calm["audit_hash"]
    reports = {
        "readiness": get_json(client, f"/api/audits/{audit_hash}/hackathon-readiness"),
        "judge": get_json(client, f"/api/audits/{audit_hash}/judge-brief"),
        "evidence": get_json(client, f"/api/audits/{audit_hash}/evidence-pack"),
        "router": get_json(client, f"/api/audits/{audit_hash}/execution-router"),
        "receipt": get_json(client, f"/api/audits/{audit_hash}/receipt"),
        "anchor": get_json(client, f"/api/audits/{audit_hash}/anchor-proof"),
    }
    payload = {"calm": calm, "manipulated": manipulated, "reports": reports}
    PAYLOAD_OUT.parent.mkdir(parents=True, exist_ok=True)
    PAYLOAD_OUT.write_text(json.dumps(payload, indent=2))
    return payload


def prepare_assets() -> dict[str, Path]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.open(SCREENSHOT).convert("RGB")
    crops = {
        "dashboard": img,
        "top": img.crop((0, 0, img.width, min(360, img.height))),
        "runway": img.crop((70, 300, img.width - 80, min(770, img.height))),
        "decision": img.crop((70, 720, img.width - 80, img.height)),
    }
    out: dict[str, Path] = {}
    for name, crop in crops.items():
        path = ASSET_DIR / f"{name}.png"
        crop.save(path)
        out[name] = path
    return out


def fairness_score(report: dict[str, Any]) -> float:
    return float(report.get("fairness_passport", {}).get("score", 0.0))


def hidden_cost_bps(report: dict[str, Any]) -> float:
    return float(report.get("fairness_passport", {}).get("estimated_hidden_cost_bps", report.get("metrics", {}).get("spread_bps", 0.0)))


def liquidity_score(report: dict[str, Any]) -> float:
    return float(report.get("metrics", {}).get("liquidity_score", 0.0))


def anomaly_score(report: dict[str, Any]) -> float:
    return float(report.get("ai_committee", {}).get("anomaly", {}).get("score", 0.0))


def draw_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    size: float = 12,
    color: colors.Color = WHITE,
    font: str = "Helvetica",
    max_width: float | None = None,
    leading: float | None = None,
) -> float:
    c.setFont(font, size)
    c.setFillColor(color)
    leading = leading or size * 1.25
    if not max_width:
        c.drawString(x, y, text)
        return y - leading
    words = text.split()
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if c.stringWidth(trial, font, size) <= max_width:
            line = trial
        else:
            c.drawString(x, y, line)
            y -= leading
            line = word
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def rounded(c: canvas.Canvas, x: float, y: float, w: float, h: float, fill: colors.Color, stroke: colors.Color = LINE, r: float = 12) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, r, fill=1, stroke=1)


def pill(c: canvas.Canvas, text: str, x: float, y: float, fill: colors.Color, text_color: colors.Color = BG) -> None:
    w = max(70, c.stringWidth(text, "Helvetica-Bold", 9) + 24)
    rounded(c, x, y, w, 24, fill, fill, 12)
    draw_text(c, text, x + 12, y + 7, 9, text_color, "Helvetica-Bold")


def image(c: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float) -> None:
    rounded(c, x - 4, y - 4, w + 8, h + 8, colors.HexColor("#071612"), colors.HexColor("#1F463A"), 10)
    c.drawImage(ImageReader(str(path)), x, y, w, h, preserveAspectRatio=True, anchor="c", mask="auto")


def metric_card(c: canvas.Canvas, title: str, value: str, note: str, x: float, y: float, w: float, h: float, accent: colors.Color = MINT) -> None:
    rounded(c, x, y, w, h, PANEL_2)
    draw_text(c, title.upper(), x + 14, y + h - 22, 8, MUTED, "Helvetica-Bold")
    draw_text(c, value, x + 14, y + h - 50, 19, accent, "Helvetica-Bold")
    draw_text(c, note, x + 14, y + 16, 8, MUTED, "Helvetica", max_width=w - 28, leading=10)


def step_card(c: canvas.Canvas, num: str, title: str, body: str, x: float, y: float, w: float, h: float, accent: colors.Color = MINT) -> None:
    rounded(c, x, y, w, h, PANEL)
    rounded(c, x + 14, y + h - 38, 28, 28, accent, accent, 14)
    draw_text(c, num, x + 23, y + h - 30, 10, BG, "Helvetica-Bold")
    draw_text(c, title, x + 52, y + h - 28, 13, WHITE, "Helvetica-Bold", max_width=w - 66, leading=15)
    draw_text(c, body, x + 18, y + h - 58, 9.2, MUTED, "Helvetica", max_width=w - 36, leading=12)


def header(c: canvas.Canvas, page: int, title: str) -> None:
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(MINT)
    c.rect(0, PAGE_H - 6, PAGE_W * 0.42, 6, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(PAGE_W * 0.42, PAGE_H - 6, PAGE_W * 0.24, 6, fill=1, stroke=0)
    c.setFillColor(BLUE)
    c.rect(PAGE_W * 0.66, PAGE_H - 6, PAGE_W * 0.34, 6, fill=1, stroke=0)
    draw_text(c, "FairFlow Guardian live judge demo", 42, 24, 8.5, MUTED, "Helvetica-Bold")
    draw_text(c, f"Page {page}", PAGE_W - 86, 24, 8.5, MUTED, "Helvetica-Bold")
    draw_text(c, title, 42, PAGE_H - 38, 8.5, MUTED, "Helvetica-Bold")


def title(c: canvas.Canvas, text: str, subtitle: str, y: float = PAGE_H - 92, subtitle_width: float | None = None) -> float:
    y = draw_text(c, text, 42, y, 31, WHITE, "Helvetica-Bold", max_width=PAGE_W - 84, leading=34)
    y = draw_text(c, subtitle, 44, y - 4, 12.2, MUTED, "Helvetica", max_width=subtitle_width or PAGE_W - 120, leading=16)
    return y


def page_one(c: canvas.Canvas, payload: dict[str, Any], assets: dict[str, Path]) -> None:
    header(c, 1, "Opening frame")
    y = title(c, "Live Demo Walkthrough", "A judge-ready walkthrough of what to click, what changes, and why FairFlow is built around better systems, not bigger bets.", subtitle_width=500)
    calm = payload["calm"]
    readiness = payload["reports"]["readiness"]
    metric_card(c, "Readiness", f"{readiness['readiness_score']:.1f}/100", "Demo ready", 42, y - 95, 150, 76)
    metric_card(c, "Calm path", f"{calm['final_action']}", f"Fairness {fairness_score(calm):.0f}/100", 206, y - 95, 150, 76)
    metric_card(c, "Proof", "Audit hash", calm["audit_hash"][:12], 370, y - 95, 150, 76, GOLD)
    image(c, assets["dashboard"], 560, 96, 340, 380)
    draw_text(c, "Presenter move", 42, 206, 13, MINT, "Helvetica-Bold")
    draw_text(c, "Open with one sentence: FairFlow is a paper-only AI trading safety layer that proves when a market is fair enough for retail users and when no-trade is the healthiest action.", 42, 184, 10.5, MUTED, max_width=470, leading=14)


def page_two(c: canvas.Canvas, assets: dict[str, Path]) -> None:
    header(c, 2, "Step 1 - orient the judge")
    title(c, "Start At The Top Of The UI", "Show the judge that this is a live, inspectable trading system before discussing any strategy result.")
    image(c, assets["top"], 46, 126, 500, 250)
    step_card(c, "1", "Select symbol", "BTCUSDT is the default demo asset, but the dropdown also includes ETH, SOL, BNB, XRP, LINK, ADA, and DOGE.", 585, 346, 320, 74)
    step_card(c, "2", "Scenario tabs", "Use Calm to show guarded approval, then Manipulated to prove no-trade restraint.", 585, 256, 320, 74, GOLD)
    step_card(c, "3", "Telemetry strip", "Point to fairness, liquidity, spread, anomaly score, and the audit hash. These are the inputs the agents reason over.", 585, 166, 320, 74, BLUE)


def page_three(c: canvas.Canvas, assets: dict[str, Path], payload: dict[str, Any]) -> None:
    header(c, 3, "Step 2 - competition runway")
    title(c, "Use The Runway As The Judge Map", "This panel turns the hackathon criteria into a live demo path.")
    image(c, assets["runway"], 42, 124, 548, 300)
    readiness = payload["reports"]["readiness"]
    draw_text(c, "What to say", 620, 392, 13, MINT, "Helvetica-Bold")
    draw_text(c, "The score is not a return claim. It is a readiness signal across BGA ethos, technical depth, risk management, and transparency.", 620, 366, 10.5, MUTED, max_width=285, leading=14)
    metric_card(c, "BGA ethos", "87", "Fair-market infrastructure", 620, 250, 132, 76)
    metric_card(c, "Tech depth", "94", "Agents plus audit rails", 770, 250, 132, 76, BLUE)
    metric_card(c, "Risk", "79", "Guarded execution", 620, 150, 132, 76, GOLD)
    metric_card(c, "Transparency", "92", "Receipt and proof", 770, 150, 132, 76, MINT)


def page_four(c: canvas.Canvas, payload: dict[str, Any]) -> None:
    header(c, 4, "Step 3 - calm approval")
    title(c, "Calm Does Not Mean Unrestricted Trading", "In calm conditions, approval is small, paper-only, and conditional.", subtitle_width=760)
    calm = payload["calm"]
    metrics = [
        ("Action", calm["final_action"], "Paper-only strategy result"),
        ("Fairness", f"{fairness_score(calm):.0f}/100", "Retail participation score"),
        ("Hidden cost", f"{hidden_cost_bps(calm):.1f} bps", "Spread plus estimated friction"),
        ("Liquidity", f"{liquidity_score(calm):.0f}/100", "Market depth and route quality"),
    ]
    x = 52
    for i, (label, value, note) in enumerate(metrics):
        metric_card(c, label, str(value), note, x + i * 215, 316, 190, 88, MINT if i != 2 else GOLD)
    draw_text(c, "Click path", 62, 252, 14, MINT, "Helvetica-Bold")
    step_card(c, "1", "Click Show calm approval", "The UI returns to the approved calm path and refreshes the audit state.", 62, 150, 260, 86)
    step_card(c, "2", "Point to Paper execute", "This is paper execution only. It demonstrates guardrails without placing exchange orders.", 344, 150, 260, 86, GOLD)
    step_card(c, "3", "Explain conditional approval", "The trade is allowed only because fairness, cost, liquidity, anomaly, and stress checks stay inside policy.", 626, 150, 260, 86, BLUE)
    draw_text(c, "Judge takeaway: FairFlow can approve action, but the approval is narrow and auditable.", 62, 86, 14, WHITE, "Helvetica-Bold", max_width=820, leading=18)


def page_five(c: canvas.Canvas) -> None:
    header(c, 5, "Step 4 - explain the agents")
    title(c, "The Strategy Agent Does Not Act Alone", "FairFlow is agentic because multiple specialist agents can challenge, downgrade, or block the proposed action.")
    agents = [
        ("Strategy", "Proposes a direction and confidence."),
        ("Risk", "Checks sizing, volatility, and liquidation stress."),
        ("Manipulation", "Looks for spoofing, imbalance, and anomaly risk."),
        ("Execution", "Chooses post-only, TWAP, maker ladder, or no route."),
        ("Fairness", "Tests retail cohorts and hidden-cost burden."),
        ("Audit", "Turns the decision into a verifiable receipt."),
    ]
    positions = [(54, 318), (344, 318), (634, 318), (54, 190), (344, 190), (634, 190)]
    for idx, ((name, body), (x, y)) in enumerate(zip(agents, positions), start=1):
        step_card(c, str(idx), name, body, x, y, 250, 92, [MINT, GOLD, RED, BLUE, MINT, GOLD][idx - 1])
    draw_text(c, "What to say", 54, 124, 13, MINT, "Helvetica-Bold")
    draw_text(c, "This is not a thin API wrapper. The UI exposes a committee: proposal, critique, policy, route, fairness, red-team, and proof. The safest valid output can be no trade.", 54, 102, 10.5, MUTED, max_width=830, leading=14)


def page_six(c: canvas.Canvas, payload: dict[str, Any]) -> None:
    header(c, 6, "Step 5 - manipulated no-trade")
    title(c, "Switch To Manipulated And Let The System Refuse", "The strongest proof is that FairFlow can say no when market integrity gets worse.")
    manipulated = payload["manipulated"]
    rounded(c, 58, 296, 820, 150, RED_DARK, RED, 16)
    draw_text(c, "NO_TRADE", 86, 390, 34, WHITE, "Helvetica-Bold")
    draw_text(c, f"Fairness {fairness_score(manipulated):.0f}/100", 86, 358, 15, RED, "Helvetica-Bold")
    draw_text(c, f"Anomaly {anomaly_score(manipulated):.0f}/100", 300, 358, 15, RED, "Helvetica-Bold")
    draw_text(c, f"Liquidity {liquidity_score(manipulated):.0f}/100", 520, 358, 15, RED, "Helvetica-Bold")
    draw_text(c, "Click Show no-trade or the Manipulated tab. The route locks, paper execution is blocked, and the report explains the failed guardrails.", 86, 326, 11, WHITE, max_width=720, leading=14)
    step_card(c, "1", "Same asset", "BTCUSDT does not change. Only the market health changes.", 68, 178, 250, 82, GOLD)
    step_card(c, "2", "Different decision", "The agents block the trade because the market is no longer fair enough.", 344, 178, 250, 82, RED)
    step_card(c, "3", "No-trade is success", "The project is judged on safer systems, not forced execution.", 620, 178, 250, 82, MINT)


def page_seven(c: canvas.Canvas, payload: dict[str, Any]) -> None:
    header(c, 7, "Step 6 - evidence and proof")
    title(c, "Copy Proof, Then Show Why It Matters", "Each decision can be replayed from a receipt, evidence pack, and anchor payload.")
    audit_hash = payload["calm"]["audit_hash"]
    evidence = payload["reports"]["evidence"]
    anchor = payload["reports"]["anchor"]
    metric_card(c, "Audit hash", audit_hash[:12], "Current decision fingerprint", 54, 348, 246, 82, GOLD)
    metric_card(c, "Evidence score", f"{evidence['verification_score']}/100", "Reports linked to the audit", 326, 348, 246, 82, MINT)
    metric_card(c, "Anchor proof", anchor["payload_hash"][:12], "Contract-ready payload hash", 598, 348, 246, 82, BLUE)
    routes = [
        "/evidence-pack",
        "/receipt",
        "/execution-router",
        "/policy-stress",
        "/anchor-proof",
    ]
    y = 268
    draw_text(c, "Proof surfaces to open", 58, y, 14, MINT, "Helvetica-Bold")
    y -= 28
    for route in routes:
        rounded(c, 58, y - 4, 780, 30, PANEL_3, LINE, 8)
        draw_text(c, f"/api/audits/{audit_hash[:12]}...{route}", 76, y + 6, 9.5, MUTED, "Courier")
        y -= 40
    draw_text(c, "Judge takeaway: the demo does not ask for trust. It gives a verification trail.", 58, 58, 13, WHITE, "Helvetica-Bold")


def page_eight(c: canvas.Canvas) -> None:
    header(c, 8, "Two-minute video map")
    title(c, "A Natural 2-Minute Presentation Flow", "This PDF is designed to become a short narrated video without sounding like a feature checklist.")
    beats = [
        ("0:00-0:15", "Thesis", "FairFlow proves when a market is fair enough for retail users."),
        ("0:15-0:35", "UI orientation", "Show symbol, scenario tabs, telemetry, readiness, and audit hash."),
        ("0:35-0:55", "Calm path", "Explain guarded paper approval and conditional execution."),
        ("0:55-1:20", "Agents", "Strategy proposes; risk, fairness, route, red-team, and audit agents challenge."),
        ("1:20-1:45", "No-trade proof", "Switch to manipulated and show the refusal as a successful safety outcome."),
        ("1:45-2:00", "Close", "Evidence pack, receipt, anchor proof, and BGA alignment."),
    ]
    y = 346
    for time, label, body in beats:
        rounded(c, 58, y, 830, 42, PANEL, LINE, 10)
        draw_text(c, time, 76, y + 24, 10, GOLD, "Helvetica-Bold")
        draw_text(c, label, 184, y + 24, 11, WHITE, "Helvetica-Bold")
        draw_text(c, body, 318, y + 24, 9.4, MUTED, "Helvetica", max_width=530, leading=11)
        y -= 52
    draw_text(c, "Closing line", 58, 68, 12, MINT, "Helvetica-Bold")
    draw_text(c, "FairFlow is not bigger bets. It is better market infrastructure: explainable, risk-aware, and verifiable.", 164, 68, 11, WHITE, "Helvetica-Bold", max_width=720, leading=14)


def build_pdf() -> None:
    payload = collect_payload()
    assets = prepare_assets()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=(PAGE_W, PAGE_H))
    pages = [
        lambda: page_one(c, payload, assets),
        lambda: page_two(c, assets),
        lambda: page_three(c, assets, payload),
        lambda: page_four(c, payload),
        lambda: page_five(c),
        lambda: page_six(c, payload),
        lambda: page_seven(c, payload),
        lambda: page_eight(c),
    ]
    for render in pages:
        render()
        c.showPage()
    c.save()
    SUBMISSION_OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT, SUBMISSION_OUT)
    VOICEOVER_OUT.parent.mkdir(parents=True, exist_ok=True)
    VOICEOVER_OUT.write_text(
        "FairFlow Guardian is a live demo of safer AI trading infrastructure for the BGA AI Trading and Strategy Track.\n\n"
        "Start at the top of the dashboard. The judge sees the asset, scenario tabs, market telemetry, fairness score, liquidity, spread, anomaly risk, and an audit hash. This is not a hidden bot. It is an inspectable decision surface.\n\n"
        "Next, use the Competition Runway. The readiness score is not a profit claim. It maps the demo to BGA ethos, technical depth, risk management, and transparency.\n\n"
        "In the calm path, FairFlow may approve a small paper trade. But approval is conditional. The system checks hidden cost, liquidity, volatility, liquidation stress, manipulation risk, and retail fairness before the paper route is allowed.\n\n"
        "Then explain the agents. The strategy agent can propose, but risk, manipulation, execution, fairness, red-team, and audit agents can challenge or block the action.\n\n"
        "Now switch to the manipulated path. Same asset, weaker market integrity. FairFlow blocks the trade, locks execution, and explains which guardrails failed. This is the key product choice: no trade is a successful safety outcome.\n\n"
        "Close with proof. Copy the evidence pack, receipt, route analysis, and anchor payload. FairFlow reduces information asymmetry by making every decision explainable, auditable, and easier for retail users to challenge.\n"
    )


if __name__ == "__main__":
    build_pdf()
    print(OUT)
    print(SUBMISSION_OUT)
    print(VOICEOVER_OUT)
