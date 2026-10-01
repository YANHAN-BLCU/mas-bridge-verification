"""Run experiments A, B and C from the AAMAS supplement.

The command writes all numeric results and witnesses under experiments/.
It does not hard-code expected counts or counterexample lengths.
"""
from __future__ import annotations

import csv, hashlib, json, os, platform, subprocess, sys, time
from itertools import product
from pathlib import Path
from .models import Bridge, Quota, Action, search, replay

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/'results'; TRACES=ROOT/'traces'; CONFIGS=ROOT/'configs'
for p in (RESULTS,TRACES,CONFIGS): p.mkdir(exist_ok=True)

def clean_json(x):
    if isinstance(x, tuple): return [clean_json(v) for v in x]
    if isinstance(x, list): return [clean_json(v) for v in x]
    if isinstance(x, dict): return {k:clean_json(v) for k,v in x.items()}
    return x

def trace_write(config_id, trace, extra=None):
    payload={'config_id':config_id,'steps':clean_json(list(trace))}
    if extra: payload.update(clean_json(extra))
    p=TRACES/f'{config_id}.json'; p.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8'); return p

def base_row(config_id, model, params, variable_domain, result):
    return {'config_id':config_id,'model':model,'parameters':json.dumps(params,ensure_ascii=False,separators=(',',':')),
            'variable_domain':json.dumps(variable_domain,ensure_ascii=False,separators=(',',':')),
            'initial_state':json.dumps(clean_json(result.initial_state),ensure_ascii=False,separators=(',',':')),
            'status':result.status,'discovered_states':result.discovered_states,'expanded_states':result.expanded_states,
            'transitions':result.transitions,'state_limit':result.state_limit,'touched_limit':result.touched_limit,
            'elapsed_ms':result.elapsed_ms,'counterexample_steps':len(result.trace)-1 if result.trace else '',
            'trace_file':f'traces/{config_id}.json' if result.trace else '','violation':result.violation or ''}

def run_a():
    rows=[]; traces={}
    for n in range(2,11):
        for variant in ('local','check_then_enter','token'):
            m=Bridge(n,variant); result=search(m.initial,m.successors,m.safe)
            cid=f'A_bridge_n{n}_{variant}'
            row=base_row(cid,'bridge',{'n':n,'capacity':1,'protocol':variant},
                         {'q':'0=away,1=wait,2=on','seen':'0/1','owner':f'-1..{n-1}'},result)
            if result.trace:
                acts=[s['action'] for s in result.trace if s['action']!='INITIAL']
                ok,_,err=replay(m.initial,acts,m.successors); row['replay_status']='PASS' if ok else 'FAIL'; row['replay_error']=err or ''
                trace_write(cid,result.trace,{'replay_status':row['replay_status'],'target_property':'sum(q_i==on)<=1'})
            else: row['replay_status']='NOT_APPLICABLE'; row['replay_error']=''
            rows.append(row)
    for cap in range(1,5):
        for rmax in range(1,3):
            for n in range(2,9):
                for variant in ('local','pairwise','check_then_commit','quota'):
                    m=Quota(n,cap,rmax,variant); result=search(m.initial,m.successors,m.safe)
                    cid=f'A_quota_n{n}_B{cap}_r{rmax}_{variant}'
                    row=base_row(cid,'quota',{'n':n,'B':cap,'r':rmax,'protocol':variant},
                                 {'p':f'0..{rmax}','a':f'0..{rmax}','seen':'0/1'},result)
                    if result.trace:
                        acts=[s['action'] for s in result.trace if s['action']!='INITIAL']; ok,_,err=replay(m.initial,acts,m.successors)
                        row['replay_status']='PASS' if ok else 'FAIL'; row['replay_error']=err or ''
                        trace_write(cid,result.trace,{'replay_status':row['replay_status'],'target_property':'sum(p_i)<=B'})
                    else: row['replay_status']='NOT_APPLICABLE'; row['replay_error']=''
                    rows.append(row)
    return rows

def run_static():
    rows=[]
    for B in range(1,6):
        for rmax in range(1,4):
            for n in range(2,9):
                witness=None; checked=0
                for p in product(range(rmax+1),repeat=n):
                    checked+=1
                    local=all(0<=x<=rmax for x in p)
                    pairwise=all(p[i]+p[j]<=B for i in range(n) for j in range(i+1,n))
                    global_safe=sum(p)<=B
                    if witness is None and local and pairwise and not global_safe:
                        witness=p
                cid=f'A_static_n{n}_B{B}_r{rmax}'
                row={'config_id':cid,'n':n,'B':B,'r':rmax,'checked_assignments':checked,
                     'total_assignments':(rmax+1)**n,'pairwise_implies_global':witness is None,'witness':json.dumps(witness) if witness else '',
                     'status':'COUNTEREXAMPLE' if witness else 'SAFE_EXHAUSTIVE'}
                if witness: trace_write(cid,[{'action':'STATIC_WITNESS','before':None,'after':witness,'violation':'GLOBAL_CAPACITY'}],{'local':'all p_i<=r','pairwise':'all p_i+p_j<=B','global':'sum(p)<=B'})
                rows.append(row)
    return rows

CLAUSE_REL={
    'bridge':{
        'Request':lambda n:['capacity'], 'Read':lambda n:['capacity'], 'Enter':lambda n:['capacity'],
        'EnterCached':lambda n:['capacity','owned_{i}'], 'Grant':lambda n:['owner_domain','capacity']+[f'owned_{i}' for i in range(n)],
        'EnterToken':lambda n:['capacity','owned_{i}'], 'Cancel':lambda n:['owned_{i}'], 'Exit':lambda n:['capacity','owned_{i}'],
        'Release':lambda n:['owner_domain']+[f'owned_{i}' for i in range(n)],
    },
    'quota':{
        'Consume':lambda n:['nonnegative_{i}','consumption_le_allocation_{i}'],
        'ConsumePairwise':lambda n:['nonnegative_{i}','consumption_le_allocation_{i}'],
        'ReadSpare':lambda n:['total_allocation'], 'CommitCached':lambda n:['nonnegative_{i}','consumption_le_allocation_{i}'],
        'GrantQuota':lambda n:['total_allocation','consumption_le_allocation_{i}'],
        'ConsumeAllocated':lambda n:['nonnegative_{i}','consumption_le_allocation_{i}'],
        'Finish':lambda n:['nonnegative_{i}','consumption_le_allocation_{i}'],
        'ReleaseQuota':lambda n:['total_allocation','consumption_le_allocation_{i}'],
    }
}

def rel_for(model_name, action_id, n):
    """Return a conservative semantic dependency set for an action.

    ``Aff`` remains the syntactic support intersection.  ``Rel`` may be
    larger: bridge capacity and ownership clauses are coupled, as are quota
    allocation and consumption clauses.  Checking the complete relation
    keeps the certificate explicit while avoiding an unsound assumption that
    a single written variable is the only semantic dependency.
    """
    if model_name == 'bridge':
        return ['owner_domain', 'capacity'] + [f'owned_{i}' for i in range(n)]
    return ['total_allocation'] + [f'nonnegative_{i}' for i in range(n)] + [f'consumption_le_allocation_{i}' for i in range(n)]

def all_actions(model):
    actions={}
    for s in model.domain():
        for a in model.successors(s): actions.setdefault(a.action_id,a)
    return actions

def declaration_consistent(model, before, action):
    """Check that an implementation respects Write and indexed Frame claims."""
    after = action.next_state
    names = ('q', 'seen', 'owner') if isinstance(model, Bridge) else ('p', 'a', 'seen')
    old, new = dict(zip(names, before)), dict(zip(names, after))
    import re
    match = re.search(r'\[(\d+)\]', action.action_id)
    index = int(match.group(1)) if match else None
    changed = {name for name in names if old[name] != new[name]}
    if not changed.issubset(set(action.write)):
        return False
    for frame in action.frame:
        if frame.endswith('[j]') and index is not None:
            name = frame[:-3]
            if name in ('q', 'p', 'a', 'seen') and any(old[name][j] != new[name][j] for j in range(len(old[name])) if j != index):
                return False
    return True

def check_cert(model, model_name):
    clauses, supports=model.specs(); actions=all_actions(model); rows=[]
    # Full-domain base and implication checks.
    base=model.invariant(model.initial)
    implication=True; imp_witness=None
    for s in model.domain():
        if model.invariant(s) and not model.safe(s): implication=False; imp_witness=s; break
    # Cache actual full-domain transitions for step/interference checks.
    valid_states=[s for s in model.domain() if model.state_assumptions(s)]
    transitions=[]
    for s in valid_states:
        if model.invariant(s):
            for a in model.successors(s): transitions.append((s,a))
    declaration_ok=all(declaration_consistent(model,s,a) for s in valid_states for a in model.successors(s))
    global_step=all(model.invariant(a.next_state) for _,a in transitions)
    component_ok={}
    comps=sorted({a.component for a in actions.values()})
    for comp in comps:
        component_ok[comp]=all(model.invariant(a.next_state) for s,a in transitions if a.component!=comp)
    for aid,a in sorted(actions.items()):
        prefix=aid.split('[')[0]; rel=rel_for(model_name,aid,model.n)
        aff=[c for c,supp in supports.items() if set(supp)&set(a.write)]
        if prefix in ('Enter','Exit','EnterToken','Cancel','EnterCached','Request','Read','Grant','Release','EarlyRelease','EnvironmentWriteOwner') and model_name=='bridge':
            pass
        # Context and assumptions are checked over the full declared domain.
        context=True; assumption=True; affected=True; unaffected=True; witness=None
        for s in valid_states:
            cs=model.clauses(s)
            gamma=all(cs.get(c,False) for c in rel if c in cs)
            if model.invariant(s) and not gamma: context=False; witness=('context',s); break
            if model.invariant(s) and not model.state_assumptions(s): assumption=False; witness=('assumption',s); break
            for aa in model.successors(s):
                if aa.action_id!=aid: continue
                nxt=aa.next_state; ncs=model.clauses(nxt)
                if gamma and model.state_assumptions(s) and not all(ncs[c] for c in aff): affected=False; witness=('affected',s,nxt); break
                for c in cs:
                    if c not in aff and cs[c] and not ncs[c]: unaffected=False; witness=('unaffected',c,s,nxt); break
                if witness: break
            if witness: break
        comp=component_ok.get(a.component,True)
        result='PASS' if declaration_ok and base and implication and context and assumption and affected and unaffected and comp else 'FAIL'
        rows.append({'model':model_name,'n':model.n,'B':getattr(model,'cap',''),'r':getattr(model,'r',''),'action_id':aid,
                     'component':a.component,'read':json.dumps(a.read),'write':json.dumps(a.write),'frame':json.dumps(a.frame),
                     'clause_id':json.dumps(aff),'Aff':json.dumps(aff),'Rel':json.dumps(rel),
                     'assumption':'finite_domain','obligation_types':'action_declaration;init;implication;context;assumption;affected;unaffected;interference;global_step',
                     'check_scope':'complete_declared_finite_domain','action_declaration':'PASS' if declaration_ok else 'FAIL','init':'PASS' if base else 'FAIL',
                     'implication':'PASS' if implication else 'FAIL','context':'PASS' if context else 'FAIL',
                     'assumption_closed':'PASS' if assumption else 'FAIL','affected':'PASS' if affected else 'FAIL',
                     'unaffected':'PASS' if unaffected else 'FAIL','interference':'PASS' if comp else 'FAIL',
                     'global_step':'PASS' if global_step else 'FAIL','result':result,
                     'witness':json.dumps(clean_json(witness),ensure_ascii=False) if witness else ''})
    return rows

def clean_json(x):
    if isinstance(x,tuple): return [clean_json(v) for v in x]
    if isinstance(x,list): return [clean_json(v) for v in x]
    if isinstance(x,dict): return {k:clean_json(v) for k,v in x.items()}
    return x

def run_b():
    rows=[]
    for n in range(2,6): rows += check_cert(Bridge(n,'token'),'bridge')
    for n in range(2,6): rows += check_cert(Quota(n,2,1,'quota'),'quota')
    return rows

def run_c():
    cases=[('C_stale_bridge','bridge',Bridge(2,'check_then_enter')),
           ('C_early_release','bridge',Bridge(2,'early_release')),
           ('C_non_atomic_quota','quota',Quota(3,2,1,'check_then_commit')),
           ('C_environment_write','bridge',Bridge(2,'env_write'))]
    rows=[]
    for cid,name,m in cases:
        result=search(m.initial,m.successors,m.safe); acts=[s['action'] for s in result.trace if s['action']!='INITIAL']
        replay_ok,_,err=replay(m.initial,acts,m.successors) if result.trace else (False,[], 'no counterexample')
        global_fail=None
        for s in m.domain():
            if m.invariant(s):
                for a in m.successors(s):
                    if not m.invariant(a.next_state): global_fail={'before':clean_json(s),'action':a.action_id,'after':clean_json(a.next_state)}; break
            if global_fail: break
        if result.trace: trace_write(cid,result.trace,{'replay_status':'PASS' if replay_ok else 'FAIL','failed_obligation':'global_step' if global_fail else 'none','variant':name})
        rows.append({'case_id':cid,'model':name,'status':result.status,'target_property':'SAFE','target_violation':result.violation or '',
                     'counterexample_steps':len(result.trace)-1 if result.trace else '','replay_status':'PASS' if replay_ok else 'FAIL',
                     'replay_error':err or '','candidate_invariant_status':'FAIL' if global_fail else 'PASS',
                     'failed_obligation':'global_step' if global_fail else 'none','witness_file':f'traces/{cid}.json' if result.trace else ''})
    return rows

def write_csv(path, rows):
    if not rows: return
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    a=run_a(); static=run_static(); b=run_b(); c=run_c()
    write_csv(RESULTS/'search_results.csv',a); write_csv(RESULTS/'capacity_scan.csv',static); write_csv(RESULTS/'certificate_obligations.csv',b); write_csv(RESULTS/'negative_tests.csv',c)
    (CONFIGS/'scope.json').write_text(json.dumps({'A':{'bridge':'n=2..10','quota':'n=2..8,B=1..4,r=1..2','static':'n=2..8,B=1..5,r=1..3'},'B':'bridge token n=2..5; quota B=2,r=1,n=2..5','C':['stale_bridge','early_release','non_atomic_quota','environment_write'],'state_limit':2000000},ensure_ascii=False,indent=2),encoding='utf8')
    def sha256(path):
        h=hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()
    try:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT.parent,text=True).strip()
    except Exception:
        commit='unavailable'
    memory_gb=None
    if os.name=='nt':
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_=[('dwLength',ctypes.c_ulong),('dwMemoryLoad',ctypes.c_ulong),('ullTotalPhys',ctypes.c_ulonglong),('ullAvailPhys',ctypes.c_ulonglong),('ullTotalPageFile',ctypes.c_ulonglong),('ullAvailPageFile',ctypes.c_ulonglong),('ullTotalVirtual',ctypes.c_ulonglong),('ullAvailVirtual',ctypes.c_ulonglong),('sullAvailExtendedVirtual',ctypes.c_ulonglong)]
            stat=MEMORYSTATUSEX(); stat.dwLength=ctypes.sizeof(MEMORYSTATUSEX); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)); memory_gb=round(stat.ullTotalPhys/1024**3,3)
        except Exception:
            memory_gb=None
    env={'python':sys.version,'platform':platform.platform(),'cpu':platform.processor(),'memory_gb':memory_gb,
         'git_commit':commit,'model_sha256':sha256(ROOT/'models.py'),'runner_sha256':sha256(ROOT/'run_all.py'),
         'deterministic':True,'random_seed':None,'command':'python -m experiments.run_all'}
    (ROOT/'environment.json').write_text(json.dumps(env,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'A_search':len(a),'A_static':len(static),'A_counterexamples':sum(x['status']=='COUNTEREXAMPLE' for x in a),'B_obligations':len(b),'B_pass':sum(x['result']=='PASS' for x in b),'B_fail':sum(x['result']=='FAIL' for x in b),'C_cases':len(c),'C_counterexamples':sum(x['status']=='COUNTEREXAMPLE' for x in c)},ensure_ascii=False))

if __name__=='__main__': main()
