# Independent verification scripts

These scripts recompute the quantities in Tables 2 and 3 and check the interval
implementation by methods independent of those used to produce them.

- `verify_gate_table.py` (needs `gates.py` in the same folder). Checks that each
  gate's crossing set is an upper set in s, and that its thresholds agree with
  50-digit mpmath evaluation: 2,197 horizons for the fixed gate, 589 for the
  mixture gate. The mixture integral is evaluated through the binomial-tail
  identity rather than scipy's incomplete beta. It then reruns the DP in 30-digit
  arithmetic and compares the results at n = 64 and 1024.
- `verify_benchmarks.py`. Recomputes the lower bounds and the exact binomial
  sample sizes (in 60-digit arithmetic), and checks every n up to 5000 for the
  "every larger n" claim.
- `verify_interval_enclosures.py PATH/research`. Runs the study's own gate code
  on 12,000 random and model-consistent count vectors, with n from 1 to 10^12,
  and checks every enclosure against 80-digit mpmath values. The enclosures
  checked are radius, band, logit, both theta sets, the welfare lower bound and
  the service upper bound.

Results (28 Oct 2026): 0 mismatches and 0 enclosure violations. The DP agrees
to within 1e-15. Every benchmark is reproduced: 323/637, 763-797, 1323-1360
and 3550.

Requirements: Python 3.10+, numpy, scipy, mpmath.
