
# Projection-comparison v2: independent stored-output audit

The independent audit found zero discrepancies across 30 frozen source hashes, the receipt and output inventory, all 3,240 chain-linked rows and 360 pair units, 19,440 collection blocks, 3,240 deployment blocks, observed-only responses and suppressions, 19,440 gate replays, 12,960 finite projection witnesses, latches, complete/stop-path accounting and summary point estimates. A separate analysis replay matched all 3,564 paired intervals and 7,128 endpoints. It used no scientific random draws and did not inspect the incomplete v1 output. Gate replays and witness sigmoid calculations share the frozen interval arithmetic; an independent high-precision numerical check is recorded separately and is not a proof. The portable script differs from the executed audit only by deriving the root from its own path. Scientific outcomes are not regenerated from their PCG64 keys by this audit.

```text
prior_positive 12288 natural_two:58/0 natural_three:55/0 natural_projection_three:60/0 forced_two:59/0 forced_three:55/0 forced_projection_three:60/0 prior:60/0 default:0/0
prior_positive 100000 natural_two:60/0 natural_three:59/0 natural_projection_three:60/0 forced_two:60/0 forced_three:59/0 forced_projection_three:60/0 prior:60/0 default:0/0
prior_positive 1000000 natural_two:60/0 natural_three:59/0 natural_projection_three:60/0 forced_two:60/0 forced_three:60/0 forced_projection_three:60/0 prior:60/0 default:0/0
prior_positive 3000000 natural_two:60/0 natural_three:60/0 natural_projection_three:60/0 forced_two:60/0 forced_three:60/0 forced_projection_three:60/0 prior:60/0 default:0/0
positive_mixed 12288 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
positive_mixed 100000 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
positive_mixed 1000000 natural_two:1/0 natural_three:18/0 natural_projection_three:23/0 forced_two:1/0 forced_three:15/0 forced_projection_three:23/0 prior:0/0 default:0/0
positive_mixed 3000000 natural_two:9/0 natural_three:27/0 natural_projection_three:32/0 forced_two:9/0 forced_three:25/0 forced_projection_three:32/0 prior:0/0 default:0/0
harmful 12288 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
harmful 100000 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
harmful 1000000 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
harmful 3000000 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
tight 12288 natural_two:0/0 natural_three:0/0 natural_projection_three:1/0 forced_two:0/0 forced_three:0/0 forced_projection_three:1/0 prior:0/0 default:0/0
tight 100000 natural_two:0/0 natural_three:5/0 natural_projection_three:23/0 forced_two:0/0 forced_three:3/0 forced_projection_three:23/0 prior:0/0 default:0/0
tight 1000000 natural_two:19/0 natural_three:39/0 natural_projection_three:42/0 forced_two:19/0 forced_three:38/0 forced_projection_three:42/0 prior:0/0 default:0/0
tight 3000000 natural_two:23/0 natural_three:43/0 natural_projection_three:47/0 forced_two:23/0 forced_three:43/0 forced_projection_three:47/0 prior:0/0 default:0/0
B 12288 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
B 100000 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
B 1000000 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
B 3000000 natural_two:0/0 natural_three:2/0 natural_projection_three:60/0 forced_two:0/0 forced_three:0/0 forced_projection_three:58/0 prior:0/0 default:0/0
A_prime 12288 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
A_prime 100000 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
A_prime 1000000 natural_two:0/0 natural_three:0/0 natural_projection_three:0/0 forced_two:0/0 forced_three:0/0 forced_projection_three:0/0 prior:0/0 default:0/0
A_prime 3000000 natural_two:0/0 natural_three:0/0 natural_projection_three:60/60 forced_two:0/0 forced_three:0/0 forced_projection_three:58/58 prior:0/0 default:0/0
groups {'prior_positive': 540, 'positive_mixed': 540, 'harmful': 540, 'tight': 540, 'B': 540, 'A_prime': 540} rows 3240 pairs 360 tested {'calendar_blocks': 19440, 'deployment_blocks': 3240, 'gate_replays': 19440, 'verified_witnesses': 12960} FAILURES {}

```
