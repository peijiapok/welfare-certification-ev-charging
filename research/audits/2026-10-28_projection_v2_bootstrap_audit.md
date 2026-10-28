
# Projection-comparison v2: bootstrap analysis replay

Two separate post-completion analysis replays checked the predeclared bootstrap
using saved v2 pair records and analysis seed 71960434; neither generated new
simulated pairs or inspected the incomplete v1 outputs. Across six groups,
nine checkpoints and 22 paired comparisons, 54 keyed 2,000-by-60 pair index
matrices determine 3,564 intervals and 7,128 endpoints. One replay matched all
endpoints exactly; the separately coded portable checker in
`../personalized_charging/independent_checks/projection_v2_bootstrap_audit.py`
reported no discrepancy within its documented 1e-10 absolute / 1e-12 relative
tolerances. Its machine-readable report records hashes and NumPy 2.3.5.

The matrices reproduce the same prescribed NumPy PCG64 analysis streams. The
intervals are descriptive and unadjusted; reproducibility is not an
independent random generator, a guarantee of statistical coverage or a causal
interpretation. The previously failed v1 attempt remains incomplete and is not
a source of evidence.
