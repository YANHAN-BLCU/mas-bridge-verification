"""Finite-state multi-agent safety models and explicit-state verification.

All models and transitions are deterministic. State tuples are immutable and
hashable so breadth-first search produces shortest counterexamples.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Iterable


State = tuple
Action = tuple[str, State]


@dataclass(frozen=True)
class SearchResult:
    safe: bool
    states: int
    transitions: int
    seconds: float
    trace: tuple[tuple[str, State], ...]


def explore(initial: State, successors: Callable[[State], Iterable[Action]],
            safety: Callable[[State], bool], max_states: int = 2_000_000) -> SearchResult:
    start = perf_counter()
    queue = deque([initial])
    parent: dict[State, tuple[State | None, str]] = {initial: (None, "initial")}
    transitions = 0
    while queue:
        state = queue.popleft()
        if not safety(state):
            rev: list[tuple[str, State]] = []
            cur: State | None = state
            while cur is not None:
                prev, label = parent[cur]
                rev.append((label, cur))
                cur = prev
            return SearchResult(False, len(parent), transitions, perf_counter()-start, tuple(reversed(rev)))
        for label, nxt in successors(state):
            transitions += 1
            if nxt not in parent:
                parent[nxt] = (state, label)
                queue.append(nxt)
                if len(parent) > max_states:
                    raise RuntimeError(f"state limit exceeded: {max_states}")
    return SearchResult(True, len(parent), transitions, perf_counter()-start, ())


def replace(t: tuple, i: int, value: int) -> tuple:
    return t[:i] + (value,) + t[i+1:]


class Bridge:
    """q: 0=away, 1=waiting, 2=on; seen: cached free flag."""
    def __init__(self, n: int, protocol: str):
        assert n >= 2 and protocol in {"local", "check_then_enter", "token"}
        self.n, self.protocol = n, protocol
        self.initial: State = ((0,) * n, (0,) * n, -1)

    def safe(self, s: State) -> bool:
        q, _, _ = s
        return sum(x == 2 for x in q) <= 1

    def invariant(self, s: State) -> bool:
        q, _, owner = s
        return all(q[i] != 2 or owner == i for i in range(self.n))

    def successors(self, s: State) -> Iterable[Action]:
        q, seen, owner = s
        for i in range(self.n):
            if q[i] == 0:
                yield f"request({i})", (replace(q, i, 1), seen, owner)
            elif q[i] == 1:
                if self.protocol == "local":
                    yield f"enter({i})", (replace(q, i, 2), seen, owner)
                elif self.protocol == "check_then_enter":
                    if not seen[i] and all(x != 2 for x in q):
                        yield f"read_free({i})", (q, replace(seen, i, 1), owner)
                    if seen[i]:
                        yield f"enter_cached({i})", (replace(q, i, 2), replace(seen, i, 0), owner)
                else:
                    if owner == -1:
                        yield f"grant({i})", (q, seen, i)
                    if owner == i:
                        yield f"enter_token({i})", (replace(q, i, 2), seen, owner)
                    if owner == i:
                        yield f"cancel({i})", (replace(q, i, 0), seen, owner)
            else:
                yield f"exit({i})", (replace(q, i, 0), seen, owner)
            if self.protocol == "token" and owner == i and q[i] == 0:
                yield f"release({i})", (q, seen, -1)


class Quota:
    """p: consumption, a: allocated quota, seen: cached spare-capacity flag.

    Pairwise baseline allows an increment only if resulting pair sums are <=B.
    No guarantee is imposed on the sum over all agents.
    """
    def __init__(self, n: int, cap: int, r: int, protocol: str):
        assert n >= 2 and cap >= 1 and r >= 1
        assert protocol in {"local", "pairwise", "check_then_commit", "quota"}
        self.n, self.cap, self.r, self.protocol = n, cap, r, protocol
        self.initial: State = ((0,) * n, (0,) * n, (0,) * n)

    def safe(self, s: State) -> bool:
        return sum(s[0]) <= self.cap

    def pairwise_safe(self, s: State) -> bool:
        p = s[0]
        return all(p[i]+p[j] <= self.cap for i in range(self.n) for j in range(i+1,self.n))

    def invariant(self, s: State) -> bool:
        p, a, _ = s
        return all(0 <= p[i] <= a[i] for i in range(self.n)) and sum(a) <= self.cap

    def successors(self, s: State) -> Iterable[Action]:
        p, a, seen = s
        for i in range(self.n):
            if self.protocol == "local":
                if p[i] < self.r:
                    yield f"consume({i})", (replace(p,i,p[i]+1),a,seen)
            elif self.protocol == "pairwise":
                if p[i] < self.r and all(p[i]+1+p[j] <= self.cap for j in range(self.n) if j != i):
                    yield f"consume_pairwise({i})", (replace(p,i,p[i]+1),a,seen)
            elif self.protocol == "check_then_commit":
                if p[i] < self.r and not seen[i] and sum(p) < self.cap:
                    yield f"read_spare({i})", (p,a,replace(seen,i,1))
                if p[i] < self.r and seen[i]:
                    yield f"commit_cached({i})", (replace(p,i,p[i]+1),a,replace(seen,i,0))
            else:
                # Atomic grant checks the new global allocation. Consume remains local.
                if a[i] < self.r and sum(a) < self.cap:
                    yield f"grant_quota({i})", (p,replace(a,i,a[i]+1),seen)
                if p[i] < a[i]:
                    yield f"consume_allocated({i})", (replace(p,i,p[i]+1),a,seen)
                if p[i] > 0:
                    yield f"finish({i})", (replace(p,i,p[i]-1),a,seen)
                if a[i] > p[i]:
                    yield f"release_quota({i})", (p,replace(a,i,a[i]-1),seen)


def check_induction(initial: State, states: Iterable[State],
                    successors: Callable[[State], Iterable[Action]],
                    invariant: Callable[[State], bool], safety: Callable[[State], bool]) -> dict:
    """Check base, step, implication over a supplied finite candidate domain.

    If states is the full Cartesian state domain, this is a full finite-model
    inductive proof. A reachable-only domain is reported as such by caller.
    """
    base = invariant(initial)
    step, implies = True, True
    checked, eligible = 0, 0
    witness = None
    for s in states:
        checked += 1
        if invariant(s):
            eligible += 1
            if not safety(s):
                implies, witness = False, ("implication",s)
                break
            for label, nxt in successors(s):
                if not invariant(nxt):
                    step, witness = False, ("step",s,label,nxt)
                    break
        if witness:
            break
    return {"base":base,"step":step,"implies_safe":implies,"states_checked":checked,
            "invariant_states_checked":eligible,"witness":witness}
