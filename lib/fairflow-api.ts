export type AgentStatus = "pass" | "watch" | "block";
export type DecisionStatus = "approved" | "blocked" | "observe";
export type Scenario = "live" | "calm" | "volatile" | "manipulated";

export type Candle = {
  start_ms: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type MarketSeries = {
  symbol: string;
  category: string;
  scenario: string;
  source: string;
  generated_at: string;
  interval_minutes: number;
  latest_price: number;
  change_pct: number;
  candles: Candle[];
};

export type Metrics = {
  price: number;
  mid_price: number;
  spread_bps: number;
  order_book_imbalance: number;
  top_depth_usd: number;
  impact_25k_bps: number;
  realized_volatility_pct: number;
  range_24h_pct: number;
  momentum_1h_pct: number;
  momentum_4h_pct: number;
  rsi_14: number;
  latest_volume_ratio: number;
  latest_wick_pct: number;
  funding_rate_bps: number;
  open_interest: number;
  liquidity_score: number;
};

export type Proposal = {
  action: "LONG" | "SHORT" | "NO_TRADE";
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  leverage: number;
  position_size_usdt: number;
  confidence: number;
  thesis: string;
  risk_budget_pct: number;
};

export type Agent = {
  name: string;
  status: AgentStatus;
  verdict: string;
  score: number;
  rationale: string[];
};

export type Stress = {
  price_move_pct: number;
  projected_pnl_pct: number;
  projected_equity_usdt: number;
  stop_triggered: boolean;
  note: string;
};

export type MLRegimeSignal = {
  regime: "trend" | "mean_reversion" | "choppy" | "high_volatility" | "fragile_liquidity";
  confidence: number;
  probabilities: Record<string, number>;
  top_drivers: string[];
  model_version: string;
};

export type AnomalySignal = {
  score: number;
  status: "normal" | "elevated" | "extreme";
  drivers: string[];
  method: string;
};

export type ForecastSignal = {
  horizon_minutes: number;
  expected_move_pct: number;
  downside_risk_pct: number;
  upside_risk_pct: number;
  stop_loss_hit_probability: number;
  confidence: number;
  rationale: string[];
};

export type ExecutionPlan = {
  order_style: "none" | "limit" | "market";
  side: "Buy" | "Sell" | "None";
  entry_style: string;
  max_slippage_bps: number;
  cooldown_seconds: number;
  time_in_force: string;
  notes: string[];
};

export type BacktestSummary = {
  strategy_name: string;
  lookback_candles: number;
  trades: number;
  rejected_setups: number;
  win_rate: number;
  average_return_pct: number;
  max_drawdown_pct: number;
  conclusion: string;
};

export type CalibrationMemory = {
  sample_size: number;
  confidence_bucket: string;
  calibration_score: number;
  recent_false_positives: number;
  avoided_trade_count: number;
  note: string;
};

export type AICommittee = {
  narrator_summary: string;
  debate: string[];
  ml_regime: MLRegimeSignal;
  anomaly: AnomalySignal;
  forecast: ForecastSignal;
  execution_plan: ExecutionPlan;
  backtest: BacktestSummary;
  calibration: CalibrationMemory;
};

export type DecisionTraceStep = {
  step: number;
  status: AgentStatus;
  title: string;
  summary: string;
  evidence: string[];
};

export type FairnessCheck = {
  name: string;
  status: AgentStatus;
  score: number;
  explanation: string;
  evidence: string[];
};

export type FairnessPassport = {
  score: number;
  verdict: "fair_to_execute" | "wait_for_parity" | "unfair_to_retail";
  summary: string;
  estimated_hidden_cost_bps: number;
  checks: FairnessCheck[];
  retail_protections: string[];
};

export type Decision = {
  id: string;
  symbol: string;
  category: string;
  scenario: string;
  source: string;
  generated_at: string;
  final_action: "LONG" | "SHORT" | "NO_TRADE";
  status: DecisionStatus;
  summary: string;
  metrics: Metrics;
  proposal: Proposal;
  agents: Agent[];
  ai_committee: AICommittee;
  decision_trace: DecisionTraceStep[];
  fairness_passport: FairnessPassport;
  stress_tests: Stress[];
  safeguards: string[];
  audit_hash: string;
};

export type PaperOrder = {
  accepted: boolean;
  audit_hash: string;
  client_order_id: string;
  symbol: string;
  category: string;
  side: "Buy" | "Sell" | "None";
  order_type: "Market" | "None";
  qty_usdt: number;
  entry_price: number | null;
  leverage: number;
  max_slippage_bps: number;
  stop_loss: number | null;
  take_profit: number | null;
  created_at: string;
  message: string;
};

export type PaperPosition = {
  client_order_id: string;
  audit_hash: string;
  symbol: string;
  side: "Buy" | "Sell";
  entry_price: number;
  current_price: number;
  qty_usdt: number;
  leverage: number;
  gross_exposure_usdt: number;
  stop_loss: number | null;
  take_profit: number | null;
  pnl_usdt: number;
  pnl_pct: number;
  status: "open" | "stopped" | "target";
  opened_at: string;
};

export type PaperPortfolio = {
  generated_at: string;
  scenario: string;
  starting_equity_usdt: number;
  equity_usdt: number;
  realized_pnl_usdt: number;
  unrealized_pnl_usdt: number;
  gross_exposure_usdt: number;
  net_exposure_usdt: number;
  accepted_order_count: number;
  rejected_order_count: number;
  positions: PaperPosition[];
  orders: PaperOrder[];
  risk_notes: string[];
};

export type ScenarioComparison = {
  symbol: string;
  category: string;
  generated_at: string;
  summary: string;
  healthiest_scenario: string;
  approved_count: number;
  blocked_count: number;
  average_fairness_score: number;
  decisions: Decision[];
};

export type RiskSizingRequest = {
  audit_hash: string;
  account_equity_usdt: number;
  risk_budget_pct: number;
  max_notional_pct: number;
};

export type RiskSizing = {
  audit_hash: string;
  executable: boolean;
  account_equity_usdt: number;
  risk_budget_pct: number;
  risk_amount_usdt: number;
  stop_distance_pct: number | null;
  recommended_notional_usdt: number;
  estimated_margin_usdt: number;
  max_loss_usdt: number;
  leverage: number;
  capped_by: string[];
  message: string;
  safeguards: string[];
};

export type GuardrailPolicyRequest = {
  audit_hash: string;
  min_fairness_score: number;
  max_hidden_cost_bps: number;
  max_anomaly_score: number;
  min_liquidity_score: number;
  max_leverage: number;
  max_stop_hit_probability: number;
};

export type GuardrailPolicyCheck = {
  name: string;
  status: AgentStatus;
  observed: number | string;
  limit: number | string;
  unit: string;
  explanation: string;
};

export type GuardrailPolicyReport = {
  audit_hash: string;
  symbol: string;
  scenario: string;
  generated_at: string;
  verdict: "compliant" | "needs_review" | "blocked";
  execution_allowed: boolean;
  summary: string;
  checks: GuardrailPolicyCheck[];
  suggested_actions: string[];
  policy: GuardrailPolicyRequest;
};

export type PolicyStressOutcome = {
  name: string;
  stance: "access_first" | "balanced" | "strict";
  purpose: string;
  report: GuardrailPolicyReport;
  pass_count: number;
  watch_count: number;
  block_count: number;
  first_breaking_check: string | null;
};

export type PolicyStressReport = {
  audit_hash: string;
  symbol: string;
  scenario: string;
  generated_at: string;
  resilience_verdict: "stable_greenlight" | "fragile_greenlight" | "needs_review" | "protective_lockdown";
  stability_score: number;
  execution_allowed_count: number;
  blocked_policy_count: number;
  summary: string;
  outcomes: PolicyStressOutcome[];
  fragile_checks: string[];
  judge_takeaway: string;
  recommended_next_steps: string[];
};

export type CounterfactualLever = {
  name: string;
  lever_type: "fairness" | "hidden_cost" | "anomaly" | "liquidity" | "leverage" | "stop_risk" | "core_gate";
  status: "already_clear" | "improvement_needed" | "non_bypassable";
  current_value: number | string;
  target_value: number | string;
  unit: string;
  improvement_required: number | null;
  direction: "increase" | "decrease" | "hold" | "fresh_audit_required";
  retail_impact: string;
  explanation: string;
};

export type CounterfactualFairnessReport = {
  audit_hash: string;
  symbol: string;
  scenario: string;
  generated_at: string;
  verdict: "already_fair" | "improvable" | "fresh_audit_required" | "do_not_unlock";
  unlockable_in_current_audit: boolean;
  readiness_score: number;
  summary: string;
  top_blocker: string;
  levers: CounterfactualLever[];
  non_bypassable_constraints: string[];
  recommended_next_steps: string[];
  judge_takeaway: string;
};

export type ExecutionRouteCandidate = {
  name: string;
  route_type: "market" | "post_only_limit" | "twap" | "maker_ladder" | "hold";
  status: "recommended" | "available" | "watch" | "locked";
  expected_slippage_bps: number;
  fill_probability: number;
  information_leakage_score: number;
  manipulation_exposure_score: number;
  retail_fairness_score: number;
  max_notional_usdt: number;
  time_to_complete_seconds: number;
  reason: string;
  safeguards: string[];
};

export type FairExecutionRouterReport = {
  audit_hash: string;
  symbol: string;
  scenario: string;
  generated_at: string;
  verdict: "route_ready" | "route_with_caution" | "paper_only_locked" | "no_fair_route";
  execution_permitted: boolean;
  recommended_route: string;
  summary: string;
  fairness_floor_score: number;
  liquidity_budget_usdt: number;
  max_route_notional_usdt: number;
  route_candidates: ExecutionRouteCandidate[];
  locked_reasons: string[];
  verification_notes: string[];
  judge_takeaway: string;
};

export type RedTeamProbe = {
  name: string;
  attack_vector:
    | "liquidity_withdrawal"
    | "spoofed_imbalance"
    | "volatility_cascade"
    | "funding_squeeze"
    | "oracle_gap";
  severity: "moderate" | "high" | "critical";
  status: AgentStatus;
  stressed_hidden_cost_bps: number;
  stressed_anomaly_score: number;
  stressed_liquidity_score: number;
  stressed_stop_hit_probability: number;
  stressed_impact_25k_bps: number;
  first_trigger: string;
  retail_harm: string;
  mitigation: string;
  explanation: string;
};

export type RedTeamReport = {
  audit_hash: string;
  symbol: string;
  scenario: string;
  generated_at: string;
  verdict: "resilient" | "watchlist" | "kill_switch_ready" | "already_locked";
  integrity_score: number;
  baseline_gate: string;
  summary: string;
  probes: RedTeamProbe[];
  blocked_probe_count: number;
  watch_probe_count: number;
  worst_probe: string;
  kill_switches: string[];
  judge_takeaway: string;
  recommended_next_steps: string[];
};

export type EvidencePackClaim = {
  label: string;
  status: "verified" | "watch" | "blocked";
  evidence_url: string;
  explanation: string;
};

export type AuditEvidencePack = {
  audit_hash: string;
  symbol: string;
  scenario: string;
  generated_at: string;
  package_version: string;
  headline: string;
  summary: string;
  verification_score: number;
  key_metrics: Record<string, string | number | boolean>;
  evidence_urls: Record<string, string>;
  included_reports: string[];
  core_claims: EvidencePackClaim[];
  decision: Decision;
  fairness_receipt: FairnessReceipt;
  retail_cohorts: RetailCohortReport;
  anchor_proof: AnchorProof;
  judge_brief: JudgeBrief;
  model_provenance: ModelProvenanceCard;
  fair_execution_router: FairExecutionRouterReport;
  counterfactuals: CounterfactualFairnessReport;
  policy_stress: PolicyStressReport;
  red_team: RedTeamReport;
  verifier_notes: string[];
  limitations: string[];
};

export type FairnessReceiptMetric = {
  label: string;
  value: string;
  status: AgentStatus | "info";
  explanation: string;
};

export type FairnessReceipt = {
  audit_hash: string;
  symbol: string;
  category: string;
  scenario: string;
  generated_at: string;
  decision_status: DecisionStatus;
  final_action: "LONG" | "SHORT" | "NO_TRADE";
  public_summary: string;
  retail_verdict: string;
  bga_alignment_score: number;
  metrics: FairnessReceiptMetric[];
  agent_concerns: string[];
  retail_protections: string[];
  verification_steps: string[];
  machine_readable_url: string;
  disclaimer: string;
};

export type RetailCohortProfile = {
  name: string;
  account_equity_usdt: number;
  risk_budget_pct: number;
  max_notional_pct: number;
};

export type RetailCohortResult = {
  profile: RetailCohortProfile;
  status: AgentStatus;
  executable: boolean;
  recommended_notional_usdt: number;
  estimated_margin_usdt: number;
  hidden_cost_usdt: number;
  hidden_cost_pct_equity: number;
  max_loss_usdt: number;
  max_loss_pct_equity: number;
  buying_power_used_pct: number;
  stop_distance_pct: number | null;
  friction_score: number;
  notes: string[];
};

export type RetailCohortReport = {
  audit_hash: string;
  symbol: string;
  category: string;
  scenario: string;
  generated_at: string;
  verdict: "inclusive" | "limited" | "exclusionary";
  summary: string;
  pass_count: number;
  watch_count: number;
  block_count: number;
  cohorts: RetailCohortResult[];
  fairness_warnings: string[];
};

export type ImpactLedgerIssue = {
  label: string;
  count: number;
  severity: "info" | "watch" | "block";
  examples: string[];
};

export type ImpactLedgerReport = {
  generated_at: string;
  audit_count: number;
  approved_count: number;
  observe_count: number;
  blocked_count: number;
  no_trade_count: number;
  manipulation_alert_count: number;
  cohort_inclusive_count: number;
  cohort_limited_count: number;
  cohort_exclusionary_count: number;
  estimated_hidden_cost_saved_usdt: number;
  average_fairness_score: number;
  average_hidden_cost_bps: number;
  average_liquidity_score: number;
  bga_ethos_score: number;
  summary: string;
  issues: ImpactLedgerIssue[];
  recent_audit_hashes: string[];
};

export type AnchorProof = {
  audit_hash: string;
  decision_hash_bytes32: string;
  symbol: string;
  action: "LONG" | "SHORT" | "NO_TRADE";
  scenario: string;
  status: DecisionStatus;
  generated_at: string;
  contract_name: string;
  contract_file: string;
  function_signature: string;
  metadata_uri: string;
  audit_url: string;
  receipt_url: string;
  payload_hash: string;
  calldata_preview: string;
  contract_arguments: Record<string, string>;
  metadata: Record<string, string | number | boolean>;
  safety_notes: string[];
  verification_steps: string[];
};

export type JudgeBriefRubricItem = {
  category: "bga_ethos" | "technical_depth" | "risk_management" | "transparency";
  score: number;
  headline: string;
  evidence: string[];
  demo_cue: string;
};

export type JudgeBriefStep = {
  step: number;
  title: string;
  script: string;
  evidence_url: string | null;
  proof_point: string;
};

export type JudgeBrief = {
  audit_hash: string;
  symbol: string;
  scenario: string;
  generated_at: string;
  one_sentence_pitch: string;
  judge_thesis: string;
  recommended_opening: string;
  total_demo_minutes: number;
  rubric: JudgeBriefRubricItem[];
  demo_steps: JudgeBriefStep[];
  safety_boundaries: string[];
  likely_questions: string[];
  proof_links: string[];
};

export type HackathonReadinessCriterion = {
  category: "bga_ethos" | "technical_depth" | "risk_management" | "transparency";
  max_points: number;
  readiness_score: number;
  status: "ready" | "watch" | "gap";
  headline: string;
  evidence: string[];
  proof_urls: string[];
  judge_angle: string;
  remaining_risks: string[];
};

export type HackathonRunbookStep = {
  step: number;
  title: string;
  ui_action: string;
  expected_result: string;
  underlying_mechanism: string;
  proof_url: string | null;
  judge_script: string;
  criteria: Array<"bga_ethos" | "technical_depth" | "risk_management" | "transparency">;
};

export type HackathonReadinessReport = {
  audit_hash: string;
  symbol: string;
  scenario: string;
  generated_at: string;
  verdict: "demo_ready" | "needs_review" | "blocked_demo";
  readiness_score: number;
  summary: string;
  recommended_demo_minutes: number;
  criteria: HackathonReadinessCriterion[];
  runbook_steps: HackathonRunbookStep[];
  strongest_claims: string[];
  known_limitations: string[];
  final_30_second_pitch: string;
  proof_links: string[];
};

export type SubmissionVideoSegment = {
  slide: number;
  timecode: string;
  title: string;
  narration: string;
  dashboard_action: string;
  proof_url: string | null;
};

export type SubmissionAsset = {
  label: string;
  path: string;
  purpose: string;
  required: boolean;
};

export type SubmissionChecklistItem = {
  label: string;
  status: "ready" | "watch";
  evidence: string;
};

export type HackathonSubmissionKit = {
  audit_hash: string;
  symbol: string;
  scenario: string;
  generated_at: string;
  headline: string;
  total_runtime_seconds: number;
  opening_hook: string;
  video_segments: SubmissionVideoSegment[];
  submission_assets: SubmissionAsset[];
  final_checklist: SubmissionChecklistItem[];
  copy_block: string;
  proof_links: string[];
};

export type ProvenanceDataSource = {
  name: string;
  source_type: "live_public_api" | "deterministic_fallback" | "derived" | "session_memory";
  status: "active" | "fallback" | "derived";
  fields: string[];
  caveat: string;
};

export type ModelComponentCard = {
  name: string;
  component_type: "ml_signal" | "heuristic_agent" | "risk_model" | "execution_guard" | "audit_infrastructure";
  version: string;
  inputs: string[];
  outputs: string[];
  limitations: string[];
  validation: string;
};

export type ModelProvenanceCard = {
  audit_hash: string;
  symbol: string;
  scenario: string;
  generated_at: string;
  provenance_score: number;
  summary: string;
  data_sources: ProvenanceDataSource[];
  model_components: ModelComponentCard[];
  feature_groups: string[];
  known_limitations: string[];
  validation_artifacts: string[];
  reproducibility_steps: string[];
  ethical_boundaries: string[];
};

export type AgentTask = {
  agent: string;
  objective: string;
  tool: string;
  status: "complete" | "watch" | "blocked";
  confidence: number;
  finding: string;
  evidence: string[];
};

export type AgentAction = {
  label: string;
  action_type:
    | "refresh_market"
    | "compare_scenarios"
    | "size_position"
    | "paper_execute"
    | "hold"
    | "review_audit"
    | "reset_portfolio";
  priority: "low" | "medium" | "high" | "critical";
  permitted: boolean;
  reason: string;
};

export type AgentMission = {
  id: string;
  symbol: string;
  category: string;
  scenario: string;
  generated_at: string;
  autonomy_level: "advisory" | "guarded_paper";
  final_recommendation: string;
  can_execute: boolean;
  decision: Decision;
  portfolio: PaperPortfolio;
  tasks: AgentTask[];
  action_queue: AgentAction[];
  memory_notes: string[];
  risk_register: string[];
};

export type WatchlistItem = {
  symbol: string;
  category: string;
  scenario: string;
  price: number;
  status: DecisionStatus;
  final_action: "LONG" | "SHORT" | "NO_TRADE";
  fairness_score: number;
  liquidity_score: number;
  anomaly_score: number;
  rank_score: number;
  audit_hash: string;
  summary: string;
  rank_reason: string;
};

export type WatchlistReport = {
  symbols: string[];
  category: string;
  scenario: string;
  generated_at: string;
  safest_symbol: string | null;
  items: WatchlistItem[];
};

export type DecisionRequest = {
  symbol: string;
  scenario: Scenario;
  category?: "spot" | "linear" | "inverse";
};

export type AgentMissionRequest = DecisionRequest & {
  auditHash?: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);

  if (!response.ok) {
    let detail = `API returned ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      // Keep the status-based fallback for non-JSON errors.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export function fetchDecision({ symbol, category = "linear", scenario }: DecisionRequest): Promise<Decision> {
  const params = new URLSearchParams({ symbol, category, scenario });
  return requestJson<Decision>(`/api/analysis?${params.toString()}`);
}

export function fetchScenarioComparison(symbol: string, includeLive = false): Promise<ScenarioComparison> {
  const params = new URLSearchParams({ symbol, category: "linear", include_live: String(includeLive) });
  return requestJson<ScenarioComparison>(`/api/compare?${params.toString()}`);
}

export function fetchMarketSeries({ symbol, category = "linear", scenario }: DecisionRequest): Promise<MarketSeries> {
  const params = new URLSearchParams({ symbol, category, scenario });
  return requestJson<MarketSeries>(`/api/market/series?${params.toString()}`);
}

export function fetchAudits(): Promise<Decision[]> {
  return requestJson<Decision[]>("/api/audits");
}

export function fetchFairnessReceipt(auditHash: string): Promise<FairnessReceipt> {
  return requestJson<FairnessReceipt>(`/api/audits/${auditHash}/receipt`);
}

export function fetchRetailCohorts(auditHash: string): Promise<RetailCohortReport> {
  return requestJson<RetailCohortReport>(`/api/audits/${auditHash}/retail-cohorts`);
}

export function fetchImpactLedger(limit = 50): Promise<ImpactLedgerReport> {
  const params = new URLSearchParams({ limit: String(limit) });
  return requestJson<ImpactLedgerReport>(`/api/impact?${params.toString()}`);
}

export function fetchAnchorProof(auditHash: string): Promise<AnchorProof> {
  return requestJson<AnchorProof>(`/api/audits/${auditHash}/anchor-proof`);
}

export function fetchJudgeBrief(auditHash: string): Promise<JudgeBrief> {
  return requestJson<JudgeBrief>(`/api/audits/${auditHash}/judge-brief`);
}

export function fetchHackathonReadiness(auditHash: string): Promise<HackathonReadinessReport> {
  return requestJson<HackathonReadinessReport>(`/api/audits/${auditHash}/hackathon-readiness`);
}

export function fetchSubmissionKit(auditHash: string): Promise<HackathonSubmissionKit> {
  return requestJson<HackathonSubmissionKit>(`/api/audits/${auditHash}/submission-kit`);
}

export function fetchModelProvenance(auditHash: string): Promise<ModelProvenanceCard> {
  return requestJson<ModelProvenanceCard>(`/api/audits/${auditHash}/model-provenance`);
}

export function fetchPolicyStress(auditHash: string): Promise<PolicyStressReport> {
  return requestJson<PolicyStressReport>(`/api/audits/${auditHash}/policy-stress`);
}

export function fetchCounterfactuals(auditHash: string): Promise<CounterfactualFairnessReport> {
  return requestJson<CounterfactualFairnessReport>(`/api/audits/${auditHash}/counterfactuals`);
}

export function fetchExecutionRouter(auditHash: string): Promise<FairExecutionRouterReport> {
  return requestJson<FairExecutionRouterReport>(`/api/audits/${auditHash}/execution-router`);
}

export function fetchRedTeamReport(auditHash: string): Promise<RedTeamReport> {
  return requestJson<RedTeamReport>(`/api/audits/${auditHash}/red-team`);
}

export function fetchEvidencePack(auditHash: string): Promise<AuditEvidencePack> {
  return requestJson<AuditEvidencePack>(`/api/audits/${auditHash}/evidence-pack`);
}

export function fetchPaperPortfolio(scenario: Scenario): Promise<PaperPortfolio> {
  const params = new URLSearchParams({ scenario });
  return requestJson<PaperPortfolio>(`/api/portfolio?${params.toString()}`);
}

export function resetPaperPortfolio(): Promise<PaperPortfolio> {
  return requestJson<PaperPortfolio>("/api/portfolio/reset", { method: "POST" });
}

export function simulatePaperOrder(auditHash: string): Promise<PaperOrder> {
  return requestJson<PaperOrder>("/api/orders/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ audit_hash: auditHash })
  });
}

export function calculateRiskSize(request: RiskSizingRequest): Promise<RiskSizing> {
  return requestJson<RiskSizing>("/api/risk/size", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });
}

export function evaluatePolicy(request: GuardrailPolicyRequest): Promise<GuardrailPolicyReport> {
  return requestJson<GuardrailPolicyReport>("/api/policy/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });
}

export function runAgentMission({ symbol, category = "linear", scenario, auditHash }: AgentMissionRequest): Promise<AgentMission> {
  const params = new URLSearchParams({ symbol, category, scenario });
  if (auditHash) params.set("audit_hash", auditHash);
  return requestJson<AgentMission>(`/api/agents/mission?${params.toString()}`);
}

export function fetchWatchlist(symbols: string[], scenario: Scenario, category = "linear"): Promise<WatchlistReport> {
  const params = new URLSearchParams({ symbols: symbols.join(","), category, scenario });
  return requestJson<WatchlistReport>(`/api/watchlist?${params.toString()}`);
}
