# Manuscript figure data and scripts

All four plots are rendered from saved summary files, using NumPy and
Matplotlib. The plots do **not** rerun a scientific simulation, fit a model,
or resample a confidence interval; the summaries already contain the reported
statistics and intervals.

| Manuscript figure | Files in `figures/` | Standalone source | Input folder | Original study |
|---|---|---|---|---|
| Figure 1 | `decision_outcomes.{pdf,png,svg}` | `figure_scripts/figure_1_plot.py` | `figure_data/figure_1/` | `sequential_identification_v1` |
| Figure 2 | `matched_decisions.{pdf,png,svg}` | `figure_scripts/figure_2_plot.py` | `figure_data/figure_2/` | `matched_verifiers_v1` |
| Figure 3 | `bias_robust_decisions.{pdf,png,svg}` | `figure_scripts/figure_3_plot.py` | `figure_data/figure_3/` | `bias_robust_study_v1` |
| Figure 4 | `prior_vs_collect.{pdf,png,svg}` | `figure_scripts/figure_4_plot.py` | `figure_data/figure_4/` | `variable_sensitivity_study_v1` |

The plotting scripts are unchanged copies. They expect a `runs/heldout_20261027_v1/`
folder next to the script and write to a sibling `figures/` folder. Use the
root `regenerate_figures.py` helper instead: it constructs those paths in a
temporary directory and places results in a new output folder, so the original
manuscript figures and historical research artifacts are not overwritten.

The four figures were regenerated successfully in a temporary location using
Python 3.13.11, NumPy 2.3.5 and Matplotlib 3.10.8. In that environment each
regenerated PNG was pixel-identical to the corresponding saved PNG. PDF/SVG
files can differ bytewise due to metadata or environment even when the plots
look identical; exact rendering in a different environment is not guaranteed.
`figure_provenance.json` records the copied inputs, scripts, figure hashes and
versions. Full saved scientific records and their original provenance remain in
`research/personalized_charging/`; the data is synthetic and is not human or
field data.
