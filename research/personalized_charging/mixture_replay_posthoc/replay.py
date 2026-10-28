"""Post hoc replay of the one-sided mixture gate (Proposition 3) on the stored
Study 1 p-only histories. This is NOT part of any frozen protocol.

For each of the 1,800 p-only drivers, read the 64 stored first-offer responses
from the Study 1 event log, and check after every response whether
  (a) the fixed-alternative gate certifies: alpha * L_A > L_0, and
  (b) the uniform-mixture gate certifies:  M_n >= 1/alpha,
with alpha = 0.05, null envelope q0 = 2/3, and the service guard epsilon >= 1/200.
M_n is evaluated in closed form,
  M_n = 3 q0^{-s} (1-q0)^{-f} B(s+1, f+1) P(Bin(n+1, q0) <= s),
in 50-digit arithmetic. (The manuscript's replay used 96-point Gauss-Legendre
quadrature, which is exact for these degree <= 64 polynomial integrands.)

Usage: python replay.py [path/to/sequential_identification_v1/runs/heldout_20261027_v1]
"""
import csv, gzip, sys, os, collections
import mpmath as mp
mp.mp.dps = 50
Q0, ALT, ALPHA = mp.mpf(2)/3, mp.mpf(22)/25, mp.mpf(1)/20
GROUPS = ["easy", "low_information_positive", "boundary", "harmful", "tight_service", "misspecified"]

def binom_cdf(k, m, x):
    term = (1-x)**m; tot = term
    for j in range(k):
        term *= (m-j)/mp.mpf(j+1) * x/(1-x); tot += term
    return tot

def mixture_M(s, f):
    n = s + f
    return 3 * Q0**(-s) * (1-Q0)**(-f) * mp.beta(s+1, f+1) * binom_cdf(s, n+1, Q0)

def fixed_crosses(s, f):
    n = s + f; q = min(mp.mpf(s)/n, Q0)
    L0 = (q**s if s else 1) * ((1-q)**f if f else 1)
    return ALPHA * ALT**s * (1-ALT)**f > L0

def main(run_dir):
    drivers = {}
    with open(os.path.join(run_dir, "drivers.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            if row["collector"] == "p_only" and row["gate"] == "exact":
                drivers[(row["group"], row["driver"])] = row
    seqs = collections.defaultdict(list)
    with gzip.open(os.path.join(run_dir, "events.csv.gz"), "rt", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["arm"] == "p_only" and row["phase"] == "collection" and row["offer"] == "p":
                seqs[(row["group"], row["driver"])].append((int(row["episode"]), int(row["accepted"])))
    res = collections.defaultdict(lambda: collections.Counter())
    for key, row in drivers.items():
        resp = [a for _, a in sorted(seqs[key])]
        assert len(resp) == 64, (key, len(resp))
        guard = mp.mpf(row["epsilon"]) >= mp.mpf(1)/200
        fixed = mix = False; s = f = 0
        for a in resp:
            s += a; f += 1 - a
            if guard and not fixed and fixed_crosses(s, f): fixed = True
            if guard and not mix and mixture_M(s, f) >= 1/ALPHA: mix = True
        eligible = row["true_eligible"] == "True"
        res[key[0]]["fixed"] += fixed; res[key[0]]["mixture"] += mix
        res[key[0]]["fixed_false"] += fixed and not eligible
        res[key[0]]["mixture_false"] += mix and not eligible
        res[key[0]]["stored_fixed"] += row["deployed"] == "True"
    print(f"{'group':20s} fixed (stored) mixture | false: fixed mixture")
    for g in sorted(res, key=lambda g: GROUPS.index(g) if g in GROUPS else 99):
        c = res[g]
        print(f"{g:20s} {c['fixed']:5d} ({c['stored_fixed']:3d}) {c['mixture']:7d} | {c['fixed_false']:5d} {c['mixture_false']:7d}")

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.join(here, "..", "sequential_identification_v1", "runs", "heldout_20261027_v1")
    main(sys.argv[1] if len(sys.argv) > 1 else default)
