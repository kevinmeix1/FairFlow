from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from fairflow_api import main as api


OUT = ROOT / "output" / "pdf" / "fairflow_guardian_complete_walkthrough.pdf"
DATA_OUT = ROOT / "tmp" / "pdfs" / "walkthrough_payload.json"
SCREENSHOT_CANDIDATES = [
    ROOT / "tmp" / "assets" / "fairflow_dashboard_latest.png",
    ROOT / "tmp" / "assets" / "fairflow_dashboard_ui_polish.png",
    ROOT / "tmp" / "assets" / "fairflow_dashboard.png",
]

PAGE_W, PAGE_H = letter
MARGIN = 44

INK = colors.HexColor("#14221D")
MUTED = colors.HexColor("#60716B")
GREEN = colors.HexColor("#176D5D")
GREEN_DARK = colors.HexColor("#0E4F43")
GREEN_SOFT = colors.HexColor("#E4F4EC")
BLUE = colors.HexColor("#24536D")
BLUE_SOFT = colors.HexColor("#E6F2F8")
YELLOW = colors.HexColor("#A96F12")
YELLOW_SOFT = colors.HexColor("#FFF4CD")
RED = colors.HexColor("#B34A3F")
RED_SOFT = colors.HexColor("#FFE8E2")
LINE = colors.HexColor("#D7DFD9")
WHITE = colors.white


def get_json(client: TestClient, path: str) -> dict[str, Any]:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def post_json(client: TestClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def collect_payload() -> dict[str, Any]:
    client = TestClient(api.app)
    decisions = {
        scenario: get_json(client, f"/api/analysis?symbol=BTCUSDT&category=linear&scenario={scenario}")
        for scenario in ("calm", "volatile", "manipulated")
    }
    calm_hash = decisions["calm"]["audit_hash"]
    manipulated_hash = decisions["manipulated"]["audit_hash"]

    reports = {
        "readiness": get_json(client, f"/api/audits/{calm_hash}/hackathon-readiness"),
        "readiness_manipulated": get_json(client, f"/api/audits/{manipulated_hash}/hackathon-readiness"),
        "submission": get_json(client, f"/api/audits/{calm_hash}/submission-kit"),
        "judge": get_json(client, f"/api/audits/{calm_hash}/judge-brief"),
        "evidence": get_json(client, f"/api/audits/{calm_hash}/evidence-pack"),
        "provenance": get_json(client, f"/api/audits/{calm_hash}/model-provenance"),
        "router": get_json(client, f"/api/audits/{calm_hash}/execution-router"),
        "policy_stress": get_json(client, f"/api/audits/{calm_hash}/policy-stress"),
        "counterfactuals": get_json(client, f"/api/audits/{calm_hash}/counterfactuals"),
        "red_team": get_json(client, f"/api/audits/{calm_hash}/red-team"),
        "receipt": get_json(client, f"/api/audits/{calm_hash}/receipt"),
        "cohorts": get_json(client, f"/api/audits/{calm_hash}/retail-cohorts"),
        "anchor": get_json(client, f"/api/audits/{calm_hash}/anchor-proof"),
        "mission": get_json(client, f"/api/agents/mission?audit_hash={calm_hash}"),
        "impact": get_json(client, "/api/impact?limit=50"),
        "watchlist": get_json(client, "/api/watchlist?symbols=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT,ADAUSDT,DOGEUSDT&category=linear&scenario=calm"),
        "risk_size": post_json(
            client,
            "/api/risk/size",
            {
                "audit_hash": calm_hash,
                "account_equity_usdt": 10000,
                "risk_budget_pct": 1,
                "max_notional_pct": 25,
            },
        ),
    }
    payload = {"decisions": decisions, "reports": reports}
    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUT.write_text(json.dumps(payload, indent=2))
    return payload


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="CoverTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=34,
        leading=38,
        textColor=GREEN_DARK,
        spaceAfter=12,
    )
)
styles.add(
    ParagraphStyle(
        name="H1x",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=25,
        textColor=GREEN_DARK,
        spaceBefore=4,
        spaceAfter=10,
    )
)
styles.add(
    ParagraphStyle(
        name="H2x",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        textColor=BLUE,
        spaceBefore=8,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="Bodyx",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.6,
        leading=13.2,
        textColor=INK,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="Smallx",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.1,
        leading=10.8,
        textColor=MUTED,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="Calloutx",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=10.2,
        leading=14,
        textColor=GREEN_DARK,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="Centerx",
        parent=styles["BodyText"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=INK,
    )
)


def p(text: str, style: str = "Bodyx") -> Paragraph:
    return Paragraph(escape(str(text)), styles[style])


def bullet(text: str) -> Paragraph:
    return p(f"- {text}", "Bodyx")


def small(text: str) -> Paragraph:
    return p(text, "Smallx")


def current_screenshot() -> Path | None:
    for path in SCREENSHOT_CANDIDATES:
        if path.exists():
            return path
    return None


def fitted_image(path: Path, max_width: float, max_height: float) -> Image:
    width_px, height_px = ImageReader(str(path)).getSize()
    scale = min(max_width / width_px, max_height / height_px)
    img = Image(str(path), width=width_px * scale, height=height_px * scale)
    img.hAlign = "CENTER"
    return img


def section(title: str, subtitle: str | None = None) -> list[Any]:
    out: list[Any] = [p(title, "H1x")]
    if subtitle:
        out.append(p(subtitle, "Calloutx"))
    return out


def card_table(rows: list[list[Any]], widths: list[float], fill=WHITE) -> Table:
    table = Table(rows, colWidths=widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E7ECE7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def metric_grid(metrics: list[tuple[str, str, str]]) -> Table:
    cells = []
    for label, value, note in metrics:
        cells.append([p(label.upper(), "Smallx"), p(value, "H2x"), small(note)])
    table = Table([cells], colWidths=[1.75 * inch] * len(cells), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), GREEN_SOFT),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def scenario_table(decisions: dict[str, Any]) -> Table:
    rows = [[p("Scenario", "Calloutx"), p("Decision", "Calloutx"), p("Fairness", "Calloutx"), p("Liquidity", "Calloutx"), p("Why it matters", "Calloutx")]]
    for name, decision in decisions.items():
        rows.append(
            [
                p(name.title(), "Bodyx"),
                p(f"{decision['status']} / {decision['final_action']}", "Bodyx"),
                p(f"{decision['fairness_passport']['score']:.0f}/100", "Bodyx"),
                p(f"{decision['metrics']['liquidity_score']:.0f}/100", "Bodyx"),
                p(decision["summary"], "Smallx"),
            ]
        )
    return card_table(rows, [0.9 * inch, 1.1 * inch, 0.85 * inch, 0.85 * inch, 3.2 * inch])


def criterion_table(criteria: list[dict[str, Any]]) -> Table:
    rows = [[p("Criterion", "Calloutx"), p("Score", "Calloutx"), p("What to show", "Calloutx"), p("Proof", "Calloutx")]]
    for item in criteria:
        rows.append(
            [
                p(item["category"].replace("_", " ").title(), "Bodyx"),
                p(f"{item['readiness_score']:.0f}/100 - {item['status']}", "Bodyx"),
                p(item["judge_angle"], "Smallx"),
                p(", ".join(item["proof_urls"][:2]), "Smallx"),
            ]
        )
    return card_table(rows, [1.1 * inch, 1.0 * inch, 2.45 * inch, 2.35 * inch])


def runbook_table(steps: list[dict[str, Any]]) -> Table:
    rows = [[p("Step", "Calloutx"), p("Action", "Calloutx"), p("Underlying mechanism", "Calloutx"), p("Proof", "Calloutx")]]
    for step in steps:
        rows.append(
            [
                p(f"{step['step']}. {step['title']}", "Bodyx"),
                p(step["ui_action"], "Smallx"),
                p(step["underlying_mechanism"], "Smallx"),
                p(step["proof_url"] or "Live dashboard", "Smallx"),
            ]
        )
    return card_table(rows, [1.2 * inch, 1.7 * inch, 2.55 * inch, 1.45 * inch])


def route_table(router: dict[str, Any]) -> Table:
    rows = [[p("Route", "Calloutx"), p("Status", "Calloutx"), p("Slippage", "Calloutx"), p("Fairness", "Calloutx"), p("Reason", "Calloutx")]]
    for route in router["route_candidates"]:
        rows.append(
            [
                p(route["name"], "Bodyx"),
                p(route["status"], "Smallx"),
                p(f"{route['expected_slippage_bps']:.1f} bps", "Smallx"),
                p(f"{route['retail_fairness_score']:.0f}/100", "Smallx"),
                p(route["reason"], "Smallx"),
            ]
        )
    return card_table(rows, [1.45 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch, 2.85 * inch])


def red_team_table(red_team: dict[str, Any]) -> Table:
    rows = [[p("Probe", "Calloutx"), p("Status", "Calloutx"), p("Trigger", "Calloutx"), p("Mitigation", "Calloutx")]]
    for probe in red_team["probes"]:
        rows.append(
            [
                p(probe["name"], "Bodyx"),
                p(probe["status"], "Smallx"),
                p(probe["first_trigger"], "Smallx"),
                p(probe["mitigation"], "Smallx"),
            ]
        )
    return card_table(rows, [1.35 * inch, 0.75 * inch, 1.35 * inch, 3.35 * inch])


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(GREEN_DARK)
    canvas.rect(0, PAGE_H - 18, PAGE_W * 0.42, 18, fill=True, stroke=False)
    canvas.setFillColor(YELLOW)
    canvas.rect(PAGE_W * 0.42, PAGE_H - 18, PAGE_W * 0.22, 18, fill=True, stroke=False)
    canvas.setFillColor(BLUE)
    canvas.rect(PAGE_W * 0.64, PAGE_H - 18, PAGE_W * 0.36, 18, fill=True, stroke=False)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 25, "FairFlow Guardian - Complete Walkthrough")
    canvas.drawRightString(PAGE_W - MARGIN, 25, f"Page {doc.page}")
    canvas.restoreState()


def add_cover(story: list[Any], payload: dict[str, Any]):
    reports = payload["reports"]
    readiness = reports["readiness"]
    decision = payload["decisions"]["calm"]
    story.append(Spacer(1, 0.45 * inch))
    story.append(p("FairFlow Guardian", "CoverTitle"))
    story.append(
        p(
            "Complete hackathon walkthrough for the BGA AI Trading & Strategy Track",
            "H1x",
        )
    )
    story.append(
        p(
            "This PDF explains what the project does, how the app should be demoed, and how the underlying agents, fairness checks, risk controls, competition runway, route router, evidence pack, and audit proofs fit together.",
            "Calloutx",
        )
    )
    story.append(
        p(
            "Hackathon Readiness Runbook: a judge-facing guide mapped to BGA ethos, technical depth, strategy design, risk management, transparency, and verifiability.",
            "Bodyx",
        )
    )
    story.append(Spacer(1, 0.2 * inch))
    story.append(
        metric_grid(
            [
                ("Readiness", f"{readiness['readiness_score']:.1f}/100", readiness["verdict"].replace("_", " ")),
                ("Current audit", decision["audit_hash"][:12], f"{decision['status']} / {decision['final_action']}"),
                ("Route", reports["router"]["recommended_route"], reports["router"]["verdict"].replace("_", " ")),
            ]
        )
    )
    story.append(Spacer(1, 0.2 * inch))
    story.append(p(readiness["final_30_second_pitch"], "Bodyx"))
    screenshot = current_screenshot()
    if screenshot:
        story.append(Spacer(1, 0.18 * inch))
        story.append(fitted_image(screenshot, 6.75 * inch, 2.7 * inch))
    story.append(PageBreak())


def build_story(payload: dict[str, Any]) -> list[Any]:
    decisions = payload["decisions"]
    reports = payload["reports"]
    readiness = reports["readiness"]
    submission = reports["submission"]
    judge = reports["judge"]
    evidence = reports["evidence"]
    provenance = reports["provenance"]
    router = reports["router"]
    policy = reports["policy_stress"]
    counterfactuals = reports["counterfactuals"]
    red_team = reports["red_team"]
    receipt = reports["receipt"]
    cohorts = reports["cohorts"]
    anchor = reports["anchor"]
    mission = reports["mission"]
    impact = reports["impact"]
    risk_size = reports["risk_size"]

    story: list[Any] = []
    add_cover(story, payload)

    story += section(
        "1. Executive Summary",
        "FairFlow Guardian is a trading safety layer, not a profit-maximizing black box.",
    )
    for claim in readiness["strongest_claims"]:
        story.append(bullet(claim))
    story.append(Spacer(1, 0.1 * inch))
    story.append(p("Current calm audit:", "H2x"))
    story.append(
        metric_grid(
            [
                ("Final action", decisions["calm"]["final_action"], decisions["calm"]["status"]),
                ("Fairness", f"{decisions['calm']['fairness_passport']['score']:.0f}/100", decisions["calm"]["fairness_passport"]["verdict"]),
                ("Hidden cost", f"{decisions['calm']['fairness_passport']['estimated_hidden_cost_bps']:.1f} bps", "spread plus impact pressure"),
            ]
        )
    )
    story += [PageBreak()]

    story += section("2. Hackathon Readiness Runbook", "Use this sequence when a judge asks what the project does.")
    story.append(criterion_table(readiness["criteria"]))
    story.append(Spacer(1, 0.12 * inch))
    story.append(p("Start from the Competition Runway panel in the dashboard: it collects the BGA thesis, proof-copy action, readiness score, evidence pack status, route proof, and calm/no-trade scenario controls in one judge-friendly surface.", "Bodyx"))
    story.append(Spacer(1, 0.08 * inch))
    story.append(p("Recommended opening line", "H2x"))
    story.append(p(judge["recommended_opening"], "Bodyx"))
    story.append(p("The detailed runbook spans the next pages. Every step has a UI action, expected result, underlying mechanism, and proof URL.", "Bodyx"))
    story.append(PageBreak())

    steps = readiness["runbook_steps"]
    for idx in range(0, len(steps), 4):
        story += section(f"3.{idx // 4 + 1} Step-by-Step Runbook", "Follow these actions in the dashboard and explain the mechanism under each surface.")
        story.append(runbook_table(steps[idx : idx + 4]))
        story.append(PageBreak())

    story += section("4. Architecture And Data Flow", "The architecture separates data intake, strategy proposal, independent review, route gating, and evidence packaging.")
    architecture_rows = [
        ["Layer", "What happens", "Why it matters"],
        ["Market data", "Bybit public data or deterministic fallback snapshots create candles, book levels, ticker fields, funding, and open interest.", "The demo remains stable while still supporting live public data."],
        ["Feature engineering", "Spread, depth, impact, volatility, RSI, momentum, wick pressure, book imbalance, funding, and liquidity score are derived.", "The model reasons over explicit market structure, not vague chart vibes."],
        ["Agents", "Strategy, risk, manipulation, regime, forecast, backtest, planner, memory, narrator, fairness, and route steward checks debate the setup.", "The strategy proposer cannot execute by itself."],
        ["Verifier layer", "Receipt, cohorts, provenance, router, policy stress, counterfactuals, red-team, anchor proof, evidence pack, and readiness runbook are generated from one audit hash.", "Judges can verify claims without trusting the UI."],
    ]
    story.append(card_table([[p(cell, "Calloutx") if i == 0 else p(cell, "Bodyx") for i, cell in enumerate(row)] for row in architecture_rows], [1.15 * inch, 3.35 * inch, 2.35 * inch]))
    story.append(PageBreak())

    story += section("5. Scenario Lab", "The project proves selectivity: the same system can approve, observe, or block depending on market quality.")
    story.append(scenario_table(decisions))
    story.append(Spacer(1, 0.12 * inch))
    story.append(p("Interpretation", "H2x"))
    story.append(p("A calm audit may allow guarded paper execution, while volatile and manipulated scenarios demonstrate restraint. No-trade is a product feature because it records why market structure is unhealthy.", "Bodyx"))
    story.append(PageBreak())

    story += section("6. Fairness Passport And Retail Inclusion", "Fairness is scored before execution is discussed.")
    story.append(
        metric_grid(
            [
                ("Receipt", f"{receipt['bga_alignment_score']:.1f}/100", "BGA alignment"),
                ("Cohorts", cohorts["verdict"], f"{cohorts['pass_count']} pass / {cohorts['watch_count']} watch / {cohorts['block_count']} block"),
                ("Hidden cost", f"{decisions['calm']['fairness_passport']['estimated_hidden_cost_bps']:.1f} bps", "retail friction"),
            ]
        )
    )
    for check in decisions["calm"]["fairness_passport"]["checks"]:
        story.append(bullet(f"{check['name']}: {check['status']} - {check['explanation']}"))
    story.append(PageBreak())

    story += section("7. Model And Data Provenance", "The project documents what is live, what is derived, and what is only a prototype signal.")
    rows = [[p("Component", "Calloutx"), p("Type", "Calloutx"), p("Inputs", "Calloutx"), p("Limits", "Calloutx")]]
    for component in provenance["model_components"]:
        rows.append(
            [
                p(component["name"], "Bodyx"),
                p(component["component_type"], "Smallx"),
                p(", ".join(component["inputs"][:3]), "Smallx"),
                p(component["limitations"][0], "Smallx"),
            ]
        )
    story.append(card_table(rows, [1.45 * inch, 0.95 * inch, 1.85 * inch, 2.65 * inch]))
    story.append(PageBreak())

    story += section("8. Risk Sizing And Policy Stress", "Risk controls are applied before any paper route can proceed.")
    story.append(
        metric_grid(
            [
                ("Sizing", f"${risk_size['recommended_notional_usdt']:,.0f}", risk_size["message"]),
                ("Policy stress", policy["resilience_verdict"].replace("_", " "), f"{policy['stability_score']:.1f}/100 stability"),
                ("Allowed policies", f"{policy['execution_allowed_count']}/3", "access-first, balanced, strict"),
            ]
        )
    )
    for outcome in policy["outcomes"]:
        story.append(bullet(f"{outcome['name']}: {outcome['report']['verdict']} - first breaking check: {outcome['first_breaking_check'] or 'none'}"))
    story.append(PageBreak())

    story += section("9. Fair Execution Router", "The router asks whether the execution method itself is fair enough for retail paper routing.")
    story.append(route_table(router))
    story.append(Spacer(1, 0.1 * inch))
    story.append(p("Router proof", "H2x"))
    story.append(p(router["summary"], "Bodyx"))
    for note in router["verification_notes"]:
        story.append(bullet(note))
    story.append(PageBreak())

    story += section("10. Counterfactual Fairness Lab", "The lab explains what must actually improve before a future audit can be safer.")
    story.append(
        metric_grid(
            [
                ("Verdict", counterfactuals["verdict"].replace("_", " "), f"{counterfactuals['readiness_score']:.1f}/100 readiness"),
                ("Top blocker", counterfactuals["top_blocker"], "largest guardrail gap"),
                ("Unlockable", "Yes" if counterfactuals["unlockable_in_current_audit"] else "No", "current audit state"),
            ]
        )
    )
    for lever in counterfactuals["levers"]:
        story.append(bullet(f"{lever['name']}: {lever['status']} - current {lever['current_value']} target {lever['target_value']}"))
    story.append(PageBreak())

    story += section("11. Market Integrity Red Team", "Adversarial probes show where the system halts under worse market structure.")
    story.append(red_team_table(red_team))
    story.append(Spacer(1, 0.1 * inch))
    story.append(p(red_team["judge_takeaway"], "Calloutx"))
    story.append(PageBreak())

    story += section("12. Evidence Pack And Audit Hash", "The evidence pack is the machine-readable verifier artifact for a single audit hash.")
    story.append(
        metric_grid(
            [
                ("Verification", f"{evidence['verification_score']:.1f}/100", evidence["package_version"]),
                ("Reports", str(len(evidence["included_reports"])), "nested proof artifacts"),
                ("Claims", str(len(evidence["core_claims"])), "verified, watch, blocked"),
            ]
        )
    )
    rows = [[p("Claim", "Calloutx"), p("Status", "Calloutx"), p("Explanation", "Calloutx")]]
    for claim in evidence["core_claims"]:
        rows.append([p(claim["label"], "Bodyx"), p(claim["status"], "Smallx"), p(claim["explanation"], "Smallx")])
    story.append(card_table(rows, [1.8 * inch, 0.8 * inch, 4.25 * inch]))
    story.append(PageBreak())

    story += section("13. On-chain Audit Anchor", "Blockchain is used as a verification handoff, not as live trading or custody.")
    story.append(p(f"Contract: {anchor['contract_name']} in {anchor['contract_file']}", "Bodyx"))
    story.append(p(f"Function: {anchor['function_signature']}", "Bodyx"))
    story.append(p(f"Decision hash: {anchor['decision_hash_bytes32']}", "Smallx"))
    story.append(p(f"Payload hash: {anchor['payload_hash']}", "Smallx"))
    for step in anchor["verification_steps"]:
        story.append(bullet(step))
    story.append(PageBreak())

    story += section("14. Agentic Mission Control", "The project is agentic, but bounded by guardrails and paper-only actions.")
    rows = [[p("Agent", "Calloutx"), p("Status", "Calloutx"), p("Finding", "Calloutx")]]
    for task in mission["tasks"]:
        rows.append([p(task["agent"], "Bodyx"), p(task["status"], "Smallx"), p(task["finding"], "Smallx")])
    story.append(card_table(rows, [1.45 * inch, 0.8 * inch, 4.55 * inch]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(p(f"Final recommendation: {mission['final_recommendation']}", "Calloutx"))
    story.append(PageBreak())

    story += section("15. Watchlist And Impact Ledger", "The project can scan a crypto universe and summarize cumulative market-health evidence.")
    watchlist = reports["watchlist"]
    rows = [[p("Symbol", "Calloutx"), p("Rank score", "Calloutx"), p("Fairness", "Calloutx"), p("Reason", "Calloutx")]]
    for item in watchlist["items"][:6]:
        rows.append([p(item["symbol"], "Bodyx"), p(f"{item['rank_score']:.1f}", "Smallx"), p(f"{item['fairness_score']:.0f}/100", "Smallx"), p(item["rank_reason"], "Smallx")])
    story.append(card_table(rows, [0.85 * inch, 0.95 * inch, 0.85 * inch, 4.2 * inch]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(p(impact["summary"], "Bodyx"))
    story.append(PageBreak())

    story += section("16. Submission Kit And 2-Minute Video Handoff", "This is the final judge-facing package for recording and submitting the project.")
    story.append(
        metric_grid(
            [
                ("Runtime", f"{submission['total_runtime_seconds']} sec", f"{len(submission['video_segments'])} video segments"),
                ("Assets", str(len(submission["submission_assets"])), "PDF, deck, script, endpoint, anchor"),
                ("Checklist", str(len(submission["final_checklist"])), "submission readiness checks"),
            ]
        )
    )
    rows = [[p("Time", "Calloutx"), p("Segment", "Calloutx"), p("Dashboard action", "Calloutx")]]
    for segment in submission["video_segments"]:
        rows.append([p(segment["timecode"], "Bodyx"), p(segment["title"], "Bodyx"), p(segment["dashboard_action"], "Smallx")])
    story.append(card_table(rows, [0.85 * inch, 1.2 * inch, 4.8 * inch]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(p("Required submission assets", "H2x"))
    for asset in submission["submission_assets"]:
        if asset["required"]:
            story.append(bullet(f"{asset['label']}: {asset['path']}"))
    story.append(PageBreak())

    story += section("17. Testing, Boundaries, And Honest Limitations", "This is where the project earns trust by saying what it does not do.")
    story.append(p("Validation run by the project:", "H2x"))
    story.append(bullet("Backend API tests cover audit lookup, receipts, cohorts, anchor proof, judge brief, readiness runbook, provenance, counterfactuals, router, red team, evidence pack, scenario comparison, market series, risk sizing, portfolio, mission control, watchlist, and policy evaluation."))
    story.append(bullet("Frontend production build validates TypeScript contracts and the Next.js dashboard bundle."))
    story.append(bullet("Browser checks confirm the readiness and router panels render, buttons work, and mobile layout avoids horizontal overflow."))
    story.append(p("Known limitations:", "H2x"))
    for limitation in readiness["known_limitations"]:
        story.append(bullet(limitation))
    story.append(PageBreak())

    story += section("18. Final Demo Script", "Use this exact closing sequence.")
    story.append(p(readiness["final_30_second_pitch"], "Calloutx"))
    story.append(p("Close by switching to Manipulated. Say that this is not a failed trade. This is FairFlow doing its job: refusing execution, recording the reasons, and preserving proof that the decision was made before the outcome.", "Bodyx"))
    story.append(p("Proof links to copy during judging:", "H2x"))
    for link in readiness["proof_links"]:
        story.append(small(link))

    return story


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = collect_payload()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=letter,
        rightMargin=MARGIN,
        leftMargin=MARGIN,
        topMargin=58,
        bottomMargin=48,
        title="FairFlow Guardian Complete Walkthrough",
    )
    story = build_story(payload)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(OUT)


if __name__ == "__main__":
    build()
