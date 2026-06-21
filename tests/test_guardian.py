from fastapi.testclient import TestClient

from fairflow_api import main as main_module
from fairflow_api.agents import build_decision
from fairflow_api.audit_store import AuditLedger
from fairflow_api.bybit import fallback_snapshot


client = TestClient(main_module.app)


def test_calm_scenario_can_be_approved_or_observed_without_safety_block():
    decision = build_decision(fallback_snapshot(scenario="calm"))

    assert decision.status in {"approved", "observe"}
    assert decision.audit_hash
    assert len(decision.audit_hash) == 64
    assert any(agent.name == "Risk Guardian" for agent in decision.agents)
    assert decision.ai_committee.ml_regime.model_version.startswith("nearest-centroid")
    assert decision.ai_committee.execution_plan.order_style in {"limit", "none"}
    assert any(agent.name == "Uncertainty Forecast Agent" for agent in decision.agents)
    assert len(decision.decision_trace) == 7
    assert decision.decision_trace[-1].title == "Final audited outcome"
    assert decision.fairness_passport.score >= 70
    assert decision.fairness_passport.verdict in {"fair_to_execute", "wait_for_parity"}
    assert any(check.name == "Information parity" for check in decision.fairness_passport.checks)


def test_manipulated_scenario_is_not_executable():
    decision = build_decision(fallback_snapshot(scenario="manipulated"))

    assert decision.final_action == "NO_TRADE"
    assert decision.status in {"blocked", "observe"}
    assert any(agent.name == "Manipulation Sentinel" and agent.status in {"watch", "block"} for agent in decision.agents)
    assert decision.ai_committee.anomaly.status == "extreme"
    assert decision.ai_committee.ml_regime.regime == "fragile_liquidity"
    assert any(agent.name == "ML Manipulation Analyst" and agent.status == "block" for agent in decision.agents)
    assert any(step.title == "AI committee debate" and step.status == "block" for step in decision.decision_trace)
    assert decision.fairness_passport.verdict == "unfair_to_retail"
    assert any(check.status == "block" for check in decision.fairness_passport.checks)


def test_audit_hash_changes_when_market_context_changes():
    calm = build_decision(fallback_snapshot(scenario="calm"))
    volatile = build_decision(fallback_snapshot(scenario="volatile"))

    assert calm.audit_hash != volatile.audit_hash


def test_audit_ledger_persists_reports(tmp_path):
    ledger = AuditLedger(tmp_path / "fairflow-audits.sqlite3")
    decision = build_decision(fallback_snapshot(scenario="calm"))

    ledger.store_decision(decision)
    reloaded = AuditLedger(tmp_path / "fairflow-audits.sqlite3").get_decision(decision.audit_hash)
    recent = ledger.list_decisions()

    assert ledger.count() == 1
    assert reloaded is not None
    assert reloaded.audit_hash == decision.audit_hash
    assert recent[-1].audit_hash == decision.audit_hash


def test_audit_endpoint_loads_from_persistent_ledger_after_cache_clear():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_fairness_receipt_uses_persistent_audit_lookup():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/receipt")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["symbol"] == analysis["symbol"]
    assert 0 <= payload["bga_alignment_score"] <= 100
    assert payload["machine_readable_url"].endswith(analysis["audit_hash"])
    assert payload["metrics"]
    assert any(metric["label"] == "Hidden cost" for metric in payload["metrics"])
    assert payload["retail_protections"]
    assert payload["verification_steps"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_retail_cohort_report_uses_persistent_audit_lookup():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/retail-cohorts")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["symbol"] == analysis["symbol"]
    assert payload["verdict"] in {"inclusive", "limited", "exclusionary"}
    assert len(payload["cohorts"]) == 4
    assert payload["pass_count"] + payload["watch_count"] + payload["block_count"] == 4
    assert all(cohort["profile"]["account_equity_usdt"] > 0 for cohort in payload["cohorts"])
    assert all(0 <= cohort["friction_score"] <= 100 for cohort in payload["cohorts"])
    assert payload["fairness_warnings"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_retail_cohort_report_blocks_manipulated_decision():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/retail-cohorts")

    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "exclusionary"
    assert payload["block_count"] == 4
    assert all(cohort["status"] == "block" for cohort in payload["cohorts"])
    assert all(cohort["executable"] is False for cohort in payload["cohorts"])
    assert any("core execution gate" in warning.lower() for warning in payload["fairness_warnings"])


def test_impact_ledger_summarizes_audit_history():
    calm = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    manipulated = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get("/api/impact?limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_count"] >= 2
    assert payload["approved_count"] + payload["observe_count"] + payload["blocked_count"] == payload["audit_count"]
    assert payload["no_trade_count"] >= 1
    assert payload["manipulation_alert_count"] >= 1
    assert 0 <= payload["bga_ethos_score"] <= 100
    assert payload["average_fairness_score"] >= 0
    assert payload["estimated_hidden_cost_saved_usdt"] >= 0
    assert payload["cohort_inclusive_count"] + payload["cohort_limited_count"] + payload["cohort_exclusionary_count"] == payload["audit_count"]
    assert calm["audit_hash"] in payload["recent_audit_hashes"] or manipulated["audit_hash"] in payload["recent_audit_hashes"]
    assert payload["summary"]
    assert payload["issues"]


def test_anchor_proof_is_contract_ready_and_deterministic():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    first = client.get(f"/api/audits/{analysis['audit_hash']}/anchor-proof")
    second = client.get(f"/api/audits/{analysis['audit_hash']}/anchor-proof")

    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["decision_hash_bytes32"] == f"0x{analysis['audit_hash']}"
    assert payload["contract_name"] == "FairFlowAudit"
    assert payload["contract_file"] == "contracts/FairFlowAudit.sol"
    assert payload["function_signature"] == "anchorDecision(bytes32,string,string,string)"
    assert payload["contract_arguments"]["decisionHash"] == payload["decision_hash_bytes32"]
    assert payload["contract_arguments"]["symbol"] == analysis["symbol"]
    assert payload["contract_arguments"]["action"] == analysis["final_action"]
    assert payload["metadata"]["paper_only"] is True
    assert payload["payload_hash"] == second.json()["payload_hash"]
    assert payload["calldata_preview"].startswith("anchorDecision(")
    assert payload["verification_steps"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_anchor_proof_explains_blocked_no_trade_reports():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/anchor-proof")

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "NO_TRADE"
    assert payload["status"] in {"blocked", "observe"}
    assert any("blocked or no-trade" in note.lower() for note in payload["safety_notes"])


def test_judge_brief_uses_persistent_audit_lookup_and_rubric_evidence():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/judge-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["symbol"] == analysis["symbol"]
    assert "FairFlow Guardian" in payload["one_sentence_pitch"]
    assert payload["total_demo_minutes"] == 3.0
    assert {item["category"] for item in payload["rubric"]} == {
        "bga_ethos",
        "technical_depth",
        "risk_management",
        "transparency",
    }
    assert all(0 <= item["score"] <= 100 for item in payload["rubric"])
    assert len(payload["demo_steps"]) == 5
    assert payload["proof_links"]
    assert any(link.endswith("/receipt") for link in payload["proof_links"])
    assert any(link.endswith("/anchor-proof") for link in payload["proof_links"])
    assert any(link.endswith("/execution-router") for link in payload["proof_links"])
    assert payload["safety_boundaries"]
    assert payload["likely_questions"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_judge_brief_frames_manipulated_no_trade_as_protection():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/judge-brief")

    assert response.status_code == 200
    payload = response.json()
    assert "refused" in payload["recommended_opening"].lower()
    assert any("no-trade" in step["proof_point"].lower() or "no trade" in step["proof_point"].lower() for step in payload["demo_steps"])


def test_hackathon_readiness_runbook_maps_judging_criteria_and_demo_steps():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/hackathon-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["symbol"] == analysis["symbol"]
    assert payload["verdict"] in {"demo_ready", "needs_review", "blocked_demo"}
    assert 0 <= payload["readiness_score"] <= 100
    assert payload["recommended_demo_minutes"] >= 5
    assert {criterion["category"] for criterion in payload["criteria"]} == {
        "bga_ethos",
        "technical_depth",
        "risk_management",
        "transparency",
    }
    assert {criterion["max_points"] for criterion in payload["criteria"]} == {20, 15}
    assert all(criterion["proof_urls"] for criterion in payload["criteria"])
    assert len(payload["runbook_steps"]) >= 12
    assert any("Fair Execution Router" in step["underlying_mechanism"] or "route" in step["title"].lower() for step in payload["runbook_steps"])
    assert any(step["proof_url"] and step["proof_url"].endswith("/evidence-pack") for step in payload["runbook_steps"])
    assert payload["strongest_claims"]
    assert payload["known_limitations"]
    assert "FairFlow Guardian" in payload["final_30_second_pitch"]
    assert any(link.endswith("/hackathon-readiness") for link in payload["proof_links"])
    assert analysis["audit_hash"] in main_module.AUDITS


def test_hackathon_readiness_runbook_keeps_manipulated_no_trade_in_demo_path():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/hackathon-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert any("no trade" in claim.lower() or "no-trade" in claim.lower() for claim in payload["strongest_claims"])
    assert any(step["title"] == "Close with unsafe-market behavior" for step in payload["runbook_steps"])
    assert all(criterion["remaining_risks"] for criterion in payload["criteria"])


def test_submission_kit_packages_two_minute_video_and_artifacts():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/submission-kit")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["total_runtime_seconds"] == 120
    assert len(payload["video_segments"]) == 6
    assert payload["video_segments"][0]["timecode"] == "0:00-0:15"
    assert payload["video_segments"][-1]["timecode"] == "1:41-2:00"
    assert any("Competition Runway" in segment["narration"] for segment in payload["video_segments"])
    assert any(segment["title"] == "No-trade proof" for segment in payload["video_segments"])
    assert any(asset["path"].endswith("fairflow_guardian_complete_walkthrough.pdf") for asset in payload["submission_assets"])
    assert any(asset["path"].endswith("fairflow_2_minute_video_deck.pptx") for asset in payload["submission_assets"])
    assert any(asset["path"].endswith("fairflow_2min_video_contact_sheet.png") for asset in payload["submission_assets"])
    assert any(item["label"] == "No-trade is framed as a success state" and item["status"] == "ready" for item in payload["final_checklist"])
    assert "Primary proof endpoint" in payload["copy_block"]
    assert any(link.endswith("/submission-kit") for link in payload["proof_links"])
    assert analysis["audit_hash"] in main_module.AUDITS


def test_submission_kit_closes_on_manipulated_no_trade_proof():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/submission-kit")

    assert response.status_code == 200
    payload = response.json()
    closing = payload["video_segments"][-1]
    assert "judging criteria" in closing["narration"].lower()
    assert "evidence pack" in closing["dashboard_action"].lower()
    assert any("no-trade" in item["label"].lower() and item["status"] == "ready" for item in payload["final_checklist"])


def test_model_provenance_uses_persistent_audit_lookup_and_documents_ai_stack():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/model-provenance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["symbol"] == analysis["symbol"]
    assert 0 <= payload["provenance_score"] <= 100
    assert len(payload["data_sources"]) >= 3
    assert len(payload["model_components"]) >= 5
    assert any(component["name"] == "ML Market Regime Classifier" for component in payload["model_components"])
    assert any(component["name"] == "Audit Ledger and Anchor Proof" for component in payload["model_components"])
    assert payload["validation_artifacts"]
    assert payload["reproducibility_steps"]
    assert payload["ethical_boundaries"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_model_provenance_marks_fallback_data_caveat():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/model-provenance")

    assert response.status_code == 200
    payload = response.json()
    market_source = payload["data_sources"][0]
    assert market_source["source_type"] == "deterministic_fallback"
    assert market_source["status"] == "fallback"
    assert "not a live market forecast" in market_source["caveat"].lower()
    assert any("fallback" in limitation.lower() for limitation in payload["known_limitations"])


def test_policy_stress_lab_uses_persistent_audit_lookup_and_runs_three_presets():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/policy-stress")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["symbol"] == analysis["symbol"]
    assert payload["resilience_verdict"] in {
        "stable_greenlight",
        "fragile_greenlight",
        "needs_review",
        "protective_lockdown",
    }
    assert 0 <= payload["stability_score"] <= 100
    assert len(payload["outcomes"]) == 3
    assert {outcome["stance"] for outcome in payload["outcomes"]} == {"access_first", "balanced", "strict"}
    assert all(len(outcome["report"]["checks"]) == 7 for outcome in payload["outcomes"])
    assert all(outcome["report"]["policy"]["audit_hash"] == analysis["audit_hash"] for outcome in payload["outcomes"])
    assert payload["fragile_checks"]
    assert payload["judge_takeaway"]
    assert payload["recommended_next_steps"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_policy_stress_lab_frames_manipulated_no_trade_as_protective_lockdown():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/policy-stress")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resilience_verdict"] == "protective_lockdown"
    assert payload["execution_allowed_count"] == 0
    assert payload["blocked_policy_count"] == 3
    assert all(outcome["report"]["execution_allowed"] is False for outcome in payload["outcomes"])
    assert any("guardian execution gate" in check.lower() for check in payload["fragile_checks"])
    assert "no-trade" in payload["judge_takeaway"].lower()


def test_counterfactual_fairness_report_uses_persistent_lookup_and_lists_guardrail_levers():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/counterfactuals")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["symbol"] == analysis["symbol"]
    assert payload["verdict"] in {"already_fair", "improvable", "fresh_audit_required", "do_not_unlock"}
    assert 0 <= payload["readiness_score"] <= 100
    assert len(payload["levers"]) == 7
    assert {lever["lever_type"] for lever in payload["levers"]} == {
        "fairness",
        "hidden_cost",
        "anomaly",
        "liquidity",
        "leverage",
        "stop_risk",
        "core_gate",
    }
    assert all(lever["status"] in {"already_clear", "improvement_needed", "non_bypassable"} for lever in payload["levers"])
    assert payload["top_blocker"]
    assert payload["recommended_next_steps"]
    assert payload["judge_takeaway"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_counterfactual_fairness_report_refuses_to_unlock_manipulated_no_trade():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/counterfactuals")

    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "do_not_unlock"
    assert payload["unlockable_in_current_audit"] is False
    assert any(lever["lever_type"] == "core_gate" and lever["status"] == "non_bypassable" for lever in payload["levers"])
    assert payload["non_bypassable_constraints"]
    assert any("fresh audit" in item.lower() for item in payload["non_bypassable_constraints"])


def test_fair_execution_router_uses_persistent_lookup_and_ranks_routes():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/execution-router")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["symbol"] == analysis["symbol"]
    assert payload["verdict"] in {"route_ready", "route_with_caution", "paper_only_locked", "no_fair_route"}
    assert payload["fairness_floor_score"] == 72.0
    assert len(payload["route_candidates"]) == 5
    assert {route["route_type"] for route in payload["route_candidates"]} == {
        "market",
        "post_only_limit",
        "twap",
        "maker_ladder",
        "hold",
    }
    assert sum(route["status"] == "recommended" for route in payload["route_candidates"]) == 1
    recommended = next(route for route in payload["route_candidates"] if route["status"] == "recommended")
    assert payload["recommended_route"] == recommended["name"]
    assert all(0 <= route["retail_fairness_score"] <= 100 for route in payload["route_candidates"])
    assert all(0 <= route["fill_probability"] <= 1 for route in payload["route_candidates"])
    assert payload["verification_notes"]
    assert payload["judge_takeaway"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_fair_execution_router_locks_trading_routes_for_manipulated_no_trade():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/execution-router")

    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "paper_only_locked"
    assert payload["execution_permitted"] is False
    assert payload["recommended_route"] == "Hold and re-audit"
    trading_routes = [route for route in payload["route_candidates"] if route["route_type"] != "hold"]
    assert all(route["status"] == "locked" for route in trading_routes)
    assert all(route["max_notional_usdt"] == 0 for route in trading_routes)
    hold_route = next(route for route in payload["route_candidates"] if route["route_type"] == "hold")
    assert hold_route["status"] == "recommended"
    assert any("no_trade" in reason.lower() or "no-trade" in reason.lower() for reason in payload["locked_reasons"])


def test_red_team_report_uses_persistent_audit_lookup_and_runs_integrity_probes():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/red-team")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["symbol"] == analysis["symbol"]
    assert payload["verdict"] in {"resilient", "watchlist", "kill_switch_ready", "already_locked"}
    assert 0 <= payload["integrity_score"] <= 100
    assert len(payload["probes"]) == 5
    assert {probe["attack_vector"] for probe in payload["probes"]} == {
        "liquidity_withdrawal",
        "spoofed_imbalance",
        "volatility_cascade",
        "funding_squeeze",
        "oracle_gap",
    }
    assert all(probe["first_trigger"] for probe in payload["probes"])
    assert all(probe["retail_harm"] for probe in payload["probes"])
    assert payload["worst_probe"]
    assert payload["kill_switches"]
    assert payload["recommended_next_steps"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_red_team_report_keeps_manipulated_market_already_locked():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/red-team")

    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "already_locked"
    assert payload["blocked_probe_count"] == len(payload["probes"])
    assert all(probe["status"] == "block" for probe in payload["probes"])
    assert payload["kill_switches"] == ["Guardian execution gate"]
    assert "no-trade" in payload["judge_takeaway"].lower()


def test_evidence_pack_uses_persistent_lookup_and_bundles_verification_artifacts():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    main_module.AUDITS.pop(analysis["audit_hash"], None)

    response = client.get(f"/api/audits/{analysis['audit_hash']}/evidence-pack")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["package_version"] == "fairflow-evidence-pack-v1"
    assert 0 <= payload["verification_score"] <= 100
    assert payload["decision"]["audit_hash"] == analysis["audit_hash"]
    assert payload["fairness_receipt"]["audit_hash"] == analysis["audit_hash"]
    assert payload["retail_cohorts"]["audit_hash"] == analysis["audit_hash"]
    assert payload["anchor_proof"]["audit_hash"] == analysis["audit_hash"]
    assert payload["judge_brief"]["audit_hash"] == analysis["audit_hash"]
    assert payload["model_provenance"]["audit_hash"] == analysis["audit_hash"]
    assert payload["fair_execution_router"]["audit_hash"] == analysis["audit_hash"]
    assert payload["counterfactuals"]["audit_hash"] == analysis["audit_hash"]
    assert payload["policy_stress"]["audit_hash"] == analysis["audit_hash"]
    assert payload["red_team"]["audit_hash"] == analysis["audit_hash"]
    assert payload["evidence_urls"]["evidence_pack"].endswith("/evidence-pack")
    assert payload["evidence_urls"]["execution_router"].endswith("/execution-router")
    assert payload["evidence_urls"]["red_team"].endswith("/red-team")
    assert payload["core_claims"]
    assert {claim["status"] for claim in payload["core_claims"]} <= {"verified", "watch", "blocked"}
    assert "paper_only" in payload["key_metrics"]
    assert payload["key_metrics"]["paper_only"] is True
    assert "recommended_route" in payload["key_metrics"]
    assert "FairExecutionRouterReport" in payload["included_reports"]
    assert "CounterfactualFairnessReport" in payload["included_reports"]
    assert "RedTeamReport" in payload["included_reports"]
    assert payload["verifier_notes"]
    assert payload["limitations"]
    assert analysis["audit_hash"] in main_module.AUDITS


def test_evidence_pack_preserves_protective_no_trade_claim():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=manipulated").json()

    response = client.get(f"/api/audits/{analysis['audit_hash']}/evidence-pack")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["final_action"] == "NO_TRADE"
    assert "protective no-trade" in payload["headline"].lower()
    no_trade_claim = next(claim for claim in payload["core_claims"] if claim["label"] == "No-trade can be a protective outcome")
    assert no_trade_claim["status"] == "verified"
    assert payload["fair_execution_router"]["verdict"] == "paper_only_locked"
    assert payload["counterfactuals"]["verdict"] == "do_not_unlock"
    assert payload["policy_stress"]["resilience_verdict"] == "protective_lockdown"
    assert payload["red_team"]["verdict"] == "already_locked"


def test_compare_endpoint_returns_scenario_lab_payload():
    response = client.get("/api/compare?symbol=BTCUSDT&category=linear")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "BTCUSDT"
    assert len(payload["decisions"]) == 3
    assert payload["approved_count"] >= 0
    assert payload["blocked_count"] >= 1
    assert payload["average_fairness_score"] > 0
    assert payload["healthiest_scenario"] in {"calm", "volatile", "manipulated"}
    assert all(decision["audit_hash"] for decision in payload["decisions"])


def test_market_series_endpoint_returns_ordered_candles():
    response = client.get("/api/market/series?symbol=BTCUSDT&category=linear&scenario=calm")

    assert response.status_code == 200
    payload = response.json()
    candles = payload["candles"]
    assert payload["symbol"] == "BTCUSDT"
    assert payload["latest_price"] == candles[-1]["close"]
    assert payload["interval_minutes"] == 5
    assert len(candles) == 96
    assert candles[0]["start_ms"] < candles[-1]["start_ms"]
    assert payload["source"] == "fallback:calm"


def test_risk_sizing_respects_audited_execution_gate():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    response = client.post(
        "/api/risk/size",
        json={
            "audit_hash": analysis["audit_hash"],
            "account_equity_usdt": 15_000,
            "risk_budget_pct": 1.25,
            "max_notional_pct": 30,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_amount_usdt"] == 187.5
    assert payload["recommended_notional_usdt"] >= 0
    if analysis["status"] == "approved":
        assert payload["executable"] is True
        assert payload["stop_distance_pct"] > 0
        assert payload["estimated_margin_usdt"] > 0
    else:
        assert payload["executable"] is False


def test_paper_portfolio_tracks_orders_and_can_reset():
    client.post("/api/portfolio/reset")
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    order = client.post("/api/orders/simulate", json={"audit_hash": analysis["audit_hash"]}).json()
    portfolio = client.get("/api/portfolio?scenario=calm").json()

    assert portfolio["starting_equity_usdt"] == 10_000
    assert len(portfolio["orders"]) == 1
    assert portfolio["orders"][0]["client_order_id"] == order["client_order_id"]
    assert portfolio["accepted_order_count"] in {0, 1}
    if order["accepted"]:
        assert len(portfolio["positions"]) == 1
        assert portfolio["positions"][0]["symbol"] == "BTCUSDT"
        assert portfolio["positions"][0]["current_price"] > 0
    else:
        assert portfolio["rejected_order_count"] == 1

    reset = client.post("/api/portfolio/reset").json()
    assert reset["orders"] == []
    assert reset["positions"] == []


def test_agent_mission_returns_task_graph_and_actions():
    response = client.get("/api/agents/mission?symbol=BTCUSDT&category=linear&scenario=calm")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"].startswith("mission-")
    assert payload["symbol"] == "BTCUSDT"
    assert payload["decision"]["audit_hash"]
    assert len(payload["tasks"]) >= 8
    assert any(task["agent"] == "Fairness Auditor" for task in payload["tasks"])
    route_task = next(task for task in payload["tasks"] if task["agent"] == "Route Steward")
    assert route_task["tool"] == "Fair Execution Router"
    assert route_task["status"] in {"complete", "watch", "blocked"}
    assert any("route" in item.lower() or "liquidity budget" in item.lower() for item in route_task["evidence"])
    assert any(action["action_type"] == "compare_scenarios" and action["permitted"] for action in payload["action_queue"])
    assert payload["autonomy_level"] in {"advisory", "guarded_paper"}
    assert payload["risk_register"]


def test_agent_mission_blocks_manipulated_execution():
    response = client.get("/api/agents/mission?symbol=BTCUSDT&category=linear&scenario=manipulated")

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_execute"] is False
    assert payload["autonomy_level"] == "advisory"
    assert any(task["status"] == "blocked" for task in payload["tasks"])
    assert any(action["action_type"] == "hold" and action["priority"] == "critical" for action in payload["action_queue"])
    assert any(action["action_type"] == "paper_execute" and action["permitted"] is False for action in payload["action_queue"])


def test_watchlist_scanner_returns_ranked_agent_outputs():
    symbols = "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT,ADAUSDT,DOGEUSDT"
    response = client.get(f"/api/watchlist?symbols={symbols}&category=linear&scenario=calm")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbols"] == symbols.split(",")
    assert payload["safest_symbol"] in payload["symbols"]
    assert len(payload["items"]) == 8
    assert all(item["audit_hash"] for item in payload["items"])
    assert all(item["rank_reason"] for item in payload["items"])
    scores = [item["rank_score"] for item in payload["items"]]
    assert scores == sorted(scores, reverse=True)


def test_policy_evaluation_reports_custom_guardrails():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    response = client.post(
        "/api/policy/evaluate",
        json={
            "audit_hash": analysis["audit_hash"],
            "min_fairness_score": 75,
            "max_hidden_cost_bps": 12,
            "max_anomaly_score": 50,
            "min_liquidity_score": 50,
            "max_leverage": 3,
            "max_stop_hit_probability": 0.6,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"] == analysis["audit_hash"]
    assert payload["verdict"] in {"compliant", "needs_review", "blocked"}
    assert len(payload["checks"]) == 7
    assert any(check["name"] == "Guardian execution gate" for check in payload["checks"])
    assert payload["suggested_actions"]


def test_policy_evaluation_can_block_with_strict_limits():
    analysis = client.get("/api/analysis?symbol=BTCUSDT&category=linear&scenario=calm").json()
    response = client.post(
        "/api/policy/evaluate",
        json={
            "audit_hash": analysis["audit_hash"],
            "min_fairness_score": 99,
            "max_hidden_cost_bps": 0.5,
            "max_anomaly_score": 5,
            "min_liquidity_score": 99,
            "max_leverage": 1,
            "max_stop_hit_probability": 0.05,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "blocked"
    assert payload["execution_allowed"] is False
    assert any(check["status"] == "block" for check in payload["checks"])
