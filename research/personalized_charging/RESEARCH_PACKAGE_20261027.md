# Simulation research package, 27 October 2026

The four studies are artificial, model-conditional simulations. None contains real charging sessions or demonstrates an RL improvement. The manuscript is a working draft, not a journal submission.

- `sequential_identification_v1/PROTOCOL.md`, `RESULTS.md`, `APPENDIX_RESULTS.md`, `MANUSCRIPT_DRAFT.md`, `IDENTIFICATION_LIMIT.md`: first frozen study, full results, paper and post-run theory.
- `continuous_certificate_exploratory_v1/README.md`: exploratory p/r interval verifier and proof replay. Its arithmetic is shared with the P3d diagnostic.
- `matched_verifiers_v1/PROTOCOL.md`, `RESULTS.md`, `README.md`: fresh matched comparison and stored artifacts.
- `three_contrast_confidence_exploratory_v1/` and `two_contrast_bias_exploratory_v1/`: audited finite-data bias-robust prototype gates using shared interval arithmetic.
- `bias_robust_study_v1/PROTOCOL.md` and `RESULTS.md`: third frozen finite-data comparison, including explicitly extreme synthetic stress horizons.
- `variable_physics_exploratory_v1/`: generalized known-physics confidence and no-data rules plus exact physical controls.
- `variable_sensitivity_study_v1/PROTOCOL.md` and `RESULTS.md`: fourth frozen paired sensitivity study and prior-only baseline.
- `*/runs/heldout_20261027_v1/`: original saved outputs and hash receipts. These are sealed; do not overwrite, selectively repeat or tune them.
- Development worklogs and internal review notes are not included in this public release; the audit records cited in the manuscript are in `../audits/`.

Python 3.13.11 and NumPy 2.3.5 were used; Matplotlib 3.10.8 is used only for plotting. These version pins and local source hashes do not define a fully hermetic environment. In particular, the first study's frozen manifest omitted the parent package initializer and imports, whereas the matched follow-up includes them. The recorded run-time identity of the omitted files is not independently established.

Run deterministic checks from the extracted package root:

```bash
python -m unittest personalized_charging.sequential_identification_v1.test_physical personalized_charging.sequential_identification_v1.test_certificate personalized_charging.sequential_identification_v1.test_run personalized_charging.sequential_identification_v1.test_identification_limit personalized_charging.continuous_certificate_exploratory_v1.test_comparator personalized_charging.continuous_certificate_exploratory_v1.test_proof_replay personalized_charging.matched_verifiers_v1.test_run personalized_charging.two_contrast_bias_exploratory_v1.test_gate personalized_charging.three_contrast_confidence_exploratory_v1.test_gate personalized_charging.bias_robust_study_v1.test_aggregate_independent personalized_charging.bias_robust_study_v1.test_run personalized_charging.variable_physics_exploratory_v1.test_extension personalized_charging.variable_sensitivity_study_v1.test_joint_independent personalized_charging.variable_sensitivity_study_v1.test_run -v
```

Run `python personalized_charging/verify_research_package_20261027.py` to check all four saved result sets, their manifests and the output-digest chains without rerunning any scientific catalog. An exact seeded reproduction, if undertaken, reproduces the same evidence and must use a new output path. A genuinely new scientific assessment requires its own frozen protocol and independent simulated populations.
