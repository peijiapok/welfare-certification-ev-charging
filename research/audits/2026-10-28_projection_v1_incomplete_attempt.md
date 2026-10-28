
# Projection comparison v1: incomplete held-out attempt

The separately frozen v1 comparison was started once and generated simulated
rows, but exited with status 1 during `summarize()` with
`KeyError: 'natural_prior'`. No `completed.json` or `summary.json` exists.
The source builds `natural_prior` and `forced_prior` (and similarly for
`default`) although the actual baseline keys are unprefixed `prior` and
`default`. This is a software/integration failure, not a scientific result.
The prior five completed studies and their artifacts were not changed.

The v1 protocol, source, manifest and partial output remain sealed. The
partial checkpoint file has 79,616,020 bytes and SHA-256
`e1e55370e83a952fc8554f5227c79fffcd8a1627a1b01f03cb70a627a7d8d1af`;
`started.json` SHA-256 is
`fb329e356cbea02b2da632a0980d7ca7fab93092c43f2b583dad40e00587c911`.
No analyst has inspected or used partial outcome values. The rows may contain
simulated decisions internally, so it would be false to say that no synthetic
data were generated. They are incomplete and excluded from the paper and
scientific summaries.

An independent source-only review concluded that a separately versioned,
transparently disclosed corrected protocol with distinct random seeds and a
new output directory is compatible with the project rule of one attempt per
frozen protocol. That would be a fresh prospective assessment, not completion
or silent replay of v1. It must keep scenarios, methods, checkpoints and
analysis fixed absent a documented methodological reason; never use v1 partial
outcomes for selection, and add a synthetic end-to-end summary/receipt test
covering every comparator before a new independent source audit and freeze.
Any v2 failure similarly remains incomplete; no automatic retry is authorized.

A separate v2 draft has now been implemented with fresh, searched master and
bootstrap seeds 71960433/71960434, a distinct future output directory and the
same scientific groups, schedules, checkpoints, alpha, targets and budgets.
It corrects the baseline key mapping and expands the preregistered paired
summary family to 22 comparisons, including each gate against both baselines
and prior versus default. This analysis expansion was chosen without inspecting
v1 outcomes; intervals remain descriptive and unadjusted. Its 53 deterministic
controls include a synthetic summary test covering all 22 named comparisons
and paired bootstrap values and a miniature end-to-end run of all receipt,
hash-chain and failure stages using no scientific seed. Its source is under an
independent read-only audit; no v2 source freeze or catalog has occurred yet.

A targeted independent v2 re-audit passed 60 deterministic tests and found no
freeze blocker. It checked all 22 declared pairwise comparisons, corrected key
mapping, fresh generation and bootstrap seeds, scientific settings, full
synthetic summary/receipt/hash-chain and failure fixtures, and transitive source
manifest. After the read-only lock was released, the protocol status label was
changed from draft to prospective, without changing its scientific substance.
The 30-source v2 manifest SHA-256 is
`531bb8011b6d452a5fa4092c479aa2ff8dd599df5fec9e5592be0a5a76f0f2e4`.
The single separately frozen fresh-seed v2 attempt has started. No v2 outcome
will be used before completion, receipt verification and independent audit.
