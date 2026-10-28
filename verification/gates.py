"""Exact finite-horizon certification probabilities for the fixed-alternative
gate (Theorem 1) and the uniform-mixture gate (Proposition mixture), with the
crossing checked after every first-offer response. Pure calculation: dynamic
programming over (successes, failures); no simulation."""
import numpy as np
from scipy.special import betaln, betainc, xlogy
from math import log
Q0, ALT, ALPHA = 2/3, 22/25, 0.05
LOGTHR = log(1/ALPHA)

def fixed_cross(n):
    s = np.arange(n+1); f = n - s
    q = np.minimum(s/n, Q0)
    llr = s*log(ALT) + f*log(1-ALT) - (xlogy(s, q) + xlogy(f, 1-q))
    return llr > LOGTHR          # alpha*L_A > L_0 (strict)

def mixture_cross(n):
    s = np.arange(n+1); f = n - s
    # M_n = 3 * int_{2/3}^1 (u/q0)^s ((1-u)/(1-q0))^f du ; uniform density 3 on (2/3,1)
    with np.errstate(divide='ignore'):
        logint = betaln(s+1, f+1) + np.log(betainc(f+1, s+1, 1-Q0))
    logM = log(3) + logint - s*log(Q0) - f*log(1-Q0)
    return logM >= LOGTHR        # M_n >= 1/alpha

def curves(p, N, cross):
    mass = np.array([1.0])        # not-yet-certified mass over s at step n
    out = np.zeros(N+1)
    done = 0.0
    for n in range(1, N+1):
        new = np.zeros(n+1)
        new[:-1] += mass*(1-p); new[1:] += mass*p
        c = cross(n)
        done += new[c].sum(); new[c] = 0.0
        mass = new; out[n] = done
    return out
