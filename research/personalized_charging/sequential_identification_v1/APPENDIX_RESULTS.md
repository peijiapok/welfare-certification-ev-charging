# Appendix: all prespecified collectors and outcomes

These descriptive results are computed from the sealed summary; n=300 independent drivers in each group. “False / ineligible” uses the within-group number of truly nonbeneficial or service-infeasible drivers. The lifecycle column is mean credits versus always-default over 64 collection and 32 deployment episodes, with an unadjusted paired 95% bootstrap interval. Collection unmet shows mean realized total and the mean of the sum of per-step conditional expected unmet, both over 64 episodes. Deployment unmet shows mean realized total and expected total (32 times per-episode expectation). These are expected-service quantities, not pathwise guarantees.

## Easy

| Collector / gate | Deployed | False / ineligible | Mean p offers | Collection unmet realized / expected | Deployment unmet realized / expected | Lifecycle mean [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| p_only:exact | 167/300 | 0/0 | 64.00 | 0.2867 / 0.2568 | 0.0800 / 0.0861 | +3.598 [+2.191, +4.958] |
| p_only:plugin | 300/300 | 0/0 | 64.00 | 0.2867 / 0.2568 | 0.1600 / 0.1540 | +4.136 [+2.626, +5.590] |
| alternating:exact | 95/300 | 0/0 | 32.00 | 0.2867 / 0.2588 | 0.0467 / 0.0490 | +2.772 [+1.441, +4.014] |
| alternating:plugin | 300/300 | 0/0 | 32.00 | 0.2867 / 0.2588 | 0.1600 / 0.1540 | +3.824 [+2.318, +5.322] |
| entropy:exact | 167/300 | 0/0 | 64.00 | 0.2867 / 0.2568 | 0.0800 / 0.0861 | +3.598 [+2.191, +4.958] |
| entropy:plugin | 300/300 | 0/0 | 64.00 | 0.2867 / 0.2568 | 0.1600 / 0.1540 | +4.136 [+2.626, +5.590] |
| myopic:exact | 77/300 | 0/0 | 18.69 | 0.2833 / 0.2596 | 0.0367 / 0.0398 | +2.654 [+1.288, +3.894] |
| myopic:plugin | 299/300 | 0/0 | 18.69 | 0.2833 / 0.2596 | 0.1600 / 0.1535 | +3.771 [+2.253, +5.237] |

## Low Information Positive

| Collector / gate | Deployed | False / ineligible | Mean p offers | Collection unmet realized / expected | Deployment unmet realized / expected | Lifecycle mean [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| p_only:exact | 1/300 | 0/0 | 64.00 | 0.1767 / 0.1831 | 0.0000 / 0.0004 | +2.059 [+1.040, +2.985] |
| p_only:plugin | 217/300 | 0/0 | 64.00 | 0.1767 / 0.1831 | 0.1133 / 0.0950 | +2.603 [+1.298, +3.810] |
| alternating:exact | 2/300 | 0/0 | 32.00 | 0.1833 / 0.1843 | 0.0000 / 0.0009 | +1.778 [+0.752, +2.749] |
| alternating:plugin | 166/300 | 0/0 | 32.00 | 0.1833 / 0.1843 | 0.0933 / 0.0728 | +2.055 [+0.751, +3.216] |
| entropy:exact | 1/300 | 0/0 | 64.00 | 0.1767 / 0.1831 | 0.0000 / 0.0004 | +2.059 [+1.040, +2.985] |
| entropy:plugin | 217/300 | 0/0 | 64.00 | 0.1767 / 0.1831 | 0.1133 / 0.0950 | +2.603 [+1.298, +3.810] |
| myopic:exact | 0/300 | 0/0 | 0.04 | 0.1800 / 0.1856 | 0.0000 / 0.0000 | +1.662 [+0.745, +2.548] |
| myopic:plugin | 66/300 | 0/0 | 0.04 | 0.1800 / 0.1856 | 0.0467 / 0.0290 | +1.603 [+0.619, +2.558] |

## Boundary

| Collector / gate | Deployed | False / ineligible | Mean p offers | Collection unmet realized / expected | Deployment unmet realized / expected | Lifecycle mean [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| p_only:exact | 2/300 | 1/177 | 64.00 | 0.1400 / 0.1722 | 0.0000 / 0.0009 | +0.331 [-0.470, +1.074] |
| p_only:plugin | 154/300 | 79/177 | 64.00 | 0.1400 / 0.1722 | 0.0733 / 0.0681 | +0.203 [-0.817, +1.120] |
| alternating:exact | 0/300 | 0/177 | 32.00 | 0.1733 / 0.1841 | 0.0000 / 0.0000 | +0.220 [-0.781, +1.116] |
| alternating:plugin | 132/300 | 66/177 | 32.00 | 0.1733 / 0.1841 | 0.0733 / 0.0586 | -0.068 [-1.160, +0.950] |
| entropy:exact | 2/300 | 1/177 | 64.00 | 0.1400 / 0.1722 | 0.0000 / 0.0009 | +0.331 [-0.470, +1.074] |
| entropy:plugin | 154/300 | 79/177 | 64.00 | 0.1400 / 0.1722 | 0.0733 / 0.0681 | +0.203 [-0.817, +1.120] |
| myopic:exact | 0/300 | 0/177 | 0.16 | 0.1767 / 0.1959 | 0.0000 / 0.0000 | +0.741 [-0.245, +1.682] |
| myopic:plugin | 105/300 | 58/177 | 0.16 | 0.1767 / 0.1959 | 0.0600 / 0.0472 | +0.488 [-0.591, +1.540] |

## Harmful

| Collector / gate | Deployed | False / ineligible | Mean p offers | Collection unmet realized / expected | Deployment unmet realized / expected | Lifecycle mean [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| p_only:exact | 0/300 | 0/300 | 64.00 | 0.1433 / 0.1244 | 0.0000 / 0.0000 | -2.957 [-3.858, -2.192] |
| p_only:plugin | 11/300 | 11/300 | 64.00 | 0.1433 / 0.1244 | 0.0033 / 0.0044 | -2.974 [-3.893, -2.205] |
| alternating:exact | 0/300 | 0/300 | 32.00 | 0.1633 / 0.1446 | 0.0000 / 0.0000 | -2.294 [-3.194, -1.446] |
| alternating:plugin | 13/300 | 13/300 | 32.00 | 0.1633 / 0.1446 | 0.0033 / 0.0053 | -2.299 [-3.247, -1.439] |
| entropy:exact | 0/300 | 0/300 | 64.00 | 0.1433 / 0.1244 | 0.0000 / 0.0000 | -2.957 [-3.858, -2.192] |
| entropy:plugin | 11/300 | 11/300 | 64.00 | 0.1433 / 0.1244 | 0.0033 / 0.0044 | -2.974 [-3.893, -2.205] |
| myopic:exact | 0/300 | 0/300 | 0.05 | 0.1833 / 0.1649 | 0.0000 / 0.0000 | -1.635 [-2.645, -0.714] |
| myopic:plugin | 23/300 | 23/300 | 0.05 | 0.1833 / 0.1649 | 0.0067 / 0.0092 | -1.674 [-2.711, -0.703] |

## Tight Service

| Collector / gate | Deployed | False / ineligible | Mean p offers | Collection unmet realized / expected | Deployment unmet realized / expected | Lifecycle mean [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| p_only:exact | 0/300 | 0/123 | 64.00 | 0.2033 / 0.1964 | 0.0000 / 0.0000 | +0.891 [-0.197, +1.921] |
| p_only:plugin | 202/300 | 57/123 | 64.00 | 0.2033 / 0.1964 | 0.0800 / 0.0932 | +1.666 [+0.341, +2.952] |
| alternating:exact | 0/300 | 0/123 | 32.00 | 0.2167 / 0.2042 | 0.0000 / 0.0000 | +0.844 [-0.320, +1.960] |
| alternating:plugin | 176/300 | 52/123 | 32.00 | 0.2167 / 0.2042 | 0.0633 / 0.0811 | +1.647 [+0.292, +2.962] |
| entropy:exact | 0/300 | 0/123 | 64.00 | 0.2033 / 0.1964 | 0.0000 / 0.0000 | +0.891 [-0.197, +1.921] |
| entropy:plugin | 202/300 | 57/123 | 64.00 | 0.2033 / 0.1964 | 0.0800 / 0.0932 | +1.666 [+0.341, +2.952] |
| myopic:exact | 0/300 | 0/123 | 2.17 | 0.2300 / 0.2116 | 0.0000 / 0.0000 | +0.854 [-0.343, +1.988] |
| myopic:plugin | 139/300 | 53/123 | 2.17 | 0.2300 / 0.2116 | 0.0533 / 0.0644 | +1.402 [+0.070, +2.629] |

## Misspecified

| Collector / gate | Deployed | False / ineligible | Mean p offers | Collection unmet realized / expected | Deployment unmet realized / expected | Lifecycle mean [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| p_only:exact | 189/300 | 189/300 | 64.00 | 0.2800 / 0.2599 | 0.0667 / 0.0991 | -5.522 [-6.847, -4.260] |
| p_only:plugin | 299/300 | 299/300 | 64.00 | 0.2800 / 0.2599 | 0.1200 / 0.1564 | -6.433 [-7.841, -5.048] |
| alternating:exact | 135/300 | 135/300 | 32.00 | 0.2767 / 0.2739 | 0.0567 / 0.0708 | -3.781 [-4.976, -2.625] |
| alternating:plugin | 299/300 | 299/300 | 32.00 | 0.2767 / 0.2739 | 0.1200 / 0.1564 | -4.698 [-6.042, -3.363] |
| entropy:exact | 189/300 | 189/300 | 64.00 | 0.2800 / 0.2599 | 0.0667 / 0.0991 | -5.522 [-6.847, -4.260] |
| entropy:plugin | 299/300 | 299/300 | 64.00 | 0.2800 / 0.2599 | 0.1200 / 0.1564 | -6.433 [-7.841, -5.048] |
| myopic:exact | 148/300 | 148/300 | 33.50 | 0.2900 / 0.2751 | 0.0467 / 0.0777 | -3.757 [-4.990, -2.526] |
| myopic:plugin | 300/300 | 300/300 | 33.50 | 0.2900 / 0.2751 | 0.1200 / 0.1570 | -4.969 [-6.370, -3.551] |

Intervals and comparisons are descriptive and unadjusted for multiplicity. The exact gate uses p responses only, even if the collector observes r. The misspecified group falls outside the exact gate’s model-based welfare guarantee. The oracle is a deployment-only reference and is not included in lifecycle comparisons.
