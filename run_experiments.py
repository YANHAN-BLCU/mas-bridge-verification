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
for n in range(2,9):
    for protocol in ('local','check_then_enter','token'):
        m=Bridge(n,protocol)
        r=explore(m.initial,m.successors,m.safe)
        rows.append({'model':'bridge','n':n,'capacity':1,'local_max':1,'protocol':protocol,
                     'safe':r.safe,'discovered_states':r.states,'explored_transitions':r.transitions,
                     'counterexample_steps':len(r.trace)-1 if r.trace else '',
                     'runtime_ms':round(r.seconds*1000,3)})
        if not r.safe and n in (2,3):
            traces[f'bridge_n{n}_{protocol}']=[{'action':a,'state':s} for a,s in r.trace]

for n in range(2,9):
    for protocol in ('local','pairwise','check_then_commit','quota'):
        m=Quota(n,cap=2,r=1,protocol=protocol)
        r=explore(m.initial,m.successors,m.safe)
        rows.append({'model':'quota','n':n,'capacity':2,'local_max':1,'protocol':protocol,
                     'safe':r.safe,'discovered_states':r.states,'explored_transitions':r.transitions,
                     'counterexample_steps':len(r.trace)-1 if r.trace else '',
                     'runtime_ms':round(r.seconds*1000,3)})
        if not r.safe and n in (2,3):
            traces[f'quota_n{n}_{protocol}']=[{'action':a,'state':s} for a,s in r.trace]

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
(DATA/'provenance.json').write_text(json.dumps({'python':sys.version,'platform':platform.platform(),
    'command':'python run_experiments.py','state_limit':2000000,'deterministic':True,
    'random_seed':None,'models':'bridge: n=2..8; quota: n=2..8, B=2, r=1'},ensure_ascii=False,indent=2),encoding='utf-8')
print('cases',len(rows),'certificates',len(cert))
print('unsafe',sum(not r['safe'] for r in rows))
print('all_certificates_valid',all(c['base'] and c['step'] and c['implies_safe'] for c in cert))
