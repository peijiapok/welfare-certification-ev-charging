# Matched verifier comparison: results

The one frozen follow-up completed in 265.85 seconds for 300 fresh synthetic drivers, 60 per group. An independent stored-output audit verified the frozen-source and artifact hash chains, 1,200 driver-method rows, 28,800 innovation triples, 115,200 physical episode ledgers, all recorded responses and costs, and every one of the 88 saved proof trees, with no discrepancies. It did not rerun the scientific catalog. The 46 deterministic preflight tests passed before freeze.

This is a small follow-up designed after observing the earlier study, with fresh seeds. Both rules saw the same data for each collector and used the same four checkpoints; the p-only rule additionally claims a stronger benefit margin. The 25-point interval verifier uses both feedback types, a 100-created-node cap and independent tree traversal, but the producer and checker share interval arithmetic. Its resource cap may cause abstention. Neither the nominal model guarantee nor conclusions about real drivers apply to the shifted-response group.

## Certification and false decisions

Each cell has 60 drivers. “False / ineligible” counts decisions when actual benefit is nonpositive or actual expected unmet exceeds the common allowance; a dash means there are no ineligible drivers in that group. The two rules use identical histories within a collector, although their decision regions are not assumed nested.

| Group | Collector | Exact p-only certified | Continuous certified | Exact false / ineligible | Continuous false / ineligible |
|---|---|---:|---:|---:|---:|
| easy | p only | 32/60 | 31/60 | — | — |
| easy | alternating | 21/60 | 8/60 | — | — |
| low information | p only | 0/60 | 0/60 | — | — |
| low information | alternating | 0/60 | 0/60 | — | — |
| mixed | p only | 0/60 | 0/60 | 0/54 | 0/54 |
| mixed | alternating | 0/60 | 0/60 | 0/54 | 0/54 |
| tight | p only | 0/60 | 0/60 | 0/25 | 0/25 |
| tight | alternating | 0/60 | 0/60 | 0/25 | 0/25 |
| misspecified | p only | 34/60 | 30/60 | 34/60 | 30/60 |
| misspecified | alternating | 20/60 | 19/60 | 20/60 | 19/60 |

For the easy group under p-only collection, the exact and continuous rules certified 32/60 (95% Wilson interval 40.9–65.4%) and 31/60 (39.3–63.8%), respectively. Thirty were certified by both; one only by the continuous rule and two only by the exact rule. Under alternating collection, the counts were 21/60 and 8/60. The paired difference in certification proportions was 21.7 percentage points (unadjusted 95% paired-bootstrap interval 11.7–31.7 percentage points), which describes this fixed sample and capped implementation; it is not a general proof that observing r is harmful or that either rule is optimal.

Neither rule certified any driver in the low-information, mixed or tight-service groups. In the misspecified group, with all 60 drivers truly ineligible, p-only collection led to false favorable decisions for 34/60 by the exact rule and 30/60 by the continuous rule; alternating collection led to 20/60 and 19/60, respectively. The interval rule is not robust to the deliberately incorrect choice–welfare link merely because its numerical bounds are conservative. Sixty drivers per group cannot establish a 5% error guarantee, and no nominal benefit guarantee is claimed under misspecification.

## Collection-inclusive welfare and service

| Group | Collector | Exact lifecycle advantage | Continuous lifecycle advantage | Expected collection unmet (64 episodes) |
|---|---|---:|---:|---:|
| easy | p only | +4.622 | +4.537 | 0.2577 |
| easy | alternating | +3.947 | +4.234 | 0.2595 |
| low information | p only | +0.568 | +0.568 | 0.1828 |
| low information | alternating | +0.349 | +0.349 | 0.1840 |
| mixed | p only | -4.077 | -4.077 | 0.1402 |
| mixed | alternating | -3.142 | -3.142 | 0.1560 |
| tight | p only | -1.685 | -1.685 | 0.1889 |
| tight | alternating | -1.238 | -1.238 | 0.1986 |
| misspecified | p only | -7.547 | -7.241 | 0.2582 |
| misspecified | alternating | -5.417 | -5.114 | 0.2727 |

Lifecycle advantage is mean credits against always-default over the same 64 collection and 32 deployment episodes. Both rules share the full collection ledger within a collector. The mixed group incurred losses despite no deployment: −4.077 credits for p-only collection and −3.142 for alternating collection. Expected collection unmet sums the per-step model expectations along each observed action path; it is not a pathwise cap. Full realized and expected service, stop-at-crossing counterfactuals, truth strata, paired intervals, checkpoint statuses and compute metrics are in `runs/heldout_20261027_v1/summary.json` and the driver/event records.

The 100-node cap was reached on many checkpoint calls, including 120 of the 240 easy p-only-collection continuous checks; subsequent latched checkpoints are included in that denominator. Counts of witness-based abstentions are explicitly unverified witness labels, not validated counterexamples. Gate wall times include verification but exclude fixed-mixture construction immediately before the timer, and cannot establish implementation-independent solver speed. The result supports no broad algorithmic or RL improvement claim.

## Provenance and limitations

Read `PROTOCOL.md`, `freeze_manifest.json`, `runs/heldout_20261027_v1/completed.json` and `output_hashes.json` for the fixed design and digest chain. The original first-study manifest omitted parent package files; this follow-up included them, but neither environment is fully hermetic. Uncatchable termination can defeat cleanup. The verifier and replay checker use shared interval arithmetic and formulas, the third-contrast identification result is analytical and was not tested here, and the toy model does not establish multi-driver, multi-port or real-world performance. These results alone do not establish publication readiness.

[Matched decision figure](figures/matched_decisions.png) and [plotting code](plot_results.py) use only stored outputs; all favorable decisions in the misspecified group are false.
