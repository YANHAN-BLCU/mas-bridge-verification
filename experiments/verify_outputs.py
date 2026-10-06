"""Independent checks for the generated A/B/C artifacts.

This script intentionally reads the CSV/JSON outputs and reconstructs the
models rather than trusting the runner's in-memory status fields.  It is a
small audit command for CI and for reviewers who want to validate every
stored witness.
"""
from __future__ import annotations

import csv
import json
from itertools import product
from pathlib import Path

from .models import Bridge, Quota, replay

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TRACES = ROOT / "traces"


def _model(row):
    params = json.loads(row["parameters"])
    if row["model"] == "bridge":
        return Bridge(params["n"], params["protocol"])
    return Quota(params["n"], params["B"], params["r"], params["protocol"])


def verify_search():
    rows = list(csv.DictReader((RESULTS / "search_results.csv").open(encoding="utf-8")))
    replayed = 0
    for row in rows:
        if row["status"] != "COUNTEREXAMPLE":
            continue
        payload = json.loads((ROOT / row["trace_file"]).read_text(encoding="utf-8"))
        model = _model(row)
        actions = [x["action"] for x in payload["steps"] if x["action"] != "INITIAL"]
        ok, states, error = replay(model.initial, actions, model.successors)
        assert ok, f"{row['config_id']}: {error}"
        assert not model.safe(states[-1]["after"]), row["config_id"]
        assert row["replay_status"] == "PASS", row["config_id"]
        replayed += 1
    return len(rows), replayed


def verify_static():
    rows = list(csv.DictReader((RESULTS / "capacity_scan.csv").open(encoding="utf-8")))
    witnesses = 0
    for row in rows:
        n, cap, rmax = int(row["n"]), int(row["B"]), int(row["r"])
        total = (rmax + 1) ** n
        assert int(row["checked_assignments"]) == total
        assert int(row["total_assignments"]) == total
        found = None
        for p in product(range(rmax + 1), repeat=n):
            pairwise = all(p[i] + p[j] <= cap for i in range(n) for j in range(i + 1, n))
            if pairwise and sum(p) > cap:
                found = p
                break
        has_witness = bool(row["witness"])
        assert has_witness == (found is not None), row["config_id"]
        if has_witness:
            w = tuple(json.loads(row["witness"]))
            assert all(0 <= x <= rmax for x in w)
            assert all(w[i] + w[j] <= cap for i in range(n) for j in range(i + 1, n))
            assert sum(w) > cap
            witnesses += 1
    return len(rows), witnesses


def verify_certificates():
    rows = list(csv.DictReader((RESULTS / "certificate_obligations.csv").open(encoding="utf-8")))
    assert rows and all(r["result"] == "PASS" for r in rows)
    assert all(r["action_declaration"] == "PASS" for r in rows)
    assert all(r["check_scope"] == "complete_declared_finite_domain" for r in rows)
    assert all(r["global_step"] == "PASS" and r["interference"] == "PASS" for r in rows)
    return len(rows)


def verify_negative():
    rows = list(csv.DictReader((RESULTS / "negative_tests.csv").open(encoding="utf-8")))
    assert len(rows) == 4
    for row in rows:
        assert row["status"] == "COUNTEREXAMPLE"
        assert row["replay_status"] == "PASS"
        assert row["candidate_invariant_status"] == "FAIL"
        assert row["failed_obligation"] == "global_step"
    return len(rows)


def verify_experiment_d():
    """Audit the independently supplied D artifacts from their JSON outputs."""
    minimal = json.loads((RESULTS / "minimal_context_results.json").read_text(encoding="utf-8"))
    generated = json.loads((RESULTS / "certificate_generation_results.json").read_text(encoding="utf-8"))
    assert minimal["generic_synthesis"] == {"exhaustive_conflict_families": 276, "passed": True}
    assert [row["n"] for row in minimal["bridge"]] == [2, 3, 4]
    assert all(row["enumerated_states"] == row["declared_domain_states"] for row in minimal["bridge"])
    assert all(row["initialization_passed"] and row["safety_implication_passed"] for row in minimal["bridge"])
    pruning = generated["generic_pruning_validation"]
    assert pruning["checked_models"] == 4032 and pruning["unique_greatest_feasible_subset_passed"]
    assert generated["generic_minimum_context_validation"]["exhaustive_conflict_families"] == 276
    assert generated["capacity_update_iff_validation"]["total_pairs"] == 2000
    assert len(generated["correct_models"]) == 6
    assert all(row["certificate_status"] == "proved" for row in generated["correct_models"])
    assert len(generated["fault_mutations"]) == 9
    return {"context_families": 276, "template_models": 4032, "capacity_pairs": 2000,
            "correct_models": 6, "fault_variants": 9}


def main():
    a, ar = verify_search()
    s, sw = verify_static()
    b = verify_certificates()
    c = verify_negative()
    d = verify_experiment_d()
    summary = {
        "search_configs": a,
        "replayed_counterexamples": ar,
        "static_configs": s,
        "static_witnesses": sw,
        "certificate_rows": b,
        "negative_cases": c,
        "experiment_d": d,
        "status": "PASS",
    }
    (RESULTS / "verification_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
