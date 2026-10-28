"""Independent check of Table 3 (third-offer benchmarks) in 60-digit arithmetic."""
import mpmath as mp
from scipy.stats import binom
mp.mp.dps = 60
qa, qb = 1/(1+mp.e**(-mp.mpf(4)/5)), 1/(1+mp.e**(-1))
kl = lambda a, b: a*mp.log(a/b) + (1-a)*mp.log((1-a)/(1-b))
for a, b in ((mp.mpf('0.05'), mp.mpf('0.2')), (mp.mpf('0.05'), mp.mpf('0.05'))):
    print("lower bound E_A[N3] >=", mp.nstr(kl(a, 1-b)/kl(qa, qb), 10))
print("Hoeffding n >=", mp.nstr(2*mp.log(20)/(qb-qa)**2, 10))
def tails(n, q):
    """exact upper tails P(X>=k), k=0..n+1, in mp precision"""
    pm = [mp.binomial(n, k)*q**k*(1-q)**(n-k) for k in range(n+1)]
    t = [mp.mpf(0)]*(n+2)
    for k in range(n, -1, -1): t[k] = t[k+1] + pm[k]
    return t
def ok_mp(n, pw):
    ta, tb = tails(n, qa), tails(n, qb)
    k = next(k for k in range(n+2) if ta[k] <= mp.mpf('0.05'))   # smallest valid critical value
    return tb[k] >= pw
for pw, lo, hi in ((mp.mpf('0.8'), 740, 800), (mp.mpf('0.95'), 1300, 1362)):
    ok = [n for n in range(lo, hi+1) if ok_mp(n, pw)]
    first = ok[0]
    fails = [n for n in range(first, hi+1) if n not in ok]
    print(f"power {pw}: first n={first}, last failing n in window={max(fails) if fails else None}")
# float scan for 'every larger n' up to 5000
qaf, qbf = float(qa), float(qb)
def ok_f(n, pw):
    k = int(binom.isf(0.05, n, qaf))
    while binom.sf(k-1, n, qaf) > 0.05: k += 1
    while k > 0 and binom.sf(k-2, n, qaf) <= 0.05: k -= 1
    return binom.sf(k-1, n, qbf) >= pw
for pw, a in ((0.8, 797), (0.95, 1360)):
    print(pw, "all n in [%d,5000] pass:" % a, all(ok_f(n, pw) for n in range(a, 5001)), "; n-1 passes:", ok_f(a-1, pw))
