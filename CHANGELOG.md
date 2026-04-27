# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/pablocopete/ascal/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/pablocopete/ascal/releases/tag/v0.1.0
