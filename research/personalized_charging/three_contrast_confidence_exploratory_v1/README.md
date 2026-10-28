# Exploratory three-contrast confidence gate

This standalone count-only prototype has not been used in a scientific run.
It uses the fixed P3c candidate/default physical model, with persistent
theta in [0,0.25], tau in [0.05,0.4] and an unrestricted **common** logit
shift c. The three known (price saving, added delay) contrasts are
(0.1,1), (0.1,0.5) and (0.2,1). The shift affects modeled choices only;
theta remains the normative linear delay cost. A contrast-specific shift is
outside the model and invalidates the nominal error guarantee.

Given observed (acceptances,total) for each contrast, the gate uses radius
`sqrt(log(120*n*(n+1))/(2*n))`. A two-sided Hoeffding bound spends
`1/[60*n*(n+1)]` on each contrast at count n. Summing over all n and the three
contrasts gives 3/60=0.05. Under the fixed conditional Bernoulli model and
predictable offer selection, this event covers all three probabilities at all
counts simultaneously. It is unconditional coverage for each fixed model, not
conditional coverage given a favorable result; separate drivers require error
budget accounting if a joint guarantee is desired.

Let l_j be the three logits. The exact common-shift equations give
`lambda=1/tau=10*(l_3-l_1)` and `v=theta/tau=2*(l_2-l_1)`. The gate constructs
outward intervals for lambda and v, intersects them with their prior ranges,
and obtains a conservative outer theta interval. It requires an independently
verified feasible central-probability model: the three observed empirical
proportions determine exact central lambda, theta, tau and c, and their outward
enclosures must fit the prior. An unresolved central witness leads to
abstention even if another feasible model might exist. Missing samples, bands
touching 0 or 1, nonpositive or empty inversion domains, and arithmetic
failures also lead to abstention. Counts must be integers up to 10^12.

The candidate benefit is `p*(.07-theta)+(1-p)*r*(.05-theta/2)` and its
expected unmet is `.005*(p+(1-p)*r)`; baseline expected unmet is zero. Benefit
decreases in theta and is bilinear in p,r at a fixed theta. The bound checks
all four probability corners at each theta endpoint, so it does not assume
that either benefit coefficient is positive. The service expression is
nondecreasing in p and r, so its upper probability corner is safe. ALLOW
requires strictly positive lower benefit and the candidate service upper bound
no larger than the specified per-episode allowance. Rectangular projection
overapproximates the common-model set and may be very conservative.

## Synthetic physical meaning of contrast 3

In a separate predeclared collection tariff, offer the first 1-kWh vehicle
slot 2 for 0.3 credits against its slot-0 fallback at 0.5, then default the
second request. This is a synthetic promotional collection price, not the
deployment tariff, which remains 0.5/0.5/0.4. A single 2-kW port and existing
commitments are respected. An accepted first offer reserves slot 2 and can
block a later urgent 1-kWh arrival with probability 1/200. The expected
collection advantage against default is `q3*(0.07-theta)` and expected
unmet is `q3/200<=1/200`; over H reset episodes the latter is at most H/200.
Record collection welfare cost and service separately from deployment. Retail
payments cancel in the equal-weight operator–driver system ledger, although
the private driver/operator accounts change. These are model consequences,
not empirical service or field-safety evidence.

## Deterministic controls and limitations

The two reviewed worlds A=(theta=.08,tau=.2,c=.2) and B=(2/35,1/7,0)
have identical first two logits (.3,.5), but third logits .8 and 1 and benefits
approximately −.0030955 and +.013062. The tests use rounded ideal probabilities
as deterministic arithmetic controls, not observations or simulated power.
For both B and a second favorable nonzero-shift control, 10^4 and 10^5 samples
per contrast abstain; 10^6 per contrast allow. A remains an abstention, with
an entirely negative benefit interval by 10^8 per contrast. This is neither
a guarantee on sample size nor a frequency or power result.

One contrast-specific violation makes A's third logit 1 while retaining its
first two logits. Its three probabilities then equal B's although their true
benefits have opposite signs. The tests explicitly demonstrate that this gate
cannot detect that violation; it must not be presented as safe under such
misspecification.

Python Decimal documents correctly rounded HALF_EVEN ln and sqrt; the gate
steps to adjacent representable values and uses outward arithmetic, sharing
the existing P3d interval implementation. Independent source and rounding
review, an independent implementation or checked proof artifact, predeclared
physical/collection simulation and strong matched comparisons are still
needed. Tests against high-precision point values do not prove whole-domain
arithmetic or empirical calibration, and this is not a new general
confidence-sequence construction.
