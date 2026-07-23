"""
Tests for the exact version-space size computation (evaluation.py, 2026-07-24).

Covers, against brute-force enumeration:
  * ``n_pre`` — exact inclusion-exclusion over overlapping ``U_pre`` splits
    (the naive per-child sum double-counts hypotheses above two children);
  * ``total`` — exact count of semantically distinct (hp, he) models, i.e.
    effects counted in the hp-adjusted interval [L_eff−hp, U_eff−hp] rather
    than the global proxy 2^|U_eff−L_eff| (which double-counts no-op effect
    variants for literals in hp ∩ gap and is only an upper bound);
  * edge cases: empty lower bound, empty-u shortcut, collapsed actions,
    convergence, and the inexact fallback for > ~20 frontier elements.

Brute force stays feasible by keeping |l| ≤ 10 everywhere.
"""

import itertools
import random

from ascal.evaluation import (
    _count_pre_interval_single_lower,
    compute_version_space_size,
    compute_version_space_upper_bound,
)
from ascal.models import (
    Action,
    Demonstration,
    Literal,
    State,
    generate_version_space_effects,
)
from ascal.algorithm import precondition_interval_hypotheses


def _brute_force(u_hyps, l_hyp, eff_gap):
    """(n_pre, n_models) by enumerating every h with some u ⊆ h ⊆ l."""
    n_pre = 0
    n_models = 0
    elems = sorted(l_hyp, key=repr)
    for r in range(len(elems) + 1):
        for comb in itertools.combinations(elems, r):
            h = frozenset(comb)
            if any(u <= h for u in u_hyps):
                n_pre += 1
                n_models += 1 << len(eff_gap - h)
    return n_pre, n_models


class _NamedAction:
    def __init__(self, name):
        self.name = name


def _report_for(u_pre, l_pre, le, ue, name="act"):
    return compute_version_space_size(
        [_NamedAction(name)],
        {name: u_pre},
        {name: {l_pre}},
        {name: {le}},
        {name: {ue}},
    )[name]


# ---------------------------------------------------------------------------
# _count_pre_interval_single_lower
# ---------------------------------------------------------------------------

def test_ie_matches_bruteforce_random():
    rng = random.Random(7)
    for _ in range(300):
        m = rng.randint(0, 9)
        universe = list(range(m + 3))          # literals outside l too
        l_hyp = frozenset(range(m))
        u_hyps = {
            frozenset(rng.sample(universe, rng.randint(0, len(universe))))
            for _ in range(rng.randint(1, 6))
        }
        # gap mixes literals inside and outside l
        eff_gap = frozenset(rng.sample(universe, rng.randint(0, len(universe))))

        exp_pre, exp_mod = _brute_force(u_hyps, l_hyp, eff_gap)
        n_pre, n_models, exact = _count_pre_interval_single_lower(
            u_hyps, l_hyp, eff_gap=eff_gap
        )
        assert exact
        assert n_pre == exp_pre
        assert n_models == exp_mod
        # the old proxy is an upper bound on the exact count
        assert n_models <= n_pre * (1 << len(eff_gap))


def test_split_overlap_not_double_counted():
    """Split children {a}, {b}: hypotheses containing both lie in both up-sets."""
    l_hyp = frozenset("abcd")
    splits = {frozenset("a"), frozenset("b")}
    exp_pre, exp_mod = _brute_force(splits, l_hyp, frozenset("bx"))

    n_pre, n_models, exact = _count_pre_interval_single_lower(
        splits, l_hyp, eff_gap=frozenset("bx")
    )
    assert exact
    assert n_pre == exp_pre == 12
    naive = sum(1 << (len(l_hyp) - len(u)) for u in splits)
    assert naive == 16 > n_pre
    assert n_models == exp_mod


def test_gap_empty_reduces_models_to_npre():
    rng = random.Random(3)
    for _ in range(50):
        m = rng.randint(0, 8)
        l_hyp = frozenset(range(m))
        u_hyps = {
            frozenset(rng.sample(range(m), rng.randint(0, m)))
            for _ in range(rng.randint(1, 4))
        }
        n_pre, n_models, exact = _count_pre_interval_single_lower(u_hyps, l_hyp)
        assert exact
        assert n_models == n_pre


def test_empty_u_shortcut_closed_form():
    """U = {∅} takes the full-down-set shortcut; check its closed form."""
    l_hyp = frozenset("abc")
    eff_gap = frozenset("bcxy")                # b, c overlap l; x, y outside
    exp_pre, exp_mod = _brute_force({frozenset()}, l_hyp, eff_gap)
    n_pre, n_models, exact = _count_pre_interval_single_lower(
        {frozenset()}, l_hyp, eff_gap=eff_gap
    )
    assert exact
    assert (n_pre, n_models) == (exp_pre, exp_mod) == (8, 4 * 2 * 3 * 3)


def test_empty_lower_bound_edge():
    n_pre, n_models, exact = _count_pre_interval_single_lower(
        {frozenset()}, frozenset(), eff_gap=frozenset("xy")
    )
    assert (n_pre, n_models, exact) == (1, 4, True)
    n_pre, n_models, exact = _count_pre_interval_single_lower(
        {frozenset("a")}, frozenset(), eff_gap=frozenset("xy")
    )
    assert (n_pre, n_models, exact) == (0, 0, True)


def test_fallback_is_flagged_and_bounded():
    """>20 incomparable frontier elements exceed ie_term_limit → estimate."""
    m = 21
    l_hyp = frozenset(range(m))
    u_hyps = {frozenset({i}) for i in range(m)}
    eff_gap = frozenset(range(3)) | frozenset({"x"})

    n_pre, n_models, exact = _count_pre_interval_single_lower(
        u_hyps, l_hyp, eff_gap=eff_gap
    )
    assert not exact
    # estimates must lie between the max single up-set and the clipped sum
    singles_pre = [1 << (m - 1)] * m
    assert max(singles_pre) <= n_pre <= min(sum(singles_pre), 1 << m)
    assert 0 < n_models <= n_pre * (1 << len(eff_gap))
    # exact answer here is 2^21 - 1 hypotheses (all but the empty set)
    assert abs(n_pre - ((1 << m) - 1)) < (1 << m)


# ---------------------------------------------------------------------------
# compute_version_space_size (report level, with Literals)
# ---------------------------------------------------------------------------

def _lit(name, value=True):
    return Literal(name, (), value)


def test_static_frame_literal_total_is_exact():
    """A static literal s (candidate precondition AND candidate no-op effect)
    inflated the old total: n_pre * n_eff = 8, but only 6 distinct models."""
    l_pre = frozenset({_lit("p"), _lit("s")})
    u_pre = {frozenset()}
    le = frozenset({_lit("q")})
    ue = frozenset({_lit("q"), _lit("s")})

    rep = _report_for(u_pre, l_pre, le, ue)
    assert rep["n_pre"] == 4
    assert rep["n_eff"] == 2                    # proxy unchanged
    assert rep["total"] == 6                    # was 8 with the proxy product
    assert rep["total_exact"] and rep["n_pre_exact"]

    # must equal what the materializers actually enumerate
    generated = 0
    for hp in precondition_interval_hypotheses({l_pre}, u_pre):
        generated += len(generate_version_space_effects(le - hp, ue - hp))
    assert generated == rep["total"]

    # the retained upper-bound variant reports the pre-0.2.0 proxy
    ub = compute_version_space_upper_bound(
        [_NamedAction("act")], {"act": u_pre}, {"act": {l_pre}},
        {"act": {le}}, {"act": {ue}},
    )["act"]
    assert ub["total"] == 8 == ub["n_pre"] * ub["n_eff"]
    assert "total_exact" not in ub


def test_upper_bound_variant_consistency():
    """compute_version_space_upper_bound: total == n_pre * n_eff >= exact
    total, every other key identical to the exact report."""
    rng = random.Random(42)
    names = ["a", "b", "c", "d", "e"]
    for _ in range(60):
        l_pre = frozenset(
            _lit(n) for n in rng.sample(names, rng.randint(0, len(names)))
        )
        u_pre = {
            frozenset(rng.sample(sorted(l_pre, key=repr), rng.randint(0, len(l_pre))))
            for _ in range(rng.randint(1, 3))
        }
        ue = frozenset(
            _lit(n) for n in rng.sample(names, rng.randint(0, len(names)))
        )
        le = frozenset(rng.sample(sorted(ue, key=repr), rng.randint(0, len(ue))))

        exact = _report_for(u_pre, l_pre, le, ue)
        ub = compute_version_space_upper_bound(
            [_NamedAction("act")], {"act": u_pre}, {"act": {l_pre}},
            {"act": {le}}, {"act": {ue}},
        )["act"]

        assert ub["total"] == ub["n_pre"] * ub["n_eff"] >= exact["total"]
        assert "total_exact" not in ub
        for key in exact:
            if key not in ("total", "total_exact"):
                assert ub[key] == exact[key], key

    # collapsed actions report zero in both variants
    ub = compute_version_space_upper_bound(
        [_NamedAction("act")], {"act": set()}, {"act": {frozenset({_lit("p")})}},
        {"act": {frozenset()}}, {"act": {frozenset()}},
    )["act"]
    assert ub["collapsed"] and ub["total"] == 0 and "total_exact" not in ub


def test_total_matches_semantic_classes():
    """total == number of semantically distinct transition functions among all
    raw (hp, he) pairs, hp in the pre interval x he in the *unadjusted*
    [L_eff, U_eff] interval (consistent regime: l, ue subsets of real states)."""
    a, b, c = _lit("a"), _lit("b"), _lit("c")
    d_neg = _lit("d", False)
    atoms = ["a", "b", "c", "d"]

    l_pre = frozenset({a, b})
    u_pre = {frozenset({a}), frozenset({b})}    # overlapping split children
    le = frozenset({c})
    ue = frozenset({c, b, d_neg})               # gap {b, ¬d}: b overlaps l

    rep = _report_for(u_pre, l_pre, le, ue)
    assert rep["total_exact"]

    def consistent_states():
        for vals in itertools.product([True, False], repeat=len(atoms)):
            yield frozenset(_lit(n, v) for n, v in zip(atoms, vals))

    def fingerprint(hp, he):
        rows = []
        for st in consistent_states():
            if hp <= st:
                succ = frozenset(x for x in st if x.negated() not in he) | he
                rows.append(succ)
            else:
                rows.append(None)
        return tuple(rows)

    hyps = precondition_interval_hypotheses({l_pre}, u_pre)
    gap = sorted(ue - le, key=repr)
    fingerprints = {
        fingerprint(hp, le | frozenset(ext))
        for hp in hyps
        for r in range(len(gap) + 1)
        for ext in itertools.combinations(gap, r)
    }
    assert rep["total"] == len(fingerprints) == 8


def test_converged_action_total_is_one():
    l_pre = frozenset({_lit("p")})
    le = frozenset({_lit("q")})
    rep = _report_for({l_pre}, l_pre, le, le)
    assert rep["converged"]
    assert rep["n_pre"] == rep["n_eff"] == rep["total"] == 1


def test_collapsed_action_reports_zero():
    rep = _report_for(set(), frozenset({_lit("p")}),
                      frozenset({_lit("q")}), frozenset({_lit("q")}))
    assert rep["collapsed"]
    assert rep["total"] == 0


# ---------------------------------------------------------------------------
# Property tests (randomized, brute-forced)
# ---------------------------------------------------------------------------

_ATOMS = ["a", "b", "c", "d"]


def _consistent_states():
    for vals in itertools.product([True, False], repeat=len(_ATOMS)):
        yield frozenset(_lit(n, v) for n, v in zip(_ATOMS, vals))


def _fingerprint(hp, he):
    """Transition function of model (hp, he) over all consistent states."""
    rows = []
    for st in _consistent_states():
        if hp <= st:
            rows.append(frozenset(x for x in st if x.negated() not in he) | he)
        else:
            rows.append(None)
    return tuple(rows)


def _random_consistent_literals(rng, atoms):
    """Random consistent literal set: at most one polarity per atom."""
    out = set()
    for n in atoms:
        c = rng.randint(0, 2)
        if c:
            out.add(_lit(n, c == 1))
    return frozenset(out)


def test_semantic_bijection_randomized():
    """total == #semantically distinct transition functions, over random
    consistent-regime configurations (the regime after >=1 positive demo)."""
    rng = random.Random(24)
    nontrivial = 0
    for _ in range(120):
        l_pre = _random_consistent_literals(rng, _ATOMS)
        u_pre = {
            frozenset(rng.sample(sorted(l_pre, key=repr), rng.randint(0, len(l_pre))))
            for _ in range(rng.randint(1, 3))
        }
        ue = _random_consistent_literals(rng, _ATOMS)
        le = frozenset(rng.sample(sorted(ue, key=repr), rng.randint(0, len(ue))))

        rep = _report_for(u_pre, l_pre, le, ue)
        assert rep["total_exact"]

        gap = sorted(ue - le, key=repr)
        hyps = precondition_interval_hypotheses({l_pre}, u_pre)
        fingerprints = {
            _fingerprint(hp, le | frozenset(ext))
            for hp in hyps
            for r in range(len(gap) + 1)
            for ext in itertools.combinations(gap, r)
        }
        assert rep["total"] == len(fingerprints)
        if rep["total"] < rep["n_pre"] * rep["n_eff"]:
            nontrivial += 1
    # make sure the sample actually exercised the overcount regime
    assert nontrivial >= 20


def test_equality_with_old_proxy_iff_no_gap_absorption():
    """total == n_pre * n_eff exactly when no consistent hp intersects the
    effect gap — the condition under which the old product was already right."""
    rng = random.Random(11)
    for _ in range(200):
        m = rng.randint(0, 7)
        l_hyp = frozenset(range(m))
        u_hyps = {
            frozenset(rng.sample(range(m), rng.randint(0, m)))
            for _ in range(rng.randint(1, 4))
        }
        eff_gap = frozenset(rng.sample(range(m + 3), rng.randint(0, m + 3)))
        n_pre, n_models, exact = _count_pre_interval_single_lower(
            u_hyps, l_hyp, eff_gap=eff_gap
        )
        assert exact
        assert n_models <= n_pre * (1 << len(eff_gap))
        overlap_free = all(
            not (frozenset(h) & eff_gap)
            for r in range(m + 1)
            for h in itertools.combinations(range(m), r)
            if any(u <= frozenset(h) for u in u_hyps)
        )
        assert (n_models == n_pre * (1 << len(eff_gap))) == overlap_free


def test_operator_stream_monotone_exact_and_sound():
    """Drive the real update operators (run_ASCAL_iteration) with demos from a
    synthetic ground-truth model; after every demo the counts must equal brute
    force, never increase, and the ground truth must remain in the space."""
    from ascal.algorithm import run_ASCAL_iteration

    for seed in range(5):
        rng = random.Random(seed)
        universe = frozenset(
            _lit(n, v) for n in _ATOMS for v in (True, False)
        )
        hp_true = frozenset({_lit("a"), _lit("b")})
        he_true = frozenset({_lit("c"), _lit("d", False)})

        L_pre = {"act": {universe}}
        U_pre = {"act": {frozenset()}}
        L_eff = {"act": {frozenset()}}
        U_eff = {"act": {universe}}

        prev_total = None
        for _ in range(14):
            st = frozenset(
                _lit(n, rng.random() < 0.5) for n in _ATOMS
            )
            if hp_true <= st:
                succ = frozenset(x for x in st if x.negated() not in he_true) | he_true
                demo = Demonstration(State(st), Action("act", ()), State(succ))
            else:
                demo = Demonstration(State(st), Action("act", ()), None)
            run_ASCAL_iteration(L_pre, U_pre, L_eff, U_eff, demo)

            rep = compute_version_space_size(
                [_NamedAction("act")], U_pre, L_pre, L_eff, U_eff
            )["act"]
            if rep["collapsed"]:
                raise AssertionError("consistent GT must never collapse the space")

            l_hyp = next(iter(L_pre["act"]))
            gap = next(iter(U_eff["act"])) - next(iter(L_eff["act"]))
            exp_pre, exp_mod = _brute_force(U_pre["act"], l_hyp, gap)
            assert rep["total_exact"]
            assert (rep["n_pre"], rep["total"]) == (exp_pre, exp_mod)

            # version-space soundness: the ground truth is still representable
            assert any(u <= hp_true for u in U_pre["act"]) and hp_true <= l_hyp
            le = next(iter(L_eff["act"]))
            ue = next(iter(U_eff["act"]))
            assert le <= he_true <= ue

            if prev_total is not None:
                assert rep["total"] <= prev_total
            prev_total = rep["total"]


def test_non_antichain_frontier_same_count():
    """IE must be robust to redundant (non-minimal) frontier elements."""
    l_hyp = frozenset("abcde")
    gap = frozenset("bcx")
    minimal = {frozenset("a"), frozenset("bc")}
    redundant = minimal | {frozenset("ab"), frozenset("abc")}
    assert _count_pre_interval_single_lower(
        minimal, l_hyp, eff_gap=gap
    ) == _count_pre_interval_single_lower(redundant, l_hyp, eff_gap=gap)


def test_large_scale_closed_form_and_midsize_ie():
    """Bignum shortcut path at |l|=40, and a 12-frontier IE (4095 terms)
    against full 4096-subset brute force."""
    # empty-u shortcut, big: 15 gap literals outside l, 10 inside, 30 free non-gap
    l_hyp = frozenset(range(40))
    gap = frozenset(range(30, 55))              # 30..39 inside l, 40..54 outside
    n_pre, n_models, exact = _count_pre_interval_single_lower(
        {frozenset()}, l_hyp, eff_gap=gap
    )
    assert exact
    assert n_pre == 1 << 40
    assert n_models == (2**15) * (2**30) * (3**10)

    # converged, big
    n_pre, n_models, exact = _count_pre_interval_single_lower({l_hyp}, l_hyp)
    assert (n_pre, n_models, exact) == (1, 1, True)

    # mid-size IE: 12 singleton frontier elements, brute-forced
    l12 = frozenset(range(12))
    u12 = {frozenset({i}) for i in range(12)}
    gap12 = frozenset(range(8, 15))
    exp_pre, exp_mod = _brute_force(u12, l12, gap12)
    got = _count_pre_interval_single_lower(u12, l12, eff_gap=gap12)
    assert got == (exp_pre, exp_mod, True)
