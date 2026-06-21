from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from fairflow_api import main as api


OUT = ROOT / "output" / "pdf" / "fairflow_live_demo_runbook.pdf"
DATA_OUT = ROOT / "tmp" / "pdfs" / "live_demo_payload.json"
SCREENSHOTS = [
    ROOT / "tmp" / "assets" / "fairflow_dashboard_latest.png",
    ROOT / "tmp" / "assets" / "fairflow_dashboard.png",
]

PAGE_W, PAGE_H = landscape(letter)
MARGIN = 34

INK = colors.HexColor("#14221D")
MUTED = colors.HexColor("#60716B")
GREEN = colors.HexColor("#0E4F43")
GREEN_2 = colors.HexColor("#176D5D")
MINT = colors.HexColor("#DFF2E8")
BLUE = colors.HexColor("#24536D")
BLUE_SOFT = colors.HexColor("#E4F1F7")
GOLD = colors.HexColor("#B87812")
GOLD_SOFT = colors.HexColor("#FFF2C7")
RED = colors.HexColor("#B34A3F")
RED_SOFT = colors.HexColor("#FFE7E0")
LINE = colors.HexColor("#D5DED8")
WHITE = colors.white


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
        "submission": get_json(client, f"/api/audits/{audit_hash}/submission-kit"),
        "evidence": get_json(client, f"/api/audits/{audit_hash}/evidence-pack"),
        "router": get_json(client, f"/api/audits/{audit_hash}/execution-router"),
        "receipt": get_json(client, f"/api/audits/{audit_hash}/receipt"),
        "anchor": get_json(client, f"/api/audits/{audit_hash}/anchor-proof"),
    }
    payload = {"calm": calm, "manipulated": manipulated, "reports": reports}
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
        textColor=GREEN,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="H1x",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=27,
        textColor=GREEN,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="H2x",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=BLUE,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="Bodyx",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=12.4,
        textColor=INK,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="Smallx",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.6,
        leading=9.6,
        textColor=MUTED,
        spaceAfter=2,
    )
)
styles.add(
    ParagraphStyle(
        name="Calloutx",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=10.4,
        leading=13.2,
        textColor=GREEN,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="Headerx",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9.2,
        leading=11.5,
        textColor=WHITE,
        spaceAfter=0,
    )
)
styles.add(
    ParagraphStyle(
        name="Centerx",
        parent=styles["BodyText"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=INK,
    )
)


def p(text: Any, style: str = "Bodyx") -> Paragraph:
    return Paragraph(escape(str(text)), styles[style])


def small(text: Any) -> Paragraph:
    return p(text, "Smallx")


def bullet(text: str) -> Paragraph:
    return p(f"- {text}", "Bodyx")


def section(story: list[Any], title: str, subtitle: str | None = None) -> None:
    story.append(p(title, "H1x"))
    if subtitle:
        story.append(p(subtitle, "Calloutx"))


def table(rows: list[list[Any]], widths: list[float], fill=WHITE, header=True) -> Table:
    converted = []
    for row_index, row in enumerate(rows):
        converted.append([cell if hasattr(cell, "wrap") else p(cell, "Headerx" if header and row_index == 0 else "Bodyx") for cell in row])
    t = Table(converted, colWidths=widths, hAlign="LEFT", repeatRows=1 if header else 0)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("BACKGROUND", (0, 0), (-1, 0), GREEN if header else fill),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE if header else INK),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E6ECE8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def metric_grid(metrics: list[tuple[str, str, str]], fills: list[Any] | None = None) -> Table:
    rows = []
    for label, value, note in metrics:
        rows.append([small(label.upper()), p(value, "H2x"), small(note)])
    t = Table([rows], colWidths=[1.7 * inch] * len(rows), hAlign="LEFT")
    commands = [
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]
    for idx in range(len(rows)):
        commands.append(("BACKGROUND", (idx, 0), (idx, 0), fills[idx] if fills else MINT))
    t.setStyle(TableStyle(commands))
    return t


def current_screenshot() -> Path | None:
    for path in SCREENSHOTS:
        if path.exists():
            return path
    return None


def fitted_image(path: Path, max_width: float, max_height: float) -> Image:
    width_px, height_px = ImageReader(str(path)).getSize()
    scale = min(max_width / width_px, max_height / height_px)
    img = Image(str(path), width=width_px * scale, height=height_px * scale)
    img.hAlign = "CENTER"
    return img


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(GREEN)
    canvas.rect(0, PAGE_H - 14, PAGE_W * 0.42, 14, fill=True, stroke=False)
    canvas.setFillColor(GOLD)
    canvas.rect(PAGE_W * 0.42, PAGE_H - 14, PAGE_W * 0.2, 14, fill=True, stroke=False)
    canvas.setFillColor(BLUE)
    canvas.rect(PAGE_W * 0.62, PAGE_H - 14, PAGE_W * 0.38, 14, fill=True, stroke=False)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 20, "FairFlow Guardian - Live Demo Runbook")
    canvas.drawRightString(PAGE_W - MARGIN, 20, f"Page {doc.page}")
    canvas.restoreState()


def add_cover(story: list[Any], payload: dict[str, Any]):
    calm = payload["calm"]
    manipulated = payload["manipulated"]
    reports = payload["reports"]
    screenshot = current_screenshot()

    story.append(Spacer(1, 0.1 * inch))
    story.append(p("FairFlow Guardian", "CoverTitle"))
    story.append(p("Live Demo Runbook", "H1x"))
    story.append(
        p(
            "A focused, presenter-ready guide for the actual judge demo: what to click, what should appear, what to say, and which proof to copy.",
            "Calloutx",
        )
    )
    story.append(Spacer(1, 0.08 * inch))
    story.append(
        metric_grid(
            [
                ("Demo thesis", "No-trade is proof", "Better systems, not bigger bets"),
                ("Calm path", f"{calm['status']} / {calm['final_action']}", f"Fairness {calm['fairness_passport']['score']:.0f}/100"),
                ("Manipulated path", manipulated["final_action"], f"Fairness {manipulated['fairness_passport']['score']:.0f}/100"),
                ("Evidence", f"{reports['evidence']['verification_score']:.0f}/100", f"{len(reports['evidence']['included_reports'])} linked reports"),
            ],
            [MINT, BLUE_SOFT, RED_SOFT, GOLD_SOFT],
        )
    )
    story.append(Spacer(1, 0.12 * inch))
    if screenshot:
        story.append(fitted_image(screenshot, 6.8 * inch, 2.65 * inch))
    story.append(Spacer(1, 0.08 * inch))
    story.append(p("Use this beside the app. It intentionally avoids deep architecture and focuses only on the live demonstration path.", "Bodyx"))
    story.append(PageBreak())


def build_story(payload: dict[str, Any]) -> list[Any]:
    calm = payload["calm"]
    manipulated = payload["manipulated"]
    reports = payload["reports"]
    submission = reports["submission"]
    evidence = reports["evidence"]
    router = reports["router"]
    receipt = reports["receipt"]
    anchor = reports["anchor"]

    story: list[Any] = []
    add_cover(story, payload)

    section(story, "1. Pre-Demo Setup", "Goal: make the first screen instantly understandable.")
    setup_rows = [
        ["Check", "Do this", "Success signal"],
        ["App", "Open http://localhost:5174", "Dashboard loads with Competition Runway near the top."],
        ["Market", "Select BTCUSDT and Calm", "Decision is approved and paper-only route is visible."],
        ["Proof", "Keep audit hash, evidence pack, route proof, and Copy proof visible", "Judges see verifiability before performance claims."],
        ["Backup", "Keep PPT, PDF, and SUBMISSION.md nearby", "If network slows, demo story still works."],
    ]
    story.append(table(setup_rows, [1.05 * inch, 4.2 * inch, 4.9 * inch]))
    story.append(Spacer(1, 0.12 * inch))
    story.append(p("Do not open with a profit chart. Open with the fairness thesis: FairFlow decides whether a market is safe enough to route.", "Calloutx"))
    story.append(PageBreak())

    section(story, "2. Exact Click Path", "Use this sequence during the live screen share.")
    click_rows = [
        ["Time", "Click / show", "Expected screen result", "Say"],
        ["0:00", "Start on Competition Runway", "Readiness, evidence pack, route proof, audit hash visible", "FairFlow proves when a market is fair enough to review."],
        ["0:15", "Point to Fairness Passport and hidden cost", f"Hidden cost about {calm['fairness_passport']['estimated_hidden_cost_bps']:.1f} bps", "Retail users need market-quality evidence, not just a signal."],
        ["0:34", "Open Active Agents or Mission Control", "Agents show propose, challenge, gate, and audit roles", "The strategy agent cannot execute alone."],
        ["0:54", "Open Submission Kit or Evidence Pack", f"{len(evidence['included_reports'])} reports bundled", "Every claim is inspectable and copyable."],
        ["1:18", "Click Show no-trade or Manipulated", f"{manipulated['status']} / {manipulated['final_action']}", "This is the strongest proof: unsafe routing is refused."],
        ["1:41", "Click Copy proof", "Submission/evidence proof copied", "Better systems, not bigger bets."],
    ]
    story.append(table(click_rows, [0.72 * inch, 2.15 * inch, 3.05 * inch, 4.2 * inch]))
    story.append(PageBreak())

    section(story, "3. What Judges Should Notice", "These are the visual signals to call out while the dashboard is live.")
    notice_rows = [
        ["Screen area", "What it proves", "Judge takeaway"],
        ["Competition Runway", "The demo thesis, readiness score, evidence pack, route proof, and calm/no-trade controls are in one place.", "The project is designed to be judged, not guessed."],
        ["Decision panel", f"Calm state is {calm['status']} with {calm['final_action']} and fairness {calm['fairness_passport']['score']:.0f}/100.", "Approval is bounded and auditable."],
        ["Fair Execution Router", f"Recommended route: {router['recommended_route']}; verdict: {router['verdict'].replace('_', ' ')}.", "Execution method is checked separately from strategy."],
        ["Evidence Pack", f"Verification score {evidence['verification_score']:.0f}/100 with {len(evidence['included_reports'])} linked reports.", "Claims are verifiable from a single audit hash."],
        ["Manipulated scenario", f"Outcome: {manipulated['final_action']} with fairness {manipulated['fairness_passport']['score']:.0f}/100.", "No-trade is an intended protection, not a failed trade."],
    ]
    story.append(table(notice_rows, [1.75 * inch, 4.65 * inch, 3.75 * inch]))
    story.append(PageBreak())

    section(story, "4. Two-Minute Voiceover", "This matches the current judge-facing PPT notes.")
    segment_rows = [["Time", "Slide", "Voiceover"]]
    for segment in submission["video_segments"]:
        segment_rows.append([segment["timecode"], segment["title"], segment["narration"]])
    story.append(table(segment_rows, [0.9 * inch, 1.55 * inch, 7.7 * inch]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(p("Presenter tip: speak slower than feels natural. The script is short enough to leave room for live clicks.", "Calloutx"))
    story.append(PageBreak())

    section(story, "5. Proof Links To Copy Live", "Use one or two of these if judges ask how claims can be verified.")
    proof_rows = [
        ["Proof", "Path", "Use when"],
        ["Current audit", f"/api/audits/{calm['audit_hash']}", "A judge asks for the raw decision report."],
        ["Evidence pack", f"/api/audits/{calm['audit_hash']}/evidence-pack", "A judge asks for the single verifier bundle."],
        ["Submission kit", f"/api/audits/{calm['audit_hash']}/submission-kit", "A judge asks what to record or submit."],
        ["Receipt", f"/api/audits/{calm['audit_hash']}/receipt", "A judge asks how retail protections are explained."],
        ["Anchor proof", f"/api/audits/{calm['audit_hash']}/anchor-proof", "A judge asks where blockchain enters the system."],
    ]
    story.append(table(proof_rows, [1.55 * inch, 4.45 * inch, 4.15 * inch]))
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        metric_grid(
            [
                ("Audit hash", calm["audit_hash"][:12], "show this on screen"),
                ("Receipt", f"{receipt['bga_alignment_score']:.0f}/100", "BGA alignment"),
                ("Anchor", anchor["decision_hash_bytes32"][:12], "contract-ready bytes32"),
            ],
            [MINT, BLUE_SOFT, GOLD_SOFT],
        )
    )
    story.append(PageBreak())

    section(story, "6. Backup Plan If The Live App Slows", "Keep control of the story even if a network or browser hiccup appears.")
    backup_rows = [
        ["Problem", "Fast response", "What to show"],
        ["Bybit is slow", "Switch to Calm or Manipulated deterministic scenario.", "The project intentionally has stable fallback scenarios."],
        ["Browser refresh takes time", "Use the PPT while the app reloads.", "Slide 4 shows the Competition Runway; slide 5 shows no-trade proof."],
        ["Judge asks if this trades real money", "Say: paper-only by design; live execution is intentionally not implemented.", "Safety boundary in README and PDF."],
        ["Judge asks what is blockchain-for-good", "Say: audit hashes and anchor payloads reduce information asymmetry without custody or live trading.", "Evidence Pack and Anchor Proof."],
        ["Judge asks what to submit", "Use SUBMISSION.md and the Submission Kit panel.", "PPT, script, walkthrough PDF, evidence endpoint."],
    ]
    story.append(table(backup_rows, [1.8 * inch, 4.1 * inch, 4.25 * inch]))
    story.append(PageBreak())

    section(story, "7. Final Close", "Say this after showing Manipulated -> NO_TRADE.")
    story.append(Spacer(1, 0.22 * inch))
    story.append(
        table(
            [
                [p("Closing line", "Calloutx")],
                [
                    p(
                        "FairFlow is not trying to win a pure PnL contest. It is infrastructure for safer retail participation: agentic review, risk-first route gating, no-trade discipline, and verifiable audit proof.",
                        "H1x",
                    )
                ],
                [p("Better systems, not bigger bets.", "CoverTitle")],
            ],
            [9.8 * inch],
            fill=MINT,
            header=False,
        )
    )
    story.append(Spacer(1, 0.18 * inch))
    story.append(bullet("End on Manipulated / NO_TRADE, not on a return number."))
    story.append(bullet("Copy the evidence pack or audit hash as the proof handoff."))
    story.append(bullet("Remind judges that live execution is intentionally locked out."))

    return story


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = collect_payload()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=landscape(letter),
        rightMargin=MARGIN,
        leftMargin=MARGIN,
        topMargin=34,
        bottomMargin=34,
        title="FairFlow Guardian Live Demo Runbook",
    )
    doc.build(build_story(payload), onFirstPage=on_page, onLaterPages=on_page)
    print(OUT)


if __name__ == "__main__":
    build()
