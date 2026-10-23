"""Numerical checks of Adam, Sokolowski & Banks (2009), Math. Comput. Modelling 49:1115-1126.

Each check prints the paper's claim next to what the equations actually give.
Usage: python paper/verify_adam2009.py
"""
import numpy as np
import sympy as sp
from mpmath import hyp1f1, hyperu, mp
from scipy.integrate import solve_ivp

mp.dps = 30
line = "-" * 78

# 1. Eq. (13): unforced QPPM fit, I(t) = e^{0.287t}[4000 cos 0.153t + 2000 sin 0.153t]
print(line, "\n1. Eq. (13) fit")
I13 = lambda t: np.exp(0.287 * t) * (4000 * np.cos(0.153 * t) + 2000 * np.sin(0.153 * t))
half_beta, root_lam = 0.287, 0.153
beta, lam = 2 * half_beta, root_lam ** 2
print(f"I(0)={I13(0):.0f}  I(4)={I13(4):.0f} (paper: data ~12,500)  I(10)={I13(10):.0f} (paper: 38,100)")
print(f"implied I'(0) = beta/2*I0 + sqrt(lam)*B = {half_beta*4000 + root_lam*2000:.0f} per year")
print(f"gamma = lam + beta^2/4 = {lam + beta**2/4:.3f} (paper: 0.106)")
print(f"oscillation period 2pi/0.153 = {2*np.pi/0.153:.1f} yr; e-folding 1/0.287 = {1/0.287:.2f} yr")

# 2. Section 8: piecewise exponential (17a,b) and the paper's growth-rate reading
print(line, "\n2. Section 8: growth and decay rates")
a, at = 0.019, 0.014
c = 0.450 - a          # from (a + c)/2 = 0.225
ct = at + 0.150        # from (a~ - c~)/2 = -0.075
print(f"c = {c:.3f}, c~ = {ct:.3f}  (paper: 0.431, 0.164)")
print(f"(17a) I(10) = 4000 e^2.25 = {4000*np.exp(2.25):.0f}")
print(f"realized one-year factor 1993-2003: e^0.225 = {np.exp(0.225):.3f}  -> 100 insurgents become {100*np.exp(0.225):.0f}")
print(f"realized one-year factor after 2003: e^-0.075 = {np.exp(-0.075):.3f} -> 100 become {100*np.exp(-0.075):.0f}")
print("paper says 143 and 86, i.e. it reads the parameters c, c~ as the population's growth rates.")
# With lambda ~ 0 the system (15) has a double eigenvalue beta/2 = 0.225, so I grows at 0.225, not c.
bd = ((a - c) / 2) ** 2
M = np.array([[a, -1.0], [bd, c]])  # take b = 1, d = bd (only the product matters for eigenvalues)
print(f"eigenvalues of (15) with |a-c| = 2 sqrt(bd), bd = {bd:.4f}: {np.round(np.linalg.eigvals(M), 4)}")

# 3. Section 9 decoupled system and Fig. 4
print(line, "\n3. Section 9: decoupled system (d = 0)")
print(f"with d = 0, I(t) = I0 e^(ct): I(10)/I0 = e^(10c) = {np.exp(10*c):.1f}  (data: 38,100/4,000 = {38100/4000:.2f})")
I0 = 0.001  # I/S ~ 0.001 with S0 = 1; reproduces Fig. 4
def S27(t, b, c_=c):
    return np.exp(a * t) + b * I0 / (c_ - a) * (np.exp(a * t) - np.exp(c_ * t))
for b in (0.5, 1.0, 1.5):
    print(f"  b={b}: S(10) from (27) = {S27(10, b):.3f}   (Fig. 4 shows ~{ {0.5: 1.12, 1.0: 1.03, 1.5: 0.945}[b] })")
print("  -> Fig. 4 uses c = 0.431 (74-fold insurgent growth), not the 0.225 the data supports.")
for b in (0.5, 1.0, 1.5):
    print(f"  b={b}: S(10) with the data-consistent growth c = 0.225: {S27(10, b, 0.225):.3f}")

# Eq. (28) vs the correct continuation for t > 10
print("\n  Eq. (28) vs direct integration for t > 10 (b = 1, c = 0.431):")
b = 1.0
S10, I10 = S27(10, b), I0 * np.exp(10 * c)
def S28(t):
    tau = t - 10
    return S10 * (np.exp(at * tau) - b * I0 / (ct + at) * (np.exp(at * tau) - np.exp(-ct * tau)))
def S_correct(t):
    tau = t - 10
    return S10 * np.exp(at * tau) - b * I10 / (ct + at) * (np.exp(at * tau) - np.exp(-ct * tau))
sol = solve_ivp(lambda t, y: [at * y[0] - b * y[1], -ct * y[1]], (10, 20), [S10, I10],
                dense_output=True, rtol=1e-10, atol=1e-12)
for t in (10, 11, 12, 14, 17, 20):
    print(f"   t={t:>2}: paper (28) {S28(t):.4f}   corrected {S_correct(t):.4f}   ODE {sol.sol(t)[0]:.4f}")
print(f"   slope just after 2003: S'(10+) = a~ S(10) - b I(10) = {at*S10 - b*I10:+.4f} (negative: S keeps falling)")

# 4. Appendix A.2: derive the S-equation coefficient and test the closed-form solution
print(line, "\n4. Appendix A.2")
t = sp.symbols("t")
a_, b_, c_, d_, D, w = sp.symbols("a b c d D w", positive=True)
S, I = sp.Function("S")(t), sp.Function("I")(t)
f2 = D * (1 - sp.exp(-w * t))
# Model 2 with f1 = 0: S' = aS - bI, I' = -cI + dS - f2 I. Eliminate I via I = (aS - S')/b.
Iexpr = (a_ * S - S.diff(t)) / b_
eqS = sp.expand(-(Iexpr.diff(t) - (-c_ * Iexpr + d_ * S - f2 * Iexpr)) * b_)
coeffS0 = sp.simplify(sp.expand(eqS).coeff(S.diff(t), 0).coeff(S.diff(t, 2), 0) / S)
print("S'' coefficient of S:", sp.simplify(sp.expand(coeffS0)))
print("  = gamma - aD + aD e^{-wt}: the paper's C^ = C + aD e^{-wt} should be C^ = aD (a constant)")
# I-equation: eliminate S via S = (I' + cI + f2 I)/d.
Sexpr = (I.diff(t) + c_ * I + f2 * I) / d_
eqI = sp.expand((Sexpr.diff(t) - (a_ * Sexpr - b_ * I)) * d_)
print("I-equation:", sp.collect(sp.simplify(eqI), [I.diff(t, 2), I.diff(t), I]))

# Numerical test of (A.13): I'' + [A - D e^{-wt}] I' + [B + C e^{-wt}] I = 0
pa, pb, pc, pd, pD, pw = 0.02, 1.0, 0.1, 0.05, 0.3, 0.5
beta, gamma = pa - pc, pb * pd - pa * pc
A, B, C = pD - beta, gamma - pa * pD, pD * (pa + pw)
Dt, At, Bt, Ct = pD / pw, 1 - A / pw, B / pw**2, C / pw**2
k = (-(At - 1) + np.sqrt((At - 1) ** 2 - 4 * Bt + 0j)) / 2  # root of k^2 + (A~-1)k + B~ = 0
k = complex(k)
# Correct reduction: with x = xi = e^{-wt}, y = x^k eta, eta solves Kummer's equation in z = -D~ x
# with parameters a_K = k + C~/D~, b_K = 2k + A~ (no exponential prefactor).
aK, bK = k + Ct / Dt, 2 * k + At
def I_correct(tt, c1=1.0, c2=0.0):
    x = mp.e ** (-pw * tt)
    z = -Dt * x
    return complex(x ** k * (c1 * hyp1f1(aK, bK, z) + c2 * hyperu(aK, bK, z)))
# The paper's version: h = (D~^2 - D~)/2, argument -D~^2 x, a~ = B(h)/A(h), prefactor e^{h x}
h = (Dt**2 - Dt) / 2
aP = (k * Dt**2 + At * (Dt**2 - Dt) / 2 + Ct) / Dt**2
def I_paper(tt):
    x = mp.e ** (-pw * tt)
    return complex(x ** k * mp.e ** (h * x) * hyp1f1(aP, bK, -Dt**2 * x))
def residual(fun, tt, eps=1e-4):
    f0, fp, fm = fun(tt), fun(tt + eps), fun(tt - eps)
    d1, d2 = (fp - fm) / (2 * eps), (fp - 2 * f0 + fm) / eps**2
    e = np.exp(-pw * tt)
    return abs(d2 + (A - pD * e) * d1 + (B + C * e) * f0) / max(abs(f0), 1e-30)
print(f"\ntest parameters a={pa}, b={pb}, c={pc}, d={pd}, D={pD}, w={pw}; k = {k:.4f}")
for tt in (0.5, 2.0, 5.0):
    print(f"  t={tt}: relative ODE residual  corrected {residual(I_correct, tt):.1e}   paper (A.21-A.23) {residual(I_paper, tt):.1e}")
