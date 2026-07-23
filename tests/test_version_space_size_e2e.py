"""
End-to-end version-space size checks on the bundled benchmark domains.

Feeds a real planner-generated demonstration stream (plan walk + sampled
negatives) through ``Learner`` and asserts, after every single demo:

  * ``total <= n_pre * n_eff``   (old proxy is an upper bound on the new exact
    count — equality only without gap absorption);
  * ``total`` monotonically non-increasing per action (the version space only
    shrinks; checked while ``total_exact`` holds);
  * at the end, for every action whose space is small enough to enumerate,
    ``total`` equals exactly what the materializers build:
    ``Σ_hp |generate_version_space_effects(L_eff−hp, U_eff−hp)|`` over the full
    precondition interval (he = ∅ included).

Requires a UP-visible planner; the test skips cleanly if planning fails.
"""

from pathlib import Path

import pytest

from ascal import Learner
from ascal.algorithm import precondition_interval_hypotheses
from ascal.models import generate_version_space_effects
from ascal.transitions import generate_lifted_demonstrations_from_problem

BENCH_ROOT = Path(__file__).resolve().parent.parent / "benchmarks"
ENUM_CAP = 50_000


def _load_problem(domain_dir):
    from unified_planning.io import PDDLReader

    reader = PDDLReader()
    return reader.parse_problem(
        str(BENCH_ROOT / domain_dir / "domain_original.pddl"),
        str(BENCH_ROOT / domain_dir / "problems" / "problem-00.pddl"),
    )


@pytest.mark.parametrize("domain_dir", ["blocks", "driverlog"])
def test_e2e_totals_bounded_monotone_and_enumerable(domain_dir):
    if not (BENCH_ROOT / domain_dir).is_dir():
        pytest.skip(f"benchmarks/{domain_dir} not present")
    problem = _load_problem(domain_dir)
    try:
        positives, negatives = generate_lifted_demonstrations_from_problem(
            problem, max_neg_per_step=5, max_check_per_action=30, seed=0
        )
    except Exception as exc:  # no planner installed / engine error
        pytest.skip(f"demo generation unavailable: {exc}")
    if not positives:
        pytest.skip("problem not solved — no demonstrations")

    learner = Learner(list(problem.fluents), list(problem.actions), [])

    prev_total: dict[str, int] = {}
    for demo in positives + negatives:
        learner.update(demo)
        rep = learner.version_space_size
        for name, r in rep.items():
            if r.get("collapsed"):
                continue
            assert r["total"] <= r["n_pre"] * r["n_eff"], name
            if r.get("total_exact"):
                if name in prev_total:
                    assert r["total"] <= prev_total[name], (
                        f"{name}: version space grew {prev_total[name]} -> "
                        f"{r['total']}"
                    )
                prev_total[name] = r["total"]
            else:
                prev_total.pop(name, None)   # estimate: stop strict tracking

    # final cross-check against the materializers' enumeration
    rep = learner.version_space_size
    checked = 0
    inflation = {}
    for action in problem.actions:
        r = rep[action.name]
        if r.get("collapsed") or not r.get("total_exact"):
            continue
        if r["total"] > ENUM_CAP:
            continue
        lp = next(iter(learner.L_pre[action.name]))
        le = next(iter(learner.L_eff[action.name]))
        ue = next(iter(learner.U_eff[action.name]))
        generated = sum(
            len(generate_version_space_effects(le - hp, ue - hp))
            for hp in precondition_interval_hypotheses(
                {lp}, learner.U_pre[action.name]
            )
        )
        assert generated == r["total"], (
            f"{action.name}: materializer={generated} vs total={r['total']}"
        )
        checked += 1
        inflation[action.name] = (r["n_pre"] * r["n_eff"], r["total"])

    assert checked >= 1, "no action small enough to enumerate — extend the stream"
    print(
        f"\n[{domain_dir}] pos={len(positives)} neg={len(negatives)} "
        f"enumeration-verified={checked}/{len(rep)} actions; "
        "old_proxy vs exact total: "
        + ", ".join(f"{k}: {p}->{t}" for k, (p, t) in sorted(inflation.items()))
    )
