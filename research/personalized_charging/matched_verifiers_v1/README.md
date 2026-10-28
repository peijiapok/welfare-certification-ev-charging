# Matched charging-verifier comparison

This separate simulation compares the prior p-only exact gate with an exploratory two-contrast interval verifier on identical operational response histories. The fixed five-group catalog, decision checkpoints, seeds, service accounting, resource caps and analysis are in `PROTOCOL.md`. The manifest hashes the study, its preflight tests and the imported project code. The node-capped continuous verifier shares interval arithmetic with the earlier P3d diagnostic; its replay checker does not constitute an independent interval library. The model remains a one-port, two-request synthetic construction, not real-driver evidence or an RL benchmark.

The study allows one scientific catalog attempt. A `completed.json` receipt, its output digest chain and the recorded artifact files are required for a complete result. A start marker with an incomplete or missing completion receipt denotes interruption; do not silently resume, overwrite the output or alter the frozen source and protocol to improve results. An exact seeded reproduction, if later needed, verifies the same study and does not create independent scientific evidence.

Run deterministic preflight from the repository root without running the held-out catalog:

```bash
python -m unittest personalized_charging.sequential_identification_v1.test_physical personalized_charging.sequential_identification_v1.test_certificate personalized_charging.continuous_certificate_exploratory_v1.test_comparator personalized_charging.continuous_certificate_exploratory_v1.test_proof_replay personalized_charging.matched_verifiers_v1.test_run -v
```

The study uses Python 3.13.11 and NumPy 2.3.5 on Linux. The manifest and environment metadata improve provenance but do not create a hermetic environment. Individual search and replay calls use a three-second cap and a created-node limit; mixture construction is outside the individual timer but inside the global wall limit. Catchable interrupt signals are handled; an uncatchable process kill cannot guarantee cleanup. Theoretical guarantees assume the ideal declared conditional choice model, whereas the numerical simulator uses pseudorandom finite-bit approximations. Under misspecification, the welfare-error guarantee is not claimed.
