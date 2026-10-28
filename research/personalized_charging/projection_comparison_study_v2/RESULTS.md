# Fresh-sample theta-projection comparison: results

The separately frozen v2 run completed once in 174.76 seconds for six groups of
60 independent synthetic pairs, with nine prespecified checkpoints. The prior
v1 attempt failed in summary generation and remains incomplete; its partial
outcomes were not analyzed or used to design v2. The v2 analysis includes 22
prespecified descriptive paired comparisons per group and checkpoint. It
compares the two existing rules with an independently coded theta-projection
rule, all on identical observed histories within each schedule. The projection
is Schnitzer-inspired, but is neither the published PRISM implementation nor
a full expression-wise projection. Natural and forced schedules alter both
exposure and actions. The no-data and default policies are shared baselines.

The saved-output audit checked all 30 frozen-source hashes, completion and
output inventory, all 3,240 chained records, 19,440 collection blocks, 3,240
deployment blocks, all 19,440 gate decisions and 12,960 projection witnesses,
suppressions, true strata, latches and full/stop-path accounting with no
discrepancies. Gate and witness replays share the original interval arithmetic.
A separate 100-digit numerical diagnostic independently reconstructed bands,
polygons, witness checks and benefit/service bounds for 6,480 projection
outputs with no discrepancies or inconclusive favorable margins at relative-or-absolute
tolerance 1e-28; this is not a rigorous directed-rounding proof. Two post-completion
bootstrap analysis replays verified all 3,564 intervals; neither generated new
scientific pairs or examined incomplete v1 records. The physical RNG draws
were not regenerated in the stored-output audit.

Each cell in the following table is favorable declarations per 60, followed
by false declarations. The null denominator counts true B<=0 or expected
urgent unmet U>epsilon, including any overlap. Fixed B and A-prime are repeated
independent simulated pair histories at fixed model parameters, not samples
of human drivers. The A-prime behavior law violates the common-shift assumption
used by the three-contrast and projection rules.

| Group | H | Null / 60 | Natural two | Natural three | Natural projection | Forced two | Forced three | Forced projection | Prior |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| prior_positive | 64 | 0 | 0/60 (0 false) | 0/60 (0 false) | 21/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 14/60 (0 false) | 60/60 (0 false) |
| prior_positive | 12,288 | 0 | 58/60 (0 false) | 55/60 (0 false) | 60/60 (0 false) | 59/60 (0 false) | 55/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) |
| prior_positive | 100,000 | 0 | 60/60 (0 false) | 59/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) | 59/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) |
| prior_positive | 3,000,000 | 0 | 60/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) | 60/60 (0 false) |
| positive_mixed | 64 | 22 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| positive_mixed | 12,288 | 22 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| positive_mixed | 100,000 | 22 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| positive_mixed | 3,000,000 | 22 | 9/60 (0 false) | 27/60 (0 false) | 32/60 (0 false) | 9/60 (0 false) | 25/60 (0 false) | 32/60 (0 false) | 0/60 (0 false) |
| harmful | 64 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| harmful | 12,288 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| harmful | 100,000 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| harmful | 3,000,000 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| tight | 64 | 9 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| tight | 12,288 | 9 | 0/60 (0 false) | 0/60 (0 false) | 1/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 1/60 (0 false) | 0/60 (0 false) |
| tight | 100,000 | 9 | 0/60 (0 false) | 5/60 (0 false) | 23/60 (0 false) | 0/60 (0 false) | 3/60 (0 false) | 23/60 (0 false) | 0/60 (0 false) |
| tight | 3,000,000 | 9 | 23/60 (0 false) | 43/60 (0 false) | 47/60 (0 false) | 23/60 (0 false) | 43/60 (0 false) | 47/60 (0 false) | 0/60 (0 false) |
| B | 64 | 0 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| B | 12,288 | 0 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| B | 100,000 | 0 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| B | 3,000,000 | 0 | 0/60 (0 false) | 2/60 (0 false) | 60/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 58/60 (0 false) | 0/60 (0 false) |
| A_prime | 64 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| A_prime | 12,288 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| A_prime | 100,000 | 60 | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) | 0/60 (0 false) |
| A_prime | 3,000,000 | 60 | 0/60 (0 false) | 0/60 (0 false) | 60/60 (60 false) | 0/60 (0 false) | 0/60 (0 false) | 58/60 (58 false) | 0/60 (0 false) |

At H=64, in prior-positive physics natural projection certifies 21/60 while
the old natural three-contrast rule certifies 0/60; projection minus old
certification is +35 percentage points, with an unadjusted paired 95% bootstrap
interval of +23.3 to +46.7 points. On the full H+32 calendar, mean system
advantage over default is +8.583 credits for projection versus +6.794 for the
old three-contrast rule, a paired projection-minus-old difference of +1.788
[+0.743,+2.874]. However, the prior-only rule certifies all 60 immediately
and yields +8.670 mean credits; projection-minus-prior is -0.087
[-2.175,+2.299]. Expected urgent unmet over the entire calendar is 0.220 kWh
for projection and 0.238 kWh for prior; those totals are not per-reset service
violations. No superiority over the no-data baseline is established here.

In the harmful group at H=64, all data gates abstain, but natural collection
still incurs mean advantage -4.082 credits versus default; the prior rule also
abstains. At H=100,000, the tight-service group has 9/60 ineligible pairs;
natural projection certifies 23/60 versus 5/60 for old three-contrast, with
zero observed false declarations. Projection-minus-old certification is +30
percentage points [18.3,41.7] and mean full-calendar gain difference is
+0.938 credits [0.317,1.589]. One hundred thousand 1.5-hour resets correspond
to about 17.1 simulated years, and results are not practical forecasts.

At H=3,000,000 in the fixed beneficial B world, natural/forced projection
certify 60/60 and 58/60, respectively; old three-contrast certifies 2/60 and
0/60. At the same extreme checkpoint, all 60 A-prime pairs are truly
ineligible, yet projection falsely certifies 60/60 natural and 58/60 forced;
the old three-contrast rule certifies none. A-prime's three observable choice
probabilities match B's but its true welfare is negative, and its third-only
shift violates the three-contrast model. The nominal guarantee does not apply
to A-prime. B and A-prime use independent group streams; natural and forced
are paired within group. The contrast illustrates dependence on the
choice–welfare link, not a failure of the stated conditional theorem.

The three-million-reset horizon is about 514 simulated years. Full-calendar
costs and service include collection, which can dominate the 32-reset
deployment. Confidence is per pair and per schedule under the fixed common-
shift conditional Bernoulli model; there is no joint 95% claim across schedules
or pairs, no pathwise service guarantee and no claim for misspecified shifts.
Finite-bit simulation approximates the ideal probabilities. Unadjusted paired
bootstrap intervals measure the simulated-pair sampling design, not uncertainty
about real users or physical calibration. Neither these comparisons nor the
projection implementation establish that it is the authors' PRISM method, a
mature-verifier benchmark, a general RL improvement, or a field result.
Full saved denominators, offer counts, service, latches and paired comparisons
are in `runs/heldout_20261028_v2/summary.json`; the audit records document the
remaining numerical and reproducibility limits.
