"""Plot a fixed-checkpoint sensitivity comparison from saved outputs."""
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

root=Path(__file__).resolve().parent
run=root/"runs/heldout_20261027_v1"
if json.loads((run/"completed.json").read_text())["status"] != "complete":
    raise RuntimeError("study is not complete")
data=json.loads((run/"summary.json").read_text())
groups=("prior_positive_1","prior_positive_2","harmful","near_zero","tight","low_penalty","A","B","A_prime")
labels=("Prior +1","Prior +2","Harmful","Near zero","Tight","Low penalty","A","B","A′")
x=np.arange(len(groups))
fig,ax=plt.subplots(figsize=(11.8,4.6),constrained_layout=True)
for offset,method,label,color in ((-.16,"prior","No-data prior rule","#0072B2"),(.16,"three","Collect then decide","#D55E00")):
    entries=[data[f"{g}|64"] for g in groups]
    stats=[entry["paired"][method+" minus default"]["lifecycle_advantage"] for entry in entries]
    mean=np.array([z["mean_difference"] for z in stats])
    ci=np.array([z["bootstrap_95"] for z in stats])
    ax.vlines(x+offset,ci[:,0],ci[:,1],color=color,linewidth=1.0)
    ax.scatter(x+offset,mean,color=color,s=28,label=label,zorder=3)
ax.axhline(0,color="#555555",linewidth=.8)
ax.set_xticks(x,labels,rotation=35,ha="right")
ax.set_ylabel("Mean paired welfare advantage (credits)")
ax.set_title("Sensitivity study: 64 collection episodes plus 32 deployment episodes")
ax.grid(axis="y",color="#dddddd",linewidth=.7)
ax.set_axisbelow(True)
ax.spines[["top","right"]].set_visible(False)
ax.legend(frameon=False,loc="upper right")
folder=root/"figures";folder.mkdir(exist_ok=True)
for ext in ("png","pdf","svg"):
    fig.savefig(folder/("prior_vs_collect."+ext),dpi=200)
print(folder)
