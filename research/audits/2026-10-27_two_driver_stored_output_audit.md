
# Two-driver study independent stored-output audit

The independent audit found no discrepancies in the frozen manifest, saved-output hashes, 420 pair worlds, 3,780 checkpoint rows, 22,680 collection blocks, 3,780 deployment blocks, 15,120 gate replays, feasible offer labels, suppressions, full and stop-path accounting, truth strata, Wilson intervals and paired summary means. No scientific randomness or bootstrap resampling was regenerated: stream-key structure was checked, but the exact multinomial draws were not reproduced from PCG64 keys. Gate replay shares the original interval arithmetic and is not an independent numerical proof; bootstrap interval endpoints were not independently regenerated. The archived audit script differs from the executed script only in deriving the project root from its location for portability.

```text
prior_positive 12288 natural_two:59/0 natural_three:57/0 forced_two:59/0 forced_three:56/0 prior:60/0 default:0/0
prior_positive 100000 natural_two:59/0 natural_three:59/0 forced_two:59/0 forced_three:59/0 prior:60/0 default:0/0
prior_positive 1000000 natural_two:60/0 natural_three:60/0 forced_two:60/0 forced_three:60/0 prior:60/0 default:0/0
prior_positive 3000000 natural_two:60/0 natural_three:60/0 forced_two:60/0 forced_three:60/0 prior:60/0 default:0/0
positive_mixed 12288 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
positive_mixed 100000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
positive_mixed 1000000 natural_two:0/0 natural_three:10/0 forced_two:0/0 forced_three:8/0 prior:0/0 default:0/0
positive_mixed 3000000 natural_two:0/0 natural_three:17/0 forced_two:0/0 forced_three:17/0 prior:0/0 default:0/0
harmful 12288 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
harmful 100000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
harmful 1000000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
harmful 3000000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
tight 12288 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
tight 100000 natural_two:2/0 natural_three:9/0 forced_two:1/0 forced_three:8/0 prior:0/0 default:0/0
tight 1000000 natural_two:17/0 natural_three:42/0 forced_two:17/0 forced_three:41/0 prior:0/0 default:0/0
tight 3000000 natural_two:20/0 natural_three:45/0 forced_two:22/0 forced_three:45/0 prior:0/0 default:0/0
A 12288 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
A 100000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
A 1000000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
A 3000000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
B 12288 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
B 100000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
B 1000000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
B 3000000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
A_prime 12288 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
A_prime 100000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
A_prime 1000000 natural_two:0/0 natural_three:0/0 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
A_prime 3000000 natural_two:0/0 natural_three:3/3 forced_two:0/0 forced_three:0/0 prior:0/0 default:0/0
groups {'prior_positive': 540, 'positive_mixed': 540, 'harmful': 540, 'tight': 540, 'A': 540, 'B': 540, 'A_prime': 540} rows 3780 pairs 420 tested {'calendar_blocks': 22680, 'deployment_blocks': 3780, 'gate_replays': 15120} FAILURES {}

```
