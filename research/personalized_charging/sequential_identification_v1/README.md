# Sequential identification study

This self-contained simulation examines a one-port, two-offer charging example. It is a small artificial research model, not real-world data or an RL benchmark. Read `PROTOCOL.md` for the estimands, assumptions, prospective catalog, error-control limits, episode accounting and known limitations. The exact certificate uses only p-offer responses and makes a model-conditional, per-driver guarantee; it may abstain on beneficial cases. The working paper is `MANUSCRIPT_DRAFT.md`. `IDENTIFICATION_LIMIT.md` contains a separately reviewed post-run mathematical construction.

## Software and tests

Development environment: Python 3.13.11, NumPy 2.3.5 and Matplotlib 3.10.8 (plotting only). The version pins are partial, not a fully hermetic environment. The study freeze manifest hashes the study sources and tests but did not hash the parent package initializer or its imported modules at run time; the archive contains their current copies, and its own SHA-256 covers the packaged copies, but their run-time identity was not independently recorded. From the repository root:

```bash
python -m unittest personalized_charging.sequential_identification_v1.test_physical personalized_charging.sequential_identification_v1.test_certificate personalized_charging.sequential_identification_v1.test_run -v
```

The tests use deterministic controls and separate fixture inputs; they do not reproduce the held-out catalog. The post-run identification construction has six additional controls: `python -m unittest personalized_charging.sequential_identification_v1.test_identification_limit -v`. Those controls were added after the original study and are not part of its frozen preflight. Public simulator events carry only observable events; simulator losses and latent parameters are evaluator-only. The randomness generator supplies independent event-type uniforms and paired exogenous innovations across comparable arms.

## Execution and preservation

A prospective run requires a SHA-256 manifest covering the protocol, implementation and tests, as checked by the runner. The runner requires both the manifest and an output directory that does not already exist. Invoke from the repository root:

```bash
python -m personalized_charging.sequential_identification_v1.run --manifest personalized_charging/sequential_identification_v1/freeze_manifest.json --output PATH_TO_A_NEW_DIRECTORY
```

The released scientific run, if completed, is a sealed result. Do not overwrite it, use its output to retune the protocol, or represent a repeat as an additional independent experiment. Any exact reproduction is a verification of the same seeded study, not new evidence; preserve it in a distinct directory and compare only scientific outputs, since timestamps, elapsed time, platform strings and compressed-file headers can vary. The runner uses a cooperative 600-second wall-clock limit, reports partial runs as incomplete when it can, and creates a start sentinel to identify interruptions without a final receipt. Retain the complete generated outputs and their digest record with the source manifest.

A grid posterior is used only by heuristic collectors and the plug-in comparison; it does not certify the continuous parameter domain. Model misspecification is separately labeled and has no nominal error-control guarantee. One driver, one port and the modeled prices, procurement costs, response law and urgent-arrival mechanism limit interpretation. A deployment-only oracle is not a full-lifecycle upper bound.

The completed results and interpretation are in `RESULTS.md`. To regenerate the descriptive figure from the sealed summary without rerunning the simulation: `python personalized_charging/sequential_identification_v1/plot_results.py`.
