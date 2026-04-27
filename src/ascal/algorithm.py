from unified_planning.shortcuts import *

"""
ASCAL version-space operators and action-model generators.

This module implements the eight boundary-update operators that form the core
of the ASCAL algorithm, together with initialisation, the single-step and
batch learning loops, and model-generation functions (sound, U-border, full
version space).

Version-space operators
-----------------------
Preconditions (called on *positive* demos unless noted):
    ULP  — Update Lower Preconditions   (intersect L_pre with pre_state)
    RUP  — Refine Upper Preconditions   (remove hypotheses not ⊆ pre_state)
    RLP  — Refine Lower Preconditions   (negative: remove hypotheses ⊆ pre_state)
    UUP  — Update Upper Preconditions   (negative: extend firing hypotheses)

Effects (called on *positive* demos only):
    ULE  — Update Lower Effects         (add delta to every L_eff hypothesis)
    RLE  — Remove Lower Effects         (keep only hypotheses ⊆ post_state)
    RUE  — Remove Upper Effects         (keep only hypotheses ⊇ delta)
    UUE  — Update Upper Effects         (intersect every U_eff hypothesis with post_state)

Learning entry points
---------------------
    ASCAL_initialization   — create empty/full boundary dicts for all actions
    run_ASCAL_iteration    — process one Demonstration in-place
    run_ASCAL              — offline batch wrapper

Model generators
----------------
    generate_sound_action_model / generate_sound_ground_action_model
        — L-boundary (sound) models; lifted and grounded.
    pre_generate_version_space
        — lifted full ``(hp, he)`` materialization without dummy-noop (legacy).
    generate_complete_border / generate_complete_border_grounded
        — permissive U-border: one action per ``hp ∈ U_pre`` with effects
        from the upper bound only (``U_eff`` minus literals in ``hp``).
    generate_complete_border_consistent / _grounded
        — same shape as border, but effect literals are a **maximal
        contradiction-free** subset of ``(U_eff - hp)`` containing ``L_eff - hp``.
    generate_complete_border_consistent_split / _grounded
        — like consistent border, but emits **one operator per completion** when
        ``(U_eff - hp)`` leaves polarities ambiguous (Cartesian split); optional
        ``max_completions`` cap.
    generate_complete_model / generate_complete_model_grounded
        — every ``hp ∈ U_pre`` × full effect interval; pairs with empty ``he``
        are omitted (no dummy-noop operators).
    generate_true_full_version_space / _grounded
        — **pre** interval × **effect** interval: every ``hp`` with
        ``∃ ℓ ∈ L_pre, u ∈ U_pre : u ⊆ hp ⊆ ℓ``, crossed with all ``he`` from
        ``generate_version_space_effects`` (can be exponentially larger than
        ``generate_complete_model``); empty ``he`` omitted in lifted export.
"""
from unified_planning.shortcuts import *
from itertools import combinations, product
from ascal.models import Literal, Action, Demonstration, has_contradiction, get_subsets, generate_version_space_effects
from ascal.transitions import generate_all_lifted_literals, generate_all_ground_literals
from ascal.logger import get_logger

logger = get_logger(__name__)


def precondition_interval_hypotheses(
    L_hypotheses: set[frozenset],
    U_hypotheses: set[frozenset],
) -> set[frozenset]:
    """
    Enumerate every precondition conjunction ``hp`` in the **literal-interval**
    between the L and U precondition boundaries.

    A hypothesis ``hp`` is included iff there exist ``ℓ ∈ L_hypotheses`` and
    ``u ∈ U_hypotheses`` such that ``u ⊆ hp ⊆ ℓ`` (subset order = adding
    literals makes preconditions stronger / more specific).

    This matches the precondition side of the full Cartesian version space
    used for exhaustive checks; ``generate_complete_model`` only
    iterates ``hp ∈ U_hypotheses`` (boundary hypotheses), not every ``hp``
    in this interval.
    """
    result: set[frozenset] = set()
    for l_hyp in L_hypotheses:
        for u in U_hypotheses:
            if not u.issubset(l_hyp):
                continue
            gap = l_hyp - u
            for ext in get_subsets(gap):
                result.add(frozenset(u.union(ext)))
    return result


def is_consistent(
    hp:            frozenset,
    he:            frozenset,
    demonstration: Demonstration,
) -> bool:
    """
    Check if a hypothesis (hp, he) is consistent with a demonstration.

    A hypothesis is consistent if:
    - Positive demonstration: 
        1) hp (preconditions) are all satisfied in pre_state
        2) delta (observed changes) are all explained by he (effects)
        3) he (effects) are all present in post_state
    - Negative demonstration (action failed):
        1) hp (preconditions) are NOT all satisfied → explains the failure
    Args:
        hp: frozenset of precondition literals
        he: frozenset of effect literals  
        demonstration: (pre_state, (action_name, args), post_state_or_None)
    """
    pre_state = demonstration.pre_state.literals  # frozenset — no set() conversion needed

    if demonstration.is_positive:
        # Positive demonstration
        post_state = demonstration.post_state.literals   # frozenset
        delta = post_state.difference(pre_state)         # observed changes

        consistent = (hp.issubset(pre_state)             # preconditions satisfied
                      and delta.issubset(he)             # changes explained by effects
                      and he.issubset(post_state))       # effects occurred
    else:
        # Negative demonstration — action failed
        # Consistent only if preconditions were NOT all satisfied
        consistent = not hp.issubset(pre_state)

    return consistent

def is_effect_consistent(
    he:            frozenset,
    demonstration: Demonstration,
) -> bool:
    """
    Check if an effect hypothesis is consistent with a POSITIVE demonstration.

    A demonstration (pre, action, post) is consistent with he if:
      1) Every observed change (delta) is explained by he
         → the action "caused" those changes
      2) Every hypothesized effect actually occurred
         → he doesn't predict changes that didn't happen

    IMPORTANT: caller must guarantee demonstration[2] is not None.

    Args:
        he: frozenset of effect literals e.g. {('on','(?x,?y)',True), ...}
        demonstration: (pre_state_frozenset, action, post_state_frozenset)
    """

    pre_state = demonstration.pre_state.literals
    post_state = demonstration.post_state.literals
    delta = post_state.difference(pre_state)

    consistent = delta.issubset(he) and he.issubset(post_state)
    # Condition 1:  every change is explained
    # Condition 2:  every predicted effect occurred

    return consistent

def is_precondition_consistent(
    hp:            frozenset,
    demonstration: Demonstration,
) -> bool:
    """
    Check if a precondition hypothesis is consistent with a demonstration.

    - Positive demo (post_state is not None):
        hp must be SATISFIED in pre_state
        → the action was applicable, so preconditions must hold

    - Negative demo (post_state is None):
        hp must NOT be fully satisfied in pre_state
        → this explains WHY the action failed

    Args:
        hp: frozenset of precondition literals
        demonstration: (pre_state_frozenset, action, post_state_or_None)
    """

    pre_state = demonstration.pre_state.literals

    if demonstration.is_positive:
        consistent = hp.issubset(pre_state)
    
    else:
        consistent = not hp.issubset(pre_state)

    return consistent

# Precondition operators
# Initialization
# L_hp := {frozenset(all_literals)}   most specific — all literals required
# U_hp := {frozenset()}               most general  — no literals required   
def RUP(U: set[frozenset], demonstration: Demonstration) -> set[frozenset]:
    """Refine Upper bound Preconditions on a positive demonstration."""
    return {h for h in U if h.issubset(demonstration.pre_state.literals)}

def RLP(L: set[frozenset], demonstration: Demonstration) -> set[frozenset]:
    """Refine Lower bound Preconditions on a negative demonstration."""
    return {h for h in L if not h.issubset(demonstration.pre_state.literals)}

def ULP(L: set[frozenset], demonstration: Demonstration) -> set[frozenset]:
    """Update Lower bound Preconditions on a positive demonstration."""
    return {h.intersection(demonstration.pre_state.literals) for h in L}

def UUP(U: set[frozenset], demonstration: Demonstration, L: set[frozenset]) -> set[frozenset]:
    """Update Upper bound Preconditions on a negative demonstration.

    For each hu in U that would fire (hu ⊆ pre_state), extend it by adding one
    literal from hL ∈ L_pre that was absent from pre_state.

    Subsumption filter (post-hoc): after generating all candidates, keep only
    the MINIMAL elements — discard h if any strictly smaller h2 (h2 ⊂ h, i.e.
    h2 is more general) already exists in the candidate set.
    This is order-independent.
    """
    pre_state = demonstration.pre_state.literals
    candidates = set()
    for hu in U:
        if not hu.issubset(pre_state):
            candidates.add(hu)
        else:
            for hL in L:
                missing = hL.difference(pre_state)
                for l in missing:
                    candidates.add(hu.union(frozenset({l})))
    # Keep only minimal elements (h2 < h means h2 is a proper subset of h)
    return {h for h in candidates if not any(h2 < h for h2 in candidates)}

# Effect operators
# Initialization
# L_he := {frozenset()}               most specific — no effects
# U_he := {frozenset(all_literals)}   most general  — all literals are effects

def RLE(L: set[frozenset], demonstration: Demonstration) -> set[frozenset]:
    """Remove inconsistent Lower bound Effects on a positive demonstration."""
    return {h for h in L if h.issubset(demonstration.post_state.literals)}

def RUE(U: set[frozenset], demonstration: Demonstration) -> set[frozenset]:
    """Remove inconsistent Upper bound Effects on a positive demonstration."""
    delta = demonstration.post_state.literals.difference(demonstration.pre_state.literals)
    return {h for h in U if delta.issubset(h)}

def ULE(L: set[frozenset], demonstration: Demonstration) -> set[frozenset]:
    """Update Lower bound Effects on a positive demonstration."""
    delta = demonstration.post_state.literals.difference(demonstration.pre_state.literals)
    return {h.union(delta) for h in L}

def UUE(U: set[frozenset], demonstration: Demonstration) -> set[frozenset]:
    """Update Upper bound Effects on a positive demonstration."""
    return {h.intersection(demonstration.post_state.literals) for h in U}


def run_ASCAL(
    all_fluents:    list,
    all_actions:    list,
    static_fluents: list,
    demonstrations: list[Demonstration],
) -> tuple[dict[str, set[frozenset]], dict[str, set[frozenset]],
           dict[str, set[frozenset]], dict[str, set[frozenset]]]:
    """Offline wrapper: initialize then process all demonstrations."""

    logger.info("Starting ASCAL | actions=%d | demos=%d", len(all_actions), len(demonstrations))

    L_pre, U_pre, L_eff, U_eff = ASCAL_initialization(all_fluents, all_actions, static_fluents)

    for demonstration in demonstrations:
        run_ASCAL_iteration(L_pre, U_pre, L_eff, U_eff, demonstration)

                
    logger.info("ASCAL complete after %d iterations", len(demonstrations))

    return L_pre, U_pre, L_eff, U_eff

def run_ASCAL_iteration(
    L_pre: dict[str, set[frozenset]],
    U_pre: dict[str, set[frozenset]],
    L_eff: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
    demonstration: Demonstration,
) -> None:
    """
    Process a single demonstration and update version space boundaries.
    """

    action_name = demonstration.action.name
    logger.debug("Processing %s demo: %s", "positive" if demonstration.is_positive else "negative", demonstration.action)

    if demonstration.is_positive:
        # Positive demonstration 
        U_pre[action_name] = RUP(U_pre[action_name], demonstration)
        L_pre[action_name] = ULP(L_pre[action_name], demonstration)
        L_eff[action_name] = RLE(L_eff[action_name], demonstration)
        L_eff[action_name] = ULE(L_eff[action_name], demonstration)
        U_eff[action_name] = RUE(U_eff[action_name], demonstration)
        U_eff[action_name] = UUE(U_eff[action_name], demonstration)
    else:
        # Negative demonstration 
        L_pre[action_name] = RLP(L_pre[action_name], demonstration)
        U_pre[action_name] = UUP(U_pre[action_name], demonstration,
                                  L_pre[action_name])
                        
def ASCAL_initialization(
    all_fluents:    list,
    all_actions:    list,
    static_fluents: list,
    ground:         bool = False,
) -> tuple[dict[str, set[frozenset]], dict[str, set[frozenset]],
           dict[str, set[frozenset]], dict[str, set[frozenset]]]:
    """
    Initialize version space boundaries.
    
    Use this directly when you need the online interface:
        state = ASCAL_initialization(...)
        while True:
            run_ASCAL_iteration(*state, next_demo)
    """

    logger.debug("Initializing ASCAL | actions=%d | ground=%s", len(all_actions), ground)

    L_pre = {action.name: set() for action in all_actions}
    U_pre = {action.name: set() for action in all_actions}
    L_eff = {action.name: set() for action in all_actions}
    U_eff = {action.name: set() for action in all_actions}

    if ground:
        all_grounded_literals = frozenset(generate_all_ground_literals(all_fluents))
        for action in all_actions:
            L_pre[action.name].add(all_grounded_literals)
            U_pre[action.name].add(frozenset())
            L_eff[action.name].add(frozenset())
            U_eff[action.name].add(all_grounded_literals)
    else:
        static_names = {f.name for f in static_fluents}
        all_literals = {action.name: generate_all_lifted_literals(action, all_fluents) for action in all_actions}
        all_nonstatic_literals = { action.name: frozenset(l for l in all_literals[action.name]if l.fluent not in static_names) for action in all_actions}
        for action in all_actions:
            L_pre[action.name].add(frozenset(all_literals[action.name]))
            U_pre[action.name].add(frozenset())
            L_eff[action.name].add(frozenset())
            U_eff[action.name].add(all_nonstatic_literals[action.name])

    logger.debug("Initialization complete")

    return L_pre, U_pre, L_eff, U_eff

def old_generate_sound_action_model(
    all_fluents: list,
    all_actions: list,
    L_pre:       dict[str, set[frozenset]],
    L_eff:       dict[str, set[frozenset]],
) -> Problem:
    """
    Build a lifted sound action model from the L boundaries of the version space.

    'Sound' means we use the L (lower/most-specific) boundary:
    - L_pre: the most restrictive preconditions learned so far
    - L_eff: the most conservative effects learned so far

    An action is only added if:
    1) The version space has converged to a single hypothesis for both
       preconditions and effects (``len == 1``).
    2) The precondition hypothesis contains no contradictions.

    Inequality preconditions ``not (= ?p1 ?p2)`` are added automatically for
    all pairs of parameters that share the same type.

    Args:
        all_fluents: list of UP Fluent objects from the domain.
        all_actions: list of UP Action objects from the domain.
        L_pre:       lower precondition boundary — ``{action_name: {frozenset[Literal]}}``.
        L_eff:       lower effect boundary       — ``{action_name: {frozenset[Literal]}}``.

    Returns:
        A UP ``Problem`` containing one ``InstantaneousAction`` per action
        whose version space has converged and whose preconditions are consistent.
    """

    sound_model = Problem("Sound Action Model")
    
    for fluent in all_fluents:
        sound_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}
    for action in all_actions:
        if len(L_pre[action.name]) == 1 and len(L_eff[action.name]) == 1:
            hp = next(iter(L_pre[action.name])) 
            he = next(iter(L_eff[action.name]))

            if not has_contradiction(hp):
                my_action = InstantaneousAction(
                    action.name,
                    {par.name: par.type for par in action.parameters}
                )
                my_pars = {par.name: my_action.parameter(par.name)
                           for par in action.parameters}

                for pair in combinations(my_action.parameters, 2):
                    if pair[0].type == pair[1].type:
                        my_action.add_precondition(Not(Equals(pair[0], pair[1])))

                for literal in hp:
                    literal_arguments = [my_pars[lit_par] for lit_par in literal.arguments]
                    if literal.value:
                        my_action.add_precondition(my_fluents[literal.fluent](*literal_arguments))
                    else:
                        my_action.add_precondition(Not(my_fluents[literal.fluent](*literal_arguments)))

                for literal in he:
                    literal_arguments = [my_pars[lit_par] for lit_par in literal.arguments]
                    my_action.add_effect(my_fluents[literal.fluent](*literal_arguments), literal.value)

                sound_model.add_action(my_action)

    return sound_model

def generate_sound_action_model(
    all_fluents: list,
    all_actions: list,
    L_pre:       dict[str, set[frozenset]],
    L_eff:       dict[str, set[frozenset]],
) -> Problem:
    """
    Build a lifted sound action model from the L boundaries of the version space.
    The sound (lower) boundary uses:
    - ``L_pre``: most specific precondition hypotheses learned so far
    - ``L_eff``: most conservative effect hypotheses learned so far
    For each domain action, an ``InstantaneousAction`` is added **only when**
    both boundaries are singletons for that symbol
    (``len(L_pre[name]) == 1`` and ``len(L_eff[name]) == 1``) **and** the unique
    effect hypothesis ``he`` is **non-empty**. Rows with ``he = ∅`` are skipped
    so PDDL exports remain valid (Fast Downward requires every action to have
    an ``:effect``).
    **Contradictory preconditions.** If the unique ``hp ∈ L_pre`` contains both
    a literal and its negation for the same atom, the encoded precondition
    conjunction is classically **unsatisfiable**. The action is still emitted
    so the model reflects the current L boundary; such an action is never
    applicable in a consistent state. This is intentional when you want a
    total representation of L even before learning removes contradictions.
    **Planner note.** Unsatisfiable or very strong preconditions may yield a
    domain that does not support plans even when a looser U-boundary model
    does; use ``generate_complete_border`` or ``generate_complete_model``
    for permissive planning-oriented exports.
    Inequality preconditions ``not (= ?p1 ?p2)`` are added for all pairs of
    parameters that share the same type (same as before).
    Args:
        all_fluents: UP fluent objects from the domain.
        all_actions: UP action objects from the domain.
        L_pre: ``{action_name: {frozenset[Literal]}}``.
        L_eff: ``{action_name: {frozenset[Literal]}}``.
    Returns:
        A UP ``Problem`` with fluents and one instantiated action per action
        symbol that has singleton L_pre and L_eff.
    """

    sound_model = Problem("Sound Action Model")
    
    for fluent in all_fluents:
        sound_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}
    for action in all_actions:
        if len(L_pre[action.name]) == 1 and len(L_eff[action.name]) == 1:
            hp = next(iter(L_pre[action.name]))
            he = next(iter(L_eff[action.name]))
            if not he:
                continue

            #if not has_contradiction(hp):
            my_action = InstantaneousAction(
                action.name,
                {par.name: par.type for par in action.parameters}
            )
            my_pars = {par.name: my_action.parameter(par.name)
                        for par in action.parameters}

            for pair in combinations(my_action.parameters, 2):
                if pair[0].type == pair[1].type:
                    my_action.add_precondition(Not(Equals(pair[0], pair[1])))

            for literal in hp:
                literal_arguments = [my_pars[lit_par] for lit_par in literal.arguments]
                if literal.value:
                    my_action.add_precondition(my_fluents[literal.fluent](*literal_arguments))
                else:
                    my_action.add_precondition(Not(my_fluents[literal.fluent](*literal_arguments)))

            for literal in he:
                literal_arguments = [my_pars[lit_par] for lit_par in literal.arguments]
                my_action.add_effect(my_fluents[literal.fluent](*literal_arguments), literal.value)

            sound_model.add_action(my_action)

    return sound_model


def generate_sound_ground_action_model(
    all_fluents:   list,                        # list of UP Fluent objects
    all_actions:   list,                        # list of UP Action objects
    all_constants: list,                        # list of UP Object (constant) objects
    L_pre:         dict[str, set[frozenset]],   # action name → {frozenset[Literal]}
    L_eff:         dict[str, set[frozenset]],   # action name → {frozenset[Literal]}
) -> Problem:
    """
    Build a grounded sound action model from the L boundaries of the version space.

    'Sound' means we use the L (lower/most-specific) boundary:
    - L_pre: the most restrictive preconditions learned so far
    - L_eff: the most conservative effects learned so far

    'Grounded' means literal arguments are concrete object names (e.g. "blockA"),
    looked up via my_constants — unlike the lifted version which uses parameter
    names (e.g. "?x") looked up via my_pars.

    An action is only added if:
    1) The version space has converged to a single hypothesis for both
       preconditions and effects (len == 1).
    2) The precondition hypothesis has no contradictions
       (e.g. on(blockA,blockB)=True AND on(blockA,blockB)=False).
    3) The effect hypothesis is non-empty (PDDL requires ``:effect``).

    Note: inequality preconditions (Not(Equals(...))) are NOT added here
    because grounded actions use concrete distinct objects — no two constants
    can be equal, so the guard is unnecessary.
    """

    sound_model = Problem("Sound Ground Action Model")

    for fluent in all_fluents:
        sound_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}  
    my_constants = {constant.name: constant for constant in all_constants}

    for action in all_actions:
        if len(L_pre[action.name]) == 1 and len(L_eff[action.name]) == 1:
            hp = next(iter(L_pre[action.name]))
            he = next(iter(L_eff[action.name]))

            if has_contradiction(hp):
                continue
            if not he:
                continue

            my_action = InstantaneousAction(action.name)

            for literal in hp:
                literal_arguments = [my_constants[object_name] for object_name in literal.arguments] 
                if literal.value:
                    my_action.add_precondition(my_fluents[literal.fluent](*literal_arguments)) 
                else:
                    my_action.add_precondition(Not(my_fluents[literal.fluent](*literal_arguments)))

            for literal in he:
                literal_arguments = [my_constants[obj_name] for obj_name in literal.arguments]
                my_action.add_effect(my_fluents[literal.fluent](*literal_arguments), literal.value)

            sound_model.add_action(my_action)

    return sound_model

def pre_generate_version_space(
    all_fluents: list,
    all_actions: list,
    U_pre:       dict[str, set[frozenset]],
    L_eff:       dict[str, set[frozenset]],
    U_eff:       dict[str, set[frozenset]],
) -> Problem:
    """
    Lifted **full version space** (legacy helper): materialize every consistent
    ``(hp, he)`` with ``hp ∈ U_pre`` and ``he`` ranging over the effect interval
    between ``L_eff`` and ``U_eff`` (after subtracting ``hp`` from bounds).

    Same logic as ``generate_complete_model`` except it keeps empty-``he``
    operators as zero-effect actions (no dummy fluent). Prefer
    ``generate_complete_model`` for normal use (empty ``he`` rows omitted).

    Action names are ``{domain_action}_version{n}``.
    """
    complete_model = Problem("Version Space Action Model (pre)")

    for fluent in all_fluents:
        complete_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}

    for action in all_actions:
        version_num = 1
        le_raw = next(iter(L_eff[action.name]))
        ue_raw = next(iter(U_eff[action.name]))
        for hp in U_pre[action.name]:
            heL = le_raw - hp
            heU = ue_raw - hp
            V_eff = generate_version_space_effects(heL, heU)

            for he in V_eff:
                my_action = InstantaneousAction(
                    f"{action.name}_version{version_num}",
                    {par.name: par.type for par in action.parameters}
                )
                my_pars = {par.name: my_action.parameter(par.name) for par in action.parameters}

                for pair in combinations(my_action.parameters, 2):
                    if pair[0].type == pair[1].type:
                        my_action.add_precondition(Not(Equals(pair[0], pair[1])))

                for literal in hp:                                                     
                    literal_arguments = [my_pars[lit_par] for lit_par in literal.arguments]
                    if literal.value:
                        my_action.add_precondition(my_fluents[literal.fluent](*literal_arguments))
                    else:
                        my_action.add_precondition(Not(my_fluents[literal.fluent](*literal_arguments)))

                for literal in he:                                                    
                    literal_arguments = [my_pars[lit_par] for lit_par in literal.arguments]
                    my_action.add_effect(my_fluents[literal.fluent](*literal_arguments), literal.value)

                complete_model.add_action(my_action)
                version_num += 1

    return complete_model


def maximal_consistent_effect_subset(he_lo: frozenset, he_hi: frozenset) -> frozenset:
    """
    Return a **maximal-cardinality** frozenset ``H`` with
    ``he_lo ⊆ H ⊆ he_hi`` and ``not has_contradiction(H)``.

    Used to export border-style operators without both ``p`` and ``¬p`` on the
    same ground/lifted atom in one action's effect list.

    For each atom ``(fluent, arguments)`` that appears in ``he_hi`` with **both**
    polarities, at most one may appear in ``H``. If ``he_lo`` already contains a
    literal for that atom, it is kept (must be one of the two). If ``he_lo`` is
    silent on that atom, the **positive** literal is kept (deterministic
    tie-break).

    Returns empty ``frozenset()`` if ``he_lo ⊄ he_hi``, ``he_lo`` is contradictory,
    or no valid ``H`` exists.
    """
    if not he_lo.issubset(he_hi):
        return frozenset()
    if has_contradiction(he_lo):
        return frozenset()

    def atom_key(lit: Literal) -> tuple[str, tuple]:
        return (lit.fluent, lit.arguments)

    by_atom: dict[tuple[str, tuple], list[Literal]] = {}
    for lit in he_hi:
        k = atom_key(lit)
        by_atom.setdefault(k, []).append(lit)

    H: set[Literal] = set(he_lo)

    for atom, lits in by_atom.items():
        pos = next((l for l in lits if l.value), None)
        neg = next((l for l in lits if not l.value), None)
        lo_here = [l for l in he_lo if atom_key(l) == atom]

        if pos is not None and neg is not None:
            if len(lo_here) > 1:
                return frozenset()
            if len(lo_here) == 1:
                chosen = lo_here[0]
                if chosen not in (pos, neg):
                    return frozenset()
            else:
                chosen = pos
            H = {l for l in H if atom_key(l) != atom}
            H.add(chosen)
        else:
            if len(lits) != 1:
                return frozenset()
            only = lits[0]
            if lo_here:
                if lo_here != [only]:
                    return frozenset()
            else:
                H.add(only)

    out = frozenset(H)
    if not he_lo.issubset(out) or not out.issubset(he_hi):
        return frozenset()
    if has_contradiction(out):
        return frozenset()
    return out


def enumerate_maximal_consistent_effect_subsets(
    he_lo: frozenset,
    he_hi: frozenset,
    *,
    max_completions: int | None = None,
) -> list[frozenset]:
    """
    Enumerate **all** maximal-cardinality contradiction-free effect sets ``H``
    with ``he_lo ⊆ H ⊆ he_hi``.

    For each atom in ``he_hi`` that appears with **both** polarities and
    ``he_lo`` fixes neither, both choices are emitted (Cartesian product across
    such atoms). Atoms with a single polarity, or forced by ``he_lo``, yield a
    single option. Ordering is deterministic (sorted atom keys; ambiguous
    branches try **positive** before **negative**).

    Returns ``[]`` if ``he_lo ⊄ he_hi``, ``he_lo`` is contradictory, or the
    constraints are impossible. If ``max_completions`` is set, stops after that
    many completions (order as produced by ``itertools.product``).
    """
    if not he_lo.issubset(he_hi):
        return []
    if has_contradiction(he_lo):
        return []

    def atom_key(lit: Literal) -> tuple[str, tuple]:
        return (lit.fluent, lit.arguments)

    by_atom: dict[tuple[str, tuple], list[Literal]] = {}
    for lit in he_hi:
        k = atom_key(lit)
        by_atom.setdefault(k, []).append(lit)

    slots: list[tuple[Literal, ...]] = []
    for atom in sorted(by_atom.keys(), key=lambda k: (k[0], k[1])):
        lits = by_atom[atom]
        pos = next((l for l in lits if l.value), None)
        neg = next((l for l in lits if not l.value), None)
        lo_here = [l for l in he_lo if atom_key(l) == atom]

        if pos is not None and neg is not None:
            if len(lo_here) > 1:
                return []
            if len(lo_here) == 1:
                if lo_here[0] not in (pos, neg):
                    return []
                slots.append((lo_here[0],))
            else:
                slots.append((pos, neg))
        else:
            if len(lits) != 1:
                return []
            only = lits[0]
            if lo_here:
                if lo_here != [only]:
                    return []
            slots.append((only,))

    out: list[frozenset] = []
    for combo in product(*slots):
        H = frozenset(combo)
        if not he_lo.issubset(H) or not H.issubset(he_hi) or has_contradiction(H):
            continue
        out.append(H)
        if max_completions is not None and len(out) >= max_completions:
            break
    return out


def generate_complete_border(
    all_fluents: list,
    all_actions: list,
    U_pre: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
) -> Problem:
    """
    Lifted **U-border** (compact) action model for permissive planning.

    For each domain action and each ``hp ∈ U_pre``, emits **one**
    ``InstantaneousAction`` with preconditions from ``hp`` (plus same-type
    parameter inequalities) and effects from **only** the upper effect bound:
    ``he = U_eff - hp`` (one representative ``U_eff`` hypothesis per action,
    same rule as ``generate_complete_model``).

    Does **not** enumerate intermediate effect hypotheses; for that use
    ``generate_complete_model``.

    If ``he = U_eff - hp`` is empty, that ``hp`` row is **omitted** (no operator),
    saving actions and avoiding a dummy-noop fluent.

    Action names are ``{domain_action}_version{n}`` (one version per kept ``hp``).
    """
    complete_model = Problem("Complete Border Action Model")

    for fluent in all_fluents:
        complete_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}

    for action in all_actions:
        version_num = 1
        ue_raw = next(iter(U_eff[action.name]))
        for hp in U_pre[action.name]:
            he = ue_raw - hp
            if not he:
                continue
            params_to_pass = {par.name: par.type for par in action.parameters}
            my_action = InstantaneousAction(
                f"{action.name}_version{version_num}",
                **params_to_pass,
            )
            my_pars = {
                par.name: my_action.parameter(par.name) for par in action.parameters
            }

            for pair in combinations(my_action.parameters, 2):
                if pair[0].type == pair[1].type:
                    my_action.add_precondition(Not(Equals(pair[0], pair[1])))

            for literal in hp:
                literal_arguments = [my_pars[lit_par] for lit_par in literal.arguments]
                if literal.value:
                    my_action.add_precondition(
                        my_fluents[literal.fluent](*literal_arguments)
                    )
                else:
                    my_action.add_precondition(
                        Not(my_fluents[literal.fluent](*literal_arguments))
                    )

            for literal in he:
                literal_arguments = [
                    my_pars[lit_par] for lit_par in literal.arguments
                ]
                my_action.add_effect(
                    my_fluents[literal.fluent](*literal_arguments), literal.value
                )

            complete_model.add_action(my_action)
            version_num += 1

    return complete_model



def generate_complete_border_grounded(
    all_fluents: list,
    all_actions: list,
    all_constants: list,
    U_pre: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
) -> Problem:
    """
    Grounded **U-border** model: same semantics as ``generate_complete_border`` but
    with concrete object arguments (no lifted parameters, no inequality guards).

    One ``InstantaneousAction`` per ``hp ∈ U_pre`` with effects ``U_eff - hp``.
    Rows with empty ``he`` are omitted (same as lifted border).
    """
    complete_model = Problem("Complete Border Ground Action Model")

    for fluent in all_fluents:
        complete_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}
    my_constants = {constant.name: constant for constant in all_constants}

    for action in all_actions:
        version_num = 1
        ue_raw = next(iter(U_eff[action.name]))
        for hp in U_pre[action.name]:
            he = ue_raw - hp
            if not he:
                continue
            my_action = InstantaneousAction(f"{action.name}_version{version_num}")

            for literal in hp:
                literal_arguments = [
                    my_constants[obj_name] for obj_name in literal.arguments
                ]
                if literal.value:
                    my_action.add_precondition(
                        my_fluents[literal.fluent](*literal_arguments)
                    )
                else:
                    my_action.add_precondition(
                        Not(my_fluents[literal.fluent](*literal_arguments))
                    )

            for literal in he:
                literal_arguments = [
                    my_constants[obj_name] for obj_name in literal.arguments
                ]
                my_action.add_effect(
                    my_fluents[literal.fluent](*literal_arguments), literal.value
                )

            complete_model.add_action(my_action)
            version_num += 1

    return complete_model


def generate_complete_border_consistent(
    all_fluents: list,
    all_actions: list,
    U_pre: dict[str, set[frozenset]],
    L_eff: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
) -> Problem:
    """
    Lifted **U-border consistent** model: same layout as ``generate_complete_border``
    (one ``InstantaneousAction`` per ``hp ∈ U_pre``), but effects are a
    **maximal contradiction-free** set ``H`` with
    ``(L_eff - hp) ⊆ H ⊆ (U_eff - hp)`` (using one representative each from
    ``L_eff`` and ``U_eff``, same as ``generate_complete_model``).

    Rows with empty ``H`` are omitted (no dummy-noop operators).

    Action names are ``{domain_action}_version{n}`` (one version per kept ``hp``).
    """
    complete_model = Problem("Complete Border Consistent Action Model")

    for fluent in all_fluents:
        complete_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}

    for action in all_actions:
        version_num = 1
        le_raw = next(iter(L_eff[action.name]))
        ue_raw = next(iter(U_eff[action.name]))
        for hp in U_pre[action.name]:
            he_lo = le_raw - hp
            he_hi = ue_raw - hp
            he = maximal_consistent_effect_subset(he_lo, he_hi)
            if not he:
                continue
            params_to_pass = {par.name: par.type for par in action.parameters}
            my_action = InstantaneousAction(
                f"{action.name}_version{version_num}",
                **params_to_pass,
            )
            my_pars = {
                par.name: my_action.parameter(par.name) for par in action.parameters
            }

            for pair in combinations(my_action.parameters, 2):
                if pair[0].type == pair[1].type:
                    my_action.add_precondition(Not(Equals(pair[0], pair[1])))

            for literal in hp:
                literal_arguments = [my_pars[lit_par] for lit_par in literal.arguments]
                if literal.value:
                    my_action.add_precondition(
                        my_fluents[literal.fluent](*literal_arguments)
                    )
                else:
                    my_action.add_precondition(
                        Not(my_fluents[literal.fluent](*literal_arguments))
                    )

            for literal in he:
                literal_arguments = [
                    my_pars[lit_par] for lit_par in literal.arguments
                ]
                my_action.add_effect(
                    my_fluents[literal.fluent](*literal_arguments), literal.value
                )

            complete_model.add_action(my_action)
            version_num += 1

    return complete_model


def generate_complete_border_consistent_grounded(
    all_fluents: list,
    all_actions: list,
    all_constants: list,
    U_pre: dict[str, set[frozenset]],
    L_eff: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
) -> Problem:
    """
    Grounded **U-border consistent** model: same semantics as
    ``generate_complete_border_consistent`` with concrete object arguments.
    """
    complete_model = Problem("Complete Border Consistent Ground Action Model")

    for fluent in all_fluents:
        complete_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}
    my_constants = {constant.name: constant for constant in all_constants}

    for action in all_actions:
        version_num = 1
        le_raw = next(iter(L_eff[action.name]))
        ue_raw = next(iter(U_eff[action.name]))
        for hp in U_pre[action.name]:
            he_lo = le_raw - hp
            he_hi = ue_raw - hp
            he = maximal_consistent_effect_subset(he_lo, he_hi)
            if not he:
                continue
            my_action = InstantaneousAction(f"{action.name}_version{version_num}")

            for literal in hp:
                literal_arguments = [
                    my_constants[obj_name] for obj_name in literal.arguments
                ]
                if literal.value:
                    my_action.add_precondition(
                        my_fluents[literal.fluent](*literal_arguments)
                    )
                else:
                    my_action.add_precondition(
                        Not(my_fluents[literal.fluent](*literal_arguments))
                    )

            for literal in he:
                literal_arguments = [
                    my_constants[obj_name] for obj_name in literal.arguments
                ]
                my_action.add_effect(
                    my_fluents[literal.fluent](*literal_arguments), literal.value
                )

            complete_model.add_action(my_action)
            version_num += 1

    return complete_model


def generate_complete_border_consistent_split(
    all_fluents: list,
    all_actions: list,
    U_pre: dict[str, set[frozenset]],
    L_eff: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
    *,
    max_completions_per_hp: int | None = None,
) -> Problem:
    """
    Lifted **U-border consistent split** model: like ``generate_complete_border_consistent``,
    but when ``(U_eff - hp)`` contains **both** polarities for an atom while
    ``(L_eff - hp)`` fixes neither, emits **separate** ``InstantaneousAction``s for
    each Cartesian choice (all maximal contradiction-free ``H`` in that interval),
    up to ``max_completions_per_hp`` per ``hp`` (``None`` = no cap).

    With no ambiguous atoms, this matches ``generate_complete_border_consistent``
    (one operator per ``hp``). Action names are ``{domain_action}_version{n}``
    (global counter per domain action).
    """
    complete_model = Problem("Complete Border Consistent Split Action Model")

    for fluent in all_fluents:
        complete_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}

    for action in all_actions:
        version_num = 1
        le_raw = next(iter(L_eff[action.name]))
        ue_raw = next(iter(U_eff[action.name]))
        for hp in U_pre[action.name]:
            he_lo = le_raw - hp
            he_hi = ue_raw - hp
            completions = enumerate_maximal_consistent_effect_subsets(
                he_lo,
                he_hi,
                max_completions=max_completions_per_hp,
            )
            for he in completions:
                if not he:
                    continue
                params_to_pass = {par.name: par.type for par in action.parameters}
                my_action = InstantaneousAction(
                    f"{action.name}_version{version_num}",
                    **params_to_pass,
                )
                my_pars = {
                    par.name: my_action.parameter(par.name) for par in action.parameters
                }

                for pair in combinations(my_action.parameters, 2):
                    if pair[0].type == pair[1].type:
                        my_action.add_precondition(Not(Equals(pair[0], pair[1])))

                for literal in hp:
                    literal_arguments = [
                        my_pars[lit_par] for lit_par in literal.arguments
                    ]
                    if literal.value:
                        my_action.add_precondition(
                            my_fluents[literal.fluent](*literal_arguments)
                        )
                    else:
                        my_action.add_precondition(
                            Not(my_fluents[literal.fluent](*literal_arguments))
                        )

                for literal in he:
                    literal_arguments = [
                        my_pars[lit_par] for lit_par in literal.arguments
                    ]
                    my_action.add_effect(
                        my_fluents[literal.fluent](*literal_arguments), literal.value
                    )

                complete_model.add_action(my_action)
                version_num += 1

    return complete_model


def generate_complete_border_consistent_split_grounded(
    all_fluents: list,
    all_actions: list,
    all_constants: list,
    U_pre: dict[str, set[frozenset]],
    L_eff: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
    *,
    max_completions_per_hp: int | None = None,
) -> Problem:
    """
    Grounded **U-border consistent split** model: same semantics as
    ``generate_complete_border_consistent_split`` with concrete object arguments.
    """
    complete_model = Problem("Complete Border Consistent Split Ground Action Model")

    for fluent in all_fluents:
        complete_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}
    my_constants = {constant.name: constant for constant in all_constants}

    for action in all_actions:
        version_num = 1
        le_raw = next(iter(L_eff[action.name]))
        ue_raw = next(iter(U_eff[action.name]))
        for hp in U_pre[action.name]:
            he_lo = le_raw - hp
            he_hi = ue_raw - hp
            completions = enumerate_maximal_consistent_effect_subsets(
                he_lo,
                he_hi,
                max_completions=max_completions_per_hp,
            )
            for he in completions:
                if not he:
                    continue
                my_action = InstantaneousAction(f"{action.name}_version{version_num}")

                for literal in hp:
                    literal_arguments = [
                        my_constants[obj_name] for obj_name in literal.arguments
                    ]
                    if literal.value:
                        my_action.add_precondition(
                            my_fluents[literal.fluent](*literal_arguments)
                        )
                    else:
                        my_action.add_precondition(
                            Not(my_fluents[literal.fluent](*literal_arguments))
                        )

                for literal in he:
                    literal_arguments = [
                        my_constants[obj_name] for obj_name in literal.arguments
                    ]
                    my_action.add_effect(
                        my_fluents[literal.fluent](*literal_arguments), literal.value
                    )

                complete_model.add_action(my_action)
                version_num += 1

    return complete_model


def generate_complete_model(
    all_fluents: list,
    all_actions: list,
    U_pre:       dict[str, set[frozenset]],
    L_eff:       dict[str, set[frozenset]],
    U_eff:       dict[str, set[frozenset]],
) -> Problem:
    """
    Lifted export: every ``hp ∈ U_pre`` crossed with the **full effect interval**.

    For each domain action, for each **boundary** precondition hypothesis
    ``hp ∈ U_pre`` (not every ``hp`` in the L–U literal interval), enumerates
    every ``he`` with ``heL ⊆ he ⊆ heU`` where ``heL = L_eff - hp`` and
    ``heU = U_eff - hp``. For **pre interval × eff interval**, use
    ``generate_true_full_version_space`` (can be exponentially larger).

    For **compact permissive planning** (upper effects only, one action per
    ``hp ∈ U_pre``), use ``generate_complete_border`` instead.

    Pairs with empty ``he`` are **omitted** (no dummy-noop operators).

    Action names are ``{domain_action}_version{n}``.
    """
    complete_model = Problem("Version Space Action Model")

    for fluent in all_fluents:
        complete_model.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}

    for action in all_actions:
        version_num = 1
        le_raw = next(iter(L_eff[action.name]))
        ue_raw = next(iter(U_eff[action.name]))
        for hp in U_pre[action.name]:
            heL = le_raw - hp
            heU = ue_raw - hp
            V_eff = generate_version_space_effects(heL, heU)

            for he in V_eff:
                if not he:
                    continue
                params_to_pass = {par.name: par.type for par in action.parameters}
                my_action = InstantaneousAction(
                    f"{action.name}_version{version_num}",
                    **params_to_pass
                )
                my_pars = {par.name: my_action.parameter(par.name) for par in action.parameters}

                for pair in combinations(my_action.parameters, 2):
                    if pair[0].type == pair[1].type:
                        my_action.add_precondition(Not(Equals(pair[0], pair[1])))

                for literal in hp:                                                     
                    literal_arguments = [my_pars[lit_par] for lit_par in literal.arguments]
                    if literal.value:
                        my_action.add_precondition(my_fluents[literal.fluent](*literal_arguments))
                    else:
                        my_action.add_precondition(Not(my_fluents[literal.fluent](*literal_arguments)))

                for literal in he:                                                    
                    literal_arguments = [my_pars[lit_par] for lit_par in literal.arguments]
                    my_action.add_effect(my_fluents[literal.fluent](*literal_arguments), literal.value)

                complete_model.add_action(my_action)
                version_num += 1

    return complete_model




def generate_complete_model_grounded(
    all_fluents:   list,
    all_actions:   list,
    all_constants: list,
    U_pre:         dict[str, set[frozenset]],
    L_eff:         dict[str, set[frozenset]],
    U_eff:         dict[str, set[frozenset]],
) -> Problem:
    """
    Grounded export: same ``(hp, he)`` pairs as ``generate_complete_model``
    (only ``hp ∈ U_pre``), with concrete objects and no inequality preconditions.
    Empty-``he`` pairs are omitted.

    For **pre interval × eff interval**, use ``generate_true_full_version_space_grounded``.
    For the grounded **U-border**, use ``generate_complete_border_grounded``.
    """
    complete_model = Problem("Version Space Ground Action Model")

    for fluent in all_fluents:
        complete_model.add_fluent(fluent)

    my_fluents   = {fluent.name: fluent for fluent in all_fluents}
    my_constants = {constant.name: constant for constant in all_constants}

    for action in all_actions:
        version_num = 1
        le_raw = next(iter(L_eff[action.name]))
        ue_raw = next(iter(U_eff[action.name]))
        for hp in U_pre[action.name]:
            heL = le_raw - hp
            heU = ue_raw - hp
            V_eff = generate_version_space_effects(heL, heU)

            for he in V_eff:
                if not he:
                    continue
                my_action = InstantaneousAction(f"{action.name}_version{version_num}")

                for literal in hp:                                                   
                    literal_arguments = [my_constants[obj_name] for obj_name in literal.arguments]
                    if literal.value:
                        my_action.add_precondition(my_fluents[literal.fluent](*literal_arguments))
                    else:
                        my_action.add_precondition(Not(my_fluents[literal.fluent](*literal_arguments)))

                for literal in he:                                                   
                    literal_arguments = [my_constants[obj_name] for obj_name in literal.arguments]
                    my_action.add_effect(my_fluents[literal.fluent](*literal_arguments), literal.value)

                complete_model.add_action(my_action)
                version_num += 1

    return complete_model


def generate_true_full_version_space(
    all_fluents: list,
    all_actions: list,
    L_pre: dict[str, set[frozenset]],
    U_pre: dict[str, set[frozenset]],
    L_eff: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
) -> Problem:
    """
    Lifted **true** full version-space materialization: **pre interval × eff interval**.

    For each action, enumerates **every** ``hp`` with
    ``∃ ℓ ∈ L_pre, u ∈ U_pre : u ⊆ hp ⊆ ℓ`` via
    ``precondition_interval_hypotheses``, then every ``he`` in
    ``generate_version_space_effects(L_eff - hp, U_eff - hp)``.

    Use this for **exhaustive checks** or evaluation cross-validation on small
    domains. Prefer ``generate_complete_model`` when you only need
    hypotheses stored in ``U_pre``; this function can have **many more** actions
    (exponential in ``|ℓ \\ u|`` for preconditions times effect gap).

    Empty-``he`` rows are omitted (no dummy-noop).

    Problem name: ``True Full Version Space Action Model``.
    """
    problem = Problem("True Full Version Space Action Model")

    for fluent in all_fluents:
        problem.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}

    for action in all_actions:
        name = action.name
        if (
            not L_pre.get(name)
            or not U_pre.get(name)
            or not L_eff.get(name)
            or not U_eff.get(name)
        ):
            continue

        V_pre = precondition_interval_hypotheses(L_pre[name], U_pre[name])
        le_raw = next(iter(L_eff[name]))
        ue_raw = next(iter(U_eff[name]))
        version_num = 1

        for hp in V_pre:
            heL = le_raw - hp
            heU = ue_raw - hp
            V_eff = generate_version_space_effects(heL, heU)

            for he in V_eff:
                if not he:
                    continue
                params_to_pass = {par.name: par.type for par in action.parameters}
                my_action = InstantaneousAction(
                    f"{action.name}_version{version_num}",
                    **params_to_pass,
                )
                my_pars = {
                    par.name: my_action.parameter(par.name) for par in action.parameters
                }

                for pair in combinations(my_action.parameters, 2):
                    if pair[0].type == pair[1].type:
                        my_action.add_precondition(Not(Equals(pair[0], pair[1])))

                for literal in hp:
                    literal_arguments = [
                        my_pars[lit_par] for lit_par in literal.arguments
                    ]
                    if literal.value:
                        my_action.add_precondition(
                            my_fluents[literal.fluent](*literal_arguments)
                        )
                    else:
                        my_action.add_precondition(
                            Not(my_fluents[literal.fluent](*literal_arguments))
                        )

                for literal in he:
                    literal_arguments = [
                        my_pars[lit_par] for lit_par in literal.arguments
                    ]
                    my_action.add_effect(
                        my_fluents[literal.fluent](*literal_arguments),
                        literal.value,
                    )

                problem.add_action(my_action)
                version_num += 1

    return problem


def generate_true_full_version_space_grounded(
    all_fluents: list,
    all_actions: list,
    all_constants: list,
    L_pre: dict[str, set[frozenset]],
    U_pre: dict[str, set[frozenset]],
    L_eff: dict[str, set[frozenset]],
    U_eff: dict[str, set[frozenset]],
) -> Problem:
    """
    Grounded **true** full version space (same kept ``(hp, he)`` pairs as
    ``generate_true_full_version_space``; empty ``he`` omitted).
    """
    problem = Problem("True Full Version Space Ground Action Model")

    for fluent in all_fluents:
        problem.add_fluent(fluent)

    my_fluents = {fluent.name: fluent for fluent in all_fluents}
    my_constants = {constant.name: constant for constant in all_constants}

    for action in all_actions:
        name = action.name
        if (
            not L_pre.get(name)
            or not U_pre.get(name)
            or not L_eff.get(name)
            or not U_eff.get(name)
        ):
            continue

        V_pre = precondition_interval_hypotheses(L_pre[name], U_pre[name])
        le_raw = next(iter(L_eff[name]))
        ue_raw = next(iter(U_eff[name]))
        version_num = 1

        for hp in V_pre:
            heL = le_raw - hp
            heU = ue_raw - hp
            V_eff = generate_version_space_effects(heL, heU)

            for he in V_eff:
                if not he:
                    continue
                my_action = InstantaneousAction(f"{action.name}_version{version_num}")

                for literal in hp:
                    literal_arguments = [
                        my_constants[obj_name] for obj_name in literal.arguments
                    ]
                    if literal.value:
                        my_action.add_precondition(
                            my_fluents[literal.fluent](*literal_arguments)
                        )
                    else:
                        my_action.add_precondition(
                            Not(my_fluents[literal.fluent](*literal_arguments))
                        )

                for literal in he:
                    literal_arguments = [
                        my_constants[obj_name] for obj_name in literal.arguments
                    ]
                    my_action.add_effect(
                        my_fluents[literal.fluent](*literal_arguments), literal.value
                    )

                problem.add_action(my_action)
                version_num += 1

    return problem
