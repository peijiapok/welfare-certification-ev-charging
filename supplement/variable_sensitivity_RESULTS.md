# Variable-physics sensitivity study: results

The single frozen run completed in 63.52 seconds for nine groups of 60 synthetic drivers. Before freeze, 42 deterministic tests passed; the malformed unresolved-ALLOW validator case was corrected and re-audited before the run. An independent stored-output audit verified the 22-source manifest and output chain, 540 worlds, 4,860 driver-checkpoint records, 14,580 collection blocks, 4,860 deployment blocks, 9,720 data-gate replays, prior-rule decisions, paired lifecycle/stop ledgers and summary strata with no discrepancies. Replays use the same interval arithmetic as the gates and are consistency checks, not independent numerical proofs. The scientific catalog was not rerun.

The known procurement costs, urgent-arrival rate, shortfall penalty and service allowance vary by predeclared scenario. Two data gates receive identical p/r/third collection histories; the two-contrast gate ignores the third label. A third, no-data prior rule uses known physics only: when it certifies, it runs the candidate for the entire H+32 calendar; otherwise it defaults. The data gates collect for H episodes and then deploy for 32. All are compared with the same always-default counterfactual and share underlying simulated potential outcomes. The common-random coupling is a simulation design, not a claim about real user potential outcomes.

## Certification across horizons

Entries are numbers certified by prior / two-contrast / three-contrast among 60 simulated drivers. “False / null” for the three-contrast rule counts favorable decisions for drivers whose true B≤0 or U exceeds their deployment allowance. Near-zero drivers were deliberately selected conditional on |B|≤0.002 and do not represent an unconditional population.

| Group | 64 episodes | 12,288 episodes | 3,000,000 episodes (stress) | Three-gate false / null at 3m |
|---|---:|---:|---:|---:|
| prior positive 1 | 60 / 0 / 0 | 60 / 59 / 58 | 60 / 60 / 60 | — |
| prior positive 2 | 60 / 0 / 0 | 60 / 59 / 58 | 60 / 60 / 60 | — |
| harmful | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 60 |
| near zero | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 24 |
| tight | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 15 / 35 | 0 / 16 |
| low penalty | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 57 |
| A | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 60 |
| B | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | — |
| A prime | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 60 |

In each prior-positive group, the no-data rule certified all 60 drivers immediately; at the 64-episode checkpoint the two data rules certified none. In prior-positive group 1, mean advantage over the same 96-episode always-default calendar was +11.837 credits for the no-data rule versus +5.398 for either data rule. The paired data-minus-prior difference was −6.439 credits (unadjusted 95% bootstrap interval −8.546 to −4.179). The prior rule’s mean expected unmet over the full calendar was 0.364 kWh versus 0.174 for the data rules; these totals are not per-episode service-limit violations. The no-data proof uses the declared physical assumptions and provides pointwise positivity, not a strictly positive uniform margin.

In the harmful group at the same checkpoint, both data rules abstained from deployment yet their collection led to mean lifecycle advantage −3.627 credits; the prior rule defaulted and had zero advantage. In the tight-service group, at the extreme 3-million checkpoint the two- and three-contrast rules certified 15/60 and 35/60, respectively, with no observed false declaration among 16 ineligible drivers. Sixty samples cannot empirically verify the nominal confidence guarantee. In the new fixed B and misspecified A-prime physics, neither data rule certified at any evaluated checkpoint, including the extreme horizon; this does not establish robustness to arbitrary misspecification.

## Interpretation and limitations

The prior-only comparison shows that collecting feedback can be unnecessary when known physics already certifies the candidate, and collection can itself incur welfare losses. These are results under a particular predeclared one-port simulator and welfare ledger, not general statements about charging systems. The low-penalty group has W<g2: the stated ledger can reward an unmet urgent request because avoided procurement exceeds the penalty, so it is a mathematical stress case and service must be judged separately.

The α/3 per-contrast Hoeffding bands jointly cover both data rules with probability at least 95% per correctly modeled driver under the declared common-shift and conditional Bernoulli assumptions. The two-band simple failure bound is 2/60. The three-rule welfare guarantee does not apply in A-prime, where the third shift differs; this study is not an empirical proof of that guarantee. Collection has a separate expected-unmet allowance Hδ; it is not the per-deployment epsilon and is not a pathwise guarantee.

The 100,000-, one-million- and three-million-episode checkpoints are explicitly extreme synthetic stress tests. Three million nonoverlapping 1.5-hour episodes correspond to about 514 years per port; for δ=.02 the uniform cumulative expected-unmet bound is 60,000 kWh. These horizons require implausibly persistent behavior and are neither field forecasts nor operating recommendations. The short horizons are synthetic as well.

Joint multinomial block counts are distributionally faithful for the specified fixed schedules and independent response/urgency primitives at checkpoint boundaries, as checked against exact small physical-path enumerations. They do not reveal within-block order or decisions. Full raw truth, matched block counts, service, welfare, stop-counterfactuals, per-method confidence bounds and descriptive intervals are in `runs/heldout_20261027_v1/checkpoints.jsonl` and `summary.json`. The source/manifest/completion/output hash chain is retained; Python/NumPy versions and a 4-GiB address-space cap are recorded, but the environment is not fully hermetic. See `PROTOCOL.md` for the initial-verification watchdog and uncatchable-termination caveats. The study is one port and two requests; it does not demonstrate general multi-driver performance, RL improvement, or publication readiness.

[Prior versus collection figure](figures/prior_vs_collect.png) and [plotting code](plot_results.py) use saved outputs only. At 64 episodes, the two data rules have identical outcomes; error bars are unadjusted paired-bootstrap intervals against default.
