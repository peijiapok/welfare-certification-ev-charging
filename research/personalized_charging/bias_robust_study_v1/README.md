# Bias-robust finite-data study

This simulation compares two- and three-contrast confidence gates using identical periodic collection histories. `PROTOCOL.md` specifies the frozen model, groups, checkpoints, budget accounting and failure rules. `RESULTS.md` reports the single audited run, including harms, misspecification and the very large synthetic stress horizons. `runs/heldout_20261027_v1/` contains the sealed count records, summary, manifest-linked completion receipt and output hashes; do not overwrite, retune or rerun the catalog to improve results.

Both rules share conservative anytime Hoeffding bands and Decimal interval arithmetic. The theoretical joint per-driver guarantee assumes the specified common response shift, persistent model, conditional Bernoulli choices and urgent-arrival law; it does not extend to arbitrary model misspecification, multiple drivers or real charging systems. The three-million-episode checkpoint assumes about 514 years of continuous toy-model port use; it is not an operational recommendation. Collection expected-unmet allowance H/200 and the per-deployment-episode service allowance are separate.

From the repository root, deterministic tests can be run without scientific sampling:

```bash
python -m unittest personalized_charging.sequential_identification_v1.test_physical personalized_charging.two_contrast_bias_exploratory_v1.test_gate personalized_charging.three_contrast_confidence_exploratory_v1.test_gate personalized_charging.bias_robust_study_v1.test_aggregate_independent personalized_charging.bias_robust_study_v1.test_run -v
```

`plot_results.py` generates figures from the saved summary only. The combined package checker `personalized_charging/verify_research_package_20261027.py` verifies the saved source and artifact hashes. Python 3.13.11, NumPy 2.3.5 and POSIX process/resource limits were used; source hashes and package versions are not a complete hermetic environment. The internal watchdog cannot preempt initial source verification, and uncatchable termination cannot guarantee cleanup.
