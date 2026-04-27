"""
Smoke tests for the ascal package.

These tests build a tiny Unified Planning domain in-memory (no PDDL files,
no planner required) and exercise the public entry points enough to catch
packaging breakage, wrong imports, and accidental API renames.
"""

from unified_planning.shortcuts import (
    BoolType,
    Fluent,
    InstantaneousAction,
    UserType,
)


def _tiny_domain():
    """Return (all_fluents, all_actions, static_fluents) for a minimal
    move(src, dst) domain over a single Location UserType."""
    Location = UserType("Location")

    at = Fluent("at", BoolType(), loc=Location)
    clear = Fluent("clear", BoolType(), loc=Location)

    move = InstantaneousAction("move", src=Location, dst=Location)
    src = move.parameter("src")
    dst = move.parameter("dst")
    move.add_precondition(at(src))
    move.add_precondition(clear(dst))
    move.add_effect(at(dst), True)
    move.add_effect(at(src), False)
    move.add_effect(clear(src), True)
    move.add_effect(clear(dst), False)

    return [at, clear], [move], []


def test_public_imports():
    """All top-level symbols advertised in README must be importable."""
    from ascal import (
        Action,
        Demonstration,
        Learner,
        Literal,
        State,
    )

    assert Learner is not None
    assert Literal is not None
    assert State is not None
    assert Action is not None
    assert Demonstration is not None


def test_dunder_all_is_exhaustive():
    """Every name in __all__ must actually resolve on the ascal module."""
    import ascal

    missing = [name for name in ascal.__all__ if not hasattr(ascal, name)]
    assert not missing, f"Names in __all__ not exported: {missing}"


def test_learner_construction():
    """Learner should initialize version-space bounds for every action."""
    from ascal import Learner

    fluents, actions, static = _tiny_domain()
    learner = Learner(fluents, actions, static)

    assert learner.demo_count == 0
    vs = learner.version_space_size
    assert isinstance(vs, dict)
    assert set(vs.keys()) == {"move"}
    assert "converged" in vs["move"]


def test_learner_repr():
    from ascal import Learner

    fluents, actions, static = _tiny_domain()
    learner = Learner(fluents, actions, static)
    text = repr(learner)
    assert "Learner(" in text
    assert "actions=1" in text
    assert "demos=0" in text


def test_sound_model_returns_up_problem():
    """The sound (L-boundary) model should always build a Unified Planning
    Problem; with no demonstrations the L-boundary is the contradictory
    most-specific hypothesis so the resulting problem has zero actions,
    which is itself valid UP output."""
    from unified_planning.model import Problem

    from ascal import Learner

    fluents, actions, static = _tiny_domain()
    learner = Learner(fluents, actions, static)

    problem = learner.sound_model()
    assert isinstance(problem, Problem)


def test_raw_upper_bound_returns_up_problem():
    from unified_planning.model import Problem

    from ascal import Learner

    fluents, actions, static = _tiny_domain()
    learner = Learner(fluents, actions, static)

    problem = learner.raw_upper_bound()
    assert isinstance(problem, Problem)


def test_update_accepts_demonstration():
    """Feed one synthetic lifted demonstration and check update() returns a bool
    and increments the demo counter."""
    from ascal import Action, Demonstration, Learner, Literal, State

    fluents, actions, static = _tiny_domain()
    learner = Learner(fluents, actions, static)

    pre = State(
        frozenset(
            {
                Literal("at", ("src",), True),
                Literal("at", ("dst",), False),
                Literal("clear", ("src",), False),
                Literal("clear", ("dst",), True),
            }
        )
    )
    post = State(
        frozenset(
            {
                Literal("at", ("src",), False),
                Literal("at", ("dst",), True),
                Literal("clear", ("src",), True),
                Literal("clear", ("dst",), False),
            }
        )
    )
    demo = Demonstration(
        pre_state=pre,
        action=Action("move", ("src", "dst")),
        post_state=post,
    )

    ok = learner.update(demo)
    assert isinstance(ok, bool)
    assert learner.demo_count == 1
