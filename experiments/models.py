from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from time import perf_counter
from typing import Callable, Iterable


@dataclass(frozen=True)
class Action:
    action_id: str
    component: str
    read: tuple[str, ...]
    write: tuple[str, ...]
    frame: tuple[str, ...]
    next_state: tuple


@dataclass(frozen=True)
class SearchResult:
    status: str
    initial_state: tuple
    discovered_states: int
    expanded_states: int
    transitions: int
    elapsed_ms: float
    state_limit: int
    touched_limit: bool
    trace: tuple[dict, ...]
    violation: str | None


def _set(t: tuple, i: int, value: int) -> tuple:
    return t[:i] + (value,) + t[i + 1:]


def search(initial: tuple, successors: Callable[[tuple], Iterable[Action]],
           is_safe: Callable[[tuple], bool], state_limit: int = 2_000_000) -> SearchResult:
    from collections import deque
    start = perf_counter(); queue = deque([initial])
    parent: dict[tuple, tuple[tuple | None, Action | None]] = {initial: (None, None)}
    expanded = transitions = 0
    while queue:
        state = queue.popleft(); expanded += 1
        if not is_safe(state):
            items=[]; cur=state
            while cur is not None:
                prev, act=parent[cur]
                items.append({'action': act.action_id if act else 'INITIAL', 'component': act.component if act else 'INIT',
                              'before': prev, 'after': cur, 'violation': 'TARGET_UNSAFE'})
                cur=prev
            items.reverse()
            return SearchResult('COUNTEREXAMPLE',initial,len(parent),expanded,transitions,
                                round((perf_counter()-start)*1000,3),state_limit,False,tuple(items),'TARGET_UNSAFE')
        for act in successors(state):
            transitions += 1; nxt=act.next_state
            if nxt not in parent:
                parent[nxt]=(state,act); queue.append(nxt)
                if len(parent)>state_limit:
                    return SearchResult('UNKNOWN_LIMIT',initial,len(parent),expanded,transitions,
                                        round((perf_counter()-start)*1000,3),state_limit,True,(),None)
    return SearchResult('SAFE_EXHAUSTIVE',initial,len(parent),expanded,transitions,
                        round((perf_counter()-start)*1000,3),state_limit,False,(),None)


class Bridge:
    """Finite narrow-bridge model.

    q: 0=away, 1=waiting, 2=on; seen: cached free bit; owner=-1 means none.
    Variants are correct protocols or one-condition failures for experiment C.
    """
    def __init__(self, n: int, variant: str):
        assert n >= 2
        self.n, self.variant = n, variant
        self.initial=((0,)*n,(0,)*n,-1)

    def domain(self):
        return product(product(range(3), repeat=self.n), product(range(2), repeat=self.n), range(-1,self.n))

    def state_assumptions(self,s):
        q,seen,owner=s
        return len(q)==self.n and len(seen)==self.n and all(x in (0,1,2) for x in q) and all(x in (0,1) for x in seen) and -1<=owner<self.n

    def safe(self,s): return sum(x==2 for x in s[0])<=1

    def clauses(self,s):
        q,seen,owner=s
        out={'owner_domain': -1<=owner<self.n,
             'capacity': sum(x==2 for x in q)<=1}
        for i in range(self.n): out[f'owned_{i}']=(q[i]!=2 or owner==i)
        return out

    def invariant(self,s): return all(self.clauses(s).values())

    def successors(self,s):
        q,seen,owner=s
        for i in range(self.n):
            if q[i]==0:
                yield Action(f'Request[{i}]','agent',('q',),('q',),("q[j]",),(_set(q,i,1),seen,owner))
            elif q[i]==1:
                if self.variant=='local':
                    yield Action(f'Enter[{i}]','agent',('q',),('q',),("q[j]",),(_set(q,i,2),seen,owner))
                elif self.variant in ('check_then_enter','stale_check'):
                    if not seen[i] and all(x!=2 for x in q):
                        yield Action(f'Read[{i}]','agent',('q',),('seen',),("q[j]",), (q,_set(seen,i,1),owner))
                    if seen[i]:
                        yield Action(f'EnterCached[{i}]','agent',('seen',),('q','seen'),("q[j]",),(_set(q,i,2),_set(seen,i,0),owner))
                else:
                    if owner==-1:
                        yield Action(f'Grant[{i}]','manager',('owner','q'),('owner',),('q[j]',), (q,seen,i))
                    if owner==i:
                        yield Action(f'EnterToken[{i}]','agent',('owner','q'),('q',),("q[j]",),(_set(q,i,2),seen,owner))
                    if owner==i:
                        yield Action(f'Cancel[{i}]','agent',('owner','q'),('q',),("q[j]",),(_set(q,i,0),seen,owner))
            else:
                yield Action(f'Exit[{i}]','agent',('q',),('q',),("q[j]",),(_set(q,i,0),seen,owner))
            if self.variant=='token' and owner==i and q[i]==0:
                yield Action(f'Release[{i}]','manager',('owner','q'),('owner',),("q[j]",), (q,seen,-1))
            if self.variant=='early_release' and owner==i and q[i] in (1,2):
                yield Action(f'EarlyRelease[{i}]','manager',('owner','q'),('owner',),("q[j]",), (q,seen,-1))
        if self.variant=='env_write':
            yield Action('EnvironmentWriteOwner','environment',('owner',),('owner',),('q[j]',), (q,seen,-1))

    def specs(self):
        clauses={k:tuple(['owner'] if k=='owner_domain' else ['q'] if k=='capacity' else ['q','owner']) for k in self.clauses(self.initial)}
        return clauses, clauses.copy()


class Quota:
    """Finite resource model. p=consumption, a=allocation, seen=cached spare bit."""
    def __init__(self,n:int,cap:int,r:int,variant:str):
        assert n>=2 and cap>=1 and r>=1
        self.n,self.cap,self.r,self.variant=n,cap,r,variant
        self.initial=((0,)*n,(0,)*n,(0,)*n)

    def domain(self): return product(product(range(self.r+1),repeat=self.n), product(range(self.r+1),repeat=self.n), product(range(2),repeat=self.n))
    def state_assumptions(self,s):
        p,a,seen=s
        return len(p)==self.n and len(a)==self.n and all(0<=x<=self.r for x in p+a) and all(x in (0,1) for x in seen)
    def safe(self,s): return sum(s[0])<=self.cap
    def clauses(self,s):
        p,a,_=s; out={'total_allocation':sum(a)<=self.cap}
        for i in range(self.n): out[f'nonnegative_{i}']=(p[i]>=0); out[f'consumption_le_allocation_{i}']=(p[i]<=a[i])
        return out
    def invariant(self,s): return all(self.clauses(s).values())
    def successors(self,s):
        p,a,seen=s
        for i in range(self.n):
            if self.variant=='local' and p[i]<self.r:
                yield Action(f'Consume[{i}]','agent',('p',),('p',),('p[j]',),(_set(p,i,p[i]+1),a,seen))
            elif self.variant=='pairwise' and p[i]<self.r and all(p[i]+1+p[j]<=self.cap for j in range(self.n) if j!=i):
                yield Action(f'ConsumePairwise[{i}]','agent',('p',),('p',),('p[j]',),(_set(p,i,p[i]+1),a,seen))
            elif self.variant=='check_then_commit':
                if p[i]<self.r and not seen[i] and sum(p)<self.cap:
                    yield Action(f'ReadSpare[{i}]','agent',('p',),('seen',),('p[j]',),(p,a,_set(seen,i,1)))
                if p[i]<self.r and seen[i]:
                    yield Action(f'CommitCached[{i}]','agent',('seen',),('p','seen'),('p[j]',),(_set(p,i,p[i]+1),a,_set(seen,i,0)))
            else:
                if a[i]<self.r and sum(a)<self.cap:
                    yield Action(f'GrantQuota[{i}]','manager',('a',),('a',),('a[j]',),(p,_set(a,i,a[i]+1),seen))
                if p[i]<a[i]:
                    yield Action(f'ConsumeAllocated[{i}]','agent',('p','a'),('p',),('p[j]',),(_set(p,i,p[i]+1),a,seen))
                if p[i]>0:
                    yield Action(f'Finish[{i}]','agent',('p',),('p',),('p[j]',),(_set(p,i,p[i]-1),a,seen))
                if a[i]>p[i]:
                    yield Action(f'ReleaseQuota[{i}]','manager',('p','a'),('a',),('a[j]',),(p,_set(a,i,a[i]-1),seen))
    def specs(self):
        clauses={'total_allocation':tuple(['a'])}
        for i in range(self.n): clauses[f'nonnegative_{i}']=('p',); clauses[f'consumption_le_allocation_{i}']=('p','a')
        return clauses,clauses.copy()


def replay(initial, actions, successors):
    state=initial; seen=[{'action':'INITIAL','before':None,'after':state}]
    for expected in actions:
        options={a.action_id:a for a in successors(state)}
        if expected not in options: return False, seen, f'action not enabled: {expected}'
        nxt=options[expected].next_state; seen.append({'action':expected,'before':state,'after':nxt}); state=nxt
    return True,seen,None
