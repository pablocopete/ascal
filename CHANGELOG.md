# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-07-24

### Changed

- `compute_version_space_size` / `Learner.version_space_size`: `total` is now
  the **exact** number of semantically distinct `(hp, he)` action models,
  computed by a weighted inclusion–exclusion with closed-form terms
  `2^|G−l| · 2^|S−G| · 3^|S∩G|` (`G = U_eff − L_eff`). Previously
  `n_pre * 2^|G|`, an upper bound that double-counted no-op effect variants
  (effect literals already guaranteed by `hp`) — inflation `2^|hp ∩ G|` per
  hypothesis, triggered by every unconverged static/frame literal (13.5×
  observed on driverlog `drive_truck`). `n_pre` and the `n_eff` proxy are
  unchanged; the count now matches what `generate_complete_model` /
  `generate_true_full_version_space` materialize (with `he = ∅` deliberately
  included, and no contradiction filtering — vacuous once an action has one
  positive demo).

### Added

- `compute_version_space_upper_bound` / `Learner.version_space_upper_bound`:
  the pre-0.2.0 proxy semantics (`total = n_pre * n_eff`), kept for
  comparability with metrics recorded by runs on ascal < 0.2.0.
- `total_exact` flag in the per-action report (False only on the
  ≥20-frontier-element estimate fallback, alongside `n_pre_exact`).
- `tests/test_version_space_size.py` (brute-force randoms, split-overlap,
  semantic-class bijection, operator-stream soundness/monotonicity) and
  `tests/test_version_space_size_e2e.py` (bundled-benchmark learner runs with
  full materializer enumeration as oracle; skips cleanly without a planner).

## [0.1.1] - 2026-07-15

### Changed

- `UUP` (upper-precondition update): replaced the post-hoc O(|candidates|²)
  minimal-element filter with two exact shortcuts — an early return when no
  hypothesis fires, and a size-sorted scan that compares each candidate only
  against already-accepted minimal elements. **Output-identical** to the
  previous filter on any minimal-antichain `U` (the invariant the learner
  maintains); verified over 200k randomized cases and 653 live calls. Cuts
  per-probe update time substantially on high-arity domains (~5× on rovers);
  neutral on conversion-bound domains. `UUP` remains a notable cost center —
  further optimization is possible.
  - Note: the early-return shortcut assumes `U` is a minimal antichain (always
    true via the learner). Calling `UUP` directly with a non-minimal `U` and no
    firing hypothesis now returns `U` unfiltered.

## [0.1.0] - 2026-04-22

Initial public release of ASCAL (Anytime Sound and Complete Action Learning).

### Added

- Core data classes: `Literal`, `State`, `Action`, `Demonstration`.
- Unified Planning bridge in `ascal.transitions`:
  - `generate_transitions_from_problem`
  - `generate_lifted_demonstrations_from_problem`
  - `lift_demonstrations`, `lift_transitions`, `lift_transitions_with_map`
  - `generate_all_lifted_literals`, `generate_all_ground_literals`
  - `state_to_signature`, `build_literal_descriptors`
- ASCAL version-space operators in `ascal.algorithm`:
  - Precondition operators `RUP`, `RLP`, `ULP`, `UUP`
  - Effect operators `RLE`, `RUE`, `ULE`, `UUE`
  - `ASCAL_initialization`, `run_ASCAL_iteration`, `run_ASCAL`
- Model generators: `generate_sound_action_model`, `generate_complete_border`,
  `generate_complete_border_consistent`, `generate_complete_border_consistent_split`,
  and their grounded variants.
- Evaluation functions in `ascal.evaluation`:
  - `evaluate_detailed`, `evaluate_representative`, `evaluate_convergence_gated`
  - `compute_version_space_size`, `evaluate_f1score`
- High-level `Learner` class wrapping initialization, incremental `update()`,
  batch `update_batch()`, model extraction (`sound_model`, `complete_model`,
  `upper_border_split`, `upper_border_single`, `raw_upper_bound`), and evaluation
  (`evaluate`, `evaluate_repr`, `evaluate_gated`).
- Packaging metadata for PyPI:
  - `src/`-layout with `pyproject.toml` (PEP 621) and `setuptools` backend.
  - GPL-3.0-or-later license.
  - Optional extras: `notebook`, `planner`, `dev`.

[Unreleased]: https://github.com/pablocopete/ascal/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/pablocopete/ascal/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/pablocopete/ascal/releases/tag/v0.1.0
