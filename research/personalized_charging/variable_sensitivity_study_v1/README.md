# Variable-physics sensitivity study

This frozen simulation varies known procurement costs, urgent-arrival rates, shortfall penalties and expected-service limits in the one-port, two-request model. It compares the two- and three-contrast confidence gates with an explicit no-data prior rule on paired simulated calendars. `PROTOCOL.md` contains the frozen model, groups, checkpoints, accounting and failure rules; `RESULTS.md` reports the audited outcomes, including the value of the no-data baseline, collection losses, misspecification and extreme synthetic stress horizons. The 3-million-episode case assumes about 514 years of continuous port use and is not a deployment recommendation.

The scientific catalog in `runs/heldout_20261027_v1/` is sealed. Do not overwrite, retune, silently resume or rerun it to change the results. Its `completed.json`, `output_hashes.json`, source freeze manifest, keyed count records and summary form the stored provenance chain. Block aggregates preserve the declared fixed-schedule ideal distribution and paired additive ledgers, but not within-block order. The code's numerical RNG approximates that ideal law.

Run deterministic controls from the repository root without a scientific catalog:

```bash
python -m unittest personalized_charging.sequential_identification_v1.test_physical personalized_charging.two_contrast_bias_exploratory_v1.test_gate personalized_charging.three_contrast_confidence_exploratory_v1.test_gate personalized_charging.variable_physics_exploratory_v1.test_extension personalized_charging.variable_sensitivity_study_v1.test_joint_independent personalized_charging.variable_sensitivity_study_v1.test_run -v
```

The generalized gates and prior-only rule use shared Decimal interval primitives. Statistical coverage is conditional on the assumed common-shift choice model and conditional response laws; it is not familywise across drivers, is not a practical-service guarantee and does not extend to the three-gate under a contrast-specific shift. The W<g2 group is a mathematical stress case, not a recommended penalty. Python 3.13.11, NumPy 2.3.5 and POSIX process/resource limits were used; this is not a fully hermetic environment. Initial source verification and a blocked process-start window have the watchdog limitations documented in the protocol, and uncatchable termination cannot guarantee cleanup.
