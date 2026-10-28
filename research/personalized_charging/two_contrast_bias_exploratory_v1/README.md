# Exploratory two-contrast common-bias gate

This count-only prototype compares the fixed P3c candidate and default policy.
It has not been used in a scientific run. It uses p/r acceptance counts,
the same alpha/3 Hoeffding bands and the same outward Decimal probability,
logit, benefit and service helpers as the exploratory three-contrast gate.
It does not receive theta, tau, c, hidden utility, or third-offer observations.

For unrestricted common logit shift c and a fixed (theta,tau) in the P3c
prior, `k=2*(logit(r)-logit(p))=theta/tau`. Intersect the outward k interval
with [0,5]. For each fixed feasible k, the sharp prior theta range is
`[k/20, min(1/4, 2*k/5)]`. Applying those endpoints to the outer k interval
therefore covers all compatible common-shift models. The probability and
theta rectangle is an overapproximation, so benefit bounds may be loose.

The gate also requires a verified empirical-center model: derive an outward
interval for k from the two exact empirical proportions; require that interval
to lie in [0,5]; set lambda=20, tau=.05 and theta=k/20; and choose the common
shift to reproduce the first empirical logit. Boundary, missing, invalid,
empty or unresolved inputs abstain. The common-shift model, prior, and
conditional response law remain assumptions, not findings from the data.

The benefit bound uses all four p/r corners at both theta endpoints, so it
does not assume that the coefficients are positive. Expected candidate unmet
is bounded at the upper p/r corner and baseline unmet is zero. ALLOW requires
positive lower benefit and candidate service at or below the chosen allowance.

Each stream's two-sided confidence error is bounded by 1/60 across all its
sample counts. Using p and r alone spends at most 2/60, conservatively below
0.05. When both this gate and the three-contrast gate use the **same** p/r
streams and correctly specified common-shift model, the three-stream
simultaneous coverage event costs at most 3/60=.05 and covers both rules for
one driver. This does not give a joint guarantee for multiple drivers or
under contrast-specific shifts.

The reviewed A=(.08,.2,.2) and B=(2/35,1/7,0) worlds have the same p/r
probabilities but opposite benefit signs. Whenever their common probabilities
are inside both confidence bands, the compatible model set contains both and
the gate must abstain. The deterministic rounded-probability tests abstain for
these controls through 10^12 observations per contrast. An exceptional
noncoverage history can still yield a false declaration; the statement is not
a pathwise or unconditional impossibility of false certification.

No empirical service, power or field-effectiveness claim follows. Existing
three-gate and P3d interval routines are shared, so passing tests do not supply
independent numerical replication. Source and rounding audit, especially of
logit enclosure and the reused helper functions, remains necessary.
