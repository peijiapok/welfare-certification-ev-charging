
# Independent numerical audit of projection-comparison v2

The independently written [mpmath audit](2026-10-28_projection_independent_numeric_audit.py) returned **PASS** on the completed v2 attempt. Its [separate JSON receipt](2026-10-28_projection_independent_numeric_audit_result.json) records the output. The audit was prepared before the v2 completion notice, used no scientific random draws and did not access incomplete v1 records.

It checked 3,240 saved rows, 6,480 projection-gate outputs and 12,960 driver projections, with 438,501 individual checks, zero failures and zero favorable decisions classified as numerically inconclusive at the configured tolerance. It independently reconstructed the six observed-count Hoeffding bands, finite logit inequalities and projected polygon intersections, then checked reported theta enclosures, feasible witnesses, welfare/service bounds, decisions, reasons and latches. It verified the v2 manifest binding, started-marker seed, checkpoint digest and record hash chain against the completed receipt.

This is a **100-decimal-digit mpmath numerical consistency diagnostic with relative-or-absolute tolerance 1e-28**, not a directed-rounding proof. It does not establish statistical coverage or independently audit the scientific RNG, physical accounting, bootstrap resamples, or the interval library. The hash-chain check is not an authentication signature. No scientific files or original receipt were changed.

Inputs and SHA-256 values:

- Audit script: `fd458253e098f5d41c062e4cf3aaef51eea3110e2a643d7a57870a2dbdff3bc5`.
- Audit JSON receipt: `60d674b7648752a996faee6bc5bdc64c72d089633943c317219ac9f898bf0bc3`.
- [V2 runner source](../personalized_charging/projection_comparison_study_v2/run.py): `188ae91a3d338aa2bae6cf0a37c3ede982e2f309955e9b88b5c799495b74b82d`.
- [V2 freeze manifest](../personalized_charging/projection_comparison_study_v2/freeze_manifest.json): `531bb8011b6d452a5fa4092c479aa2ff8dd599df5fec9e5592be0a5a76f0f2e4`.
- [Completed v2 receipt](../personalized_charging/projection_comparison_study_v2/runs/heldout_20261028_v2/completed.json): `acc24bbaef7eaf59498464a391a2b7659ea2abf4359d433ce26f7ef8a5ee6edc`.
- [Completed v2 checkpoints](../personalized_charging/projection_comparison_study_v2/runs/heldout_20261028_v2/checkpoints.jsonl): `bb08050e668cdd5aff2584404e2a3bc814bd79d0071106dbb4d09914c457538c`.
