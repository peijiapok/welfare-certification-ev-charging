# Frozen simulation results: sequential charging identification

The predeclared single attempt completed with 1,800 independent synthetic drivers (300 per group), 64 collection episodes per driver and collector, and 32 deployment episodes. It took 37.37 seconds elapsed and 38.52 CPU seconds on the recorded host. The [frozen protocol](PROTOCOL.md), [source manifest](freeze_manifest.json), [full summary](runs/heldout_20261027_v1/summary.json), [per-driver outcomes](runs/heldout_20261027_v1/drivers.csv), [event ledger](runs/heldout_20261027_v1/events.csv.gz), and [artifact hashes](runs/heldout_20261027_v1/SHA256SUMS) contain the full specification and evidence. The 25 deterministic tests passed before freeze. The source manifest omitted the parent package initializer and the modules it imports; their run-time identities were not independently recorded, and this limits the provenance claim. An independent audit regenerated the keyed draws, verified the frozen study-source and output hashes, and reconstructed all 921,600 episodes, 1,847,948 events, exact first crossings, per-driver paired costs and unmet service with no discrepancies. No held-out rerun was performed.

## Matched p-only collection: exact gate versus plug-in

All entries are simulated drivers. “False” means the candidate's true expected benefit is nonpositive or its true expected unmet exceeds the allowed level; denominators for the false rate are drivers in that group who are truly ineligible. A dash means there were no ineligible drivers in the group, so no false-declaration rate is estimable. Lifecycle benefit is the mean paired advantage in credits over the always-default policy across 64 collection plus 32 deployment episodes; negative values are losses.

| Group | Exact deployed | Plug-in deployed | Exact false / ineligible | Plug-in false / ineligible | Exact lifecycle | Plug-in lifecycle |
|---|---:|---:|---:|---:|---:|---:|
| Easy | 167/300 | 300/300 | — | — | +3.598 | +4.136 |
| Low-information positive | 1/300 | 217/300 | — | — | +2.059 | +2.603 |
| Boundary | 2/300 | 154/300 | 1/177 | 79/177 | +0.331 | +0.203 |
| Harmful | 0/300 | 11/300 | 0/300 | 11/300 | −2.957 | −2.974 |
| Tight service | 0/300 | 202/300 | 0/123 | 57/123 | +0.891 | +1.666 |
| Misspecified | 189/300 | 299/300 | 189/300 | 299/300 | −5.522 | −6.433 |

For easy drivers, the exact deployment rate was 55.7% (95% Wilson interval 50.0–61.2%); for the low-information positive group, it was 0.3% (0.06–1.86%). The boundary false-declaration rate was 0.6% (0.10–3.13%) for the exact gate and 44.6% (37.5–52.0%) for the plug-in among ineligible drivers. Under deliberate response-model misspecification, all 300 drivers were truly ineligible and the exact gate falsely deployed 63.0% (57.4–68.3%); its nominal welfare guarantee does not apply there. The actual first-offer probability can be high despite adverse latent welfare because the behavior model was deliberately shifted.

The exact-minus-plug-in paired lifecycle difference was −0.538 credits in the easy group (95% bootstrap interval −1.142 to +0.077), and +0.129 in the boundary group (−0.416 to +0.690). These descriptive, unadjusted intervals do not establish a general ranking. In the nominal harmful group, the exact gate never deployed yet the p-only collector still incurred an average 2.957-credit lifecycle loss: a safe expected-unmet budget does not guarantee that information collection has positive welfare. In the tight-service group, the deterministic 0.005 service bound is insufficient for the 0.0045 allowance, so the exact gate abstained for everyone. The plug-in deployed 202 drivers, of whom 22 had nonpositive true benefit and 35 exceeded the service allowance.

## Other collectors and interpretation

The sign-entropy collector chose p on all 64 episodes for every driver in every group; its results are exactly identical to the p-only collector under the paired inputs. This study therefore provides **no observed advantage from adaptive contrast selection**. Alternating and myopic collectors used different offers and are reported in the full summary; for example, in the easy group their exact gates deployed 95/300 and 77/300, respectively, versus 167/300 with p-only collection. The common cap and the decision to keep collecting after a first crossing are part of this study; these numbers are not a comparison of optimized early-stopping policies.

The model-correct theorem is a per-driver, time-uniform error guarantee under the ideal logistic choice/welfare link and predictable observations, not a probability that a realized certificate is true. The simulator approximates that law with floating-point probabilities and pseudorandom uniforms; no separate finite-bit 5% theorem is claimed. The observed one false declaration in the boundary group is possible under a 5% bound and is not itself a contradiction of the theorem. The misspecified group exposes a failure of the structural link from choices to welfare, even though the one-dimensional observed-response null remains meaningful. The deterministic expected-unmet bound does not imply a pathwise service guarantee, and its collection and deployment allowances differ.

This result is **not yet publication-ready**: it is a one-port, two-request constructed system, uses fixed costs and one persistent modeled driver, lacks a matched general continuous-domain robust baseline, has no successful RL improvement, shows no adaptive information-gathering gain, and is highly sensitive to behavior-model misspecification. A broader, separately prespecified study and substantive evidence against close methods remain necessary. The simulation is not real-user evidence.

## Figure

[Decision rates and lifecycle outcomes](figures/decision_outcomes.png) compares the p-only exact gate and plug-in using the sealed summary. Bars show deployment rates with 95% Wilson intervals; points show lifecycle advantages against default with unadjusted paired bootstrap intervals. [Plotting code](plot_results.py) reads stored outputs and does not rerun the experiment. The figure is descriptive, with no multiplicity correction.
