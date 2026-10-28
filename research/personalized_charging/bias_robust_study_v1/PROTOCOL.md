# Prospective common-bias charging certification study

Status: **FROZEN before the one permitted 360-driver scientific catalog attempt.** This is a new simulation-only study informed by prior exploration. It
does not read prior held-out records or developer-only review files at runtime.
Its binary choices, physical dynamics and welfare interpretation are assumed.

## Groups, checkpoint horizons and observed choices

Use 60 independent synthetic driver/world units in each group, with master
PCG64 seed 94613011 and bootstrap seed 94613012. Unless fixed below, draw theta,
tau and the common logit shift c independently and uniformly on the stated
intervals. Group A-prime adds 0.2 **only** to the third response logit.

| Group | theta | tau | c | deployment epsilon |
|---|---|---|---|---|
| beneficial | [0,.03] | [.08,.18] | [−.2,.2] | .005 |
| harmful | [.15,.25] | [.1,.3] | [−.2,.2] | .005 |
| A | .08 | .2 | .2 | .005 |
| B | 2/35 | 1/7 | 0 | .005 |
| tight | [0,.1] | [.05,.2] | [−.2,.2] | .0045 |
| A-prime | .08 | .2 | .2 | .005 |

These epsilon values apply to deployment only. Collection has a separate
universal expected-unmet allowance H/200 over H reset episodes. In particular,
the tight group's .0045 deployment allowance is not claimed as a per-collection
bound when c ranges over [−.2,.2].

Collection cycles p, r, third in that order, with no intra-block adaptivity.
Total episode checkpoints are 16, 64, 256, 1024, 4096, 12288, 100000,
1000000 and 3000000. Both gates see the identical realized cumulative p/r
counts; the three-contrast gate also sees third counts. The final three
checkpoints are **extreme synthetic stress tests**. At 1.5 hours per reset,
three million episodes represent about 514 years for one port and have an
H/200=15000 kWh universal expected-unmet bound. These are consequences of
the toy assumptions, not operational or real-world recommendations. There is
no within-block observation, adaptive stopping or confidence check.

For each checkpoint block and offer type j, with m scheduled observations,
draw K~Binomial(m,q_j), U~Binomial(K,.005), and V~Binomial(m−K,.005), using
separate PCG64 streams keyed by seed, group, driver, block, contrast and draw
type. The conditional U and V draws are independent given K. The aggregate
counts have the ideal iid acceptance/urgent joint distribution at block
boundaries, provided urgent arrivals are independent of choices; NumPy's
finite-precision sampler approximates that ideal law. Save keys and counts.
Model drift, response/urgency dependence, and within-block decisions are not
addressed. The third collection offer uses price .3 versus fallback .5 for
the same first-request slot-2 schedule; deployment keeps original pricing.

For p or third, realized collection advantage over default is
`K*(.168−theta)−19.6*U`; for r it is `K*(.148−theta/2)−19.6*U`.
Realized unmet is U, total urgent arrivals U+V, and added delay loss is
theta*(K_p+K_third+K_r/2). Expected unmet is `.005*m*q_j`. Record the
physical ledger and focal discounts; retail payments cancel only
under the specified equal-weight operator–driver boundary.

## Verifiers, deployment and outcomes

The two-contrast gate uses p/r counts and the three-contrast gate uses all
three. They share the same alpha/3 Hoeffding bands. The two-contrast rule uses
only two such bands, so its simple union-bound failure probability is at most
2/60, more conservative than .05; it does not individually spend all .05.
Under the nominal common-shift conditional model, the three-stream simultaneous
confidence event has coverage at least .95 per fixed driver and covers both
rules; this is not a joint guarantee across drivers. A-prime violates the common-shift
model and has no nominal guarantee. Its p/r and third probabilities match
world B, but its true welfare is computed from its own theta and actual p/r.
No superiority, new general inference technique, or field claim is made.

At every checkpoint compute both outward gate outputs from current counts,
and latch each rule's first favorable decision. Continue collection after
crossing. At each checkpoint simulate 32 separately keyed, shared candidate
and baseline deployment episodes; the gate selects candidate only if latched.
Compute true B and U from actual p/r and theta even in A-prime. Record full
collection-plus-deployment advantage and service, plus a checkpoint-level
counterfactual that stops collection at the first favorable checkpoint. These
are paired normalized ledgers; no within-block early stop is asserted.

Save groups, driver parameters/truth, block counts/keys, gate input counts,
outward bounds/reasons, decisions/times, first crossing, collection and
deployment costs/service, full and stop-counterfactual lifecycle results, and
resource metadata. For every group, gate and checkpoint report certification,
abstention, false declarations and null denominators, Wilson intervals,
benefit/service strata, first-crossing and welfare/service statistics. Use
2,000 paired bootstrap driver-unit resamples for certification and lifecycle
differences. Intervals are descriptive and not multiplicity-adjusted.

## Controls, freeze and execution

Before any freeze or scientific catalog: pass both existing gate suites and
independent deterministic controls for small-n aggregate joint probabilities,
direct physical path enumeration, periodic counts, keyed streams and pairing,
shared alpha, 0/1 count boundaries, A-prime versus B, truth and ledgers,
manifest integrity, output digests and signal cleanup. Any arithmetic failure,
invalid gate output or failed source postcheck makes the run incomplete.

A manifest must cover this protocol, runner and tests, both gate sources and
their tests, actual shared interval primitives, physical simulator and tests,
and all parent initializer/import sources. Verify it before any RNG is used
and again after the worker finishes. The runtime does not read dev-only notes.
Require a new exclusive output directory and write a started marker, partial
records and a completion receipt only after output hashes and source postcheck.
The 600-second wall budget charges the initial manifest verification, but the
internal watchdog cannot preempt that initial verification: its elapsed time
is checked after verification returns. If verification never returns, external
intervention is required; no catalog data are generated and an output marker
need not exist. Once started, the watchdog covers generation, analysis and
output hashing; before generating any catalog data, the worker enforces an
address-space soft limit of at most 4 GiB or fails closed as incomplete. This
requires POSIX resource limits and may be incompatible with some environments.
Catchable SIGTERM/SIGINT terminate and reap the
worker and write an incomplete receipt where feasible. SIGKILL or machine
failure cannot guarantee cleanup; missing completion means incomplete. Never
silently resume, retry or tune a started catalog.
