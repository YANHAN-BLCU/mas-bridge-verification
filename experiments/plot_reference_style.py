"""Export eight figures from verified finite-state artifacts (no new experiments).

Run: python -m experiments.plot_reference_style
English labels use Comic Sans MS. Source CSVs record every plotted value.
"""
from __future__ import annotations

import csv
import hashlib
import json
import warnings
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.text import Text
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'
OUT = ROOT / 'figures' / 'reference_style'
DATA = OUT / 'source_data'
RED, BLUE, GREEN, ORANGE, PURPLE, CYAN = (
    '#FF4148', '#4740FF', '#329C40', '#FFAA24', '#9A32AC', '#10BEC9')
PALETTE = [RED, BLUE, GREEN, ORANGE, PURPLE, CYAN]
CHECKS = ['action_declaration', 'init', 'implication', 'context',
          'assumption_closed', 'affected', 'unaffected', 'interference', 'global_step']
FIGURES, QA, WARNINGS = [], [], []


def read_csv(name):
    with (RESULTS / name).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(name, rows):
    with (DATA / (name + '.csv')).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def style():
    font = Path('C:/Windows/Fonts/comic.ttf')
    bold = Path('C:/Windows/Fonts/comicbd.ttf')
    if not font.exists():
        raise RuntimeError('Comic Sans MS is required for this figure style')
    font_manager.fontManager.addfont(font)
    font_manager.fontManager.addfont(bold)
    plt.rcParams.update({
        'font.family': 'Comic Sans MS', 'font.size': 8.5,
        'axes.titlesize': 10, 'axes.titleweight': 'bold', 'axes.labelsize': 9,
        'axes.labelweight': 'bold', 'xtick.labelsize': 8, 'ytick.labelsize': 8,
        'axes.linewidth': .65, 'axes.spines.top': True, 'axes.spines.right': True,
        'grid.color': '#B0B0B0', 'grid.linewidth': .45, 'grid.alpha': .65,
        'axes.axisbelow': True, 'legend.fontsize': 8, 'legend.frameon': True,
        'legend.framealpha': .9, 'legend.edgecolor': '#DDDDDD',
        'lines.linewidth': 1.7, 'lines.markersize': 5,
        'pdf.fonttype': 42, 'svg.fonttype': 'none', 'savefig.dpi': 600,
        'figure.facecolor': 'white', 'axes.facecolor': 'white',
        'mathtext.fontset': 'dejavusans', 'text.usetex': False,
    })


def title(fig, text):
    fig.suptitle(text, fontsize=12, fontweight='bold', y=.98)


def panel(ax, text):
    ax.set_title(text, loc='left', pad=8)


def save(fig, name, caption_cn, caption_en, claim, sources):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    outside = []
    for t in fig.findobj(Text):
        if not t.get_visible() or not t.get_text():
            continue
        b = t.get_window_extent(renderer)
        if b.width and b.height and (b.x0 < -2 or b.y0 < -2 or b.x1 > bounds.x1+2 or b.y1 > bounds.y1+2):
            # Tick labels created by a locator outside the visible data limits
            # are clipped by Matplotlib and are not part of the printed figure.
            if t.axes is None or t.get_clip_on() is False:
                outside.append(t.get_text())
    QA.append({'figure': name, 'canvas_width_mm': round(fig.get_figwidth()*25.4, 1),
               'canvas_height_mm': round(fig.get_figheight()*25.4, 1),
               'text_outside_canvas': sorted(set(outside)),
               'source_csv': 'source_data/'+name+'.csv'})
    for fmt in ['pdf', 'svg', 'png']:
        fig.savefig(OUT / (name+'.'+fmt), dpi=600, facecolor='white')
    FIGURES.append({'name': name, 'caption_cn': caption_cn, 'caption_en': caption_en,
                    'claim': claim, 'sources': sources})
    plt.close(fig)


def fig01(search):
    name = 'fig01_A_bridge_scaling'
    rows = sorted([r for r in search if r['model']=='bridge'], key=lambda r:(r['protocol'],r['n']))
    write_csv(name, [{'config_id':r['config_id'], 'n':r['n'], 'protocol':r['protocol'],
                     'status':r['status'], 'discovered_states':int(r['discovered_states']),
                     'shortest_counterexample_steps':r['counterexample_steps']} for r in rows])
    fig, axes = plt.subplots(1,2,figsize=(7.2,3.05))
    fig.subplots_adjust(left=.095, right=.975, bottom=.19, top=.72, wspace=.3)
    title(fig,'A | Bridge protocols over system size')
    specs=[('local','Local',RED,'o'),('check_then_enter','Cached entry',BLUE,'s'),('token','Atomic token',GREEN,'D')]
    for protocol,label,color,marker in specs:
        a=[r for r in rows if r['protocol']==protocol]
        axes[0].plot([r['n'] for r in a], [int(r['discovered_states']) for r in a], color=color,marker=marker,alpha=.9,label=label)
        bad=[r for r in a if r['status']=='COUNTEREXAMPLE']
        if bad:
            axes[1].plot([r['n'] for r in bad], [int(r['counterexample_steps']) for r in bad], color=color,marker=marker,alpha=.9)
    axes[0].set_yscale('log'); axes[0].set_ylabel('Discovered states (log scale)')
    axes[1].set_ylim(0,8); axes[1].set_yticks(range(0,9,2)); axes[1].set_ylabel('Shortest counterexample (steps)')
    axes[1].text(.04,.9,'Atomic token: 0/9 counterexamples',transform=axes[1].transAxes,color=GREEN,fontsize=8)
    for ax in axes:
        ax.set_xlabel('Number of agents, n'); ax.set_xticks(range(2,11)); ax.grid(True)
    panel(axes[0],'a  BFS exploration'); panel(axes[1],'b  Reachable violations')
    fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.875),ncol=3)
    save(fig,name,
         '实验 A 的窄桥规模扫描。左图为 BFS 已发现状态数（对数轴）；反例配置在首个反例处停止，安全配置穷尽搜索。右图只绘制存在反例的配置，令牌协议的安全结果不记作零步反例。共 27 个配置。',
         'Bridge size sweep in Experiment A (27 configurations). Discovered states use a log axis; unsafe searches stop at the first counterexample and safe searches are exhaustive. Counterexample length is defined only for unsafe configurations.',
         'Local and cached bridge protocols admit violations at every tested size; the atomic token protocol is safe in these finite models.', ['search_results.csv'])


def fig02(search):
    name='fig02_A_quota_outcome_map'
    rows=[r for r in search if r['model']=='quota']
    write_csv(name,[{'config_id':r['config_id'],'n':r['n'],'B':r['B'],'r':r['r'],'protocol':r['protocol'],'status':r['status']} for r in rows])
    fig,axes=plt.subplots(2,4,figsize=(7.2,4.15),sharex=True,sharey=True)
    fig.subplots_adjust(left=.14,right=.985,bottom=.15,top=.76,hspace=.4,wspace=.15)
    title(fig,'A | Quota safety across the full parameter grid')
    protocols=['local','pairwise','check_then_commit','quota']
    labels=['Local','Pairwise','Cached commit','Atomic quota']
    for i,rval in enumerate([1,2]):
        for j,budget in enumerate(range(1,5)):
            ax=axes[i,j]
            for y,protocol in enumerate(protocols):
                for n in range(2,9):
                    row=next(r for r in rows if r['r']==rval and r['B']==budget and r['protocol']==protocol and r['n']==n)
                    safe=row['status']=='SAFE_EXHAUSTIVE'
                    ax.scatter(n,y,s=40,marker='s' if safe else 'X',color=CYAN if safe else RED,alpha=.9,edgecolors='white',linewidths=.3)
            ax.set_xlim(1.5,8.5);ax.set_ylim(3.5,-.5);ax.set_xticks(range(2,9));ax.set_yticks(range(4),labels=labels)
            ax.set_title(f'r = {rval}, B = {budget}',fontsize=9)
            ax.grid(True)
    fig.legend(handles=[Line2D([],[],marker='s',ls='',color=CYAN,label='Exhaustively safe'),Line2D([],[],marker='X',ls='',color=RED,label='Counterexample')],loc='upper center',bbox_to_anchor=(.56,.88),ncol=2)
    fig.supxlabel('Number of agents, n',y=.04,fontsize=9,fontweight='bold')
    save(fig,name,
         '实验 A 配额模型全部 224 个配置的结果。行对应单体上限 r，列对应容量 B；每个子图展示四类协议与智能体数 n。方块表示穷尽安全，叉号表示可达反例。',
         'Outcomes for all 224 quota configurations in Experiment A. Panel rows vary the local bound r and columns vary capacity B. Squares denote exhaustive safety; crosses denote reachable counterexamples.',
         'Atomic quota is safe across the tested grid; local, pairwise and cached constraints admit violations when the collective load exceeds capacity.', ['search_results.csv'])


def fig03():
    name='fig03_A_static_capacity_gaps'
    rows=read_csv('capacity_scan.csv')
    data=[]
    for r in rows:
        witness=json.loads(r['witness']) if r['witness'] else None
        excess=sum(witness)-int(r['B']) if witness else 0
        if witness:
            assert max(witness)<=int(r['r'])
            assert all(witness[i]+witness[j]<=int(r['B']) for i in range(len(witness)) for j in range(i+1,len(witness)))
            assert excess>0
        data.append({'config_id':r['config_id'],'n':int(r['n']),'B':int(r['B']),'r':int(r['r']),
                     'status':r['status'],'witness':r['witness'],'saved_witness_excess':excess})
    write_csv(name,data)
    fig,axes=plt.subplots(1,3,figsize=(7.2,3.35),sharey=True)
    fig.subplots_adjust(left=.09,right=.985,bottom=.2,top=.75,wspace=.16)
    title(fig,'A | Pairwise checks leave collective capacity gaps')
    cmap=colors.ListedColormap(['#C6F3F5','#FFCFD2'])
    for ax,rval in zip(axes,[1,2,3]):
        sub=[r for r in data if r['r']==rval]
        vals=np.array([[next(r for r in sub if r['n']==n and r['B']==b)['saved_witness_excess'] for n in range(2,9)] for b in range(1,6)])
        ax.imshow((vals>0).astype(int),cmap=cmap,vmin=0,vmax=1,origin='lower',aspect='auto')
        for i,j in np.ndindex(vals.shape):
            ax.text(j,i,str(vals[i,j]) if vals[i,j] else '-',ha='center',va='center',fontsize=9,fontweight='bold',color='#950024' if vals[i,j] else '#12676B')
        ax.set_xticks(range(7),labels=range(2,9));ax.set_yticks(range(5),labels=range(1,6));ax.set_xlabel('Number of agents, n');ax.set_title(f'Local bound r = {rval}')
        ax.set_xticks(np.arange(-.5,7,.1)[::10],minor=True);ax.set_yticks(np.arange(-.5,5,1),minor=True);ax.grid(which='minor',color='white',linewidth=1);ax.tick_params(which='minor',bottom=False,left=False)
    axes[0].set_ylabel('Capacity, B')
    fig.legend(handles=[Patch(facecolor='#C6F3F5',label='No gap (-)'),Patch(facecolor='#FFCFD2',label='Gap: saved witness overload')],loc='upper center',bbox_to_anchor=(.52,.875),ncol=2)
    save(fig,name,
         '实验 A 静态容量扫描（105 个配置）。66 个配置存在满足全部个体及两两约束、却违反群体容量的见证。红色单元中的整数是已保存见证的超额量 Σp_i−B，不是最大超额；蓝色横线表示穷尽扫描未发现缺口。',
         'Static capacity scan over 105 configurations. A gap exists in 66 configurations. Red-cell values are the overload of the saved witness, sum(p_i)-B, rather than maximal overload; cyan cells mark configurations with no gap after exhaustive scanning.',
         'Pairwise capacity checks do not generally imply the collective constraint.', ['capacity_scan.csv'])


def fig04():
    name='fig04_B_certificate_coverage'
    rows=read_csv('certificate_obligations.csv')
    assert len(rows)==140 and all(r['result']=='PASS' for r in rows)
    groups=[(m,n) for m in ['bridge','quota'] for n in range(2,6)]
    data=[]
    for model,n in groups:
        subset=[r for r in rows if r['model']==model and int(r['n'])==n]
        for check in CHECKS:
            data.append({'model':model,'n':n,'check':check,'action_records':len(subset),'passed_records':sum(r[check]=='PASS' for r in subset)})
    write_csv(name,data)
    fig=plt.figure(figsize=(7.2,3.75))
    gs=fig.add_gridspec(1,2,width_ratios=[1,2.65],left=.09,right=.985,bottom=.23,top=.78,wspace=.4)
    left=fig.add_subplot(gs[0]);right=fig.add_subplot(gs[1])
    title(fig,'B | All 140 action records pass every certificate check')
    for model,label,color,marker in [('bridge','Atomic token',BLUE,'s'),('quota','Atomic quota',GREEN,'D')]:
        vals=[next(r for r in data if r['model']==model and r['n']==n)['action_records'] for n in range(2,6)]
        left.plot(range(2,6),vals,marker=marker,color=color,label=label)
    left.set_ylim(0,34);left.set_xticks(range(2,6));left.set_xlabel('Agents, n');left.set_ylabel('Action records');left.grid(True);left.legend(fontsize=7,loc='upper left')
    panel(left,'a  Finite-domain coverage')
    for y,(model,n) in enumerate(groups):
        color=BLUE if model=='bridge' else GREEN
        for x,check in enumerate(CHECKS):
            count=next(r for r in data if r['model']==model and r['n']==n and r['check']==check)['passed_records']
            right.scatter(x,y,s=230,color=color,alpha=.16,marker='s',edgecolor=color,linewidth=.5)
            right.text(x,y,str(count),ha='center',va='center',fontsize=7.5,color=color)
    right.set_xticks(range(9),labels=['Decl.','Init','Safety','Context','Assump.','Aff.','Frame','Interf.','Global'],rotation=55,ha='right')
    right.set_yticks(range(8),labels=[('Token' if m=='bridge' else 'Quota')+f' n={n}' for m,n in groups]);right.set_ylim(7.5,-.5);right.set_xlim(-.6,8.6)
    panel(right,'b  Passed records per check')
    save(fig,name,
         '实验 B 的动作级证书覆盖。左图统计各有限域配置的动作记录数；右图每个单元显示通过该项检查的动作记录数。各列重复检查同一组 140 条记录，不能相加视作独立样本。Decl. 为读写声明，Aff./Frame 为受影响及未受影响保持，Interf. 为组件干扰，Global 为全局一步保持。',
         'Action-level certificate coverage in Experiment B. The left panel counts action records for eight finite configurations; cells on the right count records passing each check. Columns evaluate the same 140 records and are not independent samples.',
         'The supplied atomic protocols pass all declared-domain certificate checks for all eight configurations.', ['certificate_obligations.csv'])


def fig05():
    name='fig05_C_coordination_failure_traces'
    tests=read_csv('negative_tests.csv')
    order=['C_stale_bridge','C_early_release','C_non_atomic_quota','C_environment_write']
    labels=['a  Stale bridge check','b  Early token release','c  Non-atomic quota','d  Environment overwrite']
    data=[]
    fig,axes=plt.subplots(2,2,figsize=(7.2,4.5),sharey=True)
    fig.subplots_adjust(left=.1,right=.985,bottom=.12,top=.83,hspace=.58,wspace=.24)
    title(fig,'C | Coordination failures replay as safety violations')
    for ax,case,label,color,marker in zip(axes.flat,order,labels,[RED,BLUE,ORANGE,PURPLE],['o','s','^','v']):
        row=next(r for r in tests if r['case_id']==case)
        trace=json.loads((ROOT/row['witness_file']).read_text(encoding='utf-8'))
        cap=2 if row['model']=='quota' else 1
        loads=[]
        for step,s in enumerate(trace['steps']):
            load=sum(s['after'][0]) if row['model']=='quota' else sum(x==2 for x in s['after'][0])
            loads.append(load/cap)
            data.append({'case':case,'model':row['model'],'step':step,'action':s['action'],'load':load,'capacity':cap,'load_capacity_ratio':load/cap,'replay_status':row['replay_status']})
        assert len(loads)-1==int(row['counterexample_steps']) and loads[-1]>1
        ax.axhspan(1,2.2,color=RED,alpha=.06);ax.axhline(1,color='#555555',ls='--',lw=1)
        ax.step(range(len(loads)),loads,where='post',color=color,alpha=.95)
        ax.plot(range(len(loads)),loads,ls='',marker=marker,color=color,alpha=.8)
        ax.scatter(len(loads)-1,loads[-1],color=RED,marker='X',s=48,zorder=5)
        ax.set_xlim(-.2,8.4);ax.set_ylim(-.05,2.25);ax.set_xticks(range(0,9));ax.set_yticks([0,.5,1,1.5,2]);ax.set_xlabel('Trace step (0 = initial)');ax.grid(True)
        ax.annotate(f'{len(loads)-1} steps; replay PASS',xy=(len(loads)-1,loads[-1]),xytext=(.06,.77),textcoords='axes fraction',fontsize=8,color=color,
                    arrowprops={'arrowstyle':'->','color':color,'lw':1})
        panel(ax,label)
    axes[0,0].set_ylabel('Load / capacity');axes[1,0].set_ylabel('Load / capacity')
    write_csv(name,data)
    save(fig,name,
         '实验 C 四种协调失效的独立重放轨迹。窄桥负载为在桥智能体数（容量 1）；配额负载为总消耗（容量 2）。纵轴为负载/容量，虚线是安全边界。红叉仅标注最终违规状态；反例长度分别为 6、7、6、7 步。',
         'Independently replayed traces for four coordination failures in Experiment C. Bridge load counts agents on the bridge (capacity 1); quota load is total consumption (capacity 2). The dashed line is the safety boundary, with final violations marked by crosses.',
         'Each coordination mutation produces a replayable capacity violation in its supplied finite model.', ['negative_tests.csv','traces/C_*.json'])


def fig06(minimal):
    name='fig06_D_minimum_context_scaling'
    rows=minimal['bridge']
    data=[]
    for r in rows:
        full=r['full_context_clause_occurrences'];small=r['minimum_context_clause_occurrences']
        data.append({'n':r['n'],'affected_action_target_pairs':r['affected_action_target_pairs'],
                     'full_context_occurrences':full,'affected_only_occurrences':r['affected_only_clause_occurrences'],
                     'minimum_context_occurrences':small,'reduction_percent':100*(1-small/full),
                     'maximum_minimum_cardinality':r['maximum_minimum_context_cardinality']})
    assert [r['minimum_context_occurrences'] for r in data]==[6,18,36]
    write_csv(name,data)
    fig,axes=plt.subplots(1,2,figsize=(7.2,3.05))
    fig.subplots_adjust(left=.105,right=.98,bottom=.19,top=.75,wspace=.37)
    title(fig,'D | Minimal contexts reduce repeated proof premises')
    for key,label,color,marker in [('full_context_occurrences','Full context',RED,'o'),('affected_only_occurrences','Affected only',BLUE,'s'),('minimum_context_occurrences','Minimum context',CYAN,'>')]:
        axes[0].plot([r['n'] for r in data],[r[key] for r in data],marker=marker,color=color,alpha=.9,label=label)
    axes[0].set_ylim(0,880);axes[0].set_ylabel('Clause occurrences');axes[0].set_yticks(range(0,901,200))
    axes[1].plot([r['n'] for r in data],[r['reduction_percent'] for r in data],marker='D',color=GREEN)
    axes[1].set_ylim(0,105);axes[1].set_yticks(range(0,101,20));axes[1].set_ylabel('Reduction vs full context (%)')
    for r in data:
        axes[1].annotate(f"{r['reduction_percent']:.1f}%",(r['n'],r['reduction_percent']),xytext=(0,-18),textcoords='offset points',ha='center',color=GREEN,fontsize=8)
    for ax in axes:
        ax.set_xticks([2,3,4]);ax.set_xlim(1.85,4.15);ax.set_xlabel('Number of agents, n');ax.grid(True)
    panel(axes[0],'a  Premise representation');panel(axes[1],'b  Relative reduction')
    fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.875),ncol=3)
    save(fig,name,
         '实验 D 显式共享类窄桥的证明前提计数。全部前提、仅受影响前提与基数最小前提在同一批动作–目标对上比较；最小前提出现次数为 6、18、36，相对全部前提减少 90.0%、93.3%、95.5%。指标只度量逐目标前提的重复表示，不代表运行时间、通信或状态空间收益。',
         'Proof-premise occurrences for the explicit shared-class bridge in Experiment D. All methods use the same action-target pairs. Minimum-context occurrences are 6, 18 and 36, a reduction of 90.0%, 93.3% and 95.5%. This metric describes premise representation, not runtime or communication speedup.',
         'The minimum-context representation uses fewer repeated premises than the full or affected-only representations.', ['minimal_context_results.json'])


def fig07(minimal):
    name='fig07_D_action_target_contexts'
    model=next(r for r in minimal['bridge'] if r['n']==4)
    rec=model['records']
    actions=[f'{kind}_{i}' for kind in ['Request','Grant','Enter','Exit','Release'] for i in range(1,5)]
    targets=[f'tau_{i}' for i in range(1,5)]+[f'zeta_kappa_{i}_{j}' for i in range(1,5) for j in range(i+1,5)]
    matrix=np.full((20,10),-1,dtype=int)
    data=[]
    for y,action in enumerate(actions):
        for x,target in enumerate(targets):
            row=next((r for r in rec if r['action']==action and r['target']==target),None)
            if row: matrix[y,x]=row['cardinality']
            data.append({'n':4,'action':action,'target':target,'affected':row is not None,
                         'minimum_cardinality':row['cardinality'] if row else '',
                         'context':json.dumps(row['context']) if row else ''})
    assert np.sum(matrix>=0)==80 and np.sum(matrix==1)==36
    write_csv(name,data)
    fig,ax=plt.subplots(figsize=(7.2,5.2))
    fig.subplots_adjust(left=.18,right=.985,bottom=.155,top=.855)
    title(fig,'D | One premise per affected target is enough (n = 4)')
    ax.imshow(matrix,cmap=colors.ListedColormap(['#F2F2F2','#CDF3F6','#DDD8FF']),vmin=-1,vmax=1,aspect='auto')
    for y,x in np.ndindex(matrix.shape):
        if matrix[y,x]>=0:
            ax.text(x,y,str(matrix[y,x]),ha='center',va='center',color=BLUE if matrix[y,x] else '#08717A',fontsize=8)
    ax.set_xticks(range(10),labels=[f'tok-{i}' for i in range(1,5)]+[f'share-{i}{j}' for i in range(1,5) for j in range(i+1,5)],rotation=40,ha='right')
    ax.set_yticks(range(20),labels=[a.replace('_',' ') for a in actions],fontsize=8)
    ax.set_xticks(np.arange(-.5,10,1),minor=True);ax.set_yticks(np.arange(-.5,20,1),minor=True);ax.grid(which='minor',color='white',lw=.7);ax.tick_params(which='minor',length=0)
    for y in [3.5,7.5,11.5,15.5]: ax.axhline(y,color='#999999',lw=.8)
    ax.axvline(3.5,color='#999999',lw=.8)
    ax.set_xlabel('Target invariant clause')
    fig.legend(handles=[Patch(facecolor='#F2F2F2',label='Unaffected (frame)'),Patch(facecolor='#CDF3F6',label='0: empty context'),Patch(facecolor='#DDD8FF',label='1: one premise')],loc='upper center',bbox_to_anchor=(.54,.936),ncol=3,fontsize=7.5)
    save(fig,name,
         '实验 D 在 n=4 时的逐动作、逐目标最小前提矩阵。20 个动作对应 10 个不变式子句，共 80 个受影响动作–目标对；44 个取空上下文，36 个仅需一个前提。灰格为未受影响目标，由帧条件保持。tok-i 对应所有权子句，share-ij 对应共享类一致性子句；数值不统计动作守卫或环境假设。',
         'Minimum premise cardinalities for n=4 in Experiment D. Of 80 affected action-target pairs, 44 require no premise and 36 require one. Gray cells are unaffected targets preserved by frame conditions. tok-i denotes ownership and share-ij shared-class consistency; guards and environment assumptions are excluded.',
         'Proof dependencies are sparse and action-specific in the fixed shared-class bridge clause family.', ['minimal_context_results.json'])


def fig08(generated):
    name='fig08_D_certificate_diagnosis'
    faults=generated['fault_mutations']
    labels=['Missing ownership guard','Early token release','Split shared-state refresh','Environment overwrite','Incorrect write metadata','Missing token template','Missing budget guard','Unsafe quota reclaim','Missing budget template']
    data=[]
    fig,ax=plt.subplots(figsize=(7.2,4.35))
    fig.subplots_adjust(left=.365,right=.98,bottom=.21,top=.77)
    title(fig,'D | Failure to prove and reachable unsafety are distinct')
    ax.set_xlim(-.5,3.5);ax.set_ylim(8.5,-.5)
    for y,(r,label) in enumerate(zip(faults,labels)):
        status=r['certificate_status'];reachable=r['reachable_safety']['status']
        retained=len(r['template_pruning']['retained']);removed=len(r['template_pruning']['removed']);total=retained+removed
        counter=r['reachable_safety'].get('counterexample')
        steps=counter['length'] if counter else ''
        record={'case':r['name'],'certificate_status':status,'BFS_target_status':reachable,'retained_templates':retained,'supplied_templates':total,'reachable_counterexample_steps':steps}
        data.append(record)
        cert='Proved' if status=='proved' else ('Blocked' if status.startswith('blocked') else 'Not proved')
        texts=[cert,'Safe' if reachable=='safe' else 'Unsafe',f'{retained}/{total}',str(steps) if steps else '-']
        tones=[GREEN if cert=='Proved' else (PURPLE if cert=='Blocked' else ORANGE),CYAN if reachable=='safe' else RED,BLUE,RED if steps else '#777777']
        for x,(text,color) in enumerate(zip(texts,tones)):
            ax.add_patch(plt.Rectangle((x-.49,y-.47),.98,.94,color=color,alpha=.1,lw=0))
            ax.text(x,y,text,ha='center',va='center',color=color,fontsize=8.5,fontweight='bold')
    ax.set_yticks(range(9),labels=labels);ax.set_xticks(range(4),labels=['Certificate','BFS target','Kept / supplied','Trace steps']);ax.xaxis.tick_top();ax.tick_params(length=0)
    for sp in ax.spines.values():sp.set_visible(False)
    fig.text(.53,.1,'All 6 correct instances: proved and safe.\n9 mutations: 5 unsafe, 4 safe; 1 blocked by metadata.',ha='center',fontsize=8,color='#444444')
    assert len(faults)==9 and sum(r['BFS_target_status']=='unsafe' for r in data)==5
    write_csv(name,data)
    save(fig,name,
         '实验 D 九个故障及元数据变体的证书诊断。证书状态、BFS 目标安全、保留/提供模板数与可达反例长度分别记录。共有 5 个变体出现目标反例、4 个目标安全；缺失模板可能使证书无法证明而协议仍安全，写集元数据错误则阻断证书。拆分刷新删除一致性模板后仍证明目标安全。另有 6 个正确实例均已证明且安全。',
         'Certificate diagnostics for nine mutations in Experiment D. Certificate status, BFS target safety, retained/supplied templates and reachable trace lengths are reported separately. Five mutations are unsafe and four are safe. Missing templates can prevent proof without causing unsafety; incorrect write metadata blocks certification. All six correct instances are proved and safe.',
         'Certificate failure, metadata rejection and a reachable safety violation are different diagnostic outcomes.', ['certificate_generation_results.json'])


def bundle():
    # Contact sheet is a browsing aid; full-size exports are the manuscript assets.
    tiles=[]
    for f in FIGURES:
        im=Image.open(OUT/(f['name']+'.png')).convert('RGB')
        im.thumbnail((980,690))
        tile=Image.new('RGB',(1040,735),'white')
        tile.paste(im,((1040-im.width)//2,(700-im.height)//2+25))
        tiles.append(tile)
    sheet=Image.new('RGB',(2080,2940),'#EEEEEE')
    for i,tile in enumerate(tiles):sheet.paste(tile,((i%2)*1040,(i//2)*735))
    sheet.save(OUT/'overview.png')
    files=list(RESULTS.glob('*.csv'))+list(RESULTS.glob('*.json'))+list((ROOT/'traces').glob('C_*.json'))
    provenance={'random_seed':None,'deterministic':True,'font':'Comic Sans MS',
                'palette':PALETTE,'export_dpi':600,'svg_text':'editable','pdf_fonttype':42,
                'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                'figures':FIGURES,'qa':QA,'render_warnings':sorted(set(WARNINGS))}
    (OUT/'manifest.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
    text=['# 实验论文图\n',
          '共 8 张图，覆盖实验 A–D。采用白底、灰网格、鲜明红蓝绿橙紫青配色及 Comic Sans MS 字体；线型、点形、文字与颜色共同编码。图中文字采用英文，便于投稿；下列提供中英文图注。\n',
          'PDF 为论文插图首选；SVG 保留可编辑文字；PNG 为 600 DPI。画布宽度统一为 182.9 mm，按双栏宽度排版；如缩为单栏，需要重新设置画布与字号。没有添加误差棒或显著性标记，实验为确定性有限域检查，没有随机重复。\n',
          '建议优先选择图 03（群体缺口）、05（协调反例）、06（证明前提）；图 01、02、04、07、08 可用于实验补充材料。当前只交付图，不自动插入六页正文。\n',
          '复现命令：`python -m experiments.plot_reference_style`。依赖：Matplotlib、NumPy、Pillow；字体需要 Comic Sans MS。数据来自 `experiments/results` 和实验 C 的原始轨迹。各图对应的数值在 `source_data`，输入哈希与样式参数在 `manifest.json`。\n']
    for f in FIGURES:
        text.extend([f"## {f['name']}\n",f"中文图注：{f['caption_cn']}\n",f"English caption: {f['caption_en']}\n"])
    (OUT/'README.md').write_text('\n'.join(text),encoding='utf-8')


def main():
    OUT.mkdir(parents=True,exist_ok=True);DATA.mkdir(exist_ok=True);style()
    raw=read_csv('search_results.csv')
    search=[{**r,**json.loads(r['parameters'])} for r in raw]
    assert len(search)==251 and Counter(r['status'] for r in search)=={'COUNTEREXAMPLE':165,'SAFE_EXHAUSTIVE':86}
    minimal=json.loads((RESULTS/'minimal_context_results.json').read_text(encoding='utf-8'))
    generated=json.loads((RESULTS/'certificate_generation_results.json').read_text(encoding='utf-8'))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig01(search);fig02(search);fig03();fig04();fig05();fig06(minimal);fig07(minimal);fig08(generated)
        WARNINGS.extend(str(w.message) for w in caught)
    bundle()
    print(json.dumps({'figures':len(FIGURES),'warnings':len(set(WARNINGS)),'qa':QA},ensure_ascii=False))


if __name__=='__main__':
    main()
