
# Independent replay of two-driver paired-bootstrap intervals

The existing two-driver held-out study's paired bootstrap was replayed from its
saved `checkpoints.jsonl` and checked against `summary.json`. This was an
analysis replay only: no simulated pairs or scientific outcomes were generated,
no result was used to retune the study, and no frozen source or artifact was
modified.

## Result

**PASS: all 1,134 paired estimates and 1,134 percentile intervals matched.**
All 2,268 interval endpoints matched exactly in the recorded NumPy 2.3.5
environment; the maximum absolute discrepancy was zero. The audit covered seven
groups, nine checkpoints, six paired comparisons per group/checkpoint and three
outcomes per comparison: lifecycle gain, certification and stop-path gain.
Each comparison retained its original 60 paired units.

For every group index `gi` and checkpoint index `ci`, the audit reconstructed
the declared 2,000 index vectors with
`PCG64(SeedSequence([55821762, gi, ci]))`, using the saved pair order 0–59.
It recomputed paired differences, resampled whole pairs, and checked the mean
and the linearly interpolated 2.5th and 97.5th percentiles. These are descriptive,
unadjusted intervals; reproducing their arithmetic does not establish nominal
coverage, a multiple-comparison claim or real-world validity.

The saved data and summary both matched their completed-run SHA-256 entries:

- `checkpoints.jsonl`: `60da1b8d51f74a4053565b53776cb03cbd58317456d39f249b8aaf2f85c45917`
- `summary.json`: `db96491d337635ad7cf70b028f8b86e9b2945e27eb1ba8aba8d4dc9f2b845184`
- `completed.json`: `d05805fa1a0534b3af38d6e6a87ad7a10aa97096bd79de21f636bcb5829c3091`

The separate replay script is preserved at
`../personalized_charging/two_driver_study_v1/audit_bootstrap.py`; its original
machine-readable receipt remains `/tmp/two_driver_bootstrap_replay_receipt.json`.
The audit script is a post-run check, not part of the frozen scientific source. The reproducibility check
is conditional on the saved records, fixed resampling procedure and compatible
NumPy implementation; it is not an independent rerun of the physical model or
the gate's shared interval arithmetic.
