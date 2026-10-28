"""Check that the implemented Decimal interval enclosures contain the exact
values, computed independently with 80-digit mpmath, for random and extreme
counts. Uses the study code unchanged."""
import sys, random
# Usage: python verify_interval_enclosures.py PATH_TO/research   (folder containing personalized_charging/)
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "research")
import mpmath as mp
from decimal import Decimal
from personalized_charging.three_contrast_confidence_exploratory_v1 import gate as g3
from personalized_charging.two_contrast_bias_exploratory_v1 import gate as g2
mp.mp.dps = 80
D = lambda x: mp.mpf(str(x))
def h_exact(n): return mp.sqrt(mp.log(120*n*(n+1))/(2*n))
def logit(x): return mp.log(x/(1-x))
rng = random.Random(2026)
ns = [1,2,3,5,10,64,100,1000,4096,10**5,10**6,3*10**6,10**9,10**12]
viol = {"radius":0,"band":0,"logit":0,"theta2":0,"theta3":0,"benefit":0,"service":0}
checks = dict.fromkeys(viol, 0)
for trial in range(12000):
    n = rng.choice(ns) if trial % 2 else rng.randint(1, 20000)
    # radius
    ru = D(g3.radius_upper(n)); checks["radius"] += 1
    if not ru >= h_exact(n): viol["radius"] += 1
    if trial % 3 == 0:
        counts = {k: (rng.randint(0, n), n) for k in ("p","r","third")}
    else:   # counts near a model-consistent point, to exercise realistic theta sets
        th_, ta_, c_ = rng.uniform(0, .25), rng.uniform(.05, .4), rng.uniform(-1, 1)
        q = {"p": 1/(1+mp.e**(-((.1-th_)/ta_+c_))), "r": 1/(1+mp.e**(-((.1-th_/2)/ta_+c_))),
             "third": 1/(1+mp.e**(-((.2-th_)/ta_+c_)))}
        counts = {k: (min(n, max(0, int(round(float(q[k])*n + rng.gauss(0, 1)*(n**.5)/2)))), n) for k in q}
    bands = {}
    for k,(s,m) in counts.items():
        band, emp = g3.probability_band(s, m); checks["band"] += 1
        lo_ex = max(mp.mpf(0), mp.mpf(s)/m - h_exact(m)); hi_ex = min(mp.mpf(1), mp.mpf(s)/m + h_exact(m))
        if not (D(band.lo) <= lo_ex and D(band.hi) >= hi_ex): viol["band"] += 1
        bands[k] = band
    if any(b.lo <= 0 or b.hi >= 1 for b in bands.values()): continue
    for b in bands.values():
        L = g3.logit(b); checks["logit"] += 1
        if not (D(L.lo) <= logit(D(b.lo)) and D(L.hi) >= logit(D(b.hi))): viol["logit"] += 1
    lp = (logit(D(bands["p"].lo)), logit(D(bands["p"].hi)))
    lr = (logit(D(bands["r"].lo)), logit(D(bands["r"].hi)))
    lt = (logit(D(bands["third"].lo)), logit(D(bands["third"].hi)))
    # exact outer theta for two-contrast
    k_lo, k_hi = max(0, 2*(lr[0]-lp[1])), min(5, 2*(lr[1]-lp[0]))
    T2 = g2.theta_outer({"p":bands["p"],"r":bands["r"]})
    if k_lo <= k_hi:
        ex = (max(0, k_lo/20), min(mp.mpf(1)/4, mp.mpf(2)/5*k_hi)); checks["theta2"] += 1
        if T2 is None or not (D(T2.lo) <= ex[0] and D(T2.hi) >= ex[1]): viol["theta2"] += 1
    lam_lo, lam_hi = max(mp.mpf(5)/2, 10*(lt[0]-lp[1])), min(20, 10*(lt[1]-lp[0]))
    v_lo, v_hi = max(0, 2*(lr[0]-lp[1])), min(5, 2*(lr[1]-lp[0]))
    T3 = g3.theta_outer(bands)
    if lam_lo <= lam_hi and v_lo <= v_hi:
        ex = (max(0, v_lo/lam_hi), min(mp.mpf(1)/4, v_hi/lam_lo))
        if ex[0] <= ex[1]:
            checks["theta3"] += 1
            if T3 is None or not (D(T3.lo) <= ex[0] and D(T3.hi) >= ex[1]): viol["theta3"] += 1
            B, U = g3.benefit_service_bounds(bands["p"], bands["r"], T3)
            th = D(T3.hi)
            bex = min(pp*(mp.mpf('0.07')-th)+(1-pp)*rr*(mp.mpf('0.05')-th/2)
                      for pp in (D(bands["p"].lo),D(bands["p"].hi)) for rr in (D(bands["r"].lo),D(bands["r"].hi)))
            checks["benefit"] += 1
            if not D(B.lo) <= bex: viol["benefit"] += 1
            uex = min(mp.mpf('0.005'), mp.mpf('0.005')*(D(bands["p"].hi)+(1-D(bands["p"].hi))*D(bands["r"].hi)))
            checks["service"] += 1
            if not D(U) >= uex: viol["service"] += 1
print("checks:", checks); print("violations:", viol)
