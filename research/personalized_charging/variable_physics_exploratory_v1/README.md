# Variable known-physics charging extension

This exploratory, separately versioned code has not been used in a scientific
catalog. The p/r and optional third choice model, unknown common logit shift,
prior and alpha allocation are inherited from the audited two-/three-contrast
gates. Known synthetic g0, g1, g2, W, delta and epsilon are exact decimal
strings. Inputs must be nonnegative, delta must lie in [0,1], and strings are
limited to 80 significant digits and nonzero adjusted exponents in [−100,100]
to avoid unsupported extreme arithmetic; invalid or unresolved cases abstain.

The confidence gate reuses valid probability bands, theta outer bounds and a
verified witness even when the original-cost benefit/service decision abstains.
It computes outward coefficients

    a = g0 - g2 - delta*(W-g2)
    b = g1 - g2 - delta*(W-g2)

and bounds `B=p*(a-theta)+(1-p)*r*(b-theta/2)` with all four p/r corners at
each relevant theta endpoint. No coefficient sign is assumed. Candidate
expected unmet is `delta*(p+(1-p)*r)`; default expected unmet is zero.
Rectangular relaxation is conservative for correlated common-model sets.
Confidence, predictable selection and one-driver scope remain inherited from
the underlying gates. Arithmetic primitives are shared and require independent
review; no empirical safety, power, realism or general solver claim follows.

The separate `prior_gate.py` offers a no-data baseline. For finite logits,
`0<p,r<1`; if a>=.25 and b>=.125, at least one strictly, each branch's
benefit increment is nonnegative for all theta and at least one is positive.
It certifies pointwise B>0 only when epsilon>=delta. It does not assert a
uniform strictly positive margin over the unrestricted logit shift. If both
thresholds are equal, theta=.25 gives B=0 and the rule abstains.

The deterministic `physical.py` simulates a three-slot one-port reset using
exact rational supplied probabilities, uniforms and monetary parameters. It
stores public physical events and evaluator-only normalized cost accounts.
Default focal retail is .5, p/r delayed retail .4 and third-promotion retail
.3; a served urgent request pays .4. The penalty W is assigned to the
operator private account solely for this declared accounting convention.
Driver payments and operator receipts cancel exactly; system cost is
procurement plus added focal delay plus W once per unmet urgent kWh. Urgent
delay cost is zero. The caller supplies conditionally independent innovations
when drawing probabilistic conclusions.

For a p or third collection offer, expected advantage is q*(a-theta) and
expected unmet is delta*q; for r it is q*(b-theta/2) with the same unmet
formula. Collection service and welfare are separate from deployment. Cases
with W<g2 are valid mathematical stress tests but can make unserved demand
cheaper in the chosen system ledger, so service must be assessed separately.

Deterministic exact-rational enumeration covers positive, harmful, mixed,
zero/unit-arrival, tied-cost and W<=g2 scenarios, private-account cancellation,
and the original physical implementation. Point controls and unit tests are
not a representative parameter catalog, a power study, or real-world evidence.
