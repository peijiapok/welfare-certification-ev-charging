# Exploratory two-driver, one-port comparison

This separately versioned prototype has not been used in a scientific run.
Two persistent drivers A and B have their own theta, tau and finite common
logit shift. In the fixed AB deployment target, A arrives first and B second;
the candidate offers A delayed slot 2, then offers B slot 2 only if A rejects.
The baseline defaults both. A suppressed B offer has no response label.

With known `a=g0-g2-delta*(W-g2)` and `b=g1-g2-delta*(W-g2)`, expected
candidate system advantage and urgent unmet are

    B_AB = p_A*(a-theta_A) + (1-p_A)*r_B*(b-theta_B/2)
    U_AB = delta*(p_A + (1-p_A)*r_B).

This factorization requires B's response after reaching the second offer to
remain Bernoulli(r_B) conditional on the full public history and A's rejection,
and the urgent-arrival law to remain the declared independent conditional law.
Role, clock time, opponent identity and earlier decisions must not alter a
driver's stated contrast probabilities; otherwise a different model is needed.

`gate.evaluate(counts, method=..., g0=..., g1=..., g2=..., W=..., delta=...,
epsilon=...)` accepts nested A/B observed-count dictionaries. The `two`
method requires p/r per driver and ignores optional third entries; `three`
requires all six driver/contrast streams. For each stream the outward radius
is `sqrt(log(240*n*(n+1))/(2*n))`, allocating 1/120 of error. A union bound
gives at most 4/120 for the four-stream rule and at most 6/120=.05 for the
shared six-stream event controlling both rules for one pair under the model.
Neither stream nor driver independence is needed for the union bound, but the
conditional Bernoulli exposure law is required for each stream. This is not
familywise coverage across pairs or conditional validity given a certificate.

The gate derives separate theta intervals and central feasible witnesses for
the two drivers, using the previously audited two-/three-contrast inversions.
It evaluates the four p_A/r_B corners at the upper theta endpoints for a
benefit lower bound and at lower theta endpoints for an upper bound. Service
uses the upper p_A/r_B corner. This rectangular relaxation is conservative;
all reused Decimal primitives are shared and still require independent audit.
Missing, noninterior, invalid or numerically unresolved states abstain. The
imported `gate.prior_only(**physics)` is the no-data sufficient rule; it
certifies pointwise positive gain under finite logits, not a uniform positive
margin over an unrestricted common shift.

## Shared collection calendar

`schedule.plan(index, variant)` uses zero-based indices and repeats this fixed
six-reset exogenous calendar:

| Reset | Role | Natural collection | Forced collection |
|---:|---|---|---|
| 1 | AB | first p_A | first p_A |
| 2 | BA | default first, then r_A | same |
| 3 | AB | first third_A | same |
| 4 | BA | first p_B | same |
| 5 | AB | p_A, then r_B only after rejection | default A, then r_B |
| 6 | BA | first third_B | same |

Thus forcing reset 5 can add r_B feedback but removes a p_A exposure. It is a
schedule/information tradeoff, not a one-variable causal experiment. All arms
must face the same exogenous roles and correctly coupled fresh innovations.
`schedule.prior_plan(index, certified)` applies the AB candidate on AB resets
and defaults BA resets only when the prior rule certifies; otherwise it always
defaults. A specified 32-episode deployment evaluation consists of fresh AB
resets, not a role-average target.

Each reset occupies three half-hour slots. A p or third collection offer of
driver i has expected gain `q_i*(a-theta_i)`; an r offer has expected gain
`q_i*(b-theta_i/2)`. The other driver's default remains feasible in that
reset, but an accepted delayed reservation can block the independent urgent
request. Any collection reset has expected unmet at most delta, so H resets
have a separate expected collection allowance H*delta. Epsilon applies to
deployment, not automatically to each collection reset. A six-reset cycle
requires at least nine modeled hours. Long synthetic horizons must not be
described as realistic field time or practical deployment evidence.

`physical.simulate` is an exact-rational reset with supplied probabilities and
uniform innovations, separate theta values, a guaranteed one-port calendar,
and an equal-weight operator/driver ledger. The third offer's .3 versus .5
promotion is a separate synthetic collection quote; other delayed offers
charge .4. Retail transfers cancel in the combined ledger, and W is assigned
to the operator account as an accounting convention. System costs use added
focal delay relative to default, so paired differences are valid while raw
costs are normalized. The caller must supply conditionally valid innovations.

Independent exact-Fraction tests check AB/BA paths, signed physical costs and
the 12-cell response/urgency law; other deterministic tests check six-stream
allocation, distinct theta values, suppressed feedback, no hidden gate input,
safe corner bounds and the two schedules. These controls do not establish
empirical power, solver independence, general multi-port behavior or field
effectiveness. Any future study needs a separately frozen protocol, a fresh
catalog and independent source/output review.
