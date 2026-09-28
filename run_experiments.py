"""Run deterministic exhaustive experiments and write all report data."""
import csv
import itertools
import json
import platform
import sys
from pathlib import Path
from src.masverify import Bridge, Quota, explore, check_induction

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
rows=[]
traces={}
for n in range(2,11):
    for protocol in ('local','check_then_enter','token'):
        m=Bridge(n,protocol)
        r=explore(m.initial,m.successors,m.safe)
        rows.append({'model':'bridge','n':n,'capacity':1,'local_max':1,'protocol':protocol,
                     'safe':r.safe,'discovered_states':r.states,'explored_transitions':r.transitions,
                     'counterexample_steps':len(r.trace)-1 if r.trace else '',
                     'runtime_ms':round(r.seconds*1000,3)})
        if not r.safe and n in (2,3):
            traces[f'bridge_n{n}_{protocol}']=[{'action':a,'state':s} for a,s in r.trace]

for cap in range(1,5):
  for rmax in range(1,3):
    for n in range(2,9):
      for protocol in ('local','pairwise','check_then_commit','quota'):
        m=Quota(n,cap=cap,r=rmax,protocol=protocol)
        r=explore(m.initial,m.successors,m.safe)
        rows.append({'model':'quota','n':n,'capacity':cap,'local_max':rmax,'protocol':protocol,
                     'safe':r.safe,'discovered_states':r.states,'explored_transitions':r.transitions,
                     'counterexample_steps':len(r.trace)-1 if r.trace else '',
                     'runtime_ms':round(r.seconds*1000,3)})
        if not r.safe and n in (2,3) and cap in (1,2) and rmax == 1:
            traces[f'quota_n{n}_B{cap}_{protocol}']=[{'action':a,'state':s} for a,s in r.trace]

# Exact static baseline: test whether pairwise capacity constraints imply the
# global capacity constraint. This is independent of the transition protocol.
static=[]
for cap in range(1,6):
  for rmax in range(1,4):
    for n in range(2,9):
      witness=None; checked=0
      for p in itertools.product(range(rmax+1), repeat=n):
        checked += 1
        pairwise=all(p[i]+p[j] <= cap for i in range(n) for j in range(i+1,n))
        global_safe=sum(p) <= cap
        if pairwise and not global_safe:
          witness=p; break
      static.append({'n':n,'capacity':cap,'local_max':rmax,'pairwise_implies_global':witness is None,
                     'checked_assignments':checked,'witness':witness or ''})

# Check the whole Cartesian domain (including unreachable states) for the
# protocol invariants, so step preservation is a genuine finite-model proof.
cert=[]
for n in range(2,6):
    m=Bridge(n,'token')
    domain=((q,(0,)*n,owner) for q in itertools.product(range(3),repeat=n)
            for owner in range(-1,n))
    c=check_induction(m.initial,domain,m.successors,m.invariant,m.safe)
    cert.append({'model':'bridge','n':n,**c})
for n in range(2,6):
    m=Quota(n,cap=2,r=1,protocol='quota')
    domain=((p,a,(0,)*n) for p in itertools.product(range(2),repeat=n)
            for a in itertools.product(range(2),repeat=n))
    c=check_induction(m.initial,domain,m.successors,m.invariant,m.safe)
    cert.append({'model':'quota','n':n,**c})

with (DATA/'experiments.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(DATA/'counterexamples.json').write_text(json.dumps(traces,ensure_ascii=False,indent=2),encoding='utf-8')
(DATA/'certificates.json').write_text(json.dumps(cert,ensure_ascii=False,indent=2),encoding='utf-8')
(DATA/'static_capacity_sweep.csv').write_text('',encoding='utf8')
with (DATA/'static_capacity_sweep.csv').open('w',newline='',encoding='utf8') as f:
    w=csv.DictWriter(f,fieldnames=list(static[0])); w.writeheader(); w.writerows(static)
(DATA/'provenance.json').write_text(json.dumps({'python':sys.version,'platform':platform.platform(),
    'command':'python run_experiments.py','state_limit':2000000,'deterministic':True,
    'random_seed':None,'models':'bridge: n=2..10; quota: n=2..8, B=1..4, r=1..2; static: n=2..8, B=1..5, r=1..3'},ensure_ascii=False,indent=2),encoding='utf-8')
print('dynamic_cases',len(rows),'static_cases',len(static),'certificates',len(cert))
print('unsafe',sum(not r['safe'] for r in rows))
print('static_pairwise_not_sufficient',sum(not r['pairwise_implies_global'] for r in static))
print('all_certificates_valid',all(c['base'] and c['step'] and c['implies_safe'] for c in cert))
