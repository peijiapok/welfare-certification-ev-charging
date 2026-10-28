# Prospective projection comparison in a two-driver shared-port simulation

Status: V2 PROSPECTIVE, frozen by its source manifest before its catalog draw.
The frozen v1 attempt failed
in summary generation with a `natural_prior` key error and produced no
completion receipt. Its partial outputs have not been read or analyzed for
this revision. V2 corrects summary keys, uses a fresh seed namespace and a new
exclusive output directory; scientific scenarios, calendar and checkpoints are
unchanged and were not adapted to v1's partial outcomes. This simulation-only
study requires an independent source, protocol, numerical and accounting audit
before freeze. Earlier completed studies informed scenario selection; previous
results are never consulted by runtime.

## Model and experiment

Each independent unit is a synthetic pair A,B. Each driver's theta, tau and
finite choice shift are driver-specific and fixed across resets; the shift is
common across that driver's contrasts. The two drivers may have equal values. A single 2-kW port has three half-hour
slots per reset; each driver requests 1 kWh. In an AB reset A defaults to slot
0, B to slot 1, and the candidate offers A slot 2 then offers B slot 2 only if
A rejects. No unoffered response is observed. Urgent 1-kWh arrival at slot 2
has independent probability delta and unserved penalty W; g0,g1,g2 are known
unit procurement costs. Utilities include delay costs and all monetary
transfers cancel in the equal-weight aggregate system ledger. Target AB welfare
advantage and expected urgent unmet are B=p_A(a-theta_A)+(1-p_A)r_B(b-theta_B/2)
and U=delta[p_A+(1-p_A)r_B], with a=g0-g2-delta(W-g2),
b=g1-g2-delta(W-g2). A favorable declaration targets B>0 and U<=epsilon, not
individual fairness, realized service guarantees, or physical-world validity.
The response model assumes predictable reach, fresh conditionally Bernoulli
responses, and the declared fixed logit law and stationary preference over
all resets; all are simulation assumptions.

Use 60 independent pairs per group, master seed 71960433 and bootstrap seed
71960434. An exact-text search of existing research files found neither seed.
Separate keyed PCG64 streams distinguish parameters, blocks, deployment and
bootstrap draws. The fifth runner is not imported: its seed and constants
cannot drive generation here. For ordinary groups each user's theta, tau, and common shift are
independent uniform on the stated theta interval, [.08,.3], and [-.2,.2].
Known physics is stated as exact decimal strings. Values represent synthetic
credits/kWh and probabilities, not empirical calibration.

| Group | g0,g1,g2 | delta | W | epsilon | user parameter rule |
|---|---|---|---|---|---|
| prior_positive | .8,.65,.4 | .005 | 20 | .005 | theta uniform [0,.25] |
| positive_mixed | .568,.548,.4 | .005 | 20 | .005 | theta uniform [0,.12] |
| harmful | .568,.548,.4 | .005 | 20 | .005 | theta uniform [.15,.25] |
| tight | .75,.65,.45 | .01 | 10 | .0085 | theta uniform [0,.25] |
| B | .568,.548,.4 | .005 | 20 | .005 | A=(2/35,1/7,0), B=(1/14,1/7,0) |
| A_prime | .568,.548,.4 | .005 | 20 | .005 | A=(.08,.2,.2), B=(.10,.2,.2), +.2 on each third-only logit |

Tuple order is theta,tau,common shift. The first and second contrast logits
for each named driver agree in A and B; the third logits agree in A_prime and
B. In A_prime the common-shift assumption used by the three-contrast gate is
false; its nominal three-contrast guarantee does not apply. These fixed cases
are constructed identifiability/misspecification stresses, not random samples
from a population of real drivers.

## Collection and inference

Use an exogenously alternating AB, BA six-reset calendar: (1) AB offer p_A,
(2) BA default B then offer r_A, (3) AB offer third_A, (4) BA offer p_B,
(5) AB natural candidate p_A then r_B only after A rejects, (6) BA offer
third_B. All unoffered users default. The forced schedule changes only reset
5 to default A and offer r_B. All data gates in a schedule receive exactly the
same offered-response history, and the two-contrast gate ignores third labels.
The third tariff is .3 vs default .5, but retail transfers cancel. Forced and
natural schedules differ in information *and* action cost: a tradeoff, not an
isolated causal treatment of sample count. Counts only advance when offered.

Allocate .05/6=1/120 to each driver's three contrast streams. Hoeffding bands
have radius sqrt(log(240*n*(n+1))/(2*n)); a union bound gives simultaneous
coverage at least .95 per pair for all three rules within each fixed collection
schedule on the correctly specified conditional Bernoulli model, including
predictably reached offers. The natural and forced histories are different; no
simultaneous .95 guarantee is claimed across both schedules. No stream
independence is required for the union bound, but the conditional response law
is essential; there is no familywise guarantee over pairs, and misspecification
is outside that three-contrast guarantee. Use outward Decimal bounds and abstain
on empty or unwitnessed inference; the original gates also abstain on
noninterior bands. An arithmetic failure invalidates the run. A no-data prior rule
can act immediately if a>=.25,b>=.125 with at least one strict and epsilon>=
delta; this is pointwise positive for finite logits, with no positive uniform
margin. Compare prior, default, and all three data gates under both schedules.
The third is an independently implemented theta-only logit-polytope projection,
inspired by the comparator literature; it is not PRISM or expression-wise
projection of all transition and reward expressions. All three use the same
six-band event; no additional split is needed for three conclusions that each
hold on that same event, subject to verification of every gate's soundness.
The projection can handle boundary probability bands when it verifies a finite
witness, unlike the original gates. The gates share directed interval code;
re-evaluation by the runner is not independent proof replay.

The checkpoints are H=16,64,256,1024,4096,12288,100000,1000000,3000000
resets. Three million 1.5-hour reset episodes are about 514 simulated years;
the last three are idealized mathematical stress tests, not practicable
collection windows or field forecasts. At H, data rules latch their first
favorable checked decision, collect through H on their prespecified schedule,
then deploy for 32 fresh independent AB resets or default if never latched.
The no-data rule uses AB candidate on AB calendar episodes and defaults BA
through collection, and candidate on deployment if it certifies. Collection
expected urgent unmet is separately bounded by H*delta; epsilon is the expected
per-deployment-reset allowance only. A stop-at-checkpoint counterfactual uses
candidate on later AB and default on later BA calendar episodes, retaining all
remaining time and the same paired innovations. First crossings between
checkpoints are neither observed nor inferred.

For each calendar position in each block, draw aggregate multinomial counts
over 12 joint cells: the first user's shared uniform is below p, between p and
third, or above third, crossed with an independent second-user r response and
an independent urgent indicator. This requires p<third. The same cells couple
natural, forced, candidate, and default paths for that position, preserving
each simulated policy's full trajectory marginal under the model. Coupling is
a simulator choice, not identification of real-world individual effects.
Only response counts on the chosen feasible path enter gates; all cells and
true preferences are evaluator-only. NumPy finite-bit draws approximate the
ideal laws. Independent pair, rather than episode, is the sampling unit for
uncertainty; use 2000 paired pair-resampling bootstrap draws for descriptive
intervals. Record observed counts, suppression, exact group/physics, stream
keys, joint cell vectors, bounds, first crossings, null/false declarations,
collection and deployment welfare and urgent unmet, stop-path outcomes and
complete-calendar differences. Summaries report the pair denominators in each
combination of positive/nonpositive true welfare and feasible/infeasible expected
service, offered and accepted counts by driver and contrast, suppressed offers,
and expected and realized service separately. Paired bootstrap intervals are
descriptive, unadjusted for multiplicity, and include gate comparisons
within each schedule, each data gate against the shared unprefixed prior and
default baselines, natural versus forced comparisons for each data gate, and
prior versus default. Comparison names are recorded explicitly.

## Freeze and run controls

Complete independent exact-enumeration physical tests and a read-only source,
protocol, leakage and runner audit before a source manifest is frozen. Manifest
covers this protocol, runner, tests, imported gates and all package initializer
and interval dependencies. Verify hashes before and after the catalog and hash
all outputs. Write to an exclusive new run directory with started and completed
receipts; missing completion or timeout means incomplete, never silently rerun.
The proposed v2 output location is `personalized_charging/projection_comparison_study_v2/runs/heldout_20261028_v2`;
it must not already exist. No v1 output path is used.
Checkpoint records also form a SHA-256 chain whose final head is stored in the
completion receipt. The chain detects alteration only when its head or receipt
is independently retained; it is not an authentication signature.
A single-process SIGALRM limits elapsed time to 600 seconds starting after Python
imports and argument parsing, including manifest verification, generation,
analysis and output hashing up to receipt finalization. Imports, startup before
the timer, final atomic receipt rename and process shutdown are not externally
supervised; no address-space cap is enforced. A temporary receipt is written
and the final completed receipt is installed atomically only after checking
the elapsed time and pending interruption signals. The atomic rename is the
commit point: a signal arriving after the pending-signal check can be delivered
after the rename, causing a nonzero process exit even though a valid completion
receipt exists. At that commit point all data, analysis, source checks and
output digests have already finished. Hard kill or machine failure can leave
partial files; only a valid completed receipt counts as complete.
These controls do not guarantee cleanup or a fully hermetic environment.
Results and limitations must be independently audited before manuscript use. No claims of general RL, fleet/multiport, field
performance, or external validation follow from this study.
