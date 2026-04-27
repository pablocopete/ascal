"""
Unified Planning (UP) bridge for ASCAL demo generation and state lifting.

This module translates between Unified Planning (UP) framework objects and
the project's Literal/State/Demonstration types, and implements the lifting
step that converts grounded demonstrations into the lifted (parameter-name)
representation expected by the ASCAL version-space operators.

Key functions
-------------
``generate_transitions_from_problem``
    Solve a planning problem, simulate the plan, and collect positive
    (plan-step) and negative (failed-grounding) demonstrations.

``generate_lifted_demonstrations_from_problem``
    Same pipeline as manual notebook demo generation: plan, simulate, optional
    sampled negative groundings, then emit **lifted** demonstrations (schema
    parameter names). Supports ``max_neg_per_step`` and
    ``max_check_per_action`` for large domains.

``lift_demonstrations``
    Lift a **list** of grounded demonstrations in order (no deduplication).
    Prefer this over ``lift_transitions`` when duplicates must be preserved.

``lift_transitions``
    Replace concrete object names with action parameter names in every
    Demonstration, deduplicating by structural equality.

``lift_transitions_with_map``
    Like ``lift_transitions`` but also returns a lifted→grounded mapping
    (useful for trajectory-file generation).

``generate_all_lifted_literals``
    Enumerate every possible lifted Literal for a given action + fluent set.

``generate_all_ground_literals``
    Enumerate every grounded Literal (True/False) for a grounded problem.
"""
from unified_planning.shortcuts import *
import unified_planning
import random
from itertools import product
from typing import Any
from ascal.models import Literal, State, Action, Demonstration
from ascal.logger import get_logger

logger = get_logger(__name__)


def clear_fluent_value_cache() -> None:
    """No-op kept for backward compatibility."""
    pass


def get_fluent_value(fluent: Any, state: Any) -> bool | None:
    """
    Resolve fluent value by walking the UP state's _father chain.

    Note: caching was removed because UP's SequentialSimulator mutates
    state objects in-place (flattening the _father chain), which silently
    invalidates cached lookups and produces wrong fluent values at later
    plan steps.
    """
    current = state
    while current is not None:
        value_found = current._values.get(fluent, None)
        if value_found is not None:
            return value_found._content.payload
        current = current._father
    return None

def _build_literal_descriptors(all_literals: list) -> list[tuple]:
    """
    Precompute metadata for each literal once
    """
    descriptors = []
    for lit in all_literals:
        pred_name = lit.fluent().name
        arg_names = tuple(arg._content.payload.name for arg in lit.args)
        descriptors.append((lit, pred_name, arg_names))
    return descriptors

def _state_to_signature(state, literal_descriptors: list[tuple]) -> frozenset:
    """
    Convert a simulator state into the project state representation:
      frozenset of (predicate_name, arg_tuple, value)

    Why frozenset:
    - Immutable + hashable (useful if later indexing/deduplicating states).
    - Still represents an unordered logical state (like a set of facts).
    """
    return frozenset(
        (pred_name, arg_names, bool(v) if (v := get_fluent_value(lit, state)) is not None else False)
        for lit, pred_name, arg_names in literal_descriptors
    )

# Old implementation, might be removed in the future, not sure yet (may be needed for FAMA comparison)
def generate_transitions_from_problem(
    problem: Any,
    generate_failures: bool = True,
    planning_problem: Any | None = None,
    planner_name: str | None = None,
) -> tuple[list[Demonstration], list[Demonstration]]:
    """
    Generate transitions by solving the problem with a planner and simulating
    the resulting plan step by step.

    Args:
        problem:          The ASCAL learning problem (domain.pddl) — used for
                          simulation, failure grounding, and state signatures.
        generate_failures: Whether to record non-applicable groundings as negative
                          demonstrations.
        planning_problem: Optional simpler problem (domain_original.pddl) to use
                          for planning only. Useful on Windows where Fast Downward
                          is unavailable and pyperplan cannot handle equality/negative
                          conditions in the ASCAL domain.
                          When provided, plan steps are padded with dummy objects to
                          match problem's action signatures before simulation.
        planner_name:     Optional planner name to use (e.g. 'pyperplan', 'fast-downward').
                          Defaults to auto-selection based on problem_kind.

    Key optimizations vs original:
    1) Freeze all_literals into a list once → avoids repeated dict-view iteration.
    2) Precompute literal_descriptors once → avoids rebuilding predicate names
       and argument names inside the hot loop (same pattern as generate_transition_relation).
    3) Precompute action_groundings once → matching_objects + product computed
       once per action, not once per plan step per action.
    4) Use _state_to_signature for consistent, cache-friendly state representation.
    5) Removed the `break` after failure recording — it was silently dropping
       all failures after the first one per action per step.
       If the original single-failure behavior was intentional, pass
       generate_failures='one_per_action' and restore it explicitly.
    """
    transitions = []
    failures = []

    # 1) Freeze once — dict_keys is a live view, unsafe to iterate repeatedly
    all_literals = list(problem.initial_values.keys())
    all_objects = list(problem.all_objects)

    # 2) Precompute descriptor tuples (pred_name, arg_names) for each literal
    #    Avoids O(literals) string extraction on every transition recorded.
    literal_descriptors = _build_literal_descriptors(all_literals)

    # 3) Precompute groundings — types don't change across plan steps
    #    Uses subtype check (is_subtype) consistent with original failure loop.
    action_groundings_failures = {} #{action: list of valid groundings}
    if generate_failures:
        for a in problem.actions:
            matching_objects = [
                [o for o in all_objects if o.type.is_subtype(a.parameters[i].type)]
                for i in range(len(a.parameters))
            ] #[action][parameter_index][object_index]
            action_groundings_failures[a] = [
                args for args in product(*matching_objects)
                if len(set(args)) == len(args)
            ] # [action][instantiation_index] every possible intantation with arg1!=arg2!=arg3...

    # 4) Choose which problem to plan with
    #    If planning_problem given (e.g. domain_original) use that; else use problem itself.
    plan_with = planning_problem if planning_problem is not None else problem

    planner_kwargs = {"name": planner_name} if planner_name else {"problem_kind": plan_with.kind}
    with OneshotPlanner(**planner_kwargs) as planner:
        result = planner.solve(plan_with)
        if result.status != unified_planning.engines.PlanGenerationResultStatus.SOLVED_SATISFICING:
            logger.warning("Planner failed to find a solution.")
            return transitions, failures
        logger.info("Plan: %s", result.plan)

    # 5) If using a different planning domain, build a map from action name → ASCAL action
    #    so we can pad dummy parameters when applying steps to the ASCAL simulator.
    ascal_action_map: dict = {a.name: a for a in problem.actions}

    with SequentialSimulator(problem=problem) as simulator:
        pre_state = simulator.get_initial_state()

        for action_instance in result.plan.actions:
            pre_signature = _state_to_signature(pre_state, literal_descriptors)

            # 6) Generate failures for ALL non-applicable groundings at this step
            #    Original code had a `break` that silently stopped after the first
            #    failure per action — removed here for correctness.
            if generate_failures:
                for a, valid_args in action_groundings_failures.items():
                    for args in valid_args:
                        if not simulator.is_applicable(pre_state, a, args):
                            failures.append(Demonstration(pre_state = _signature_to_state(pre_signature), action = Action(a.name, tuple(arg.name for arg in args)), post_state = None))

            # 7) Build the concrete args to apply in the ASCAL simulator.
            #    When planning_problem is given, the plan step may have fewer params
            #    (e.g. pickup(b1) vs ASCAL pickup(b1,b2,b3)).
            #    Pad with the first unused objects to satisfy uniqueness.
            orig_args = tuple(par.object() for par in action_instance.actual_parameters)
            if planning_problem is not None:
                ascal_action = ascal_action_map[action_instance.action.name]
                n_need = len(ascal_action.parameters)
                if len(orig_args) < n_need:
                    used = set(orig_args)
                    extra = [o for o in all_objects if o not in used]
                    padded = list(orig_args) + extra
                    sim_args = tuple(padded[:n_need])
                else:
                    sim_args = orig_args
                post_state = simulator.apply(pre_state, ascal_action, sim_args)
            else:
                ascal_action = action_instance.action
                sim_args = orig_args
                post_state = simulator.apply(pre_state, action_instance)

            if post_state is None:
                logger.error("Error applying: %s %s", ascal_action.name, sim_args)
                break

            post_signature = _state_to_signature(post_state, literal_descriptors)

            transitions.append(Demonstration(
                pre_state  = _signature_to_state(pre_signature),
                action     = Action(ascal_action.name, tuple(arg.name for arg in sim_args)),
                post_state = _signature_to_state(post_signature)
            ))
            pre_state = post_state

    return transitions, failures


def _lift_state(state: State, action_args_set: set, map_arg_to_par: dict) -> State:
    """Replace concrete argument names with action parameter names in one State."""
    lifted = set()
    for literal in state.literals:
        if (set(literal.arguments).issubset(action_args_set) and
                len(set(literal.arguments)) == len(literal.arguments)):
            lifted_args = tuple(map_arg_to_par[a] for a in literal.arguments)
            lifted.add(Literal(literal.fluent, lifted_args, literal.value))
    return State(frozenset(lifted))


# Actual implementation for ASCAL learning loop
def generate_lifted_demonstrations_from_problem(
    problem: Any,
    *,
    max_neg_per_step: int = 50,
    max_check_per_action: int | None = None,
    seed: int = 0,
    planner_name: str | None = None,
    verbose: bool = False,
) -> tuple[list[Demonstration], list[Demonstration]]:
    """
    Generate **lifted** positive and negative demonstrations from one UP problem.

    This matches the evaluation notebooks: solve the problem, walk the plan in
    the simulator, record inapplicable groundings as negatives (optionally
    sampling groundings and capping negatives per step for large domains), then
    lift states to schema parameter names.

    Args:
        problem: UP ``Problem`` (domain + instance) used for planning and
            simulation.
        max_neg_per_step: Maximum negative demos kept per plan step after
            filtering. Use ``0`` or any falsy behaviour: if 0, no cap is applied
            (same as the notebook idiom ``if max_neg_per_step and ...``).
        max_check_per_action: Maximum groundings sampled per action per step
            before calling ``is_applicable``. ``None`` checks all groundings.
            ``0`` skips the negative loop for that step (positives only).
        seed: RNG seed for sampling.
        planner_name: Optional planner name; default uses ``problem.kind``.
        verbose: If ``True``, ``print`` the plan and demo counts (notebook UX).

    Returns:
        (positives, negatives) as lists of lifted :class:`Demonstration`.
    """
    rng = random.Random(seed)
    all_literals = list(problem.initial_values.keys())
    all_objects = list(problem.all_objects)
    literal_desc = _build_literal_descriptors(all_literals)
    action_pars = {a.name: tuple(p.name for p in a.parameters) for a in problem.actions}

    action_groundings: dict[Any, list] = {}
    for a in problem.actions:
        matching = [
            [o for o in all_objects if o.type.is_subtype(a.parameters[i].type)]
            for i in range(len(a.parameters))
        ]
        action_groundings[a] = [
            args for args in product(*matching) if len(set(args)) == len(args)
        ]

    planner_kwargs = {"name": planner_name} if planner_name else {"problem_kind": problem.kind}
    with OneshotPlanner(**planner_kwargs) as planner:
        result = planner.solve(problem)
    if result.status != unified_planning.engines.PlanGenerationResultStatus.SOLVED_SATISFICING:
        if verbose:
            print("⚠ Problem unsolvable — no demonstrations generated.")
        return [], []

    if verbose:
        print(f"Plan: {[str(a) for a in result.plan.actions]}")

    pos_list: list[Demonstration] = []
    neg_list: list[Demonstration] = []

    with SequentialSimulator(problem=problem) as sim:
        pre = sim.get_initial_state()
        for ai in result.plan.actions:
            pre_sig = _state_to_signature(pre, literal_desc)
            step_negs: list[Demonstration] = []
            for a, grds in action_groundings.items():
                pars = action_pars[a.name]
                if max_check_per_action is None:
                    grds_to_check = grds
                else:
                    grds_to_check = rng.sample(
                        grds, min(len(grds), max_check_per_action)
                    )
                for args in grds_to_check:
                    if not sim.is_applicable(pre, a, args):
                        names = tuple(o.name for o in args)
                        m = {names[i]: pars[i] for i in range(len(names))}
                        grounded_pre = _signature_to_state(pre_sig)
                        lifted_pre = _lift_state(grounded_pre, set(names), m)
                        step_negs.append(
                            Demonstration(
                                pre_state=lifted_pre,
                                action=Action(a.name, pars),
                                post_state=None,
                            )
                        )
            if max_neg_per_step and len(step_negs) > max_neg_per_step:
                step_negs = rng.sample(step_negs, max_neg_per_step)
            neg_list.extend(step_negs)

            va = ai.action
            orig_args = tuple(p.object() for p in ai.actual_parameters)
            post = sim.apply(pre, ai)
            if post is None:
                break
            post_sig = _state_to_signature(post, literal_desc)
            names = tuple(o.name for o in orig_args)
            pars = action_pars[va.name]
            m = {names[i]: pars[i] for i in range(len(names))}
            g_pre = _signature_to_state(pre_sig)
            g_post = _signature_to_state(post_sig)
            pos_list.append(
                Demonstration(
                    pre_state=_lift_state(g_pre, set(names), m),
                    action=Action(va.name, pars),
                    post_state=_lift_state(g_post, set(names), m),
                )
            )
            pre = post

    if verbose:
        print(f"Generated: {len(pos_list)} positive, {len(neg_list)} negative")
    return pos_list, neg_list


def signature_to_state(signature: frozenset) -> State:
    """Convert a state signature (from :func:`state_to_signature`) to grounded :class:`State`."""
    return _signature_to_state(signature)


def state_to_signature(state: Any, literal_descriptors: list[tuple]) -> frozenset:
    """Public alias for :func:`_state_to_signature` (UP state → fact signature)."""
    return _state_to_signature(state, literal_descriptors)


def build_literal_descriptors(all_literals: list) -> list[tuple]:
    """Public alias for :func:`_build_literal_descriptors`."""
    return _build_literal_descriptors(all_literals)


def lift_demonstrations(
    demonstrations: list[Demonstration],
    all_actions: list,
) -> list[Demonstration]:
    """
    Lift grounded demonstrations **in input order** (no deduplication).

    Use this when duplicates must be preserved (e.g. operator-tracing
    notebooks). For a unique set of lifted demos, use :func:`lift_transitions`.
    """
    action_pars_dict = {a.name: tuple(par.name for par in a.parameters) for a in all_actions}
    result: list[Demonstration] = []
    for demonstration in demonstrations:
        action_name = demonstration.action.name
        action_pars = action_pars_dict[action_name]
        action_args = list(demonstration.action.args)
        action_args_set = set(action_args)
        map_arg_to_par = {action_args[i]: action_pars[i] for i in range(len(action_args))}

        if len(set(action_args)) != len(action_args):
            logger.warning("Action %s has repeated arguments — skipping", action_name)
            continue

        lifted_pre = _lift_state(demonstration.pre_state, action_args_set, map_arg_to_par)
        lifted_post = (
            _lift_state(demonstration.post_state, action_args_set, map_arg_to_par)
            if demonstration.is_positive
            else None
        )
        result.append(
            Demonstration(
                pre_state=lifted_pre,
                action=Action(action_name, action_pars),
                post_state=lifted_post,
            )
        )
    return result


def lift_transitions(transitions: list[Demonstration], all_actions: list) -> set[Demonstration]:
    """
    Convert grounded transitions to lifted transitions by replacing
    concrete object names with action parameter names.

    Optimizations vs original:
    1) action_args built as list then converted to set once → O(1) subset checks.
    2) Duplicate pre/post lifting logic extracted to _lift_state helper.
    3) list(pre_state) / list(post_state) removed → no unnecessary copies.
    4) NARG + range(NARG) replaced by direct generator over literal_args.
    5) Named unpacking instead of magic t[0], t[1], t[2] indexing.
    """
    # Precompute once: action_name → tuple of parameter names
    action_pars_dict = {a.name: tuple(par.name for par in a.parameters)
                        for a in all_actions}

    lifted_transitions = set()
    for demonstration in transitions:
        action_name = demonstration.action.name
        action_pars = action_pars_dict[action_name]
        action_args = list(demonstration.action.args)   # already strings
        action_args_set = set(action_args)
        map_arg_to_par = {action_args[i]: action_pars[i] for i in range(len(action_args))}

        if len(set(action_args)) != len(action_args):
            logger.warning("Action %s has repeated arguments — skipping", action_name)
            continue

        lifted_pre  = _lift_state(demonstration.pre_state, action_args_set, map_arg_to_par)

        if demonstration.is_positive:
            lifted_post = _lift_state(demonstration.post_state, action_args_set, map_arg_to_par)
        else:
            lifted_post = None

        lifted_transitions.add(Demonstration(
            pre_state  = lifted_pre,
            action     = Action(action_name, action_pars),
            post_state = lifted_post,
        ))

    logger.info("From %d transitions to %d lifted transitions",
                len(transitions), len(lifted_transitions))      

    return lifted_transitions


def lift_transitions_with_map(
    transitions: list[Demonstration],
    all_actions: list,
) -> tuple[set[Demonstration], dict[Demonstration, Demonstration]]:
    """
    Like lift_transitions(), but also returns a mapping from each lifted
    Demonstration to one representative grounded Demonstration.

    Used by FAMA evaluation to write trajectory files, which need concrete
    object names from the grounded transition.

    Args:
        transitions:  list of grounded Demonstration objects
                      as returned by generate_transitions_from_problem()[0]
        all_actions:  list of UP Action objects (for parameter name lookup)

    Returns:
        lifted:             set[Demonstration] — same as lift_transitions()
        lifted_to_grounded: dict[Demonstration, Demonstration]
                            maps each lifted Demonstration to its grounded
                            source (last grounded seen wins on collision)
    """
    action_pars_dict = {a.name: tuple(par.name for par in a.parameters)
                        for a in all_actions}

    lifted_set: set[Demonstration] = set()
    lifted_to_grounded: dict[Demonstration, Demonstration] = {}

    for demonstration in transitions:
        action_name = demonstration.action.name
        action_pars = action_pars_dict[action_name]
        action_args = list(demonstration.action.args)  # already strings
        action_args_set = set(action_args)
        map_arg_to_par = {action_args[i]: action_pars[i]
                          for i in range(len(action_args))}

        if len(set(action_args)) != len(action_args):
            logger.warning("Action %s has repeated arguments — skipping", action_name)
            continue

        lifted_pre  = _lift_state(demonstration.pre_state, action_args_set, map_arg_to_par)
        lifted_post = (_lift_state(demonstration.post_state, action_args_set, map_arg_to_par)
                       if demonstration.is_positive else None)

        lifted_demo = Demonstration(
            pre_state  = lifted_pre,
            action     = Action(action_name, action_pars),
            post_state = lifted_post,
        )

        lifted_set.add(lifted_demo)
        lifted_to_grounded[lifted_demo] = demonstration  

    logger.info("lift_transitions_with_map: %d grounded → %d lifted",
                len(transitions), len(lifted_set))

    return lifted_set, lifted_to_grounded

def transitions_to_demonstrations(
    lifted_transitions: set[Demonstration],
    failures: list[Demonstration],
) -> list[Demonstration]:
    """
    Combine lifted transitions and failures into a single demonstration list
    ready for run_ASCAL_iteration().

    Returns:
        list[Demonstration] — positives first, then negatives
    """
    return list(lifted_transitions) + failures

def generate_all_lifted_literals(action: Any, all_fluents: list) -> set[Literal]:
    """
    Generate all possible lifted literals for a given action.

    A lifted literal is a tuple (fluent_name, parameter_tuple, bool_value)
    where parameter_tuple contains action parameter names (not concrete objects).

    Example:
        action: move(x:block, y:block)
        fluent: on(block, block)
        → ("on", ("x","y"), True), ("on", ("x","y"), False),
          ("on", ("y","x"), True), ("on", ("y","x"), False)

        where "x" and "y" are object types
    Optimizations vs original:
    1) par_ancestors precomputed once per parameter → avoids consuming the
       generator twice (once for action_types, once for type_to_par).
    2) type_to_par uses par_ancestors instead of calling is_subtype() →
       is_subtype() internally walks the ancestor chain again, which we
       already have stored.
    3) fluent_signature_types precomputed once per fluent → avoids rebuilding
       the set inside the action loop if this function is called multiple times.
    4) set([...]) → set comprehension {...} → no intermediate list.
    5) product([fluent.name], matches, [True, False]) replaced by explicit
       generator → product over a singleton list is wasteful.
    6) generated_literals built as a set from the start → no .union() call
       creating intermediate sets.
    """

    # 1) Precompute ancestor sets per parameter — avoids consuming the
    #    generator multiple times (ancestors is a generator, not a set)
    #    Original called par.type.ancestors once for action_types and then
    #    implicitly again inside type_to_par via is_subtype()
    par_ancestors = {par: set(par.type.ancestors) for par in action.parameters} #key: parameter, value: type and subtypes

    # 2) Build action_types from already-computed ancestor sets
    #    set().union(*...) is cleaner than iterating and calling update()
    action_types = set().union(*par_ancestors.values()) # all types included in the action

    # 3) Build type_to_par using par_ancestors instead of is_subtype()
    #    is_subtype() walks the ancestor chain again — we already have it
    #    Original: par.type.is_subtype(t) → O(depth) per parameter per type
    #    Optimized: t in par_ancestors[par] → O(1) per parameter per type
    type_to_par = {
        t: {par.name for par in action.parameters if t in par_ancestors[par]}
        for t in action_types
    } #output: {"robot_type": {"robot1", "robot2"},
    #            "object_type": "robot1", "robot2"}

    generated_literals = set()

    for fluent in all_fluents:
        # 4) Check if all fluent argument types are covered by action_types
        #    set comprehension instead of set([list comprehension])
        fluent_arg_types = {fpar.type for fpar in fluent.signature}

        if not fluent_arg_types.issubset(action_types):
            continue  # skip fluents with incompatible types early

        # 5) Build matching parameter sets for each fluent argument
        #    Each position gets the set of action parameters whose type
        #    covers that fluent argument type
        matching_pars = [type_to_par[fpar.type] for fpar in fluent.signature] #[{robot1, robot2}, {loc1, loc2, loc3}]

        # 6) Generate all combinations and filter repeated parameters
        #    e.g. on(block,block) + move(x,y) → [("x","y"), ("y","x")]
        #    ("x","x") excluded by len(set(match)) == len(match)
        valid_matches = [
            match for match in product(*matching_pars)
            if len(set(match)) == len(match)
        ] #([robot1, loc1], [robot1, loc2], [robot1, loc3])

        # 7) Add both True and False versions of each lifted literal
        #    Explicit generator avoids product() over a singleton [fluent.name]
        for match in valid_matches:
            generated_literals.add(Literal(fluent.name, match, True))
            generated_literals.add(Literal(fluent.name, match, False))

    return generated_literals


def generate_all_ground_literals(grounded_fluents: list) -> set:
    """
    Generate all possible grounded literals (True and False) from the
    grounded fluents of a problem.
    """
    generated_literals = set()
    for fluent in grounded_fluents:
        pred_name = fluent.fluent().name                                   # stored once
        literal_args = tuple(arg.constant_value().name for arg in fluent.args)  # generator
        generated_literals.add(Literal(pred_name, literal_args, True))
        generated_literals.add(Literal(pred_name, literal_args, False))
    return generated_literals

def _signature_to_state(signature:frozenset) -> State:
    """Convert a frozenset of (name, args, value) tuples to a State object."""
    return State(frozenset(Literal(name, args, value) for name, args, value in signature))