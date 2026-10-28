"""Plot stored matched-verifier output; does not run any simulation."""
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parent
out = root / "runs/heldout_20261027_v1"
if json.loads((out / "completed.json").read_text())["status"] != "complete":
    raise RuntimeError("scientific run is not complete")
data = json.loads((out / "summary.json").read_text())
groups = ("easy", "low_information", "mixed", "tight", "misspecified")
labels = ("Easy", "Low information", "Mixed", "Tight service", "Misspecified")
x = np.arange(len(groups))
fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.4), sharey=True, constrained_layout=True)
for ax, collector, heading in zip(axes, ("p_only", "alternating"), ("P-only collection", "Alternating collection")):
    for offset, gate, label, color in ((-.19, "p_only", "Exact p-only", "#0072B2"),
                                       (.19, "continuous", "Continuous mixture", "#D55E00")):
        entries = [data[g]["methods"][collector + ":" + gate] for g in groups]
        mean = np.array([m["certified"]/m["n"] for m in entries])*100
        ci = np.array([m["certified_wilson_95"] for m in entries])*100
        ax.bar(x+offset, mean, width=.38, label=label, color=color)
        ax.errorbar(x+offset, mean, yerr=np.maximum(0., np.vstack((mean-ci[:,0],ci[:,1]-mean))),
                    fmt="none", color="black", capsize=2, linewidth=.8)
    ax.set_title(heading)
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.grid(axis="y", color="#dddddd", linewidth=.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
axes[0].set_ylabel("Favorable decisions (%)")
axes[1].legend(frameon=False, loc="upper right")
fig.suptitle("Matched verifier comparison by collection schedule")
folder = root / "figures"
folder.mkdir(exist_ok=True)
for ext in ("png", "svg", "pdf"):
    fig.savefig(folder / ("matched_decisions."+ext), dpi=200)
print(folder)
