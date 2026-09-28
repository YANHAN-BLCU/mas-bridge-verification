import csv, json
from pathlib import Path
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent; DATA=ROOT/'data'; FIG=ROOT/'figures'; FIG.mkdir(exist_ok=True)
rows=list(csv.DictReader((DATA/'experiments.csv').open(encoding='utf8')))
plt.rcParams.update({'font.family':'DejaVu Sans','figure.dpi':160,'axes.spines.top':False,'axes.spines.right':False})
colors={'local':'#D55E00','check_then_enter':'#CC79A7','token':'#0072B2','pairwise':'#E69F00','check_then_commit':'#56B4E9','quota':'#009E73'}
labels={'local':'local','check_then_enter':'check-then-enter','token':'atomic token','pairwise':'pairwise','check_then_commit':'cached commit','quota':'atomic quota'}

def plot_model(model, ylabel, file, value):
    rs=[r for r in rows if r['model']==model]
    plt.figure(figsize=(6.8,4.2))
    for prot in sorted(set(r['protocol'] for r in rs)):
        z=[r for r in rs if r['protocol']==prot]
        plt.plot([int(r['n']) for r in z],[value(r) for r in z],marker='o',label=labels[prot],color=colors[prot])
    plt.xlabel('number of agents'); plt.ylabel(ylabel); plt.grid(alpha=.2); plt.legend(frameon=False,ncol=2); plt.tight_layout(); plt.savefig(FIG/file); plt.close()

plot_model('bridge','reachable states','bridge_reachable_states.png',lambda r:int(r['discovered_states']))
plot_model('bridge','runtime (ms)','bridge_runtime_ms.png',lambda r:float(r['runtime_ms']))
plot_model('quota','reachable states','quota_reachable_states.png',lambda r:int(r['discovered_states']))
plt.figure(figsize=(6.8,4.2))
for model in ('bridge','quota'):
    rs=[r for r in rows if r['model']==model]
    for prot in sorted(set(r['protocol'] for r in rs)):
        z=[r for r in rs if r['protocol']==prot]
        xs=[int(r['n']) for r in z]; ys=[0 if r['safe']=='True' else 1 for r in z]
        plt.plot(xs,ys,marker='o',label=f'{model}:{labels[prot]}',color=colors[prot],linestyle='-' if model=='bridge' else '--')
plt.yticks([0,1],['safe','counterexample']); plt.xlabel('number of agents'); plt.ylabel('result'); plt.grid(alpha=.2); plt.legend(frameon=False,ncol=2,fontsize=8); plt.tight_layout(); plt.savefig(FIG/'safety_by_protocol.png'); plt.close()

def fmt(v): return 'safe' if v=='True' else 'counterexample'
lines=[]
lines += ['# 从安全反例到桥接不变量：多智能体系统的有限状态验证','','## 1. 项目说明','',
          '本项目研究有限状态多智能体系统中，局部安全和两两安全何时不足以保证高阶安全，以及简单桥接协议能否恢复全局安全。实验不使用大语言模型训练；所有结果来自确定性的显式状态 BFS 和有限域不变量检查。','',
          '> 证据范围：本报告的结论只对代码中明确的有限状态模型、动作和参数成立。搜索未发现反例时，报告使用“该有限模型中安全”，不外推到任意规模系统。','',
          '## 2. 模型与安全性质','',
          '### 2.1 共享窄桥','',
          '每个 Agent 的位置状态为 `away=0`、`wait=1`、`on=2`。桥容量为 1，全局安全谓词为：','',
          '$$\\Phi_{bridge}=\\sum_i [q_i=on]\\le 1.$$','',
          '比较 local、check-then-enter 和 atomic token 三种协议。前两者允许直接进入或先缓存桥状态后进入；atomic token 通过唯一 owner 串行化授权。','',
          '### 2.2 群体配额','',
          '每个 Agent 的消耗为 $p_i$，局部上限为 $r=1$，总容量为 $B=2$。全局安全谓词为：','',
          '$$\\Phi_{quota}=\\sum_i p_i\\le B.$$','',
          '比较 local、pairwise、check-then-commit 和 atomic quota。pairwise 只检查任意两者的总量；atomic quota 先原子授予配额，再允许消耗。','',
          '## 3. 实验设置','',
          '- Agent 数量：$n=2,3,\\ldots,8$。','- 每个配置从固定初始状态开始。','- 使用 BFS 搜索最短安全反例。','- 状态上限为 2,000,000；本次所有配置均未触发上限。','- 记录可达状态数、转移数、运行时间、是否安全和最短反例步数。','- 对 token/quota 协议在 $n=2,3,4,5$ 上枚举完整有限候选域，检查初始化、保持性和安全蕴含。','',
          '## 4. 实验结果','',
          '### 4.1 反例搜索','',
          '| 模型 | 协议 | n=2 | n=3–8 | 最短反例 |','|---|---|---|---|---|']
for model in ('bridge','quota'):
    for prot in sorted(set(r['protocol'] for r in rows if r['model']==model)):
        z=[r for r in rows if r['model']==model and r['protocol']==prot]
        n2=fmt(next(r for r in z if r['n']=='2')['safe']); n3=fmt(next(r for r in z if r['n']=='3')['safe']); n8=fmt(next(r for r in z if r['n']=='8')['safe'])
        lengths=sorted(set(r['counterexample_steps'] for r in z if r['counterexample_steps']))
        lines.append(f'| {model} | {labels[prot]} | {n2} | {n3} … {n8} | {", ".join(lengths) or "—"} |')
lines += ['', '窄桥结果中，local 在所有 $n$ 上出现 4 步反例，check-then-enter 出现 6 步反例；atomic token 在 $n=2$ 至 $8$ 的搜索中均未发现违规状态。群体配额中，local 和 pairwise 从 $n=3$ 开始出现 3 步反例；cached commit 从 $n=3$ 开始出现 6 步竞态；atomic quota 在所有测试规模中均未发现反例。','',
          '![桥模型可达状态数](figures/bridge_reachable_states.png)','', '![桥模型运行时间](figures/bridge_runtime_ms.png)','', '![配额模型可达状态数](figures/quota_reachable_states.png)','', '![安全结果](figures/safety_by_protocol.png)','',
          '### 4.2 最短反例','', '窄桥 local 的最短轨迹为：','', '```text','initial → request(0) → enter(0) → request(1) → enter(1)','```','', '最终状态为 `(on_0, on_1)`，违反桥容量为 1 的安全性质。','', 'cached commit 的反例包含两个 Agent 先后读取“有剩余容量”，再使用缓存完成提交，说明检查与提交分离会使局部检查失效。','',
          '### 4.3 归纳证书','', '8 组完整有限域检查全部通过：', '', '| 模型 | n 范围 | base | step | invariant ⇒ safety |', '|---|---:|---:|---:|---:|']
cert=json.loads((DATA/'certificates.json').read_text(encoding='utf8'))
for model in ('bridge','quota'):
    z=[c for c in cert if c['model']==model]
    lines.append(f'| {model} | 2–5 | {all(c["base"] for c in z)} | {all(c["step"] for c in z)} | {all(c["implies_safe"] for c in z)} |')
lines += ['', '这意味着在本次枚举的完整有限候选域中，token 和 quota 桥接不变量分别满足初始化、所有动作保持性以及对全局安全的蕴含。它是有限模型内的形式证书，不是任意规模系统的定理。','',
          '## 5. 结论','',
          '1. 单体安全和两两安全不能覆盖高阶总量约束：当 $n=3$、每个 Agent 最多消耗 1、总容量为 2 时，任意两者总量不超过 2，但三者合计为 3。','2. 非原子检查和提交会产生动态竞态；最短反例可以由 BFS 自动给出。','3. 唯一令牌和原子配额协议在给定有限模型中恢复了全局安全，并通过完整候选域的不变量检查获得证书。','4. 桥接协议有状态和动作开销；运行时间与状态空间随 Agent 数量增长，报告中的结果只覆盖 $n\\le8$。','',
          '## 6. 复现','', '```powershell','cd mas-bridge-verification','python run_experiments.py','python make_report.py','```','',
          '原始结果见 `data/experiments.csv`、`data/counterexamples.json` 和 `data/certificates.json`；运行环境与命令见 `data/provenance.json`。','',
          '## 7. 限制','', '- 模型采用有限整数状态，不代表真实 LLM Agent 的行为。','- 调度是非概率的全状态枚举，没有测量真实网络延迟。','- 协议安全依赖动作定义和 owner/quota 管理器可信。','- 尚未研究活性、饥饿、故障恢复和恶意协议实现。']
(ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print('report written',ROOT/'REPORT.md')
