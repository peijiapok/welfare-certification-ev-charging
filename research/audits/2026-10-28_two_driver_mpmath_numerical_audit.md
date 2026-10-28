
# Independent high-precision check of saved two-driver gate outputs

28 October 2026. This is a **numerical cross-check, not a rigorous proof**.
It reads the completed fifth-study checkpoint artifact and uses saved offered
counts and known physical inputs; it does not use hidden driver parameters,
regenerate draws, run an experiment, or modify the frozen study. JSON rows
also contain evaluator truth, but the script consults only their known physics
and metadata in addition to observed counts and gate outputs.

Script: `dev_planning/2026-10-27_two_driver_mpmath_check.py`
SHA-256: `daf831fbde34d2772959af73d0237cfb517a4fa3aa4a632385cb3bc57bd86f7b`.

Machine-readable output: `dev_planning/2026-10-28_two_driver_mpmath_numerical_audit.json`
SHA-256: `a0df5a059f13fd4e4493ea8d1f5e1d86791a21b8f23138e3cebde5e54db1d836`.
It was saved from a second deterministic pass over the same stored artifact;
the counts and zero-discrepancy result agree with the initial pass.

Input: `personalized_charging/two_driver_study_v1/runs/heldout_20261027_v1/checkpoints.jsonl`
SHA-256: `60da1b8d51f74a4053565b53776cb03cbd58317456d39f249b8aaf2f85c45917`.
Environment: Python 3.13.11, mpmath 1.3.0, 110 decimal digits. Comparisons
allow absolute numerical tolerance 1e-75. The script imports neither the
study's gate nor its interval arithmetic. The tolerance and arbitrary-precision
transcendental calculations are numerical tools, not certified enclosures.

The script independently reconstructs each available six-stream Hoeffding
band using `sqrt(log(240*n*(n+1))/(2*n))`, checks saved outward bands, and
reconstructs each driver's two-/three-contrast theta inversion. Where the saved
result includes a central witness, it independently derives its empirical
logits, temperature, theta and shift, checks its prior feasibility and checks
the saved witness intervals. It recomputes known-physics coefficients and
evaluates all four p_A/r_B corners at the relevant theta endpoints, and checks
the saved benefit/service enclosures and raw ALLOW/abstention conditions.
For witness-abstention rows that do not save bands, the inversion is checked
against bands independently reconstructed from counts. It also checks the
no-data prior rule's coefficients and sufficient ALLOW condition and verifies
that saved first-crossing/latching fields match the raw decision sequence.

Results: **zero numerical discrepancies** among 3,780 rows and 15,120 raw
gate outputs. The main check counts were:

| Check | Number |
|---|---:|
| Saved probability-band enclosures | 69,082 |
| Driver theta outer enclosures | 19,994 |
| Central witness prior-domain checks | 17,932 |
| Benefit rectangle and service enclosures | 8,966 each |
| Raw favorable decision conditions | 1,562 |
| Gate latching consistency | 15,120 |
| Prior coefficient/service checks | 3,780 each |
| Prior favorable sufficient conditions | 540 |

Raw gate reasons were 7,370 benefit abstentions, 1,031 central-witness
abstentions, 228 missing-stream abstentions, 4,895 noninterior-band
abstentions, 1,562 ALLOWs and 34 service abstentions.

This check does not prove the correctness of the physical or behavioral
model, time-uniform statistical coverage, every possible input, numerical
rounding of the original interval implementation, causal validity of the
simulated coupling, or field effectiveness. It does not evaluate whether the
latent truth lies in a confidence set and does not replicate the scientific
random generator or bootstrap. Shared counts and physical assumptions remain;
the computation is independent of the original arithmetic implementation,
but mpmath's numerical values and the 1e-75 tolerance are not formal proof.
