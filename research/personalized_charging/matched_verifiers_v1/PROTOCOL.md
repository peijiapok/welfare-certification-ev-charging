# Prospective matched sequential-verifier comparison

Status: **FROZEN before the one permitted scientific catalog attempt.** This is a
new exploratory simulation, informed by earlier work, not a revision or rerun
of sealed outputs. It uses fresh synthetic drivers and does not read any prior
held-out records. A valid source manifest is required before data generation.

## Model and population

The physical model, logit contrasts, two-offer candidate, default baseline,
and nominal benefit and expected unmet formulas are the fixed P3c model in the
imported physical simulator. There are five groups of 60 independent simulated
driver/world units. Draw theta and tau independently and uniformly within
each group's closed interval (continuous endpoints have probability zero):

| Group | theta | tau | deployment epsilon | actual behavior |
| --- | --- | --- | --- | --- |
| easy | 0–0.02 | 0.05–0.08 | 0.005 | nominal logit |
| low_information | 0–0.035 | 0.2–0.4 | 0.005 | nominal logit |
| mixed | 0.055–0.25 | 0.05–0.4 | 0.005 | nominal logit |
| tight | 0–0.1 | 0.05–0.2 | 0.0045 | nominal logit |
| misspecified | 0.11–0.2 | 0.05–0.2 | 0.005 | add 2 to both response logits |

The misspecified group does not satisfy the nominal likelihood assumptions.
Its actual benefit and service use the shifted response probabilities; neither
rule has its nominal benefit-error guarantee in that group. The simulation's
floating-point pseudo-random implementation approximates ideal Bernoulli
sampling and is not itself an exact finite-bit calibration proof.

Use PCG64 with master seed 80327941 for disjoint namespace keys indexed by
group, driver and stream type (theta, tau, and p/r/urgent innovations); use
seed 80327942 for the paired bootstrap. A driver receives 96 keyed innovations
per event stream, with collection and deployment indices disjoint. Each
collector and each evaluated gate uses the same relevant event innovation for
the same driver, episode and event. The two event types p and r have distinct
streams. Different seeds and pseudorandom streams do not mathematically prove
independence; driver/world independence is a simulation assumption.

## Matched collection and decisions

For each driver, simulate both a p-only collector and an alternating p/r
collector, beginning with p. Each offers exactly one feasible contrast per
reset episode for 64 episodes. Feed the *same observed collection history*
within a collector to both verifiers. No hidden parameter, unexposed response,
future draw, or evaluator loss enters either decision. At only episodes 16,
32, 48 and 64 evaluate both methods, latching the first favorable checkpoint.
Continue collecting after a crossing through episode 64. Both methods target
the same true statement B>0 and U<=epsilon. The p-only rule also asserts
B>161/41100 under its assumptions; report this extra margin separately.

* `p_only`: the exact alpha=0.05 one-sided p-response test in certificate.py;
  r responses do not enter its statistic. It requires epsilon>=0.005.
* `continuous`: the 25-point fixed pre-data mixture, all prefix constraints,
  shared-model interval boxes, 100-created-node cap and complete proof tree.
  An independent traversal checker must replay every completed ALLOW before
  a decision is latched. Both implementations share interval arithmetic.

The continuous evaluate **and replay together** have a per-call elapsed cap
of 3 seconds; construction of the fixed mixture just before that timer is not included in the reported per-call time, although it is included in the global wall limit. A timeout is a declared abstention, including timeout during
replay; a produced proof is retained with its timeout status if available.
Node cap, precision limit, no found witness and alleged counterexample witnesses
are distinct abstentions. Counterexample witnesses are schema-checked but not
independently verified and are labeled accordingly. Arithmetic failure, no retained boxes despite a
strict witness, invalid outputs, or replay rejection invalidate the run. A
node cap only counts created boxes, not mixture, witness or replay work.

For collection, the simple universal expected-unmet bound is 1/200 kWh per
episode. In the nominal tight group, a single offer has acceptance probability
at most sigmoid(2)<121/137, hence expected unmet below 121/27400<0.0045 per
episode, and at most 64 times this bound over collection. Collection and
deployment allowances are separate. These bounds are in expectation, not a
pathwise guarantee; the universal 1/200 bound also holds for the shifted
responses if the stated urgent-arrival process holds.

## Outcomes and analysis

Simulate 32 fresh deployment episodes under candidate if latched, otherwise
default. Both use the same event-indexed innovations as their default
counterfactual. Record the full 64-episode collection ledger, 32-episode
deployment ledger, and paired 96-episode advantage over always-default; the
physical simulator uses normalized focal delay, which cancels in paired
differences. Also record a counterfactual that defaults the remaining collection
episodes after the first crossing; absent crossing it uses all 64 episodes.

Save keyed p/r/urgent innovations and per-episode physical-event ledgers for
the paired default, paired candidate, each collection policy and each gate's
selected deployment. Each ledger contains policy, phase, driver and episode
indices, public event labels and normalized loss components; innovations and
losses are evaluator-only and are not controller feedback. Also save driver-level
truth, collection choices and observable feedback, each
checkpoint's decision/reason, first crossing, proof and replay status, gate
elapsed times and created-node counts where known, realized and expected
collection/deployment unmet, collection/deployment/lifecycle advantage and
the stop-at-crossing counterfactual. If a timeout interrupts node creation,
the node count is unknown, not zero. Save and hash all generated ALLOW proof
trees, including trees whose replay timed out, with input metadata and replay
status. Both matched verifiers consume the same history and budget.

Report each group, collector and gate's certification, abstention, and false
declaration counts and proportions, with Wilson 95% intervals. Stratify by
actual B<=0, 0<B<=161/41100, B>161/41100 and U<=epsilon versus U>epsilon;
report denominators and empty strata. Report p-only margin violations
separately. Report means of service, collection/deployment and lifecycle
advantage, first crossing, compute wall time and known-node count. Use 2,000
paired bootstrap resamples of driver units per group for paired differences
in certification and lifecycle advantage. Intervals are descriptive and not
adjusted for multiplicity. Sixty drivers per group cannot verify the nominal
error guarantee. Separate alpha guarantees do not imply a joint guarantee or
prove superiority; neither rule's acceptance region is assumed nested.

## Preflight, outputs and resource limits

Before freeze, pass deterministic physical, rational-test, proof-replay,
pairing, service-boundary, truth-denominator, source-manifest, timeout and
partial-output tests. Freeze the prospective protocol, runner, tests, parent
package imports, physical model, p-only certificate, interval comparator and
replay checker, and actual imported P3d interval primitives. Verify the exact
SHA-256 manifest before any scientific data generation and again afterwards.
Record Python/NumPy/platform information; this is not a hermetic environment.

Create a new output directory exclusively and never overwrite. Write a started
marker before generation, checkpoint per-driver records and proofs, hash
outputs after worker completion, and write a complete receipt only after
replay, analysis and source postcheck succeed. A separate supervisor applies
a hard 900-second wall target to the full run including generation,
verification, replay, analysis and output hashing. Catchable SIGTERM and SIGINT trigger worker termination and reaping where feasible; an uncatchable SIGKILL cannot guarantee cleanup. External interruption,
global timeout, invalid result or missing completion receipt is incomplete;
preserve partial artifacts, do not silently resume, retry or tune on results.
Catchable SIGTERM/SIGINT trigger worker termination/reaping and an incomplete
receipt where feasible. SIGKILL, machine failure and similar uncatchable events
cannot guarantee cleanup or a final receipt; a missing completion remains incomplete.
One started catalog attempt is permitted under this frozen protocol.
