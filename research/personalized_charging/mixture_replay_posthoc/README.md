# Post hoc mixture replay (not a frozen study)

`replay.py` re-evaluates the stored Study 1 p-only histories (1,800 drivers,
64 first-offer responses each) under the uniform-mixture gate of
Proposition 3, and re-derives the fixed-alternative gate on the same data. No
new simulation is run, and the frozen Study 1 outputs are only read.

`replay_output.txt` holds the output. It reproduces the manuscript's counts:

- Mixture certifications by group: 146, 1, 1, 0, 0, 180.
- Fixed-gate certifications: 167, 1, 2, 0, 0, 189. These match the stored
  Study 1 decisions.
- False mixture certifications: 1 (boundary) and 180 (misspecified).

The script was added after the six studies were frozen. It is a descriptive
benchmark, not part of any prospective protocol.
