# Finite-data common-bias simulation: results

The single frozen run completed in 44.26 seconds for six groups of 60 synthetic drivers, producing 3,240 driver-checkpoint rows. Before freeze, 37 deterministic tests passed. An independent stored-output audit verified the source and output hashes, 3,240 driver-checkpoint records, 9,720 aggregate offer blocks, all 6,480 gate evaluations, paired deployment draws, service and lifecycle accounting, with no discrepancies. Replaying a gate shares its interval arithmetic and is a consistency check, not an independent numerical proof. No catalog was rerun.

The p/r/third collection schedule and sampled response counts are identical for both methods; the two-contrast gate ignores third labels. The model-conditional, shared Hoeffding event has at least 95% per-driver coverage across all sample counts and jointly covers both gates under the stated common-shift assumptions. The two-contrast rule uses only two α/3 bands; its simple union-bound failure probability is at most 2/60. Neither inference nor behavioral assumptions are established by simulation. The group A-prime violates the common-shift model, so its three-contrast welfare guarantee does not apply.

## Outcomes across fixed checkpoints

Each group contains 60 independent synthetic driver/world units. Entries are the number certified by the two-contrast / three-contrast rule. The last three columns before false count are explicitly synthetic stress tests; the first listed checkpoint is already a long hypothetical horizon.

| Group | 12,288 episodes | 100,000 stress | 1,000,000 stress | 3,000,000 stress | Three-gate false / ineligible at 3m |
|---|---:|---:|---:|---:|---:|
| beneficial | 0 / 0 | 0 / 10 | 20 / 60 | 30 / 60 | — |
| harmful | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 60 |
| A | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 60 |
| B | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 60 | — |
| tight | 0 / 0 | 0 / 2 | 5 / 22 | 6 / 26 | 0 / 25 |
| A prime | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 60 | 60 / 60 |

At all checkpoints through 12,288 episodes, neither rule certified any of the 360 simulated drivers. At 100,000 episodes, the three-contrast rule certified 10/60 drivers in the beneficial group and 2/60 in the tight-service group; the two-contrast rule certified none. At one million, it certified 60/60 beneficial versus 20/60 for the two-contrast rule. At three million, it certified 60/60 in beneficial world B, compared with 0/60 for the two-contrast rule; it also falsely certified 60/60 harmful A-prime cases whose third response violated the assumed common-shift model. The nominal 95% welfare guarantee is inapplicable to that misspecified three-contrast group. Its original p/r response law remains common-shift, and the two-contrast rule ignores the third labels.

For world B at the 3-million checkpoint, the three-contrast 60/60 rate has a 95% Wilson interval of 94.0–100%; the same interval describes the 60/60 false-declaration rate in A-prime. These intervals concern fixed synthetic models and do not establish field behavior. All normal-model groups had zero observed false declarations at that checkpoint, but 60 independent units per group cannot empirically validate a 5% time-uniform theorem. The two rules share data and sufficient confidence events, but different conservative bound constructions; do not treat this as a general algorithmic superiority result.

## Collection burden and practical scope

The period comprises three nonoverlapping half-hour slots per collection episode. At 12,288 episodes this implies at least 768 days; at three million it implies about 514 years of continuous single-port use before downtime. The latter assumes fixed preferences and a fixed response law for centuries. These are mathematical toy consequences, not field forecasts or recommendations. The universal expected collection-unmet upper bound H/200 is 61.44 kWh at 12,288 episodes and 15,000 kWh at three million, separate from the deployment allowance. The latter is not a pathwise limit.

At the 3-million checkpoint, mean realized collection advantage was approximately +29,995 credits in world B, −6,810 in harmful world A, and −6,515 in A-prime; both methods incurred the same full-horizon collection history. Mean realized collection unmet was approximately 9,646 kWh in B and 9,624 kWh in A-prime. These very large modeled totals reflect the extreme repeated-episode assumption. The stop-at-first-certified-checkpoint counterfactual is saved separately; no within-block early decision was simulated.

The aggregate sampler is equivalent in ideal distribution to per-episode response and urgency draws under independence and the fixed periodic schedule, as checked on exact small physical fixtures. It preserves the specified count-based information, matched collection and welfare totals at checkpoint boundaries; it does not retain episode order within blocks or support claims about earlier decisions. NumPy pseudorandom draws and floating-point probabilities approximate the ideal model. The model does not test drift, urgency–response dependence, multiple drivers sharing a system, or field behavior.

Full strata, Wilson intervals, paired bootstrap intervals, timing, expected and realized service, cost and stop-counterfactual results are in `runs/heldout_20261027_v1/summary.json` and `checkpoints.jsonl`. Source, protocol, tests, event-block counts and all required dependencies are bound by `freeze_manifest.json`; the completion and output-digest chain are in the run directory. The code and replay share Decimal interval primitives. Source hashing and reproducible seeded outputs are not a fully hermetic environment.

## Figure

[Bias-robust decisions by horizon](figures/bias_robust_decisions.png) and [plotting code](plot_results.py) read stored outputs only. Bands are 95% Wilson intervals; lines connect the prespecified checkpoints. Shaded horizons are synthetic stress tests; every favorable decision for harmful A-prime is false.
