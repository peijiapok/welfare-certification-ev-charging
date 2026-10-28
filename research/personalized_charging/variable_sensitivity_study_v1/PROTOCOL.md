# Prospective variable-physics sensitivity study

Status: **FROZEN before the one permitted scientific catalog attempt.** This is a
separate simulation-only study of a known one-port, two-request model, informed
by prior exploration. Runtime reads no developer-only review files or prior
held-out results. The three rules share the same target B>0 and U<=epsilon,
but have different sufficient conditions and are not claimed nested or optimal.

## Fixed population and physics

Use 60 independent synthetic driver/world units per group, master seed
83269021, bootstrap seed 83269022. Nonfixed theta, tau and common shift c are
independent uniform on [0,.25], [.08,.3], [−.2,.2], unless stated otherwise.
All physical values below are known exact decimal strings in credits/kWh and
known probabilities. Epsilon is the per-deployment-episode allowance;
collection has its separate universal H*delta expected-unmet allowance.

| Group | g0,g1,g2 | delta | W | epsilon | driver rule |
|---|---|---|---|---|---|
| prior_positive_1 | .8,.65,.4 | .005 | 20 | .005 | standard |
| prior_positive_2 | .82,.70,.45 | .02 | 5 | .02 | standard |
| harmful | .568,.548,.4 | .005 | 20 | .005 | theta uniform [.15,.25] |
| near_zero | .61,.571,.45 | .02 | 5 | .02 | standard conditional on abs(true B)<=.002 |
| tight | .75,.65,.45 | .01 | 10 | .0085 | standard |
| low_penalty | .51,.46,.5 | .02 | .2 | .02 | theta uniform [0,.12] |
| A | .61,.571,.45 | .02 | 5 | .02 | theta=.08, tau=.2, c=.2 |
| B | .61,.571,.45 | .02 | 5 | .02 | theta=2/35, tau=1/7, c=0 |
| A_prime | .61,.571,.45 | .02 | 5 | .02 | A, with +.2 added only to third logit |

Near-zero parameters use a prespecified per-driver sequence of independently
keyed candidate draws, accepting the first whose floating-point computed
abs(B)<=.002; at most 10000 candidates are allowed and failure invalidates the
run. This is a conditional sample and cannot represent the unconditional
driver population. Save attempt and keys. A-prime's probabilities match B's
but its true theta and welfare match A; the third contrast violates the
common-shift model. No nominal three-gate coverage or joint guarantee applies
to that group.

## Periodic collection and coupled counterfactuals

Collection cycles p, r, third in order, with checkpoints 16, 64, 256, 1024,
4096, 12288, 100000, 1000000 and 3000000. The last three are extreme synthetic
stress tests: three million 1.5-hour reset episodes are about 514 years, and
H*delta=60000 kWh at delta=.02. They are not deployment recommendations or
field forecasts. No within-block timing, adaptive scheduling or early stop is
observed or inferred. The third collection tariff is .3 versus .5 fallback;
the deployment tariff and paired candidate/default policies remain unchanged.

In each fixed block of each offer, the evaluator generates one multinomial
count vector over 12 categories: one shared first-request uniform has states
`u<p`, `p<=u<q3`, `u>=q3`, crossed with an independent r-response bit and
independent urgent-arrival bit. These probabilities require p<=q3 and fixed,
conditionally iid probabilities within the block. The positive third-only
shift also satisfies p<q3. The common-random coupling is a simulator choice,
not a claim about real-world potential outcomes; NumPy finite-bit sampling
approximates the ideal multinomial law. Only the response for the actually
offered contrast is passed to the data gates. Unoffered category outcomes and
true preferences are evaluator-only, retained to reconstruct matched costs.

From each category compute observed offered K, blocked urgent U and served
urgent V, plus paired candidate and collection costs, unmet and focal delays.
Retail transfers cancel in the equal-weight operator–driver system ledger;
the urgent penalty W is charged once. W<g2 is a labeled synthetic stress case
whose welfare ledger can reward nonservice; service is assessed separately.
Use the same model/physical categories for both data gates, the prior rule and
always-default baseline. No gate receives hidden potential responses or truth.

## Rules, lifecycle and analysis

Two- and three-contrast gates use the same per-contrast alpha/3 Hoeffding
bands. The two-band simple union failure bound is 2/60; under the fixed common
shift and declared iid model, one simultaneous three-band event of coverage
at least .95 controls both data rules per driver. This is not familywise
across drivers and does not cover the three-gate in A-prime. Interval
arithmetic is shared, and numerical simulation only approximates ideal laws.
The no-data prior rule deterministically certifies pointwise B>0, not a
positive uniform margin, when its directed physical and service tests pass.

Latch each data rule at its first favorable checkpoint, but continue actual
collection through each H for the primary path. For each H, compare against
the same always-default H+32 calendar; a data rule collects H then deploys its
latched candidate or default for 32 independently keyed, matched episodes.
The prior rule uses candidate from the start of that full calendar if it
certifies, otherwise default. The stop-at-checkpoint counterfactual switches a
data rule to candidate after its first favorable checkpoint, using the same
evaluator-only candidate potential outcomes for every remaining episode up to
H, then the same paired deployment; it does not discard remaining time.

Save world/physics and true B/U; parameter, block and deployment keys; joint
evaluator category counts; observed-only gate counts, outward bounds, reasons,
times and first crossing; full and stop-path collection, policy and deployment
gain, normalized loss, realized/expected unmet and focal delay. Record per-rule
realized total service and welfare on the full calendar, including prior-rule
candidate actions. Summarize by group/rule/checkpoint certification, false and
null counts, Wilson intervals, benefit/service strata, resources and first
crossing. Use 2000 paired bootstrap driver-unit resamples for certification
and lifecycle differences, with unadjusted descriptive intervals. There is no
claim of field performance, empirical safety, superiority, or new inference.

## Freeze, controls and limits

Before any scientific RNG, verify a manifest covering this protocol, runner,
tests including `test_joint_independent.py`, both generalized gates, their
dependencies and tests, shared P3d interval code and all parent package
initializer/import sources. Run the exact 12-category independent physical
controls and deterministic tests for pairing, zero/one and signed-penalty
boundaries, rejection selection, gate isolation, lifecycle and source/output
integrity. A 4-GiB address-space soft cap must be enforced before catalog RNG
or the worker fails incomplete. Use a new exclusive output directory, started
marker, partial records and only a postchecked, hashed complete receipt.

The total wall budget is 600 seconds including input verification, generation,
analysis and hashing. Initial manifest verification is charged to the budget
but not internally preemptible; if it hangs, external intervention is needed
and no catalog data are generated. Once the worker starts, a watchdog and
catchable SIGTERM/SIGINT terminate and reap it and mark incomplete where
feasible. The supervisor temporarily blocks these signals while creating the
worker, so a stuck fork/start cannot be interrupted by the internal alarm until
the signal mask is restored; pending signals trigger cleanup after restoration.
External SIGKILL or machine failure cannot guarantee cleanup; missing a
complete receipt is incomplete. Any math/selection failure or timeout is
incomplete. A started catalog is never silently resumed, retried or retuned.
