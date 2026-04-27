"""
Evaluation functions for ASCAL action-model learners.

Three evaluation strategies are provided, each suitable for different stages
of learning and different reporting needs:

``evaluate_detailed``
    The core evaluation used during training.  Positives are scored with an
    existential check (any hypothesis in U_pre consistent → TP) and negatives
    use fractional counting across U_pre hypotheses.  Guarantees: sound
    precision = 1.0 always (C1); complete recall = 1.0 always (C2).

``evaluate_representative``
    Picks a single representative hypothesis — ``min(U_pre, key=len)`` — for
    the complete model and applies standard binary classification.  Matches
    ``evaluate_detailed`` exactly once ``|U_pre| == 1``.  Suitable for
    publication plots and comparison with non-version-space baselines.

``evaluate_convergence_gated``
    Reports metrics only for actions whose precondition version space has
    converged (``|U_pre| == 1``).  Non-converged actions are excluded from
    every numerator and denominator, giving clean binary P/R/F1.
"""
from ascal.algorithm import is_consistent, is_precondition_consistent
from ascal.models import Demonstration
from ascal.logger import get_logger

logger = get_logger(__name__)

from itertools import combinations

def _count_pre_interval_single_lower(
    u_hyps: set[frozenset],
    l_hyp: frozenset,
    ie_term_limit: int = 1_000_000,
) -> tuple[int, bool]:
    """
    Count |{h : exists u in U, u ⊆ h ⊆ l}| exactly via inclusion-exclusion
    when there is a single lower bound l.

    Returns:
      (count, exact_flag)
    """
    # Keep only U hypotheses compatible with l
    valid_u = [u for u in u_hyps if u.issubset(l_hyp)]
    m = len(l_hyp)

    if m == 0:
        # Only hypothesis is empty set; valid iff some u ⊆ empty (i.e., u==empty)
        return (1 if any(len(u) == 0 for u in valid_u) else 0), True

    if not valid_u:
        return 0, True

    # If empty precondition is in U, then every h ⊆ l is valid
    if any(len(u) == 0 for u in valid_u):
        return (1 << m), True

    k = len(valid_u)
    # inclusion-exclusion terms = 2^k - 1
    if (1 << k) - 1 > ie_term_limit:
        # Fallback bounds when exact IE is too large
        # lower: largest single up-set
        lower = max(1 << (m - len(u)) for u in valid_u)
        # upper: sum of single up-sets, clipped by full space
        upper = min(sum(1 << (m - len(u)) for u in valid_u), 1 << m)
        # midpoint estimate
        return (lower + upper) // 2, False

    # Exact inclusion-exclusion:
    # |⋃_u E_u| where E_u = {h ⊆ l : u ⊆ h} and |E_u| = 2^(m-|u|)
    total = 0
    vu = list(valid_u)
    for r in range(1, k + 1):
        sign = 1 if (r % 2 == 1) else -1
        for grp in combinations(vu, r):
            union_u = set().union(*grp)
            if len(union_u) > m:
                continue
            total += sign * (1 << (m - len(union_u)))
    return total, True


def compute_version_space_size(
    all_actions: list,
    U_pre: dict[str, set[frozenset]],
    L_pre: dict[str, set[frozenset]],
    L_eff: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
) -> dict[str, dict]:
    """
    Version-space size with multi-U_pre support.
    - Pre: exact for singleton L_pre via inclusion-exclusion over U_pre.
    - Eff: current interval proxy 2^|U_eff - L_eff|.
    """
    report = {}

    for action in all_actions:
        a = action.name

        up = U_pre.get(a, set())
        lp = L_pre.get(a, set())
        le = L_eff.get(a, set())
        ue = U_eff.get(a, set())

        # Collapse-safe handling
        if not up or not lp or not le or not ue:
            report[a] = {
                "n_pre": 0,
                "n_eff": 0,
                "total": 0,
                "converged": False,
                "collapsed": True,
                "n_pre_exact": True,
            }
            continue

        # ----- precondition size -----
        # In this codebase L_pre is usually singleton, but keep a fallback.
        if len(lp) == 1:
            l_hyp = next(iter(lp))
            n_pre, exact = _count_pre_interval_single_lower(up, l_hyp)
            pre_converged = (len(up) == 1 and next(iter(up)) == l_hyp)
        else:
            # Conservative fallback if multiple lower bounds exist:
            # sum per-lower (can overcount overlaps)
            n_pre = 0
            exact = False
            for l_hyp in lp:
                c, _ = _count_pre_interval_single_lower(up, l_hyp)
                n_pre += c
            pre_converged = False

        # ----- effect size (current proxy) -----
        heL = next(iter(le))
        heU = next(iter(ue))
        diff = heU - heL
        n_eff = 1 << len(diff)
        eff_converged = (len(diff) == 0)

        report[a] = {
            "n_pre": n_pre,                 # interval size (not len(U_pre))
            "n_eff": n_eff,
            "total": n_pre * n_eff,
            "converged": pre_converged and eff_converged,
            "collapsed": False,
            "n_pre_exact": exact,
            # useful diagnostics
            "frontier_u_pre": len(up),
            "frontier_l_pre": len(lp),
            "eff_gap_literals": len(diff),
        }

    return report

def old_compute_version_space_size(
    all_actions: list,
    U_pre: dict[str, set[frozenset]],
    L_pre: dict[str, set[frozenset]],
    L_eff: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
) -> dict[str, dict]:
    """
    Compute version space statistics per action.

    The version space is the set of all hypotheses still consistent
    with all demonstrations seen so far — bounded by L and U:

        L_pre: shrinks from full → converges to true preconditions
        U_pre: grows  from empty → converges to true preconditions
        L_eff: grows  from empty → converges to true effects
        U_eff: shrinks from full → converges to true effects

    Convergence is reached when L == U for both pre and eff.

    For each action reports:
        - n_pre:     number of hypotheses still in U_pre
        - n_eff:     2^|U_eff - L_eff| upper bound on effect hypotheses
        - converged: True if L_pre == U_pre and L_eff == U_eff
        - total:     n_pre * n_eff
    """
    report = {}

    for action in all_actions:
        n_pre = len(U_pre[action.name])

        heL  = next(iter(L_eff[action.name]))
        heU  = next(iter(U_eff[action.name]))
        diff = heU - heL
        n_eff = 1 << len(diff)   # 2^|diff|

        pre_converged = next(iter(U_pre[action.name])) == next(iter(L_pre[action.name]))
        eff_converged = len(diff) == 0

        report[action.name] = {
            "n_pre":     n_pre,
            "n_eff":     n_eff,
            "converged": pre_converged and eff_converged,
            "total":     n_pre * n_eff,
        }

        logger.debug("Action %-15s | pre=%d | eff≤%d | converged=%s",
                     action.name, n_pre, n_eff, pre_converged and eff_converged)

    total = sum(v["total"] for v in report.values())
    logger.info("Version space total size: %d | fully converged: %s",
                total, all(v["converged"] for v in report.values()))

    return report

def evaluate_detailed(
    positives: list[Demonstration],
    negatives: list[Demonstration],
    L_pre:     dict[str, set[frozenset]],
    U_pre:     dict[str, set[frozenset]],
    L_eff:     dict[str, set[frozenset]],
    U_eff:     dict[str, set[frozenset]],
) -> tuple[float, float, float, float, float, float]:
    """
    Evaluate precision, recall, and F1 for both sound and complete models.

    Returns (f1_sound, f1_complete,
             precision_sound, recall_sound,
             precision_complete, recall_complete).
    """
    tp_sound = fp_sound = fn_sound = 0
    tp_complete = fp_complete = fn_complete = 0

    for demonstration in positives:
        action_name = demonstration.action.name

        if not L_pre[action_name] or not L_eff[action_name] or not U_eff[action_name]:
            fn_sound += 1
            fn_complete += 1
            continue

        hpL = next(iter(L_pre[action_name]))
        heL = next(iter(L_eff[action_name]))                          

        if is_consistent(hpL, heL, demonstration):
            tp_sound += 1
        else:
            fn_sound += 1

        # Check whether ANY hypothesis in the version space is consistent
        # with this positive demo.
        #
        # Naive approach: enumerate all he between heL and heU (2^N elements).
        # Witness approach: the minimal candidate he* = heL ∪ delta is
        # consistent iff:
        #   (a) hp  ⊆ pre_state           (precondition satisfied)
        #   (b) heL ⊆ post_state          (mandatory effects occurred)
        #   (c) delta ⊆ heU               (all changes within upper bound)
        # Condition (c) implies he* ⊆ heU; delta ⊆ post_state is always true
        # by definition, so (b) is the only non-trivial effect check.
        # This is mathematically equivalent to the full enumeration — O(|U_pre|)
        # instead of O(|U_pre| × 2^|heU−heL|).
        pre_lits  = demonstration.pre_state.literals
        post_lits = demonstration.post_state.literals
        delta     = post_lits - pre_lits

        found = False
        for hp in U_pre[action_name]:
            if not hp.issubset(pre_lits):
                continue
            heL = next(iter(L_eff[action_name])) - hp
            heU = next(iter(U_eff[action_name])) - hp
            he_witness = heL | delta
            if he_witness.issubset(heU) and heL.issubset(post_lits):
                found = True
                break

        if found:
            tp_complete += 1
        else:
            fn_complete += 1

    for demonstration in negatives:
        action_name = demonstration.action.name

        if not L_pre[action_name] or not L_eff[action_name]:
            # No hypothesis yet → model can't accept anything → skip (not an FP)
            continue

        hpL = next(iter(L_pre[action_name]))
        heL = next(iter(L_eff[action_name]))                       

        if is_consistent(hpL, heL, demonstration):
            pass   # TN — not needed for precision/recall formula
        else:
            fp_sound += 1

        version_count = consistent_count = 0
        for hp in U_pre[action_name]:
            version_count += 1
            if is_precondition_consistent(hp, demonstration):
                consistent_count += 1

        if version_count > 0:
            fp_complete += (version_count - consistent_count) / version_count

    precision_sound    = tp_sound / (tp_sound + fp_sound) if (tp_sound + fp_sound) > 0 else 1.0
    recall_sound       = tp_sound / (tp_sound + fn_sound) if (tp_sound + fn_sound) > 0 else 0.0
    precision_complete = tp_complete / (tp_complete + fp_complete) if (tp_complete + fp_complete) > 0 else 1.0
    recall_complete    = tp_complete / (tp_complete + fn_complete) if (tp_complete + fn_complete) > 0 else 0.0

    f1_sound     = (2 * precision_sound * recall_sound) / (precision_sound + recall_sound) if (precision_sound + recall_sound) > 0 else 0.0
    f1_complete  = (2 * precision_complete * recall_complete) / (precision_complete + recall_complete) if (precision_complete + recall_complete) > 0 else 0.0

    logger.info("Sound     — P=%.2f R=%.2f F1=%.2f", precision_sound, recall_sound, f1_sound)
    logger.info("Complete  — P=%.2f R=%.2f F1=%.2f", precision_complete, recall_complete, f1_complete)

    return (f1_sound, f1_complete,
            precision_sound, recall_sound,
            precision_complete, recall_complete)


def evaluate_representative(
    positives: list[Demonstration],
    negatives: list[Demonstration],
    L_pre:     dict[str, set[frozenset]],
    U_pre:     dict[str, set[frozenset]],
    L_eff:     dict[str, set[frozenset]],
    U_eff:     dict[str, set[frozenset]],
) -> tuple[float, float, float, float, float, float, dict]:
    """
    Evaluate precision, recall and F1 using a single **representative hypothesis**
    for the complete model, instead of the existential / fractional strategy used
    by ``evaluate_detailed``.

    Representative selection
    ------------------------
    For each action the representative complete-model precondition hypothesis is::

        repr_hp = min(U_pre[action], key=len)   # fewest literals → most permissive

    This is the hypothesis closest to the true upper boundary.  When the version
    space has converged (``|U_pre| == 1``) it is the only hypothesis and the
    result is identical to ``evaluate_detailed``.

    Evaluation strategy
    -------------------
    * **Positive demos** — the complete model accepts if:

      1. ``repr_hp ⊆ pre_state``  (representative precondition satisfied)
      2. The minimal effect witness ``he* = (L_eff − repr_hp) ∪ delta`` is
         consistent with ``U_eff`` (same witness check as ``evaluate_detailed``).

    * **Negative demos** — standard binary check: the complete model correctly
      rejects iff ``repr_hp ⊄ pre_state`` (no fractional counting).

    Returns
    -------
    ``(f1_sound, f1_complete,
      precision_sound, recall_sound,
      precision_complete, recall_complete,
      status)``

    ``status`` is a ``dict[action_name -> {'n_hyps': int, 'converged': bool}]``
    indicating how many hypotheses each action still holds.  Use this to judge
    whether the complete-model metrics are meaningful yet:
    ``converged=True`` means ``n_hyps == 1`` and the metrics are exact.
    """
    # Pre-compute per-action representative hypotheses and convergence status
    status: dict[str, dict] = {}
    repr_hp_map: dict[str, frozenset] = {}
    for action_name in L_pre:
        hyps = U_pre[action_name]
        repr_hp = min(hyps, key=len) if hyps else frozenset()
        n_hyps  = len(hyps)
        repr_hp_map[action_name] = repr_hp
        status[action_name] = {
            "n_hyps":    n_hyps,
            "converged": n_hyps == 1 and repr_hp == next(iter(L_pre[action_name])),
        }

    tp_sound = fp_sound = fn_sound = 0
    tp_complete = fp_complete = fn_complete = 0

    for demonstration in positives:
        action_name = demonstration.action.name

        if not L_pre[action_name] or not L_eff[action_name] or not U_eff[action_name]:
            fn_sound += 1
            fn_complete += 1
            continue

        hpL = next(iter(L_pre[action_name]))
        heL = next(iter(L_eff[action_name]))

        # Sound model — same as evaluate_detailed
        if is_consistent(hpL, heL, demonstration):
            tp_sound += 1
        else:
            fn_sound += 1

        # Complete model — single representative, same witness approach as
        # evaluate_detailed but limited to repr_hp instead of all U_pre hyps
        repr_hp   = repr_hp_map[action_name]
        pre_lits  = demonstration.pre_state.literals
        post_lits = demonstration.post_state.literals
        delta     = post_lits - pre_lits

        if repr_hp.issubset(pre_lits):
            heL_adj    = heL - repr_hp
            heU_adj    = next(iter(U_eff[action_name])) - repr_hp
            he_witness = heL_adj | delta
            if he_witness.issubset(heU_adj) and heL_adj.issubset(post_lits):
                tp_complete += 1
            else:
                fn_complete += 1
        else:
            fn_complete += 1

    for demonstration in negatives:
        action_name = demonstration.action.name

        if not L_pre[action_name] or not L_eff[action_name]:
            # No hypothesis yet — model rejects everything, no FP possible
            continue

        hpL = next(iter(L_pre[action_name]))
        heL = next(iter(L_eff[action_name]))

        # Sound model: FP when model would accept (preconditions met) but action failed
        # is_consistent on a negative returns True when preconditions are NOT met (correct
        # rejection = TN). False means preconditions ARE met → model accepts → FP.
        if not is_consistent(hpL, heL, demonstration):
            fp_sound += 1
        # else: TN — not counted, only fp affects precision denominator

        # Complete model — binary check with representative hypothesis
        # FP when repr_hp ⊆ pre_state (model accepts) but action failed
        repr_hp  = repr_hp_map[action_name]
        pre_lits = demonstration.pre_state.literals
        if repr_hp.issubset(pre_lits):
            fp_complete += 1
        # else: TN — correctly rejected

    # Precision = TP / (TP + FP), Recall = TP / (TP + FN)
    precision_sound    = tp_sound / (tp_sound + fp_sound) if (tp_sound + fp_sound) > 0 else 1.0
    recall_sound       = tp_sound / (tp_sound + fn_sound) if (tp_sound + fn_sound) > 0 else 0.0
    precision_complete = tp_complete / (tp_complete + fp_complete) if (tp_complete + fp_complete) > 0 else 1.0
    recall_complete    = tp_complete / (tp_complete + fn_complete) if (tp_complete + fn_complete) > 0 else 0.0

    f1_sound    = (2 * precision_sound * recall_sound) / (precision_sound + recall_sound) if (precision_sound + recall_sound) > 0 else 0.0
    f1_complete = (2 * precision_complete * recall_complete) / (precision_complete + recall_complete) if (precision_complete + recall_complete) > 0 else 0.0

    logger.info("Representative | Sound    — P=%.2f R=%.2f F1=%.2f", precision_sound, recall_sound, f1_sound)
    logger.info("Representative | Complete — P=%.2f R=%.2f F1=%.2f", precision_complete, recall_complete, f1_complete)
    logger.info("Representative | Status   — %s",
                {k: f"n_hyps={v['n_hyps']} converged={v['converged']}" for k, v in status.items()})

    return (f1_sound, f1_complete,
            precision_sound, recall_sound,
            precision_complete, recall_complete,
            status)


def evaluate_convergence_gated(
    positives: list[Demonstration],
    negatives: list[Demonstration],
    L_pre:     dict[str, set[frozenset]],
    U_pre:     dict[str, set[frozenset]],
    L_eff:     dict[str, set[frozenset]],
    U_eff:     dict[str, set[frozenset]],
) -> tuple[float, float, float, float, float, float, dict]:
    """
    Evaluate P/R/F1 **only** for actions whose **precondition** version space has
    converged (``|U_pre| == 1``).

    Why precondition-only gating?
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ``|U_pre| == 1`` is the condition that eliminates the fractional/existential
    ambiguity in ``evaluate_detailed``.  Once a single precondition hypothesis
    remains, both sound and complete model evaluations use standard binary
    classification — no fractional FP counting, no existential TP checks.

    Effect uncertainty (``L_eff != U_eff``) is handled correctly by the witness
    check in ``evaluate_representative`` regardless of convergence state, so it
    does not need to be gated.  In extended domains with dummy inequality
    parameters, effect convergence may never be achieved within a reasonable
    number of problems, so requiring it would make this function permanently
    return ``0.0``.

    Non-gated actions are excluded from every numerator and denominator, so
    the aggregate numbers are always standard binary precision/recall — suitable
    for direct comparison with other papers.

    When no action has a converged precondition yet all six aggregate metrics
    are ``0.0`` and the per-action entries in ``status`` carry ``None`` for the
    metric fields.

    Returns
    -------
    ``(f1_sound, f1_complete,
      precision_sound, recall_sound,
      precision_complete, recall_complete,
      status)``

    ``status`` is a ``dict[action_name -> dict]`` with keys:

    * ``converged``   — bool: ``|U_pre| == 1`` for this action (gate criterion)
    * ``n_hyps``      — int: current ``|U_pre|`` for this action
    * ``p_sound``, ``r_sound``, ``f1_sound`` — float or ``None``
    * ``p_complete``, ``r_complete``, ``f1_complete`` — float or ``None``
    """
    # ── 1. Determine which actions have converged preconditions ───────────
    converged: set[str] = set()
    status: dict[str, dict] = {}

    for aname in L_pre:
        n_hyps   = len(U_pre[aname])
        pre_conv = (n_hyps == 1)          # sole gate criterion
        if pre_conv:
            converged.add(aname)
        status[aname] = {
            "converged":   pre_conv,
            "n_hyps":      n_hyps,
            "p_sound":     None, "r_sound":    None, "f1_sound":    None,
            "p_complete":  None, "r_complete": None, "f1_complete": None,
        }

    # ── 2. Per-action metrics for converged actions ───────────────────────
    for aname in converged:
        pos_a = [d for d in positives if d.action.name == aname]
        neg_a = [d for d in negatives if d.action.name == aname]
        # evaluate_representative is exact binary when |U_pre| == 1
        f1_s, f1_c, p_s, r_s, p_c, r_c, _ = evaluate_representative(
            pos_a, neg_a,
            {aname: L_pre[aname]}, {aname: U_pre[aname]},
            {aname: L_eff[aname]}, {aname: U_eff[aname]},
        )
        status[aname].update({
            "p_sound":    p_s,  "r_sound":    r_s,  "f1_sound":    f1_s,
            "p_complete": p_c,  "r_complete": r_c,  "f1_complete": f1_c,
        })

    # ── 3. Aggregate over converged actions only ──────────────────────────
    if not converged:
        logger.info(
            "Convergence-gated: 0/%d actions have |U_pre|=1 — aggregate undefined",
            len(L_pre),
        )
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, status)

    pos_gated = [d for d in positives if d.action.name in converged]
    neg_gated = [d for d in negatives if d.action.name in converged]

    f1_s, f1_c, p_s, r_s, p_c, r_c, _ = evaluate_representative(
        pos_gated, neg_gated,
        {a: L_pre[a] for a in converged},
        {a: U_pre[a] for a in converged},
        {a: L_eff[a] for a in converged},
        {a: U_eff[a] for a in converged},
    )

    logger.info(
        "Convergence-gated: %d/%d |U_pre|=1 | Sound P=%.2f R=%.2f | Complete P=%.2f R=%.2f",
        len(converged), len(L_pre), p_s, r_s, p_c, r_c,
    )
    return (f1_s, f1_c, p_s, r_s, p_c, r_c, status)


def evaluate_f1score(
    positives: list[Demonstration],
    negatives: list[Demonstration],
    L_pre:     dict[str, set[frozenset]],
    U_pre:     dict[str, set[frozenset]],
    L_eff:     dict[str, set[frozenset]],
    U_eff:     dict[str, set[frozenset]],
) -> tuple[float, float]:
    """
    Evaluate F1 scores for both sound and complete action models.
    Returns (f1_sound, f1_complete).
    """
    result = evaluate_detailed(positives, negatives, L_pre, U_pre, L_eff, U_eff)
    return result[0], result[1]
