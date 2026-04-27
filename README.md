# ASCAL — Anytime Sound and Complete Action Learning

[![PyPI version](https://img.shields.io/pypi/v/ascal.svg)](https://pypi.org/project/ascal/)
[![Python versions](https://img.shields.io/pypi/pyversions/ascal.svg)](https://pypi.org/project/ascal/)
[![License: GPL v3+](https://img.shields.io/badge/License-GPLv3+-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Paper: KR 2024](https://img.shields.io/badge/paper-KR%202024-brightgreen.svg)](https://proceedings.kr.org/2024/75/kr2024-0075-aineto-et-al.pdf)

ASCAL is an online algorithm for Action Model Learning (AML) with full observability.
It leverages Version Space Learning to maintain a compact representation of all action models consistent with a set of positive and negative demonstrations.
The output can be used to build action models guaranteed to be **sound** or **complete** with respect to the true underlying model.

Paper: <https://proceedings.kr.org/2024/75/kr2024-0075-aineto-et-al.pdf>

---

## What is ASCAL?

Given a sequence of fully-observable demonstrations `(pre_state, action, post_state)`, ASCAL maintains per-action **version-space boundaries**:

- `L_pre` / `U_pre` — lower and upper bounds on the precondition hypothesis space
- `L_eff` / `U_eff` — lower and upper bounds on the effect hypothesis space

Eight operators (`RUP`, `RLP`, `ULP`, `UUP` for preconditions; `RLE`, `RUE`, `ULE`, `UUE` for effects) keep these bounds consistent with every new demonstration.

From the learned boundaries you can extract:

| Model | Method | Guarantee |
|---|---|---|
| Sound model | `learner.sound_model()` | Never permits a transition the true model forbids |
| Complete model | `learner.complete_model()` | U-border with non-contradictory effects. Splits ambiguous polarities into maximal completions |
| Consistent complete model | `learner.complete_model_single()` | U-border with non-contradictory effects. Does not split hypothesis |
| Upper-border model | `learner.raw_upper_bound()` | Compact U-boundary (one operator per precondition hypothesis). It is not complete but it is fast for planning. Can be used instead of blind search as a first approach |
| Full version-space model | `learner.version_space()` | All consistent hypotheses (can be large) |

---

## Installation

Requires Python 3.10+.

```bash
# From PyPI (recommended for users)
pip install ascal
```

```bash
# Notebook and evaluation workflow (adds numpy, matplotlib, jupyter)
pip install "ascal[notebook]"
```

```bash
# Optional planner backend: Fast Downward via Unified Planning plugin
pip install "ascal[planner]"
```

For contributors working from a clone:

```bash
# Editable install with development tools (pytest, build, twine, ruff)
pip install -e ".[dev]"
```

```bash
# Exact reproducibility environment for paper/benchmark reruns
pip install -r requirements-repro-lock.txt
pip install -e .
```

See `documentation/dependency-classification.md` for the full classification of dependencies and `documentation/dependency-validation-checklist.md` for post-install smoke tests.

---

## Quick start

```python
from ascal import (
    Learner,
    generate_lifted_demonstrations_from_problem,
)

# --- Build demonstrations from a Unified Planning problem ---
# pos_demos, neg_demos = generate_lifted_demonstrations_from_problem(problem, plan, planner_name="pyperplan")

# --- Initialise learner from domain info ---
learner = Learner(all_fluents, all_actions, static_fluents)

# --- Feed demonstrations one at a time ---
for demo in demonstrations:
    ok = learner.update(demo)
    if not ok:
        print(f"Version space collapsed for {demo.action.name}")

# --- Or feed a batch ---
n_collapses = learner.update_batch(remaining_demos)

# --- Inspect convergence ---
print(learner.converged)           # True when L == U for all actions
print(learner.version_space_size)  # Per-action statistics dict
print(learner.demo_count)          # Total demonstrations processed

# --- Extract learned models as UP Problem objects ---
sound_problem  = learner.sound_model()        # Sound (L-boundary)
border_problem = learner.raw_upper_bound()    # Compact U-boundary
complete_model = learner.complete_model()     # Consistent split completions
vs_problem     = learner.version_space()        # Full version space (may be large)

# --- Evaluate against labelled test data ---
f1_s, f1_c, p_s, r_s, p_c, r_c = learner.evaluate(test_pos, test_neg)

# Variant: representative hypothesis for complete model
f1_s, f1_c, p_s, r_s, p_c, r_c, status = learner.evaluate_repr(test_pos, test_neg)

# Variant: only fully-converged actions
f1_s, f1_c, p_s, r_s, p_c, r_c, status = learner.evaluate_gated(test_pos, test_neg)
```

---

## Package structure

```
src/ascal/
    __init__.py     — Public API (Learner + all exported symbols)
    models.py       — Data classes: Literal, State, Action, Demonstration
    transitions.py  — Unified Planning bridge: plan execution, grounding,
                      lifting, demonstration generation
    algorithm.py    — ASCAL operators (RUP, RLP, ULP, UUP, RLE, RUE, ULE, UUE),
                      initialisation, iteration, and model generation
    evaluation.py   — F1, precision, recall; version-space size computation;
                      three evaluation strategies (detailed, representative, gated)
    learner.py      — Learner: stateful high-level wrapper
    logger.py       — Logging utilities (get_logger)
```

### Key public symbols

```python
from ascal import (
    # Core data classes
    Literal, State, Action, Demonstration,

    # High-level learner (recommended entry point)
    Learner,

    # Demonstration generation from Unified Planning
    generate_lifted_demonstrations_from_problem,
    generate_transitions_from_problem,
    lift_demonstrations,

    # Low-level ASCAL algorithm
    ASCAL_initialization,
    run_ASCAL_iteration,
    run_ASCAL,

    # Version-space operators
    RUP, RLP, ULP, UUP,   # preconditions
    RLE, RUE, ULE, UUE,   # effects

    # Model generation (used internally by Learner)
    generate_sound_action_model,
    generate_complete_border,
    generate_complete_border_consistent,
    generate_complete_border_consistent_split,

    # Evaluation
    evaluate_detailed,
    evaluate_representative,
    evaluate_convergence_gated,
    compute_version_space_size,
)
```

---

## Repository structure

```
benchmarks/
    blocks/             — Blocks-world domain
    driverlog/          — Driverlog domain
    miconic/            — Miconic domain
    satellite/          — Satellite domain
    mockup/             — Small synthetic domain for quick sanity checks
    debug_pq/           — Debug / edge-case domain
    Each subdomain contains:
        domain_original.pddl   — Original IPC domain
        domain_extended.pddl   — Extended variant used in experiments
        problems/              — Problem instances (.pddl)

notebooks/
    ascal_validation.ipynb          — Mockup domain: ASCAL validation trace,
                                      L/U checks, evaluate_detailed, version-space size
    MultiProblemEvaluation.ipynb    — Multi-problem pipeline, 80/20 split,
                                      learning curves, convergence, ground-truth checks
    Evaluation Learner.ipynb        — Learner pipeline: update, snapshots, F1 metrics

tests/
    GroupA_StructuralInvariants.ipynb  — Structural invariants of version-space bounds
    GroupB_OperatorVerification.ipynb  — Operator correctness (RUP/RLP/…)
    GroupC_TheoreticalGuarantees.ipynb — Theoretical soundness/completeness guarantees
    GroupD_Monotonicity.ipynb          — Monotonicity properties
    GroupE_GroundTruthComparison.ipynb — Comparison against known ground truth
    _run_comparison.py                 — Script: compare evaluate vs evaluate_repr
```

---

## Running tests and notebooks

```bash
# Run the comparison script from the repo root
python tests/_run_comparison.py

# Launch notebooks
jupyter lab
```

Ensure the package is installed (`pip install -e .`) so that `import ascal` resolves correctly.

---

## Citation

If you use ASCAL in academic work, please cite the KR 2024 paper. Structured metadata is provided in [`CITATION.cff`](CITATION.cff) and GitHub will render a "Cite this repository" button from it.

```bibtex
@article{aineto2024ascal,
  title     = {Action Model Learning with Guarantees},
  author    = {Aineto, Diego and Scala, Enrico},
  year      = {2024},
  url       = {https://proceedings.kr.org/2024/75/kr2024-0075-aineto-et-al.pdf}
}
```

---

## License

ASCAL is free software: you can redistribute it and/or modify it under the terms of the
**GNU General Public License v3.0 or later** (GPL-3.0-or-later) as published by the Free Software Foundation.
See `LICENSE` for the full license text.

Copyright (c) 2026 Diego Aineto, Enrico Scala, Pablo Copete.

### Third-party planner licensing

This project integrates with planners through the [Unified Planning Framework](https://github.com/aiplan4eu/unified-planning) (Apache-2.0).
Some optional planner backends — for example Fast Downward via `up-fast-downward` — are distributed under separate licenses including GPL-family licenses.
Those components are **not** part of ASCAL's own license and must be installed, used, and redistributed according to their respective terms.
