# Two simulated drivers sharing one charging port: results

The frozen study completed once in 99.26 seconds, using 420 independent
synthetic pairs in seven groups of 60 and nine prespecified checkpoints. The
source manifest and saved-output hashes passed verification. A separate
stored-output audit found no discrepancies across 3,780 pair-checkpoint rows,
22,680 collection blocks, 3,780 deployment blocks, 15,120 gate replays,
conditional feedback reach, and full/stop-path accounting. It did not regenerate
scientific PCG64 draws or bootstrap resamples; replays share the original
interval arithmetic. A subsequent independent analysis replay regenerated only
the prespecified bootstrap indices and matched all 1,134 paired intervals and
2,268 endpoints exactly; no simulated pairs were regenerated. An independent
110-digit mpmath numerical check found no discrepancies in 15,120 stored gate
outputs and their available bands, theta bounds, witnesses, welfare/service
rectangles and latches. That check is not a rigorous directed-rounding proof. The separate 36-test preflight included exact-Fraction
physical and two-episode multinomial controls. These are conditional toy-model
results, not tests with people, stations, or fleets.

Each row below reports certified pairs, followed by false declarations among
the indicated true-ineligible denominator. Ineligibility means true B<=0 or
true expected urgent unmet U>epsilon, including overlap. Natural and forced are
different data-collection schedules; both data gates within each schedule share
the same observed feedback. The prior rule requires no preference data.

| Group | H | Ineligible / 60 | Natural two | Natural three | Forced two | Forced three | Prior |
|---|---:|---:|---:|---:|---:|---:|---:|
| prior_positive | 64 | 0 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 60/60 (0 false) |
| prior_positive | 12,288 | 0 | 59/60 (0 false) | 57/60 (0 false) | 59/60 (0 false) | 56/60 (0 false) | 60/60 (0 false) |
| prior_positive | 3,000,000 | 0 | 60/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) |
| positive_mixed | 64 | 26 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| positive_mixed | 12,288 | 26 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| positive_mixed | 3,000,000 | 26 | 0/60 (0 false) | 17/60 (0 false) | 0/60 (0 false) | 17/60 (0 false) | 0/60 (0 false) |
| harmful | 64 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| harmful | 12,288 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| harmful | 3,000,000 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| tight | 64 | 7 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| tight | 12,288 | 7 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| tight | 3,000,000 | 7 | 20/60 (0 false) | 45/60 (0 false) | 22/60 (0 false) | 45/60 (0 false) | 0/60 (0 false) |
| A | 64 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| A | 12,288 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| A | 3,000,000 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| B | 64 | 0 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| B | 12,288 | 0 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| B | 3,000,000 | 0 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| A_prime | 64 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| A_prime | 12,288 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| A_prime | 3,000,000 | 60 | 0/60 (0 false) | 3/60 (3 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |

At H=64 in prior-positive physics, the no-data rule certifies 60/60 immediately;
both data gates certify 0/60 under both schedules. The natural data rule's
mean welfare advantage over default for the whole 64+32 reset calendar is
+5.225 synthetic credits, versus +10.064 for the prior rule; the paired
natural-two-minus-prior difference is -4.840 (unadjusted 95% pair bootstrap
interval [-7.186,-2.445]). Their mean expected urgent unmet for that entire
calendar is 0.187 and 0.248 kWh, respectively; these totals are not
per-deployment-episode violations. The difference does not establish a
universal advantage for the prior rule at other horizons or under other physics.

In the harmful group, neither data rule certifies at H=64, but natural
collection has mean lifecycle advantage -4.079 credits, versus zero for the
always-default prior rule. The forced schedule has -3.562 credits. The natural
minus forced paired difference is -0.517 (95% descriptive bootstrap interval
[-1.194,-0.166]); this comparison changes both information and actions.

At H=64 in the prior-positive group, natural collection suppresses an average
5.25 of the 10 possible second-user r offers, so it observes a mean 4.75 B-r
responses; forced collection observes 10. The natural schedule also observes
21 A-p responses versus forced's 11. This comparison changes two exposures,
so it cannot isolate the causal effect of a single extra observation.

At the extreme H=3,000,000 checkpoint, both three-contrast schedules certify
17/60 in the positive-mixed group, whose true-ineligible denominator is 26/60,
and neither observes a false declaration. In the tight group, natural/forced
three-contrast certify 45/60 each, while the two-contrast rules certify 20/60
and 22/60; seven pairs are ineligible and no false declarations were observed.
The fixed beneficial B world remains uncertified under all four data rules. In
the deliberately misspecified A-prime group, natural three-contrast falsely
certifies 3/60 and forced three-contrast 0/60. A-prime violates the common
shift used by the three-contrast gate; nominal model-conditional coverage
therefore does not apply. Observed zero errors are not proof of zero risk or
calibration. The data do not show general superiority of either schedule.

Three million nonoverlapping 1.5-hour resets represent about 514 simulated
years, and at delta=.01 the universal H*delta collection service bound is
30,000 kWh. These horizons and stable preferences are extreme theoretical
stress tests, not realistic proposals or field forecasts. Collection and
32-reset deployment share an expected-service accounting boundary but the
deployment epsilon is per episode, not a bound on the entire collection total.
The conditional 95% event applies to the two data gates jointly within a single
schedule for one modeled pair, not jointly across schedules or pairs. Bias,
nonstationarity, history-dependent or correlated response shocks, and incorrect
physical assumptions can invalidate the inference. No individual fairness or
real-world causal claim is implied by the same-world system utility or
common-random pairing.

`runs/heldout_20261027_v1/summary.json` contains the full checkpoint table,
truth-strata denominators, offered and accepted counts, realized and expected
service, stop-path counterfactuals, paired differences and unadjusted descriptive
bootstrap intervals. `audit_saved_outputs.py` reads saved artifacts and draws no
new randomness; the separate audit receipt records its scope and limitations.
