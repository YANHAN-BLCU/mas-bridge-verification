"""Finite-domain, fixed-template bridge-certificate construction and diagnosis.

Run with Python 3 (standard library only).  The companion JSON is generated
under ``experiments/results``.  Input consists of finite variable domains, guarded parallel
assignment syntax, a safety target, explicit initial states, and a finite
role-annotated template library.  This is not unrestricted invariant synthesis.
Every declared Cartesian state, including inconsistent records, is enumerated.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import itertools
import json
from pathlib import Path

try:
    from .minimal_context_artifact import synthesize_context, verify_generic_synthesis
except ImportError:  # direct execution from the experiments directory
    from minimal_context_artifact import synthesize_context, verify_generic_synthesis


def V(name):
    return ("var", name)


def C(value):
    return ("const", value)


def E(op, *args):
    return (op, *args)


def AND(*args):
    return E("and", *args)


def ON(name):
    return E("eq", V(name), C(2))


def indicator(predicate):
    return E("ite", predicate, C(1), C(0))


def free_variables(expression):
    if expression[0] == "var":
        return {expression[1]}
    if expression[0] == "const":
        return set()
    return set().union(*(free_variables(arg) for arg in expression[1:]))


def evaluate(expression, state):
    op, *args = expression
    if op == "var":
        return state[args[0]]
    if op == "const":
        return args[0]
    if op == "and":
        return all(evaluate(arg, state) for arg in args)
    if op == "or":
        return any(evaluate(arg, state) for arg in args)
    if op == "not":
        return not evaluate(args[0], state)
    if op == "ite":
        return evaluate(args[1] if evaluate(args[0], state) else args[2], state)
    values = [evaluate(arg, state) for arg in args]
    if op == "eq":
        return values[0] == values[1]
    if op == "ne":
        return values[0] != values[1]
    if op == "lt":
        return values[0] < values[1]
    if op == "le":
        return values[0] <= values[1]
    if op == "add":
        return sum(values)
    if op == "sub":
        return values[0] - values[1]
    raise ValueError(op)


@dataclass
class Action:
    name: str
    component: str
    guard: tuple
    assignments: dict[str, tuple]
    declared_write: set[str] | None = None

    @property
    def writes(self):
        return set(self.assignments)

    @property
    def reads(self):
        return free_variables(self.guard) | set().union(
            *(free_variables(rhs) for rhs in self.assignments.values())
        )


@dataclass
class Clause:
    name: str
    family: str
    expression: tuple

    @property
    def support(self):
        return free_variables(self.expression)


@dataclass
class Model:
    name: str
    domains: dict[str, tuple[int, ...]]
    actions: list[Action]
    clauses: list[Clause]
    initial: dict[str, int]
    target: tuple
    role_annotations: dict
    mutation: str | None = None
    variables: tuple[str, ...] = field(init=False)

    def __post_init__(self):
        self.variables = tuple(self.domains)

    def state_dict(self, state):
        return dict(zip(self.variables, state))

    def encode(self, state):
        return tuple(state[name] for name in self.variables)

    def successor(self, state, action):
        values = self.state_dict(state)
        if not evaluate(action.guard, values):
            return None
        successor = dict(values)
        # All RHS expressions see the pre-state: genuinely parallel updates.
        successor.update({x: evaluate(rhs, values) for x, rhs in action.assignments.items()})
        assert all(successor[x] in self.domains[x] for x in self.variables), (
            self.name, action.name, values, successor
        )
        assert all(successor[x] == values[x] for x in self.variables if x not in action.writes)
        return self.encode(successor)

    def false_mask(self, state):
        values = self.state_dict(state)
        return sum(1 << i for i, clause in enumerate(self.clauses)
                   if not evaluate(clause.expression, values))


def bridge_model(n, mutation=None):
    # Responsibility is directed; reverse arcs for the same symmetric
    # constraint share one kappa class and one state variable.
    kappa_classes = list(itertools.combinations(range(n), 2))
    responsibility_arcs = [(u, v) for u in range(n) for v in range(n) if u != v]
    domains = {f"q_{i + 1}": (0, 1, 2) for i in range(n)}
    domains["owner"] = tuple(range(-1, n))
    domains.update({f"z_kappa_{u + 1}_{v + 1}": (0, 1, 2) for u, v in kappa_classes})
    clauses = [Clause(f"tau_{i + 1}", "ownership",
                      E("or", E("not", ON(f"q_{i + 1}")),
                        E("eq", V("owner"), C(i)))) for i in range(n)]
    clauses += [Clause(f"zeta_kappa_{u + 1}_{v + 1}", "kappa_consistency",
                       E("eq", V(f"z_kappa_{u + 1}_{v + 1}"),
                         E("add", indicator(ON(f"q_{u + 1}")),
                           indicator(ON(f"q_{v + 1}"))))) for u, v in kappa_classes]
    actions = []
    for i in range(n):
        q = f"q_{i + 1}"
        component = f"agent_{i + 1}"
        actions.append(Action(f"Request_{i + 1}", component,
                              E("eq", V(q), C(0)), {q: C(1)}))
        actions.append(Action(f"Grant_{i + 1}", "manager",
                              AND(E("eq", V(q), C(1)), E("eq", V("owner"), C(-1))),
                              {"owner": C(i)}))
        enter_guard = AND(E("eq", V(q), C(1)), E("eq", V("owner"), C(i)))
        if mutation == "missing_ownership_guard" and i == 0:
            enter_guard = E("eq", V(q), C(1))
        enter_updates = {q: C(2)}
        exit_updates = {q: C(0)}
        refresh_updates = {}
        for u, v in kappa_classes:
            if i in (u, v):
                other = v if u == i else u
                z = f"z_kappa_{u + 1}_{v + 1}"
                other_on = indicator(ON(f"q_{other + 1}"))
                enter_updates[z] = E("add", C(1), other_on)
                exit_updates[z] = other_on
                refresh_updates[z] = E("add", indicator(ON(f"q_{u + 1}")),
                                       indicator(ON(f"q_{v + 1}")))
        if mutation == "split_refresh" and i == 0:
            enter_updates = {q: C(2)}
        declared = {q} if mutation == "corrupted_write_metadata" and i == 0 else None
        if mutation == "conservative_write_superset" and i == 0:
            declared = set(enter_updates) | {"owner"}
        actions.append(Action(f"Enter_{i + 1}", component, enter_guard, enter_updates, declared))
        actions.append(Action(f"Exit_{i + 1}", component, E("eq", V(q), C(2)), exit_updates))
        release_guard = AND(E("eq", V("owner"), C(i)), E("ne", V(q), C(2)))
        if mutation == "early_release" and i == 0:
            release_guard = E("eq", V("owner"), C(i))
        actions.append(Action(f"Release_{i + 1}", "manager", release_guard, {"owner": C(-1)}))
        if mutation == "split_refresh" and i == 0:
            actions.append(Action("Refresh_1", component, E("eq", V(q), C(2)), refresh_updates))
    if mutation == "environment_overwrite":
        actions.append(Action("EnvironmentResetOwner", "environment", C(True), {"owner": C(-1)}))
    if mutation == "missing_template":
        clauses = [clause for clause in clauses if clause.name != "tau_1"]
    initial = {name: 0 for name in domains}
    initial["owner"] = -1
    target = E("le", E("add", *(indicator(ON(f"q_{i + 1}")) for i in range(n))), C(1))
    return Model(f"bridge_n{n}" + (f"_{mutation}" if mutation else ""), domains,
                 actions, clauses, initial, target,
                 {"q": "0=away,1=wait,2=on", "owner": "-1=free;0..n-1=agent",
                  "responsibility_arcs": [f"{u + 1}->{v + 1}" for u, v in responsibility_arcs],
                  "kappa_classes": [f"kappa_{u + 1}_{v + 1}" for u, v in kappa_classes],
                  "symmetric_arc_attribute": "reverse arcs share kappa class; sym=1",
                  "provided_template_families": ["ownership", "kappa_consistency"]}, mutation)

def capacity_model(n, maximum, mutation=None):
    # Capacity is maximum, deliberately smaller than n*maximum.
    capacity = maximum
    domains = {f"p_{i + 1}": tuple(range(maximum + 1)) for i in range(n)}
    domains.update({f"a_{i + 1}": tuple(range(maximum + 1)) for i in range(n)})
    quota_sum = E("add", *(V(f"a_{i + 1}") for i in range(n)))
    clauses = [Clause(f"rho_{i + 1}", "coverage",
                      E("le", V(f"p_{i + 1}"), V(f"a_{i + 1}"))) for i in range(n)]
    clauses.append(Clause("kappa", "budget", E("le", quota_sum, C(capacity))))
    actions = []
    for i in range(n):
        p, a = f"p_{i + 1}", f"a_{i + 1}"
        actions.append(Action(f"Consume_{i + 1}", f"agent_{i + 1}",
                              E("lt", V(p), V(a)), {p: E("add", V(p), C(1))}))
        actions.append(Action(f"Free_{i + 1}", f"agent_{i + 1}",
                              E("lt", C(0), V(p)), {p: E("sub", V(p), C(1))}))
        allocate_guard = AND(E("lt", V(a), C(maximum)), E("lt", quota_sum, C(capacity)))
        if mutation == "missing_budget_guard" and i == 0:
            allocate_guard = E("lt", V(a), C(maximum))
        actions.append(Action(f"Allocate_{i + 1}", "manager", allocate_guard,
                              {a: E("add", V(a), C(1))}))
        reclaim_guard = E("lt", V(p), V(a))
        if mutation == "unsafe_reclaim" and i == 0:
            reclaim_guard = E("lt", C(0), V(a))
        actions.append(Action(f"Reclaim_{i + 1}", "manager", reclaim_guard,
                              {a: E("sub", V(a), C(1))}))
    for i, j in itertools.permutations(range(n), 2):
        ai, aj = f"a_{i + 1}", f"a_{j + 1}"
        actions.append(Action(f"Transfer_{i + 1}_{j + 1}", "manager",
                              AND(E("lt", V(f"p_{i + 1}"), V(ai)),
                                  E("lt", V(aj), C(maximum))),
                              {ai: E("sub", V(ai), C(1)), aj: E("add", V(aj), C(1))}))
    if mutation == "missing_template":
        clauses = [clause for clause in clauses if clause.name != "kappa"]
    target = E("le", E("add", *(V(f"p_{i + 1}") for i in range(n))), C(capacity))
    return Model(f"capacity_n{n}_range0to{maximum}" + (f"_{mutation}" if mutation else ""),
                 domains, actions, clauses, {name: 0 for name in domains}, target,
                 {"capacity": capacity, "consumption": [f"p_{i + 1}" for i in range(n)],
                  "quota": [f"a_{i + 1}" for i in range(n)],
                  "provided_template_families": ["coverage", "budget"]}, mutation)


def unaffected_premise_model():
    return Model("unaffected_premise_boolean", {"x": (0, 1), "y": (0, 1)},
                 [Action("ResetX", "agent", C(True), {"x": C(0)})],
                 [Clause("I1", "equality", E("eq", V("x"), V("y"))),
                  Clause("I2", "fixed_zero", E("eq", V("y"), C(0)))],
                 {"x": 0, "y": 0}, E("eq", V("x"), C(0)),
                 {"provided_template_families": ["equality", "fixed_zero"]})


def infer_structure(model):
    writers = {x: set() for x in model.variables}
    for action in model.actions:
        for x in action.writes:
            writers[x].add(action.component)
    clauses = [{"name": clause.name, "family": clause.family,
                "expression": clause.expression, "support": sorted(clause.support),
                "writer_components": sorted(set().union(*(writers[x] for x in clause.support)))}
               for clause in model.clauses]
    actions = []
    metadata_errors = []
    conservative_metadata = []
    for action in model.actions:
        affected = [clause.name for clause in model.clauses if clause.support & action.writes]
        actions.append({"name": action.name, "component": action.component,
                        "guard": action.guard, "parallel_assignments": action.assignments,
                        "inferred_read": sorted(action.reads), "inferred_write": sorted(action.writes),
                        "frame_variables": [x for x in model.variables if x not in action.writes],
                        "frame_relation": "x'=x for every frame_variables entry",
                        "affected_targets": affected})
        if action.declared_write is not None and action.writes - action.declared_write:
            metadata_errors.append({"action": action.name,
                                    "declared_write": sorted(action.declared_write),
                                    "inferred_write": sorted(action.writes),
                                    "omitted": sorted(action.writes - action.declared_write),
                                    "extra": sorted(action.declared_write - action.writes)})
        elif action.declared_write is not None and action.declared_write - action.writes:
            conservative_metadata.append({"action": action.name,
                                          "declared_write": sorted(action.declared_write),
                                          "inferred_write": sorted(action.writes),
                                          "extra": sorted(action.declared_write - action.writes),
                                          "accepted": True,
                                          "reason": "declared writes soundly contain all actual assignment targets"})
    components = sorted({action.component for action in model.actions})
    component_relations = {}
    for component in components:
        own_actions = [action.name for action in model.actions if action.component == component]
        interference_actions = [action.name for action in model.actions if action.component != component]
        component_relations[component] = {
            "own_guarantee_action_names": own_actions,
            "guarantee_relation": "disjunction of actual T_a for own_guarantee_action_names",
            "interference_action_names": interference_actions,
            "rely_relation": "disjunction of actual T_a for interference_action_names",
            "action_definitions": "references full guard/parallel-assignment/frame definitions in structure.actions",
            "exact_relation_on_declared_full_domain": True,
            "environment_actions_included_when_not_this_component":
                [action.name for action in model.actions
                 if action.component == "environment" and action.component != component],
            "assumptions_added_to_actual_transitions": False,
        }
    return {"support_inference": "syntactic free variables; sound, not necessarily minimal",
            "read_write_inference": "guard/RHS free variables and assignment LHS; parallel semantics",
            "ownership_inference": "writer components only; no automatic ownership protocol invented",
            "variables": {x: {"domain": model.domains[x], "writer_components": sorted(writers[x]),
                               "unique_writer_component": next(iter(writers[x])) if len(writers[x]) == 1 else None,
                               "shared_writer": len(writers[x]) > 1} for x in model.variables},
            "clauses": clauses, "actions": actions, "component_relations": component_relations,
            "write_metadata_validation_policy": "block omitted actual assignment targets; accept conservative supersets",
            "conservative_write_metadata": conservative_metadata,
            "write_metadata_errors": metadata_errors}


def enumerate_semantics(model):
    states = list(itertools.product(*model.domains.values()))
    masks = {state: model.false_mask(state) for state in states}
    transitions = []
    frame_checks = 0
    for state in states:
        pre_values = model.state_dict(state)
        for action_index, action in enumerate(model.actions):
            successor = model.successor(state, action)
            if successor is not None:
                transitions.append((state, successor, action_index))
                post_values = model.state_dict(successor)
                for clause in model.clauses:
                    if not (clause.support & action.writes):
                        assert evaluate(clause.expression, pre_values) == evaluate(clause.expression, post_values)
                        frame_checks += 1
    return states, masks, transitions, frame_checks


def witness(model, state, successor, action_index, reachable_states=None, allowed_premise_indices=None):
    action = model.actions[action_index]
    pre_values, post_values = model.state_dict(state), model.state_dict(successor)
    false_indices = {i for i, clause in enumerate(model.clauses)
                     if not evaluate(clause.expression, pre_values)}
    allowed = set(range(len(model.clauses))) if allowed_premise_indices is None else set(allowed_premise_indices)
    return {"action": action.name, "component": action.component,
            "inferred_written_variables": sorted(action.writes),
            "actual_changed_variables": [x for x in model.variables if pre_values[x] != post_values[x]],
            "source": pre_values, "successor": post_values,
            "allowed_premise_names": [clause.name for i, clause in enumerate(model.clauses) if i in allowed],
            "unmet_allowed_premises": [clause.name for i, clause in enumerate(model.clauses)
                                       if i in false_indices & allowed],
            "false_other_library_templates": [clause.name for i, clause in enumerate(model.clauses)
                                               if i in false_indices - allowed],
            "source_BFS_reachable": state in reachable_states if reachable_states is not None else None,
            "source_reachability_status": "confirmed_reachable" if reachable_states is not None and state in reachable_states
            else "confirmed_unreachable" if reachable_states is not None else "unknown",
            "reachability_evidence": "complete exact BFS on actual transition table" if reachable_states is not None else None,
            "diagnostic_scope": "specific failed obligation; does not identify a unique causal bug"}


def restrict_witness_allowed_premises(record, allowed_names):
    result = dict(record)
    allowed = set(allowed_names)
    all_false = set(record["unmet_allowed_premises"]) | set(record["false_other_library_templates"])
    result["allowed_premise_names"] = list(allowed_names)
    result["unmet_allowed_premises"] = sorted(all_false & allowed)
    result["false_other_library_templates"] = sorted(all_false - allowed)
    return result


def prune_templates(model, masks, transitions, reachable_states=None):
    """Houdini-style exact strongest initialized inductive subset of the library."""
    current = (1 << len(model.clauses)) - 1
    initial = model.encode(model.initial)
    removals = []
    initial_false = masks[initial]
    for i, clause in enumerate(model.clauses):
        if initial_false & (1 << i):
            removals.append({"clause": clause.name, "round": 0, "kind": "initialization",
                             "source": model.initial, "source_BFS_reachable": True,
                             "source_reachability_status": "confirmed_reachable_initial_state"})
    current &= ~initial_false
    rounds = 0
    while True:
        rounds += 1
        remove = 0
        for state, successor, action_index in transitions:
            if masks[state] & current:
                continue
            failures = masks[successor] & current
            new = failures & ~remove
            remove |= failures
            for i, clause in enumerate(model.clauses):
                if new & (1 << i):
                    removals.append({"clause": clause.name, "round": rounds,
                                     "kind": "inductiveness",
                                     **witness(model, state, successor, action_index, reachable_states,
                                               [j for j in range(len(model.clauses)) if current & (1 << j)]),
                                     "source_satisfies_current_candidate": True,
                                     "current_clause_names": [c.name for j, c in enumerate(model.clauses)
                                                              if current & (1 << j)]})
        if not remove:
            break
        current &= ~remove
    assert not (masks[initial] & current)
    assert all(masks[s] & current or not (masks[t] & current) for s, t, _ in transitions)
    return {"retained": [c.name for i, c in enumerate(model.clauses) if current & (1 << i)],
            "removed": removals, "rounds_including_terminal_check": rounds,
            "fixed_library_relative_completeness": True,
            "scope": "greatest feasible clause subset, not synthesis of new formulas"}, current


def reachable_check(model, property_test):
    initial = model.encode(model.initial)
    queue = deque([initial])
    previous = {initial: None}
    failure = None
    while queue:
        state = queue.popleft()
        if not property_test(state):
            failure = state
            break
        for action_index, action in enumerate(model.actions):
            successor = model.successor(state, action)
            if successor is not None and successor not in previous:
                previous[successor] = (state, action_index)
                queue.append(successor)
    if failure is None:
        return {"status": "safe", "reachable_states": len(previous),
                "complete_reachable_exploration": True, "counterexample": None}
    path_states, path_actions = [failure], []
    cursor = failure
    while previous[cursor] is not None:
        pre, action_index = previous[cursor]
        path_actions.append(model.actions[action_index].name)
        path_states.append(pre)
        cursor = pre
    path_states.reverse()
    path_actions.reverse()
    assert path_states[0] == initial
    for pre, action_name, post in zip(path_states, path_actions, path_states[1:]):
        action = next(a for a in model.actions if a.name == action_name)
        assert model.successor(pre, action) == post
    assert not property_test(path_states[-1])
    return {"status": "unsafe", "discovered_states": len(previous),
            "complete_reachable_exploration": False,
            "counterexample": {"length": len(path_actions), "actions": path_actions,
                               "states": [model.state_dict(s) for s in path_states],
                               "verified_against_actual_actions": True}}


def complete_reachable_set(model, transitions):
    """Exact complete BFS, separately from BFS that stops at a bad state."""
    adjacency = {}
    for source, target, _ in transitions:
        adjacency.setdefault(source, set()).add(target)
    initial = model.encode(model.initial)
    reachable = {initial}
    queue = deque([initial])
    while queue:
        source = queue.popleft()
        for target in adjacency.get(source, ()):
            if target not in reachable:
                reachable.add(target)
                queue.append(target)
    return reachable


def contexts_and_baselines(model, masks, transitions, reachable_states=None):
    size = len(model.clauses)
    affected = [[i for i, clause in enumerate(model.clauses) if clause.support & action.writes]
                for action in model.actions]
    failures = {(a, target): set() for a, targets in enumerate(affected) for target in targets}
    examples = {}
    for state, successor, action_index in transitions:
        for target in affected[action_index]:
            if masks[successor] & (1 << target):
                failures[(action_index, target)].add(masks[state])
                examples.setdefault((action_index, target, masks[state]),
                                    witness(model, state, successor, action_index, reachable_states))
    records = []
    affected_failed = []
    full_failed = []
    for (a, target), bad in failures.items():
        result = synthesize_context(bad, size)
        affected_mask = sum(1 << i for i in affected[a])
        affected_bad = next((mask for mask in sorted(bad) if not (mask & affected_mask)), None)
        if affected_bad is not None:
            affected_failed.append({"action": model.actions[a].name,
                                    "target": model.clauses[target].name,
                                    **restrict_witness_allowed_premises(examples[(a, target, affected_bad)],
                                                                      [model.clauses[i].name for i in affected[a]])})
        if 0 in bad:
            full_failed.append({"action": model.actions[a].name,
                                "target": model.clauses[target].name,
                                **examples[(a, target, 0)]})
        chosen = result.get("context")
        proof_interface = (model.actions[a].reads | model.actions[a].writes | model.clauses[target].support
                           | set().union(*(model.clauses[i].support for i in chosen))) if chosen is not None else None
        records.append({"action": model.actions[a].name, "target": model.clauses[target].name,
                        "status": result["status"],
                        "context": [model.clauses[i].name for i in chosen] if chosen is not None else None,
                        "cardinality": result.get("cardinality"),
                        "proof_interface_variables": sorted(proof_interface) if proof_interface is not None else None,
                        "proof_variable_width": len(proof_interface) if proof_interface is not None else None,
                        "oracle_calls": result["oracle_calls"],
                        "discovered_conflict_masks": result["conflicts"],
                        "distinct_bad_source_signatures": len(bad)})
    valid = not full_failed
    all_goal_pairs = len(model.actions) * size
    minimum_occurrences = sum(r["cardinality"] for r in records) if valid else None
    return {"same_actual_transition_table": True,
            "baseline_metric": "clause-wise obligations and repeated premise occurrences; not execution time",
            "global_all_goal_full_context": {"obligations": all_goal_pairs,
                                             "premise_occurrences": all_goal_pairs * size,
                                             "max_context": size, "valid": valid},
            "frame_full_context": {"obligations": len(records),
                                   "premise_occurrences": len(records) * size,
                                   "max_context": size, "valid": valid},
            "affected_only_context": {"obligations": len(records),
                                      "premise_occurrences": sum(len(targets) ** 2 for targets in affected),
                                      "max_context": max(map(len, affected), default=0),
                                      "valid": not affected_failed, "failures": affected_failed},
            "minimum_context": {"obligations": len(records),
                                "premise_occurrences": minimum_occurrences,
                                "max_context": max((r["cardinality"] for r in records), default=0) if valid else None,
                                "max_proof_variable_width": max((r["proof_variable_width"] for r in records), default=0)
                                if valid else None,
                                "valid": valid, "infeasible_full_candidate": full_failed},
            "records": records}


def run_model(model):
    structure = infer_structure(model)
    states, masks, transitions, frame_checks = enumerate_semantics(model)
    all_reachable = complete_reachable_set(model, transitions)
    pruning, retained = prune_templates(model, masks, transitions, all_reachable)
    implication_failure = next((model.state_dict(s) for s in states
                                if not (masks[s] & retained)
                                and not evaluate(model.target, model.state_dict(s))), None)
    safety = reachable_check(model, lambda s: evaluate(model.target, model.state_dict(s)))
    candidate_reachability = reachable_check(model, lambda s: masks[s] == 0)
    baselines = contexts_and_baselines(model, masks, transitions, all_reachable)
    retained_model = Model(model.name, model.domains, model.actions,
                           [clause for i, clause in enumerate(model.clauses) if retained & (1 << i)],
                           model.initial, model.target, model.role_annotations, model.mutation)
    retained_masks = {state: retained_model.false_mask(state) for state in states}
    retained_baselines = contexts_and_baselines(retained_model, retained_masks, transitions, all_reachable)
    assert retained_baselines["minimum_context"]["valid"]
    labels = []
    if structure["write_metadata_errors"]:
        labels.append({"kind": "write_metadata_mismatch", "evidence": structure["write_metadata_errors"],
                       "status": "structural_fact", "suggested_remedy": "regenerate metadata from actual syntax"})
    if structure["conservative_write_metadata"]:
        labels.append({"kind": "conservative_write_declaration", "evidence": structure["conservative_write_metadata"],
                       "status": "accepted_sound_metadata", "suggested_remedy": None})
    shared = {x: v["writer_components"] for x, v in structure["variables"].items() if v["shared_writer"]}
    if shared:
        labels.append({"kind": "shared_writer_interference", "evidence": shared,
                       "status": "structural_fact_not_a_bug", "suggested_remedy": "check every writer action"})
    for removal in pruning["removed"]:
        labels.append({"kind": "candidate_not_initialized" if removal["kind"] == "initialization"
                       else "candidate_not_inductive", "evidence": removal,
                       "status": "one_step_obligation_failure_with_separate_exact_reachability_check"})
    if implication_failure is not None:
        labels.append({"kind": "safety_not_entailed_by_retained_library",
                       "evidence": implication_failure, "status": "full_domain_static_witness",
                       "suggested_remedy": "extend supplied templates or use a different abstraction; hypothesis only"})
    if model.mutation:
        mutation_labels = {
            "missing_ownership_guard": "guard_reads_no_owner_on_faulty_enter",
            "early_release": "release_omits_on_state_exclusion",
            "split_refresh": "node_update_and_kappa_refresh_are_separate_transitions",
            "environment_overwrite": "environment_is_an_actual_additional_owner_writer",
            "missing_template": "provided_template_library_is_incomplete_for_static_entailment",
            "unsafe_reclaim": "quota_reclaim_omits_consumption_coverage_guard",
            "missing_budget_guard": "allocation_omits_global_budget_guard",
            "corrupted_write_metadata": "declared_write_set_omits_actual_assignment_targets",
            "conservative_write_superset": "declared_write_set_soundly_overapproximates_actual_assignments",
        }
        labels.append({"kind": mutation_labels[model.mutation],
                       "status": "source_syntax_fact_of_deliberate_mutation",
                       "suggested_remedy": None if model.mutation == "conservative_write_superset"
                       else "repair this protocol condition and rerun all checks; hypothesis only"})
    if safety["status"] == "unsafe":
        labels.append({"kind": "reachable_safety_violation", "evidence": safety["counterexample"],
                       "status": "verified_shortest_BFS_trace"})
    issuance_status = ("blocked_write_metadata_mismatch" if structure["write_metadata_errors"]
                       else "proved" if implication_failure is None else "not_proved_by_retained_library")
    return {"name": model.name, "role_annotations": model.role_annotations,
            "initial": model.initial, "target": model.target, "structure": structure,
            "enumeration": {"full_cartesian_states": len(states),
                            "actual_enabled_transitions": len(transitions),
                            "unaffected_clause_frame_checks": frame_checks,
                            "includes_inconsistent_and_unreachable_records": True},
            "complete_reachability_diagnosis": {"reachable_states": len(all_reachable),
                                               "complete_exact_BFS": True,
                                               "actual_transition_table_used": True},
            "template_pruning": pruning,
            "retained_library_entails_target": implication_failure is None,
            "static_entailment_witness": implication_failure,
            "reachable_safety": safety, "reachable_original_candidate": candidate_reachability,
            "certificate_status": issuance_status,
            "baselines": baselines,
            "generated_certificate": {
                "retained_clause_names": pruning["retained"],
                "all_retained_minimum_contexts_valid": retained_baselines["minimum_context"]["valid"],
                "safety_entailment_passed": implication_failure is None,
                "structural_validation_passed": not structure["write_metadata_errors"],
                "issuance_status": issuance_status,
                "metadata_policy": "inferred true writes used for checking; omitted actual writes block issuance; conservative supersets accepted",
                "one_step_context_records": retained_baselines["records"],
                "minimum_context_metrics": retained_baselines["minimum_context"]},
            "diagnosis": labels}


def generic_pruning(mask_table, edges, initial_indices, size):
    current = (1 << size) - 1
    for initial in initial_indices:
        current &= ~mask_table[initial]
    while True:
        remove = 0
        for source, target in edges:
            if not (mask_table[source] & current):
                remove |= mask_table[target] & current
        if not remove:
            return current
        current &= ~remove


def verify_pruning_exhaustively():
    checked = 0
    greatest_counts = {}
    possible_edges = list(itertools.product(range(2), repeat=2))
    for size in range(1, 4):
        count = 0
        for clause_truth_tables in itertools.product(range(4), repeat=size):
            masks = [sum(1 << i for i, truth in enumerate(clause_truth_tables)
                         if not (truth & (1 << s))) for s in range(2)]
            for edge_bits in range(16):
                edges = [edge for i, edge in enumerate(possible_edges) if edge_bits & (1 << i)]
                for initials in ((0,), (1,), (0, 1)):
                    selected = generic_pruning(masks, edges, initials, size)
                    feasible = [subset for subset in range(1 << size)
                                if all(not (masks[s] & subset) for s in initials)
                                and all(masks[s] & subset or not (masks[t] & subset) for s, t in edges)]
                    assert selected in feasible
                    assert all((subset | selected) == selected for subset in feasible)
                    assert selected == sum(1 << i for i in range(size)
                                           if any(subset & (1 << i) for subset in feasible))
                    checked += 1
                    count += 1
        greatest_counts[str(size)] = count
    assert checked == 4032
    return {"checked_models": checked, "models_per_clause_count": greatest_counts,
            "states_per_model": 2, "all_clause_truth_tables": True,
            "all_binary_transition_relations": True, "all_nonempty_initial_sets": True,
            "against_exhaustive_subset_solver": True,
            "unique_greatest_feasible_subset_passed": True}


def verify_support_semantics(model):
    # Independently group by inferred support/read valuations on every state.
    states = list(itertools.product(*model.domains.values()))
    checks = 0
    for clause in model.clauses:
        observed = {}
        for state in states:
            values = model.state_dict(state)
            key = tuple(values[x] for x in sorted(clause.support))
            truth = evaluate(clause.expression, values)
            assert key not in observed or observed[key] == truth
            observed[key] = truth
            checks += 1
    for action in model.actions:
        observed = {}
        for state in states:
            values = model.state_dict(state)
            key = tuple(values[x] for x in sorted(action.reads))
            result = (evaluate(action.guard, values),
                      tuple(evaluate(rhs, values) for rhs in action.assignments.values()))
            assert key not in observed or observed[key] == result
            observed[key] = result
            checks += 1
    return {"model": model.name, "full_domain_grouping_checks": checks, "passed": True}


def verify_capacity_update_conditions():
    """Exhaustively verify the exact batch-update iff on a bounded test domain.

    This finite check validates the algebraic theorem's implementation on its
    stated domain.  The manuscript proof establishes the general statement.
    U ranges over every subset, and all post-states that frame its complement
    are checked, not merely transitions of the hand-picked safe protocol.
    """
    n = 2
    maximum = 2
    states = list(itertools.product(range(maximum + 1), repeat=2 * n))
    records = []
    for capacity in (1, 2):
        legal_pre = [s for s in states if all(s[i] <= s[n + i] for i in range(n))
                     and sum(s[n:]) <= capacity]
        checks = 0
        safe_post_checks = 0
        per_subset = {}
        for subset_bits in range(1 << n):
            subset = [i for i in range(n) if subset_bits & (1 << i)]
            subset_count = 0
            for pre in legal_pre:
                p, a = pre[:n], pre[n:]
                slack = [a[i] - p[i] for i in range(n)]
                remaining = capacity - sum(a)
                assert capacity - sum(p) == remaining + sum(slack)
                for post in states:
                    if any((post[i] != p[i] or post[n + i] != a[i])
                           for i in range(n) if i not in subset):
                        continue
                    post_p, post_a = post[:n], post[n:]
                    delta_p = [post_p[i] - p[i] for i in range(n)]
                    delta_a = [post_a[i] - a[i] for i in range(n)]
                    exact_conditions = (all(delta_p[i] >= -p[i] for i in subset)
                                        and all(delta_p[i] - delta_a[i] <= slack[i] for i in subset)
                                        and sum(delta_a[i] for i in subset) <= remaining)
                    post_certificate = (all(0 <= post_p[i] <= post_a[i] for i in range(n))
                                        and sum(post_a) <= capacity)
                    assert exact_conditions == post_certificate
                    checks += 1
                    subset_count += 1
                    safe_post_checks += int(post_certificate)
            per_subset[','.join(map(str, subset)) or "empty"] = subset_count
        assert checks == len(legal_pre) * 100
        records.append({"n": n, "component_domain": [0, maximum], "capacity": capacity,
                        "full_domain_states": len(states), "certificate_pre_states": len(legal_pre),
                        "legal_pre_and_framed_post_pairs": checks, "pairs_per_updated_subset": per_subset,
                        "post_certificate_true_pairs": safe_post_checks,
                        "iff_passed": True, "slack_identity_passed": True})
    assert sum(record["legal_pre_and_framed_post_pairs"] for record in records) == 2000
    return {"total_pairs": 2000, "records": records,
            "scope": "finite algebraic validation, separate from action-baseline transition counts"}


def main():
    correct_models = [bridge_model(n) for n in (2, 3)]
    correct_models += [capacity_model(n, maximum) for n in (2, 3) for maximum in (1, 2)]
    correct = [run_model(model) for model in correct_models]
    for model, record in zip(correct_models, correct):
        assert record["certificate_status"] == "proved"
        assert record["reachable_safety"]["status"] == "safe"
        assert not record["template_pruning"]["removed"]
        if model.name.startswith("bridge"):
            n = int(model.name[-1])
            baseline = record["baselines"]
            assert baseline["frame_full_context"]["obligations"] == 5 * n * n
            assert baseline["frame_full_context"]["premise_occurrences"] == 5 * n * n * n * (n + 1) // 2
            assert baseline["affected_only_context"]["premise_occurrences"] == 5 * n ** 3
            assert baseline["minimum_context"]["premise_occurrences"] == 3 * n * (n - 1)
            for context in baseline["records"]:
                kind, agent = context["action"].split("_")
                expected = ([context["target"]] if kind == "Request" and context["target"].startswith("zeta")
                            or kind in ("Grant", "Release") and context["target"] != f"tau_{agent}" else [])
                assert context["context"] == expected
    faults = [run_model(bridge_model(2, mutation)) for mutation in
              ("missing_ownership_guard", "early_release", "split_refresh", "environment_overwrite",
               "corrupted_write_metadata", "missing_template")]
    faults += [run_model(capacity_model(2, 1, mutation)) for mutation in
               ("missing_budget_guard", "unsafe_reclaim", "missing_template")]
    expected_safety = {"missing_ownership_guard": "unsafe", "early_release": "unsafe",
                       "split_refresh": "safe", "environment_overwrite": "unsafe",
                       "corrupted_write_metadata": "safe", "missing_template": "safe",
                       "missing_budget_guard": "unsafe", "unsafe_reclaim": "unsafe"}
    for record in faults:
        mutation = next(key for key in expected_safety if record["name"].endswith(key))
        assert record["reachable_safety"]["status"] == expected_safety[mutation]
    unaffected = run_model(unaffected_premise_model())
    assert unaffected["baselines"]["records"][0]["context"] == ["I2"]
    assert not unaffected["baselines"]["affected_only_context"]["valid"]
    assert unaffected["structure"]["actions"][0]["affected_targets"] == ["I1"]
    assert unaffected["baselines"]["affected_only_context"]["failures"][0]["unmet_allowed_premises"] == []
    assert unaffected["baselines"]["affected_only_context"]["failures"][0]["false_other_library_templates"] == ["I2"]
    conservative = run_model(bridge_model(2, "conservative_write_superset"))
    assert conservative["certificate_status"] == "proved"
    assert not conservative["structure"]["write_metadata_errors"]
    assert conservative["structure"]["conservative_write_metadata"][0]["extra"] == ["owner"]
    assert conservative["baselines"] == correct[0]["baselines"]
    assert conservative["reachable_safety"] == correct[0]["reachable_safety"]
    for record in correct + faults:
        assert all(not removed.get("unmet_allowed_premises") for removed in record["template_pruning"]["removed"])
    output = {"artifact_scope": "semiautomatic fixed-template construction with exact finite-domain checks",
              "backend": "Python standard-library explicit evaluator, not an SMT experiment",
              "claims_not_made": ["unrestricted invariant synthesis", "arbitrary-system relative completeness",
                                  "automatic invention of ownership protocols", "unique cause of protocol failure",
                                  "parameterized cutoff proof", "wall-clock speedup", "rely-guarantee runtime baseline"],
              "generic_pruning_validation": verify_pruning_exhaustively(),
              "generic_minimum_context_validation": verify_generic_synthesis(),
              "capacity_update_iff_validation": verify_capacity_update_conditions(),
              "support_read_inference_validation": [verify_support_semantics(model) for model in correct_models],
              "conservative_write_superset_validation": {"passed": True,
                                                         "same_actual_semantics_and_context_results_as_base_model": True,
                                                         "model": conservative},
              "correct_models": correct, "fault_mutations": faults,
              "unaffected_premise_example": unaffected}
    output_path = Path(__file__).with_name("results") / "certificate_generation_results.json"
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "generic_validation": output["generic_pruning_validation"],
                      "correct_models": [{"name": r["name"], "states": r["enumeration"]["full_cartesian_states"],
                                          "transitions": r["enumeration"]["actual_enabled_transitions"],
                                          "affected_pairs": r["baselines"]["frame_full_context"]["obligations"],
                                          "full_premises": r["baselines"]["frame_full_context"]["premise_occurrences"],
                                          "affected_premises": r["baselines"]["affected_only_context"]["premise_occurrences"],
                                          "minimum_premises": r["baselines"]["minimum_context"]["premise_occurrences"],
                                          "max_min_context": r["baselines"]["minimum_context"]["max_context"],
                                          "reachable_states": r["reachable_safety"]["reachable_states"]} for r in correct],
                      "faults": [{"name": r["name"], "removed": [x["clause"] for x in r["template_pruning"]["removed"]],
                                  "safety": r["reachable_safety"]["status"],
                                  "safety_trace_length": (r["reachable_safety"]["counterexample"] or {}).get("length"),
                                  "certificate": r["certificate_status"]} for r in faults]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
