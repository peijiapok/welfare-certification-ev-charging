# Six-study simulation research package

This package contains six completed, prospectively frozen synthetic simulation
studies, the working manuscript, their source and output receipts, independent
audit material and deterministic checks. No real charging sessions or people
were studied. The work does not establish a real-world or RL improvement.
The fifth study and prior studies are described in
`RESEARCH_PACKAGE_FIVE_STUDIES_20261027.md` and
`RESEARCH_PACKAGE_20261027.md`; their provenance limitations remain in force.

The sixth successful study is `projection_comparison_study_v2/`, with its
prospective protocol, frozen manifest and saved run. It compares the existing
data rules against `logit_polytope_exploratory_v1/`, an independently coded
Schnitzer-inspired theta-projection rule. The latter is not the published
PRISM tool or a full expression-wise verification method. The comparison uses
fresh simulated pairs, per-schedule shared confidence events, and separately
records a deliberately misspecified population. Its stress horizons are not
realistic deployment durations. All guarantees depend on the stated model.

The distinct `projection_comparison_study_v1/` attempt is intentionally
preserved **incomplete**: it failed during summary generation, has no
completion receipt, and is not evidence or an additional successful run. Its
partial simulated records were not analyzed for the v2 design. The disclosed
reason and v2 construction appear in
`../audits/2026-10-28_projection_v1_incomplete_attempt.md`. No prior
sealed scientific catalog is to be overwritten or retuned.

Verify six completed studies' frozen-source and output chains without generating
scientific data:

```bash
python personalized_charging/verify_research_package_six_studies_20261028.py
```

Run the five-study deterministic commands in the two earlier package READMEs,
then the new controls:

```bash
python -m unittest personalized_charging.logit_polytope_exploratory_v1.test_projector personalized_charging.logit_polytope_exploratory_v1.test_independent_geometry personalized_charging.projection_comparison_study_v2.test_run personalized_charging.projection_comparison_study_v2.test_audit_regressions personalized_charging.projection_comparison_study_v2.test_integration personalized_charging.independent_checks.test_projection_v2_bootstrap_audit -v
```

The independent stored-output, high-precision numerical and bootstrap audits
are post-run checks, not new independent scientific runs. Run them with:

```bash
python -m personalized_charging.projection_comparison_study_v2.audit_saved_outputs personalized_charging/projection_comparison_study_v2/runs/heldout_20261028_v2 personalized_charging/projection_comparison_study_v2/freeze_manifest.json
python audits/2026-10-28_projection_independent_numeric_audit.py --results personalized_charging/projection_comparison_study_v2/runs/heldout_20261028_v2 --manifest personalized_charging/projection_comparison_study_v2/freeze_manifest.json
python -m personalized_charging.independent_checks.projection_v2_bootstrap_audit personalized_charging/projection_comparison_study_v2/runs/heldout_20261028_v2 --manifest personalized_charging/projection_comparison_study_v2/freeze_manifest.json
```
 Their scripts and
Markdown receipts state exactly what they verify and what they share. The
numerical cross-check needs mpmath and is not a rigorous interval proof; seeded
bootstrap replay is descriptive and does not establish coverage. The source
and artifact checks identify the recorded environment but do not create a
hermetic installation. Actual publication requires authors to verify the work,
select a venue, provide genuine declarations and arrange external scholarly
review; no acceptance is implied.
