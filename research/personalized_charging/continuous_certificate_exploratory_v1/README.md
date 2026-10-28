# Exploratory two-contrast continuous-domain comparator

This is a separate research prototype for the fixed P3c single-port model. It
does not alter the sealed sequential study and has not been used in a held-out
scientific run. It compares the fixed candidate with the always-default policy;
it is not a general policy optimizer or a mature independent solver baseline.

The input history contains actual, predictably selected p and r offers and
their accept/reject responses. Given fixed pre-data mixture weights on the
continuous prior, the interval implementation constructs alpha times the
mixture likelihood at every prefix. It retains boxes unless some prefix
provably excludes the whole box. The surviving boxes cover the strict
intersection of likelihood-ratio confidence sets. They are split until every
retained box has positive lower benefit and service upper bound within the
specified allowance, or the node/precision limit is reached. The test requires
a separately verified strict in-prior feasible point, and abstains on a
counterexample, no such witness, numerical failure or unresolved boxes.

All objective and service calculations use the same theta/tau box, preserving
the common-model requirement; natural interval dependency can be conservative.
The service upper bound is additionally intersected with the analytic prior
bound of 0.005 kWh. A fixed 25-point, equal-weight mixture is supplied for
prospective exploratory use. The point-alternative regression mixture and the
99%/1% mixture used in one unit test are separate constructed controls; they
are not descriptions of that prospective mixture.

The all-acceptance known-answer sequence uses p, then r, then eleven p offers.
The 99%/1% control places 99% weight at (theta,tau)=(0,0.05). If p<=352/525,
its likelihood ratio is strictly larger than
`(99/100)*(21/16)^12*(22/25)>20`; hence the final confidence set excludes
those models, and the P3c inequalities imply benefit greater than
161/41100 credits. This is a selected mathematical control, not an empirical
power or frequency estimate. The prior and two-acceptance controls abstain with
a strictly verified negative-benefit witness.

The intended time-uniform error argument is the standard fixed-mixture
likelihood-martingale argument, assuming persistent parameters, the specified
conditional response law, feasible predictable offer selection and exact
model-independent physical dynamics. The proof is conditional on those
assumptions and does not cover response misspecification or multiple drivers
without an error-budget adjustment. Collection service must be budgeted
separately from deployment service.

Every completed ALLOW result now emits a tree of root-covering subdivisions,
excluded boxes and accepted boxes. A separate checker recomputes the likelihood
threshold and every leaf bound, verifies exact child partitions, checks the
strict feasible witness and supplied history, mixture and service metadata,
and rejects incomplete or resource-limited results. Its tests include mutated
trees, JSON round trips and mixed accept/reject histories. Arithmetic-failure
results record the number of boxes created before the exception.

**Remaining proof and engineering obligations:** independently inspect the
whole solver, replay checker and imported P3d Decimal primitives; verify their
rounding and statistical assumptions; define behavior and resource limits for
very long histories; and test a predeclared range of cases. Replay independently
checks tree structure and recomputes bounds, but both implementations use the
same interval library. Thus the tests and tree replay are not independent
verification of interval arithmetic or independent solver replication. The
only enforced resource budget is a node-count cap; there is no time or memory
cap, and termination with a decision is not guaranteed near a boundary. The
count covers created subdivision boxes, not mixture-threshold or witness work.

For a mixture of M support points, H observations and N evaluated boxes, the
basic arithmetic work is O(MH+NH), excluding refinement and precision costs.
Repeating a fresh search at every prefix may increase this to O((M+N)H^2).
The number of required boxes can grow quickly and is not bounded by those
expressions; time, memory and finite-precision limits can force abstention.
