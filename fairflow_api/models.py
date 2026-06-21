from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Candle(BaseModel):
    start_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class BookLevel(BaseModel):
    price: float
    size: float


class Ticker(BaseModel):
    last_price: float
    bid_price: float
    ask_price: float
    mark_price: float | None = None
    index_price: float | None = None
    price_24h_pct: float = 0.0
    volume_24h: float = 0.0
    turnover_24h: float = 0.0
    funding_rate: float = 0.0
    open_interest: float = 0.0


class MarketSnapshot(BaseModel):
    symbol: str
    category: str
    scenario: str
    source: str
    generated_at: datetime
    candles: list[Candle]
    bids: list[BookLevel]
    asks: list[BookLevel]
    ticker: Ticker


class MarketSeries(BaseModel):
    symbol: str
    category: str
    scenario: str
    source: str
    generated_at: datetime
    interval_minutes: int
    latest_price: float
    change_pct: float
    candles: list[Candle]


class MarketMetrics(BaseModel):
    price: float
    mid_price: float
    spread_bps: float
    order_book_imbalance: float
    top_depth_usd: float
    impact_25k_bps: float
    realized_volatility_pct: float
    range_24h_pct: float
    momentum_1h_pct: float
    momentum_4h_pct: float
    rsi_14: float
    latest_volume_ratio: float
    latest_wick_pct: float
    funding_rate_bps: float
    open_interest: float
    liquidity_score: float


class StrategyProposal(BaseModel):
    action: Literal["LONG", "SHORT", "NO_TRADE"]
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    leverage: float
    position_size_usdt: float
    confidence: float
    thesis: str
    risk_budget_pct: float = 1.0


class AgentFinding(BaseModel):
    name: str
    status: Literal["pass", "watch", "block"]
    verdict: str
    score: float = Field(ge=0, le=100)
    rationale: list[str]


class StressResult(BaseModel):
    price_move_pct: float
    projected_pnl_pct: float
    projected_equity_usdt: float
    stop_triggered: bool
    note: str


class MLRegimeSignal(BaseModel):
    regime: Literal["trend", "mean_reversion", "choppy", "high_volatility", "fragile_liquidity"]
    confidence: float = Field(ge=0, le=1)
    probabilities: dict[str, float]
    top_drivers: list[str]
    model_version: str


class AnomalySignal(BaseModel):
    score: float = Field(ge=0, le=100)
    status: Literal["normal", "elevated", "extreme"]
    drivers: list[str]
    method: str


class ForecastSignal(BaseModel):
    horizon_minutes: int
    expected_move_pct: float
    downside_risk_pct: float
    upside_risk_pct: float
    stop_loss_hit_probability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    rationale: list[str]


class ExecutionPlan(BaseModel):
    order_style: Literal["none", "limit", "market"]
    side: Literal["Buy", "Sell", "None"]
    entry_style: str
    max_slippage_bps: float
    cooldown_seconds: int
    time_in_force: str
    notes: list[str]


class BacktestSummary(BaseModel):
    strategy_name: str
    lookback_candles: int
    trades: int
    rejected_setups: int
    win_rate: float = Field(ge=0, le=1)
    average_return_pct: float
    max_drawdown_pct: float
    conclusion: str


class CalibrationMemory(BaseModel):
    sample_size: int
    confidence_bucket: str
    calibration_score: float = Field(ge=0, le=100)
    recent_false_positives: int
    avoided_trade_count: int
    note: str


class CommitteeReport(BaseModel):
    narrator_summary: str
    debate: list[str]
    ml_regime: MLRegimeSignal
    anomaly: AnomalySignal
    forecast: ForecastSignal
    execution_plan: ExecutionPlan
    backtest: BacktestSummary
    calibration: CalibrationMemory


class DecisionTraceStep(BaseModel):
    step: int
    status: Literal["pass", "watch", "block"]
    title: str
    summary: str
    evidence: list[str]


class FairnessCheck(BaseModel):
    name: str
    status: Literal["pass", "watch", "block"]
    score: float = Field(ge=0, le=100)
    explanation: str
    evidence: list[str]


class FairnessPassport(BaseModel):
    score: float = Field(ge=0, le=100)
    verdict: Literal["fair_to_execute", "wait_for_parity", "unfair_to_retail"]
    summary: str
    estimated_hidden_cost_bps: float
    checks: list[FairnessCheck]
    retail_protections: list[str]


class GuardianDecision(BaseModel):
    id: str
    symbol: str
    category: str
    scenario: str
    source: str
    generated_at: datetime
    final_action: Literal["LONG", "SHORT", "NO_TRADE"]
    status: Literal["approved", "blocked", "observe"]
    summary: str
    metrics: MarketMetrics
    proposal: StrategyProposal
    agents: list[AgentFinding]
    ai_committee: CommitteeReport
    decision_trace: list[DecisionTraceStep]
    fairness_passport: FairnessPassport
    stress_tests: list[StressResult]
    safeguards: list[str]
    audit_hash: str


class ScenarioComparison(BaseModel):
    symbol: str
    category: str
    generated_at: datetime
    summary: str
    healthiest_scenario: str
    approved_count: int
    blocked_count: int
    average_fairness_score: float
    decisions: list[GuardianDecision]


class PaperOrderRequest(BaseModel):
    audit_hash: str


class PaperOrder(BaseModel):
    accepted: bool
    audit_hash: str
    client_order_id: str
    symbol: str
    category: str
    side: Literal["Buy", "Sell", "None"]
    order_type: Literal["Market", "None"]
    qty_usdt: float
    entry_price: float | None
    leverage: float
    max_slippage_bps: float
    stop_loss: float | None
    take_profit: float | None
    created_at: datetime
    message: str


class PaperPosition(BaseModel):
    client_order_id: str
    audit_hash: str
    symbol: str
    side: Literal["Buy", "Sell"]
    entry_price: float
    current_price: float
    qty_usdt: float
    leverage: float
    gross_exposure_usdt: float
    stop_loss: float | None
    take_profit: float | None
    pnl_usdt: float
    pnl_pct: float
    status: Literal["open", "stopped", "target"]
    opened_at: datetime


class PaperPortfolio(BaseModel):
    generated_at: datetime
    scenario: str
    starting_equity_usdt: float
    equity_usdt: float
    realized_pnl_usdt: float
    unrealized_pnl_usdt: float
    gross_exposure_usdt: float
    net_exposure_usdt: float
    accepted_order_count: int
    rejected_order_count: int
    positions: list[PaperPosition]
    orders: list[PaperOrder]
    risk_notes: list[str]


class RiskSizingRequest(BaseModel):
    audit_hash: str
    account_equity_usdt: float = Field(default=10_000.0, gt=0, le=10_000_000)
    risk_budget_pct: float = Field(default=1.0, gt=0, le=5)
    max_notional_pct: float = Field(default=25.0, gt=0, le=100)


class RiskSizingResponse(BaseModel):
    audit_hash: str
    executable: bool
    account_equity_usdt: float
    risk_budget_pct: float
    risk_amount_usdt: float
    stop_distance_pct: float | None
    recommended_notional_usdt: float
    estimated_margin_usdt: float
    max_loss_usdt: float
    leverage: float
    capped_by: list[str]
    message: str
    safeguards: list[str]


class GuardrailPolicyRequest(BaseModel):
    audit_hash: str
    min_fairness_score: float = Field(default=80.0, ge=0, le=100)
    max_hidden_cost_bps: float = Field(default=8.0, ge=0, le=100)
    max_anomaly_score: float = Field(default=45.0, ge=0, le=100)
    min_liquidity_score: float = Field(default=55.0, ge=0, le=100)
    max_leverage: float = Field(default=3.0, gt=0, le=25)
    max_stop_hit_probability: float = Field(default=0.45, ge=0, le=1)


class GuardrailPolicyCheck(BaseModel):
    name: str
    status: Literal["pass", "watch", "block"]
    observed: float | str
    limit: float | str
    unit: str
    explanation: str


class GuardrailPolicyReport(BaseModel):
    audit_hash: str
    symbol: str
    scenario: str
    generated_at: datetime
    verdict: Literal["compliant", "needs_review", "blocked"]
    execution_allowed: bool
    summary: str
    checks: list[GuardrailPolicyCheck]
    suggested_actions: list[str]
    policy: GuardrailPolicyRequest


class PolicyStressOutcome(BaseModel):
    name: str
    stance: Literal["access_first", "balanced", "strict"]
    purpose: str
    report: GuardrailPolicyReport
    pass_count: int
    watch_count: int
    block_count: int
    first_breaking_check: str | None


class PolicyStressReport(BaseModel):
    audit_hash: str
    symbol: str
    scenario: str
    generated_at: datetime
    resilience_verdict: Literal["stable_greenlight", "fragile_greenlight", "needs_review", "protective_lockdown"]
    stability_score: float = Field(ge=0, le=100)
    execution_allowed_count: int
    blocked_policy_count: int
    summary: str
    outcomes: list[PolicyStressOutcome]
    fragile_checks: list[str]
    judge_takeaway: str
    recommended_next_steps: list[str]


class CounterfactualLever(BaseModel):
    name: str
    lever_type: Literal[
        "fairness",
        "hidden_cost",
        "anomaly",
        "liquidity",
        "leverage",
        "stop_risk",
        "core_gate",
    ]
    status: Literal["already_clear", "improvement_needed", "non_bypassable"]
    current_value: float | str
    target_value: float | str
    unit: str
    improvement_required: float | None
    direction: Literal["increase", "decrease", "hold", "fresh_audit_required"]
    retail_impact: str
    explanation: str


class CounterfactualFairnessReport(BaseModel):
    audit_hash: str
    symbol: str
    scenario: str
    generated_at: datetime
    verdict: Literal["already_fair", "improvable", "fresh_audit_required", "do_not_unlock"]
    unlockable_in_current_audit: bool
    readiness_score: float = Field(ge=0, le=100)
    summary: str
    top_blocker: str
    levers: list[CounterfactualLever]
    non_bypassable_constraints: list[str]
    recommended_next_steps: list[str]
    judge_takeaway: str


class ExecutionRouteCandidate(BaseModel):
    name: str
    route_type: Literal["market", "post_only_limit", "twap", "maker_ladder", "hold"]
    status: Literal["recommended", "available", "watch", "locked"]
    expected_slippage_bps: float
    fill_probability: float = Field(ge=0, le=1)
    information_leakage_score: float = Field(ge=0, le=100)
    manipulation_exposure_score: float = Field(ge=0, le=100)
    retail_fairness_score: float = Field(ge=0, le=100)
    max_notional_usdt: float
    time_to_complete_seconds: int
    reason: str
    safeguards: list[str]


class FairExecutionRouterReport(BaseModel):
    audit_hash: str
    symbol: str
    scenario: str
    generated_at: datetime
    verdict: Literal["route_ready", "route_with_caution", "paper_only_locked", "no_fair_route"]
    execution_permitted: bool
    recommended_route: str
    summary: str
    fairness_floor_score: float = Field(ge=0, le=100)
    liquidity_budget_usdt: float
    max_route_notional_usdt: float
    route_candidates: list[ExecutionRouteCandidate]
    locked_reasons: list[str]
    verification_notes: list[str]
    judge_takeaway: str


class RedTeamProbe(BaseModel):
    name: str
    attack_vector: Literal[
        "liquidity_withdrawal",
        "spoofed_imbalance",
        "volatility_cascade",
        "funding_squeeze",
        "oracle_gap",
    ]
    severity: Literal["moderate", "high", "critical"]
    status: Literal["pass", "watch", "block"]
    stressed_hidden_cost_bps: float
    stressed_anomaly_score: float = Field(ge=0, le=100)
    stressed_liquidity_score: float = Field(ge=0, le=100)
    stressed_stop_hit_probability: float = Field(ge=0, le=1)
    stressed_impact_25k_bps: float
    first_trigger: str
    retail_harm: str
    mitigation: str
    explanation: str


class RedTeamReport(BaseModel):
    audit_hash: str
    symbol: str
    scenario: str
    generated_at: datetime
    verdict: Literal["resilient", "watchlist", "kill_switch_ready", "already_locked"]
    integrity_score: float = Field(ge=0, le=100)
    baseline_gate: str
    summary: str
    probes: list[RedTeamProbe]
    blocked_probe_count: int
    watch_probe_count: int
    worst_probe: str
    kill_switches: list[str]
    judge_takeaway: str
    recommended_next_steps: list[str]


class FairnessReceiptMetric(BaseModel):
    label: str
    value: str
    status: Literal["pass", "watch", "block", "info"]
    explanation: str


class FairnessReceipt(BaseModel):
    audit_hash: str
    symbol: str
    category: str
    scenario: str
    generated_at: datetime
    decision_status: Literal["approved", "blocked", "observe"]
    final_action: Literal["LONG", "SHORT", "NO_TRADE"]
    public_summary: str
    retail_verdict: str
    bga_alignment_score: float = Field(ge=0, le=100)
    metrics: list[FairnessReceiptMetric]
    agent_concerns: list[str]
    retail_protections: list[str]
    verification_steps: list[str]
    machine_readable_url: str
    disclaimer: str


class RetailCohortProfile(BaseModel):
    name: str
    account_equity_usdt: float = Field(gt=0)
    risk_budget_pct: float = Field(gt=0, le=5)
    max_notional_pct: float = Field(gt=0, le=100)


class RetailCohortResult(BaseModel):
    profile: RetailCohortProfile
    status: Literal["pass", "watch", "block"]
    executable: bool
    recommended_notional_usdt: float
    estimated_margin_usdt: float
    hidden_cost_usdt: float
    hidden_cost_pct_equity: float
    max_loss_usdt: float
    max_loss_pct_equity: float
    buying_power_used_pct: float
    stop_distance_pct: float | None
    friction_score: float = Field(ge=0, le=100)
    notes: list[str]


class RetailCohortReport(BaseModel):
    audit_hash: str
    symbol: str
    category: str
    scenario: str
    generated_at: datetime
    verdict: Literal["inclusive", "limited", "exclusionary"]
    summary: str
    pass_count: int
    watch_count: int
    block_count: int
    cohorts: list[RetailCohortResult]
    fairness_warnings: list[str]


class ImpactLedgerIssue(BaseModel):
    label: str
    count: int
    severity: Literal["info", "watch", "block"]
    examples: list[str]


class ImpactLedgerReport(BaseModel):
    generated_at: datetime
    audit_count: int
    approved_count: int
    observe_count: int
    blocked_count: int
    no_trade_count: int
    manipulation_alert_count: int
    cohort_inclusive_count: int
    cohort_limited_count: int
    cohort_exclusionary_count: int
    estimated_hidden_cost_saved_usdt: float
    average_fairness_score: float
    average_hidden_cost_bps: float
    average_liquidity_score: float
    bga_ethos_score: float = Field(ge=0, le=100)
    summary: str
    issues: list[ImpactLedgerIssue]
    recent_audit_hashes: list[str]


class AnchorProof(BaseModel):
    audit_hash: str
    decision_hash_bytes32: str
    symbol: str
    action: Literal["LONG", "SHORT", "NO_TRADE"]
    scenario: str
    status: Literal["approved", "blocked", "observe"]
    generated_at: datetime
    contract_name: str
    contract_file: str
    function_signature: str
    metadata_uri: str
    audit_url: str
    receipt_url: str
    payload_hash: str
    calldata_preview: str
    contract_arguments: dict[str, str]
    metadata: dict[str, str | float | int | bool]
    safety_notes: list[str]
    verification_steps: list[str]


class JudgeBriefRubricItem(BaseModel):
    category: Literal["bga_ethos", "technical_depth", "risk_management", "transparency"]
    score: float = Field(ge=0, le=100)
    headline: str
    evidence: list[str]
    demo_cue: str


class JudgeBriefStep(BaseModel):
    step: int
    title: str
    script: str
    evidence_url: str | None
    proof_point: str


class JudgeBrief(BaseModel):
    audit_hash: str
    symbol: str
    scenario: str
    generated_at: datetime
    one_sentence_pitch: str
    judge_thesis: str
    recommended_opening: str
    total_demo_minutes: float
    rubric: list[JudgeBriefRubricItem]
    demo_steps: list[JudgeBriefStep]
    safety_boundaries: list[str]
    likely_questions: list[str]
    proof_links: list[str]


class HackathonReadinessCriterion(BaseModel):
    category: Literal["bga_ethos", "technical_depth", "risk_management", "transparency"]
    max_points: int
    readiness_score: float = Field(ge=0, le=100)
    status: Literal["ready", "watch", "gap"]
    headline: str
    evidence: list[str]
    proof_urls: list[str]
    judge_angle: str
    remaining_risks: list[str]


class HackathonRunbookStep(BaseModel):
    step: int
    title: str
    ui_action: str
    expected_result: str
    underlying_mechanism: str
    proof_url: str | None
    judge_script: str
    criteria: list[Literal["bga_ethos", "technical_depth", "risk_management", "transparency"]]


class HackathonReadinessReport(BaseModel):
    audit_hash: str
    symbol: str
    scenario: str
    generated_at: datetime
    verdict: Literal["demo_ready", "needs_review", "blocked_demo"]
    readiness_score: float = Field(ge=0, le=100)
    summary: str
    recommended_demo_minutes: float
    criteria: list[HackathonReadinessCriterion]
    runbook_steps: list[HackathonRunbookStep]
    strongest_claims: list[str]
    known_limitations: list[str]
    final_30_second_pitch: str
    proof_links: list[str]


class SubmissionVideoSegment(BaseModel):
    slide: int
    timecode: str
    title: str
    narration: str
    dashboard_action: str
    proof_url: str | None


class SubmissionAsset(BaseModel):
    label: str
    path: str
    purpose: str
    required: bool = True


class SubmissionChecklistItem(BaseModel):
    label: str
    status: Literal["ready", "watch"]
    evidence: str


class HackathonSubmissionKit(BaseModel):
    audit_hash: str
    symbol: str
    scenario: str
    generated_at: datetime
    headline: str
    total_runtime_seconds: int
    opening_hook: str
    video_segments: list[SubmissionVideoSegment]
    submission_assets: list[SubmissionAsset]
    final_checklist: list[SubmissionChecklistItem]
    copy_block: str
    proof_links: list[str]


class ProvenanceDataSource(BaseModel):
    name: str
    source_type: Literal["live_public_api", "deterministic_fallback", "derived", "session_memory"]
    status: Literal["active", "fallback", "derived"]
    fields: list[str]
    caveat: str


class ModelComponentCard(BaseModel):
    name: str
    component_type: Literal["ml_signal", "heuristic_agent", "risk_model", "execution_guard", "audit_infrastructure"]
    version: str
    inputs: list[str]
    outputs: list[str]
    limitations: list[str]
    validation: str


class ModelProvenanceCard(BaseModel):
    audit_hash: str
    symbol: str
    scenario: str
    generated_at: datetime
    provenance_score: float = Field(ge=0, le=100)
    summary: str
    data_sources: list[ProvenanceDataSource]
    model_components: list[ModelComponentCard]
    feature_groups: list[str]
    known_limitations: list[str]
    validation_artifacts: list[str]
    reproducibility_steps: list[str]
    ethical_boundaries: list[str]


class EvidencePackClaim(BaseModel):
    label: str
    status: Literal["verified", "watch", "blocked"]
    evidence_url: str
    explanation: str


class AuditEvidencePack(BaseModel):
    audit_hash: str
    symbol: str
    scenario: str
    generated_at: datetime
    package_version: str
    headline: str
    summary: str
    verification_score: float = Field(ge=0, le=100)
    key_metrics: dict[str, str | float | int | bool]
    evidence_urls: dict[str, str]
    included_reports: list[str]
    core_claims: list[EvidencePackClaim]
    decision: GuardianDecision
    fairness_receipt: FairnessReceipt
    retail_cohorts: RetailCohortReport
    anchor_proof: AnchorProof
    judge_brief: JudgeBrief
    model_provenance: ModelProvenanceCard
    fair_execution_router: FairExecutionRouterReport
    counterfactuals: CounterfactualFairnessReport
    policy_stress: PolicyStressReport
    red_team: RedTeamReport
    verifier_notes: list[str]
    limitations: list[str]


class AgentTask(BaseModel):
    agent: str
    objective: str
    tool: str
    status: Literal["complete", "watch", "blocked"]
    confidence: float = Field(ge=0, le=1)
    finding: str
    evidence: list[str]


class AgentAction(BaseModel):
    label: str
    action_type: Literal[
        "refresh_market",
        "compare_scenarios",
        "size_position",
        "paper_execute",
        "hold",
        "review_audit",
        "reset_portfolio",
    ]
    priority: Literal["low", "medium", "high", "critical"]
    permitted: bool
    reason: str


class AgentMission(BaseModel):
    id: str
    symbol: str
    category: str
    scenario: str
    generated_at: datetime
    autonomy_level: Literal["advisory", "guarded_paper"]
    final_recommendation: str
    can_execute: bool
    decision: GuardianDecision
    portfolio: PaperPortfolio
    tasks: list[AgentTask]
    action_queue: list[AgentAction]
    memory_notes: list[str]
    risk_register: list[str]


class WatchlistItem(BaseModel):
    symbol: str
    category: str
    scenario: str
    price: float
    status: Literal["approved", "blocked", "observe"]
    final_action: Literal["LONG", "SHORT", "NO_TRADE"]
    fairness_score: float = Field(ge=0, le=100)
    liquidity_score: float = Field(ge=0, le=100)
    anomaly_score: float = Field(ge=0, le=100)
    rank_score: float
    audit_hash: str
    summary: str
    rank_reason: str


class WatchlistReport(BaseModel):
    symbols: list[str]
    category: str
    scenario: str
    generated_at: datetime
    safest_symbol: str | None
    items: list[WatchlistItem]
