"""
Quick CLI runner to compare evaluate() vs evaluate_repr() for blocks domain.
Mirrors what GroupC cell 10 and GroupE cells 20-22 do in the notebooks.
Run: conda run -n ASCAL_env python3 Pablo/tests/_run_comparison.py
"""
import sys, os, tempfile, shutil, random as _rng
from itertools import product as _prod

sys.path.insert(0, 'src')
os.environ['PYTHONWARNINGS'] = 'ignore'

from unified_planning.shortcuts import OneshotPlanner, SequentialSimulator, get_environment
from unified_planning.io import PDDLReader
import unified_planning
get_environment().credits_stream = None

from ascal.learner import Learner
from ascal.models import Literal, State, Action, Demonstration
from ascal.transitions import _build_literal_descriptors, _state_to_signature


# ── Demo generation ──────────────────────────────────────────────────────

def generate_demos(prob, max_neg_per_step=50, seed=0):
    rng = _rng.Random(seed)
    all_literals = list(prob.initial_values.keys())
    all_objects  = list(prob.all_objects)
    literal_desc = _build_literal_descriptors(all_literals)
    action_pars  = {a.name: tuple(p.name for p in a.parameters) for a in prob.actions}
    action_ground = {}
    for a in prob.actions:
        matching = [[o for o in all_objects
                     if o.type.is_subtype(a.parameters[i].type)]
                    for i in range(len(a.parameters))]
        action_ground[a] = [args for args in _prod(*matching)
                            if len(set(args)) == len(args)]
    with OneshotPlanner(problem_kind=prob.kind) as pl:
        result = pl.solve(prob)
    if result.status != unified_planning.engines.PlanGenerationResultStatus.SOLVED_SATISFICING:
        return [], []

    def _lift(sig, arg_names, m):
        return State(frozenset(
            Literal(n, tuple(m[a] for a in args), v)
            for n, args, v in sig
            if set(args).issubset(set(arg_names)) and len(set(args)) == len(args)))

    pos, neg = [], []
    with SequentialSimulator(problem=prob) as sim:
        pre = sim.get_initial_state()
        for ai in result.plan.actions:
            pre_sig = _state_to_signature(pre, literal_desc)
            step_negs = []
            for a, grds in action_ground.items():
                pars = action_pars[a.name]
                for args in grds:
                    if not sim.is_applicable(pre, a, args):
                        names = tuple(o.name for o in args)
                        step_negs.append(Demonstration(
                            pre_state=_lift(pre_sig, names,
                                            {names[i]: pars[i] for i in range(len(names))}),
                            action=Action(a.name, pars), post_state=None))
            if max_neg_per_step and len(step_negs) > max_neg_per_step:
                step_negs = rng.sample(step_negs, max_neg_per_step)
            neg.extend(step_negs)
            va = ai.action
            orig_args = tuple(p.object() for p in ai.actual_parameters)
            post = sim.apply(pre, ai)
            if post is None:
                break
            post_sig = _state_to_signature(post, literal_desc)
            names = tuple(o.name for o in orig_args)
            pars  = action_pars[va.name]
            m     = {names[i]: pars[i] for i in range(len(names))}
            pos.append(Demonstration(pre_state=_lift(pre_sig, names, m),
                                     action=Action(va.name, pars),
                                     post_state=_lift(post_sig, names, m)))
            pre = post
    return pos, neg


def train_interleaved(learner, pos_demos, neg_demos):
    if not pos_demos:
        for d in neg_demos:
            learner.update(d)
        return
    if not neg_demos:
        for d in pos_demos:
            learner.update(d)
        return
    sz  = len(neg_demos) / len(pos_demos)
    seq = []
    for i, p in enumerate(pos_demos):
        seq.extend(neg_demos[int(sz * i):int(sz * (i + 1))])
        seq.append(p)
    for d in seq:
        learner.update(d)


# ── Comparison printer ───────────────────────────────────────────────────

def compare(learner, pos, neg, label=''):
    f1_s,  f1_c,  p_s,  r_s,  p_c,  r_c         = learner.evaluate(pos, neg)
    f1_s2, f1_c2, p_s2, r_s2, p_c2, r_c2, status = learner.evaluate_repr(pos, neg)

    print(f'\n{"="*68}')
    print(f'  {label}')
    print(f'  Demos: {len(pos)} pos + {len(neg)} neg  |  Converged: {learner.converged}')
    print(f'{"="*68}')
    print(f'{"Method":<22} {"P_sound":>8} {"R_sound":>8} {"F1_sound":>9}'
          f'  {"P_comp":>8} {"R_comp":>8} {"F1_comp":>8}')
    print('-' * 80)
    print(f'{"evaluate()":22} {p_s:>8.4f} {r_s:>8.4f} {f1_s:>9.4f}'
          f'  {p_c:>8.4f} {r_c:>8.4f} {f1_c:>8.4f}')
    print(f'{"evaluate_repr()":22} {p_s2:>8.4f} {r_s2:>8.4f} {f1_s2:>9.4f}'
          f'  {p_c2:>8.4f} {r_c2:>8.4f} {f1_c2:>8.4f}')

    d_pc = abs(p_c - p_c2); d_rc = abs(r_c - r_c2); d_f1 = abs(f1_c - f1_c2)
    print()
    if d_pc < 1e-6 and d_rc < 1e-6:
        print('  ✓ Both methods agree on complete-model metrics.')
    else:
        print(f'  → Complete model differs: ΔP_c={d_pc:.4f}  ΔR_c={d_rc:.4f}  ΔF1={d_f1:.4f}')
        if r_c2 < r_c - 1e-6:
            print('    evaluate_repr() lower recall — expected before convergence')
        elif r_c2 > r_c + 1e-6:
            print('    evaluate_repr() higher recall — representative covers more positives')

    c1 = abs(p_s  - 1) < 1e-9; c2 = abs(r_c  - 1) < 1e-9
    c1r= abs(p_s2 - 1) < 1e-9; c2r= abs(r_c2 - 1) < 1e-9
    print()
    print(f'  C1 (P_sound=1): evaluate()={"✓" if c1 else "✗"}  evaluate_repr()={"✓" if c1r else "✗"}')
    print(f'  C2 (R_comp=1) : evaluate()={"✓" if c2 else "✗"}  evaluate_repr()={"✓" if c2r else "✗"}')
    print()
    print('  Per-action convergence (evaluate_repr):')
    for a, s in status.items():
        tag = '✓ converged' if s['converged'] else f'⏳ {s["n_hyps"]} hyps remaining'
        print(f'    {a}: {tag}')


# ── Load blocks domain ───────────────────────────────────────────────────

BLOCKS_DIR  = 'benchmarks/blocks'
BLOCKS_DOM  = os.path.join(BLOCKS_DIR, 'domain_extended.pddl')
BLOCKS_PRBS = os.path.join(BLOCKS_DIR, 'problems')
prob_files  = sorted(f for f in os.listdir(BLOCKS_PRBS) if f.endswith('.pddl'))

print(f'Loading {len(prob_files)} blocks problems...')
reader = PDDLReader()

seen_p, seen_n = set(), set()
all_pos, all_neg = [], []
for pf in prob_files:
    prob = reader.parse_problem(BLOCKS_DOM, os.path.join(BLOCKS_PRBS, pf))
    td = tempfile.mkdtemp(); cwd = os.getcwd(); os.chdir(td)
    try:
        p, n = generate_demos(prob)
    finally:
        os.chdir(cwd); shutil.rmtree(td, ignore_errors=True)
    for d in p:
        k = repr(d)
        if k not in seen_p: seen_p.add(k); all_pos.append(d)
    for d in n:
        k = repr(d)
        if k not in seen_n: seen_n.add(k); all_neg.append(d)

print(f'Collected: {len(all_pos)} pos + {len(all_neg)} neg unique demos')

# Train on ALL demos (in-sample)
b_prob = reader.parse_problem(BLOCKS_DOM, os.path.join(BLOCKS_PRBS, prob_files[0]))
b_fluents = b_prob.fluents; b_actions = b_prob.actions; b_static = b_prob.get_static_fluents()

learner_full = Learner(b_fluents, b_actions, b_static)
train_interleaved(learner_full, all_pos, all_neg)

compare(learner_full, all_pos, all_neg,
        'Blocks — evaluate() vs evaluate_repr() (all demos, in-sample)')

# Train on 80% / test on 20%
split_p = int(len(all_pos) * 0.8); split_n = int(len(all_neg) * 0.8)
t_pos, te_pos = all_pos[:split_p], all_pos[split_p:]
t_neg, te_neg = all_neg[:split_n], all_neg[split_n:]

learner_split = Learner(b_fluents, b_actions, b_static)
train_interleaved(learner_split, t_pos, t_neg)

compare(learner_split, te_pos, te_neg,
        'Blocks — evaluate() vs evaluate_repr() (80/20 split, held-out test)')

print('\nDone.')
