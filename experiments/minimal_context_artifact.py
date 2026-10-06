"""Finite-domain artifact for the revised bridge-certificate manuscript.

Python 3 standard library only. No external files or network are read.
Run: python -m experiments.minimal_context_artifact
The output JSON is written to experiments/results/.

The model includes explicit shared-class variables indexed by kappa and every state in the declared
Cartesian domain, including inconsistent and unreachable states. Responsibility arcs remain directed; two reverse arcs may share one kappa class. Proof-context
failures are one-step induction failures, not reachable safety counterexamples.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
import time


def minimum_hitting_set(conflicts: list[int], size: int) -> int:
    for cardinality in range(size + 1):
        for indices in itertools.combinations(range(size), cardinality):
            chosen = sum(1 << index for index in indices)
            if all(chosen & conflict for conflict in conflicts):
                return chosen
    raise ValueError("An empty conflict has no hitting set")


def synthesize_context(bad_source_masks: set[int], size: int) -> dict:
    """Exact counterexample-guided minimum context for an explicit oracle.

    Each bad transition is represented by the candidate clauses false in its
    source. A query fails exactly when one such mask avoids the chosen context.
    All masks are obtained by full-domain enumeration, not random sampling.
    """
    conflicts: list[int] = []
    calls = 0
    while True:
        chosen = minimum_hitting_set(conflicts, size)
        calls += 1
        witness = next(
            (mask for mask in sorted(bad_source_masks) if not (mask & chosen)),
            None,
        )
        if witness is None:
            return {
                "status": "valid",
                "context": [i for i in range(size) if chosen & (1 << i)],
                "cardinality": chosen.bit_count(),
                "oracle_calls": calls,
                "conflicts": conflicts,
            }
        if witness == 0:
            return {
                "status": "candidate_not_inductive",
                "context": None,
                "oracle_calls": calls,
                "conflicts": conflicts + [0],
            }
        assert witness not in conflicts
        conflicts.append(witness)


def truth_mask(q: tuple[int, ...], owner: int, z: tuple[int, ...], kappa_classes) -> int:
    false_mask = 0
    n = len(q)
    for i in range(n):
        if q[i] == 2 and owner != i:
            false_mask |= 1 << i
    for index, (u, v) in enumerate(kappa_classes):
        if z[index] != int(q[u] == 2) + int(q[v] == 2):
            false_mask |= 1 << (n + index)
    return false_mask


def slow_successor(q, owner, z, kappa_classes, kind, agent):
    """Independent explicit-state update used to check the fast oracle."""
    new_q = list(q)
    new_z = list(z)
    new_owner = owner
    if kind == "Request":
        new_q[agent] = 1
    elif kind == "Grant":
        new_owner = agent
    elif kind == "Enter":
        new_q[agent] = 2
    elif kind == "Exit":
        new_q[agent] = 0
    elif kind == "Release":
        new_owner = -1
    else:
        raise ValueError(kind)
    if kind in {"Enter", "Exit"}:
        for index, (u, v) in enumerate(kappa_classes):
            if agent in (u, v):
                new_z[index] = int(new_q[u] == 2) + int(new_q[v] == 2)
    return tuple(new_q), new_owner, tuple(new_z)


def verify_bridge(n: int) -> dict:
    started = time.perf_counter()
    kappa_classes = list(itertools.combinations(range(n), 2))
    responsibility_arcs = [(u, v) for u in range(n) for v in range(n) if u != v]
    clause_names = [f"tau_{i + 1}" for i in range(n)] + [
        f"zeta_kappa_{u + 1}_{v + 1}" for u, v in kappa_classes
    ]
    m = len(clause_names)
    token_bits = (1 << n) - 1
    incident = [
        sum(1 << (n + e) for e, kappa_class in enumerate(kappa_classes) if i in kappa_class)
        for i in range(n)
    ]
    affected = {}
    for kind in ("Request", "Grant", "Enter", "Exit", "Release"):
        for i in range(n):
            affected[(kind, i)] = (
                token_bits if kind in {"Grant", "Release"}
                else (1 << i) | incident[i]
            )
    failures = {
        (kind, i, target): set()
        for (kind, i), mask in affected.items()
        for target in range(m) if mask & (1 << target)
    }
    states = 0
    transitions = 0
    invariant_states = 0
    frame_checks = 0
    explicit_endpoint_checks = 0
    implication_passed = True
    initial = ((0,) * n, -1, (0,) * len(kappa_classes))
    assert truth_mask(*initial, kappa_classes) == 0

    for q in itertools.product(range(3), repeat=n):
        on_mask = sum(1 << i for i in range(n) if q[i] == 2)
        actual_edges = tuple(int(q[u] == 2) + int(q[v] == 2) for u, v in kappa_classes)
        for owner in range(-1, n):
            pre_tokens = on_mask & ~(1 << owner) if owner >= 0 else on_mask
            enabled = []
            for i in range(n):
                if q[i] == 0:
                    enabled.append(("Request", i, pre_tokens))
                if q[i] == 1 and owner == -1:
                    enabled.append(("Grant", i, on_mask & ~(1 << i)))
                if q[i] == 1 and owner == i:
                    enabled.append(("Enter", i, pre_tokens & ~(1 << i)))
                if q[i] == 2:
                    enabled.append(("Exit", i, pre_tokens & ~(1 << i)))
                if owner == i and q[i] != 2:
                    enabled.append(("Release", i, on_mask))
            for z in itertools.product(range(3), repeat=len(kappa_classes)):
                states += 1
                pre_edges = sum(
                    1 << (n + e) for e, value in enumerate(z)
                    if value != actual_edges[e]
                )
                pre_false = pre_tokens | pre_edges
                if pre_false == 0:
                    invariant_states += 1
                    implication_passed &= on_mask.bit_count() <= 1
                for kind, agent, post_tokens in enabled:
                    transitions += 1
                    post_edges = (
                        pre_edges & ~incident[agent]
                        if kind in {"Enter", "Exit"} else pre_edges
                    )
                    post_false = post_tokens | post_edges
                    aff = affected[(kind, agent)]
                    # This is a semantic check on every enumerated transition.
                    assert ((pre_false ^ post_false) & ~aff) == 0
                    frame_checks += 1
                    if n <= 3:
                        endpoint = slow_successor(q, owner, z, kappa_classes, kind, agent)
                        assert truth_mask(*endpoint, kappa_classes) == post_false
                        explicit_endpoint_checks += 1
                    bad_targets = post_false & aff
                    while bad_targets:
                        bit = bad_targets & -bad_targets
                        target = bit.bit_length() - 1
                        failures[(kind, agent, target)].add(pre_false)
                        bad_targets ^= bit

    assert implication_passed
    records = []
    for (kind, agent, target), masks in failures.items():
        result = synthesize_context(masks, m)
        assert result["status"] == "valid"
        expected = (
            [target] if kind == "Request" and target >= n
            or kind in {"Grant", "Release"} and target != agent
            else []
        )
        assert result["context"] == expected, (n, kind, agent, target, result)
        records.append({
            "action": f"{kind}_{agent + 1}",
            "target": clause_names[target],
            "context": [clause_names[i] for i in result["context"]],
            "cardinality": result["cardinality"],
            "oracle_calls": result["oracle_calls"],
            "distinct_bad_source_signatures": len(masks),
        })
    pairs = len(records)
    selected = sum(record["cardinality"] for record in records)
    assert states == (3 ** n) * (n + 1) * (3 ** len(kappa_classes))
    assert pairs == 5 * n * n
    assert selected == 3 * n * (n - 1)
    assert invariant_states == (n + 1) * (2 ** n) + n * (2 ** (n - 1))
    return {
        "n": n,
        "responsibility_arcs": len(responsibility_arcs),
        "shared_kappa_variables": len(kappa_classes),
        "kappa_classes": [f"kappa_{u + 1}_{v + 1}" for u, v in kappa_classes],
        "symmetric_arc_attribute": "reverse arcs share kappa class; sym=1",
        "candidate_clauses": m,
        "declared_domain_states": states,
        "enumerated_states": states,
        "non_stutter_transitions": transitions,
        "semantic_frame_checks": frame_checks,
        "independent_endpoint_checks": explicit_endpoint_checks,
        "initialization_passed": True,
        "safety_implication_passed": implication_passed,
        "invariant_states": invariant_states,
        "affected_action_target_pairs": pairs,
        "full_context_clause_occurrences": pairs * m,
        "affected_only_clause_occurrences": 5 * n ** 3,
        "minimum_context_clause_occurrences": selected,
        "maximum_minimum_context_cardinality": max(r["cardinality"] for r in records),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "records": records,
    }


def verify_generic_synthesis() -> dict:
    """Compare CEG synthesis against direct minimization for all small families."""
    checked = 0
    for m in range(1, 4):
        possible_masks = list(range(1 << m))
        for family_bits in range(1 << len(possible_masks)):
            bad = {mask for i, mask in enumerate(possible_masks) if family_bits & (1 << i)}
            result = synthesize_context(bad, m)
            if 0 in bad:
                assert result["status"] == "candidate_not_inductive"
            else:
                valid_sizes = [
                    chosen.bit_count() for chosen in range(1 << m)
                    if all(chosen & witness for witness in bad)
                ]
                assert result["status"] == "valid"
                assert result["cardinality"] == min(valid_sizes)
            checked += 1
    return {"exhaustive_conflict_families": checked, "passed": True}


def verify_summary_bound() -> list[dict]:
    results = []
    for k in range(1, 7):
        # Counts 0..k+1 on L; continuation counts 0..k on R.
        rows = [tuple(c + t <= k for t in range(k + 1)) for c in range(k + 2)]
        assert len(set(rows)) == k + 2
        results.append({"k": k, "distinct_required_summary_values": len(set(rows))})
    return results


def main() -> None:
    output = {
        "scope": "new full-domain one-step proof-context checks, not the old BFS experiments",
        "generic_synthesis": verify_generic_synthesis(),
        "summary_lower_bound": verify_summary_bound(),
        "bridge": [verify_bridge(n) for n in (2, 3, 4)],
    }
    output_path = Path(__file__).with_name("results") / "minimal_context_results.json"
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output_path),
        "generic_synthesis": output["generic_synthesis"],
        "bridge": [{k: v for k, v in row.items() if k != "records"} for row in output["bridge"]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
