"use client";

import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bot,
  BrainCircuit,
  Calculator,
  CheckCircle2,
  Clipboard,
  Database,
  FileText,
  Film,
  Gauge,
  History,
  Layers3,
  LineChart,
  PauseCircle,
  Play,
  RefreshCw,
  Route,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  XCircle
} from "lucide-react";
import type { CSSProperties, PointerEvent, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  calculateRiskSize,
  evaluatePolicy,
  fetchAudits,
  fetchAnchorProof,
  fetchCounterfactuals,
  fetchDecision,
  fetchEvidencePack,
  fetchExecutionRouter,
  fetchFairnessReceipt,
  fetchHackathonReadiness,
  fetchImpactLedger,
  fetchJudgeBrief,
  fetchMarketSeries,
  fetchModelProvenance,
  fetchPaperPortfolio,
  fetchPolicyStress,
  fetchRedTeamReport,
  fetchRetailCohorts,
  fetchScenarioComparison,
  fetchSubmissionKit,
  fetchWatchlist,
  resetPaperPortfolio,
  runAgentMission,
  simulatePaperOrder
} from "@/lib/fairflow-api";
import type {
  Agent,
  AgentAction,
  AgentMission,
  AgentTask,
  AgentStatus,
  AnchorProof,
  AuditEvidencePack,
  Candle,
  CounterfactualFairnessReport,
  Decision,
  DecisionStatus,
  DecisionTraceStep,
  FairnessPassport,
  FairExecutionRouterReport,
  FairnessReceipt,
  GuardrailPolicyReport,
  GuardrailPolicyRequest,
  HackathonReadinessReport,
  HackathonSubmissionKit,
  ImpactLedgerReport,
  JudgeBrief,
  JudgeBriefRubricItem,
  MarketSeries,
  ModelProvenanceCard,
  ModelComponentCard,
  PaperOrder,
  PaperPortfolio,
  PolicyStressReport,
  RedTeamReport,
  RetailCohortReport,
  RetailCohortResult,
  RiskSizing,
  Scenario,
  ScenarioComparison,
  Stress,
  WatchlistItem,
  WatchlistReport
} from "@/lib/fairflow-api";

const scenarios: { label: string; value: Scenario }[] = [
  { label: "Live", value: "live" },
  { label: "Calm", value: "calm" },
  { label: "Volatile", value: "volatile" },
  { label: "Manipulated", value: "manipulated" }
];

const cryptoUniverse = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "LINKUSDT", "ADAUSDT", "DOGEUSDT"];
const defaultWatchlistSymbols = cryptoUniverse.slice(0, 8);

function formatNumber(value: number, digits = 2) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }).format(value);
}

function formatUsd(value: number, digits = 0) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }).format(value);
}

function formatPercent(value: number, digits = 0) {
  return `${formatNumber(value * 100, digits)}%`;
}

function titleize(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusIcon(status: AgentStatus | DecisionStatus) {
  if (status === "approved" || status === "pass") return <CheckCircle2 size={18} />;
  if (status === "blocked" || status === "block") return <XCircle size={18} />;
  return <AlertTriangle size={18} />;
}

function statusLabel(status: AgentStatus | DecisionStatus) {
  if (status === "approved") return "Approved";
  if (status === "blocked") return "Blocked";
  if (status === "observe") return "Observe";
  if (status === "pass") return "Pass";
  if (status === "watch") return "Watch";
  return "Block";
}

function receiptStatusLabel(status: FairnessReceipt["metrics"][number]["status"]) {
  if (status === "info") return "Info";
  return statusLabel(status);
}

function receiptTone(status: FairnessReceipt["metrics"][number]["status"]): "good" | "warn" | "bad" | "neutral" {
  if (status === "pass") return "good";
  if (status === "watch") return "warn";
  if (status === "block") return "bad";
  return "neutral";
}

function cohortVerdictLabel(verdict: RetailCohortReport["verdict"]) {
  if (verdict === "inclusive") return "Inclusive";
  if (verdict === "limited") return "Limited";
  return "Exclusionary";
}

function cohortVerdictTone(verdict: RetailCohortReport["verdict"]): "good" | "warn" | "bad" {
  if (verdict === "inclusive") return "good";
  if (verdict === "limited") return "warn";
  return "bad";
}

function verdictLabel(verdict: FairnessPassport["verdict"]) {
  if (verdict === "fair_to_execute") return "Fair to execute";
  if (verdict === "wait_for_parity") return "Wait for parity";
  return "Unfair to retail";
}

function verdictTone(verdict: FairnessPassport["verdict"]): "good" | "warn" | "bad" {
  if (verdict === "fair_to_execute") return "good";
  if (verdict === "wait_for_parity") return "warn";
  return "bad";
}

function statusTone(status: AgentStatus | DecisionStatus): "good" | "warn" | "bad" {
  if (status === "approved" || status === "pass") return "good";
  if (status === "blocked" || status === "block") return "bad";
  return "warn";
}

function missionStatusIcon(status: AgentTask["status"]) {
  if (status === "complete") return <CheckCircle2 size={17} />;
  if (status === "blocked") return <XCircle size={17} />;
  return <AlertTriangle size={17} />;
}

function missionStatusLabel(status: AgentTask["status"]) {
  if (status === "complete") return "Complete";
  if (status === "blocked") return "Blocked";
  return "Watch";
}

function missionStatusTone(status: AgentTask["status"]): "good" | "warn" | "bad" {
  if (status === "complete") return "good";
  if (status === "blocked") return "bad";
  return "warn";
}

function actionIcon(actionType: AgentAction["action_type"]) {
  if (actionType === "refresh_market") return <RefreshCw size={16} />;
  if (actionType === "compare_scenarios") return <Layers3 size={16} />;
  if (actionType === "size_position") return <Calculator size={16} />;
  if (actionType === "paper_execute") return <Play size={16} />;
  if (actionType === "review_audit") return <Clipboard size={16} />;
  if (actionType === "reset_portfolio") return <Database size={16} />;
  return <PauseCircle size={16} />;
}

function sparkPath(values: number[], width = 260, height = 86) {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

function MetricTile({
  label,
  value,
  tone,
  detail,
  className
}: {
  label: string;
  value: string;
  tone?: "good" | "warn" | "bad";
  detail?: string;
  className?: string;
}) {
  return (
    <div className={`metric-tile ${tone ?? ""} ${className ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

function DecisionBadge({ decision }: { decision: Decision }) {
  return (
    <div className={`decision-badge ${decision.status}`}>
      {statusIcon(decision.status)}
      <span>{statusLabel(decision.status)}</span>
    </div>
  );
}

function AgentCard({ agent }: { agent: Agent }) {
  return (
    <article className={`agent-card ${agent.status}`}>
      <header>
        <div>
          <span className="agent-name">{agent.name}</span>
          <strong>{agent.verdict}</strong>
        </div>
        <div className="agent-score">{Math.round(agent.score)}</div>
      </header>
      <div className="agent-status">
        {statusIcon(agent.status)}
        <span>{statusLabel(agent.status)}</span>
      </div>
      <ul>
        {agent.rationale.slice(0, 3).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </article>
  );
}

function missionAsAgentStatus(status: AgentTask["status"]): AgentStatus {
  if (status === "complete") return "pass";
  if (status === "blocked") return "block";
  return "watch";
}

function agentRole(name: string) {
  if (name.includes("Regime")) return "Market regime";
  if (name.includes("Strategy")) return "Trade thesis";
  if (name.includes("Manipulation") || name.includes("Sentinel")) return "Anomaly defense";
  if (name.includes("Risk")) return "Risk gate";
  if (name.includes("Forecast")) return "Uncertainty";
  if (name.includes("Execution")) return "Route planner";
  if (name.includes("Backtest")) return "Evidence replay";
  if (name.includes("Memory")) return "Session memory";
  if (name.includes("Audit")) return "Explainability";
  return "Specialist agent";
}

function AgentSwarmCard({
  name,
  role,
  status,
  score,
  detail,
  source
}: {
  name: string;
  role: string;
  status: AgentStatus;
  score: number;
  detail: string;
  source: string;
}) {
  return (
    <article className={`swarm-agent ${status}`}>
      <header>
        <div className="swarm-avatar">
          <Bot size={17} />
        </div>
        <div>
          <span>{source}</span>
          <strong>{name}</strong>
        </div>
        <div className="swarm-score">{Math.round(score)}</div>
      </header>
      <p>{detail}</p>
      <div className={`swarm-status ${status}`}>
        {statusIcon(status)}
        <span>{statusLabel(status)}</span>
      </div>
      <small>{role}</small>
    </article>
  );
}

function AgentSwarmPanel({
  decision,
  mission,
  loading,
  onRunMission
}: {
  decision: Decision;
  mission: AgentMission | null;
  loading: boolean;
  onRunMission: () => void;
}) {
  const missionTasks = mission?.tasks ?? [];
  const allStatuses = [...decision.agents.map((agent) => agent.status), ...missionTasks.map((task) => missionAsAgentStatus(task.status))];
  const passCount = allStatuses.filter((status) => status === "pass").length;
  const watchCount = allStatuses.filter((status) => status === "watch").length;
  const blockCount = allStatuses.filter((status) => status === "block").length;

  return (
    <section className="panel agent-swarm-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <Bot size={20} />
          <h2>Active agents</h2>
        </div>
        <button className="icon-button small" onClick={onRunMission} disabled={loading} data-testid="swarm-run-mission">
          <BrainCircuit size={16} />
          <span>{loading ? "Planning" : mission ? "Re-run mission" : "Run mission"}</span>
        </button>
      </header>

      <div className="swarm-stats">
        <DecisionStat label="Report agents" value={String(decision.agents.length)} />
        <DecisionStat label="Mission agents" value={mission ? String(mission.tasks.length) : "Pending"} tone={mission ? "good" : "warn"} />
        <DecisionStat label="Passing" value={String(passCount)} tone="good" />
        <DecisionStat label="Watch / Block" value={`${watchCount}/${blockCount}`} tone={blockCount ? "bad" : watchCount ? "warn" : "good"} />
      </div>

      <div className="agent-lanes">
        <div className="agent-lane">
          <div className="mini-heading">
            <span>Report specialists</span>
            <strong>{decision.agents.length}</strong>
          </div>
          <div className="agent-strip" aria-label="Report specialist agents">
            {decision.agents.map((agent) => (
              <AgentSwarmCard
                key={agent.name}
                name={agent.name}
                role={agentRole(agent.name)}
                status={agent.status}
                score={agent.score}
                detail={agent.verdict}
                source="Audit"
              />
            ))}
          </div>
        </div>

        <div className="agent-lane">
          <div className="mini-heading">
            <span>Mission specialists</span>
            <strong>{mission ? mission.tasks.length : 0}</strong>
          </div>
          {mission ? (
            <div className="agent-strip" aria-label="Mission specialist agents">
              {mission.tasks.map((task) => (
                <AgentSwarmCard
                  key={task.agent}
                  name={task.agent}
                  role={task.objective}
                  status={missionAsAgentStatus(task.status)}
                  score={task.confidence * 100}
                  detail={task.finding}
                  source="Mission"
                />
              ))}
            </div>
          ) : (
            <div className="empty-state compact-empty">
              <RefreshCw size={18} className={loading ? "spin" : ""} />
              <span>{loading ? "Spinning up mission agents" : "Mission agents appear after the first mission run"}</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function WatchlistCard({
  item,
  rank,
  active,
  onOpen
}: {
  item: WatchlistItem;
  rank: number;
  active: boolean;
  onOpen: (item: WatchlistItem) => void;
}) {
  const tone = item.status === "approved" ? "good" : item.status === "blocked" ? "bad" : "warn";
  const anomalyTone = item.anomaly_score < 35 ? "good" : item.anomaly_score < 65 ? "warn" : "bad";

  return (
    <article className={`watchlist-card ${item.status} ${active ? "active" : ""}`}>
      <header>
        <div className="watchlist-rank">#{rank}</div>
        <div>
          <span>{titleize(item.scenario)} scanner</span>
          <strong>{item.symbol}</strong>
        </div>
        <div className={`audit-status ${item.status}`}>{statusLabel(item.status)}</div>
      </header>

      <div className="watchlist-price">
        <span>{item.final_action.replace("_", " ")}</span>
        <strong>{formatUsd(item.price, 2)}</strong>
      </div>

      <div className="watchlist-meters">
        <MiniMeter label="Fairness" value={item.fairness_score} tone={tone} />
        <MiniMeter label="Liquidity" value={item.liquidity_score} tone={item.liquidity_score > 70 ? "good" : item.liquidity_score > 45 ? "warn" : "bad"} />
        <MiniMeter label="Anomaly" value={item.anomaly_score} tone={anomalyTone} />
      </div>

      <p>{item.rank_reason}</p>

      <footer>
        <code>{item.audit_hash.slice(0, 12)}</code>
        <button className="mini-button" onClick={() => onOpen(item)} data-testid={`open-watchlist-${item.symbol}`}>
          Open
        </button>
      </footer>
    </article>
  );
}

function WatchlistScannerPanel({
  report,
  loading,
  activeSymbol,
  selectedSymbols,
  universe,
  onRefresh,
  onOpen,
  onToggleSymbol
}: {
  report: WatchlistReport | null;
  loading: boolean;
  activeSymbol: string;
  selectedSymbols: string[];
  universe: string[];
  onRefresh: () => void;
  onOpen: (item: WatchlistItem) => void;
  onToggleSymbol: (symbol: string) => void;
}) {
  const averageFairness = report?.items.length
    ? report.items.reduce((total, item) => total + item.fairness_score, 0) / report.items.length
    : 0;

  return (
    <section className="panel watchlist-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <LineChart size={20} />
          <h2>Agent watchlist scanner</h2>
        </div>
        <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="refresh-watchlist">
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          <span>{loading ? "Scanning" : "Scan"}</span>
        </button>
      </header>

      <div className="watchlist-stats">
        <DecisionStat label="Safest" value={report?.safest_symbol ?? "--"} tone={report?.safest_symbol ? "good" : "warn"} />
        <DecisionStat label="Symbols" value={report ? `${report.items.length}/${universe.length}` : `${selectedSymbols.length}/${universe.length}`} />
        <DecisionStat label="Avg fairness" value={report ? `${Math.round(averageFairness)}/100` : "--"} />
        <DecisionStat label="Scenario" value={report ? titleize(report.scenario) : "Pending"} />
      </div>

      <div className="watchlist-selector" aria-label="Crypto watchlist selector">
        {universe.map((item) => {
          const selected = selectedSymbols.includes(item);
          return (
            <button
              key={item}
              className={selected ? "selected" : ""}
              onClick={() => onToggleSymbol(item)}
              aria-pressed={selected}
              data-testid={`toggle-watchlist-${item}`}
            >
              {item.replace("USDT", "")}
            </button>
          );
        })}
      </div>

      {report ? (
        <div className="watchlist-grid">
          {report.items.map((item, index) => (
            <WatchlistCard
              key={item.audit_hash}
              item={item}
              rank={index + 1}
              active={item.symbol === activeSymbol}
              onOpen={onOpen}
            />
          ))}
        </div>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Agents are scanning the watchlist" : "Run a scan to rank markets by fairness and safety"}</span>
        </div>
      )}
    </section>
  );
}

function GaugeBar({ label, value, invert = false }: { label: string; value: number; invert?: boolean }) {
  const clamped = Math.max(0, Math.min(100, value));
  const bad = invert ? clamped > 65 : clamped < 45;
  const warn = invert ? clamped > 35 && clamped <= 65 : clamped >= 45 && clamped < 70;
  return (
    <div className="gauge-row">
      <div className="gauge-label">
        <span>{label}</span>
        <strong>{Math.round(clamped)}</strong>
      </div>
      <div className="gauge-track">
        <div className={`gauge-fill ${bad ? "bad" : warn ? "warn" : "good"}`} style={{ width: `${clamped}%` }} />
      </div>
    </div>
  );
}

function SignalCard({
  icon,
  label,
  value,
  detail,
  tone = "neutral"
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone?: "good" | "warn" | "bad" | "neutral";
}) {
  return (
    <article className={`signal-card ${tone}`}>
      <div className="signal-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

function FairnessPassportPanel({ passport }: { passport: FairnessPassport }) {
  const tone = verdictTone(passport.verdict);
  const scoreStyle = { "--score": `${Math.round(passport.score)}%` } as CSSProperties;
  return (
    <section className={`panel fairness-panel ${tone}`}>
      <div className="fairness-hero">
        <div>
          <div className="panel-heading">
            <Shield size={20} />
            <h2>Fairness passport</h2>
          </div>
          <p>{passport.summary}</p>
        </div>
        <div className={`fairness-score ${tone}`} style={scoreStyle}>
          <div className="fairness-ring">
            <strong>{Math.round(passport.score)}</strong>
          </div>
          <div>
            <span>{verdictLabel(passport.verdict)}</span>
            <small>{formatNumber(passport.estimated_hidden_cost_bps, 1)} bps hidden-cost estimate</small>
          </div>
        </div>
      </div>

      <div className="fairness-grid">
        {passport.checks.map((check) => (
          <article key={check.name} className={`fairness-check ${check.status}`}>
            <header>
              <div>
                <span>{check.name}</span>
                <strong>{Math.round(check.score)}/100</strong>
              </div>
              <div className="agent-status">
                {statusIcon(check.status)}
                <span>{statusLabel(check.status)}</span>
              </div>
            </header>
            <p>{check.explanation}</p>
            <ul>
              {check.evidence.slice(0, 3).map((item, index) => (
                <li key={`${check.name}-${index}`}>{item}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>

      <div className="protection-strip">
        {passport.retail_protections.slice(0, 4).map((item) => (
          <div key={item}>
            <CheckCircle2 size={15} />
            <span>{item}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function FairnessReceiptPanel({
  receipt,
  loading,
  onRefresh
}: {
  receipt: FairnessReceipt | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const gateMetric = receipt?.metrics.find((metric) => metric.label === "Execution gate");
  const costMetric = receipt?.metrics.find((metric) => metric.label === "Hidden cost");
  const anomalyMetric = receipt?.metrics.find((metric) => metric.label === "Anomaly risk");
  const scoreTone = receipt ? statusTone(receipt.decision_status) : "warn";

  async function copyReceipt() {
    if (!receipt) return;
    await navigator.clipboard.writeText(JSON.stringify(receipt, null, 2));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <section className={`panel receipt-panel ${receipt?.decision_status ?? "pending"}`}>
      <header className="section-header">
        <div className="panel-heading compact">
          <Clipboard size={20} />
          <h2>Retail fairness receipt</h2>
        </div>
        <div className="section-actions">
          <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="receipt-refresh">
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            <span>{loading ? "Generating" : "Generate"}</span>
          </button>
          <button className="icon-button small" onClick={copyReceipt} disabled={!receipt} data-testid="receipt-copy">
            <Clipboard size={16} />
            <span>{copied ? "Copied" : "Copy JSON"}</span>
          </button>
        </div>
      </header>

      {receipt ? (
        <>
          <div className="receipt-hero">
            <div>
              <span className="eyebrow">{receipt.symbol} / {titleize(receipt.scenario)} / {receipt.final_action.replace("_", " ")}</span>
              <p>{receipt.public_summary}</p>
              <small>{receipt.retail_verdict}</small>
            </div>
            <div className={`receipt-score ${scoreTone}`}>
              <span>BGA alignment</span>
              <strong>{formatNumber(receipt.bga_alignment_score, 1)}</strong>
              <small>Fairness, anomaly safety, transparency, and gate discipline</small>
            </div>
          </div>

          <div className="receipt-stats">
            <DecisionStat label="Gate" value={gateMetric?.value ?? statusLabel(receipt.decision_status)} tone={statusTone(receipt.decision_status)} />
            <DecisionStat label="Hidden cost" value={costMetric?.value ?? "--"} tone={costMetric ? receiptTone(costMetric.status) as "good" | "warn" | "bad" : undefined} />
            <DecisionStat label="Anomaly risk" value={anomalyMetric?.value ?? "--"} tone={anomalyMetric ? receiptTone(anomalyMetric.status) as "good" | "warn" | "bad" : undefined} />
            <DecisionStat label="Audit" value={receipt.audit_hash.slice(0, 12)} />
          </div>

          <div className="receipt-grid">
            {receipt.metrics.map((metric) => (
              <article key={metric.label} className={`receipt-metric ${metric.status}`}>
                <header>
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                </header>
                <div className={`receipt-pill ${metric.status}`}>{receiptStatusLabel(metric.status)}</div>
                <p>{metric.explanation}</p>
              </article>
            ))}
          </div>

          <div className="receipt-columns">
            <div className="receipt-column">
              <div className="mini-heading">
                <span>Agent concerns</span>
                <strong>{receipt.agent_concerns.length}</strong>
              </div>
              <ul className="receipt-list">
                {receipt.agent_concerns.slice(0, 5).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="receipt-column">
              <div className="mini-heading">
                <span>Retail protections</span>
                <strong>{receipt.retail_protections.length}</strong>
              </div>
              <ul className="receipt-list">
                {receipt.retail_protections.slice(0, 5).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="receipt-column">
              <div className="mini-heading">
                <span>Verify</span>
                <strong>{receipt.verification_steps.length}</strong>
              </div>
              <ul className="receipt-list">
                {receipt.verification_steps.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>

          <footer className="receipt-footer">
            <code>{receipt.machine_readable_url}</code>
            <span>{receipt.disclaimer}</span>
          </footer>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Building a verifiable retail receipt" : "Generate a receipt for the current audit"}</span>
        </div>
      )}
    </section>
  );
}

function CohortMiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="cohort-mini-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function CohortCard({ cohort }: { cohort: RetailCohortResult }) {
  const tone = statusTone(cohort.status);
  return (
    <article className={`cohort-card ${cohort.status}`}>
      <header>
        <div>
          <span>{formatUsd(cohort.profile.account_equity_usdt)} account</span>
          <strong>{cohort.profile.name}</strong>
        </div>
        <div className={`receipt-pill ${cohort.status}`}>{statusLabel(cohort.status)}</div>
      </header>

      <div className="cohort-affordability">
        <div>
          <span>Friction score</span>
          <strong>{Math.round(cohort.friction_score)}</strong>
        </div>
        <MiniMeter label="Affordability" value={cohort.friction_score} tone={tone} />
      </div>

      <div className="cohort-metrics">
        <CohortMiniStat label="Notional" value={formatUsd(cohort.recommended_notional_usdt)} />
        <CohortMiniStat label="Margin" value={formatUsd(cohort.estimated_margin_usdt)} />
        <CohortMiniStat label="Max loss" value={`${formatUsd(cohort.max_loss_usdt)} / ${formatNumber(cohort.max_loss_pct_equity, 2)}%`} />
        <CohortMiniStat label="Hidden cost" value={`${formatUsd(cohort.hidden_cost_usdt, 2)} / ${formatNumber(cohort.hidden_cost_pct_equity, 3)}%`} />
      </div>

      <ul className="cohort-notes">
        {cohort.notes.slice(0, 3).map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </article>
  );
}

function RetailCohortPanel({
  report,
  loading,
  onRefresh
}: {
  report: RetailCohortReport | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const tone = report ? cohortVerdictTone(report.verdict) : "warn";
  return (
    <section className={`panel cohort-panel ${report?.verdict ?? "pending"}`}>
      <header className="section-header">
        <div className="panel-heading compact">
          <Users size={20} />
          <h2>Retail cohort simulator</h2>
        </div>
        <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="cohort-refresh">
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          <span>{loading ? "Testing" : "Test cohorts"}</span>
        </button>
      </header>

      {report ? (
        <>
          <div className="cohort-hero">
            <div>
              <span className="eyebrow">{report.symbol} / {titleize(report.scenario)} affordability ladder</span>
              <p>{report.summary}</p>
            </div>
            <div className={`cohort-verdict ${tone}`}>
              <span>Retail reach</span>
              <strong>{cohortVerdictLabel(report.verdict)}</strong>
              <small>{report.pass_count} pass / {report.watch_count} watch / {report.block_count} block</small>
            </div>
          </div>

          <div className="cohort-stats">
            <DecisionStat label="Pass" value={String(report.pass_count)} tone="good" />
            <DecisionStat label="Watch" value={String(report.watch_count)} tone={report.watch_count ? "warn" : "good"} />
            <DecisionStat label="Block" value={String(report.block_count)} tone={report.block_count ? "bad" : "good"} />
            <DecisionStat label="Audit" value={report.audit_hash.slice(0, 12)} />
          </div>

          <div className="cohort-grid">
            {report.cohorts.map((cohort) => (
              <CohortCard key={cohort.profile.name} cohort={cohort} />
            ))}
          </div>

          <div className="cohort-warnings">
            {report.fairness_warnings.slice(0, 4).map((warning) => (
              <div key={warning}>
                <Shield size={15} />
                <span>{warning}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Testing affordability across retail cohorts" : "Run the cohort simulator for the current audit"}</span>
        </div>
      )}
    </section>
  );
}

function ImpactLedgerPanel({
  report,
  loading,
  onRefresh
}: {
  report: ImpactLedgerReport | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const scoreTone = report
    ? report.bga_ethos_score >= 82
      ? "good"
      : report.bga_ethos_score >= 64
        ? "warn"
        : "bad"
    : "warn";
  return (
    <section className="panel impact-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <Database size={20} />
          <h2>Impact ledger</h2>
        </div>
        <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="impact-refresh">
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          <span>{loading ? "Auditing" : "Refresh"}</span>
        </button>
      </header>

      {report ? (
        <>
          <div className="impact-hero">
            <div>
              <span className="eyebrow">BGA ethos evidence</span>
              <p>{report.summary}</p>
            </div>
            <div className={`impact-score ${scoreTone}`}>
              <span>Ethos score</span>
              <strong>{formatNumber(report.bga_ethos_score, 1)}</strong>
              <small>Fairness, inclusion, cost, transparency, and unsafe-market gate discipline</small>
            </div>
          </div>

          <div className="impact-stats">
            <DecisionStat label="Audits" value={String(report.audit_count)} />
            <DecisionStat label="Blocked/no trade" value={`${report.blocked_count}/${report.no_trade_count}`} tone={report.no_trade_count ? "good" : "warn"} />
            <DecisionStat label="Manipulation alerts" value={String(report.manipulation_alert_count)} tone={report.manipulation_alert_count ? "good" : "warn"} />
            <DecisionStat label="Cost drag avoided" value={formatUsd(report.estimated_hidden_cost_saved_usdt, 2)} tone="good" />
            <DecisionStat label="Avg fairness" value={`${Math.round(report.average_fairness_score)}/100`} />
            <DecisionStat label="Avg hidden cost" value={`${formatNumber(report.average_hidden_cost_bps, 1)} bps`} />
          </div>

          <div className="impact-layout">
            <div className="impact-block">
              <div className="mini-heading">
                <span>Cohort outcomes</span>
                <strong>{report.cohort_inclusive_count + report.cohort_limited_count + report.cohort_exclusionary_count}</strong>
              </div>
              <div className="impact-bars">
                <div>
                  <span>Inclusive</span>
                  <strong>{report.cohort_inclusive_count}</strong>
                </div>
                <div>
                  <span>Limited</span>
                  <strong>{report.cohort_limited_count}</strong>
                </div>
                <div>
                  <span>Exclusionary</span>
                  <strong>{report.cohort_exclusionary_count}</strong>
                </div>
              </div>
            </div>

            <div className="impact-block issues">
              <div className="mini-heading">
                <span>Recurring issues</span>
                <strong>{report.issues.length}</strong>
              </div>
              <div className="impact-issue-list">
                {report.issues.slice(0, 5).map((issue) => (
                  <article key={issue.label} className={`impact-issue ${issue.severity}`}>
                    <div>
                      <strong>{issue.label}</strong>
                      <span>{issue.count} audit{issue.count === 1 ? "" : "s"}</span>
                    </div>
                    <p>{issue.examples[0] ?? "No example recorded"}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Summarizing audit history" : "Generate audits to populate the impact ledger"}</span>
        </div>
      )}
    </section>
  );
}

function AnchorProofPanel({
  proof,
  loading,
  onRefresh
}: {
  proof: AnchorProof | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const [copied, setCopied] = useState<"call" | "metadata" | null>(null);

  async function copyValue(kind: "call" | "metadata") {
    if (!proof) return;
    const value = kind === "call" ? proof.calldata_preview : JSON.stringify(proof.metadata, null, 2);
    await navigator.clipboard.writeText(value);
    setCopied(kind);
    window.setTimeout(() => setCopied(null), 1400);
  }

  return (
    <section className={`panel anchor-panel ${proof?.status ?? "pending"}`}>
      <header className="section-header">
        <div className="panel-heading compact">
          <Database size={20} />
          <h2>On-chain audit anchor</h2>
        </div>
        <div className="section-actions">
          <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="anchor-refresh">
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            <span>{loading ? "Preparing" : "Prepare"}</span>
          </button>
          <button className="icon-button small" onClick={() => copyValue("call")} disabled={!proof} data-testid="anchor-copy-call">
            <Clipboard size={16} />
            <span>{copied === "call" ? "Copied" : "Copy call"}</span>
          </button>
        </div>
      </header>

      {proof ? (
        <>
          <div className="anchor-hero">
            <div>
              <span className="eyebrow">{proof.contract_name} / {proof.function_signature}</span>
              <p>
                Anchor this audit hash to prove the FairFlow report existed before later market outcomes. The proof is paper-only and keeps the full reasoning available through the audit and receipt URLs.
              </p>
            </div>
            <div className="anchor-contract">
              <span>Decision hash</span>
              <strong>{proof.decision_hash_bytes32.slice(0, 18)}...</strong>
              <small>{proof.contract_file}</small>
            </div>
          </div>

          <div className="anchor-stats">
            <DecisionStat label="Symbol" value={proof.symbol} />
            <DecisionStat label="Action" value={proof.action.replace("_", " ")} tone={proof.action === "NO_TRADE" ? "good" : statusTone(proof.status)} />
            <DecisionStat label="Status" value={statusLabel(proof.status)} tone={statusTone(proof.status)} />
            <DecisionStat label="Payload hash" value={proof.payload_hash.slice(0, 12)} />
          </div>

          <div className="anchor-grid">
            <div className="anchor-block">
              <div className="mini-heading">
                <span>Contract call</span>
                <strong>Ready</strong>
              </div>
              <code>{proof.calldata_preview}</code>
            </div>
            <div className="anchor-block">
              <div className="mini-heading">
                <span>Metadata URI</span>
                <strong>Proof</strong>
              </div>
              <code>{proof.metadata_uri}</code>
              <button className="mini-button anchor-copy" onClick={() => copyValue("metadata")} data-testid="anchor-copy-metadata">
                <Clipboard size={14} />
                <span>{copied === "metadata" ? "Copied metadata" : "Copy metadata"}</span>
              </button>
            </div>
          </div>

          <div className="anchor-columns">
            <div className="anchor-column">
              <div className="mini-heading">
                <span>Safety notes</span>
                <strong>{proof.safety_notes.length}</strong>
              </div>
              <ul>
                {proof.safety_notes.slice(0, 4).map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
            <div className="anchor-column">
              <div className="mini-heading">
                <span>Verify</span>
                <strong>{proof.verification_steps.length}</strong>
              </div>
              <ul>
                {proof.verification_steps.slice(0, 4).map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Preparing contract-ready proof" : "Prepare an anchor proof for the current audit"}</span>
        </div>
      )}
    </section>
  );
}

function rubricLabel(category: JudgeBriefRubricItem["category"]) {
  if (category === "bga_ethos") return "BGA ethos";
  if (category === "technical_depth") return "Technical depth";
  if (category === "risk_management") return "Risk management";
  return "Transparency";
}

function rubricIcon(category: JudgeBriefRubricItem["category"]) {
  if (category === "bga_ethos") return <Shield size={17} />;
  if (category === "technical_depth") return <BrainCircuit size={17} />;
  if (category === "risk_management") return <Gauge size={17} />;
  return <Route size={17} />;
}

function JudgeModePanel({
  brief,
  loading,
  onRefresh
}: {
  brief: JudgeBrief | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copyPitch() {
    if (!brief) return;
    const script = [
      brief.one_sentence_pitch,
      "",
      brief.recommended_opening,
      "",
      ...brief.demo_steps.map((step) => `${step.step}. ${step.title}: ${step.script} Proof: ${step.proof_point}`)
    ].join("\n");
    await navigator.clipboard.writeText(script);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <section className="panel judge-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <Sparkles size={20} />
          <h2>Judge mode brief</h2>
        </div>
        <div className="section-actions">
          <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="judge-refresh">
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            <span>{loading ? "Briefing" : "Refresh"}</span>
          </button>
          <button className="icon-button small" onClick={copyPitch} disabled={!brief} data-testid="judge-copy">
            <Clipboard size={16} />
            <span>{copied ? "Copied" : "Copy pitch"}</span>
          </button>
        </div>
      </header>

      {brief ? (
        <>
          <div className="judge-hero">
            <div>
              <span className="eyebrow">{brief.symbol} / {titleize(brief.scenario)} / {formatNumber(brief.total_demo_minutes, 1)} minute demo</span>
              <p>{brief.one_sentence_pitch}</p>
              <small>{brief.judge_thesis}</small>
            </div>
            <div className="judge-opening">
              <span>Opening line</span>
              <strong>{brief.recommended_opening}</strong>
            </div>
          </div>

          <div className="judge-rubric-grid">
            {brief.rubric.map((item) => {
              const tone = item.score >= 82 ? "good" : item.score >= 65 ? "warn" : "bad";
              return (
                <article key={item.category} className={`judge-rubric ${tone}`}>
                  <header>
                    <div>
                      {rubricIcon(item.category)}
                      <span>{rubricLabel(item.category)}</span>
                    </div>
                    <strong>{Math.round(item.score)}</strong>
                  </header>
                  <h3>{item.headline}</h3>
                  <p>{item.demo_cue}</p>
                  <ul>
                    {item.evidence.slice(0, 2).map((evidence) => (
                      <li key={evidence}>{evidence}</li>
                    ))}
                  </ul>
                </article>
              );
            })}
          </div>

          <div className="judge-layout">
            <div className="judge-timeline">
              <div className="mini-heading">
                <span>3-minute path</span>
                <strong>{brief.demo_steps.length}</strong>
              </div>
              {brief.demo_steps.map((step) => (
                <article key={step.step} className="judge-step">
                  <div className="judge-step-index">{step.step}</div>
                  <div>
                    <strong>{step.title}</strong>
                    <p>{step.script}</p>
                    <small>{step.proof_point}</small>
                  </div>
                </article>
              ))}
            </div>

            <div className="judge-side">
              <div className="judge-box">
                <div className="mini-heading">
                  <span>Safety boundaries</span>
                  <strong>{brief.safety_boundaries.length}</strong>
                </div>
                <ul>
                  {brief.safety_boundaries.slice(0, 4).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div className="judge-box">
                <div className="mini-heading">
                  <span>Likely questions</span>
                  <strong>{brief.likely_questions.length}</strong>
                </div>
                <ul>
                  {brief.likely_questions.slice(0, 4).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Preparing judge narrative" : "Generate a rubric-aligned demo brief for this audit"}</span>
        </div>
      )}
    </section>
  );
}

function readinessVerdictLabel(verdict: HackathonReadinessReport["verdict"]) {
  if (verdict === "demo_ready") return "Demo ready";
  if (verdict === "needs_review") return "Needs review";
  return "Blocked demo";
}

function readinessTone(verdict: HackathonReadinessReport["verdict"]): "good" | "warn" | "bad" {
  if (verdict === "demo_ready") return "good";
  if (verdict === "needs_review") return "warn";
  return "bad";
}

function criterionTone(status: HackathonReadinessReport["criteria"][number]["status"]): "good" | "warn" | "bad" {
  if (status === "ready") return "good";
  if (status === "watch") return "warn";
  return "bad";
}

function HackathonReadinessPanel({
  report,
  loading,
  onRefresh
}: {
  report: HackathonReadinessReport | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const tone = report ? readinessTone(report.verdict) : "warn";

  async function copyRunbook() {
    if (!report) return;
    const text = [
      report.final_30_second_pitch,
      "",
      "Runbook:",
      ...report.runbook_steps.map((step) => `${step.step}. ${step.title}\nAction: ${step.ui_action}\nMechanism: ${step.underlying_mechanism}\nProof: ${step.proof_url ?? "live UI"}`)
    ].join("\n");
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <section className={`panel readiness-panel ${report?.verdict ?? ""}`}>
      <header className="section-header">
        <div className="panel-heading compact">
          <Target size={20} />
          <h2>Hackathon readiness</h2>
        </div>
        <div className="section-actions">
          <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="readiness-refresh">
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            <span>{loading ? "Scoring" : "Refresh"}</span>
          </button>
          <button className="icon-button small" onClick={copyRunbook} disabled={!report} data-testid="readiness-copy">
            <Clipboard size={16} />
            <span>{copied ? "Copied" : "Copy runbook"}</span>
          </button>
        </div>
      </header>

      {report ? (
        <>
          <div className="readiness-hero">
            <div>
              <span className="eyebrow">{report.symbol} / {titleize(report.scenario)} / {formatNumber(report.recommended_demo_minutes, 1)} minute path</span>
              <p>{report.summary}</p>
              <small>{report.final_30_second_pitch}</small>
            </div>
            <div className={`readiness-score ${tone}`}>
              <span>Readiness</span>
              <strong>{formatNumber(report.readiness_score, 1)}</strong>
              <small>{readinessVerdictLabel(report.verdict)}</small>
            </div>
          </div>

          <div className="readiness-criteria-grid">
            {report.criteria.map((item) => {
              const itemTone = criterionTone(item.status);
              return (
                <article key={item.category} className={`readiness-criterion ${itemTone}`}>
                  <header>
                    <div>
                      {rubricIcon(item.category)}
                      <span>{rubricLabel(item.category)}</span>
                    </div>
                    <strong>{formatNumber(item.readiness_score, 0)}</strong>
                  </header>
                  <h3>{item.headline}</h3>
                  <p>{item.judge_angle}</p>
                  <div className="readiness-evidence">
                    {item.evidence.slice(0, 2).map((evidence) => (
                      <span key={evidence}>{evidence}</span>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>

          <div className="readiness-layout">
            <div className="readiness-runbook">
              <div className="mini-heading">
                <span>Step-by-step runbook</span>
                <strong>{report.runbook_steps.length}</strong>
              </div>
              {report.runbook_steps.map((step) => (
                <article key={step.step} className="readiness-step">
                  <div className="readiness-step-index">{step.step}</div>
                  <div>
                    <strong>{step.title}</strong>
                    <p>{step.ui_action}</p>
                    <small>{step.underlying_mechanism}</small>
                    <code>{step.proof_url ?? "Live dashboard"}</code>
                  </div>
                </article>
              ))}
            </div>

            <div className="readiness-side">
              <div className="readiness-box">
                <div className="mini-heading">
                  <span>Strongest claims</span>
                  <strong>{report.strongest_claims.length}</strong>
                </div>
                <ul>
                  {report.strongest_claims.map((claim) => (
                    <li key={claim}>{claim}</li>
                  ))}
                </ul>
              </div>
              <div className="readiness-box">
                <div className="mini-heading">
                  <span>Known limitations</span>
                  <strong>{report.known_limitations.length}</strong>
                </div>
                <ul>
                  {report.known_limitations.map((limitation) => (
                    <li key={limitation}>{limitation}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Building rubric runbook" : "Generate a judge-facing readiness runbook"}</span>
        </div>
      )}
    </section>
  );
}

function SubmissionKitPanel({
  kit,
  loading,
  onRefresh
}: {
  kit: HackathonSubmissionKit | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copySubmissionKit() {
    if (!kit) return;
    await navigator.clipboard.writeText(kit.copy_block);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <section className="panel submission-kit-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <Film size={20} />
          <h2>Submission kit</h2>
        </div>
        <div className="section-actions">
          <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="submission-refresh">
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            <span>{loading ? "Packaging" : "Refresh"}</span>
          </button>
          <button className="icon-button small" onClick={copySubmissionKit} disabled={!kit} data-testid="submission-copy">
            <Clipboard size={16} />
            <span>{copied ? "Copied" : "Copy kit"}</span>
          </button>
        </div>
      </header>

      {kit ? (
        <>
          <div className="submission-hero">
            <div>
              <span className="eyebrow">{kit.symbol} / {titleize(kit.scenario)} / {Math.round(kit.total_runtime_seconds / 60)} minute video</span>
              <h3>{kit.headline}</h3>
              <p>{kit.opening_hook}</p>
            </div>
            <div className="submission-timer">
              <Play size={18} />
              <strong>{kit.total_runtime_seconds}s</strong>
              <span>{kit.video_segments.length} segments</span>
            </div>
          </div>

          <div className="submission-grid">
            <div className="submission-timeline">
              <div className="mini-heading">
                <span>Record this</span>
                <strong>{kit.video_segments.length}</strong>
              </div>
              {kit.video_segments.map((segment) => (
                <article key={segment.slide} className="submission-segment">
                  <div>
                    <span>{segment.timecode}</span>
                    <strong>{segment.title}</strong>
                  </div>
                  <p>{segment.dashboard_action}</p>
                  <small>{segment.narration}</small>
                  <code>{segment.proof_url ?? "Live dashboard"}</code>
                </article>
              ))}
            </div>

            <div className="submission-side">
              <div className="submission-box">
                <div className="mini-heading">
                  <span>Submit these</span>
                  <strong>{kit.submission_assets.filter((asset) => asset.required).length}</strong>
                </div>
                {kit.submission_assets.map((asset) => (
                  <article key={asset.path} className={asset.required ? "required" : ""}>
                    <FileText size={16} />
                    <div>
                      <strong>{asset.label}</strong>
                      <p>{asset.purpose}</p>
                      <code>{asset.path}</code>
                    </div>
                  </article>
                ))}
              </div>

              <div className="submission-box">
                <div className="mini-heading">
                  <span>Final checklist</span>
                  <strong>{kit.final_checklist.length}</strong>
                </div>
                {kit.final_checklist.map((item) => (
                  <article key={item.label} className={item.status}>
                    <CheckCircle2 size={16} />
                    <div>
                      <strong>{item.label}</strong>
                      <p>{item.evidence}</p>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Packaging video and proof assets" : "Generate the final judge submission kit"}</span>
        </div>
      )}
    </section>
  );
}

function CompetitionRunwayPanel({
  decision,
  readiness,
  submissionKit,
  evidencePack,
  executionRouter,
  onSelectScenario
}: {
  decision: Decision;
  readiness: HackathonReadinessReport | null;
  submissionKit: HackathonSubmissionKit | null;
  evidencePack: AuditEvidencePack | null;
  executionRouter: FairExecutionRouterReport | null;
  onSelectScenario: (scenario: Scenario) => void;
}) {
  const [copied, setCopied] = useState(false);
  const shortHash = decision.audit_hash.slice(0, 12);
  const readinessScore = readiness?.readiness_score ?? evidencePack?.verification_score ?? decision.fairness_passport.score;
  const runtime = submissionKit?.total_runtime_seconds ?? 120;
  const segmentCount = submissionKit?.video_segments.length ?? 6;
  const criteria = readiness?.criteria ?? [];
  const proofEndpoint = `/api/audits/${decision.audit_hash}/evidence-pack`;

  async function copyProof() {
    const text = submissionKit?.copy_block ?? [
      "FairFlow Guardian - final demo proof",
      `Audit: ${decision.audit_hash}`,
      `Decision: ${decision.status} / ${decision.final_action}`,
      `Evidence: ${proofEndpoint}`,
    ].join("\n");
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <section className="competition-runway-panel" aria-label="Competition demo runway">
      <div className="runway-hero">
        <div className="runway-copy">
          <span className="eyebrow">Finalist demo mode</span>
          <h2>Better systems, not bigger bets.</h2>
          <p>
            Lead with fairness, prove the guardrails, then end on no-trade restraint. This is the BGA story in one audited path.
          </p>
          <div className="runway-actions">
            <button className="icon-button small" onClick={() => onSelectScenario("calm")} data-testid="runway-calm">
              <CheckCircle2 size={16} />
              <span>Show calm approval</span>
            </button>
            <button className="icon-button small danger" onClick={() => onSelectScenario("manipulated")} data-testid="runway-manipulated">
              <PauseCircle size={16} />
              <span>Show no-trade</span>
            </button>
            <button className="icon-button small" onClick={copyProof} data-testid="runway-copy-proof">
              <Clipboard size={16} />
              <span>{copied ? "Copied" : "Copy proof"}</span>
            </button>
          </div>
        </div>

        <div className="runway-orbit">
          <div className="runway-score-ring">
            <span>Win readiness</span>
            <strong>{formatNumber(readinessScore, 0)}</strong>
            <small>{readiness ? readinessVerdictLabel(readiness.verdict) : "loading proof"}</small>
          </div>
          <div className="runway-proof-chip">
            <span>Audit hash</span>
            <code>{shortHash}</code>
          </div>
        </div>
      </div>

      <div className="runway-grid">
        <article>
          <Film size={18} />
          <div>
            <span>2-minute video</span>
            <strong>{runtime}s / {segmentCount} beats</strong>
            <p>{submissionKit ? submissionKit.video_segments[0]?.title : "Thesis"} → {submissionKit ? submissionKit.video_segments.at(-1)?.title : "No-trade proof"}</p>
          </div>
        </article>
        <article>
          <Route size={18} />
          <div>
            <span>Route proof</span>
            <strong>{executionRouter?.recommended_route ?? "Preparing route"}</strong>
            <p>{executionRouter?.verdict.replaceAll("_", " ") ?? "Fair route scoring is loading"}</p>
          </div>
        </article>
        <article>
          <Database size={18} />
          <div>
            <span>Evidence pack</span>
            <strong>{evidencePack ? `${formatNumber(evidencePack.verification_score, 0)}/100` : "Bundling"}</strong>
            <p>{evidencePack ? `${evidencePack.included_reports.length} linked reports` : proofEndpoint}</p>
          </div>
        </article>
      </div>

      <div className="runway-rubric">
        {["bga_ethos", "technical_depth", "risk_management", "transparency"].map((category) => {
          const criterion = criteria.find((item) => item.category === category);
          const score = criterion?.readiness_score ?? 0;
          return (
            <div key={category}>
              <span>{rubricLabel(category as JudgeBriefRubricItem["category"])}</span>
              <div className="runway-meter">
                <i style={{ width: `${Math.min(100, Math.max(6, score))}%` }} />
              </div>
              <strong>{criterion ? formatNumber(score, 0) : "--"}</strong>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function componentTypeLabel(type: ModelComponentCard["component_type"]) {
  if (type === "ml_signal") return "ML signal";
  if (type === "heuristic_agent") return "Agent";
  if (type === "risk_model") return "Risk model";
  if (type === "execution_guard") return "Gate";
  return "Audit";
}

function ProvenancePanel({
  card,
  loading,
  onRefresh
}: {
  card: ModelProvenanceCard | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const scoreTone = card
    ? card.provenance_score >= 82
      ? "good"
      : card.provenance_score >= 65
        ? "warn"
        : "bad"
    : "warn";

  return (
    <section className="panel provenance-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <Database size={20} />
          <h2>Model & data provenance</h2>
        </div>
        <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="provenance-refresh">
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          <span>{loading ? "Tracing" : "Trace"}</span>
        </button>
      </header>

      {card ? (
        <>
          <div className="provenance-hero">
            <div>
              <span className="eyebrow">{card.symbol} / {titleize(card.scenario)} model card</span>
              <p>{card.summary}</p>
            </div>
            <div className={`provenance-score ${scoreTone}`}>
              <span>Provenance</span>
              <strong>{formatNumber(card.provenance_score, 1)}</strong>
              <small>Data source clarity, component disclosure, auditability</small>
            </div>
          </div>

          <div className="provenance-sources">
            {card.data_sources.map((source) => (
              <article key={source.name} className={`provenance-source ${source.status}`}>
                <header>
                  <strong>{source.name}</strong>
                  <span>{titleize(source.source_type)}</span>
                </header>
                <p>{source.caveat}</p>
                <div>
                  {source.fields.slice(0, 4).map((field) => (
                    <span key={field}>{field}</span>
                  ))}
                </div>
              </article>
            ))}
          </div>

          <div className="provenance-layout">
            <div className="provenance-components">
              <div className="mini-heading">
                <span>Components</span>
                <strong>{card.model_components.length}</strong>
              </div>
              {card.model_components.slice(0, 5).map((component) => (
                <article key={component.name} className="provenance-component">
                  <header>
                    <div>
                      <span>{componentTypeLabel(component.component_type)}</span>
                      <strong>{component.name}</strong>
                    </div>
                    <code>{component.version}</code>
                  </header>
                  <p>{component.validation}</p>
                  <div className="provenance-io">
                    <span>In: {component.inputs.slice(0, 3).join(", ")}</span>
                    <span>Out: {component.outputs.slice(0, 2).join(", ")}</span>
                  </div>
                  <ul>
                    {component.limitations.slice(0, 2).map((limitation) => (
                      <li key={limitation}>{limitation}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>

            <aside className="provenance-side">
              <div className="provenance-box">
                <div className="mini-heading">
                  <span>Validation</span>
                  <strong>{card.validation_artifacts.length}</strong>
                </div>
                <ul>
                  {card.validation_artifacts.map((artifact) => (
                    <li key={artifact}>{artifact}</li>
                  ))}
                </ul>
              </div>
              <div className="provenance-box warning">
                <div className="mini-heading">
                  <span>Known limits</span>
                  <strong>{card.known_limitations.length}</strong>
                </div>
                <ul>
                  {card.known_limitations.slice(0, 5).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </aside>
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Tracing data and model lineage" : "Generate a model card for this audit"}</span>
        </div>
      )}
    </section>
  );
}

function AICommitteePanel({ decision }: { decision: Decision }) {
  const committee = decision.ai_committee;
  const anomalyTone = committee.anomaly.status === "normal" ? "good" : committee.anomaly.status === "elevated" ? "warn" : "bad";
  const forecastTone = committee.forecast.stop_loss_hit_probability < 0.35 ? "good" : committee.forecast.stop_loss_hit_probability < 0.6 ? "warn" : "bad";
  const backtestTone = committee.backtest.trades < 3 ? "warn" : committee.backtest.win_rate > 0.5 ? "good" : "warn";
  const planTone = committee.execution_plan.order_style === "none" ? "warn" : "good";

  return (
    <section className="committee-section">
      <div className="panel committee-panel">
        <div className="panel-heading">
          <BrainCircuit size={20} />
          <h2>AI committee</h2>
        </div>
        <p className="committee-summary">{committee.narrator_summary}</p>
        <div className="debate-list">
          {committee.debate.map((item) => (
            <div key={item} className="debate-item">
              <Sparkles size={15} />
              <span>{item}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="signal-grid">
        <SignalCard
          icon={<BrainCircuit size={19} />}
          label="ML regime"
          value={titleize(committee.ml_regime.regime)}
          detail={`${formatPercent(committee.ml_regime.confidence)} confidence / ${committee.ml_regime.top_drivers[0] ?? "no dominant driver"}`}
          tone={committee.ml_regime.regime === "fragile_liquidity" || committee.ml_regime.regime === "high_volatility" ? "bad" : "good"}
        />
        <SignalCard
          icon={<Bot size={19} />}
          label="Anomaly model"
          value={`${Math.round(committee.anomaly.score)}/100`}
          detail={`${titleize(committee.anomaly.status)} / ${committee.anomaly.drivers[0] ?? "normal baseline"}`}
          tone={anomalyTone}
        />
        <SignalCard
          icon={<LineChart size={19} />}
          label={`${committee.forecast.horizon_minutes}m forecast`}
          value={formatPercent(committee.forecast.stop_loss_hit_probability)}
          detail={`Stop-hit probability, range ${formatNumber(committee.forecast.downside_risk_pct, 2)}% to ${formatNumber(committee.forecast.upside_risk_pct, 2)}%`}
          tone={forecastTone}
        />
        <SignalCard
          icon={<Route size={19} />}
          label="Execution planner"
          value={titleize(committee.execution_plan.order_style)}
          detail={`${committee.execution_plan.side} / slippage cap ${formatNumber(committee.execution_plan.max_slippage_bps, 1)} bps`}
          tone={planTone}
        />
        <SignalCard
          icon={<BarChart3 size={19} />}
          label="Backtest agent"
          value={`${committee.backtest.trades} trades`}
          detail={`${formatPercent(committee.backtest.win_rate)} win rate / ${formatNumber(committee.backtest.max_drawdown_pct, 2)}% max drawdown`}
          tone={backtestTone}
        />
        <SignalCard
          icon={<Database size={19} />}
          label="Memory"
          value={`${Math.round(committee.calibration.calibration_score)}/100`}
          detail={`${committee.calibration.confidence_bucket} / ${committee.calibration.avoided_trade_count} avoided trades`}
          tone={committee.calibration.sample_size >= 5 ? "good" : "warn"}
        />
      </div>
    </section>
  );
}

function DecisionTracePanel({ steps }: { steps: DecisionTraceStep[] }) {
  return (
    <section className="panel trace-panel">
      <div className="panel-heading">
        <Route size={20} />
        <h2>Decision trace</h2>
      </div>
      <div className="trace-list">
        {steps.map((step) => (
          <article key={step.step} className={`trace-step ${step.status}`}>
            <div className="trace-marker">{step.step}</div>
            <div className="trace-body">
              <header>
                <div>
                  <strong>{step.title}</strong>
                  <p>{step.summary}</p>
                </div>
                <span className={`trace-status ${step.status}`}>
                  {statusIcon(step.status)}
                  {statusLabel(step.status)}
                </span>
              </header>
              <ul>
                {step.evidence.slice(0, 4).map((item, index) => (
                  <li key={`${step.step}-${index}`}>{item}</li>
                ))}
              </ul>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function StressTable({ rows }: { rows: Stress[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Move</th>
            <th>PnL</th>
            <th>Equity</th>
            <th>Stop</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.price_move_pct}-${row.projected_pnl_pct}`}>
              <td>{row.price_move_pct > 0 ? "+" : ""}{row.price_move_pct}%</td>
              <td className={row.projected_pnl_pct < 0 ? "negative" : "positive"}>
                {row.projected_pnl_pct > 0 ? "+" : ""}{formatNumber(row.projected_pnl_pct, 1)}%
              </td>
              <td>{formatUsd(row.projected_equity_usdt)}</td>
              <td>{row.stop_triggered ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DecisionStat({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" | "bad" }) {
  return (
    <div className={`decision-stat ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MarketTape({
  decision,
  comparison,
  loading
}: {
  decision: Decision | null;
  comparison: ScenarioComparison | null;
  loading: boolean;
}) {
  const items = decision
    ? [
        `${decision.symbol} ${formatUsd(decision.metrics.price, 2)}`,
        `${titleize(decision.scenario)} ${statusLabel(decision.status)}`,
        `Fairness ${Math.round(decision.fairness_passport.score)}/100`,
        `Liquidity ${Math.round(decision.metrics.liquidity_score)}/100`,
        `Spread ${formatNumber(decision.metrics.spread_bps, 1)} bps`,
        `Anomaly ${Math.round(decision.ai_committee.anomaly.score)}/100`,
        `Audit ${decision.audit_hash.slice(0, 12)}`,
        comparison ? `Scenario avg ${Math.round(comparison.average_fairness_score)}/100` : "Scenario avg pending"
      ]
    : ["Waiting for market report", "Agents initializing", "Audit trail pending", "Scenario lab pending"];
  const repeated = [...items, ...items];

  return (
    <section className={`market-tape ${loading ? "loading" : ""}`} aria-label="Market telemetry">
      <div className="tape-glow" />
      <div className="tape-track">
        {repeated.map((item, index) => (
          <span key={`${item}-${index}`}>{item}</span>
        ))}
      </div>
    </section>
  );
}

function DecisionVisual({ decision, sentinelScore }: { decision: Decision; sentinelScore: number }) {
  const fairness = Math.round(decision.fairness_passport.score);
  const liquidity = Math.round(decision.metrics.liquidity_score);
  const confidence = Math.round(decision.proposal.confidence * 100);
  const riskPressure = Math.round(sentinelScore);
  const tone = statusTone(decision.status);
  const path = sparkPath([
    50,
    52 + decision.metrics.momentum_1h_pct * 4,
    50 + decision.metrics.momentum_4h_pct * 2,
    52 - decision.metrics.realized_volatility_pct * 9,
    48 + decision.metrics.order_book_imbalance * 90,
    50 + decision.metrics.funding_rate_bps * 1.4,
    52 + (liquidity - riskPressure) / 7
  ]);
  const visualStyle = {
    "--fairness": `${fairness}%`,
    "--liquidity": `${liquidity}%`,
    "--risk": `${riskPressure}%`,
    "--confidence": `${confidence}%`
  } as CSSProperties;

  return (
    <div className={`decision-visual ${tone}`} style={visualStyle}>
      <div className="radar-shell">
        <div className="radar-sweep" />
        <div className="radar-core">
          <span>Gate</span>
          <strong>{statusLabel(decision.status)}</strong>
        </div>
        <span className="radar-node node-fairness" />
        <span className="radar-node node-liquidity" />
        <span className="radar-node node-risk" />
        <span className="radar-node node-confidence" />
      </div>
      <div className="pulse-panel">
        <div className="pulse-header">
          <span>{titleize(decision.ai_committee.ml_regime.regime)}</span>
          <strong>{formatPercent(decision.ai_committee.ml_regime.confidence)}</strong>
        </div>
        <svg className="pulse-chart" viewBox="0 0 260 96" role="img" aria-label="Market pulse chart">
          <path className="pulse-area" d={`${path} L 260 96 L 0 96 Z`} />
          <path className="pulse-line" d={path} />
        </svg>
        <div className="pulse-metrics">
          <span>F {fairness}</span>
          <span>L {liquidity}</span>
          <span>R {riskPressure}</span>
          <span>C {confidence}</span>
        </div>
      </div>
    </div>
  );
}

function PriceChartPanel({
  series,
  decision,
  loading,
  streaming,
  onToggleStreaming,
  onRefresh
}: {
  series: MarketSeries | null;
  decision: Decision;
  loading: boolean;
  streaming: boolean;
  onToggleStreaming: (enabled: boolean) => void;
  onRefresh: () => void;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const candles = series?.candles ?? [];
  const width = 960;
  const height = 340;
  const padding = { top: 26, right: 56, bottom: 62, left: 42 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const volumeHeight = 46;
  const strategyLevels = [decision.proposal.stop_loss, decision.proposal.take_profit].filter((price): price is number => Boolean(price));
  const high = candles.length ? Math.max(...candles.map((candle) => candle.high), ...strategyLevels) : 1;
  const low = candles.length ? Math.min(...candles.map((candle) => candle.low), ...strategyLevels) : 0;
  const priceRange = high - low || 1;
  const volumeMax = candles.length ? Math.max(...candles.map((candle) => candle.volume)) || 1 : 1;
  const xFor = (index: number) => padding.left + (index / Math.max(1, candles.length - 1)) * plotWidth;
  const yFor = (price: number) => padding.top + ((high - price) / priceRange) * plotHeight;
  const linePath = candles
    .map((candle, index) => `${index === 0 ? "M" : "L"} ${xFor(index).toFixed(1)} ${yFor(candle.close).toFixed(1)}`)
    .join(" ");
  const areaPath = linePath ? `${linePath} L ${padding.left + plotWidth} ${padding.top + plotHeight} L ${padding.left} ${padding.top + plotHeight} Z` : "";
  const latest = candles[candles.length - 1] ?? null;
  const activeIndex = hoverIndex ?? Math.max(0, candles.length - 1);
  const active = candles[activeIndex] ?? latest;
  const first = candles[0] ?? null;
  const changePct = series?.change_pct ?? (latest && first ? ((latest.close / first.open) - 1) * 100 : 0);
  const chartTone = changePct >= 0 ? "positive" : "negative";
  const latestX = latest ? xFor(candles.length - 1) : 0;
  const latestY = latest ? yFor(latest.close) : 0;
  const activeX = active ? xFor(activeIndex) : 0;
  const activeY = active ? yFor(active.close) : 0;
  const timeLabel = active ? new Date(active.start_ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "--";

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!candles.length) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
    const index = Math.round((x / rect.width) * (candles.length - 1));
    setHoverIndex(Math.max(0, Math.min(candles.length - 1, index)));
  }

  function levelLine(price: number | null, label: string, className: string) {
    if (!price || price < low || price > high) return null;
    const y = yFor(price);
    return (
      <g className={`chart-level ${className}`}>
        <line x1={padding.left} x2={padding.left + plotWidth} y1={y} y2={y} />
        <text x={padding.left + plotWidth - 8} y={y - 7}>{label}</text>
      </g>
    );
  }

  return (
    <section className="panel price-chart-panel">
      <header className="chart-header">
        <div className="panel-heading compact">
          <TrendingUp size={20} />
          <h2>Real-time price chart</h2>
        </div>
        <div className="chart-actions">
          <span className={`live-pill ${streaming ? "on" : ""}`}>
            <span />
            {streaming ? "Streaming" : "Paused"}
          </span>
          <button className="icon-button small" onClick={() => onToggleStreaming(!streaming)}>
            {streaming ? "Pause" : "Stream"}
          </button>
          <button className="icon-button small" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            <span>Tick</span>
          </button>
        </div>
      </header>

      <div className="chart-stat-row">
        <DecisionStat label="Last" value={series ? formatUsd(series.latest_price, 2) : "--"} tone={chartTone === "positive" ? "good" : "bad"} />
        <DecisionStat label="Window" value={`${changePct >= 0 ? "+" : ""}${formatNumber(changePct, 2)}%`} tone={chartTone === "positive" ? "good" : "bad"} />
        <DecisionStat label="Source" value={series?.source ?? "Loading"} />
        <DecisionStat label="Interval" value={series ? `${series.interval_minutes}m` : "--"} />
      </div>

      <div className={`chart-stage ${chartTone}`}>
        {candles.length ? (
          <>
            <svg
              className="price-chart-svg"
              viewBox={`0 0 ${width} ${height}`}
              role="img"
              aria-label={`${series?.symbol ?? decision.symbol} real-time price chart`}
              onPointerMove={handlePointerMove}
              onPointerLeave={() => setHoverIndex(null)}
            >
              <defs>
                <linearGradient id="priceAreaGradient" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="currentColor" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
                </linearGradient>
              </defs>
              {[0, 1, 2, 3].map((line) => {
                const y = padding.top + (line / 3) * plotHeight;
                return <line key={line} className="chart-grid-line" x1={padding.left} x2={padding.left + plotWidth} y1={y} y2={y} />;
              })}
              {candles.map((candle, index) => {
                const barHeight = (candle.volume / volumeMax) * volumeHeight;
                const x = xFor(index);
                const y = height - padding.bottom + volumeHeight - barHeight;
                return <rect key={candle.start_ms} className="volume-bar" x={x - 2} y={y} width="4" height={barHeight} />;
              })}
              <path className="price-area" d={areaPath} />
              <path className="price-line" d={linePath} />
              {levelLine(decision.proposal.take_profit, "Take profit", "take")}
              {levelLine(decision.proposal.stop_loss, "Stop", "stop")}
              <line className="hover-line" x1={activeX} x2={activeX} y1={padding.top} y2={padding.top + plotHeight + volumeHeight} />
              <circle className="hover-dot" cx={activeX} cy={activeY} r="6" />
              <circle className="latest-dot" cx={latestX} cy={latestY} r="7" />
              <text className="price-axis top" x={width - 8} y={padding.top + 6}>{formatUsd(high, 2)}</text>
              <text className="price-axis bottom" x={width - 8} y={padding.top + plotHeight}>{formatUsd(low, 2)}</text>
            </svg>
            <div className="chart-tooltip" style={{ "--tooltip-x": `${(activeX / width) * 100}%` } as CSSProperties}>
              <span>{timeLabel}</span>
              <strong>{active ? formatUsd(active.close, 2) : "--"}</strong>
              <small>O {active ? formatUsd(active.open, 2) : "--"} / V {active ? formatNumber(active.volume, 0) : "--"}</small>
            </div>
          </>
        ) : (
          <div className="empty-state chart-empty">
            <RefreshCw size={18} className={loading ? "spin" : ""} />
            <span>{loading ? "Streaming candles" : "No candle data yet"}</span>
          </div>
        )}
      </div>
    </section>
  );
}

function PortfolioPanel({
  portfolio,
  loading,
  onRefresh,
  onReset
}: {
  portfolio: PaperPortfolio | null;
  loading: boolean;
  onRefresh: () => void;
  onReset: () => void;
}) {
  const pnl = portfolio ? portfolio.realized_pnl_usdt + portfolio.unrealized_pnl_usdt : 0;
  const pnlTone = pnl >= 0 ? "good" : "bad";
  const positions = portfolio?.positions.slice(-4).reverse() ?? [];
  const orders = portfolio?.orders.slice(-5).reverse() ?? [];

  return (
    <section className="panel portfolio-panel">
      <header className="chart-header">
        <div className="panel-heading compact">
          <Database size={20} />
          <h2>Paper portfolio</h2>
        </div>
        <div className="chart-actions">
          <button className="icon-button small" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            <span>Mark</span>
          </button>
          <button className="icon-button small danger-button" onClick={onReset} disabled={loading}>
            Reset
          </button>
        </div>
      </header>

      <div className="portfolio-stats">
        <DecisionStat label="Equity" value={portfolio ? formatUsd(portfolio.equity_usdt) : "--"} tone={pnlTone} />
        <DecisionStat label="Open PnL" value={portfolio ? formatUsd(portfolio.unrealized_pnl_usdt) : "--"} tone={portfolio && portfolio.unrealized_pnl_usdt < 0 ? "bad" : "good"} />
        <DecisionStat label="Gross exposure" value={portfolio ? formatUsd(portfolio.gross_exposure_usdt) : "--"} />
        <DecisionStat label="Orders" value={portfolio ? `${portfolio.accepted_order_count}/${portfolio.orders.length}` : "--"} />
      </div>

      {portfolio ? (
        <div className="portfolio-grid">
          <div className="portfolio-block">
            <div className="mini-heading">
              <span>Positions</span>
              <strong>{positions.length}</strong>
            </div>
            {positions.length ? (
              <div className="position-list">
                {positions.map((position) => (
                  <article key={position.client_order_id} className={`position-row ${position.pnl_usdt >= 0 ? "positive-row" : "negative-row"}`}>
                    <div>
                      <span>{position.symbol} / {position.side}</span>
                      <strong>{formatUsd(position.current_price, 2)}</strong>
                    </div>
                    <div>
                      <span>Entry</span>
                      <strong>{formatUsd(position.entry_price, 2)}</strong>
                    </div>
                    <div>
                      <span>PnL</span>
                      <strong>{position.pnl_usdt >= 0 ? "+" : ""}{formatUsd(position.pnl_usdt)} / {formatNumber(position.pnl_pct, 2)}%</strong>
                    </div>
                    <div className={`position-status ${position.status}`}>{titleize(position.status)}</div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state compact-empty">
                <Database size={16} />
                <span>No open paper positions</span>
              </div>
            )}
          </div>

          <div className="portfolio-block">
            <div className="mini-heading">
              <span>Execution journal</span>
              <strong>{orders.length}</strong>
            </div>
            {orders.length ? (
              <div className="journal-list">
                {orders.map((entry) => (
                  <article key={entry.client_order_id} className={`journal-row ${entry.accepted ? "accepted" : "rejected"}`}>
                    <div>
                      <span>{entry.symbol} / {entry.side}</span>
                      <strong>{entry.client_order_id}</strong>
                    </div>
                    <div>
                      <span>Notional</span>
                      <strong>{formatUsd(entry.qty_usdt)}</strong>
                    </div>
                    <div className={`audit-status ${entry.accepted ? "approved" : "blocked"}`}>
                      {entry.accepted ? "Accepted" : "Blocked"}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state compact-empty">
                <History size={16} />
                <span>No orders yet</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Loading portfolio" : "Portfolio pending"}</span>
        </div>
      )}

      {portfolio?.risk_notes.length ? (
        <div className="portfolio-notes">
          {portfolio.risk_notes.slice(0, 3).map((note) => (
            <div key={note}>
              <Shield size={15} />
              <span>{note}</span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function AgentMissionPanel({
  mission,
  loading,
  autoMission,
  onToggleAutoMission,
  onRun,
  onAction
}: {
  mission: AgentMission | null;
  loading: boolean;
  autoMission: boolean;
  onToggleAutoMission: (enabled: boolean) => void;
  onRun: () => void;
  onAction: (action: AgentAction) => void;
}) {
  const completedCount = mission?.tasks.filter((task) => task.status === "complete").length ?? 0;
  const blockedCount = mission?.tasks.filter((task) => task.status === "blocked").length ?? 0;
  const missionTone = mission?.can_execute ? "approved" : blockedCount ? "blocked" : "observe";

  return (
    <section className={`panel mission-panel ${missionTone}`}>
      <header className="mission-header">
        <div className="panel-heading compact">
          <BrainCircuit size={20} />
          <h2>Agent Mission Control</h2>
        </div>
        <div className="section-actions">
          <label className="toggle-line">
            <input
              type="checkbox"
              checked={autoMission}
              onChange={(event) => onToggleAutoMission(event.target.checked)}
            />
            <span>Auto</span>
          </label>
          <button className="icon-button small" onClick={onRun} disabled={loading} data-testid="run-agent-mission">
            <Bot size={16} />
            <span>{loading ? "Planning" : "Run mission"}</span>
          </button>
        </div>
      </header>

      {mission ? (
        <>
          <div className="mission-command">
            <div>
              <span className="eyebrow">Mission recommendation</span>
              <p>{mission.final_recommendation}</p>
            </div>
            <div className={`mission-gate ${mission.can_execute ? "open" : "locked"}`}>
              {mission.can_execute ? <CheckCircle2 size={18} /> : <Shield size={18} />}
              <span>{mission.can_execute ? "Guarded paper route open" : "Execution gate locked"}</span>
            </div>
          </div>

          <div className="mission-stats">
            <DecisionStat label="Autonomy" value={titleize(mission.autonomy_level)} tone={mission.can_execute ? "good" : "warn"} />
            <DecisionStat label="Tasks clear" value={`${completedCount}/${mission.tasks.length}`} tone={blockedCount ? "warn" : "good"} />
            <DecisionStat label="Blocked tasks" value={String(blockedCount)} tone={blockedCount ? "bad" : "good"} />
            <DecisionStat label="Mission id" value={mission.id.replace("mission-", "").slice(0, 12)} />
          </div>

          <div className="mission-layout">
            <div className="mission-task-grid">
              {mission.tasks.map((task, index) => {
                const tone = missionStatusTone(task.status);
                return (
                  <article key={`${task.agent}-${index}`} className={`mission-task ${task.status}`}>
                    <header>
                      <div className="task-node">{index + 1}</div>
                      <div>
                        <span>{task.agent}</span>
                        <strong>{task.objective}</strong>
                      </div>
                      <div className={`task-status ${task.status}`}>
                        {missionStatusIcon(task.status)}
                        <span>{missionStatusLabel(task.status)}</span>
                      </div>
                    </header>
                    <p>{task.finding}</p>
                    <div className="confidence-rail" aria-label={`${task.agent} confidence`}>
                      <div className={`confidence-fill ${tone}`} style={{ width: `${Math.round(task.confidence * 100)}%` }} />
                    </div>
                    <small>{task.tool}</small>
                    <ul>
                      {task.evidence.slice(0, 3).map((item, evidenceIndex) => (
                        <li key={`${task.agent}-${evidenceIndex}`}>{item}</li>
                      ))}
                    </ul>
                  </article>
                );
              })}
            </div>

            <aside className="mission-side">
              <div className="mission-block">
                <div className="mini-heading">
                  <span>Action queue</span>
                  <strong>{mission.action_queue.length}</strong>
                </div>
                <div className="action-list">
                  {mission.action_queue.map((action) => (
                    <article key={`${action.action_type}-${action.label}`} className={`mission-action ${action.priority} ${action.permitted ? "" : "locked"}`}>
                      <button
                        className="mini-button action-button"
                        onClick={() => onAction(action)}
                        disabled={loading}
                        aria-disabled={!action.permitted}
                        data-testid={`mission-action-${action.action_type}`}
                      >
                        {actionIcon(action.action_type)}
                        <span>{action.label}</span>
                      </button>
                      <div>
                        <span className="priority-pill">{titleize(action.priority)}</span>
                        <p>{action.reason}</p>
                      </div>
                    </article>
                  ))}
                </div>
              </div>

              <div className="mission-block">
                <div className="mini-heading">
                  <span>Memory</span>
                  <strong>{mission.memory_notes.length}</strong>
                </div>
                <ul className="mission-list">
                  {mission.memory_notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </div>

              <div className="mission-block risk">
                <div className="mini-heading">
                  <span>Risk register</span>
                  <strong>{mission.risk_register.length}</strong>
                </div>
                <ul className="mission-list">
                  {mission.risk_register.slice(0, 6).map((risk) => (
                    <li key={risk}>{risk}</li>
                  ))}
                </ul>
              </div>
            </aside>
          </div>
        </>
      ) : (
        <div className="empty-state">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Delegating to specialist agents" : "Run a mission to generate an agentic action plan"}</span>
        </div>
      )}
    </section>
  );
}

function AuditBox({ decision }: { decision: Decision }) {
  const [copied, setCopied] = useState(false);

  async function copyHash() {
    await navigator.clipboard.writeText(decision.audit_hash);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <section className="audit-panel">
      <div>
        <span className="eyebrow">Verifiable decision report</span>
        <h2>Audit hash</h2>
        <code>{decision.audit_hash}</code>
      </div>
      <button className="icon-button labeled" onClick={copyHash} aria-label="Copy audit hash">
        <Clipboard size={18} />
        <span>{copied ? "Copied" : "Copy"}</span>
      </button>
    </section>
  );
}

function MiniMeter({ label, value, tone }: { label: string; value: number; tone?: "good" | "warn" | "bad" }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="mini-meter">
      <div>
        <span>{label}</span>
        <strong>{Math.round(clamped)}</strong>
      </div>
      <div className="mini-meter-track">
        <div className={`mini-meter-fill ${tone ?? ""}`} style={{ width: `${clamped}%` }} />
      </div>
    </div>
  );
}

function ScenarioLabPanel({
  comparison,
  loading,
  includeLive,
  onToggleLive,
  onRefresh,
  onOpen
}: {
  comparison: ScenarioComparison | null;
  loading: boolean;
  includeLive: boolean;
  onToggleLive: (enabled: boolean) => void;
  onRefresh: () => void;
  onOpen: (scenario: Scenario) => void;
}) {
  return (
    <section className="panel scenario-lab-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <Layers3 size={20} />
          <h2>Scenario lab</h2>
        </div>
        <div className="section-actions">
          <label className="toggle-line">
            <input type="checkbox" checked={includeLive} onChange={(event) => onToggleLive(event.target.checked)} />
            <span>Live</span>
          </label>
          <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="scenario-compare">
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            <span>Compare</span>
          </button>
        </div>
      </header>

      {comparison ? (
        <>
          <div className="comparison-strip">
            <DecisionStat label="Approved" value={String(comparison.approved_count)} tone={comparison.approved_count > 0 ? "good" : "warn"} />
            <DecisionStat label="Blocked" value={String(comparison.blocked_count)} tone={comparison.blocked_count > 0 ? "bad" : "good"} />
            <DecisionStat label="Avg fairness" value={`${Math.round(comparison.average_fairness_score)}/100`} />
            <DecisionStat label="Healthiest" value={titleize(comparison.healthiest_scenario)} tone="good" />
          </div>

          <div className="scenario-grid">
            {comparison.decisions.map((item) => {
              const anomalyRisk = item.ai_committee.anomaly.score;
              const fairnessTone = verdictTone(item.fairness_passport.verdict);
              const anomalyTone = anomalyRisk < 35 ? "good" : anomalyRisk < 65 ? "warn" : "bad";
              return (
                <article key={item.audit_hash} className={`scenario-card ${item.status}`}>
                  <header>
                    <div>
                      <span>{titleize(item.scenario)}</span>
                      <strong>{item.final_action.replace("_", " ")}</strong>
                    </div>
                    <DecisionBadge decision={item} />
                  </header>
                  <MiniMeter label="Fairness" value={item.fairness_passport.score} tone={fairnessTone} />
                  <MiniMeter label="Liquidity" value={item.metrics.liquidity_score} tone={item.metrics.liquidity_score > 70 ? "good" : item.metrics.liquidity_score > 45 ? "warn" : "bad"} />
                  <MiniMeter label="Anomaly" value={anomalyRisk} tone={anomalyTone} />
                  <button className="mini-button" onClick={() => onOpen(item.scenario as Scenario)} data-testid={`open-scenario-${item.scenario}`}>
                    Open report
                  </button>
                </article>
              );
            })}
          </div>
        </>
      ) : (
        <div className="empty-state">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Comparing scenarios" : "Scenario comparison pending"}</span>
        </div>
      )}
    </section>
  );
}

function RiskSizingPanel({
  decision,
  sizing,
  loading,
  inputs,
  onChange,
  onRecalculate
}: {
  decision: Decision;
  sizing: RiskSizing | null;
  loading: boolean;
  inputs: { account_equity_usdt: number; risk_budget_pct: number; max_notional_pct: number };
  onChange: (field: "account_equity_usdt" | "risk_budget_pct" | "max_notional_pct", value: number) => void;
  onRecalculate: () => void;
}) {
  return (
    <section className="panel risk-sizer-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <Calculator size={20} />
          <h2>Risk sizing</h2>
        </div>
        <button className="icon-button small" onClick={onRecalculate} disabled={loading} data-testid="risk-reprice">
          <Target size={16} />
          <span>{loading ? "Sizing" : "Reprice"}</span>
        </button>
      </header>

      <div className="field-grid">
        <label className="field">
          <span>Equity</span>
          <input
            data-testid="risk-equity"
            type="number"
            min="100"
            step="100"
            value={inputs.account_equity_usdt}
            onChange={(event) => onChange("account_equity_usdt", Number(event.target.value))}
          />
        </label>
        <label className="field">
          <span>Risk %</span>
          <input
            data-testid="risk-percent"
            type="number"
            min="0.1"
            max="5"
            step="0.1"
            value={inputs.risk_budget_pct}
            onChange={(event) => onChange("risk_budget_pct", Number(event.target.value))}
          />
        </label>
        <label className="field">
          <span>Max notional %</span>
          <input
            data-testid="risk-max-notional"
            type="number"
            min="1"
            max="100"
            step="1"
            value={inputs.max_notional_pct}
            onChange={(event) => onChange("max_notional_pct", Number(event.target.value))}
          />
        </label>
      </div>

      {sizing ? (
        <>
          <div className={`sizing-verdict ${sizing.executable ? "approved" : "blocked"}`}>
            {sizing.executable ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
            <span>{sizing.message}</span>
          </div>
          <div className="sizing-grid">
            <DecisionStat label="Notional" value={formatUsd(sizing.recommended_notional_usdt)} tone={sizing.executable ? "good" : "bad"} />
            <DecisionStat label="Risk amount" value={formatUsd(sizing.risk_amount_usdt)} />
            <DecisionStat label="Margin" value={formatUsd(sizing.estimated_margin_usdt)} />
            <DecisionStat label="Stop distance" value={sizing.stop_distance_pct == null ? "Locked" : `${formatNumber(sizing.stop_distance_pct, 2)}%`} />
          </div>
          <div className="cap-strip">
            {(sizing.capped_by.length ? sizing.capped_by : ["uncapped"]).map((item) => (
              <span key={item}>{titleize(item)}</span>
            ))}
          </div>
        </>
      ) : (
        <div className="empty-state">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Calculating size" : decision.status === "approved" ? "Sizing pending" : "Execution gate locked"}</span>
        </div>
      )}
    </section>
  );
}

function policyVerdictLabel(verdict: GuardrailPolicyReport["verdict"]) {
  if (verdict === "compliant") return "Compliant";
  if (verdict === "needs_review") return "Needs review";
  return "Blocked";
}

function policyVerdictTone(verdict: GuardrailPolicyReport["verdict"]): "good" | "warn" | "bad" {
  if (verdict === "compliant") return "good";
  if (verdict === "needs_review") return "warn";
  return "bad";
}

function PolicyStudioPanel({
  report,
  loading,
  inputs,
  onChange,
  onEvaluate
}: {
  report: GuardrailPolicyReport | null;
  loading: boolean;
  inputs: Omit<GuardrailPolicyRequest, "audit_hash">;
  onChange: (field: keyof Omit<GuardrailPolicyRequest, "audit_hash">, value: number) => void;
  onEvaluate: () => void;
}) {
  const verdictTone = report ? policyVerdictTone(report.verdict) : "warn";
  return (
    <section className="panel policy-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <Shield size={20} />
          <h2>Policy studio</h2>
        </div>
        <button className="icon-button small" onClick={onEvaluate} disabled={loading} data-testid="policy-evaluate">
          <Gauge size={16} />
          <span>{loading ? "Checking" : "Evaluate"}</span>
        </button>
      </header>

      <div className="policy-field-grid">
        <label className="field">
          <span>Min fairness</span>
          <input type="number" min="0" max="100" step="1" value={inputs.min_fairness_score} onChange={(event) => onChange("min_fairness_score", Number(event.target.value))} />
        </label>
        <label className="field">
          <span>Max hidden bps</span>
          <input type="number" min="0" max="100" step="0.5" value={inputs.max_hidden_cost_bps} onChange={(event) => onChange("max_hidden_cost_bps", Number(event.target.value))} />
        </label>
        <label className="field">
          <span>Max anomaly</span>
          <input type="number" min="0" max="100" step="1" value={inputs.max_anomaly_score} onChange={(event) => onChange("max_anomaly_score", Number(event.target.value))} />
        </label>
        <label className="field">
          <span>Min liquidity</span>
          <input type="number" min="0" max="100" step="1" value={inputs.min_liquidity_score} onChange={(event) => onChange("min_liquidity_score", Number(event.target.value))} />
        </label>
        <label className="field">
          <span>Max leverage</span>
          <input type="number" min="1" max="25" step="0.5" value={inputs.max_leverage} onChange={(event) => onChange("max_leverage", Number(event.target.value))} />
        </label>
        <label className="field">
          <span>Max stop hit %</span>
          <input type="number" min="0" max="100" step="1" value={Math.round(inputs.max_stop_hit_probability * 100)} onChange={(event) => onChange("max_stop_hit_probability", Number(event.target.value) / 100)} />
        </label>
      </div>

      {report ? (
        <>
          <div className={`policy-verdict ${report.verdict}`}>
            {report.execution_allowed ? <CheckCircle2 size={18} /> : report.verdict === "blocked" ? <XCircle size={18} /> : <AlertTriangle size={18} />}
            <div>
              <strong>{policyVerdictLabel(report.verdict)}</strong>
              <span>{report.summary}</span>
            </div>
          </div>
          <div className="policy-stats">
            <DecisionStat label="Allowed" value={report.execution_allowed ? "Yes" : "No"} tone={report.execution_allowed ? "good" : "bad"} />
            <DecisionStat label="Pass" value={String(report.checks.filter((check) => check.status === "pass").length)} tone="good" />
            <DecisionStat label="Watch" value={String(report.checks.filter((check) => check.status === "watch").length)} tone="warn" />
            <DecisionStat label="Block" value={String(report.checks.filter((check) => check.status === "block").length)} tone={verdictTone} />
          </div>
          <div className="policy-check-list">
            {report.checks.map((check) => (
              <article key={check.name} className={`policy-check ${check.status}`}>
                <header>
                  <strong>{check.name}</strong>
                  <span>{statusLabel(check.status)}</span>
                </header>
                <p>{check.explanation}</p>
                <small>
                  Observed {String(check.observed)} {check.unit} / limit {String(check.limit)}
                </small>
              </article>
            ))}
          </div>
          <ul className="policy-actions">
            {report.suggested_actions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Checking custom policy" : "Evaluate the current audit against custom guardrails"}</span>
        </div>
      )}
    </section>
  );
}

function policyStressVerdictLabel(verdict: PolicyStressReport["resilience_verdict"]) {
  if (verdict === "stable_greenlight") return "Stable greenlight";
  if (verdict === "fragile_greenlight") return "Fragile greenlight";
  if (verdict === "protective_lockdown") return "Protective lockdown";
  return "Needs review";
}

function policyStressTone(verdict: PolicyStressReport["resilience_verdict"]): "good" | "warn" | "bad" {
  if (verdict === "stable_greenlight" || verdict === "protective_lockdown") return "good";
  if (verdict === "fragile_greenlight") return "warn";
  return "bad";
}

function PolicyStressLabPanel({
  report,
  loading,
  onRefresh
}: {
  report: PolicyStressReport | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const tone = report ? policyStressTone(report.resilience_verdict) : "warn";
  return (
    <section className={`panel policy-stress-panel ${report?.resilience_verdict ?? ""}`}>
      <header className="section-header">
        <div className="panel-heading compact">
          <Layers3 size={20} />
          <h2>Policy stress lab</h2>
        </div>
        <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="policy-stress-refresh">
          <Gauge size={16} />
          <span>{loading ? "Testing" : "Stress"}</span>
        </button>
      </header>

      {report ? (
        <>
          <div className="policy-stress-hero">
            <div>
              <span className="eyebrow">{report.symbol} / {titleize(report.scenario)} governance replay</span>
              <p>{report.summary}</p>
              <small>{report.judge_takeaway}</small>
            </div>
            <div className={`policy-stress-score ${tone}`}>
              <span>Stability</span>
              <strong>{formatNumber(report.stability_score, 1)}</strong>
              <small>{policyStressVerdictLabel(report.resilience_verdict)}</small>
            </div>
          </div>

          <div className="policy-stress-stats">
            <DecisionStat label="Allowed presets" value={`${report.execution_allowed_count}/3`} tone={report.execution_allowed_count === 3 ? "good" : report.execution_allowed_count > 0 ? "warn" : "bad"} />
            <DecisionStat label="Blocked policies" value={`${report.blocked_policy_count}/3`} tone={report.blocked_policy_count === 0 ? "good" : report.blocked_policy_count < 3 ? "warn" : "bad"} />
            <DecisionStat label="Fragile checks" value={String(report.fragile_checks.length)} tone={report.fragile_checks.length <= 2 ? "good" : report.fragile_checks.length <= 5 ? "warn" : "bad"} />
          </div>

          <div className="policy-stress-grid">
            {report.outcomes.map((outcome) => {
              const outcomeTone = policyVerdictTone(outcome.report.verdict);
              return (
                <article key={outcome.stance} className={`policy-stress-card ${outcome.report.verdict}`}>
                  <header>
                    <div>
                      <span>{titleize(outcome.stance)}</span>
                      <strong>{outcome.name}</strong>
                    </div>
                    <span className={`policy-stress-pill ${outcomeTone}`}>{policyVerdictLabel(outcome.report.verdict)}</span>
                  </header>
                  <p>{outcome.purpose}</p>
                  <div className="policy-stress-counts">
                    <span>{outcome.pass_count} pass</span>
                    <span>{outcome.watch_count} watch</span>
                    <span>{outcome.block_count} block</span>
                  </div>
                  <small>{outcome.first_breaking_check ? `Breaks first: ${outcome.first_breaking_check}` : "No blocking check"}</small>
                </article>
              );
            })}
          </div>

          <div className="policy-stress-footer">
            <div>
              <strong>Fragile checks</strong>
              <ul>
                {report.fragile_checks.slice(0, 5).map((check) => (
                  <li key={check}>{check}</li>
                ))}
              </ul>
            </div>
            <div>
              <strong>Next steps</strong>
              <ul>
                {report.recommended_next_steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Running preset guardrails" : "Stress test this audit against curated governance policies"}</span>
        </div>
      )}
    </section>
  );
}

function counterfactualVerdictLabel(verdict: CounterfactualFairnessReport["verdict"]) {
  if (verdict === "already_fair") return "Already fair";
  if (verdict === "improvable") return "Improvable";
  if (verdict === "fresh_audit_required") return "Fresh audit required";
  return "Do not unlock";
}

function counterfactualTone(verdict: CounterfactualFairnessReport["verdict"]): "good" | "warn" | "bad" {
  if (verdict === "already_fair" || verdict === "do_not_unlock") return "good";
  if (verdict === "improvable") return "warn";
  return "bad";
}

function leverStatusLabel(status: CounterfactualFairnessReport["levers"][number]["status"]) {
  if (status === "already_clear") return "Clear";
  if (status === "improvement_needed") return "Improve";
  return "Locked";
}

function leverTone(status: CounterfactualFairnessReport["levers"][number]["status"]): "good" | "warn" | "bad" {
  if (status === "already_clear") return "good";
  if (status === "improvement_needed") return "warn";
  return "bad";
}

function formatLeverValue(value: number | string, unit: string) {
  if (typeof value === "string") return value;
  if (unit === "%") return `${formatNumber(value, 1)}%`;
  if (unit === "x") return `${formatNumber(value, 1)}x`;
  if (unit === "bps") return `${formatNumber(value, 1)} bps`;
  return formatNumber(value, unit === "score" ? 0 : 2);
}

function CounterfactualLabPanel({
  report,
  loading,
  onRefresh
}: {
  report: CounterfactualFairnessReport | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const tone = report ? counterfactualTone(report.verdict) : "warn";
  return (
    <section className={`panel counterfactual-panel ${report?.verdict ?? ""}`}>
      <header className="section-header">
        <div className="panel-heading compact">
          <Route size={20} />
          <h2>Counterfactual fairness lab</h2>
        </div>
        <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="counterfactual-refresh">
          <Target size={16} />
          <span>{loading ? "Tracing" : "Trace"}</span>
        </button>
      </header>

      {report ? (
        <>
          <div className="counterfactual-hero">
            <div>
              <span className="eyebrow">{report.symbol} / {titleize(report.scenario)} unlock analysis</span>
              <p>{report.summary}</p>
              <small>{report.judge_takeaway}</small>
            </div>
            <div className={`counterfactual-score ${tone}`}>
              <span>Readiness</span>
              <strong>{formatNumber(report.readiness_score, 1)}</strong>
              <small>{counterfactualVerdictLabel(report.verdict)}</small>
            </div>
          </div>

          <div className="counterfactual-stats">
            <DecisionStat label="Current audit" value={report.unlockable_in_current_audit ? "Unlockable" : "Locked"} tone={report.unlockable_in_current_audit ? "good" : "bad"} />
            <DecisionStat label="Top blocker" value={report.top_blocker} tone={report.verdict === "already_fair" ? "good" : "warn"} />
            <DecisionStat label="Levers" value={String(report.levers.length)} />
          </div>

          <div className="counterfactual-grid">
            {report.levers.map((lever) => {
              const statusTone = leverTone(lever.status);
              return (
                <article key={lever.lever_type} className={`counterfactual-lever ${lever.status}`}>
                  <header>
                    <div>
                      <span>{titleize(lever.lever_type)}</span>
                      <strong>{lever.name}</strong>
                    </div>
                    <span className={`counterfactual-pill ${statusTone}`}>{leverStatusLabel(lever.status)}</span>
                  </header>
                  <div className="counterfactual-values">
                    <span>Now {formatLeverValue(lever.current_value, lever.unit)}</span>
                    <span>Target {formatLeverValue(lever.target_value, lever.unit)}</span>
                  </div>
                  <p>{lever.retail_impact}</p>
                  <small>{lever.explanation}</small>
                </article>
              );
            })}
          </div>

          <div className="counterfactual-footer">
            <div>
              <strong>Non-bypassable</strong>
              <ul>
                {(report.non_bypassable_constraints.length ? report.non_bypassable_constraints : ["No additional non-bypassable constraints beyond the current audit gate."]).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <strong>Next steps</strong>
              <ul>
                {report.recommended_next_steps.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Tracing guardrail gaps" : "Trace what must improve before this audit can be safer"}</span>
        </div>
      )}
    </section>
  );
}

function routerVerdictLabel(verdict: FairExecutionRouterReport["verdict"]) {
  if (verdict === "route_ready") return "Route ready";
  if (verdict === "route_with_caution") return "Caution";
  if (verdict === "paper_only_locked") return "Paper locked";
  return "No fair route";
}

function routerTone(verdict: FairExecutionRouterReport["verdict"]): "good" | "warn" | "bad" {
  if (verdict === "route_ready" || verdict === "paper_only_locked") return "good";
  if (verdict === "route_with_caution") return "warn";
  return "bad";
}

function routeStatusLabel(status: FairExecutionRouterReport["route_candidates"][number]["status"]) {
  if (status === "recommended") return "Best";
  if (status === "available") return "Open";
  if (status === "watch") return "Watch";
  return "Locked";
}

function routeStatusTone(status: FairExecutionRouterReport["route_candidates"][number]["status"]): "good" | "warn" | "bad" {
  if (status === "recommended" || status === "available") return "good";
  if (status === "watch") return "warn";
  return "bad";
}

function FairExecutionRouterPanel({
  report,
  loading,
  onRefresh
}: {
  report: FairExecutionRouterReport | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const tone = report ? routerTone(report.verdict) : "warn";
  return (
    <section className={`panel execution-router-panel ${report?.verdict ?? ""}`}>
      <header className="section-header">
        <div className="panel-heading compact">
          <Route size={20} />
          <h2>Fair execution router</h2>
        </div>
        <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="execution-router-refresh">
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          <span>{loading ? "Routing" : "Route"}</span>
        </button>
      </header>

      {report ? (
        <>
          <div className="execution-router-hero">
            <div>
              <span className="eyebrow">{report.symbol} / {titleize(report.scenario)} / route audit</span>
              <p>{report.summary}</p>
              <small>{report.judge_takeaway}</small>
            </div>
            <div className={`execution-router-score ${tone}`}>
              <span>Recommendation</span>
              <strong>{report.recommended_route}</strong>
              <small>{routerVerdictLabel(report.verdict)}</small>
            </div>
          </div>

          <div className="execution-router-stats">
            <DecisionStat label="Max route" value={formatUsd(report.max_route_notional_usdt, 0)} tone={report.execution_permitted ? "good" : "bad"} />
            <DecisionStat label="Liquidity budget" value={formatUsd(report.liquidity_budget_usdt, 0)} />
            <DecisionStat label="Fairness floor" value={`${formatNumber(report.fairness_floor_score, 0)}/100`} />
          </div>

          <div className="execution-route-grid">
            {report.route_candidates.map((route) => {
              const statusTone = routeStatusTone(route.status);
              return (
                <article key={route.route_type} className={`execution-route-card ${route.status}`}>
                  <header>
                    <div>
                      <span>{titleize(route.route_type)}</span>
                      <strong>{route.name}</strong>
                    </div>
                    <span className={`execution-route-pill ${statusTone}`}>{routeStatusLabel(route.status)}</span>
                  </header>
                  <p>{route.reason}</p>
                  <div className="execution-route-metrics">
                    <span>Slip {formatNumber(route.expected_slippage_bps, 1)} bps</span>
                    <span>Fill {formatPercent(route.fill_probability, 0)}</span>
                    <span>Fair {formatNumber(route.retail_fairness_score, 0)}</span>
                    <span>Max {formatUsd(route.max_notional_usdt, 0)}</span>
                  </div>
                  <div className="execution-route-risk">
                    <span>Leak {formatNumber(route.information_leakage_score, 0)}</span>
                    <span>Manip {formatNumber(route.manipulation_exposure_score, 0)}</span>
                    <span>{route.time_to_complete_seconds ? `${route.time_to_complete_seconds}s` : "Hold"}</span>
                  </div>
                  <ul>
                    {route.safeguards.slice(0, 3).map((safeguard) => (
                      <li key={safeguard}>{safeguard}</li>
                    ))}
                  </ul>
                </article>
              );
            })}
          </div>

          <div className="execution-router-footer">
            <div>
              <strong>Locks</strong>
              <ul>
                {report.locked_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
            <div>
              <strong>Verification</strong>
              <ul>
                {report.verification_notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Auditing route choices" : "Compare route fairness before paper execution"}</span>
        </div>
      )}
    </section>
  );
}

function redTeamVerdictLabel(verdict: RedTeamReport["verdict"]) {
  if (verdict === "kill_switch_ready") return "Kill-switch ready";
  if (verdict === "already_locked") return "Already locked";
  if (verdict === "watchlist") return "Watchlist";
  return "Resilient";
}

function redTeamTone(verdict: RedTeamReport["verdict"]): "good" | "warn" | "bad" {
  if (verdict === "resilient" || verdict === "already_locked" || verdict === "kill_switch_ready") return "good";
  return "warn";
}

function RedTeamPanel({
  report,
  loading,
  onRefresh
}: {
  report: RedTeamReport | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const tone = report ? redTeamTone(report.verdict) : "warn";
  return (
    <section className={`panel red-team-panel ${report?.verdict ?? ""}`}>
      <header className="section-header">
        <div className="panel-heading compact">
          <Shield size={20} />
          <h2>Market integrity red team</h2>
        </div>
        <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="red-team-refresh">
          <Target size={16} />
          <span>{loading ? "Probing" : "Replay"}</span>
        </button>
      </header>

      {report ? (
        <>
          <div className="red-team-hero">
            <div>
              <span className="eyebrow">{report.symbol} / {titleize(report.scenario)} adversarial replay</span>
              <p>{report.summary}</p>
              <small>{report.judge_takeaway}</small>
            </div>
            <div className={`red-team-score ${tone}`}>
              <span>Integrity</span>
              <strong>{formatNumber(report.integrity_score, 1)}</strong>
              <small>{redTeamVerdictLabel(report.verdict)}</small>
            </div>
          </div>

          <div className="red-team-stats">
            <DecisionStat label="Baseline gate" value={report.baseline_gate.split(" / ")[0] ?? report.baseline_gate} tone={report.verdict === "already_locked" ? "good" : undefined} />
            <DecisionStat label="Blocked probes" value={`${report.blocked_probe_count}/${report.probes.length}`} tone={report.blocked_probe_count > 0 ? "good" : "warn"} />
            <DecisionStat label="Watch probes" value={String(report.watch_probe_count)} tone={report.watch_probe_count > 0 ? "warn" : "good"} />
            <DecisionStat label="Worst probe" value={report.worst_probe} tone={report.blocked_probe_count > 0 ? "bad" : "warn"} />
          </div>

          <div className="red-team-grid">
            {report.probes.map((probe) => (
              <article key={probe.attack_vector} className={`red-team-probe ${probe.status}`}>
                <header>
                  <div>
                    <span>{titleize(probe.attack_vector)}</span>
                    <strong>{probe.name}</strong>
                  </div>
                  <span className={`red-team-pill ${probe.status}`}>{statusLabel(probe.status)}</span>
                </header>
                <p>{probe.explanation}</p>
                <div className="red-team-metrics">
                  <span>Cost {formatNumber(probe.stressed_hidden_cost_bps, 1)} bps</span>
                  <span>Anomaly {formatNumber(probe.stressed_anomaly_score, 0)}</span>
                  <span>Liquidity {formatNumber(probe.stressed_liquidity_score, 0)}</span>
                  <span>Stop {formatPercent(probe.stressed_stop_hit_probability, 0)}</span>
                </div>
                <div className="red-team-trigger">
                  <strong>{probe.first_trigger}</strong>
                  <small>{probe.mitigation}</small>
                </div>
              </article>
            ))}
          </div>

          <div className="red-team-footer">
            <div>
              <strong>Kill switches</strong>
              <ul>
                {report.kill_switches.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <strong>Next steps</strong>
              <ul>
                {report.recommended_next_steps.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Running adversarial probes" : "Replay manipulation-style market shocks for this audit"}</span>
        </div>
      )}
    </section>
  );
}

function evidenceClaimTone(status: AuditEvidencePack["core_claims"][number]["status"]): "good" | "warn" | "bad" {
  if (status === "verified") return "good";
  if (status === "watch") return "warn";
  return "bad";
}

function EvidencePackPanel({
  pack,
  loading,
  onRefresh
}: {
  pack: AuditEvidencePack | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const scoreTone = pack ? (pack.verification_score >= 84 ? "good" : pack.verification_score >= 68 ? "warn" : "bad") : "warn";

  async function copyPack() {
    if (!pack) return;
    await navigator.clipboard.writeText(JSON.stringify(pack, null, 2));
  }

  return (
    <section className="panel evidence-pack-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <Clipboard size={20} />
          <h2>Evidence pack</h2>
        </div>
        <div className="section-actions">
          <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="evidence-refresh">
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            <span>{loading ? "Packing" : "Refresh"}</span>
          </button>
          <button className="icon-button small" onClick={copyPack} disabled={!pack} data-testid="evidence-copy">
            <Clipboard size={16} />
            <span>Copy</span>
          </button>
        </div>
      </header>

      {pack ? (
        <>
          <div className="evidence-hero">
            <div>
              <span className="eyebrow">{pack.symbol} / {titleize(pack.scenario)} / {pack.package_version}</span>
              <p>{pack.headline}</p>
              <small>{pack.summary}</small>
            </div>
            <div className={`evidence-score ${scoreTone}`}>
              <span>Verification</span>
              <strong>{formatNumber(pack.verification_score, 1)}</strong>
              <small>{pack.audit_hash.slice(0, 12)}</small>
            </div>
          </div>

          <div className="evidence-stats">
            <DecisionStat label="Reports" value={String(pack.included_reports.length)} tone="good" />
            <DecisionStat label="Claims" value={String(pack.core_claims.length)} tone="good" />
            <DecisionStat label="Route" value={routerVerdictLabel(pack.fair_execution_router.verdict)} tone={routerTone(pack.fair_execution_router.verdict)} />
            <DecisionStat label="Readiness" value={`${formatNumber(pack.counterfactuals.readiness_score, 1)}/100`} tone={pack.counterfactuals.verdict === "do_not_unlock" ? "good" : "warn"} />
          </div>

          <div className="evidence-grid">
            {pack.core_claims.map((claim) => (
              <article key={claim.label} className={`evidence-claim ${claim.status}`}>
                <header>
                  <strong>{claim.label}</strong>
                  <span className={evidenceClaimTone(claim.status)}>{claim.status}</span>
                </header>
                <p>{claim.explanation}</p>
                <code>{claim.evidence_url}</code>
              </article>
            ))}
          </div>

          <div className="evidence-links">
            {Object.entries(pack.evidence_urls).slice(0, 9).map(([label, url]) => (
              <div key={label}>
                <span>{titleize(label)}</span>
                <code>{url}</code>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="empty-state compact-empty">
          <RefreshCw size={18} className={loading ? "spin" : ""} />
          <span>{loading ? "Bundling audit evidence" : "Generate a copyable proof bundle for this audit"}</span>
        </div>
      )}
    </section>
  );
}

function AuditVaultPanel({
  audits,
  loading,
  onRefresh,
  onOpen
}: {
  audits: Decision[];
  loading: boolean;
  onRefresh: () => void;
  onOpen: (decision: Decision) => void;
}) {
  const recentAudits = audits.slice(-6).reverse();
  return (
    <section className="panel audit-vault-panel">
      <header className="section-header">
        <div className="panel-heading compact">
          <History size={20} />
          <h2>Audit vault</h2>
        </div>
        <button className="icon-button small" onClick={onRefresh} disabled={loading} data-testid="audit-refresh">
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          <span>Refresh</span>
        </button>
      </header>

      {recentAudits.length ? (
        <div className="audit-list">
          {recentAudits.map((item) => (
            <article key={item.audit_hash} className="audit-row">
              <div>
                <span>{item.symbol} / {titleize(item.scenario)}</span>
                <strong>{item.audit_hash.slice(0, 14)}</strong>
              </div>
              <div className={`audit-status ${item.status}`}>{statusLabel(item.status)}</div>
              <button className="mini-button" onClick={() => onOpen(item)} data-testid={`open-audit-${item.audit_hash.slice(0, 8)}`}>
                Review
              </button>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <Database size={18} />
          <span>{loading ? "Loading audits" : "No audits yet"}</span>
        </div>
      )}
    </section>
  );
}

function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <div className="top-strip" />
      {children}
    </div>
  );
}

export function FairFlowDashboard() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [scenario, setScenario] = useState<Scenario>("calm");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [comparison, setComparison] = useState<ScenarioComparison | null>(null);
  const [marketSeries, setMarketSeries] = useState<MarketSeries | null>(null);
  const [portfolio, setPortfolio] = useState<PaperPortfolio | null>(null);
  const [mission, setMission] = useState<AgentMission | null>(null);
  const [receipt, setReceipt] = useState<FairnessReceipt | null>(null);
  const [cohortReport, setCohortReport] = useState<RetailCohortReport | null>(null);
  const [impactReport, setImpactReport] = useState<ImpactLedgerReport | null>(null);
  const [anchorProof, setAnchorProof] = useState<AnchorProof | null>(null);
  const [judgeBrief, setJudgeBrief] = useState<JudgeBrief | null>(null);
  const [readinessReport, setReadinessReport] = useState<HackathonReadinessReport | null>(null);
  const [submissionKit, setSubmissionKit] = useState<HackathonSubmissionKit | null>(null);
  const [provenanceCard, setProvenanceCard] = useState<ModelProvenanceCard | null>(null);
  const [evidencePack, setEvidencePack] = useState<AuditEvidencePack | null>(null);
  const [executionRouter, setExecutionRouter] = useState<FairExecutionRouterReport | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistReport | null>(null);
  const [watchlistSymbols, setWatchlistSymbols] = useState(defaultWatchlistSymbols);
  const [includeLiveComparison, setIncludeLiveComparison] = useState(false);
  const [audits, setAudits] = useState<Decision[]>([]);
  const [policyInputs, setPolicyInputs] = useState({
    min_fairness_score: 80,
    max_hidden_cost_bps: 8,
    max_anomaly_score: 45,
    min_liquidity_score: 55,
    max_leverage: 3,
    max_stop_hit_probability: 0.45
  });
  const [riskInputs, setRiskInputs] = useState({
    account_equity_usdt: 10_000,
    risk_budget_pct: 1,
    max_notional_pct: 25
  });
  const [riskSizing, setRiskSizing] = useState<RiskSizing | null>(null);
  const [policyReport, setPolicyReport] = useState<GuardrailPolicyReport | null>(null);
  const [policyStressReport, setPolicyStressReport] = useState<PolicyStressReport | null>(null);
  const [counterfactualReport, setCounterfactualReport] = useState<CounterfactualFairnessReport | null>(null);
  const [redTeamReport, setRedTeamReport] = useState<RedTeamReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [missionLoading, setMissionLoading] = useState(false);
  const [receiptLoading, setReceiptLoading] = useState(false);
  const [cohortLoading, setCohortLoading] = useState(false);
  const [impactLoading, setImpactLoading] = useState(false);
  const [anchorLoading, setAnchorLoading] = useState(false);
  const [judgeLoading, setJudgeLoading] = useState(false);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [submissionLoading, setSubmissionLoading] = useState(false);
  const [provenanceLoading, setProvenanceLoading] = useState(false);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [executionRouterLoading, setExecutionRouterLoading] = useState(false);
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [policyLoading, setPolicyLoading] = useState(false);
  const [policyStressLoading, setPolicyStressLoading] = useState(false);
  const [counterfactualLoading, setCounterfactualLoading] = useState(false);
  const [redTeamLoading, setRedTeamLoading] = useState(false);
  const [streaming, setStreaming] = useState(true);
  const [autoMission, setAutoMission] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [sizingLoading, setSizingLoading] = useState(false);
  const [pendingScenario, setPendingScenario] = useState<Scenario | null>(null);
  const [pendingSymbol, setPendingSymbol] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [order, setOrder] = useState<PaperOrder | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const requestIdRef = useRef(0);
  const seriesRequestIdRef = useRef(0);
  const missionRequestIdRef = useRef(0);
  const receiptRequestIdRef = useRef(0);
  const cohortRequestIdRef = useRef(0);
  const anchorRequestIdRef = useRef(0);
  const judgeRequestIdRef = useRef(0);
  const readinessRequestIdRef = useRef(0);
  const submissionRequestIdRef = useRef(0);
  const provenanceRequestIdRef = useRef(0);
  const evidenceRequestIdRef = useRef(0);
  const executionRouterRequestIdRef = useRef(0);
  const policyStressRequestIdRef = useRef(0);
  const counterfactualRequestIdRef = useRef(0);
  const redTeamRequestIdRef = useRef(0);
  const noticeTimerRef = useRef<number | null>(null);

  function showNotice(message: string) {
    if (noticeTimerRef.current) window.clearTimeout(noticeTimerRef.current);
    setNotice(message);
    noticeTimerRef.current = window.setTimeout(() => setNotice(null), 1800);
  }

  async function loadDecision(nextSymbol = symbol, nextScenario = scenario) {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setPendingSymbol(nextSymbol);
    setPendingScenario(nextScenario);
    setError(null);
    setNotice(null);
    setOrder(null);
    setRiskSizing(null);
    setMission(null);
    setReceipt(null);
    setCohortReport(null);
    setAnchorProof(null);
    setJudgeBrief(null);
    setReadinessReport(null);
    setSubmissionKit(null);
    setProvenanceCard(null);
    setEvidencePack(null);
    setExecutionRouter(null);
    setPolicyReport(null);
    setPolicyStressReport(null);
    setCounterfactualReport(null);
    setRedTeamReport(null);
    try {
      const payload = await fetchDecision({ symbol: nextSymbol, category: "linear", scenario: nextScenario });
      if (requestId !== requestIdRef.current) return;
      setDecision(payload);
      showNotice(`Report updated for ${nextSymbol} / ${titleize(nextScenario)}`);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to load FairFlow analysis");
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setPendingSymbol(null);
        setPendingScenario(null);
      }
    }
  }

  async function loadComparison(nextSymbol = symbol, withLive = includeLiveComparison) {
    setComparing(true);
    try {
      setComparison(await fetchScenarioComparison(nextSymbol, withLive));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to compare scenarios");
    } finally {
      setComparing(false);
    }
  }

  async function loadMarketSeries(nextSymbol = symbol, nextScenario = scenario) {
    const requestId = seriesRequestIdRef.current + 1;
    seriesRequestIdRef.current = requestId;
    setChartLoading(true);
    try {
      const payload = await fetchMarketSeries({ symbol: nextSymbol, category: "linear", scenario: nextScenario });
      if (requestId !== seriesRequestIdRef.current) return;
      setMarketSeries(payload);
    } catch (err) {
      if (requestId !== seriesRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to stream market candles");
    } finally {
      if (requestId === seriesRequestIdRef.current) setChartLoading(false);
    }
  }

  async function refreshAudits() {
    setAuditLoading(true);
    try {
      setAudits(await fetchAudits());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load audit vault");
    } finally {
      setAuditLoading(false);
    }
  }

  async function refreshPortfolio(nextScenario = scenario) {
    setPortfolioLoading(true);
    try {
      setPortfolio(await fetchPaperPortfolio(nextScenario));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load paper portfolio");
    } finally {
      setPortfolioLoading(false);
    }
  }

  async function loadWatchlist(nextScenario = scenario) {
    setWatchlistLoading(true);
    try {
      setWatchlist(await fetchWatchlist(watchlistSymbols, nextScenario));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to scan watchlist");
    } finally {
      setWatchlistLoading(false);
    }
  }

  async function loadImpactLedger() {
    setImpactLoading(true);
    try {
      setImpactReport(await fetchImpactLedger(50));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load impact ledger");
    } finally {
      setImpactLoading(false);
    }
  }

  function toggleWatchlistSymbol(nextSymbol: string) {
    setWatchlistSymbols((current) => {
      if (current.includes(nextSymbol)) {
        if (current.length === 1) {
          showNotice("Keep at least one market in the scanner");
          return current;
        }
        return current.filter((item) => item !== nextSymbol);
      }
      return [...current, nextSymbol];
    });
  }

  async function runMission(targetDecision = decision, silent = false) {
    const requestId = missionRequestIdRef.current + 1;
    missionRequestIdRef.current = requestId;
    setMissionLoading(true);
    const targetCategory = (targetDecision?.category as "spot" | "linear" | "inverse" | undefined) ?? "linear";
    try {
      const payload = await runAgentMission({
        symbol: targetDecision?.symbol ?? symbol,
        category: targetCategory,
        scenario: (targetDecision?.scenario as Scenario | undefined) ?? scenario,
        auditHash: targetDecision?.audit_hash
      });
      if (requestId !== missionRequestIdRef.current) return;
      setMission(payload);
      if (!silent) showNotice(`Mission updated: ${titleize(payload.autonomy_level)}`);
    } catch (err) {
      if (requestId !== missionRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to run agent mission");
    } finally {
      if (requestId === missionRequestIdRef.current) setMissionLoading(false);
    }
  }

  async function loadReceipt(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = receiptRequestIdRef.current + 1;
    receiptRequestIdRef.current = requestId;
    setReceiptLoading(true);
    try {
      const payload = await fetchFairnessReceipt(targetDecision.audit_hash);
      if (requestId !== receiptRequestIdRef.current) return;
      setReceipt(payload);
    } catch (err) {
      if (requestId !== receiptRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to generate fairness receipt");
    } finally {
      if (requestId === receiptRequestIdRef.current) setReceiptLoading(false);
    }
  }

  async function loadRetailCohorts(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = cohortRequestIdRef.current + 1;
    cohortRequestIdRef.current = requestId;
    setCohortLoading(true);
    try {
      const payload = await fetchRetailCohorts(targetDecision.audit_hash);
      if (requestId !== cohortRequestIdRef.current) return;
      setCohortReport(payload);
    } catch (err) {
      if (requestId !== cohortRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to test retail cohorts");
    } finally {
      if (requestId === cohortRequestIdRef.current) setCohortLoading(false);
    }
  }

  async function loadAnchorProof(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = anchorRequestIdRef.current + 1;
    anchorRequestIdRef.current = requestId;
    setAnchorLoading(true);
    try {
      const payload = await fetchAnchorProof(targetDecision.audit_hash);
      if (requestId !== anchorRequestIdRef.current) return;
      setAnchorProof(payload);
    } catch (err) {
      if (requestId !== anchorRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to prepare anchor proof");
    } finally {
      if (requestId === anchorRequestIdRef.current) setAnchorLoading(false);
    }
  }

  async function loadJudgeBrief(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = judgeRequestIdRef.current + 1;
    judgeRequestIdRef.current = requestId;
    setJudgeLoading(true);
    try {
      const payload = await fetchJudgeBrief(targetDecision.audit_hash);
      if (requestId !== judgeRequestIdRef.current) return;
      setJudgeBrief(payload);
    } catch (err) {
      if (requestId !== judgeRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to prepare judge brief");
    } finally {
      if (requestId === judgeRequestIdRef.current) setJudgeLoading(false);
    }
  }

  async function loadHackathonReadiness(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = readinessRequestIdRef.current + 1;
    readinessRequestIdRef.current = requestId;
    setReadinessLoading(true);
    try {
      const payload = await fetchHackathonReadiness(targetDecision.audit_hash);
      if (requestId !== readinessRequestIdRef.current) return;
      setReadinessReport(payload);
    } catch (err) {
      if (requestId !== readinessRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to build hackathon readiness runbook");
    } finally {
      if (requestId === readinessRequestIdRef.current) setReadinessLoading(false);
    }
  }

  async function loadSubmissionKit(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = submissionRequestIdRef.current + 1;
    submissionRequestIdRef.current = requestId;
    setSubmissionLoading(true);
    try {
      const payload = await fetchSubmissionKit(targetDecision.audit_hash);
      if (requestId !== submissionRequestIdRef.current) return;
      setSubmissionKit(payload);
    } catch (err) {
      if (requestId !== submissionRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to package submission kit");
    } finally {
      if (requestId === submissionRequestIdRef.current) setSubmissionLoading(false);
    }
  }

  async function loadModelProvenance(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = provenanceRequestIdRef.current + 1;
    provenanceRequestIdRef.current = requestId;
    setProvenanceLoading(true);
    try {
      const payload = await fetchModelProvenance(targetDecision.audit_hash);
      if (requestId !== provenanceRequestIdRef.current) return;
      setProvenanceCard(payload);
    } catch (err) {
      if (requestId !== provenanceRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to trace model provenance");
    } finally {
      if (requestId === provenanceRequestIdRef.current) setProvenanceLoading(false);
    }
  }

  async function loadExecutionRouter(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = executionRouterRequestIdRef.current + 1;
    executionRouterRequestIdRef.current = requestId;
    setExecutionRouterLoading(true);
    try {
      const payload = await fetchExecutionRouter(targetDecision.audit_hash);
      if (requestId !== executionRouterRequestIdRef.current) return;
      setExecutionRouter(payload);
    } catch (err) {
      if (requestId !== executionRouterRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to audit fair execution routes");
    } finally {
      if (requestId === executionRouterRequestIdRef.current) setExecutionRouterLoading(false);
    }
  }

  async function loadPolicyStress(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = policyStressRequestIdRef.current + 1;
    policyStressRequestIdRef.current = requestId;
    setPolicyStressLoading(true);
    try {
      const payload = await fetchPolicyStress(targetDecision.audit_hash);
      if (requestId !== policyStressRequestIdRef.current) return;
      setPolicyStressReport(payload);
    } catch (err) {
      if (requestId !== policyStressRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to stress test policy presets");
    } finally {
      if (requestId === policyStressRequestIdRef.current) setPolicyStressLoading(false);
    }
  }

  async function loadCounterfactuals(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = counterfactualRequestIdRef.current + 1;
    counterfactualRequestIdRef.current = requestId;
    setCounterfactualLoading(true);
    try {
      const payload = await fetchCounterfactuals(targetDecision.audit_hash);
      if (requestId !== counterfactualRequestIdRef.current) return;
      setCounterfactualReport(payload);
    } catch (err) {
      if (requestId !== counterfactualRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to trace counterfactual fairness");
    } finally {
      if (requestId === counterfactualRequestIdRef.current) setCounterfactualLoading(false);
    }
  }

  async function loadRedTeamReport(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = redTeamRequestIdRef.current + 1;
    redTeamRequestIdRef.current = requestId;
    setRedTeamLoading(true);
    try {
      const payload = await fetchRedTeamReport(targetDecision.audit_hash);
      if (requestId !== redTeamRequestIdRef.current) return;
      setRedTeamReport(payload);
    } catch (err) {
      if (requestId !== redTeamRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to run market integrity red team");
    } finally {
      if (requestId === redTeamRequestIdRef.current) setRedTeamLoading(false);
    }
  }

  async function loadEvidencePack(targetDecision = decision) {
    if (!targetDecision) return;
    const requestId = evidenceRequestIdRef.current + 1;
    evidenceRequestIdRef.current = requestId;
    setEvidenceLoading(true);
    try {
      const payload = await fetchEvidencePack(targetDecision.audit_hash);
      if (requestId !== evidenceRequestIdRef.current) return;
      setEvidencePack(payload);
    } catch (err) {
      if (requestId !== evidenceRequestIdRef.current) return;
      setError(err instanceof Error ? err.message : "Unable to assemble evidence pack");
    } finally {
      if (requestId === evidenceRequestIdRef.current) setEvidenceLoading(false);
    }
  }

  async function resetPortfolio() {
    setPortfolioLoading(true);
    try {
      setPortfolio(await resetPaperPortfolio());
      setOrder(null);
      showNotice("Paper portfolio reset");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reset paper portfolio");
    } finally {
      setPortfolioLoading(false);
    }
  }

  async function recalculateSizing(targetDecision = decision) {
    if (!targetDecision) return;
    setSizingLoading(true);
    try {
      setRiskSizing(
        await calculateRiskSize({
          audit_hash: targetDecision.audit_hash,
          ...riskInputs
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to calculate risk size");
    } finally {
      setSizingLoading(false);
    }
  }

  function updateRiskInput(field: keyof typeof riskInputs, value: number) {
    if (!Number.isFinite(value)) return;
    setRiskInputs((current) => ({ ...current, [field]: value }));
  }

  function updatePolicyInput(field: keyof typeof policyInputs, value: number) {
    if (!Number.isFinite(value)) return;
    setPolicyInputs((current) => ({ ...current, [field]: value }));
  }

  async function evaluateCurrentPolicy(targetDecision = decision) {
    if (!targetDecision) return;
    setPolicyLoading(true);
    try {
      setPolicyReport(
        await evaluatePolicy({
          audit_hash: targetDecision.audit_hash,
          ...policyInputs
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to evaluate policy");
    } finally {
      setPolicyLoading(false);
    }
  }

  function selectScenario(nextScenario: Scenario) {
    if (nextScenario === scenario) {
      void loadDecision(symbol, nextScenario);
      return;
    }
    setScenario(nextScenario);
  }

  function openAudit(auditDecision: Decision) {
    setDecision(auditDecision);
    setSymbol(auditDecision.symbol);
    setScenario(auditDecision.scenario as Scenario);
    setOrder(null);
    setRiskSizing(null);
    setMission(null);
    setReceipt(null);
    setCohortReport(null);
    setAnchorProof(null);
    setJudgeBrief(null);
    setReadinessReport(null);
    setSubmissionKit(null);
    setProvenanceCard(null);
    setEvidencePack(null);
    setExecutionRouter(null);
    setPolicyReport(null);
    setPolicyStressReport(null);
    setCounterfactualReport(null);
    setRedTeamReport(null);
    showNotice(`Audit loaded for ${auditDecision.symbol} / ${titleize(auditDecision.scenario)}`);
  }

  function openWatchlistItem(item: WatchlistItem) {
    if (item.scenario !== scenario) setScenario(item.scenario as Scenario);
    if (item.symbol === symbol) {
      void loadDecision(item.symbol, item.scenario as Scenario);
    } else {
      setSymbol(item.symbol);
    }
    showNotice(`Opening ${item.symbol}: ${item.rank_reason}`);
  }

  async function simulateOrder() {
    if (!decision) return;
    setSubmitting(true);
    try {
      setOrder(await simulatePaperOrder(decision.audit_hash));
      await refreshPortfolio(scenario);
      if (autoMission) void runMission(decision, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to simulate order");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleMissionAction(action: AgentAction) {
    if (!action.permitted) {
      showNotice(`${action.label} is locked by the mission gate`);
      return;
    }

    if (action.action_type === "refresh_market") {
      await loadDecision(symbol, scenario);
      await loadMarketSeries(symbol, scenario);
      showNotice("Market feed refreshed");
      return;
    }
    if (action.action_type === "compare_scenarios") {
      await loadComparison(symbol, includeLiveComparison);
      showNotice("Scenario lab refreshed");
      return;
    }
    if (action.action_type === "size_position") {
      await recalculateSizing(decision);
      showNotice("Risk sizing recalculated");
      return;
    }
    if (action.action_type === "paper_execute") {
      await simulateOrder();
      return;
    }
    if (action.action_type === "reset_portfolio") {
      await resetPortfolio();
      if (decision) void runMission(decision, true);
      return;
    }
    if (action.action_type === "review_audit") {
      showNotice(`Audit ready: ${decision?.audit_hash.slice(0, 12) ?? mission?.decision.audit_hash.slice(0, 12)}`);
      return;
    }
    showNotice("Mission is holding execution");
  }

  useEffect(() => {
    void loadDecision(symbol, scenario);
  }, [symbol, scenario]);

  useEffect(() => {
    void loadMarketSeries(symbol, scenario);
  }, [symbol, scenario]);

  useEffect(() => {
    void refreshPortfolio(scenario);
  }, [scenario]);

  useEffect(() => {
    void loadWatchlist(scenario);
  }, [scenario, watchlistSymbols.join(",")]);

  useEffect(() => {
    if (!streaming) return;
    const delayMs = scenario === "live" ? 5000 : 8000;
    const timer = window.setInterval(() => {
      void loadMarketSeries(symbol, scenario);
      void refreshPortfolio(scenario);
    }, delayMs);
    return () => window.clearInterval(timer);
  }, [streaming, symbol, scenario]);

  useEffect(() => {
    void loadComparison(symbol, includeLiveComparison);
  }, [symbol, includeLiveComparison]);

  useEffect(() => {
    void refreshAudits();
  }, [decision?.audit_hash]);

  useEffect(() => {
    void loadImpactLedger();
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadReceipt(decision);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadRetailCohorts(decision);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadAnchorProof(decision);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadJudgeBrief(decision);
    }, 200);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadHackathonReadiness(decision);
    }, 230);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadSubmissionKit(decision);
    }, 260);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadModelProvenance(decision);
    }, 240);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadPolicyStress(decision);
    }, 280);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadExecutionRouter(decision);
    }, 290);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadCounterfactuals(decision);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadRedTeamReport(decision);
    }, 320);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void loadEvidencePack(decision);
    }, 420);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash]);

  useEffect(() => {
    if (!autoMission || !decision) return;
    void runMission(decision, true);
  }, [autoMission, decision?.audit_hash]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void recalculateSizing(decision);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [decision?.audit_hash, riskInputs.account_equity_usdt, riskInputs.risk_budget_pct, riskInputs.max_notional_pct]);

  useEffect(() => {
    if (!decision) return;
    const timer = window.setTimeout(() => {
      void evaluateCurrentPolicy(decision);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [
    decision?.audit_hash,
    policyInputs.min_fairness_score,
    policyInputs.max_hidden_cost_bps,
    policyInputs.max_anomaly_score,
    policyInputs.min_liquidity_score,
    policyInputs.max_leverage,
    policyInputs.max_stop_hit_probability
  ]);

  const sentinelScore = useMemo(() => {
    if (!decision) return 0;
    const sentinel = decision.agents.find((agent) => agent.name === "Manipulation Sentinel");
    return sentinel ? 100 - sentinel.score : 0;
  }, [decision]);
  const fairnessTone = decision ? verdictTone(decision.fairness_passport.verdict) : "warn";
  const pendingLabel = `${pendingSymbol ?? symbol} / ${titleize(pendingScenario ?? scenario)}`;

  return (
    <AppShell>
      <header className="app-header">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Shield size={24} />
          </div>
          <div>
            <span className="eyebrow">BGA AI Trading & Strategy Track</span>
            <h1>FairFlow Guardian</h1>
          </div>
        </div>
        <div className="header-actions">
          <select value={symbol} onChange={(event) => setSymbol(event.target.value)} aria-label="Select symbol">
            {cryptoUniverse.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <button className="icon-button labeled" onClick={() => loadDecision(symbol, scenario)} disabled={loading}>
            <RefreshCw size={18} className={loading ? "spin" : ""} />
            <span>Refresh</span>
          </button>
        </div>
      </header>

      <main aria-busy={loading}>
        <MarketTape decision={decision} comparison={comparison} loading={loading} />

        <section className="control-band">
          <div className="segmented" aria-label="Scenario selector">
            {scenarios.map((item) => (
              <button
                key={item.value}
                className={`${scenario === item.value ? "active" : ""} ${loading && pendingScenario === item.value ? "pending" : ""}`}
                onClick={() => selectScenario(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className={`source-line ${loading ? "loading" : ""}`}>
            {loading ? <RefreshCw size={16} className="spin" /> : <Activity size={16} />}
            <span>{loading ? `Analyzing ${pendingLabel}` : decision ? `${decision.source} / ${new Date(decision.generated_at).toLocaleTimeString()}` : "Waiting for analysis"}</span>
          </div>
        </section>

        {error && (
          <section className="error-panel">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </section>
        )}

        {notice && !loading && (
          <section className="analysis-notice" aria-live="polite">
            <CheckCircle2 size={18} />
            <span>{notice}</span>
          </section>
        )}

        {loading && decision && (
          <section className="analysis-progress" aria-live="polite">
            <RefreshCw size={18} className="spin" />
            <span>Running agents for {pendingLabel}</span>
          </section>
        )}

        {loading && !decision ? (
          <section className="loading-panel">
            <RefreshCw size={22} className="spin" />
            <span>Running market, strategy, manipulation, and risk agents...</span>
          </section>
        ) : decision ? (
          <>
            <CompetitionRunwayPanel
              decision={decision}
              readiness={readinessReport}
              submissionKit={submissionKit}
              evidencePack={evidencePack}
              executionRouter={executionRouter}
              onSelectScenario={selectScenario}
            />

            <section className={`decision-panel ${loading ? "is-loading" : ""}`}>
              <div className="decision-copy">
                <DecisionBadge decision={decision} />
                <h2>{decision.final_action.replace("_", " ")}</h2>
                <p>{decision.summary}</p>
                <div className="decision-stats">
                  <DecisionStat
                    label="Fairness"
                    value={`${Math.round(decision.fairness_passport.score)}/100`}
                    tone={fairnessTone}
                  />
                  <DecisionStat
                    label="Hidden cost"
                    value={`${formatNumber(decision.fairness_passport.estimated_hidden_cost_bps, 1)} bps`}
                    tone={decision.fairness_passport.estimated_hidden_cost_bps < 8 ? "good" : decision.fairness_passport.estimated_hidden_cost_bps < 18 ? "warn" : "bad"}
                  />
                  <DecisionStat label="Audit" value={decision.audit_hash.slice(0, 10)} />
                </div>
              </div>
              <DecisionVisual decision={decision} sentinelScore={sentinelScore} />
              <div className="decision-actions">
                <button
                  className="execute-button"
                  disabled={decision.status !== "approved" || submitting}
                  onClick={simulateOrder}
                >
                  {decision.status === "approved" ? <Play size={18} /> : <PauseCircle size={18} />}
                  <span>{submitting ? "Submitting" : decision.status === "approved" ? "Paper execute" : "Execution locked"}</span>
                </button>
                <div className="proposal-mini">
                  <span>Strategy</span>
                  <strong>{decision.proposal.action.replace("_", " ")}</strong>
                </div>
              </div>
            </section>

            {order && (
              <section className={`order-panel ${order.accepted ? "accepted" : "rejected"}`}>
                {order.accepted ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
                <span>{order.message}</span>
                <code>{order.client_order_id}</code>
              </section>
            )}

            <JudgeModePanel
              brief={judgeBrief}
              loading={judgeLoading}
              onRefresh={() => loadJudgeBrief(decision)}
            />

            <HackathonReadinessPanel
              report={readinessReport}
              loading={readinessLoading}
              onRefresh={() => loadHackathonReadiness(decision)}
            />

            <SubmissionKitPanel
              kit={submissionKit}
              loading={submissionLoading}
              onRefresh={() => loadSubmissionKit(decision)}
            />

            <EvidencePackPanel
              pack={evidencePack}
              loading={evidenceLoading}
              onRefresh={() => loadEvidencePack(decision)}
            />

            <FairExecutionRouterPanel
              report={executionRouter}
              loading={executionRouterLoading}
              onRefresh={() => loadExecutionRouter(decision)}
            />

            <ProvenancePanel
              card={provenanceCard}
              loading={provenanceLoading}
              onRefresh={() => loadModelProvenance(decision)}
            />

            <RedTeamPanel
              report={redTeamReport}
              loading={redTeamLoading}
              onRefresh={() => loadRedTeamReport(decision)}
            />

            <ImpactLedgerPanel
              report={impactReport}
              loading={impactLoading}
              onRefresh={loadImpactLedger}
            />

            <AgentSwarmPanel
              decision={decision}
              mission={mission}
              loading={missionLoading}
              onRunMission={() => runMission(decision)}
            />

            <WatchlistScannerPanel
              report={watchlist}
              loading={watchlistLoading}
              activeSymbol={symbol}
              selectedSymbols={watchlistSymbols}
              universe={cryptoUniverse}
              onRefresh={() => loadWatchlist(scenario)}
              onOpen={openWatchlistItem}
              onToggleSymbol={toggleWatchlistSymbol}
            />

            <AgentMissionPanel
              mission={mission}
              loading={missionLoading}
              autoMission={autoMission}
              onToggleAutoMission={setAutoMission}
              onRun={() => runMission(decision)}
              onAction={handleMissionAction}
            />

            <PriceChartPanel
              series={marketSeries}
              decision={decision}
              loading={chartLoading}
              streaming={streaming}
              onToggleStreaming={setStreaming}
              onRefresh={() => loadMarketSeries(symbol, scenario)}
            />

            <PortfolioPanel
              portfolio={portfolio}
              loading={portfolioLoading}
              onRefresh={() => refreshPortfolio(scenario)}
              onReset={resetPortfolio}
            />

            <section className="metrics-grid">
              <MetricTile
                label="Last price"
                value={formatUsd(decision.metrics.price, 2)}
                detail={`${decision.symbol} / ${decision.category}`}
                className="price-tile"
              />
              <MetricTile
                label="Liquidity score"
                value={`${Math.round(decision.metrics.liquidity_score)}/100`}
                detail={`${formatUsd(decision.metrics.top_depth_usd)} top depth`}
                tone={decision.metrics.liquidity_score > 70 ? "good" : decision.metrics.liquidity_score > 45 ? "warn" : "bad"}
              />
              <MetricTile
                label="Manipulation risk"
                value={`${Math.round(sentinelScore)}/100`}
                detail={`${titleize(decision.fairness_passport.checks.find((check) => check.name === "Manipulation exposure")?.status ?? "watch")} exposure`}
                tone={sentinelScore < 35 ? "good" : sentinelScore < 62 ? "warn" : "bad"}
              />
              <MetricTile
                label="Spread"
                value={`${formatNumber(decision.metrics.spread_bps, 1)} bps`}
                detail={`${formatNumber(decision.metrics.impact_25k_bps, 1)} bps impact`}
              />
              <MetricTile
                label="Volatility"
                value={`${formatNumber(decision.metrics.realized_volatility_pct, 2)}%`}
                detail={`${formatNumber(decision.metrics.range_24h_pct, 2)}% range`}
              />
              <MetricTile
                label="Funding"
                value={`${formatNumber(decision.metrics.funding_rate_bps, 2)} bps`}
                detail={`${formatNumber(decision.metrics.order_book_imbalance * 100, 1)}% book skew`}
              />
            </section>

            <section className="workbench-grid">
              <ScenarioLabPanel
                comparison={comparison}
                loading={comparing}
                includeLive={includeLiveComparison}
                onToggleLive={setIncludeLiveComparison}
                onRefresh={() => loadComparison(symbol, includeLiveComparison)}
                onOpen={(nextScenario) => selectScenario(nextScenario)}
              />
              <div className="workbench-side">
                <RiskSizingPanel
                  decision={decision}
                  sizing={riskSizing}
                  loading={sizingLoading}
                  inputs={riskInputs}
                  onChange={updateRiskInput}
                  onRecalculate={() => recalculateSizing(decision)}
                />
                <PolicyStudioPanel
                  report={policyReport}
                  loading={policyLoading}
                  inputs={policyInputs}
                  onChange={updatePolicyInput}
                  onEvaluate={() => evaluateCurrentPolicy(decision)}
                />
                <PolicyStressLabPanel
                  report={policyStressReport}
                  loading={policyStressLoading}
                  onRefresh={() => loadPolicyStress(decision)}
                />
                <CounterfactualLabPanel
                  report={counterfactualReport}
                  loading={counterfactualLoading}
                  onRefresh={() => loadCounterfactuals(decision)}
                />
                <AuditVaultPanel
                  audits={audits}
                  loading={auditLoading}
                  onRefresh={refreshAudits}
                  onOpen={openAudit}
                />
              </div>
            </section>

            <FairnessPassportPanel passport={decision.fairness_passport} />

            <FairnessReceiptPanel
              receipt={receipt}
              loading={receiptLoading}
              onRefresh={() => loadReceipt(decision)}
            />

            <RetailCohortPanel
              report={cohortReport}
              loading={cohortLoading}
              onRefresh={() => loadRetailCohorts(decision)}
            />

            <AnchorProofPanel
              proof={anchorProof}
              loading={anchorLoading}
              onRefresh={() => loadAnchorProof(decision)}
            />

            <DecisionTracePanel steps={decision.decision_trace} />

            <AICommitteePanel decision={decision} />

            <section className="workspace-grid">
              <div className="panel">
                <div className="panel-heading">
                  <Shield size={20} />
                  <h2>Agent review</h2>
                </div>
                <div className="agent-grid">
                  {decision.agents.map((agent) => (
                    <AgentCard key={agent.name} agent={agent} />
                  ))}
                </div>
              </div>

              <aside className="panel side-panel">
                <div className="panel-heading">
                  <Gauge size={20} />
                  <h2>Execution quality</h2>
                </div>
                <GaugeBar label="Liquidity" value={decision.metrics.liquidity_score} />
                <GaugeBar label="Risk pressure" value={sentinelScore} invert />
                <GaugeBar label="Strategy confidence" value={decision.proposal.confidence * 100} />
                <div className="book-imbalance">
                  <span>Book imbalance</span>
                  <strong>{formatNumber(decision.metrics.order_book_imbalance * 100, 1)}%</strong>
                </div>
              </aside>
            </section>

            <section className="workspace-grid">
              <div className="panel">
                <div className="panel-heading">
                  <BarChart3 size={20} />
                  <h2>Stress test</h2>
                </div>
                <StressTable rows={decision.stress_tests} />
              </div>

              <aside className="panel side-panel">
                <div className="panel-heading">
                  <Shield size={20} />
                  <h2>Safeguards</h2>
                </div>
                <ul className="safeguards">
                  {decision.safeguards.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </aside>
            </section>

            <AuditBox decision={decision} />
          </>
        ) : null}
      </main>
    </AppShell>
  );
}
