"""Render finite-data decision rates from the sealed summary only."""
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parent
run = root / "runs/heldout_20261027_v1"
if json.loads((run / "completed.json").read_text())["status"] != "complete":
    raise RuntimeError("study is not complete")
data = json.loads((run / "summary.json").read_text())
horizons = (16,64,256,1024,4096,12288,100000,1000000,3000000)
fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True, constrained_layout=True)
for ax, group, title in zip(axes, ("beneficial", "B", "A_prime"),
                            ("Beneficial group", "World B: beneficial", "World A′: harmful, misspecified")):
    for gate, label, color in (("two", "Two contrasts", "#0072B2"), ("three", "Three contrasts", "#D55E00")):
        entries = [data[f"{group}|{h}"]["gates"][gate] for h in horizons]
        rates = np.array([e["certified_fraction"] for e in entries])*100
        ci = np.array([e["certified_wilson_95"] for e in entries])*100
        ax.plot(horizons, rates, marker="o", markersize=3.5, linewidth=1.4, label=label, color=color)
        ax.fill_between(horizons, ci[:,0], ci[:,1], color=color, alpha=.12, linewidth=0)
    ax.axvspan(100000, 3000000, color="#cccccc", alpha=.22, zorder=0)
    ax.set_xscale("log")
    ax.set_xticks((16,1024,100000,3000000), ("16", "1,024", "100k", "3m"), rotation=30)
    ax.set_ylim(0, 105)
    ax.set_title(title)
    ax.set_xlabel("Collection episodes")
    ax.grid(axis="y", color="#dddddd", linewidth=.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
axes[0].set_ylabel("Favorable decisions (%)")
axes[1].legend(frameon=False, loc="upper left")
fig.suptitle("Finite-data comparison; shaded horizons are extreme synthetic stress tests")
folder = root / "figures"
folder.mkdir(exist_ok=True)
for ext in ("png", "pdf", "svg"):
    fig.savefig(folder / ("bias_robust_decisions." + ext), dpi=200)
print(folder)
