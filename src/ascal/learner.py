"""
High-level stateful wrapper for the ASCAL action-model learner.

The ``Learner`` class is the recommended entry point for most users.
It manages the version-space boundaries internally and exposes a clean API:

    learner = Learner(all_fluents, all_actions, static_fluents)

    for demo in demonstrations:
        learner.update(demo)

    f1_s, f1_c, p_s, r_s, p_c, r_c = learner.evaluate(test_pos, test_neg)
    sound_problem = learner.sound_model()
    vs_problem = learner.version_space()
    border_problem = learner.raw_upper_bound()

See ``evaluate``, ``evaluate_repr``, and ``evaluate_gated`` for the three
available evaluation strategies.
"""
from ascal.models import Demonstration
from ascal.algorithm import (
    ASCAL_initialization,
    run_ASCAL_iteration,
    generate_sound_action_model,
    generate_sound_ground_action_model,
    generate_complete_border,
    generate_complete_border_grounded,
    generate_complete_border_consistent,
    generate_complete_border_consistent_grounded,
    generate_complete_border_consistent_split,
    generate_complete_border_consistent_split_grounded,
    generate_complete_model as generate_version_space_model,
    generate_complete_model_grounded as generate_version_space_model_grounded,
)
from ascal.evaluation import (
    compute_version_space_size,
    evaluate_detailed,
    evaluate_representative,
    evaluate_convergence_gated,
)
from ascal.logger import get_logger

logger = get_logger(__name__)


class Learner:
    """Stateful ASCAL learner that wraps version space initialization,
    incremental learning, model generation, and evaluation.

    Usage:
        learner = Learner(all_fluents, all_actions, static_fluents)

        for demo in initial_demos:
            learner.update(demo)

        learner.update_batch(remaining_demos)

        f1_s, f1_c, p_s, r_s, p_c, r_c = learner.evaluate(test_pos, test_neg)

        sound_problem = learner.sound_model()
        vs_problem = learner.version_space()
        border_problem = learner.raw_upper_bound()
    """

    def __init__(
        self,
        all_fluents: list,
        all_actions: list,
        static_fluents: list,
        *,
        ground: bool = False,
        all_constants: list | None = None,
    ) -> None:
        """Initialize version space bounds for all actions.

        Args:
            all_fluents:    list of UP Fluent objects from the domain.
            all_actions:    list of UP Action objects from the domain.
            static_fluents: fluents that never change (used to exclude from effects).
            ground:         if True, use grounded literals instead of lifted.
            all_constants:  list of UP Object constants — required for grounded
                            model generation (``sound_model`` / ``version_space`` /
                            ``complete_border_model`` with ``ground=True``).
        """
        self.all_fluents = all_fluents
        self.all_actions = all_actions
        self.all_constants = all_constants
        self._ground = ground
        self._demo_count = 0
        self.collapsed_actions: set[str] = set()

        self.L_pre, self.U_pre, self.L_eff, self.U_eff = ASCAL_initialization(
            all_fluents,
            all_actions,
            static_fluents,
            ground=ground,
        )

    def update(self, demonstration: Demonstration) -> bool:
        """Process a single demonstration and update version space bounds.

        Returns True if the version space is healthy, False if the action's
        version space collapsed (L or U became empty for effects).
        """
        action_name = demonstration.action.name
        run_ASCAL_iteration(
            self.L_pre,
            self.U_pre,
            self.L_eff,
            self.U_eff,
            demonstration,
        )
        self._demo_count += 1

        if len(self.L_eff[action_name]) == 0 or len(self.U_eff[action_name]) == 0:
            if action_name not in self.collapsed_actions:
                self.collapsed_actions.add(action_name)
                logger.warning(
                    "Version space collapsed for '%s' at demo %d "
                    "(L_eff=%d, U_eff=%d)",
                    action_name,
                    self._demo_count,
                    len(self.L_eff[action_name]),
                    len(self.U_eff[action_name]),
                )
            return False
        return True

    def update_batch(self, demonstrations: list[Demonstration]) -> int:
        """Process a sequence of demonstrations.

        Returns the number of demonstrations that caused a collapse (0 = all OK).
        """
        collapses = 0
        for demo in demonstrations:
            if not self.update(demo):
                collapses += 1
        return collapses

    def evaluate(
        self,
        positives: list[Demonstration],
        negatives: list[Demonstration],
    ) -> tuple[float, float, float, float, float, float]:
        """Evaluate precision, recall, and F1 for sound and complete models.

        Returns:
            (f1_sound, f1_complete,
             precision_sound, recall_sound,
             precision_complete, recall_complete)
        """
        return evaluate_detailed(
            positives,
            negatives,
            self.L_pre,
            self.U_pre,
            self.L_eff,
            self.U_eff,
        )

    def evaluate_repr(
        self,
        positives: list[Demonstration],
        negatives: list[Demonstration],
    ) -> tuple[float, float, float, float, float, float, dict]:
        """Evaluate using a single representative hypothesis for the complete model.

        Unlike ``evaluate`` (which uses all hypotheses in U_pre with fractional
        counting for negatives), this method picks the most-general hypothesis
        ``min(U_pre[action], key=len)`` and uses standard binary classification.

        Returns:
            (f1_sound, f1_complete,
             precision_sound, recall_sound,
             precision_complete, recall_complete,
             status)

            ``status`` is a ``dict[action_name -> {'n_hyps': int, 'converged': bool}]``.
            When ``converged=True`` the results are exact and identical to ``evaluate()``.
            When ``converged=False`` the complete-model metrics reflect only the most
            general remaining hypothesis — a conservative bound on the true complete model.
        """
        return evaluate_representative(
            positives,
            negatives,
            self.L_pre,
            self.U_pre,
            self.L_eff,
            self.U_eff,
        )

    def evaluate_gated(
        self,
        positives: list[Demonstration],
        negatives: list[Demonstration],
    ) -> tuple[float, float, float, float, float, float, dict]:
        """Evaluate P/R/F1 only for fully-converged actions.

        Non-converged actions are excluded from all metrics, producing clean
        binary precision/recall suitable for publication.

        Returns:
            (f1_sound, f1_complete,
             precision_sound, recall_sound,
             precision_complete, recall_complete,
             status)

            ``status`` is a ``dict[action_name -> dict]`` with keys
            ``converged``, ``n_hyps``, and per-model P/R/F1 (``None`` when
            the action has not yet converged).
        """
        return evaluate_convergence_gated(
            positives,
            negatives,
            self.L_pre,
            self.U_pre,
            self.L_eff,
            self.U_eff,
        )

    def sound_model(self, ground: bool = False) -> "Problem":  # type: ignore[name-defined]
        """Build a UP Problem with the sound (L-boundary) action model.

        Args:
            ground: if True, build a grounded model (requires all_constants
                    to have been provided at construction time).
        """
        if ground:
            if self.all_constants is None:
                raise ValueError(
                    "Cannot build grounded model: 'all_constants' was not "
                    "provided at construction time."
                )
            return generate_sound_ground_action_model(
                self.all_fluents,
                self.all_actions,
                self.all_constants,
                self.L_pre,
                self.L_eff,
            )
        return generate_sound_action_model(
            self.all_fluents,
            self.all_actions,
            self.L_pre,
            self.L_eff,
        )

    def version_space(self, ground: bool = False) -> "Problem":  # type: ignore[name-defined]
        """Build a UP Problem materialising the full learned version space.

        One UP action per consistent ``(hp, he)`` pair across all ``hp ∈ U_pre``
        and all ``he`` with ``L_eff ⊆ he ⊆ U_eff``.  Can be large (exponential
        in ``|U_eff − L_eff|``); for compact permissive planning use
        ``complete_model`` instead.

        Args:
            ground: if True, build a grounded model (requires ``all_constants``).
        """
        if ground:
            if self.all_constants is None:
                raise ValueError(
                    "Cannot build grounded model: 'all_constants' was not "
                    "provided at construction time."
                )
            return generate_version_space_model_grounded(
                self.all_fluents,
                self.all_actions,
                self.all_constants,
                self.U_pre,
                self.L_eff,
                self.U_eff,
            )
        return generate_version_space_model(
            self.all_fluents,
            self.all_actions,
            self.U_pre,
            self.L_eff,
            self.U_eff,
        )

    def raw_upper_bound(self, ground: bool = False) -> "Problem":  # type: ignore[name-defined]
        """Build a compact U-border UP Problem (one action per ``hp ∈ U_pre``, upper effects only).

        See ``generate_complete_border`` / ``generate_complete_border_grounded``.

        Args:
            ground: if True, build a grounded model (requires ``all_constants``).
        """
        if ground:
            if self.all_constants is None:
                raise ValueError(
                    "Cannot build grounded model: 'all_constants' was not "
                    "provided at construction time."
                )
            return generate_complete_border_grounded(
                self.all_fluents,
                self.all_actions,
                self.all_constants,
                self.U_pre,
                self.U_eff,
            )
        return generate_complete_border(
            self.all_fluents,
            self.all_actions,
            self.U_pre,
            self.U_eff,
        )

    def complete_model_single(self, ground: bool = False) -> "Problem":  # type: ignore[name-defined]
        """Build a compact U-border UP Problem with **non-contradictory** effects per operator.

        Same one-row-per-``hp ∈ U_pre`` layout as ``complete_border_model``, but each
        operator's effects are a maximal subset of ``(U_eff - hp)`` that contains
        ``(L_eff - hp)`` and contains no opposite literals on the same atom.

        See ``generate_complete_border_consistent`` /
        ``generate_complete_border_consistent_grounded``.

        Args:
            ground: if True, build a grounded model (requires ``all_constants``).
        """
        if ground:
            if self.all_constants is None:
                raise ValueError(
                    "Cannot build grounded model: 'all_constants' was not "
                    "provided at construction time."
                )
            return generate_complete_border_consistent_grounded(
                self.all_fluents,
                self.all_actions,
                self.all_constants,
                self.U_pre,
                self.L_eff,
                self.U_eff,
            )
        return generate_complete_border_consistent(
            self.all_fluents,
            self.all_actions,
            self.U_pre,
            self.L_eff,
            self.U_eff,
        )

    def complete_model(
        self,
        ground: bool = False,
        *,
        max_completions_per_hp: int | None = None,
    ) -> "Problem":  # type: ignore[name-defined]
        """U-border with non-contradictory effects, **splitting** ambiguous polarities.

        Like ``complete_border_consistent_model``, but emits one operator per
        maximal completion when ``(U_eff - hp)`` leaves an atom's sign
        undetermined by ``(L_eff - hp)``. See
        ``generate_complete_border_consistent_split``.

        Args:
            ground: if True, build a grounded model (requires ``all_constants``).
            max_completions_per_hp: cap completions per ``hp`` (``None`` = enumerate all).
        """
        if ground:
            if self.all_constants is None:
                raise ValueError(
                    "Cannot build grounded model: 'all_constants' was not "
                    "provided at construction time."
                )
            return generate_complete_border_consistent_split_grounded(
                self.all_fluents,
                self.all_actions,
                self.all_constants,
                self.U_pre,
                self.L_eff,
                self.U_eff,
                max_completions_per_hp=max_completions_per_hp,
            )
        return generate_complete_border_consistent_split(
            self.all_fluents,
            self.all_actions,
            self.U_pre,
            self.L_eff,
            self.U_eff,
            max_completions_per_hp=max_completions_per_hp,
        )


    @property
    def converged(self) -> bool:
        """True if all actions have converged (L == U for both pre and eff)."""
        report = self.version_space_size
        return all(v["converged"] for v in report.values())

    @property
    def version_space_size(self) -> dict[str, dict]:
        """Per-action version space statistics.

        Each entry contains:
            n_pre:     number of precondition hypotheses in U_pre
            n_eff:     upper bound on effect hypotheses (2^|U_eff - L_eff|)
            converged: True if L == U for both pre and eff
            total:     n_pre * n_eff
        """
        return compute_version_space_size(
            self.all_actions,
            self.U_pre,
            self.L_pre,
            self.L_eff,
            self.U_eff,
        )

    @property
    def demo_count(self) -> int:
        """Total number of demonstrations processed so far."""
        return self._demo_count

    def __repr__(self) -> str:
        """Return a concise summary of the learner's current state."""
        n_actions = len(self.all_actions)
        n_collapsed = len(self.collapsed_actions)
        return (
            f"Learner(actions={n_actions}, demos={self._demo_count}, "
            f"collapsed={n_collapsed}, converged={self.converged})"
        )
