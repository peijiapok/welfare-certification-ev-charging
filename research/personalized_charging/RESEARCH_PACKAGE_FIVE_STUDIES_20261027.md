# Five-study simulation research package

This package contains five prospectively frozen simulation studies, a working
manuscript and deterministic controls. All modeled drivers and charging events
are synthetic; the package does not demonstrate a real-world or RL improvement.
The paper is a narrow identifiability and simulation draft for critical review,
not a claim that publication or acceptance is guaranteed.

The first four studies and the limits of their source provenance are described
in `RESEARCH_PACKAGE_20261027.md`. The fifth is in `two_driver_study_v1/`, with
its frozen protocol and manifest, saved held-out run, and results. Its supporting
exact-physics and six-stream confidence prototype is in
`two_driver_exploratory_v1/`. The two-driver experiment has one port, fixed
synthetic response laws, and a per-schedule, per-pair confidence guarantee;
it is not a field, fleet or multiport validation. The independent stored-output audit can be replayed without generating data:

```bash
python -m personalized_charging.two_driver_study_v1.audit_saved_outputs personalized_charging/two_driver_study_v1/runs/heldout_20261027_v1 personalized_charging/two_driver_study_v1/freeze_manifest.json
```

To reproduce the separate paired-bootstrap analysis without generating new
simulated pairs, run:

```bash
python -m personalized_charging.two_driver_study_v1.audit_bootstrap personalized_charging/two_driver_study_v1/runs/heldout_20261027_v1
```

The independent 110-digit numerical check needs mpmath 1.3.0 and can be run as:

```bash
python audits/2026-10-27_two_driver_mpmath_check.py personalized_charging/two_driver_study_v1/runs/heldout_20261027_v1/checkpoints.jsonl
```

It is a non-rigorous numerical cross-check, not a directed-rounding proof.
The independently written
records under `audits/` are audit scripts and reports, never runtime inputs.
All scientific output and frozen source files are sealed; do not overwrite or
rerun them to generate new evidence.

From the extracted package root, check source and saved-output hashes with:

```bash
python personalized_charging/verify_research_package_five_studies_20261027.py
```

Run the four-study deterministic suite listed in `RESEARCH_PACKAGE_20261027.md`,
plus the fifth-study controls:

```bash
python -m unittest personalized_charging.two_driver_exploratory_v1.test_prototype personalized_charging.two_driver_exploratory_v1.test_independent_fraction personalized_charging.two_driver_study_v1.test_run -v
```

The Python, NumPy and Matplotlib versions and input/output hashes identify the
local environment but do not make it hermetic. Repeating an identical seeded
run reproduces the same evidence, not an independent scientific assessment.
A genuinely new assessment needs a separate prospective protocol, independent
simulated populations and preserved prior artifacts. The fifth simulation's
60-pair intervals are descriptive, its longest horizon is an extreme theoretical
stress, and its confidence and welfare claims remain conditional on the stated
model. Shared interval code limits numerical independence of certificate replay.
