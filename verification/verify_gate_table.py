"""Independent check of Table 2: (a) crossing sets are upper sets in s and their
thresholds agree with 50-digit mpmath evaluation; (b) an independent 50-digit
threshold-based DP reproduces the float DP at n = 64 and 1024."""
import numpy as np, mpmath as mp
from gates import fixed_cross, mixture_cross, curves
mp.mp.dps = 50
q0, alt, thr = mp.mpf(2)/3, mp.mpf(22)/25, mp.log(20)
def fixed_mp(s, n):
    f = n - s; q = min(mp.mpf(s)/n, q0)
    ll0 = (s*mp.log(q) if s else 0) + (f*mp.log(1-q) if f else 0)
    return s*mp.log(alt) + f*mp.log(1-alt) - ll0 > thr
def binom_cdf(k, m, x):
    """P(Bin(m,x) <= k) by direct term recurrence in high precision."""
    term = (1-x)**m; tot = term
    for j in range(k):
        term *= (m-j)/mp.mpf(j+1) * x/(1-x); tot += term
    return tot
def mix_mp(s, n):
    # identity: int_{q0}^1 u^s (1-u)^f du = B(s+1,f+1) * P(Bin(n+1,q0) <= s)
    f = n - s
    integ = mp.beta(s+1, f+1) * binom_cdf(s, n+1, q0)
    return mp.log(3*integ) - s*mp.log(q0) - f*mp.log(1-q0) >= thr
def thresholds(cross, N):
    th = []
    for n in range(1, N+1):
        c = cross(n)
        idx = np.flatnonzero(c)
        if idx.size:
            assert c[idx[0]:].all(), f"crossing set not an upper set at n={n}"
            th.append(int(idx[0]))
        else:
            th.append(n+1)
    return th
N = 16384
for name, cross, mpf_ in (("fixed", fixed_cross, fixed_mp), ("mixture", mixture_cross, mix_mp)):
    th = thresholds(cross, N)
    check = (list(range(1, 2049)) + list(range(2049, N+1, 97)) + [N]) if name=="fixed" else (list(range(1, 513)) + list(range(513, N+1, 211)) + [N])
    bad = 0
    for n in check:
        s = th[n-1]
        if s <= n and not mpf_(s, n): bad += 1
        if s-1 >= 0 and mpf_(s-1, n): bad += 1
    print(name, "upper-set OK; threshold mismatches vs mpmath at", len(check), "horizons:", bad)
    np.save(f"th_{name}.npy", np.array(th))
# (b) independent high-precision DP using thresholds, N=1024
def dp_mp(p, th, N):
    p = mp.mpf(p); mass = [mp.mpf(1)]; done = mp.mpf(0); out = {}
    for n in range(1, N+1):
        new = [mp.mpf(0)]*(n+1)
        for s, m in enumerate(mass):
            if m: new[s] += m*(1-p); new[s+1] += m*p
        t = th[n-1]
        done += mp.fsum(new[t:]); new[t:] = [mp.mpf(0)]*(n+1-t) if t <= n else []
        new = new[:n+1] if t <= n else new
        mass = new + [mp.mpf(0)]*(n+1-len(new))
        if n in (64, 1024): out[n] = done
    return out
mp.mp.dps = 30
for name, cross in (("fixed", fixed_cross), ("mixture", mixture_cross)):
    th = list(np.load(f"th_{name}.npy"))
    for p in (0.75, 0.80):
        ref = dp_mp(p, th, 1024); flt = curves(p, 1024, cross)
        print(name, p, {n: (float(ref[n]), round(abs(float(ref[n]) - flt[n]), 15)) for n in ref})
