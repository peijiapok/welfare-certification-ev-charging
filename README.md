# Identification Limits for Welfare Certification from Binary Choice Feedback

Code, frozen protocols, stored simulation outputs, audits and verification scripts for:

> Pok, P.; Yeo, H. *Identification Limits for Welfare Certification from Binary Choice Feedback: A Stylized Electric-Vehicle Charging Case Study.* Submitted to *Mathematics* (MDPI), 2026.

All results are from synthetic simulations of a stylized one-port charging model. No human-participant data were collected.

## Contents

| Path | What it is |
|---|---|
| `research/personalized_charging/sequential_identification_v1/` | Study 1: one-dimensional gate vs plug-in (Experiment 1) |
| `research/personalized_charging/matched_verifiers_v1/` | Study 2: matched-verifier follow-up (Appendix A) |
| `research/personalized_charging/bias_robust_study_v1/` | Study 3: two- vs three-contrast rules (Experiment 2) |
| `research/personalized_charging/variable_sensitivity_study_v1/` | Study 4: variable physics and the no-data rule (Experiment 3) |
| `research/personalized_charging/two_driver_study_v1/` | Study 5: two drivers on one port (Experiments 2 and 3) |
| `research/personalized_charging/projection_comparison_study_v2/` | Study 6: theta-projection comparator (Experiment 2) |
| `research/personalized_charging/projection_comparison_study_v1/` | Incomplete first attempt at Study 6, kept for transparency; **not evidence**, see `research/audits/2026-10-28_projection_v1_incomplete_attempt.md` |
| `research/personalized_charging/mixture_replay_posthoc/` | Post hoc mixture-gate replay on stored Study 1 histories (not a frozen study) |
| `research/personalized_charging/*` (other modules) | Shared model, gate, interval-arithmetic and projection code imported by the studies |
| `research/audits/` | Independent audit scripts and reports cited in Appendix B |
| `verification/` | Independent checks of Tables 2 and 3 and the interval enclosures (Supplementary S4) |
| `figures/`, `figure_data/`, `figure_scripts/`, `regenerate_figures.py` | Manuscript figures, their saved inputs and the plotting scripts |
| `supplement/` | Study protocol and full results for all collectors and groups |

Each study folder contains its `PROTOCOL.md`, source, tests and a `runs/` directory with the stored outputs, manifest and hashes. Every study was frozen and run once.

## Requirements

Python 3.10 or later, with `numpy`, `scipy`, `mpmath` and `matplotlib` (see `requirements-figures.txt` and each run's `environment.json` for the exact versions used).

## Reproducing the results

```bash
# Integrity: source, output and completion hash chains for all six studies
cd research && python personalized_charging/verify_research_package_six_studies_20261028.py && cd ..

# Redraw the original figures from saved summaries (no new simulation)
python regenerate_figures.py

# Figures 1 and 2 of the revised manuscript (exact calculations)
python figure_scripts/gate_comparison.py
python figure_scripts/certifiability_map.py

# Post hoc mixture replay (reproduces 146, 1, 1, 0, 0, 180)
python research/personalized_charging/mixture_replay_posthoc/replay.py

# Independent verification (Supplementary S4)
cd verification
python verify_gate_table.py
python verify_benchmarks.py
python verify_interval_enclosures.py ../research
```

`sha256sum -c SHA256SUMS.txt` checks the integrity of every file in this release.

Development worklogs and internal review notes are not included in this public release.

## License

Code: MIT License (see `LICENSE`). Stored simulation outputs, protocols and documentation: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Citation

See `CITATION.cff`. Please cite the article once published.
