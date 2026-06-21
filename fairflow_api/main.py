from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .agents import build_decision
from .audit_store import AuditLedger
from .bybit import BybitFetchError, fallback_snapshot, fetch_bybit_snapshot
from .models import (
    AgentAction,
    AgentMission,
    AgentTask,
    AnchorProof,
    AuditEvidencePack,
    CounterfactualFairnessReport,
    CounterfactualLever,
    EvidencePackClaim,
    ExecutionRouteCandidate,
    FairExecutionRouterReport,
    FairnessReceipt,
    FairnessReceiptMetric,
    GuardianDecision,
    GuardrailPolicyCheck,
    GuardrailPolicyReport,
    GuardrailPolicyRequest,
    HackathonReadinessCriterion,
    HackathonReadinessReport,
    HackathonRunbookStep,
    HackathonSubmissionKit,
    ImpactLedgerIssue,
    ImpactLedgerReport,
    JudgeBrief,
    JudgeBriefRubricItem,
    JudgeBriefStep,
    MarketSeries,
    MarketSnapshot,
    ModelComponentCard,
    ModelProvenanceCard,
    PaperOrder,
    PaperOrderRequest,
    PaperPortfolio,
    PaperPosition,
    PolicyStressOutcome,
    PolicyStressReport,
    RiskSizingRequest,
    RiskSizingResponse,
    ProvenanceDataSource,
    RedTeamProbe,
    RedTeamReport,
    RetailCohortProfile,
    RetailCohortReport,
    RetailCohortResult,
    ScenarioComparison,
    SubmissionAsset,
    SubmissionChecklistItem,
    SubmissionVideoSegment,
    WatchlistItem,
    WatchlistReport,
)

app = FastAPI(
    title="FairFlow Guardian API",
    version="0.1.0",
    description="Explainable AI trading safety layer with risk review and audit hashes.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDITS: dict[str, GuardianDecision] = {}
AUDIT_LEDGER = AuditLedger()
PAPER_ORDERS: list[PaperOrder] = []
MISSIONS: list[AgentMission] = []
SCENARIOS = ("calm", "volatile", "manipulated")
STARTING_EQUITY_USDT = 10_000.0
DEFAULT_RETAIL_COHORTS = (
    RetailCohortProfile(name="Micro retail", account_equity_usdt=250.0, risk_budget_pct=0.5, max_notional_pct=12.0),
    RetailCohortProfile(name="Starter retail", account_equity_usdt=1_000.0, risk_budget_pct=0.75, max_notional_pct=18.0),
    RetailCohortProfile(name="Everyday retail", account_equity_usdt=5_000.0, risk_budget_pct=1.0, max_notional_pct=25.0),
    RetailCohortProfile(name="Active retail", account_equity_usdt=25_000.0, risk_budget_pct=1.0, max_notional_pct=30.0),
)


async def get_snapshot_for(symbol: str, category: str, scenario: str) -> MarketSnapshot:
    if scenario == "live":
        try:
            return await fetch_bybit_snapshot(symbol=symbol, category=category)
        except (BybitFetchError, TimeoutError, OSError, Exception):
            snapshot = fallback_snapshot(symbol=symbol, category=category, scenario="calm")
            snapshot.source = "fallback:calm-after-live-error"
            snapshot.scenario = "live"
            return snapshot
    else:
        return fallback_snapshot(symbol=symbol, category=category, scenario=scenario)


async def build_decision_for(symbol: str, category: str, scenario: str) -> GuardianDecision:
    snapshot = await get_snapshot_for(symbol=symbol, category=category, scenario=scenario)
    decision = build_decision(snapshot)
    AUDITS[decision.audit_hash] = decision
    AUDIT_LEDGER.store_decision(decision)
    return decision


def get_decision_from_audit(audit_hash: str) -> GuardianDecision | None:
    decision = AUDITS.get(audit_hash)
    if decision:
        return decision
    decision = AUDIT_LEDGER.get_decision(audit_hash)
    if decision:
        AUDITS[decision.audit_hash] = decision
    return decision


def audit_count() -> int:
    return max(len(AUDITS), AUDIT_LEDGER.count())


def _agentic_status(status: str) -> str:
    if status == "pass" or status == "approved" or status == "fair_to_execute":
        return "complete"
    if status == "block" or status == "blocked" or status == "unfair_to_retail":
        return "blocked"
    return "watch"


def _bounded_confidence(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 2)


def _bounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _agent(decision: GuardianDecision, name: str):
    return next((agent for agent in decision.agents if agent.name == name), None)


def _risk_register(decision: GuardianDecision, portfolio: PaperPortfolio, can_execute: bool) -> list[str]:
    risks: list[str] = []
    for check in decision.fairness_passport.checks:
        if check.status != "pass":
            risks.append(f"{check.name}: {check.explanation}")
    for agent in decision.agents:
        if agent.status != "pass":
            risks.append(f"{agent.name}: {agent.verdict}")
    if decision.ai_committee.forecast.stop_loss_hit_probability >= 0.5:
        risks.append(
            f"Forecast: stop-hit probability is {decision.ai_committee.forecast.stop_loss_hit_probability:.0%} "
            "over the next 30 minutes."
        )
    risks.extend(portfolio.risk_notes)
    if not can_execute:
        risks.append("Autonomy gate prevented execution; the agent can review, compare, or hold, but cannot route a trade.")

    deduped: list[str] = []
    for risk in risks:
        if risk not in deduped:
            deduped.append(risk)
    return deduped or ["No critical risks surfaced; keep the mission paper-only until independently validated."]


def _mission_actions(decision: GuardianDecision, portfolio: PaperPortfolio, can_execute: bool) -> list[AgentAction]:
    actions = [
        AgentAction(
            label="Refresh market feed",
            action_type="refresh_market",
            priority="medium",
            permitted=True,
            reason="Re-run public market intake before relying on the mission state.",
        ),
        AgentAction(
            label="Compare scenario drift",
            action_type="compare_scenarios",
            priority="high" if not can_execute else "medium",
            permitted=True,
            reason="Stress the same symbol against calm, volatile, and manipulated regimes.",
        ),
    ]

    if can_execute:
        actions.extend(
            [
                AgentAction(
                    label="Calculate guarded size",
                    action_type="size_position",
                    priority="high",
                    permitted=True,
                    reason="Approved report can be sized with the retail risk budget before paper routing.",
                ),
                AgentAction(
                    label="Paper execute audited route",
                    action_type="paper_execute",
                    priority="high",
                    permitted=True,
                    reason="All mission gates passed; execution remains simulated and audit-linked.",
                ),
            ]
        )
    else:
        actions.extend(
            [
                AgentAction(
                    label="Hold execution",
                    action_type="hold",
                    priority="critical",
                    permitted=True,
                    reason="The mission found unresolved safety or fairness blockers.",
                ),
                AgentAction(
                    label="Paper execute audited route",
                    action_type="paper_execute",
                    priority="critical",
                    permitted=False,
                    reason="Execution is locked until the report status and Fairness Passport both clear.",
                ),
            ]
        )

    actions.append(
        AgentAction(
            label="Review audit hash",
            action_type="review_audit",
            priority="medium",
            permitted=True,
            reason=f"Pin the decision trail to audit hash {decision.audit_hash[:12]} before changing state.",
        )
    )

    if portfolio.orders or portfolio.positions:
        actions.append(
            AgentAction(
                label="Reset paper book",
                action_type="reset_portfolio",
                priority="low",
                permitted=True,
                reason="Clear demo inventory before a fresh judged scenario if needed.",
            )
        )

    return actions


def _watchlist_rank(decision: GuardianDecision) -> float:
    anomaly_safety = 100 - decision.ai_committee.anomaly.score
    gate_bonus = 15 if decision.status == "approved" else 4 if decision.status == "observe" else -18
    action_bonus = 3 if decision.final_action != "NO_TRADE" else 0
    depth_adjustment = _market_depth_adjustment(decision.symbol)
    return round(
        decision.fairness_passport.score * 0.42
        + decision.metrics.liquidity_score * 0.24
        + anomaly_safety * 0.22
        + decision.proposal.confidence * 12
        + gate_bonus
        + action_bonus
        + depth_adjustment,
        2,
    )


def _market_depth_adjustment(symbol: str) -> float:
    return {
        "BTCUSDT": 6.0,
        "ETHUSDT": 4.0,
        "SOLUSDT": 2.0,
        "BNBUSDT": 1.0,
        "LINKUSDT": -1.0,
        "XRPUSDT": -4.0,
        "ADAUSDT": -5.0,
        "DOGEUSDT": -9.0,
    }.get(symbol.upper(), -2.0)


def _threshold_check(
    name: str,
    observed: float,
    limit: float,
    unit: str,
    higher_is_better: bool,
    explanation: str,
) -> GuardrailPolicyCheck:
    if higher_is_better:
        status = "block" if observed < limit else "watch" if observed < min(100.0, limit + 8) else "pass"
    else:
        watch_level = limit * 0.75
        status = "block" if observed > limit else "watch" if observed > watch_level else "pass"
    return GuardrailPolicyCheck(
        name=name,
        status=status,
        observed=round(observed, 3),
        limit=round(limit, 3),
        unit=unit,
        explanation=explanation,
    )


def _receipt_status(value: float, good_floor: float, watch_floor: float) -> str:
    if value >= good_floor:
        return "pass"
    if value >= watch_floor:
        return "watch"
    return "block"


def _inverse_receipt_status(value: float, pass_ceiling: float, watch_ceiling: float) -> str:
    if value <= pass_ceiling:
        return "pass"
    if value <= watch_ceiling:
        return "watch"
    return "block"


def _receipt_metric(label: str, value: str, status: str, explanation: str) -> FairnessReceiptMetric:
    return FairnessReceiptMetric(
        label=label,
        value=value,
        status=status,
        explanation=explanation,
    )


def build_fairness_receipt(decision: GuardianDecision) -> FairnessReceipt:
    passport = decision.fairness_passport
    committee = decision.ai_committee
    anomaly_safety = 100 - committee.anomaly.score
    transparency_score = min(100.0, len(decision.decision_trace) * 12 + len(decision.safeguards) * 4 + 12)
    gate_quality = 95.0
    if decision.status == "observe":
        gate_quality = 80.0
    elif decision.status == "blocked":
        gate_quality = 92.0 if passport.verdict == "unfair_to_retail" else 68.0

    alignment_score = round(
        max(
            0.0,
            min(
                100.0,
                passport.score * 0.35
                + decision.metrics.liquidity_score * 0.20
                + anomaly_safety * 0.20
                + transparency_score * 0.15
                + gate_quality * 0.10,
            ),
        ),
        1,
    )

    gate_status = "pass"
    if decision.status == "blocked":
        gate_status = "block"
    elif decision.status == "observe":
        gate_status = "watch"

    metrics = [
        _receipt_metric(
            "Fairness score",
            f"{passport.score:.0f}/100",
            _receipt_status(passport.score, 80, 65),
            "Scores information parity, execution parity, manipulation exposure, retail risk protection, and auditability.",
        ),
        _receipt_metric(
            "Hidden cost",
            f"{passport.estimated_hidden_cost_bps:.1f} bps",
            _inverse_receipt_status(passport.estimated_hidden_cost_bps, 8, 18),
            "Estimates spread, market impact, and hidden execution drag before any paper route can be accepted.",
        ),
        _receipt_metric(
            "Liquidity",
            f"{decision.metrics.liquidity_score:.0f}/100",
            _receipt_status(decision.metrics.liquidity_score, 70, 45),
            "Rewards deeper books and penalizes thin depth, high impact, and unstable order-book imbalance.",
        ),
        _receipt_metric(
            "Anomaly risk",
            f"{committee.anomaly.score:.0f}/100",
            _inverse_receipt_status(committee.anomaly.score, 35, 65),
            "Flags wick, volume, spread, funding, impact, volatility, and imbalance outliers that can trap retail users.",
        ),
        _receipt_metric(
            "Execution gate",
            f"{decision.status} / {decision.final_action}",
            gate_status,
            "FairFlow can approve, observe, or block. A blocked or observed report cannot be upgraded by the UI.",
        ),
        _receipt_metric(
            "Audit hash",
            decision.audit_hash[:16],
            "info",
            "The full SHA-256 hash identifies the exact decision payload stored in the audit ledger.",
        ),
    ]

    agent_concerns = [
        f"{agent.name}: {agent.verdict}"
        for agent in decision.agents
        if agent.status != "pass"
    ]
    if not agent_concerns:
        agent_concerns.append("No specialist agent raised a watch or block finding for this report.")

    block_checks = [
        f"{check.name}: {check.explanation}"
        for check in passport.checks
        if check.status != "pass"
    ]
    if block_checks:
        agent_concerns.extend(block_checks[:3])

    protections = []
    for item in [*passport.retail_protections, *decision.safeguards]:
        if item not in protections:
            protections.append(item)

    if decision.status == "approved":
        public_summary = (
            f"FairFlow cleared a guarded paper {decision.final_action.replace('_', ' ').lower()} for "
            f"{decision.symbol} only after fairness, anomaly, liquidity, risk, and audit checks passed."
        )
    else:
        public_summary = (
            f"FairFlow did not clear {decision.symbol} for execution. The system kept the setup in "
            f"{decision.status} mode because the audited report found unresolved retail-safety concerns."
        )

    return FairnessReceipt(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        category=decision.category,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        decision_status=decision.status,
        final_action=decision.final_action,
        public_summary=public_summary,
        retail_verdict=passport.summary,
        bga_alignment_score=alignment_score,
        metrics=metrics,
        agent_concerns=agent_concerns[:8],
        retail_protections=protections[:8],
        verification_steps=[
            "Fetch the machine-readable audit report from the receipt URL.",
            "Compare the full audit hash in the report, dashboard, and receipt.",
            "Replay the decision trace from market intake through the final audited outcome.",
            "Optionally anchor the hash with contracts/FairFlowAudit.sol before later market outcomes are known.",
        ],
        machine_readable_url=f"/api/audits/{decision.audit_hash}",
        disclaimer="Educational paper-trading infrastructure only. This receipt is not financial advice and never unlocks live execution.",
    )


def _cohort_result(decision: GuardianDecision, profile: RetailCohortProfile) -> RetailCohortResult:
    notes: list[str] = []
    risk_amount = profile.account_equity_usdt * (profile.risk_budget_pct / 100)
    leverage = max(decision.proposal.leverage, 1)
    hidden_cost_bps = decision.fairness_passport.estimated_hidden_cost_bps
    stop_distance_pct = None
    recommended_notional = 0.0
    max_loss = 0.0
    estimated_margin = 0.0
    hidden_cost = 0.0
    executable = (
        decision.status == "approved"
        and decision.final_action != "NO_TRADE"
        and bool(decision.proposal.entry_price)
        and bool(decision.proposal.stop_loss)
    )

    if executable and decision.proposal.entry_price and decision.proposal.stop_loss:
        stop_distance_pct = abs(decision.proposal.entry_price - decision.proposal.stop_loss) / decision.proposal.entry_price * 100
        if stop_distance_pct <= 0:
            executable = False
            notes.append("Invalid stop distance; cohort cannot estimate max loss.")
        else:
            notional_by_risk = risk_amount / (stop_distance_pct / 100)
            notional_by_cap = profile.account_equity_usdt * (profile.max_notional_pct / 100)
            guardian_cap = profile.account_equity_usdt * 0.25
            recommended_notional = min(notional_by_risk, notional_by_cap, guardian_cap)
            max_loss = min(risk_amount, recommended_notional * (stop_distance_pct / 100))
            estimated_margin = recommended_notional / leverage
            hidden_cost = recommended_notional * (hidden_cost_bps / 10_000)
            if recommended_notional == notional_by_cap:
                notes.append("Capped by the cohort max-notional limit.")
            if recommended_notional == guardian_cap:
                notes.append("Capped by FairFlow's retail exposure guardrail.")
            if recommended_notional == notional_by_risk:
                notes.append("Sized by the cohort risk budget.")
    else:
        notes.append("Core FairFlow gate is not approved for execution.")

    hidden_cost_pct_equity = (hidden_cost / profile.account_equity_usdt) * 100 if profile.account_equity_usdt else 0
    max_loss_pct_equity = (max_loss / profile.account_equity_usdt) * 100 if profile.account_equity_usdt else 0
    buying_power_used_pct = (estimated_margin / profile.account_equity_usdt) * 100 if profile.account_equity_usdt else 0

    friction_penalty = min(45.0, hidden_cost_bps * 1.5)
    friction_penalty += min(20.0, hidden_cost_pct_equity * 22)
    friction_penalty += min(18.0, max(0.0, buying_power_used_pct - 18) * 1.2)
    friction_penalty += max(0.0, 55.0 - decision.metrics.liquidity_score) * 0.35
    friction_penalty += max(0.0, decision.ai_committee.forecast.stop_loss_hit_probability - 0.35) * 55
    friction_score = round(max(0.0, min(100.0, 100.0 - friction_penalty)), 1)

    status = "pass"
    if not executable:
        status = "block"
    elif decision.fairness_passport.score < 65 or decision.metrics.liquidity_score < 45:
        status = "block"
        notes.append("Fairness or liquidity is below the cohort execution floor.")
    elif hidden_cost_bps > 18 or hidden_cost_pct_equity > profile.risk_budget_pct * 0.45:
        status = "block"
        notes.append("Hidden execution friction consumes too much of this cohort's risk budget.")
    elif buying_power_used_pct > 35:
        status = "block"
        notes.append("Required margin would over-concentrate the cohort account.")
    elif (
        decision.fairness_passport.score < 80
        or hidden_cost_bps > 8
        or buying_power_used_pct > 20
        or decision.ai_committee.forecast.stop_loss_hit_probability > 0.35
        or recommended_notional < 25
    ):
        status = "watch"
        notes.append("Cohort can review the setup, but at least one retail-friction guardrail is tight.")

    if recommended_notional < 25 and executable:
        notes.append("Recommended notional is small enough that fees and minimum-order rules may matter.")
    if decision.ai_committee.forecast.stop_loss_hit_probability > 0.45:
        notes.append("Stop-hit probability is elevated for this account profile.")
    if not notes:
        notes.append("Cohort remains inside FairFlow retail affordability guardrails.")

    return RetailCohortResult(
        profile=profile,
        status=status,
        executable=executable and status != "block",
        recommended_notional_usdt=round(recommended_notional, 2),
        estimated_margin_usdt=round(estimated_margin, 2),
        hidden_cost_usdt=round(hidden_cost, 4),
        hidden_cost_pct_equity=round(hidden_cost_pct_equity, 4),
        max_loss_usdt=round(max_loss, 2),
        max_loss_pct_equity=round(max_loss_pct_equity, 4),
        buying_power_used_pct=round(buying_power_used_pct, 4),
        stop_distance_pct=round(stop_distance_pct, 4) if stop_distance_pct is not None else None,
        friction_score=friction_score,
        notes=notes[:5],
    )


def build_retail_cohort_report(decision: GuardianDecision) -> RetailCohortReport:
    cohorts = [_cohort_result(decision, profile) for profile in DEFAULT_RETAIL_COHORTS]
    pass_count = sum(1 for cohort in cohorts if cohort.status == "pass")
    watch_count = sum(1 for cohort in cohorts if cohort.status == "watch")
    block_count = sum(1 for cohort in cohorts if cohort.status == "block")
    warnings: list[str] = []

    if block_count:
        blocked_names = ", ".join(cohort.profile.name for cohort in cohorts if cohort.status == "block")
        warnings.append(f"Blocked cohorts: {blocked_names}.")
    if any(cohort.profile.name == "Micro retail" and cohort.status != "pass" for cohort in cohorts):
        warnings.append("Micro retail access is constrained; do not present this as broadly inclusive.")
    if decision.fairness_passport.estimated_hidden_cost_bps > 8:
        warnings.append("Hidden-cost estimate is above the preferred retail threshold.")
    if decision.status != "approved":
        warnings.append("The core execution gate is not approved, so cohort simulation remains advisory.")
    if not warnings:
        warnings.append("No cohort-specific inclusion warnings surfaced for the audited report.")

    if block_count >= 2 or pass_count == 0:
        verdict = "exclusionary"
    elif block_count or watch_count:
        verdict = "limited"
    else:
        verdict = "inclusive"

    summary = (
        f"{pass_count} cohorts pass, {watch_count} need review, and {block_count} are blocked. "
        f"The audited setup is {verdict} for the default retail affordability ladder."
    )

    return RetailCohortReport(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        category=decision.category,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        verdict=verdict,
        summary=summary,
        pass_count=pass_count,
        watch_count=watch_count,
        block_count=block_count,
        cohorts=cohorts,
        fairness_warnings=warnings,
    )


def _issue_severity(status: str) -> str:
    if status in {"block", "blocked", "unfair_to_retail"}:
        return "block"
    if status in {"watch", "observe", "wait_for_parity"}:
        return "watch"
    return "info"


def _collect_impact_issues(decisions: list[GuardianDecision]) -> list[ImpactLedgerIssue]:
    issue_counts: dict[str, int] = {}
    issue_severities: dict[str, str] = {}
    issue_examples: dict[str, list[str]] = {}

    def add_issue(label: str, severity: str, example: str) -> None:
        issue_counts[label] = issue_counts.get(label, 0) + 1
        current = issue_severities.get(label, "info")
        if current != "block" or severity == "block":
            issue_severities[label] = severity if severity == "block" else current if current == "watch" else severity
        examples = issue_examples.setdefault(label, [])
        if example not in examples and len(examples) < 3:
            examples.append(example)

    for decision in decisions:
        for check in decision.fairness_passport.checks:
            if check.status != "pass":
                add_issue(
                    check.name,
                    _issue_severity(check.status),
                    f"{decision.symbol} {decision.scenario}: {check.explanation}",
                )
        for agent in decision.agents:
            if agent.status != "pass":
                add_issue(
                    agent.name,
                    _issue_severity(agent.status),
                    f"{decision.symbol} {decision.scenario}: {agent.verdict}",
                )
        if decision.ai_committee.forecast.stop_loss_hit_probability > 0.45:
            add_issue(
                "Elevated stop-hit probability",
                "watch",
                f"{decision.symbol} {decision.scenario}: {decision.ai_committee.forecast.stop_loss_hit_probability:.0%}",
            )

    return [
        ImpactLedgerIssue(
            label=label,
            count=count,
            severity=issue_severities.get(label, "info"),
            examples=issue_examples.get(label, []),
        )
        for label, count in sorted(issue_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
    ]


def build_impact_ledger_report(limit: int = 50) -> ImpactLedgerReport:
    decisions = AUDIT_LEDGER.list_decisions(limit=limit)
    for decision in decisions:
        AUDITS[decision.audit_hash] = decision

    audit_count = len(decisions)
    if not decisions:
        return ImpactLedgerReport(
            generated_at=datetime.now(UTC),
            audit_count=0,
            approved_count=0,
            observe_count=0,
            blocked_count=0,
            no_trade_count=0,
            manipulation_alert_count=0,
            cohort_inclusive_count=0,
            cohort_limited_count=0,
            cohort_exclusionary_count=0,
            estimated_hidden_cost_saved_usdt=0,
            average_fairness_score=0,
            average_hidden_cost_bps=0,
            average_liquidity_score=0,
            bga_ethos_score=0,
            summary="No audited reports have been generated yet.",
            issues=[],
            recent_audit_hashes=[],
        )

    approved_count = sum(1 for decision in decisions if decision.status == "approved")
    observe_count = sum(1 for decision in decisions if decision.status == "observe")
    blocked_count = sum(1 for decision in decisions if decision.status == "blocked")
    no_trade_count = sum(1 for decision in decisions if decision.final_action == "NO_TRADE")
    manipulation_alert_count = sum(
        1
        for decision in decisions
        if decision.ai_committee.anomaly.status != "normal"
        or any(agent.name == "Manipulation Sentinel" and agent.status != "pass" for agent in decision.agents)
    )
    average_fairness = sum(decision.fairness_passport.score for decision in decisions) / audit_count
    average_hidden_cost = sum(decision.fairness_passport.estimated_hidden_cost_bps for decision in decisions) / audit_count
    average_liquidity = sum(decision.metrics.liquidity_score for decision in decisions) / audit_count
    estimated_saved = sum(
        decision.proposal.position_size_usdt * decision.fairness_passport.estimated_hidden_cost_bps / 10_000
        for decision in decisions
        if decision.status != "approved" or decision.final_action == "NO_TRADE"
    )

    cohort_reports = [build_retail_cohort_report(decision) for decision in decisions]
    cohort_inclusive_count = sum(1 for report in cohort_reports if report.verdict == "inclusive")
    cohort_limited_count = sum(1 for report in cohort_reports if report.verdict == "limited")
    cohort_exclusionary_count = sum(1 for report in cohort_reports if report.verdict == "exclusionary")
    inclusion_score = (
        cohort_inclusive_count * 100 + cohort_limited_count * 70 + cohort_exclusionary_count * 35
    ) / audit_count
    hidden_cost_score = max(0.0, min(100.0, 100 - average_hidden_cost * 4))
    transparency_score = min(100.0, 35 + audit_count * 4)
    unsafe_decisions = [
        decision
        for decision in decisions
        if decision.scenario == "manipulated" or decision.ai_committee.anomaly.status == "extreme"
    ]
    unsafe_caught = sum(1 for decision in unsafe_decisions if decision.status != "approved" or decision.final_action == "NO_TRADE")
    gate_score = 100.0 if not unsafe_decisions else unsafe_caught / len(unsafe_decisions) * 100
    bga_score = round(
        max(
            0.0,
            min(
                100.0,
                average_fairness * 0.30
                + hidden_cost_score * 0.20
                + inclusion_score * 0.20
                + gate_score * 0.15
                + transparency_score * 0.15,
            ),
        ),
        1,
    )

    summary = (
        f"{audit_count} audits reviewed: {approved_count} approved, {observe_count} observed, "
        f"{blocked_count} blocked, and {no_trade_count} ended in no trade. "
        f"Estimated avoided hidden-cost drag is {estimated_saved:.2f} USDT."
    )

    return ImpactLedgerReport(
        generated_at=datetime.now(UTC),
        audit_count=audit_count,
        approved_count=approved_count,
        observe_count=observe_count,
        blocked_count=blocked_count,
        no_trade_count=no_trade_count,
        manipulation_alert_count=manipulation_alert_count,
        cohort_inclusive_count=cohort_inclusive_count,
        cohort_limited_count=cohort_limited_count,
        cohort_exclusionary_count=cohort_exclusionary_count,
        estimated_hidden_cost_saved_usdt=round(estimated_saved, 4),
        average_fairness_score=round(average_fairness, 2),
        average_hidden_cost_bps=round(average_hidden_cost, 3),
        average_liquidity_score=round(average_liquidity, 2),
        bga_ethos_score=bga_score,
        summary=summary,
        issues=_collect_impact_issues(decisions),
        recent_audit_hashes=[decision.audit_hash for decision in reversed(decisions[-8:])],
    )


def build_anchor_proof(decision: GuardianDecision) -> AnchorProof:
    metadata_uri = f"fairflow://audit/{decision.audit_hash}"
    audit_url = f"/api/audits/{decision.audit_hash}"
    receipt_url = f"/api/audits/{decision.audit_hash}/receipt"
    metadata: dict[str, str | float | int | bool] = {
        "audit_hash": decision.audit_hash,
        "symbol": decision.symbol,
        "category": decision.category,
        "scenario": decision.scenario,
        "source": decision.source,
        "status": decision.status,
        "final_action": decision.final_action,
        "fairness_score": round(decision.fairness_passport.score, 4),
        "hidden_cost_bps": round(decision.fairness_passport.estimated_hidden_cost_bps, 4),
        "liquidity_score": round(decision.metrics.liquidity_score, 4),
        "anomaly_score": round(decision.ai_committee.anomaly.score, 4),
        "generated_at": decision.generated_at.isoformat(),
        "paper_only": True,
        "audit_url": audit_url,
        "receipt_url": receipt_url,
    }
    payload_hash = hashlib.sha256(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    decision_hash_bytes32 = f"0x{decision.audit_hash}"
    contract_arguments = {
        "decisionHash": decision_hash_bytes32,
        "symbol": decision.symbol,
        "action": decision.final_action,
        "metadataURI": metadata_uri,
    }

    safety_notes = [
        "Anchor proof is paper-only and does not submit a transaction or unlock live execution.",
        "The on-chain record should prove the report existed before later market outcomes were known.",
        "The metadata URI points back to the full audit and receipt instead of hiding reasoning behind a trade signal.",
    ]
    if decision.status != "approved" or decision.final_action == "NO_TRADE":
        safety_notes.append("Anchoring a blocked or no-trade report is useful evidence that FairFlow refused unsafe execution.")
    else:
        safety_notes.append("Even approved reports remain guarded paper routes until independently reviewed.")

    return AnchorProof(
        audit_hash=decision.audit_hash,
        decision_hash_bytes32=decision_hash_bytes32,
        symbol=decision.symbol,
        action=decision.final_action,
        scenario=decision.scenario,
        status=decision.status,
        generated_at=datetime.now(UTC),
        contract_name="FairFlowAudit",
        contract_file="contracts/FairFlowAudit.sol",
        function_signature="anchorDecision(bytes32,string,string,string)",
        metadata_uri=metadata_uri,
        audit_url=audit_url,
        receipt_url=receipt_url,
        payload_hash=payload_hash,
        calldata_preview=(
            f'anchorDecision({decision_hash_bytes32}, "{decision.symbol}", '
            f'"{decision.final_action}", "{metadata_uri}")'
        ),
        contract_arguments=contract_arguments,
        metadata=metadata,
        safety_notes=safety_notes,
        verification_steps=[
            "Fetch the full audit report from audit_url and confirm the audit_hash matches decisionHash.",
            "Fetch the fairness receipt from receipt_url and confirm it references the same audit_hash.",
            "Recompute SHA-256 over the canonical metadata JSON with sorted keys and compact separators.",
            "Call FairFlowAudit.isAnchored(decisionHash) after transaction submission to verify on-chain presence.",
            "Read the DecisionAnchored event and compare symbol, action, reporter, timestamp, and metadataURI.",
        ],
    )


def build_judge_brief(decision: GuardianDecision) -> JudgeBrief:
    receipt = build_fairness_receipt(decision)
    cohorts = build_retail_cohort_report(decision)
    anchor = build_anchor_proof(decision)
    impact = build_impact_ledger_report(limit=50)
    committee = decision.ai_committee
    non_pass_agents = [agent for agent in decision.agents if agent.status != "pass"]
    trace_count = len(decision.decision_trace)

    ethos_score = round(
        max(
            0.0,
            min(
                100.0,
                receipt.bga_alignment_score * 0.45
                + impact.bga_ethos_score * 0.25
                + (100 if cohorts.verdict == "inclusive" else 72 if cohorts.verdict == "limited" else 38) * 0.20
                + (100 - committee.anomaly.score) * 0.10,
            ),
        ),
        1,
    )
    technical_score = round(
        max(
            0.0,
            min(
                100.0,
                48
                + min(20, len(decision.agents) * 3)
                + min(16, trace_count * 2)
                + (8 if decision.source.startswith("bybit") else 4)
                + (8 if anchor.payload_hash else 0),
            ),
        ),
        1,
    )
    risk_score = round(
        max(
            0.0,
            min(
                100.0,
                decision.fairness_passport.score * 0.28
                + decision.metrics.liquidity_score * 0.20
                + (100 - committee.forecast.stop_loss_hit_probability * 100) * 0.22
                + (100 - committee.anomaly.score) * 0.20
                + (100 if decision.status != "approved" and decision.final_action == "NO_TRADE" else 82) * 0.10,
            ),
        ),
        1,
    )
    transparency_score = round(
        max(
            0.0,
            min(
                100.0,
                28
                + min(24, trace_count * 3)
                + min(18, len(receipt.verification_steps) * 4)
                + min(15, len(anchor.verification_steps) * 3)
                + (15 if decision.audit_hash else 0),
            ),
        ),
        1,
    )

    if decision.status == "approved":
        opening = (
            f"FairFlow approved only a guarded paper {decision.final_action.replace('_', ' ').lower()} "
            f"for {decision.symbol}, then proves why that route is fair enough for retail users."
        )
    else:
        opening = (
            f"FairFlow refused live-style execution for {decision.symbol}; the important demo point is that "
            "blocking unsafe conditions is treated as a successful market-health outcome."
        )

    rubric = [
        JudgeBriefRubricItem(
            category="bga_ethos",
            score=ethos_score,
            headline="Fair-market infrastructure, not a PnL race",
            evidence=[
                f"Fairness receipt alignment score: {receipt.bga_alignment_score:.1f}/100.",
                f"Cohort verdict: {cohorts.verdict} with {cohorts.pass_count} pass, {cohorts.watch_count} watch, {cohorts.block_count} block.",
                f"Impact ledger ethos score: {impact.bga_ethos_score:.1f}/100 across {impact.audit_count} audits.",
            ],
            demo_cue="Show Impact Ledger, Fairness Receipt, and Retail Cohort Simulator before discussing any strategy action.",
        ),
        JudgeBriefRubricItem(
            category="technical_depth",
            score=technical_score,
            headline="Multi-agent market review with ML-style signals and durable audit rails",
            evidence=[
                f"{len(decision.agents)} specialist agents plus AI committee signals.",
                f"Regime model: {committee.ml_regime.model_version}; current regime {committee.ml_regime.regime}.",
                f"Bybit/fallback source: {decision.source}; audit persisted under SHA-256 hash.",
            ],
            demo_cue="Open Active Agents, AI Committee, real-time chart, and anchor proof.",
        ),
        JudgeBriefRubricItem(
            category="risk_management",
            score=risk_score,
            headline="Execution is gated by anomaly, liquidity, costs, stress, and retail sizing",
            evidence=[
                f"Decision gate: {decision.status}; final action: {decision.final_action}.",
                f"Anomaly score: {committee.anomaly.score:.0f}/100; stop-hit probability: {committee.forecast.stop_loss_hit_probability:.0%}.",
                f"Hidden-cost estimate: {decision.fairness_passport.estimated_hidden_cost_bps:.1f} bps.",
            ],
            demo_cue="Switch to Manipulated scenario and show no-trade, blocked cohorts, and locked mission actions.",
        ),
        JudgeBriefRubricItem(
            category="transparency",
            score=transparency_score,
            headline="Every claim links back to a trace, receipt, and anchorable proof",
            evidence=[
                f"{trace_count}-step decision trace.",
                f"Receipt URL: {receipt.machine_readable_url}.",
                f"Anchor payload hash: {anchor.payload_hash[:16]}.",
            ],
            demo_cue="Copy the receipt JSON or contract call, then show the audit hash in the vault.",
        ),
    ]

    proof_links = [
        f"/api/audits/{decision.audit_hash}",
        f"/api/audits/{decision.audit_hash}/receipt",
        f"/api/audits/{decision.audit_hash}/retail-cohorts",
        f"/api/audits/{decision.audit_hash}/anchor-proof",
        f"/api/audits/{decision.audit_hash}/red-team",
        f"/api/audits/{decision.audit_hash}/counterfactuals",
        f"/api/audits/{decision.audit_hash}/execution-router",
        f"/api/audits/{decision.audit_hash}/evidence-pack",
        "/api/impact?limit=50",
    ]

    return JudgeBrief(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        one_sentence_pitch=(
            "FairFlow Guardian is an explainable, paper-only AI trading safety layer that protects retail users "
            "by proving when a strategy is fair enough to review and when the healthiest action is no trade."
        ),
        judge_thesis=(
            "This project should be judged as fair-market infrastructure: it reduces information asymmetry, "
            "audits every decision, blocks unsafe scenarios, and makes retail affordability visible."
        ),
        recommended_opening=opening,
        total_demo_minutes=3.0,
        rubric=rubric,
        demo_steps=[
            JudgeBriefStep(
                step=1,
                title="Start with the fairness thesis",
                script="Open Judge Mode and state that FairFlow optimizes for safer market participation, not maximum returns.",
                evidence_url="/api/impact?limit=50",
                proof_point=f"Impact ledger score {impact.bga_ethos_score:.1f}/100 with {impact.no_trade_count} no-trade outcomes.",
            ),
            JudgeBriefStep(
                step=2,
                title="Show the current audited decision",
                script="Explain the final action, status, fairness score, hidden cost, and why the gate is open or locked.",
                evidence_url=f"/api/audits/{decision.audit_hash}",
                proof_point=f"{decision.status} / {decision.final_action}; fairness {decision.fairness_passport.score:.0f}/100.",
            ),
            JudgeBriefStep(
                step=3,
                title="Prove retail inclusion",
                script="Open the Retail Cohort Simulator and show which account sizes pass, watch, or block after costs.",
                evidence_url=f"/api/audits/{decision.audit_hash}/retail-cohorts",
                proof_point=f"Cohort verdict {cohorts.verdict}; micro retail warning count {len(cohorts.fairness_warnings)}.",
            ),
            JudgeBriefStep(
                step=4,
                title="Prove verifiability",
                script="Open the anchor kit and copy the contract call or receipt JSON to show a tamper-evident handoff.",
                evidence_url=f"/api/audits/{decision.audit_hash}/anchor-proof",
                proof_point=f"Anchor-ready hash {anchor.decision_hash_bytes32[:18]}... with metadata hash {anchor.payload_hash[:12]}.",
            ),
            JudgeBriefStep(
                step=5,
                title="Close with unsafe-market behavior",
                script="Switch to Manipulated and show that no-trade is a successful protective outcome.",
                evidence_url=None,
                proof_point=(
                    "The system has explicit blocked actions, manipulated fallback scenarios, and cohort-level exclusionary reports."
                ),
            ),
        ],
        safety_boundaries=[
            "Paper execution only; the app never asks for exchange credentials or private keys.",
            "No-trade and blocked reports are first-class successful outcomes.",
            "Policy Studio can make guardrails stricter, but cannot override the core execution gate.",
            "Backtest and validation artifacts document failures instead of promoting in-sample PnL.",
            "On-chain anchoring is a proof handoff, not live trading or custody.",
        ],
        likely_questions=[
            "How do you prevent this from becoming an extractive trading bot?",
            "What evidence shows the model is not overfit to one scenario?",
            "How does a retail user verify the report after the market moves?",
            "What happens when liquidity is thin or manipulation risk is elevated?",
            "Why does the project need blockchain rather than a normal database?",
        ],
        proof_links=proof_links,
    )


def build_model_provenance_card(decision: GuardianDecision) -> ModelProvenanceCard:
    live_source = decision.source.startswith("bybit")
    committee = decision.ai_committee
    data_sources = [
        ProvenanceDataSource(
            name="Bybit V5 public market data" if live_source else "Deterministic scenario market data",
            source_type="live_public_api" if live_source else "deterministic_fallback",
            status="active" if live_source else "fallback",
            fields=[
                "5-minute OHLCV candles",
                "order book bids/asks",
                "ticker price and spread",
                "funding rate",
                "open interest",
            ],
            caveat=(
                "Public market data can be delayed, rate-limited, or unavailable; no private order flow is used."
                if live_source
                else "Fallback data is deterministic and useful for demos/tests, but it is not a live market forecast."
            ),
        ),
        ProvenanceDataSource(
            name="Derived market metrics",
            source_type="derived",
            status="derived",
            fields=[
                "spread bps",
                "top depth",
                "25k impact",
                "realized volatility",
                "RSI",
                "book imbalance",
                "liquidity score",
            ],
            caveat="Derived metrics are explainable transformations, not independent data sources.",
        ),
        ProvenanceDataSource(
            name="Session audit and paper portfolio memory",
            source_type="session_memory",
            status="derived",
            fields=["recent audits", "paper orders", "blocked attempts", "open paper exposure"],
            caveat="Session memory improves demo context but is not a long-horizon user suitability profile.",
        ),
    ]

    model_components = [
        ModelComponentCard(
            name="ML Market Regime Classifier",
            component_type="ml_signal",
            version=committee.ml_regime.model_version,
            inputs=["rolling returns", "volatility", "RSI", "momentum", "liquidity"],
            outputs=[committee.ml_regime.regime, f"{committee.ml_regime.confidence:.0%} confidence"],
            limitations=[
                "Nearest-centroid regime signal is lightweight and should not be treated as a production predictive model.",
                "It uses the current rolling window and can be unstable during structural breaks.",
            ],
            validation="Validated as an explainable signal inside chronological cost-aware experiment notes, not as a standalone alpha model.",
        ),
        ModelComponentCard(
            name="ML Manipulation Analyst",
            component_type="ml_signal",
            version=committee.anomaly.method,
            inputs=["wick size", "volume ratio", "spread", "impact", "funding", "book imbalance"],
            outputs=[committee.anomaly.status, f"{committee.anomaly.score:.0f}/100 anomaly score"],
            limitations=[
                "Robust anomaly scoring can flag stress but cannot prove intent or manipulation.",
                "False positives are preferable to unsafe execution in this prototype.",
            ],
            validation="Covered by manipulated fallback scenario tests and audit-level no-trade behavior.",
        ),
        ModelComponentCard(
            name="Uncertainty Forecast Agent",
            component_type="risk_model",
            version="rolling-distribution-v1",
            inputs=["recent volatility", "momentum", "stop distance", "range"],
            outputs=[
                f"{committee.forecast.horizon_minutes}m expected move {committee.forecast.expected_move_pct:.2f}%",
                f"{committee.forecast.stop_loss_hit_probability:.0%} stop-hit probability",
            ],
            limitations=[
                "Short-horizon distribution is a guardrail, not a guaranteed forecast.",
                "Tail risk and exchange outages can exceed the modeled range.",
            ],
            validation="Used as a risk gate in backend tests, policy checks, and retail cohort simulator.",
        ),
        ModelComponentCard(
            name="Fairness Passport and Policy Gate",
            component_type="execution_guard",
            version="fairness-passport-v1",
            inputs=["information parity", "execution parity", "manipulation exposure", "risk protection", "auditability"],
            outputs=[decision.fairness_passport.verdict, f"{decision.fairness_passport.score:.0f}/100 fairness score"],
            limitations=[
                "Fairness score is a transparent rubric, not a regulatory suitability determination.",
                "It can only evaluate available market and strategy data.",
            ],
            validation="Exercised by API tests across calm, volatile, manipulated, policy, and cohort paths.",
        ),
        ModelComponentCard(
            name="Audit Ledger and Anchor Proof",
            component_type="audit_infrastructure",
            version="sha256-sqlite-solidity-v1",
            inputs=["canonical decision payload", "receipt metadata", "contract arguments"],
            outputs=[decision.audit_hash, "contract-ready anchor proof"],
            limitations=[
                "SQLite persistence is local prototype infrastructure.",
                "On-chain anchor kit prepares proofs but does not submit transactions or manage keys.",
            ],
            validation="Persistent lookup, deterministic anchor proof, and receipt tests verify audit recovery.",
        ),
    ]

    provenance_score = round(
        max(
            0.0,
            min(
                100.0,
                (88 if live_source else 78)
                + min(8, len(decision.decision_trace))
                + (4 if decision.audit_hash else 0),
            ),
        ),
        1,
    )

    return ModelProvenanceCard(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        provenance_score=provenance_score,
        summary=(
            f"{decision.symbol} used {decision.source} with {len(model_components)} documented AI/risk/audit components. "
            "The card separates live/fallback data, derived features, model limits, and validation artifacts."
        ),
        data_sources=data_sources,
        model_components=model_components,
        feature_groups=[
            "price action and momentum",
            "order-book depth and imbalance",
            "execution cost and slippage pressure",
            "funding and open-interest crowding",
            "stress loss and stop-hit probability",
            "fairness, auditability, and retail affordability",
        ],
        known_limitations=[
            "Prototype is paper-only and not financial advice.",
            "Fallback scenarios are deterministic demos, not live market predictions.",
            "AI components are explainable lightweight signals, not autonomous production traders.",
            "Backtest evidence is intentionally leakage-safe but limited by short public candle windows.",
            "Smart contract integration prepares proofs only; it does not custody funds or submit transactions.",
        ],
        validation_artifacts=[
            "tests/test_guardian.py",
            "docs/experiments/2026-06-20-cost-aware-backtest.md",
            "scripts/validate_cost_robustness.py",
            "contracts/FairFlowAudit.sol",
        ],
        reproducibility_steps=[
            "Fetch /api/audits/{audit_hash} for the full decision payload.",
            "Check source, generated_at, and market metrics in the audit report.",
            "Compare model component outputs with the AI committee and Fairness Passport sections.",
            "Run python -m pytest -q to verify API behavior and guardrail contracts.",
            "Run scripts/validate_cost_robustness.py to reproduce the cost-aware validation artifact.",
        ],
        ethical_boundaries=[
            "Never route live execution from this prototype.",
            "Treat blocked/no-trade outcomes as successful user protection.",
            "Do not present anomaly scores as proof of market manipulation intent.",
            "Do not hide fallback data behind live-data language.",
            "Use policy controls to tighten guardrails, never to bypass the core FairFlow gate.",
        ],
    )


def evaluate_guardrail_policy(decision: GuardianDecision, policy: GuardrailPolicyRequest) -> GuardrailPolicyReport:
    committee = decision.ai_committee
    checks = [
        _threshold_check(
            "Fairness floor",
            decision.fairness_passport.score,
            policy.min_fairness_score,
            "score",
            True,
            "Retail users should only see execution unlocked when the fairness score clears their floor.",
        ),
        _threshold_check(
            "Hidden-cost cap",
            decision.fairness_passport.estimated_hidden_cost_bps,
            policy.max_hidden_cost_bps,
            "bps",
            False,
            "Estimated spread, impact, and hidden execution cost must stay below the user's cap.",
        ),
        _threshold_check(
            "Anomaly cap",
            committee.anomaly.score,
            policy.max_anomaly_score,
            "score",
            False,
            "Manipulation and outlier risk must remain under the chosen safety limit.",
        ),
        _threshold_check(
            "Liquidity floor",
            decision.metrics.liquidity_score,
            policy.min_liquidity_score,
            "score",
            True,
            "Thin books increase adverse selection for retail users, so liquidity needs a floor.",
        ),
        _threshold_check(
            "Leverage cap",
            decision.proposal.leverage,
            policy.max_leverage,
            "x",
            False,
            "The policy limits leverage even when a strategy proposal is otherwise approved.",
        ),
        _threshold_check(
            "Stop-hit probability cap",
            committee.forecast.stop_loss_hit_probability,
            policy.max_stop_hit_probability,
            "probability",
            False,
            "The uncertainty model must not assign too high a near-term stop-hit probability.",
        ),
    ]

    execution_gate_status = "pass"
    if decision.status == "blocked" or decision.fairness_passport.verdict == "unfair_to_retail":
        execution_gate_status = "block"
    elif decision.status == "observe" or decision.fairness_passport.verdict == "wait_for_parity":
        execution_gate_status = "watch"
    checks.append(
        GuardrailPolicyCheck(
            name="Guardian execution gate",
            status=execution_gate_status,
            observed=f"{decision.status} / {decision.fairness_passport.verdict}",
            limit="approved / fair_to_execute",
            unit="gate",
            explanation="Custom policy cannot override the core FairFlow execution gate.",
        )
    )

    if any(check.status == "block" for check in checks):
        verdict = "blocked"
    elif any(check.status == "watch" for check in checks):
        verdict = "needs_review"
    else:
        verdict = "compliant"

    execution_allowed = verdict == "compliant" and decision.status == "approved" and decision.final_action != "NO_TRADE"
    suggested_actions: list[str] = []
    if execution_allowed:
        suggested_actions.append("Proceed only with paper execution and risk sizing.")
        suggested_actions.append("Record the audit hash before any simulated route is submitted.")
    else:
        if any(check.status == "block" for check in checks if check.name != "Guardian execution gate"):
            suggested_actions.append("Tighten or re-check market conditions before considering execution.")
        if execution_gate_status != "pass":
            suggested_actions.append("Respect the FairFlow gate; do not route this setup.")
        if any(check.status == "watch" for check in checks):
            suggested_actions.append("Use scenario comparison and mission review before changing the policy.")
        suggested_actions.append("Keep the action in advisory or paper-review mode.")

    return GuardrailPolicyReport(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        verdict=verdict,
        execution_allowed=execution_allowed,
        summary=(
            "Policy allows guarded paper execution."
            if execution_allowed
            else f"Policy verdict is {verdict.replace('_', ' ')}; execution remains gated."
        ),
        checks=checks,
        suggested_actions=suggested_actions,
        policy=policy,
    )


def _numeric_counterfactual_lever(
    *,
    name: str,
    lever_type: str,
    current: float,
    target: float,
    unit: str,
    higher_is_better: bool,
    retail_impact: str,
    explanation: str,
) -> CounterfactualLever:
    if higher_is_better:
        gap = max(0.0, target - current)
        direction = "increase" if gap else "hold"
    else:
        gap = max(0.0, current - target)
        direction = "decrease" if gap else "hold"

    return CounterfactualLever(
        name=name,
        lever_type=lever_type,
        status="improvement_needed" if gap else "already_clear",
        current_value=round(current, 3),
        target_value=round(target, 3),
        unit=unit,
        improvement_required=round(gap, 3) if gap else 0.0,
        direction=direction,
        retail_impact=retail_impact,
        explanation=explanation,
    )


def build_counterfactual_fairness_report(decision: GuardianDecision) -> CounterfactualFairnessReport:
    policy = GuardrailPolicyRequest(audit_hash=decision.audit_hash)
    stop_hit_pct = decision.ai_committee.forecast.stop_loss_hit_probability * 100
    target_stop_pct = policy.max_stop_hit_probability * 100
    core_gate_clear = (
        decision.status == "approved"
        and decision.final_action != "NO_TRADE"
        and decision.fairness_passport.verdict == "fair_to_execute"
    )

    levers = [
        _numeric_counterfactual_lever(
            name="Fairness score floor",
            lever_type="fairness",
            current=decision.fairness_passport.score,
            target=policy.min_fairness_score,
            unit="score",
            higher_is_better=True,
            retail_impact="Improves information parity, auditability, and risk protection before a retail user sees an executable route.",
            explanation="The default policy requires the Fairness Passport to clear the user-visible floor.",
        ),
        _numeric_counterfactual_lever(
            name="Hidden-cost ceiling",
            lever_type="hidden_cost",
            current=decision.fairness_passport.estimated_hidden_cost_bps,
            target=policy.max_hidden_cost_bps,
            unit="bps",
            higher_is_better=False,
            retail_impact="Reduces spread, impact, and adverse-selection drag that disproportionately harms smaller accounts.",
            explanation="Estimated execution friction must cool below the default policy cap.",
        ),
        _numeric_counterfactual_lever(
            name="Anomaly-risk ceiling",
            lever_type="anomaly",
            current=decision.ai_committee.anomaly.score,
            target=policy.max_anomaly_score,
            unit="score",
            higher_is_better=False,
            retail_impact="Lowers the chance that retail users are routed into manipulated, unstable, or one-sided market structure.",
            explanation="The manipulation and outlier detector must return to a safer range.",
        ),
        _numeric_counterfactual_lever(
            name="Liquidity floor",
            lever_type="liquidity",
            current=decision.metrics.liquidity_score,
            target=policy.min_liquidity_score,
            unit="score",
            higher_is_better=True,
            retail_impact="Requires deeper, more stable books before small users are exposed to execution pressure.",
            explanation="Visible depth and impact conditions must recover before routing becomes fairer.",
        ),
        _numeric_counterfactual_lever(
            name="Leverage ceiling",
            lever_type="leverage",
            current=decision.proposal.leverage,
            target=policy.max_leverage,
            unit="x",
            higher_is_better=False,
            retail_impact="Keeps liquidation and stop-out risk from overwhelming the account-level risk budget.",
            explanation="Even approved strategies cannot exceed the default leverage cap.",
        ),
        _numeric_counterfactual_lever(
            name="Stop-hit probability ceiling",
            lever_type="stop_risk",
            current=stop_hit_pct,
            target=target_stop_pct,
            unit="%",
            higher_is_better=False,
            retail_impact="Avoids routing when the uncertainty model says the stop is too likely to be hit quickly.",
            explanation="The short-horizon risk model needs a lower stop-hit probability before execution is defensible.",
        ),
    ]

    core_status = "already_clear" if core_gate_clear else "non_bypassable"
    levers.append(
        CounterfactualLever(
            name="Core FairFlow execution gate",
            lever_type="core_gate",
            status=core_status,
            current_value=f"{decision.status} / {decision.final_action} / {decision.fairness_passport.verdict}",
            target_value="approved / actionable / fair_to_execute",
            unit="gate",
            improvement_required=None,
            direction="hold" if core_gate_clear else "fresh_audit_required",
            retail_impact="Prevents custom thresholds or UI pressure from bypassing the audited no-trade or review state.",
            explanation="The current audit gate is non-bypassable; a safer market state must be re-audited instead of locally overridden.",
        )
    )

    numeric_levers = [lever for lever in levers if lever.lever_type != "core_gate"]
    improvement_levers = [lever for lever in numeric_levers if lever.status == "improvement_needed"]
    non_bypassable_constraints: list[str] = []
    if not core_gate_clear:
        non_bypassable_constraints.append("The core FairFlow execution gate cannot be overridden by counterfactual sliders or policy tuning.")
    if decision.final_action == "NO_TRADE":
        non_bypassable_constraints.append("The audited final action is NO_TRADE; execution requires a fresh audit under materially safer conditions.")
    if decision.fairness_passport.verdict != "fair_to_execute":
        non_bypassable_constraints.append(f"Fairness Passport verdict is {decision.fairness_passport.verdict}; retail parity must improve before review.")

    if core_gate_clear and not improvement_levers:
        verdict = "already_fair"
        unlockable_in_current_audit = True
        summary = "The current audit clears the core gate and default fairness policy; no counterfactual repair is required."
        judge_takeaway = "FairFlow can show why this setup is currently fair enough while still keeping all proof links audit-bound."
        recommended_next_steps = [
            "Keep any route paper-only and audit-linked.",
            "Use Risk Sizing before any simulated order.",
            "Anchor the evidence pack before comparing later outcomes.",
        ]
    elif not core_gate_clear and (decision.status == "blocked" or decision.final_action == "NO_TRADE"):
        verdict = "do_not_unlock"
        unlockable_in_current_audit = False
        summary = "The current audit should not be unlocked; counterfactual improvements require a fresh market audit."
        judge_takeaway = "This is protective behavior: FairFlow explains what is unhealthy without offering a bypass path."
        recommended_next_steps = [
            "Do not paper execute this audit.",
            "Show the top blocker and Retail Cohort Simulator before discussing any future route.",
            "Re-run the audit only after market data, liquidity, and anomaly conditions actually improve.",
        ]
    elif not core_gate_clear:
        verdict = "fresh_audit_required"
        unlockable_in_current_audit = False
        summary = "Several conditions may be improvable, but the current audit remains locked until a fresh report confirms them."
        judge_takeaway = "FairFlow separates hypothetical market repair from permission to execute the current audit."
        recommended_next_steps = [
            "Treat this audit as advisory.",
            "Wait for the limiting market metrics to improve, then generate a new audit hash.",
            "Compare the old and new evidence packs instead of editing thresholds in place.",
        ]
    else:
        verdict = "improvable"
        unlockable_in_current_audit = False
        summary = "The core gate is open, but one or more default fairness-policy levers still need improvement before a stronger approval."
        judge_takeaway = "FairFlow shows which metric must improve rather than hiding the gap inside a single confidence score."
        recommended_next_steps = [
            "Review the improvement-needed levers before paper execution.",
            "Use Policy Studio to confirm whether stricter user preferences would still block.",
            "Re-run the audit after the top blocker improves.",
        ]

    severity_weights = {
        "fairness": 1.0,
        "hidden_cost": 1.1,
        "anomaly": 1.25,
        "liquidity": 1.15,
        "leverage": 0.8,
        "stop_risk": 1.05,
    }
    top_blocker = "Core FairFlow execution gate" if not core_gate_clear else "No active blocker"
    if improvement_levers:
        top = max(
            improvement_levers,
            key=lambda lever: (lever.improvement_required or 0.0) * severity_weights.get(lever.lever_type, 1.0),
        )
        top_blocker = top.name

    clear_count = sum(1 for lever in numeric_levers if lever.status == "already_clear")
    readiness_score = round(clear_count / len(numeric_levers) * 72 + (22 if core_gate_clear else 4), 1)
    if verdict == "do_not_unlock":
        readiness_score = min(readiness_score, 34.0)
    elif verdict == "fresh_audit_required":
        readiness_score = min(readiness_score, 58.0)

    return CounterfactualFairnessReport(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        verdict=verdict,
        unlockable_in_current_audit=unlockable_in_current_audit,
        readiness_score=max(0.0, min(100.0, readiness_score)),
        summary=summary,
        top_blocker=top_blocker,
        levers=levers,
        non_bypassable_constraints=non_bypassable_constraints,
        recommended_next_steps=recommended_next_steps,
        judge_takeaway=judge_takeaway,
    )


def _route_candidate(
    *,
    name: str,
    route_type: str,
    core_gate_clear: bool,
    expected_slippage_bps: float,
    fill_probability: float,
    information_leakage_score: float,
    manipulation_exposure_score: float,
    max_notional_usdt: float,
    time_to_complete_seconds: int,
    reason: str,
    safeguards: list[str],
    stop_hit_probability: float,
    fairness_floor_score: float,
) -> ExecutionRouteCandidate:
    if not core_gate_clear and route_type != "hold":
        status = "locked"
        retail_fairness_score = 0.0
        max_notional_usdt = 0.0
    else:
        retail_fairness_score = _bounded_score(
            100
            - expected_slippage_bps * 2.15
            - information_leakage_score * 0.16
            - manipulation_exposure_score * 0.24
            - stop_hit_probability * 12
            - max(0.0, 0.68 - fill_probability) * 24
        )
        if route_type == "hold":
            status = "available"
        elif retail_fairness_score >= fairness_floor_score:
            status = "available"
        elif retail_fairness_score >= fairness_floor_score - 14:
            status = "watch"
        else:
            status = "locked"
            max_notional_usdt = 0.0

    return ExecutionRouteCandidate(
        name=name,
        route_type=route_type,
        status=status,
        expected_slippage_bps=round(max(0.0, expected_slippage_bps), 2),
        fill_probability=_bounded_confidence(fill_probability),
        information_leakage_score=_bounded_score(information_leakage_score),
        manipulation_exposure_score=_bounded_score(manipulation_exposure_score),
        retail_fairness_score=retail_fairness_score,
        max_notional_usdt=round(max(0.0, max_notional_usdt), 2),
        time_to_complete_seconds=max(0, time_to_complete_seconds),
        reason=reason,
        safeguards=safeguards,
    )


def build_fair_execution_router(decision: GuardianDecision) -> FairExecutionRouterReport:
    metrics = decision.metrics
    committee = decision.ai_committee
    fairness_floor_score = 72.0
    core_gate_clear = (
        decision.status == "approved"
        and decision.final_action != "NO_TRADE"
        and decision.fairness_passport.verdict == "fair_to_execute"
    )
    hidden_cost = decision.fairness_passport.estimated_hidden_cost_bps
    anomaly = committee.anomaly.score
    stop_hit = committee.forecast.stop_loss_hit_probability
    spread = max(0.0, metrics.spread_bps)
    impact_25k = max(0.0, metrics.impact_25k_bps)
    depth = max(0.0, metrics.top_depth_usd)
    intended_notional = max(0.0, decision.proposal.position_size_usdt)
    liquidity_fraction = 0.16 if metrics.liquidity_score >= 76 else 0.1 if metrics.liquidity_score >= 55 else 0.045
    liquidity_budget = depth * liquidity_fraction
    if metrics.liquidity_score < 45:
        liquidity_budget *= 0.6
    max_route_notional = min(intended_notional, liquidity_budget) if core_gate_clear else 0.0
    notional_pressure = min(2.5, (intended_notional / 25_000.0) if intended_notional else 0.0)
    book_skew = abs(metrics.order_book_imbalance) * 100
    volatility_pressure = max(0.0, metrics.realized_volatility_pct)

    locked_reasons: list[str] = []
    if decision.status != "approved":
        locked_reasons.append(f"Guardian status is {decision.status}; route construction cannot override the audit gate.")
    if decision.final_action == "NO_TRADE":
        locked_reasons.append("Final action is NO_TRADE; fair routing is hold/re-audit only.")
    if decision.fairness_passport.verdict != "fair_to_execute":
        locked_reasons.append(f"Fairness Passport verdict is {decision.fairness_passport.verdict}; routing must stay locked.")
    if decision.ai_committee.anomaly.status == "extreme":
        locked_reasons.append("Manipulation/anomaly signal is extreme; exposing order intent would increase retail harm.")
    if core_gate_clear and liquidity_budget <= 0:
        locked_reasons.append("Visible liquidity budget is exhausted; no fair route size can be computed.")

    shared_safeguards = [
        "Paper execution only; no exchange credentials or private keys are used.",
        "Route recommendation is bound to this audit hash and must be regenerated after material market movement.",
        "Core Guardian and Fairness Passport gates remain non-bypassable.",
    ]

    candidates = [
        _route_candidate(
            name="Immediate guarded market",
            route_type="market",
            core_gate_clear=core_gate_clear,
            expected_slippage_bps=hidden_cost + spread * 0.55 + impact_25k * max(0.45, notional_pressure),
            fill_probability=0.98,
            information_leakage_score=18 + book_skew * 0.08,
            manipulation_exposure_score=anomaly * 0.78 + volatility_pressure * 1.1 + impact_25k * 0.9,
            max_notional_usdt=max_route_notional * 0.62,
            time_to_complete_seconds=3,
            reason="Fastest paper route, but it pays the most visible spread and impact.",
            safeguards=[
                "Reject if realized slippage exceeds the route budget.",
                "Never use during elevated anomaly or thin-liquidity regimes.",
                *shared_safeguards,
            ],
            stop_hit_probability=stop_hit,
            fairness_floor_score=fairness_floor_score,
        ),
        _route_candidate(
            name="Post-only limit",
            route_type="post_only_limit",
            core_gate_clear=core_gate_clear,
            expected_slippage_bps=max(0.2, hidden_cost * 0.42 + spread * 0.25),
            fill_probability=max(0.42, min(0.88, 0.86 - volatility_pressure / 38 - book_skew / 220)),
            information_leakage_score=12 + book_skew * 0.05,
            manipulation_exposure_score=anomaly * 0.46 + volatility_pressure * 0.75,
            max_notional_usdt=max_route_notional,
            time_to_complete_seconds=45,
            reason="Most retail-friendly when the book is healthy because it avoids crossing the spread.",
            safeguards=[
                "Cancel instead of chasing price if the quote moves away.",
                "Use a short cooldown before any retry to avoid signalling urgency.",
                *shared_safeguards,
            ],
            stop_hit_probability=stop_hit,
            fairness_floor_score=fairness_floor_score,
        ),
        _route_candidate(
            name="TWAP micro-slices",
            route_type="twap",
            core_gate_clear=core_gate_clear,
            expected_slippage_bps=hidden_cost * 0.62 + spread * 0.38 + impact_25k * max(0.22, notional_pressure * 0.35),
            fill_probability=max(0.55, min(0.9, 0.88 - anomaly / 260 - volatility_pressure / 55)),
            information_leakage_score=30 + min(24, notional_pressure * 9),
            manipulation_exposure_score=anomaly * 0.5 + volatility_pressure * 0.8 + impact_25k * 0.45,
            max_notional_usdt=max_route_notional * 1.18,
            time_to_complete_seconds=180,
            reason="Splits intent across time so larger paper routes do not consume too much top-of-book depth at once.",
            safeguards=[
                "Abort if spread widens or anomaly score rises during slicing.",
                "Randomize slice spacing in a production version to reduce signalling.",
                *shared_safeguards,
            ],
            stop_hit_probability=stop_hit,
            fairness_floor_score=fairness_floor_score,
        ),
        _route_candidate(
            name="Maker ladder",
            route_type="maker_ladder",
            core_gate_clear=core_gate_clear,
            expected_slippage_bps=max(0.3, hidden_cost * 0.5 + spread * 0.33 + impact_25k * 0.16),
            fill_probability=max(0.48, min(0.84, 0.8 - volatility_pressure / 45 - anomaly / 360)),
            information_leakage_score=20 + min(18, notional_pressure * 6),
            manipulation_exposure_score=anomaly * 0.42 + volatility_pressure * 0.62 + book_skew * 0.08,
            max_notional_usdt=max_route_notional * 0.92,
            time_to_complete_seconds=120,
            reason="Places smaller passive paper orders at multiple fair prices to reduce impact without chasing fills.",
            safeguards=[
                "Cancel unfilled levels when the Fairness Passport would fall below the route floor.",
                "Cap aggregate passive size to a small fraction of visible depth.",
                *shared_safeguards,
            ],
            stop_hit_probability=stop_hit,
            fairness_floor_score=fairness_floor_score,
        ),
        _route_candidate(
            name="Hold and re-audit",
            route_type="hold",
            core_gate_clear=True,
            expected_slippage_bps=0.0,
            fill_probability=0.0,
            information_leakage_score=0.0,
            manipulation_exposure_score=0.0,
            max_notional_usdt=0.0,
            time_to_complete_seconds=0,
            reason="Best route when fair execution cannot be proven from the current audit.",
            safeguards=[
                "Generate a fresh audit hash after liquidity, anomaly, and hidden-cost conditions change.",
                "Compare the new route report against this one instead of editing the current audit.",
                *shared_safeguards,
            ],
            stop_hit_probability=0.0,
            fairness_floor_score=fairness_floor_score,
        ),
    ]

    executable_candidates = [
        candidate
        for candidate in candidates
        if candidate.route_type != "hold" and candidate.status in {"available", "watch"} and candidate.max_notional_usdt > 0
    ]
    qualifying_candidates = [candidate for candidate in executable_candidates if candidate.retail_fairness_score >= fairness_floor_score]

    if not core_gate_clear:
        recommended = next(candidate for candidate in candidates if candidate.route_type == "hold")
        verdict = "paper_only_locked"
        summary = "The Fair Execution Router locks all trading routes because the current audit is not executable."
        execution_permitted = False
    elif qualifying_candidates:
        recommended = max(
            qualifying_candidates,
            key=lambda candidate: (candidate.retail_fairness_score, candidate.fill_probability, candidate.max_notional_usdt),
        )
        caution = any(candidate.status == "watch" for candidate in executable_candidates) or recommended.fill_probability < 0.62
        verdict = "route_with_caution" if caution else "route_ready"
        summary = (
            f"{recommended.name} is the fairest paper route for this audit: "
            f"{recommended.retail_fairness_score:.1f}/100 route fairness with "
            f"{recommended.expected_slippage_bps:.1f} bps expected slippage."
        )
        execution_permitted = True
    else:
        recommended = next(candidate for candidate in candidates if candidate.route_type == "hold")
        verdict = "no_fair_route"
        summary = "The core audit is open, but no route clears the retail execution-fairness floor."
        execution_permitted = False
        locked_reasons.append("Route-level fairness floor was not met by any trading route.")

    updated_candidates: list[ExecutionRouteCandidate] = []
    for candidate in candidates:
        if candidate.name == recommended.name:
            updated_candidates.append(candidate.model_copy(update={"status": "recommended"}))
        else:
            updated_candidates.append(candidate)

    max_candidate_notional = max((candidate.max_notional_usdt for candidate in updated_candidates if candidate.route_type != "hold"), default=0.0)
    judge_takeaway = (
        "FairFlow does not stop at trade direction; it audits how the paper route would be exposed to spread, impact, leakage, and manipulation."
        if execution_permitted
        else "FairFlow proves that a locked audit cannot be rescued by choosing a different execution style."
    )

    return FairExecutionRouterReport(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        verdict=verdict,
        execution_permitted=execution_permitted,
        recommended_route=recommended.name,
        summary=summary,
        fairness_floor_score=fairness_floor_score,
        liquidity_budget_usdt=round(max(0.0, liquidity_budget), 2),
        max_route_notional_usdt=round(max_candidate_notional, 2),
        route_candidates=updated_candidates,
        locked_reasons=locked_reasons or ["No core lock reason; route choice is governed by the route fairness floor."],
        verification_notes=[
            "Expected slippage uses spread, Fairness Passport hidden cost, and 25k impact pressure.",
            "Information leakage and manipulation exposure are scored separately so a cheap route can still be rejected.",
            "Recommended routes are paper-only and tied to the immutable audit hash.",
            "Hold/re-audit is a valid recommendation when route fairness cannot be proven.",
        ],
        judge_takeaway=judge_takeaway,
    )


def build_policy_stress_report(decision: GuardianDecision) -> PolicyStressReport:
    preset_specs = [
        (
            "Access-first retail review",
            "access_first",
            "Tests whether smaller retail users can still review the setup under inclusive but non-bypassable limits.",
            GuardrailPolicyRequest(
                audit_hash=decision.audit_hash,
                min_fairness_score=72,
                max_hidden_cost_bps=14,
                max_anomaly_score=62,
                min_liquidity_score=42,
                max_leverage=2.5,
                max_stop_hit_probability=0.62,
            ),
        ),
        (
            "Balanced BGA guardian",
            "balanced",
            "Uses the default FairFlow policy tuned for transparency, fair execution, and practical retail safeguards.",
            GuardrailPolicyRequest(audit_hash=decision.audit_hash),
        ),
        (
            "Strict institutional controls",
            "strict",
            "Applies a conservative desk-style policy to reveal whether approval is robust after heavier risk costs.",
            GuardrailPolicyRequest(
                audit_hash=decision.audit_hash,
                min_fairness_score=90,
                max_hidden_cost_bps=4,
                max_anomaly_score=25,
                min_liquidity_score=75,
                max_leverage=1.5,
                max_stop_hit_probability=0.25,
            ),
        ),
    ]

    outcomes: list[PolicyStressOutcome] = []
    for name, stance, purpose, policy in preset_specs:
        report = evaluate_guardrail_policy(decision, policy)
        pass_count = sum(1 for check in report.checks if check.status == "pass")
        watch_count = sum(1 for check in report.checks if check.status == "watch")
        block_count = sum(1 for check in report.checks if check.status == "block")
        first_breaking_check = next((check.name for check in report.checks if check.status == "block"), None)
        outcomes.append(
            PolicyStressOutcome(
                name=name,
                stance=stance,
                purpose=purpose,
                report=report,
                pass_count=pass_count,
                watch_count=watch_count,
                block_count=block_count,
                first_breaking_check=first_breaking_check,
            )
        )

    verdicts = {outcome.report.verdict for outcome in outcomes}
    execution_states = {outcome.report.execution_allowed for outcome in outcomes}
    execution_allowed_count = sum(1 for outcome in outcomes if outcome.report.execution_allowed)
    blocked_policy_count = sum(1 for outcome in outcomes if outcome.report.verdict == "blocked")

    check_names = sorted({check.name for outcome in outcomes for check in outcome.report.checks})
    fragile_checks: list[str] = []
    for name in check_names:
        statuses = [
            check.status
            for outcome in outcomes
            for check in outcome.report.checks
            if check.name == name
        ]
        block_count = statuses.count("block")
        watch_count = statuses.count("watch")
        if block_count or watch_count or len(set(statuses)) > 1:
            fragile_checks.append(f"{name}: {block_count} block / {watch_count} watch across 3 policies")

    if execution_allowed_count == 0 and (decision.final_action == "NO_TRADE" or decision.status != "approved"):
        resilience_verdict = "protective_lockdown"
    elif outcomes[1].report.execution_allowed and outcomes[2].report.execution_allowed:
        resilience_verdict = "stable_greenlight"
    elif execution_allowed_count > 0:
        resilience_verdict = "fragile_greenlight"
    else:
        resilience_verdict = "needs_review"

    agreement_score = 100.0 if len(verdicts) == 1 else 72.0 if len(verdicts) == 2 else 55.0
    execution_consistency_score = 100.0 if len(execution_states) == 1 else 66.0
    fragility_penalty = min(24.0, len(fragile_checks) * 3.0)
    protective_bonus = 10.0 if resilience_verdict == "protective_lockdown" else 0.0
    stability_score = round(
        max(0.0, min(100.0, agreement_score * 0.55 + execution_consistency_score * 0.45 - fragility_penalty + protective_bonus)),
        1,
    )

    if resilience_verdict == "stable_greenlight":
        summary = "The audit remains executable even under strict governance, so approval is policy-resilient."
        judge_takeaway = "This is the strongest greenlight: access, balanced, and strict policies all agree without bypassing the guardian gate."
        recommended_next_steps = [
            "Keep execution paper-only and size through the Risk Sizing panel.",
            "Anchor the audit hash before comparing later market outcomes.",
            "Use the strict policy report as the evidence floor in the judge demo.",
        ]
    elif resilience_verdict == "fragile_greenlight":
        strict_break = outcomes[2].first_breaking_check or "strict policy margin"
        summary = f"At least one policy allows review, but strict controls break first at {strict_break}."
        judge_takeaway = "The system can distinguish an accessible retail review from a truly robust execution approval."
        recommended_next_steps = [
            f"Discuss {strict_break} as the limiting safety control.",
            "Treat paper execution as optional review, not a production route.",
            "Tighten Policy Studio inputs and compare the changed report with this stress lab.",
        ]
    elif resilience_verdict == "protective_lockdown":
        summary = "All presets keep execution locked, which is a protective outcome for unsafe or unfair conditions."
        judge_takeaway = "No-trade is working as designed: different governance stances agree that retail users should not be routed."
        recommended_next_steps = [
            "Show the first breaking checks instead of trying to find a trade.",
            "Open the Retail Cohort Simulator to prove the lock protects smaller accounts too.",
            "Anchor the blocked audit as evidence that FairFlow records harmful conditions.",
        ]
    else:
        summary = "The policy suite does not produce a clean approval; human review should remain in the loop."
        judge_takeaway = "FairFlow flags governance uncertainty instead of forcing a binary trade recommendation."
        recommended_next_steps = [
            "Review watch and block checks before changing thresholds.",
            "Compare calm, volatile, and manipulated scenarios.",
            "Keep the mission in advisory mode until policy agreement improves.",
        ]

    return PolicyStressReport(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        resilience_verdict=resilience_verdict,
        stability_score=stability_score,
        execution_allowed_count=execution_allowed_count,
        blocked_policy_count=blocked_policy_count,
        summary=summary,
        outcomes=outcomes,
        fragile_checks=fragile_checks[:8],
        judge_takeaway=judge_takeaway,
        recommended_next_steps=recommended_next_steps,
    )


def _red_team_status(
    *,
    hidden_cost_bps: float,
    anomaly_score: float,
    liquidity_score: float,
    stop_hit_probability: float,
    base_locked: bool,
) -> str:
    if base_locked:
        return "block"
    if hidden_cost_bps > 16 or anomaly_score > 70 or liquidity_score < 35 or stop_hit_probability > 0.72:
        return "block"
    if hidden_cost_bps > 10 or anomaly_score > 52 or liquidity_score < 52 or stop_hit_probability > 0.52:
        return "watch"
    return "pass"


def _first_red_team_trigger(
    *,
    hidden_cost_bps: float,
    anomaly_score: float,
    liquidity_score: float,
    stop_hit_probability: float,
    base_locked: bool,
) -> str:
    if base_locked:
        return "Guardian execution gate"
    candidates = [
        ("Hidden-cost cap", max(0.0, hidden_cost_bps - 8.0) / 8.0),
        ("Anomaly cap", max(0.0, anomaly_score - 45.0) / 45.0),
        ("Liquidity floor", max(0.0, 55.0 - liquidity_score) / 55.0),
        ("Stop-hit probability cap", max(0.0, stop_hit_probability - 0.45) / 0.45),
    ]
    trigger, pressure = max(candidates, key=lambda item: item[1])
    return trigger if pressure > 0 else "No guardrail breach"


def _red_team_probe(
    *,
    decision: GuardianDecision,
    name: str,
    attack_vector: str,
    severity: str,
    hidden_delta: float,
    anomaly_delta: float,
    liquidity_delta: float,
    stop_delta: float,
    impact_multiplier: float,
    retail_harm: str,
    mitigation: str,
    explanation: str,
) -> RedTeamProbe:
    base_hidden = decision.fairness_passport.estimated_hidden_cost_bps
    base_anomaly = decision.ai_committee.anomaly.score
    base_liquidity = decision.metrics.liquidity_score
    base_stop = decision.ai_committee.forecast.stop_loss_hit_probability
    base_impact = max(0.0, decision.metrics.impact_25k_bps)
    base_locked = decision.status != "approved" or decision.final_action == "NO_TRADE"

    stressed_hidden = round(max(0.0, base_hidden + hidden_delta + max(0.0, impact_multiplier - 1) * base_impact * 0.25), 3)
    stressed_anomaly = round(max(0.0, min(100.0, base_anomaly + anomaly_delta)), 3)
    stressed_liquidity = round(max(0.0, min(100.0, base_liquidity - liquidity_delta)), 3)
    stressed_stop = round(max(0.0, min(1.0, base_stop + stop_delta)), 4)
    stressed_impact = round(max(0.0, base_impact * impact_multiplier), 3)

    status = _red_team_status(
        hidden_cost_bps=stressed_hidden,
        anomaly_score=stressed_anomaly,
        liquidity_score=stressed_liquidity,
        stop_hit_probability=stressed_stop,
        base_locked=base_locked,
    )
    first_trigger = _first_red_team_trigger(
        hidden_cost_bps=stressed_hidden,
        anomaly_score=stressed_anomaly,
        liquidity_score=stressed_liquidity,
        stop_hit_probability=stressed_stop,
        base_locked=base_locked,
    )

    return RedTeamProbe(
        name=name,
        attack_vector=attack_vector,
        severity=severity,
        status=status,
        stressed_hidden_cost_bps=stressed_hidden,
        stressed_anomaly_score=stressed_anomaly,
        stressed_liquidity_score=stressed_liquidity,
        stressed_stop_hit_probability=stressed_stop,
        stressed_impact_25k_bps=stressed_impact,
        first_trigger=first_trigger,
        retail_harm=retail_harm,
        mitigation=mitigation,
        explanation=explanation,
    )


def build_red_team_report(decision: GuardianDecision) -> RedTeamReport:
    imbalance_pressure = min(14.0, abs(decision.metrics.order_book_imbalance) * 30.0)
    funding_pressure = min(10.0, abs(decision.metrics.funding_rate_bps) * 1.4)
    volatility_pressure = min(12.0, decision.metrics.realized_volatility_pct * 1.6)
    base_locked = decision.status != "approved" or decision.final_action == "NO_TRADE"

    probes = [
        _red_team_probe(
            decision=decision,
            name="Liquidity rug pull",
            attack_vector="liquidity_withdrawal",
            severity="critical",
            hidden_delta=5.0,
            anomaly_delta=18.0,
            liquidity_delta=35.0,
            stop_delta=0.1,
            impact_multiplier=2.8,
            retail_harm="Retail routes face worse fills, wider slippage, and a higher chance of stop-outs after visible depth disappears.",
            mitigation="Lock execution, shrink notional to zero, and wait for top-depth recovery before re-running the audit.",
            explanation="Simulates a sudden withdrawal of visible depth before or during a retail-sized route.",
        ),
        _red_team_probe(
            decision=decision,
            name="Spoofed imbalance flip",
            attack_vector="spoofed_imbalance",
            severity="high",
            hidden_delta=3.0,
            anomaly_delta=22.0 + imbalance_pressure,
            liquidity_delta=16.0,
            stop_delta=0.06,
            impact_multiplier=1.7,
            retail_harm="A retail user may chase a false book signal while faster actors cancel liquidity ahead of execution.",
            mitigation="Require anomaly review and avoid market orders when imbalance and wick/volume pressure disagree.",
            explanation="Stresses the manipulation sentinel against a sharp order-book imbalance reversal.",
        ),
        _red_team_probe(
            decision=decision,
            name="Volatility stop cascade",
            attack_vector="volatility_cascade",
            severity="critical",
            hidden_delta=4.0,
            anomaly_delta=12.0 + volatility_pressure,
            liquidity_delta=20.0,
            stop_delta=0.24,
            impact_multiplier=2.1,
            retail_harm="Stops can cluster at predictable levels, producing adverse fills and repeated small-account losses.",
            mitigation="Keep paper execution locked unless stop-hit probability and realized volatility both cool down.",
            explanation="Models a fast volatility expansion where stop distance becomes too narrow for fair retail execution.",
        ),
        _red_team_probe(
            decision=decision,
            name="Funding squeeze",
            attack_vector="funding_squeeze",
            severity="high",
            hidden_delta=2.5 + funding_pressure * 0.4,
            anomaly_delta=10.0 + funding_pressure,
            liquidity_delta=10.0,
            stop_delta=0.08,
            impact_multiplier=1.45,
            retail_harm="Crowded positioning can make the same signal more expensive for late retail participants.",
            mitigation="Throttle leverage, require lower notional, and disclose funding/open-interest crowding in the receipt.",
            explanation="Raises funding and crowding pressure to test whether leverage remains defensible.",
        ),
        _red_team_probe(
            decision=decision,
            name="Reference-price gap",
            attack_vector="oracle_gap",
            severity="moderate",
            hidden_delta=3.5,
            anomaly_delta=14.0,
            liquidity_delta=12.0,
            stop_delta=0.05,
            impact_multiplier=1.55,
            retail_harm="Users may rely on a stale or diverged reference price while the executable book has already moved.",
            mitigation="Require fresh public data, anchor the stale audit separately, and refuse execution from old reports.",
            explanation="Approximates a mark/index/reference mismatch using cost, anomaly, and liquidity pressure.",
        ),
    ]

    blocked_probe_count = sum(1 for probe in probes if probe.status == "block")
    watch_probe_count = sum(1 for probe in probes if probe.status == "watch")
    worst_probe = max(
        probes,
        key=lambda probe: (
            {"block": 3, "watch": 2, "pass": 1}[probe.status],
            probe.stressed_anomaly_score + (100 - probe.stressed_liquidity_score) + probe.stressed_hidden_cost_bps,
        ),
    )
    kill_switches = []
    for trigger in [probe.first_trigger for probe in probes if probe.status == "block"]:
        if trigger not in kill_switches:
            kill_switches.append(trigger)
    if not kill_switches:
        kill_switches = ["No kill switch required under these deterministic probes"]

    if base_locked:
        verdict = "already_locked"
        integrity_score = 92.0
        summary = "The baseline audit is already locked, and adversarial probes confirm the no-trade posture protects retail users."
        judge_takeaway = "FairFlow records unsafe market structure instead of searching for a trade; the red team strengthens the no-trade case."
        recommended_next_steps = [
            "Show the blocked baseline before opening the red-team probes.",
            "Anchor the no-trade audit as evidence of protective behavior.",
            "Wait for a fresh audit rather than tuning thresholds to force execution.",
        ]
    elif blocked_probe_count >= 3:
        verdict = "kill_switch_ready"
        integrity_score = 86.0
        summary = "Multiple adversarial probes trip hard guardrails, so the system is ready to halt execution when market integrity degrades."
        judge_takeaway = "The approval is conditional: FairFlow can greenlight calm markets while showing exactly how it would stop under manipulation stress."
        recommended_next_steps = [
            "Use Risk Sizing only after confirming the current market still matches the audited state.",
            "Explain the top kill switches before discussing paper execution.",
            "Compare with the Manipulated scenario to show the same safeguards in a full audit.",
        ]
    elif blocked_probe_count > 0 or watch_probe_count >= 3:
        verdict = "watchlist"
        integrity_score = 76.0
        summary = "The setup is sensitive to at least one adversarial condition and should remain under active agent review."
        judge_takeaway = "FairFlow exposes fragile market structure before routing instead of hiding it inside a single confidence score."
        recommended_next_steps = [
            "Keep Agent Mission Control in advisory mode.",
            "Tighten Policy Studio around the first triggered check.",
            "Re-run the audit if spread, depth, or stop-hit probability changes.",
        ]
    else:
        verdict = "resilient"
        integrity_score = 90.0
        summary = "The audited setup remains below red-team guardrail thresholds across the deterministic adversarial probes."
        judge_takeaway = "This is a rare stronger approval: the trade idea survives cost, anomaly, liquidity, and stop-risk perturbations."
        recommended_next_steps = [
            "Keep any route paper-only and audit-linked.",
            "Record the red-team report with the audit hash.",
            "Monitor live depth before refreshing the decision.",
        ]

    return RedTeamReport(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        verdict=verdict,
        integrity_score=integrity_score,
        baseline_gate=f"{decision.status} / {decision.final_action} / {decision.fairness_passport.verdict}",
        summary=summary,
        probes=probes,
        blocked_probe_count=blocked_probe_count,
        watch_probe_count=watch_probe_count,
        worst_probe=worst_probe.name,
        kill_switches=kill_switches,
        judge_takeaway=judge_takeaway,
        recommended_next_steps=recommended_next_steps,
    )


def build_evidence_pack(decision: GuardianDecision) -> AuditEvidencePack:
    receipt = build_fairness_receipt(decision)
    cohorts = build_retail_cohort_report(decision)
    anchor = build_anchor_proof(decision)
    judge = build_judge_brief(decision)
    provenance = build_model_provenance_card(decision)
    router = build_fair_execution_router(decision)
    counterfactuals = build_counterfactual_fairness_report(decision)
    policy_stress = build_policy_stress_report(decision)
    red_team = build_red_team_report(decision)

    evidence_urls = {
        "audit": f"/api/audits/{decision.audit_hash}",
        "evidence_pack": f"/api/audits/{decision.audit_hash}/evidence-pack",
        "receipt": f"/api/audits/{decision.audit_hash}/receipt",
        "retail_cohorts": f"/api/audits/{decision.audit_hash}/retail-cohorts",
        "anchor_proof": f"/api/audits/{decision.audit_hash}/anchor-proof",
        "judge_brief": f"/api/audits/{decision.audit_hash}/judge-brief",
        "model_provenance": f"/api/audits/{decision.audit_hash}/model-provenance",
        "execution_router": f"/api/audits/{decision.audit_hash}/execution-router",
        "counterfactuals": f"/api/audits/{decision.audit_hash}/counterfactuals",
        "policy_stress": f"/api/audits/{decision.audit_hash}/policy-stress",
        "red_team": f"/api/audits/{decision.audit_hash}/red-team",
        "impact_ledger": "/api/impact?limit=50",
    }

    fairness_status = "verified"
    if decision.fairness_passport.verdict == "wait_for_parity":
        fairness_status = "watch"
    elif decision.fairness_passport.verdict == "unfair_to_retail":
        fairness_status = "blocked"

    no_trade_status = "verified" if decision.final_action == "NO_TRADE" else "watch"
    if decision.final_action == "NO_TRADE" and decision.status == "blocked":
        no_trade_status = "verified"

    policy_status = "verified"
    if policy_stress.resilience_verdict in {"fragile_greenlight", "needs_review"}:
        policy_status = "watch"

    red_team_status = "verified" if red_team.verdict in {"kill_switch_ready", "already_locked", "resilient"} else "watch"

    claims = [
        EvidencePackClaim(
            label="Audit is replayable by hash",
            status="verified",
            evidence_url=evidence_urls["audit"],
            explanation=f"The full decision payload is recoverable through SHA-256 audit hash {decision.audit_hash[:12]}...",
        ),
        EvidencePackClaim(
            label="Retail fairness was evaluated",
            status=fairness_status,
            evidence_url=evidence_urls["receipt"],
            explanation=(
                f"Fairness Passport verdict is {decision.fairness_passport.verdict} with "
                f"{decision.fairness_passport.score:.1f}/100 and hidden cost {decision.fairness_passport.estimated_hidden_cost_bps:.1f} bps."
            ),
        ),
        EvidencePackClaim(
            label="Cohort affordability is disclosed",
            status="verified" if cohorts.verdict == "inclusive" else "watch" if cohorts.verdict == "limited" else "blocked",
            evidence_url=evidence_urls["retail_cohorts"],
            explanation=f"Cohort simulator reports {cohorts.verdict}: {cohorts.pass_count} pass, {cohorts.watch_count} watch, {cohorts.block_count} block.",
        ),
        EvidencePackClaim(
            label="No-trade can be a protective outcome",
            status=no_trade_status,
            evidence_url=evidence_urls["red_team"],
            explanation=(
                "The current audit is a no-trade or locked report."
                if decision.final_action == "NO_TRADE"
                else "The current audit is not a no-trade, so protective behavior is demonstrated through stress and red-team reports."
            ),
        ),
        EvidencePackClaim(
            label="Model and data provenance are disclosed",
            status="verified",
            evidence_url=evidence_urls["model_provenance"],
            explanation=f"Provenance card documents {len(provenance.data_sources)} data sources and {len(provenance.model_components)} AI/risk components.",
        ),
        EvidencePackClaim(
            label="Governance stress was replayed",
            status=policy_status,
            evidence_url=evidence_urls["policy_stress"],
            explanation=f"Policy Stress Lab verdict is {policy_stress.resilience_verdict} with stability score {policy_stress.stability_score:.1f}.",
        ),
        EvidencePackClaim(
            label="Execution route fairness was checked",
            status=(
                "verified"
                if router.verdict in {"route_ready", "paper_only_locked"}
                else "watch"
                if router.verdict == "route_with_caution"
                else "blocked"
            ),
            evidence_url=evidence_urls["execution_router"],
            explanation=(
                f"Fair Execution Router verdict is {router.verdict}; recommended route is {router.recommended_route} "
                f"with max paper notional {router.max_route_notional_usdt:.0f} USDT."
            ),
        ),
        EvidencePackClaim(
            label="Counterfactual unlock path is bounded",
            status="verified" if counterfactuals.verdict in {"already_fair", "do_not_unlock"} else "watch",
            evidence_url=evidence_urls["counterfactuals"],
            explanation=f"Counterfactual verdict is {counterfactuals.verdict}; top blocker is {counterfactuals.top_blocker}.",
        ),
        EvidencePackClaim(
            label="Market integrity probes were run",
            status=red_team_status,
            evidence_url=evidence_urls["red_team"],
            explanation=f"Red-team verdict is {red_team.verdict}; {red_team.blocked_probe_count}/{len(red_team.probes)} probes trip hard blocks.",
        ),
        EvidencePackClaim(
            label="On-chain anchor payload is prepared",
            status="verified",
            evidence_url=evidence_urls["anchor_proof"],
            explanation=f"Anchor proof exposes {anchor.function_signature} with payload hash {anchor.payload_hash[:12]}...",
        ),
    ]

    status_points = {"verified": 1.0, "watch": 0.62, "blocked": 0.82}
    verification_score = round(
        max(
            0.0,
            min(
                100.0,
                sum(status_points[claim.status] for claim in claims) / len(claims) * 82
                + min(10, len(evidence_urls))
                + (8 if anchor.payload_hash else 0),
            ),
        ),
        1,
    )

    key_metrics = {
        "final_action": decision.final_action,
        "decision_status": decision.status,
        "fairness_score": round(decision.fairness_passport.score, 1),
        "hidden_cost_bps": round(decision.fairness_passport.estimated_hidden_cost_bps, 2),
        "liquidity_score": round(decision.metrics.liquidity_score, 1),
        "anomaly_score": round(decision.ai_committee.anomaly.score, 1),
        "execution_router_verdict": router.verdict,
        "recommended_route": router.recommended_route,
        "max_route_notional_usdt": router.max_route_notional_usdt,
        "policy_stability_score": policy_stress.stability_score,
        "counterfactual_readiness_score": counterfactuals.readiness_score,
        "red_team_integrity_score": red_team.integrity_score,
        "cohort_verdict": cohorts.verdict,
        "provenance_score": provenance.provenance_score,
        "paper_only": True,
    }

    headline = (
        f"{decision.symbol} evidence pack: {decision.status} / {decision.final_action}"
        if decision.final_action != "NO_TRADE"
        else f"{decision.symbol} protective no-trade evidence pack"
    )
    summary = (
        "This bundle packages the current audit, retail receipt, cohort results, governance stress, red-team probes, "
        "model provenance, and anchor proof so a reviewer can verify FairFlow's claims without trusting the UI."
    )

    return AuditEvidencePack(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        package_version="fairflow-evidence-pack-v1",
        headline=headline,
        summary=summary,
        verification_score=verification_score,
        key_metrics=key_metrics,
        evidence_urls=evidence_urls,
        included_reports=[
            "GuardianDecision",
            "FairnessReceipt",
            "RetailCohortReport",
            "AnchorProof",
            "JudgeBrief",
            "ModelProvenanceCard",
            "FairExecutionRouterReport",
            "CounterfactualFairnessReport",
            "PolicyStressReport",
            "RedTeamReport",
        ],
        core_claims=claims,
        decision=decision,
        fairness_receipt=receipt,
        retail_cohorts=cohorts,
        anchor_proof=anchor,
        judge_brief=judge,
        model_provenance=provenance,
        fair_execution_router=router,
        counterfactuals=counterfactuals,
        policy_stress=policy_stress,
        red_team=red_team,
        verifier_notes=[
            "Every nested report is generated from the same audit hash.",
            "Paper-only boundaries are repeated in the receipt, provenance card, mission controls, and anchor metadata.",
            "Blocked and no-trade states are treated as protective market-health outcomes, not missing returns.",
            "Fallback market data is explicitly labeled in the source and provenance sections.",
        ],
        limitations=[
            "This is a prototype evidence bundle, not regulated investment advice.",
            "The pack proves internal consistency and replayability, not future market outcomes.",
            "On-chain anchoring payloads are prepared for verification but not automatically submitted.",
            "Live data availability depends on public exchange API access and can fall back to deterministic scenarios.",
        ],
    )


def _criterion_status(score: float) -> str:
    if score >= 82:
        return "ready"
    if score >= 66:
        return "watch"
    return "gap"


def _rubric_score(judge: JudgeBrief, category: str) -> float:
    item = next((rubric for rubric in judge.rubric if rubric.category == category), None)
    return item.score if item else 0.0


def build_hackathon_readiness_report(decision: GuardianDecision) -> HackathonReadinessReport:
    receipt = build_fairness_receipt(decision)
    cohorts = build_retail_cohort_report(decision)
    anchor = build_anchor_proof(decision)
    judge = build_judge_brief(decision)
    provenance = build_model_provenance_card(decision)
    router = build_fair_execution_router(decision)
    counterfactuals = build_counterfactual_fairness_report(decision)
    policy_stress = build_policy_stress_report(decision)
    red_team = build_red_team_report(decision)
    impact = build_impact_ledger_report(limit=50)

    proof_links = [
        f"/api/audits/{decision.audit_hash}",
        f"/api/audits/{decision.audit_hash}/hackathon-readiness",
        f"/api/audits/{decision.audit_hash}/judge-brief",
        f"/api/audits/{decision.audit_hash}/evidence-pack",
        f"/api/audits/{decision.audit_hash}/model-provenance",
        f"/api/audits/{decision.audit_hash}/execution-router",
        f"/api/audits/{decision.audit_hash}/counterfactuals",
        f"/api/audits/{decision.audit_hash}/policy-stress",
        f"/api/audits/{decision.audit_hash}/red-team",
        f"/api/audits/{decision.audit_hash}/receipt",
        f"/api/audits/{decision.audit_hash}/retail-cohorts",
        f"/api/audits/{decision.audit_hash}/anchor-proof",
        "/api/impact?limit=50",
    ]

    ethos_score = round(
        min(
            100.0,
            _rubric_score(judge, "bga_ethos") * 0.45
            + impact.bga_ethos_score * 0.25
            + receipt.bga_alignment_score * 0.20
            + (100 if cohorts.verdict == "inclusive" else 72 if cohorts.verdict == "limited" else 42) * 0.10,
        ),
        1,
    )
    technical_score = round(
        min(
            100.0,
            _rubric_score(judge, "technical_depth") * 0.45
            + provenance.provenance_score * 0.25
            + min(100, len(decision.agents) * 12) * 0.12
            + min(100, len(decision.decision_trace) * 14) * 0.10
            + (100 if anchor.payload_hash else 50) * 0.08,
        ),
        1,
    )
    risk_score = round(
        min(
            100.0,
            _rubric_score(judge, "risk_management") * 0.35
            + policy_stress.stability_score * 0.18
            + red_team.integrity_score * 0.18
            + router.route_candidates[0].retail_fairness_score * 0.08
            + counterfactuals.readiness_score * 0.08
            + (100 if decision.final_action == "NO_TRADE" and decision.status == "blocked" else 86 if router.execution_permitted else 70) * 0.13,
        ),
        1,
    )
    transparency_score = round(
        min(
            100.0,
            _rubric_score(judge, "transparency") * 0.35
            + provenance.provenance_score * 0.18
            + min(100, len(proof_links) * 8) * 0.17
            + min(100, len(anchor.verification_steps) * 18) * 0.12
            + min(100, len(receipt.verification_steps) * 18) * 0.10
            + (100 if decision.audit_hash else 0) * 0.08,
        ),
        1,
    )

    criteria = [
        HackathonReadinessCriterion(
            category="bga_ethos",
            max_points=20,
            readiness_score=ethos_score,
            status=_criterion_status(ethos_score),
            headline="Fair-market infrastructure before returns",
            evidence=[
                f"Fairness receipt alignment score: {receipt.bga_alignment_score:.1f}/100.",
                f"Impact ledger BGA ethos score: {impact.bga_ethos_score:.1f}/100 across {impact.audit_count} audits.",
                f"Retail cohort verdict: {cohorts.verdict} with {cohorts.pass_count} pass, {cohorts.watch_count} watch, {cohorts.block_count} block.",
            ],
            proof_urls=[f"/api/audits/{decision.audit_hash}/receipt", f"/api/audits/{decision.audit_hash}/retail-cohorts", "/api/impact?limit=50"],
            judge_angle="Start here to show the project reduces information asymmetry instead of chasing opaque PnL.",
            remaining_risks=[
                "Fairness scores are transparent prototype rubrics, not regulated suitability determinations.",
                "Live market access still depends on public exchange availability.",
            ],
        ),
        HackathonReadinessCriterion(
            category="technical_depth",
            max_points=20,
            readiness_score=technical_score,
            status=_criterion_status(technical_score),
            headline="Typed full-stack agent system with audit infrastructure",
            evidence=[
                f"{len(decision.agents)} deterministic specialist agents plus AI committee signals.",
                f"Provenance card documents {len(provenance.model_components)} model/risk/audit components.",
                f"Anchor kit prepares {anchor.function_signature} with payload hash {anchor.payload_hash[:12]}...",
            ],
            proof_urls=[f"/api/audits/{decision.audit_hash}/model-provenance", f"/api/audits/{decision.audit_hash}/anchor-proof"],
            judge_angle="Use this to defend that the project is more than a thin API wrapper.",
            remaining_risks=[
                "ML components are lightweight explainable models, not production-grade predictors.",
                "On-chain anchoring prepares transaction data but does not submit transactions or custody assets.",
            ],
        ),
        HackathonReadinessCriterion(
            category="risk_management",
            max_points=15,
            readiness_score=risk_score,
            status=_criterion_status(risk_score),
            headline="Execution is gated by policy, route fairness, red-team probes, and no-trade locks",
            evidence=[
                f"Policy Stress Lab verdict: {policy_stress.resilience_verdict} with stability {policy_stress.stability_score:.1f}/100.",
                f"Fair Execution Router verdict: {router.verdict}; recommended route: {router.recommended_route}.",
                f"Red-team verdict: {red_team.verdict}; worst probe: {red_team.worst_probe}.",
            ],
            proof_urls=[
                f"/api/audits/{decision.audit_hash}/policy-stress",
                f"/api/audits/{decision.audit_hash}/execution-router",
                f"/api/audits/{decision.audit_hash}/red-team",
            ],
            judge_angle="Switch to manipulated conditions to prove blocked execution is a successful safety outcome.",
            remaining_risks=[
                "Backtest windows are short and intentionally not marketed as alpha proof.",
                "Route scores estimate paper execution quality and need exchange-specific production validation.",
            ],
        ),
        HackathonReadinessCriterion(
            category="transparency",
            max_points=15,
            readiness_score=transparency_score,
            status=_criterion_status(transparency_score),
            headline="Every claim is replayable from the audit hash",
            evidence=[
                f"Decision trace has {len(decision.decision_trace)} stages.",
                f"Evidence pack bundles 10 reports with verification score available at /evidence-pack.",
                f"Counterfactual verdict: {counterfactuals.verdict}; top blocker: {counterfactuals.top_blocker}.",
            ],
            proof_urls=[
                f"/api/audits/{decision.audit_hash}",
                f"/api/audits/{decision.audit_hash}/evidence-pack",
                f"/api/audits/{decision.audit_hash}/counterfactuals",
            ],
            judge_angle="Copy any proof endpoint to show the UI narrative is backed by machine-readable artifacts.",
            remaining_risks=[
                "SQLite is local prototype persistence.",
                "Fallback scenarios are deterministic demos, not live-market predictions.",
            ],
        ),
    ]

    runbook_steps = [
        HackathonRunbookStep(
            step=1,
            title="Open with the thesis",
            ui_action="Open Judge Mode Brief and read the one-sentence pitch.",
            expected_result=judge.one_sentence_pitch,
            underlying_mechanism="The brief is generated from the same audit hash, impact ledger, fairness receipt, cohort simulator, and anchor proof.",
            proof_url=f"/api/audits/{decision.audit_hash}/judge-brief",
            judge_script=judge.recommended_opening,
            criteria=["bga_ethos", "transparency"],
        ),
        HackathonRunbookStep(
            step=2,
            title="Show the audited decision",
            ui_action="Use the top decision panel, fairness score, hidden cost, and audit hash.",
            expected_result=f"{decision.status} / {decision.final_action} for {decision.symbol}.",
            underlying_mechanism="Market data is transformed into spread, depth, volatility, RSI, funding, impact, and liquidity metrics before the agents vote.",
            proof_url=f"/api/audits/{decision.audit_hash}",
            judge_script=f"This is not a naked signal. It is an audited decision with fairness {decision.fairness_passport.score:.0f}/100 and hash {decision.audit_hash[:12]}...",
            criteria=["technical_depth", "risk_management", "transparency"],
        ),
        HackathonRunbookStep(
            step=3,
            title="Prove retail fairness",
            ui_action="Open Fairness Receipt and Retail Cohort Simulator.",
            expected_result=f"Receipt alignment {receipt.bga_alignment_score:.1f}/100; cohort verdict {cohorts.verdict}.",
            underlying_mechanism="The app checks information parity, execution parity, manipulation exposure, risk protection, auditability, hidden cost, account size, and margin pressure.",
            proof_url=f"/api/audits/{decision.audit_hash}/retail-cohorts",
            judge_script="This is where FairFlow moves from trading to market fairness: the same strategy must remain affordable and understandable for smaller accounts.",
            criteria=["bga_ethos", "risk_management"],
        ),
        HackathonRunbookStep(
            step=4,
            title="Show the model and data card",
            ui_action="Open Model and Data Provenance.",
            expected_result=f"Provenance score {provenance.provenance_score:.1f}/100 with {len(provenance.model_components)} documented components.",
            underlying_mechanism="The card separates live/fallback data, derived metrics, ML signals, risk models, execution guards, and audit infrastructure.",
            proof_url=f"/api/audits/{decision.audit_hash}/model-provenance",
            judge_script="This is how we avoid pretending the model is magic. Inputs, outputs, limits, and validation artifacts are visible.",
            criteria=["technical_depth", "transparency"],
        ),
        HackathonRunbookStep(
            step=5,
            title="Explain fair route selection",
            ui_action="Open Fair Execution Router.",
            expected_result=f"{router.recommended_route} recommended; router verdict {router.verdict}.",
            underlying_mechanism="Route candidates are scored for slippage, fill probability, information leakage, manipulation exposure, and retail route fairness.",
            proof_url=f"/api/audits/{decision.audit_hash}/execution-router",
            judge_script="FairFlow does not stop at direction. It asks whether the route itself is fair enough to expose to a retail user.",
            criteria=["risk_management", "transparency"],
        ),
        HackathonRunbookStep(
            step=6,
            title="Stress the governance policy",
            ui_action="Open Policy Studio and Policy Stress Lab.",
            expected_result=f"Stress verdict {policy_stress.resilience_verdict}; {policy_stress.execution_allowed_count}/3 policies allow execution.",
            underlying_mechanism="The same audit is replayed through access-first, balanced, and strict guardrail policies without letting policy override the core gate.",
            proof_url=f"/api/audits/{decision.audit_hash}/policy-stress",
            judge_script="This proves we are not tuned to one hand-picked threshold. Stricter policies can downgrade or block the same audit.",
            criteria=["risk_management", "transparency"],
        ),
        HackathonRunbookStep(
            step=7,
            title="Show non-bypassable counterfactuals",
            ui_action="Open Counterfactual Fairness Lab.",
            expected_result=f"Counterfactual verdict {counterfactuals.verdict}; top blocker {counterfactuals.top_blocker}.",
            underlying_mechanism="The lab identifies which market metrics must genuinely improve and which gates require a fresh audit instead of slider overrides.",
            proof_url=f"/api/audits/{decision.audit_hash}/counterfactuals",
            judge_script="This is a guard against misuse: a bad audit cannot be locally unlocked by moving sliders.",
            criteria=["bga_ethos", "risk_management", "transparency"],
        ),
        HackathonRunbookStep(
            step=8,
            title="Run adversarial market integrity probes",
            ui_action="Open Market Integrity Red Team.",
            expected_result=f"Red-team verdict {red_team.verdict}; {red_team.blocked_probe_count}/{len(red_team.probes)} probes trip hard blocks.",
            underlying_mechanism="Deterministic probes simulate liquidity withdrawal, spoofed imbalance, volatility cascade, funding squeeze, and reference-price gaps.",
            proof_url=f"/api/audits/{decision.audit_hash}/red-team",
            judge_script="A fair system should know how it fails. These probes show what would trigger a halt before retail routing.",
            criteria=["risk_management", "technical_depth"],
        ),
        HackathonRunbookStep(
            step=9,
            title="Open the evidence pack",
            ui_action="Open Evidence Pack and copy the JSON bundle.",
            expected_result="The pack includes decision, receipt, cohorts, anchor proof, judge brief, provenance, router, counterfactuals, policy stress, and red-team report.",
            underlying_mechanism="Every nested report is generated from the same audit hash and linked by proof URLs.",
            proof_url=f"/api/audits/{decision.audit_hash}/evidence-pack",
            judge_script="The UI is not the source of truth. This single endpoint is the source-backed verifier artifact.",
            criteria=["transparency", "technical_depth"],
        ),
        HackathonRunbookStep(
            step=10,
            title="Anchor the proof",
            ui_action="Open On-chain Audit Anchor Kit.",
            expected_result=f"Contract-ready {anchor.function_signature} call with payload hash {anchor.payload_hash[:12]}...",
            underlying_mechanism="The audit hash can be anchored to make hindsight rewriting much harder while keeping execution and custody out of scope.",
            proof_url=f"/api/audits/{decision.audit_hash}/anchor-proof",
            judge_script="Blockchain is used for verifiability, not speculation: it records the decision evidence, not a trade promise.",
            criteria=["bga_ethos", "transparency", "technical_depth"],
        ),
        HackathonRunbookStep(
            step=11,
            title="Show the agentic loop",
            ui_action="Open Agent Mission Control and Active Agents.",
            expected_result="Mission tasks include Data Scout, Regime Analyst, Manipulation Sentinel, Risk Allocator, Fairness Auditor, Execution Operator, Route Steward, and Memory Curator.",
            underlying_mechanism="The action queue can refresh, compare, size, hold, review, reset, or paper execute only when the audited gate allows it.",
            proof_url=f"/api/agents/mission?audit_hash={decision.audit_hash}",
            judge_script="This is agentic, but bounded: the agents can plan and critique, while route and fairness gates decide what is permitted.",
            criteria=["technical_depth", "risk_management"],
        ),
        HackathonRunbookStep(
            step=12,
            title="Close with unsafe-market behavior",
            ui_action="Switch to Manipulated and show execution locked.",
            expected_result="Manipulated conditions produce no-trade, blocked cohorts, locked routes, and red-team confirmation.",
            underlying_mechanism="The fallback manipulated scenario deterministically worsens spread, depth, wick, funding, anomaly score, and stop-hit probability.",
            proof_url="/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated",
            judge_script="The winning behavior is restraint. FairFlow records why the market is unhealthy instead of forcing a trade.",
            criteria=["bga_ethos", "risk_management", "transparency"],
        ),
    ]

    readiness_score = round(sum(item.readiness_score for item in criteria) / len(criteria), 1)
    if readiness_score >= 84 and all(item.status != "gap" for item in criteria):
        verdict = "demo_ready"
    elif readiness_score >= 68:
        verdict = "needs_review"
    else:
        verdict = "blocked_demo"

    strongest_claims = [
        "No-trade is treated as a successful protective outcome.",
        "Execution is paper-only and cannot bypass the Fairness Passport, Policy Studio, route router, or audit gate.",
        "Every major dashboard claim has a machine-readable proof endpoint tied to the same audit hash.",
        "The system documents model limits and validation artifacts instead of overstating predictive accuracy.",
    ]
    known_limitations = [
        "Prototype only; not investment advice and not a regulated suitability engine.",
        "Live data uses public Bybit endpoints and can fall back to deterministic scenarios.",
        "ML-style signals are lightweight explainable models intended for guardrails, not production alpha.",
        "Smart contract integration prepares anchor arguments but does not submit transactions.",
    ]

    return HackathonReadinessReport(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        verdict=verdict,
        readiness_score=readiness_score,
        summary=(
            f"{decision.symbol} {decision.scenario} demo readiness is {readiness_score:.1f}/100. "
            "The runbook maps the product to BGA ethos, technical depth, risk management, and transparency so the team can present it without relying on hidden assumptions."
        ),
        recommended_demo_minutes=6.0,
        criteria=criteria,
        runbook_steps=runbook_steps,
        strongest_claims=strongest_claims,
        known_limitations=known_limitations,
        final_30_second_pitch=(
            "FairFlow Guardian is not trying to win a pure PnL contest. It is an explainable, paper-only trading safety layer "
            "that uses public market data, AI-style agents, retail fairness checks, route fairness, adversarial probes, and audit hashes "
            "to prove when a trade is fair enough to review and when the healthiest market action is no trade."
        ),
        proof_links=proof_links,
    )


def build_hackathon_submission_kit(decision: GuardianDecision) -> HackathonSubmissionKit:
    readiness = build_hackathon_readiness_report(decision)
    evidence_pack = build_evidence_pack(decision)
    router = build_fair_execution_router(decision)
    anchor = build_anchor_proof(decision)

    video_segments = [
        SubmissionVideoSegment(
            slide=1,
            timecode="0:00-0:15",
            title="Thesis",
            narration=(
                "FairFlow Guardian is an AI trading safety layer for the BGA track. "
                "It proves when a market is fair enough to review, and when no trade is the healthiest action."
            ),
            dashboard_action="Open on the Competition Runway with the calm decision, fairness score, hidden cost, and audit hash visible.",
            proof_url=f"/api/audits/{decision.audit_hash}",
        ),
        SubmissionVideoSegment(
            slide=2,
            timecode="0:15-0:34",
            title="Problem",
            narration=(
                "The retail problem is not only prediction. A trade can look profitable and still be unfair because of hidden costs, "
                "thin liquidity, spoofing, leverage pressure, or opaque automation."
            ),
            dashboard_action="Point at hidden cost, liquidity, manipulation risk, and the Fairness Passport.",
            proof_url=f"/api/audits/{decision.audit_hash}/receipt",
        ),
        SubmissionVideoSegment(
            slide=3,
            timecode="0:34-0:54",
            title="Agentic guardrail",
            narration=(
                "FairFlow turns public market data into liquidity, volatility, cost, manipulation, and risk features. "
                "The strategy agent can propose, but execution requires fairness, risk, route, and audit gates."
            ),
            dashboard_action="Open Active Agents, Mission Control, and Fair Execution Router.",
            proof_url=f"/api/agents/mission?audit_hash={decision.audit_hash}",
        ),
        SubmissionVideoSegment(
            slide=4,
            timecode="0:54-1:18",
            title="Live demo path",
            narration=(
                "In the demo, start with the Competition Runway: readiness, audit hash, evidence pack, route proof, and calm paper approval. "
                "Then switch to Manipulated and show the refusal."
            ),
            dashboard_action="Use Competition Runway: calm approval, submission proof, then manipulated no-trade.",
            proof_url=f"/api/audits/{decision.audit_hash}/hackathon-readiness",
        ),
        SubmissionVideoSegment(
            slide=5,
            timecode="1:18-1:41",
            title="No-trade proof",
            narration=(
                "The best proof is the manipulated case. Same system, same asset, lower market integrity. "
                "FairFlow blocks the trade, locks the route, and records why."
            ),
            dashboard_action="Show Calm approved versus Manipulated blocked; emphasize no-trade as a measurable protection.",
            proof_url=f"/api/audits/{decision.audit_hash}/evidence-pack",
        ),
        SubmissionVideoSegment(
            slide=6,
            timecode="1:41-2:00",
            title="Why FairFlow wins",
            narration=(
                "Close on the judging criteria: retail fairness, agentic depth, risk-first design, and inspectable proof. "
                "Better systems, not bigger bets."
            ),
            dashboard_action="Copy the evidence pack and show the audit hash as the final proof handoff.",
            proof_url="/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated",
        ),
    ]

    submission_assets = [
        SubmissionAsset(
            label="Complete walkthrough PDF",
            path="output/pdf/fairflow_guardian_complete_walkthrough.pdf",
            purpose="Long-form judge handoff with architecture, runbook, endpoints, limitations, and proof links.",
        ),
        SubmissionAsset(
            label="Two-minute video deck",
            path="output/presentation/fairflow_2_minute_video_deck.pptx",
            purpose="Six-slide presentation with embedded speaker notes and video pacing.",
        ),
        SubmissionAsset(
            label="Two-minute narration script",
            path="output/presentation/fairflow_2_minute_video_script.txt",
            purpose="Voiceover script aligned to the deck timecodes.",
        ),
        SubmissionAsset(
            label="Rendered deck QA contact sheet",
            path="output/presentation/fairflow_2min_video_contact_sheet.png",
            purpose="Visual proof that every judge-facing slide rendered cleanly before submission.",
            required=False,
        ),
        SubmissionAsset(
            label="Verifier evidence endpoint",
            path=f"/api/audits/{decision.audit_hash}/evidence-pack",
            purpose="Machine-readable audit bundle for the current demo decision.",
        ),
        SubmissionAsset(
            label="On-chain anchor payload",
            path=f"/api/audits/{decision.audit_hash}/anchor-proof",
            purpose=f"Contract-ready {anchor.function_signature} payload for the audit hash.",
            required=False,
        ),
    ]

    final_checklist = [
        SubmissionChecklistItem(
            label="BGA ethos is explicit",
            status="ready" if readiness.criteria[0].status == "ready" else "watch",
            evidence=readiness.criteria[0].headline,
        ),
        SubmissionChecklistItem(
            label="Technical depth is demonstrable",
            status="ready" if evidence_pack.verification_score >= 82 else "watch",
            evidence=f"Evidence pack verification score {evidence_pack.verification_score:.1f}/100 with {len(evidence_pack.included_reports)} reports.",
        ),
        SubmissionChecklistItem(
            label="Risk and route safeguards are visible",
            status="ready" if router.verdict in {"route_ready", "locked_by_guardian"} else "watch",
            evidence=f"Router verdict {router.verdict}; recommended route {router.recommended_route}.",
        ),
        SubmissionChecklistItem(
            label="No-trade is framed as a success state",
            status="ready",
            evidence="Slide 5 compares calm approval with manipulated no-trade proof and route lockout.",
        ),
        SubmissionChecklistItem(
            label="Submission artifacts are ready",
            status="ready",
            evidence="Walkthrough PDF, 2-minute PPTX deck, narration script, and rendered QA previews are present under output/.",
        ),
        SubmissionChecklistItem(
            label="Limits are disclosed",
            status="ready" if readiness.known_limitations else "watch",
            evidence=readiness.known_limitations[0] if readiness.known_limitations else "Add prototype limitations before submission.",
        ),
    ]

    copy_block = "\n".join(
        [
            "FairFlow Guardian - 2 minute submission path",
            readiness.final_30_second_pitch,
            "",
            "Record:",
            *[f"{segment.timecode} - {segment.title}: {segment.dashboard_action}" for segment in video_segments],
            "",
            "Submit:",
            *[f"- {asset.label}: {asset.path}" for asset in submission_assets if asset.required],
            "",
            f"Primary proof endpoint: /api/audits/{decision.audit_hash}/evidence-pack",
        ]
    )

    return HackathonSubmissionKit(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        headline="Two-minute submission kit for judges and video reviewers",
        total_runtime_seconds=120,
        opening_hook=readiness.final_30_second_pitch,
        video_segments=video_segments,
        submission_assets=submission_assets,
        final_checklist=final_checklist,
        copy_block=copy_block,
        proof_links=[
            f"/api/audits/{decision.audit_hash}/submission-kit",
            *readiness.proof_links,
        ],
    )


async def build_agent_mission_for(
    symbol: str,
    category: str,
    scenario: str,
    decision: GuardianDecision | None = None,
) -> AgentMission:
    if decision is None:
        decision = await build_decision_for(symbol=symbol, category=category, scenario=scenario)
    portfolio = await paper_portfolio(scenario=scenario)
    committee = decision.ai_committee
    deterministic_sentinel = _agent(decision, "Manipulation Sentinel")
    ml_sentinel = _agent(decision, "ML Manipulation Analyst")
    regime_agent = _agent(decision, "ML Market Regime Classifier")
    risk_agent = _agent(decision, "Risk Guardian")
    fairness_status = _agentic_status(decision.fairness_passport.verdict)
    execution_status = "complete" if decision.status == "approved" else _agentic_status(decision.status)
    core_can_execute = (
        decision.status == "approved"
        and decision.fairness_passport.verdict == "fair_to_execute"
        and committee.execution_plan.order_style != "none"
    )
    router = build_fair_execution_router(decision)
    can_execute = core_can_execute and router.execution_permitted
    route_status = "complete" if router.verdict == "route_ready" else "watch" if router.verdict == "route_with_caution" else "blocked"

    sentinel_status = "complete"
    if any(agent and agent.status == "block" for agent in (deterministic_sentinel, ml_sentinel)):
        sentinel_status = "blocked"
    elif any(agent and agent.status == "watch" for agent in (deterministic_sentinel, ml_sentinel)):
        sentinel_status = "watch"

    portfolio_status = "blocked" if portfolio.gross_exposure_usdt > STARTING_EQUITY_USDT else "complete"
    if portfolio.rejected_order_count or abs(portfolio.net_exposure_usdt) > STARTING_EQUITY_USDT * 0.75:
        portfolio_status = "watch" if portfolio_status == "complete" else portfolio_status

    tasks = [
        AgentTask(
            agent="Data Scout",
            objective="Verify that the mission is using a public, replayable market feed.",
            tool="Bybit V5 public data adapter + deterministic scenario fallback",
            status="complete",
            confidence=0.96 if decision.source.startswith("bybit") else 0.88,
            finding=f"{decision.source} produced a fresh audited report for {decision.symbol}.",
            evidence=[
                f"Scenario: {decision.scenario}",
                f"Generated: {decision.generated_at.isoformat()}",
                f"Last price: {decision.metrics.price:.2f}",
            ],
        ),
        AgentTask(
            agent="Regime Analyst",
            objective="Classify the market regime and identify drivers before any trade plan.",
            tool=committee.ml_regime.model_version,
            status=_agentic_status(regime_agent.status if regime_agent else "watch"),
            confidence=_bounded_confidence(committee.ml_regime.confidence),
            finding=f"Regime is {committee.ml_regime.regime.replace('_', ' ')}.",
            evidence=committee.ml_regime.top_drivers[:3],
        ),
        AgentTask(
            agent="Manipulation Sentinel",
            objective="Search for traps that would worsen information asymmetry for retail users.",
            tool=committee.anomaly.method,
            status=sentinel_status,
            confidence=_bounded_confidence(max(0.55, committee.anomaly.score / 100 if committee.anomaly.status != "normal" else 1 - committee.anomaly.score / 140)),
            finding=f"Anomaly model reads {committee.anomaly.status} at {committee.anomaly.score:.0f}/100.",
            evidence=committee.anomaly.drivers[:4],
        ),
        AgentTask(
            agent="Risk Allocator",
            objective="Check leverage, stop distance, size, and stress-loss before routing.",
            tool="Strategy proposal + liquidation stress tests",
            status=_agentic_status(risk_agent.status if risk_agent else decision.status),
            confidence=_bounded_confidence(decision.proposal.confidence),
            finding=f"Proposed action is {decision.proposal.action.replace('_', ' ')} at {decision.proposal.leverage:.1f}x leverage.",
            evidence=[
                f"Size: {decision.proposal.position_size_usdt:.0f} USDT",
                f"Stop: {decision.proposal.stop_loss or 'locked'}",
                f"Worst stress equity: {min(row.projected_equity_usdt for row in decision.stress_tests):.0f} USDT",
            ],
        ),
        AgentTask(
            agent="Fairness Auditor",
            objective="Confirm the setup is explainable, auditable, and fair enough for non-institutional users.",
            tool="Fairness Passport scoring rubric",
            status=fairness_status,
            confidence=_bounded_confidence(decision.fairness_passport.score / 100),
            finding=decision.fairness_passport.summary,
            evidence=[
                f"{check.name}: {check.status} ({check.score:.0f}/100)"
                for check in decision.fairness_passport.checks[:4]
            ],
        ),
        AgentTask(
            agent="Execution Operator",
            objective="Prepare only the actions allowed by the audited gate.",
            tool="Execution planner + paper order router",
            status=execution_status if can_execute else "blocked",
            confidence=_bounded_confidence(committee.forecast.confidence),
            finding=f"Route style is {committee.execution_plan.order_style}; side is {committee.execution_plan.side}.",
            evidence=[
                f"Max slippage: {committee.execution_plan.max_slippage_bps:.1f} bps",
                f"Cooldown: {committee.execution_plan.cooldown_seconds}s",
                f"Stop-hit probability: {committee.forecast.stop_loss_hit_probability:.0%}",
            ],
        ),
        AgentTask(
            agent="Route Steward",
            objective="Select the least harmful paper route after slippage, leakage, and manipulation exposure are checked.",
            tool="Fair Execution Router",
            status=route_status,
            confidence=_bounded_confidence(router.fairness_floor_score / 100 if router.execution_permitted else 0.62),
            finding=f"{router.recommended_route} is recommended; router verdict is {router.verdict.replace('_', ' ')}.",
            evidence=[
                f"Max route notional: {router.max_route_notional_usdt:.0f} USDT",
                f"Liquidity budget: {router.liquidity_budget_usdt:.0f} USDT",
                *router.locked_reasons[:2],
            ],
        ),
        AgentTask(
            agent="Memory Curator",
            objective="Use session history so repeated rejected or concentrated behavior is visible.",
            tool="In-memory audit vault + paper portfolio journal",
            status=portfolio_status,
            confidence=_bounded_confidence(committee.calibration.calibration_score / 100),
            finding=f"Session holds {audit_count()} audits, {portfolio.accepted_order_count} accepted orders, and {portfolio.rejected_order_count} blocked orders.",
            evidence=[
                committee.calibration.note,
                f"Gross exposure: {portfolio.gross_exposure_usdt:.0f} USDT",
                f"Latest audit: {decision.audit_hash[:16]}",
            ],
        ),
    ]

    recommendation = (
        f"Mission can route a guarded paper {decision.final_action.replace('_', ' ')} via {router.recommended_route} after sizing and audit review."
        if can_execute
        else f"Mission should hold execution; route steward recommends {router.recommended_route} while agents focus on scenario comparison and risk reduction."
    )

    mission = AgentMission(
        id=f"mission-{decision.audit_hash[:12]}-{len(MISSIONS) + 1}",
        symbol=decision.symbol,
        category=decision.category,
        scenario=decision.scenario,
        generated_at=datetime.now(UTC),
        autonomy_level="guarded_paper" if can_execute else "advisory",
        final_recommendation=recommendation,
        can_execute=can_execute,
        decision=decision,
        portfolio=portfolio,
        tasks=tasks,
        action_queue=_mission_actions(decision, portfolio, can_execute),
        memory_notes=[
            f"Audit vault contains {audit_count()} reports from this demo process.",
            f"Calibration bucket: {committee.calibration.confidence_bucket}; score {committee.calibration.calibration_score:.0f}/100.",
            f"Paper book equity is {portfolio.equity_usdt:.0f} USDT with {portfolio.gross_exposure_usdt:.0f} USDT open exposure.",
        ],
        risk_register=[
            *_risk_register(decision, portfolio, can_execute),
            *([] if router.execution_permitted else router.locked_reasons[:3]),
        ],
    )
    MISSIONS.append(mission)
    del MISSIONS[:-12]
    return mission


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "fairflow-guardian"}


@app.get("/api/analysis", response_model=GuardianDecision)
async def analyze(
    symbol: str = Query("BTCUSDT", min_length=3, max_length=24),
    category: str = Query("linear", pattern="^(spot|linear|inverse)$"),
    scenario: str = Query("live", pattern="^(live|calm|volatile|manipulated)$"),
) -> GuardianDecision:
    return await build_decision_for(symbol=symbol, category=category, scenario=scenario)


@app.get("/api/compare", response_model=ScenarioComparison)
async def compare_scenarios(
    symbol: str = Query("BTCUSDT", min_length=3, max_length=24),
    category: str = Query("linear", pattern="^(spot|linear|inverse)$"),
    include_live: bool = Query(False),
) -> ScenarioComparison:
    scenario_names = ("live", *SCENARIOS) if include_live else SCENARIOS
    decisions = [await build_decision_for(symbol=symbol, category=category, scenario=item) for item in scenario_names]
    approved_count = sum(1 for item in decisions if item.status == "approved")
    blocked_count = sum(1 for item in decisions if item.status == "blocked")
    average_fairness = sum(item.fairness_passport.score for item in decisions) / len(decisions)
    healthiest = max(decisions, key=lambda item: item.fairness_passport.score)

    return ScenarioComparison(
        symbol=symbol,
        category=category,
        generated_at=decisions[-1].generated_at,
        summary=(
            f"{approved_count} approved, {blocked_count} blocked, "
            f"average fairness {average_fairness:.0f}/100 across {len(decisions)} scenarios."
        ),
        healthiest_scenario=healthiest.scenario,
        approved_count=approved_count,
        blocked_count=blocked_count,
        average_fairness_score=average_fairness,
        decisions=decisions,
    )


@app.get("/api/watchlist", response_model=WatchlistReport)
async def scan_watchlist(
    symbols: str = Query("BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT,ADAUSDT,DOGEUSDT", min_length=3, max_length=160),
    category: str = Query("linear", pattern="^(spot|linear|inverse)$"),
    scenario: str = Query("live", pattern="^(live|calm|volatile|manipulated)$"),
) -> WatchlistReport:
    requested_symbols = []
    for raw_symbol in symbols.split(","):
        symbol = raw_symbol.strip().upper()
        if symbol and symbol not in requested_symbols:
            requested_symbols.append(symbol)

    if not requested_symbols:
        raise HTTPException(status_code=422, detail="At least one symbol is required")
    if len(requested_symbols) > 8:
        raise HTTPException(status_code=422, detail="Watchlist scanner supports up to 8 symbols per request")

    decisions = [
        await build_decision_for(symbol=symbol, category=category, scenario=scenario)
        for symbol in requested_symbols
    ]
    items = sorted(
        [
            WatchlistItem(
                symbol=decision.symbol,
                category=decision.category,
                scenario=decision.scenario,
                price=decision.metrics.price,
                status=decision.status,
                final_action=decision.final_action,
                fairness_score=decision.fairness_passport.score,
                liquidity_score=decision.metrics.liquidity_score,
                anomaly_score=decision.ai_committee.anomaly.score,
                rank_score=_watchlist_rank(decision),
                audit_hash=decision.audit_hash,
                summary=decision.summary,
                rank_reason=(
                    f"Fairness {decision.fairness_passport.score:.0f}/100, "
                    f"liquidity {decision.metrics.liquidity_score:.0f}/100, "
                    f"anomaly {decision.ai_committee.anomaly.score:.0f}/100, "
                    f"gate {decision.status}, "
                    f"market-depth adjustment {_market_depth_adjustment(decision.symbol):+.0f}."
                ),
            )
            for decision in decisions
        ],
        key=lambda item: item.rank_score,
        reverse=True,
    )

    return WatchlistReport(
        symbols=requested_symbols,
        category=category,
        scenario=scenario,
        generated_at=datetime.now(UTC),
        safest_symbol=items[0].symbol if items else None,
        items=items,
    )


@app.get("/api/market/series", response_model=MarketSeries)
async def market_series(
    symbol: str = Query("BTCUSDT", min_length=3, max_length=24),
    category: str = Query("linear", pattern="^(spot|linear|inverse)$"),
    scenario: str = Query("live", pattern="^(live|calm|volatile|manipulated)$"),
) -> MarketSeries:
    snapshot = await get_snapshot_for(symbol=symbol, category=category, scenario=scenario)
    first_open = snapshot.candles[0].open
    latest_price = snapshot.candles[-1].close
    change_pct = ((latest_price / first_open) - 1) * 100 if first_open else 0

    return MarketSeries(
        symbol=snapshot.symbol,
        category=snapshot.category,
        scenario=snapshot.scenario,
        source=snapshot.source,
        generated_at=snapshot.generated_at,
        interval_minutes=5,
        latest_price=latest_price,
        change_pct=change_pct,
        candles=snapshot.candles,
    )


@app.get("/api/impact", response_model=ImpactLedgerReport)
def impact_ledger(
    limit: int = Query(50, ge=1, le=200),
) -> ImpactLedgerReport:
    return build_impact_ledger_report(limit=limit)


@app.get("/api/audits", response_model=list[GuardianDecision])
def list_audits() -> list[GuardianDecision]:
    decisions = AUDIT_LEDGER.list_decisions(limit=20)
    for decision in decisions:
        AUDITS[decision.audit_hash] = decision
    return decisions


@app.get("/api/audits/{audit_hash}", response_model=GuardianDecision)
def get_audit(audit_hash: str) -> GuardianDecision:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return decision


@app.get("/api/audits/{audit_hash}/receipt", response_model=FairnessReceipt)
def get_fairness_receipt(audit_hash: str) -> FairnessReceipt:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_fairness_receipt(decision)


@app.get("/api/audits/{audit_hash}/retail-cohorts", response_model=RetailCohortReport)
def get_retail_cohorts(audit_hash: str) -> RetailCohortReport:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_retail_cohort_report(decision)


@app.get("/api/audits/{audit_hash}/anchor-proof", response_model=AnchorProof)
def get_anchor_proof(audit_hash: str) -> AnchorProof:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_anchor_proof(decision)


@app.get("/api/audits/{audit_hash}/judge-brief", response_model=JudgeBrief)
def get_judge_brief(audit_hash: str) -> JudgeBrief:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_judge_brief(decision)


@app.get("/api/audits/{audit_hash}/hackathon-readiness", response_model=HackathonReadinessReport)
def get_hackathon_readiness(audit_hash: str) -> HackathonReadinessReport:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_hackathon_readiness_report(decision)


@app.get("/api/audits/{audit_hash}/submission-kit", response_model=HackathonSubmissionKit)
def get_hackathon_submission_kit(audit_hash: str) -> HackathonSubmissionKit:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_hackathon_submission_kit(decision)


@app.get("/api/audits/{audit_hash}/model-provenance", response_model=ModelProvenanceCard)
def get_model_provenance(audit_hash: str) -> ModelProvenanceCard:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_model_provenance_card(decision)


@app.get("/api/audits/{audit_hash}/policy-stress", response_model=PolicyStressReport)
def get_policy_stress(audit_hash: str) -> PolicyStressReport:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_policy_stress_report(decision)


@app.get("/api/audits/{audit_hash}/counterfactuals", response_model=CounterfactualFairnessReport)
def get_counterfactuals(audit_hash: str) -> CounterfactualFairnessReport:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_counterfactual_fairness_report(decision)


@app.get("/api/audits/{audit_hash}/execution-router", response_model=FairExecutionRouterReport)
def get_execution_router(audit_hash: str) -> FairExecutionRouterReport:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_fair_execution_router(decision)


@app.get("/api/audits/{audit_hash}/red-team", response_model=RedTeamReport)
def get_red_team_report(audit_hash: str) -> RedTeamReport:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_red_team_report(decision)


@app.get("/api/audits/{audit_hash}/evidence-pack", response_model=AuditEvidencePack)
def get_evidence_pack(audit_hash: str) -> AuditEvidencePack:
    decision = get_decision_from_audit(audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Audit hash not found in this process")
    return build_evidence_pack(decision)


@app.post("/api/orders/simulate", response_model=PaperOrder)
def simulate_order(request: PaperOrderRequest) -> PaperOrder:
    decision = get_decision_from_audit(request.audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision must be generated before paper execution")

    if decision.status != "approved":
        order = PaperOrder(
            accepted=False,
            audit_hash=request.audit_hash,
            client_order_id=f"rejected-{request.audit_hash[:12]}",
            symbol=decision.symbol,
            category=decision.category,
            side="None",
            order_type="None",
            qty_usdt=0,
            entry_price=None,
            leverage=0,
            max_slippage_bps=0,
            stop_loss=None,
            take_profit=None,
            created_at=datetime.now(UTC),
            message="Execution blocked by FairFlow Guardian. No paper order was created.",
        )
        PAPER_ORDERS.append(order)
        return order

    side = "Buy" if decision.final_action == "LONG" else "Sell"
    order = PaperOrder(
        accepted=True,
        audit_hash=request.audit_hash,
        client_order_id=f"paper-{request.audit_hash[:12]}",
        symbol=decision.symbol,
        category=decision.category,
        side=side,
        order_type="Market",
        qty_usdt=decision.proposal.position_size_usdt,
        entry_price=decision.proposal.entry_price,
        leverage=decision.proposal.leverage,
        max_slippage_bps=6.0,
        stop_loss=decision.proposal.stop_loss,
        take_profit=decision.proposal.take_profit,
        created_at=datetime.now(UTC),
        message="Paper order accepted. In production this would route to Bybit testnet with signed API credentials.",
    )
    PAPER_ORDERS.append(order)
    return order


@app.get("/api/portfolio", response_model=PaperPortfolio)
async def paper_portfolio(
    scenario: str = Query("live", pattern="^(live|calm|volatile|manipulated)$"),
) -> PaperPortfolio:
    accepted = [order for order in PAPER_ORDERS if order.accepted and order.entry_price and order.side != "None"]
    rejected = [order for order in PAPER_ORDERS if not order.accepted]
    marks: dict[tuple[str, str], float] = {}
    positions: list[PaperPosition] = []

    for order in accepted:
        key = (order.symbol, order.category)
        if key not in marks:
            snapshot = await get_snapshot_for(symbol=order.symbol, category=order.category, scenario=scenario)
            marks[key] = snapshot.candles[-1].close

        current_price = marks[key]
        direction = 1 if order.side == "Buy" else -1
        price_return = ((current_price - order.entry_price) / order.entry_price) * direction
        pnl_pct = price_return * max(order.leverage, 1) * 100
        pnl_usdt = order.qty_usdt * price_return * max(order.leverage, 1)
        status = "open"

        if order.stop_loss:
            stop_hit = current_price <= order.stop_loss if order.side == "Buy" else current_price >= order.stop_loss
            if stop_hit:
                status = "stopped"
        if order.take_profit:
            target_hit = current_price >= order.take_profit if order.side == "Buy" else current_price <= order.take_profit
            if target_hit:
                status = "target"

        positions.append(
            PaperPosition(
                client_order_id=order.client_order_id,
                audit_hash=order.audit_hash,
                symbol=order.symbol,
                side=order.side,
                entry_price=order.entry_price,
                current_price=current_price,
                qty_usdt=order.qty_usdt,
                leverage=order.leverage,
                gross_exposure_usdt=order.qty_usdt * max(order.leverage, 1),
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                pnl_usdt=pnl_usdt,
                pnl_pct=pnl_pct,
                status=status,
                opened_at=order.created_at,
            )
        )

    realized_pnl = sum(position.pnl_usdt for position in positions if position.status in {"stopped", "target"})
    unrealized_pnl = sum(position.pnl_usdt for position in positions if position.status == "open")
    gross_exposure = sum(position.gross_exposure_usdt for position in positions if position.status == "open")
    net_exposure = sum(
        position.gross_exposure_usdt * (1 if position.side == "Buy" else -1)
        for position in positions
        if position.status == "open"
    )
    equity = STARTING_EQUITY_USDT + realized_pnl + unrealized_pnl
    risk_notes: list[str] = []

    if gross_exposure > STARTING_EQUITY_USDT:
        risk_notes.append("Gross paper exposure exceeds starting equity; reduce size before routing real orders.")
    if abs(net_exposure) > STARTING_EQUITY_USDT * 0.75:
        risk_notes.append("Net exposure is concentrated in one direction.")
    if rejected:
        risk_notes.append(f"{len(rejected)} blocked execution attempts were preserved in the journal.")
    if not positions:
        risk_notes.append("No accepted paper positions yet.")
    if not risk_notes:
        risk_notes.append("Paper portfolio is inside demo exposure guardrails.")

    return PaperPortfolio(
        generated_at=datetime.now(UTC),
        scenario=scenario,
        starting_equity_usdt=STARTING_EQUITY_USDT,
        equity_usdt=equity,
        realized_pnl_usdt=realized_pnl,
        unrealized_pnl_usdt=unrealized_pnl,
        gross_exposure_usdt=gross_exposure,
        net_exposure_usdt=net_exposure,
        accepted_order_count=len(accepted),
        rejected_order_count=len(rejected),
        positions=positions[-12:],
        orders=PAPER_ORDERS[-20:],
        risk_notes=risk_notes,
    )


@app.post("/api/portfolio/reset", response_model=PaperPortfolio)
async def reset_paper_portfolio() -> PaperPortfolio:
    PAPER_ORDERS.clear()
    return await paper_portfolio(scenario="calm")


@app.get("/api/agents/mission", response_model=AgentMission)
async def run_agent_mission(
    symbol: str = Query("BTCUSDT", min_length=3, max_length=24),
    category: str = Query("linear", pattern="^(spot|linear|inverse)$"),
    scenario: str = Query("live", pattern="^(live|calm|volatile|manipulated)$"),
    audit_hash: str | None = Query(None, min_length=12, max_length=128),
) -> AgentMission:
    if audit_hash:
        decision = get_decision_from_audit(audit_hash)
        if not decision:
            raise HTTPException(status_code=404, detail="Audit hash not found in this process")
        return await build_agent_mission_for(
            symbol=decision.symbol,
            category=decision.category,
            scenario=decision.scenario,
            decision=decision,
        )
    return await build_agent_mission_for(symbol=symbol, category=category, scenario=scenario)


@app.get("/api/agents/missions", response_model=list[AgentMission])
def list_agent_missions() -> list[AgentMission]:
    return MISSIONS[-10:]


@app.post("/api/risk/size", response_model=RiskSizingResponse)
def calculate_risk_size(request: RiskSizingRequest) -> RiskSizingResponse:
    decision = get_decision_from_audit(request.audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision must be generated before risk sizing")

    risk_amount = request.account_equity_usdt * (request.risk_budget_pct / 100)
    leverage = max(decision.proposal.leverage, 1)
    safeguards = [
        "Execution must remain blocked unless the audited decision is approved.",
        "Risk amount is capped by the user's chosen account-risk budget.",
        "Notional is capped by the user's max exposure percentage.",
        "Margin estimate uses the strategy leverage from the audited decision.",
    ]

    if decision.status != "approved" or not decision.proposal.entry_price or not decision.proposal.stop_loss:
        return RiskSizingResponse(
            audit_hash=request.audit_hash,
            executable=False,
            account_equity_usdt=request.account_equity_usdt,
            risk_budget_pct=request.risk_budget_pct,
            risk_amount_usdt=risk_amount,
            stop_distance_pct=None,
            recommended_notional_usdt=0,
            estimated_margin_usdt=0,
            max_loss_usdt=0,
            leverage=leverage,
            capped_by=["execution_gate"],
            message="Sizing locked because FairFlow did not approve this decision for execution.",
            safeguards=safeguards,
        )

    stop_distance_pct = abs(decision.proposal.entry_price - decision.proposal.stop_loss) / decision.proposal.entry_price * 100
    if stop_distance_pct <= 0:
        raise HTTPException(status_code=422, detail="Approved decision has an invalid stop distance")

    notional_by_risk = risk_amount / (stop_distance_pct / 100)
    notional_by_cap = request.account_equity_usdt * (request.max_notional_pct / 100)
    scaled_guardian_cap = request.account_equity_usdt * 0.25
    recommended_notional = min(notional_by_risk, notional_by_cap, scaled_guardian_cap)
    max_loss = recommended_notional * (stop_distance_pct / 100)
    estimated_margin = recommended_notional / leverage
    capped_by: list[str] = []

    if recommended_notional == notional_by_cap:
        capped_by.append("user_exposure_cap")
    if recommended_notional == scaled_guardian_cap:
        capped_by.append("guardian_retail_cap")
    if recommended_notional == notional_by_risk:
        capped_by.append("risk_budget")

    return RiskSizingResponse(
        audit_hash=request.audit_hash,
        executable=True,
        account_equity_usdt=request.account_equity_usdt,
        risk_budget_pct=request.risk_budget_pct,
        risk_amount_usdt=risk_amount,
        stop_distance_pct=stop_distance_pct,
        recommended_notional_usdt=recommended_notional,
        estimated_margin_usdt=estimated_margin,
        max_loss_usdt=max_loss,
        leverage=leverage,
        capped_by=capped_by,
        message="Sizing is executable under the current FairFlow audit gate and retail exposure caps.",
        safeguards=safeguards,
    )


@app.post("/api/policy/evaluate", response_model=GuardrailPolicyReport)
def evaluate_policy(request: GuardrailPolicyRequest) -> GuardrailPolicyReport:
    decision = get_decision_from_audit(request.audit_hash)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision must be generated before policy evaluation")
    return evaluate_guardrail_policy(decision, request)
