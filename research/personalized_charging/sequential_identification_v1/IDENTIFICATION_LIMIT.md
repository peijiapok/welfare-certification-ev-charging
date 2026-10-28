# An observational-equivalence limit for choice-only charging feedback

This post-run analytical construction is separate from the frozen simulation catalog. General reward-identifiability and behavioral-misspecification issues have been studied in [Skalse and Abate (2026)](https://doi.org/10.1016/j.artint.2026.104525); the construction here specializes the issue to the declared charging process. It gives an exact identifiability limitation in the specified charging model; it is not a claim that this behavior shift was measured in real users, a general new statistical principle, or evidence of journal readiness.

Let the system, candidate, baseline, procurement costs, service law and welfare ledger be those in `PROTOCOL.md`. Compare two worlds with a persistent driver:

- **A (shifted behavior):** theta=2/25, tau=1/5, with 1/5 added to each offer-response logit. The welfare delay coefficient remains theta.
- **B (nominal behavior):** theta=2/35, tau=1/7, with no response-logit shift.

Both give the same first and second logits, exactly 3/10 and 1/2. Hence p=sigmoid(3/10) and r=sigmoid(1/2) are identical in both worlds. Since the arrival law, physical transitions, commitments and feasible actions are also the same, every feasible offer produces the same conditional observable response and physical outcome distribution, at every history. The controller observes offers, accept/reject responses, slot assignments, occupancy and urgent events, but does not observe theta, latent utility or theta-dependent welfare loss.

Let B_A and B_B be expected candidate-minus-baseline welfare. In A the two conditional increments are −1/100 and +1/100, so

    B_A = (1/100)[-p+(1-p)r] < 0,

because p>1/2 and r<1. In B both increments are positive, respectively 9/700 and 3/140; consequently B_B>0. Both have the same expected urgent unmet

    U = (1/200)[p+(1-p)r] < 1/200.

Numerically, B_A≈−0.00309550, B_B≈+0.01306195 and U≈0.00419667, in the model's units. The inequalities above are exact, and the numerical values are illustrative.

## Proposition and proof

For any controller whose adaptive and randomized actions and eventual favorable declaration depend only on the observable history and world-independent internal randomness, the probability of ever declaring the candidate favorable is the same in A and B. In particular, if its probability of a false favorable declaration in A is at most alpha, its probability of declaring favorable in B is at most alpha.

Proof: start from the same initial observable state and randomization law. If the history distributions agree at some step, the controller's next-action distribution also agrees. For each selected feasible action, the two worlds have identical conditional response and physical-transition kernels, so the next-history distributions agree. Induction gives equality at every finite time; the event of ever declaring is the countable union of finite-time declaration events, so its probability agrees. A favorable declaration is false in A because B_A<0, and the conclusion follows. ∎

This impossibility requires the shifted response rule in A while normative welfare continues to use the unshifted theta coefficient. If assumptions exclude that shift, or the controller observes informative welfare, the coefficient itself, additional contrasts or another relevant side channel, the equivalence may no longer hold. Here p=sigmoid(3/10)<2/3 in both worlds, so this pair does not itself explain the separate held-out misspecification group with 63% false certification. The result makes no statement about all possible misspecifications or unrestricted charging environments. In particular, a small per-step distributional difference does not automatically yield a useful bound for an unbounded stopping time.

## A hypothetical way to distinguish this pair

If the system could feasibly offer another one-hour-delay contrast with retail savings 1/5, and both stipulated response laws extended unchanged to that contrast, its logit would be exactly 4/5 in A and 1 in B. The corresponding acceptance probabilities are about 0.690 and 0.731. Its distribution would therefore break this particular observational equivalence. A single binary response would not distinguish the worlds with certainty, and this calculation does not establish that the offer is physically feasible or safe, or that collecting it has a finite-time service or welfare guarantee. It is an analytical design direction, not a simulated result.

## Population identification under a common shift

More generally, assume all three contrasts have qi=sigmoid((xi−theta*di)/tau+c), where tau>0 and the finite shift c is the same for each offer. Use (x,d)=(1/10,1), (1/10,1/2), and (1/5,1), and suppose their exact population probabilities lie strictly between 0 and 1. Write li=logit(qi) and lambda=1/tau. Then

    l3−l1 = lambda/10,     l2−l1 = lambda*theta/2,
    lambda = 10(l3−l1),    tau = 1/lambda,
    theta = 2(l2−l1)/lambda,
    c = l1−lambda(1/10−theta).

Thus, when l3>l1 and the recovered values satisfy the declared parameter domain, the three exact probabilities uniquely identify theta, tau and c within this model. If the original physical and welfare ledger is also correct, these values and the exact q1,q2 determine its population B and U. The first two contrasts alone admit the preceding pair with opposite rankings. This algebra follows from full-rank linear inversion and is not a new general identifiability theorem.

The added action has not been shown feasible or safe. Real data provide finite binary observations, not exact probabilities; numerical accuracy, uncertainty, the effect of repeated probing, and service and welfare constraints require further analysis. Three logits have no spare unconstrained fit degrees of freedom for three coefficients, although positivity and domain restrictions can still be falsified. Unknown contrast-specific shifts or a different response link invalidate the stated inverse.

## Sharp welfare set with two contrasts and an unknown common shift

Suppose exact population probabilities p,r lie in (0,1), theta in [0,1/4], tau in [1/20,2/5], and a finite common logit shift c is unrestricted. Let

    k = 2[logit(r)−logit(p)] = theta/tau.

A compatible model exists exactly when 0≤k≤5. In that case every compatible theta, and only such theta, lies in

    [theta_min, theta_max] = [k/20, min(2k/5,1/4)].

To see sharpness, write lambda=1/tau. For a given k, all and only lambda in [max(5/2,4k),20] are feasible, with theta=k/lambda. Choose c=logit(p)−lambda(1/10−theta) to match p; the logit difference then matches r. Every point in the displayed theta interval is attained. At k=0, theta=0 even though tau and c remain ambiguous; at k=5, theta=1/4 and tau=1/20.

Write A=(7/100)p+(1/20)(1−p)r and D=p+(1−p)r/2>0. The fixed physical and welfare ledger gives B=A−D*theta. The **sharp** population set for candidate advantage is therefore

    [A−D*theta_max, A−D*theta_min].

Under the same physical assumptions, expected urgent unmet U=[p+(1−p)r]/200 is point identified by p and r. For the exact observational-equivalence pair above, k=2/5 and theta ranges over [1/50,4/25]; the corresponding B set is approximately [−0.059647,+0.039318], so it includes both signs.

This set is not a finite-data confidence interval and makes no assertion that the assumed choice model or fixed welfare ledger is correct. Restricting c can narrow the set; contrast-specific shifts can change it. A finite-data decision requires a valid joint uncertainty region for the observable response probabilities and must also account for feasibility and collection service.

## Information needed to distinguish the two constructed worlds

Assume, hypothetically, that the third contrast is feasible when selected and its conditional response is Bernoulli(qA) in A or Bernoulli(qB) in B, with qA=sigmoid(4/5) and qB=sigmoid(1). All other observable kernels remain equal and welfare remains hidden. For a world-independent adaptive policy with an almost-surely finite stopped observable transcript under both worlds and finite E_A[N3], let N3 count third-offer observations and D be a favorable declaration. If P_A(D)≤alpha and P_B(D)≥1−beta with alpha<1−beta, the standard adaptive change-of-measure argument gives

    E_A[N3] * kl(qA || qB) ≥ kl(alpha || 1−beta),

where kl is binary Kullback–Leibler divergence. This follows by applying the KL chain rule to the stopped transcript, then data processing to D; all action and other outcome kernels cancel. The method is standard in sequential decision theory; see [Kaufmann, Cappé and Garivier (2016)](https://www.jmlr.org/papers/v17/kaufman16a.html). At alpha=0.05 and beta=0.2, the bound is E_A[N3]≥322.027745…; any fixed cap on the number of third-offer observations must be at least 323.

For contrast, a fixed-n midpoint test between these *two known* Bernoulli models has each error at most exp[−n(qB−qA)^2/2] by Hoeffding's inequality; n=3550 suffices for each error to be at most 0.05. This sufficient rule targets 95% power, while the preceding necessary bound targets 80% power, so the two numbers are not matching optimality bounds. The fixed-n rule is not an anytime-valid rule merely by virtue of this calculation.

These are post-run, model-specific calculations. They do not show that the third offer is physically available, that its response remains stationary, that repeated probes satisfy a service or welfare budget, or that a practical controller knows the two alternatives. The 64-episode simulation studies did not run this hypothetical test.
