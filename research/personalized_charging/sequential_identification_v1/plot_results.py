"""Render a descriptive figure from the sealed stored summary; no rerun."""
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parent
summary = json.loads((root / "runs/heldout_20261027_v1/summary.json").read_text())
if summary["status"] != "complete":
    raise RuntimeError("the frozen scientific run is incomplete")
groups = ("easy", "low_information_positive", "boundary", "harmful", "tight_service", "misspecified")
labels = ("Easy", "Low information", "Boundary", "Harmful", "Tight service", "Misspecified")
x = np.arange(len(groups))
fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.6), constrained_layout=True)
for offset, method, label, color in ((-.19, "p_only:exact", "Exact gate", "#0072B2"),
                                     (.19, "p_only:plugin", "Plug-in", "#D55E00")):
    ms = [summary["groups"][g]["methods"][method] for g in groups]
    estimates = np.array([m["deployed_fraction"] for m in ms]) * 100
    intervals = np.array([m["deployed_wilson_95"] for m in ms]) * 100
    axes[0].bar(x + offset, estimates, width=.38, label=label, color=color)
    axes[0].errorbar(x + offset, estimates, yerr=np.maximum(0., np.vstack((estimates-intervals[:,0], intervals[:,1]-estimates))),
                     fmt="none", color="black", capsize=2, linewidth=.9)
    diffs = [summary["groups"][g]["paired_differences"][method + " minus default"] for g in groups]
    means = np.array([d["mean"] for d in diffs])
    ci = np.array([d["bootstrap_95"] for d in diffs])
    axes[1].vlines(x + offset, ci[:,0], ci[:,1], color=color, linewidth=1)
    axes[1].scatter(x + offset, means, color=color, s=26, label=label, zorder=3)
axes[0].set_ylabel("Deployed candidates (%)")
axes[0].set_ylim(0, 130)
axes[0].set_yticks([0, 25, 50, 75, 100])
axes[1].axhline(0, color="#666666", linewidth=.8)
axes[1].set_ylabel("Mean 96-episode advantage (credits)")
for ax in axes:
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#dddddd", linewidth=.7)
    ax.set_axisbelow(True)
axes[0].legend(frameon=False, loc="upper right")
fig.suptitle("One-port simulation: deployment and lifecycle outcome")
out = root / "figures"
out.mkdir(exist_ok=True)
for extension in ("png", "pdf", "svg"):
    fig.savefig(out / f"decision_outcomes.{extension}", dpi=200)
print(out)
