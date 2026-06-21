from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "fairflow_guardian_demo.pdf"
DATA = ROOT / "tmp" / "pdfs" / "scenario_summary.json"
SCREENSHOT = ROOT / "tmp" / "assets" / "fairflow_dashboard.png"

PAGE_W = 13.333 * inch
PAGE_H = 7.5 * inch
M = 42

BG = colors.HexColor("#F6F7F4")
INK = colors.HexColor("#17211C")
MUTED = colors.HexColor("#62706B")
GREEN = colors.HexColor("#176D5D")
GREEN_2 = colors.HexColor("#E2F3EA")
YELLOW = colors.HexColor("#D49A31")
YELLOW_2 = colors.HexColor("#FFF4CD")
RED = colors.HexColor("#C44D42")
RED_2 = colors.HexColor("#FFE8E2")
BLUE = colors.HexColor("#2C536C")
LINE = colors.HexColor("#D8DFD8")
WHITE = colors.white


def money(value: float) -> str:
    return f"${value:,.0f}"


def num(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def pct(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}%"


def bps(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f} bps"


def pstyle(size=12, color=INK, leading=None, bold=False, align=TA_LEFT):
    return ParagraphStyle(
        name=f"s{size}{color}",
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        leading=leading or size * 1.32,
        textColor=color,
        alignment=align,
        spaceAfter=0,
        splitLongWords=False,
    )


def para(c: canvas.Canvas, text: str, x: float, y_top: float, w: float, h: float, style: ParagraphStyle):
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    p = Paragraph(text, style)
    used_w, used_h = p.wrap(w, h)
    p.drawOn(c, x, y_top - used_h)
    return used_h


def draw_bg(c: canvas.Canvas, title: str, page: int):
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=True, stroke=False)
    c.setFillColor(GREEN)
    c.rect(0, PAGE_H - 7, PAGE_W * 0.36, 7, fill=True, stroke=False)
    c.setFillColor(YELLOW)
    c.rect(PAGE_W * 0.36, PAGE_H - 7, PAGE_W * 0.24, 7, fill=True, stroke=False)
    c.setFillColor(RED)
    c.rect(PAGE_W * 0.60, PAGE_H - 7, PAGE_W * 0.18, 7, fill=True, stroke=False)
    c.setFillColor(BLUE)
    c.rect(PAGE_W * 0.78, PAGE_H - 7, PAGE_W * 0.22, 7, fill=True, stroke=False)

    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(MUTED)
    c.drawString(M, 23, "FairFlow Guardian")
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(PAGE_W / 2, 23, title)
    c.drawRightString(PAGE_W - M, 23, f"{page:02d}")


def h1(c, text, x=M, y=PAGE_H - 80, size=32, color=INK):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", size)
    c.drawString(x, y, text)


def eyebrow(c, text, x=M, y=PAGE_H - 52):
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x, y, text.upper())


def card(c, x, y, w, h, fill=WHITE, stroke=LINE, radius=8):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, radius, fill=True, stroke=True)


def chip(c, text, x, y, fill, stroke=None, text_color=INK, w=None):
    width = w or stringWidth(text, "Helvetica-Bold", 9) + 22
    c.setFillColor(fill)
    c.setStrokeColor(stroke or fill)
    c.roundRect(x, y, width, 24, 12, fill=True, stroke=True)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(text_color)
    c.drawCentredString(x + width / 2, y + 7.2, text)
    return width


def bullet_list(c, items, x, y_top, w, size=11.2, color=INK, gap=10):
    style = pstyle(size=size, color=color, leading=size * 1.32)
    y = y_top
    for item in items:
        c.setFillColor(GREEN)
        c.circle(x + 4, y - 6, 2.5, fill=True, stroke=False)
        used = para(c, item, x + 14, y, w - 14, 46, style)
        y -= max(used, size * 1.32) + gap
    return y


def metric(c, label, value, x, y, w, tone=GREEN):
    card(c, x, y, w, 66)
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 7.7)
    c.drawString(x + 12, y + 43, label.upper())
    c.setFillColor(tone)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(x + 12, y + 17, value)


def flow_node(c, text, x, y, w, h, fill, stroke=LINE):
    card(c, x, y, w, h, fill=fill, stroke=stroke)
    para(c, text, x + 10, y + h - 13, w - 20, h - 18, pstyle(10.5, INK, bold=True, align=TA_CENTER))


def arrow(c, x1, y1, x2, y2, color=MUTED):
    c.setStrokeColor(color)
    c.setLineWidth(1.5)
    c.line(x1, y1, x2, y2)
    c.setFillColor(color)
    c.line(x2, y2, x2 - 7, y2 + 4)
    c.line(x2, y2, x2 - 7, y2 - 4)


def page_title(c, title, subtitle, page):
    draw_bg(c, title, page)
    eyebrow(c, "BGA AI Trading and Strategy Track")
    h1(c, title)
    para(c, subtitle, M, PAGE_H - 103, PAGE_W - 2 * M, 50, pstyle(14, MUTED, leading=18))


def add_cover(c, data):
    draw_bg(c, "Explainable trading safety layer", 1)
    eyebrow(c, "Hackathon demo guide")
    h1(c, "FairFlow Guardian", y=PAGE_H - 95, size=44, color=GREEN)
    para(
        c,
        "An explainable AI trading copilot that decides when to trade, when to reduce risk, and when the fairest action is no trade.",
        M,
        PAGE_H - 134,
        640,
        80,
        pstyle(18, INK, leading=24),
    )
    x = M
    y = PAGE_H - 230
    x += chip(c, "Multi-agent review", x, y, GREEN_2, text_color=GREEN) + 10
    x += chip(c, "Fairness Passport", x, y, YELLOW_2, text_color=colors.HexColor("#80600F")) + 10
    x += chip(c, "AI committee", x, y, GREEN_2, text_color=GREEN) + 10
    chip(c, "Verifiable audit hash", x, y, RED_2, text_color=RED)

    card(c, M, 92, 382, 210, fill=WHITE)
    para(c, "The one-line explanation", M + 18, 276, 340, 28, pstyle(12, GREEN, bold=True))
    para(
        c,
        "FairFlow is not a pure profit bot. It is a safety, fairness, and transparency layer for retail traders: it proposes a trade only after market parity, manipulation risk, stress tests, and execution guardrails all pass.",
        M + 18,
        248,
        340,
        130,
        pstyle(16, INK, leading=21),
    )

    card(c, 455, 92, PAGE_W - 455 - M, 210, fill=colors.HexColor("#FDFEFC"))
    para(c, "Current demo behavior", 475, 276, 400, 28, pstyle(12, GREEN, bold=True))
    calm = data["calm"]
    manip = data["manipulated"]
    metric(c, "Calm scenario", calm["status"].upper(), 475, 188, 142, GREEN)
    metric(c, "Manipulated scenario", manip["final_action"], 632, 188, 178, RED)
    metric(c, "Paper order", "GATED", 825, 188, 112, BLUE)
    para(
        c,
        "The demo is designed to show judgment, not bravado: a calm setup can be approved, while unsafe conditions are blocked with reasons.",
        475,
        166,
        430,
        55,
        pstyle(11.5, MUTED),
    )


def add_problem(c):
    page_title(
        c,
        "What problem is it solving?",
        "Retail traders often see the same price chart as institutions, but not the same risk context.",
        2,
    )
    card(c, M, 300, 258, 122, fill=RED_2, stroke=colors.HexColor("#E9B2AA"))
    para(c, "Typical trading bot", M + 16, 397, 220, 22, pstyle(14, RED, bold=True))
    bullet_list(
        c,
        [
            "Chases signals and headline returns.",
            "Often hides assumptions and overfitting.",
            "Can keep trading in thin or manipulated markets.",
        ],
        M + 16,
        368,
        220,
        size=10.8,
        gap=7,
    )
    card(c, 350, 300, 258, 122, fill=GREEN_2, stroke=colors.HexColor("#ADD9C3"))
    para(c, "FairFlow Guardian", 366, 397, 220, 22, pstyle(14, GREEN, bold=True))
    bullet_list(
        c,
        [
            "Treats no trade as a valid answer.",
            "Explains every approval or rejection.",
            "Caps execution with risk and liquidity safeguards.",
        ],
        366,
        368,
        220,
        size=10.8,
        gap=7,
    )
    card(c, 658, 300, 258, 122, fill=WHITE)
    para(c, "Why this fits BGA", 674, 397, 220, 22, pstyle(14, BLUE, bold=True))
    bullet_list(
        c,
        [
            "Reduces information asymmetry.",
            "Makes strategy decisions inspectable.",
            "Optimizes for healthier market behavior.",
        ],
        674,
        368,
        220,
        size=10.8,
        gap=7,
    )
    para(
        c,
        "The project asks a better question than: How do we maximize PnL? It asks: Is this trade fair, explainable, and safe enough to execute?",
        M,
        235,
        PAGE_W - 2 * M,
        75,
        pstyle(24, INK, leading=31, bold=True, align=TA_CENTER),
    )
    c.setStrokeColor(LINE)
    c.setLineWidth(1)
    c.line(120, 205, PAGE_W - 120, 205)
    bullet_list(
        c,
        [
            "For a judge: this is a market safety system, not a black-box alpha claim.",
            "For a user: this is a trading seatbelt that explains risk before money moves.",
            "For a protocol: this creates a verifiable record of why execution did or did not happen.",
        ],
        164,
        172,
        PAGE_W - 328,
        size=12.4,
        gap=11,
    )


def add_ui(c):
    page_title(
        c,
        "What you are seeing in the UI",
        "The dashboard is a decision cockpit. Each button runs the same review process on a different market condition.",
        3,
    )
    if SCREENSHOT.exists():
        img = ImageReader(str(SCREENSHOT))
        img_w, img_h = img.getSize()
        box_x, box_y, box_w, box_h = M, 72, 585, 330
        scale = min(box_w / img_w, box_h / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale
        card(c, box_x - 8, box_y - 8, box_w + 16, box_h + 16, fill=WHITE)
        c.drawImage(img, box_x, box_y + (box_h - draw_h) / 2, draw_w, draw_h, preserveAspectRatio=True, mask="auto")
    x = 675
    notes = [
        ("1. Scenario selector", "Live uses Bybit public data. Calm, Volatile, and Manipulated are deterministic demos.", GREEN_2, colors.HexColor("#ADD9C3"), GREEN),
        ("2. Final action", "Approved can create a paper route. Blocked or Observe locks execution.", WHITE, LINE, BLUE),
        ("3. Fairness passport", "Scores retail parity, hidden costs, manipulation exposure, and auditability.", YELLOW_2, colors.HexColor("#E4CA75"), colors.HexColor("#80600F")),
        ("4. Decision trace", "Seven stages show how raw data becomes a final audited outcome.", WHITE, LINE, GREEN),
        ("5. Audit hash", "The full report is hashed so the team cannot rewrite it after the outcome is known.", RED_2, colors.HexColor("#E9B2AA"), RED),
    ]
    yy = 340
    for title, body, fill, stroke, tone in notes:
        card(c, x, yy, 244, 60, fill=fill, stroke=stroke)
        para(c, title, x + 14, yy + 43, 212, 18, pstyle(11.8, tone, bold=True))
        para(c, body, x + 14, yy + 25, 212, 30, pstyle(9.6, INK))
        yy -= 70


def add_architecture(c):
    page_title(
        c,
        "How the system works",
        "FairFlow separates proposal from approval. The strategy agent cannot execute unless independent safety agents agree.",
        4,
    )
    y = 330
    flow_node(c, "Bybit public API or fallback scenario", 52, y, 126, 58, GREEN_2)
    flow_node(c, "Market metrics", 204, y, 132, 58, WHITE)
    flow_node(c, "Deterministic agents", 362, y, 120, 58, YELLOW_2)
    flow_node(c, "Agentic AI committee", 508, y, 124, 58, GREEN_2)
    flow_node(c, "Fairness passport and gate", 658, y, 116, 58, WHITE)
    flow_node(c, "Report and SHA-256 hash", 800, y, 112, 58, RED_2)
    arrow(c, 178, y + 29, 204, y + 29)
    arrow(c, 336, y + 29, 362, y + 29)
    arrow(c, 482, y + 29, 508, y + 29)
    arrow(c, 632, y + 29, 658, y + 29)
    arrow(c, 774, y + 29, 800, y + 29)

    labels = [
        ("Market Regime Agent", "Classifies whether the market is orderly, directional, volatile, or fragile."),
        ("Strategy Agent", "Suggests long, short, or no trade with entry, stop, take-profit, and confidence."),
        ("Manipulation Sentinel", "Scores abnormal spread, depth imbalance, wick, volume, impact, and funding crowding."),
        ("Risk Guardian", "Stress-tests the proposal and blocks trades that violate safety thresholds."),
        ("AI Committee", "Adds ML regime, anomaly, forecast, backtest, planner, memory, and narration."),
        ("Decision Trace", "Records the seven-stage path from market data intake to final audited outcome."),
    ]
    x0, y0 = M, 214
    for idx, (name, desc) in enumerate(labels):
        col = idx % 3
        row = idx // 3
        x = x0 + col * 304
        y_card = y0 - row * 88
        card(c, x, y_card, 274, 68, fill=WHITE)
        para(c, name, x + 14, y_card + 48, 246, 20, pstyle(12.5, GREEN if idx != 2 else RED, bold=True))
        para(c, desc, x + 14, y_card + 28, 246, 34, pstyle(9.5, INK))


def add_agents(c):
    page_title(
        c,
        "What each agent is checking",
        "The project is intentionally inspectable: every score comes from visible market conditions and explicit thresholds.",
        5,
    )
    cards = [
        ("Market Regime", GREEN, ["Volatility", "24h range", "Momentum", "RSI"]),
        ("Strategy", BLUE, ["Action", "Entry and stop", "Take profit", "Confidence"]),
        ("Manipulation Sentinel", RED, ["Spread", "Book imbalance", "Wick and volume", "Crowded funding"]),
        ("Risk Guardian", YELLOW, ["Stress moves", "Risk budget", "Position cap", "Execution lock"]),
        ("Fairness Passport", GREEN, ["Information parity", "Execution parity", "Manipulation exposure", "Auditability"]),
        ("Execution and Audit", BLUE, ["Planner", "Memory", "Narrator", "Decision hash"]),
    ]
    for i, (title, tone, items) in enumerate(cards):
        x = M + (i % 3) * 304
        y = 272 - (i // 3) * 146
        card(c, x, y, 274, 118, fill=WHITE)
        c.setFillColor(tone)
        c.roundRect(x + 15, y + 80, 46, 24, 12, fill=True, stroke=False)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x + 38, y + 87, f"{i + 1}")
        para(c, title, x + 72, y + 101, 184, 24, pstyle(14, INK, bold=True))
        bullet_list(c, items, x + 20, y + 68, 224, size=9.8, gap=4)


def add_demo_script(c, data):
    page_title(
        c,
        "How to demo it in two minutes",
        "This is the exact sequence to walk a judge through the app without getting lost in trading jargon.",
        6,
    )
    steps = [
        ("1", "Open BTCUSDT in Calm", "Show that the system approves a small paper trade only after all safety agents pass."),
        ("2", "Click Paper execute", "Point out that this is gated paper execution, not uncontrolled live trading."),
        ("3", "Open Fairness Passport", "Show the retail parity score and the hidden-cost estimate before discussing the trade."),
        ("4", "Open Decision trace", "Walk through data intake, features, proposal, AI committee, stress decision, and final outcome."),
        ("5", "Switch to Manipulated", "Show that the same strategy idea is rejected when spread, funding, wick, and depth become unsafe."),
    ]
    y = 365
    for n, title, desc in steps:
        c.setFillColor(GREEN if n in {"1", "2", "3", "4"} else RED)
        c.circle(75, y + 11, 17, fill=True, stroke=False)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(75, y + 6, n)
        para(c, title, 112, y + 28, 250, 24, pstyle(15, INK, bold=True))
        para(c, desc, 112, y + 7, 430, 36, pstyle(10.8, MUTED))
        y -= 62

    card(c, 585, 112, 318, 210, fill=colors.HexColor("#FDFEFC"))
    para(c, "Talk track", 606, 292, 280, 22, pstyle(13, GREEN, bold=True))
    para(
        c,
        "The important behavior is not that FairFlow can trade. It is that FairFlow knows when not to trade. The system separates alpha generation from fairness review and risk approval, shows a seven-stage decision trace, and creates an audit trail so the decision can be verified later.",
        606,
        265,
        276,
        120,
        pstyle(13.2, INK, leading=18),
    )
    para(
        c,
        f"Example audit prefix: {data['calm']['audit_hash'][:16]}...",
        606,
        139,
        270,
        28,
        pstyle(10.5, MUTED),
    )


def add_scenarios(c, data):
    page_title(
        c,
        "What the scenarios prove",
        "The same app can approve, observe, or block depending on market quality and risk context.",
        7,
    )
    headers = ["Scenario", "Decision", "Liquidity", "Fairness", "Volatility", "Why it matters"]
    widths = [110, 105, 95, 125, 95, 340]
    x = M
    y = 382
    c.setFillColor(GREEN)
    c.roundRect(x, y, sum(widths), 30, 8, fill=True, stroke=False)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 8.6)
    xx = x + 10
    for header, width in zip(headers, widths):
        c.drawString(xx, y + 10, header.upper())
        xx += width
    y -= 84
    for scenario in ["calm", "volatile", "manipulated"]:
        d = data[scenario]
        m = d["metrics"]
        fairness = d["fairness_passport"]
        tone = GREEN_2 if d["status"] == "approved" else RED_2
        card(c, x, y, sum(widths), 70, fill=tone, stroke=LINE)
        values = [
            scenario.title(),
            f"{d['status'].upper()} / {d['final_action']}",
            f"{m['liquidity_score']:.0f}/100",
            f"{fairness['score']:.0f}/100",
            pct(m["realized_volatility_pct"], 2),
            d["summary"],
        ]
        xx = x + 10
        for value, width in zip(values, widths):
            para(c, value, xx, y + 52, width - 12, 52, pstyle(9.6, INK, leading=12, bold=value == values[0]))
            xx += width
        y -= 82

    para(
        c,
        "Judge-friendly interpretation: FairFlow demonstrates selective execution. It does not pretend every signal deserves a trade.",
        M,
        72,
        PAGE_W - 2 * M,
        40,
        pstyle(15, INK, leading=20, bold=True, align=TA_CENTER),
    )


def add_risk(c, data):
    page_title(
        c,
        "Risk management is the product",
        "The execution layer is deliberately conservative because crypto leverage can fail fast.",
        8,
    )
    guards = [
        "Paper/testnet execution only in this prototype.",
        "Stop loss is mandatory for any executable recommendation.",
        "Position size is capped at 25% of demo equity.",
        "Maximum modeled risk budget is 1% of demo equity.",
        "Execution is blocked during high manipulation or fragile-liquidity states.",
        "Cooldown-first design: one decision report per user refresh, no runaway loop.",
    ]
    card(c, M, 93, 430, 310, fill=WHITE)
    para(c, "Built-in safeguards", M + 18, 374, 390, 24, pstyle(15, GREEN, bold=True))
    bullet_list(c, guards, M + 20, 338, 380, size=10.8, gap=8)

    card(c, 510, 93, 404, 310, fill=colors.HexColor("#FDFEFC"))
    para(c, "Stress test example", 530, 374, 360, 24, pstyle(15, BLUE, bold=True))
    rows = [
        ("-1%", "+2.0%", "No"),
        ("-2%", "+4.0%", "No"),
        ("+1%", "-2.0%", "Yes"),
        ("+2%", "-4.0%", "Yes"),
        ("+5%", "-10.0%", "Yes"),
    ]
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(MUTED)
    c.drawString(535, 334, "MOVE")
    c.drawString(635, 334, "PNL")
    c.drawString(735, 334, "STOP")
    yy = 306
    for move, pnl, stop in rows:
        c.setStrokeColor(LINE)
        c.line(532, yy + 18, 880, yy + 18)
        c.setFillColor(INK)
        c.setFont("Helvetica", 12)
        c.drawString(535, yy, move)
        c.setFillColor(RED if pnl.startswith("-") else GREEN)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(635, yy, pnl)
        c.setFillColor(INK)
        c.drawString(735, yy, stop)
        yy -= 36
    para(
        c,
        "For the calm short, adverse upward moves trigger the modeled stop. In manipulated conditions, execution is blocked before stress tests matter.",
        530,
        138,
        360,
        45,
        pstyle(11.2, MUTED),
    )


def add_audit(c):
    page_title(
        c,
        "Transparency and verifiability",
        "A good market system should be inspectable before the outcome is known.",
        9,
    )
    flow_y = 315
    flow_node(c, "Decision report", 92, flow_y, 150, 60, WHITE)
    flow_node(c, "Canonical JSON", 315, flow_y, 150, 60, GREEN_2)
    flow_node(c, "SHA-256 hash", 538, flow_y, 150, 60, YELLOW_2)
    flow_node(c, "Optional contract anchor", 761, flow_y, 150, 60, RED_2)
    arrow(c, 242, flow_y + 30, 315, flow_y + 30)
    arrow(c, 465, flow_y + 30, 538, flow_y + 30)
    arrow(c, 688, flow_y + 30, 761, flow_y + 30)

    card(c, M, 114, 410, 135, fill=WHITE)
    para(c, "What is inside the report?", M + 18, 223, 370, 24, pstyle(14, GREEN, bold=True))
    bullet_list(
        c,
        ["Market snapshot source", "Metric values", "Fairness Passport", "Agent verdicts", "Decision trace stages", "Stress tests"],
        M + 18,
        193,
        360,
        size=10.8,
        gap=5,
    )
    card(c, 505, 114, 410, 135, fill=WHITE)
    para(c, "What does the contract add?", 523, 223, 370, 24, pstyle(14, RED, bold=True))
    bullet_list(
        c,
        [
            "Stores the decision hash.",
            "Records symbol, action, reporter, timestamp, and metadata URI.",
            "Makes hindsight rewriting much harder.",
        ],
        523,
        193,
        360,
        size=10.8,
        gap=5,
    )


def add_judging(c):
    page_title(
        c,
        "How this maps to judging criteria",
        "Use this page as the quick mental checklist before presenting.",
        10,
    )
    criteria = [
        ("BGA ethos", "Uses a Fairness Passport to help retail users avoid unsafe trades, reduce hidden information gaps, and reward transparent no-trade decisions.", GREEN),
        ("Technical depth", "FastAPI agents, AI committee models, Bybit V5 market data, deterministic fallback scenarios, React dashboard, and Solidity audit anchoring.", BLUE),
        ("Strategy and risk", "Strategy proposals are separate from approval, with fairness scoring, stop loss, stress tests, liquidity thresholds, and manipulation gates.", YELLOW),
        ("Transparency", "Every recommendation has a decision trace, agent rationales, metric values, safeguards, and a SHA-256 audit hash.", RED),
    ]
    y = 346
    for title, body, tone in criteria:
        card(c, M, y, PAGE_W - 2 * M, 64, fill=WHITE)
        c.setFillColor(tone)
        c.roundRect(M + 14, y + 17, 12, 30, 6, fill=True, stroke=False)
        para(c, title, M + 42, y + 45, 190, 24, pstyle(14, tone, bold=True))
        para(c, body, M + 230, y + 47, 630, 42, pstyle(11.4, INK))
        y -= 78


def add_pitch(c):
    page_title(
        c,
        "Simple pitch script",
        "A concise explanation you can read almost word for word during the demo.",
        11,
    )
    card(c, M, 205, PAGE_W - 2 * M, 205, fill=WHITE)
    script = (
        "FairFlow Guardian is an explainable AI trading safety layer for retail crypto traders. "
        "Most bots focus on whether they can make money. We focus on whether a trade is safe, fair, and explainable enough to execute. "
        "The system pulls market data, builds metrics like spread, volatility, funding, depth, RSI, and market impact, then sends the setup through deterministic agents and an AI committee. "
        "One agent proposes a strategy, but separate agents challenge it for regime risk, manipulation risk, forecast uncertainty, backtest weakness, and stress-test failure. "
        "If the setup is unfair or unsafe, FairFlow blocks execution and records the full decision trace. If it passes, it creates only a capped paper order with stop loss and an audit hash."
    )
    para(c, script, M + 24, 382, PAGE_W - 2 * M - 48, 160, pstyle(15.5, INK, leading=21))
    qas = [
        ("Is this a profit bot?", "No. It is a risk and transparency layer. Profit models can plug in later, but execution remains gated."),
        ("Why blockchain?", "The report hash can be anchored on-chain, proving the decision existed before the outcome."),
        ("Why is it useful?", "It gives retail users institutional-style context: market quality, liquidation pressure, and explainable reasons to wait."),
    ]
    x = M
    for q, a in qas:
        card(c, x, 80, 274, 94, fill=colors.HexColor("#FDFEFC"))
        para(c, q, x + 14, 148, 246, 24, pstyle(12.5, GREEN, bold=True))
        para(c, a, x + 14, 125, 246, 54, pstyle(10.7, INK))
        x += 296


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(DATA.read_text())
    c = canvas.Canvas(str(OUT), pagesize=(PAGE_W, PAGE_H))
    add_cover(c, data)
    c.showPage()
    add_problem(c)
    c.showPage()
    add_ui(c)
    c.showPage()
    add_architecture(c)
    c.showPage()
    add_agents(c)
    c.showPage()
    add_demo_script(c, data)
    c.showPage()
    add_scenarios(c, data)
    c.showPage()
    add_risk(c, data)
    c.showPage()
    add_audit(c)
    c.showPage()
    add_judging(c)
    c.showPage()
    add_pitch(c)
    c.save()
    print(OUT)


if __name__ == "__main__":
    build()
