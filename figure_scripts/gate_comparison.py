"""Figure: exact finite-horizon certification probabilities of the
fixed-alternative gate and the uniform-mixture gate (crossing checked after
every first-offer response). Requires gate_curves_dp.py in the same folder.
Run from the folder that contains figures/."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from gate_curves_dp import curves, fixed_cross, mixture_cross

N = 16384
ps = [0.70, 0.75, 0.80, 0.88]
colors = ["#d95f02", "#7570b3", "#1b9e77", "#666666"]
n = np.arange(N + 1)
fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=200)
for p, col in zip(ps, colors):
    a = curves(p, N, fixed_cross)
    b = curves(p, N, mixture_cross)
    ax.plot(n[1:], b[1:], color=col, lw=1.6, label=f"mixture, $p={p:.2f}$")
    ax.plot(n[1:], a[1:], color=col, lw=1.2, ls="--", label=f"fixed, $p={p:.2f}$")
ax.axhline(0.05, color="k", lw=0.6, ls=":")
ax.set_xscale("log")
ax.set_xlim(1, N)
ax.set_ylim(0, 1.02)
ax.set_xlabel("first-offer responses $n$")
ax.set_ylabel("probability of certification by $n$")
ax.legend(fontsize=6.5, ncol=2, loc="upper left", framealpha=0.9)
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(f"figures/gate_comparison.{ext}")
