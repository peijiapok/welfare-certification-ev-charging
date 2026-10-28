"""Asymptotic (infinite-data) certifiability map for the one-port model.

Regions over the declared domain theta in [0, 1/4], tau in [1/20, 2/5], with
true common shift c = 0 (correct nominal specification):
  * B <= 0                           : no rule should certify;
  * B > 0                            : certifiable by the three-contrast rule in the limit;
  * sharp two-contrast lower bound>0 : certifiable by the two-contrast rule in the limit;
  * p > p_dagger                     : certified almost surely by the one-dimensional gate.
Area fractions use the uniform measure on the rectangle and are descriptive only.
Run from the folder that contains figures/.
"""
from math import log

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

sig = lambda x: 1.0 / (1.0 + np.exp(-x))
P_DAGGER = log((1 / 3) / 0.12) / (log(0.88 / (2 / 3)) + log((1 / 3) / 0.12))

theta = np.linspace(0.0, 0.25, 1001)
tau = np.linspace(0.05, 0.40, 1401)
T, U = np.meshgrid(theta, tau, indexing="ij")
p = sig((0.1 - T) / U)
r = sig((0.1 - T / 2) / U)
B = p * (0.07 - T) + (1 - p) * r * (0.05 - T / 2)
k = T / U
A = 0.07 * p + 0.05 * (1 - p) * r
D = p + (1 - p) * r / 2
LB2 = A - D * np.minimum(2 * k / 5, 0.25)

pos, two, one = B > 0, LB2 > 0, p > P_DAGGER
# The one-dimensional gate assumes no response shift, whereas the two- and
# three-contrast rules allow an unknown common shift, so the regions are not nested.
assert not (two & ~pos).any() and not (one & ~pos).any()
region = np.zeros_like(B, dtype=int)
region[pos] = 1
region[two] = 2

print(f"p_dagger = {P_DAGGER:.6f}")
print(
    f"area share B>0: {pos.mean():.3f}; of which two-contrast certifiable: "
    f"{two.sum() / pos.sum():.3f}; one-dimensional gate: {one.sum() / pos.sum():.3f}; "
    f"one-dimensional gate but not two-contrast: {(one & ~two).sum() / pos.sum():.3f}"
)

cmap = ListedColormap(["#d9d9d9", "#fdd49e", "#6baed6"])
fig, ax = plt.subplots(figsize=(6.4, 4.4), dpi=200)
ax.pcolormesh(U, T, region, cmap=cmap, vmin=-0.5, vmax=2.5, shading="auto")
ax.contour(U, T, B, levels=[0], colors="k", linewidths=0.8)
ax.contourf(U, T, p, levels=[P_DAGGER, 1.0], colors="none", hatches=["////"])
ax.contour(U, T, p, levels=[P_DAGGER], colors="#08306b", linewidths=1.2)
ax.set_xlabel(r"response temperature $\tau$")
ax.set_ylabel(r"delay coefficient $\theta$")
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in cmap.colors]
handles.append(plt.Rectangle((0, 0), 1, 1, facecolor="none", edgecolor="#08306b", hatch="////"))
labels = [
    r"$B\leq 0$",
    r"$B>0$: three-contrast rule only",
    r"$B>0$: two- and three-contrast rules",
    r"$p>p^{\dagger}$: one-dimensional gate (no-shift model)",
]
ax.legend(handles, labels, loc="upper right", fontsize=7, framealpha=0.9)
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(f"figures/certifiability_map.{ext}")
