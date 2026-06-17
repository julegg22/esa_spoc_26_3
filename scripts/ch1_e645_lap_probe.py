"""E-645 — assumption-falsifying probe E1: dense surrogate matrix + exact LAP.

Tests A1/A2/A4: is the trajectory gap an ASSIGNMENT/coverage problem (sparse 3.8%
matrix, 24 idE uncovered) rather than a per-pair physics problem? Fit a data-driven
dv surrogate on our 6127 REAL cached (idE,idL) costs, cross-validate (trust gate),
predict the full 400x400, solve the EXACT linear assignment (E->L, mass-bound
approx), and report predicted fill + total vs bank 249k. LAP-selected pairs NOT in
cache are flagged for real-solver validation (do NOT trust surrogate as a score).
Read-only. Usage: python ch1_e645_lap_probe.py
"""
import json, glob
import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import cross_val_predict, KFold
B = "reference/SpOC4/Challenge 1 Luna Tomato Logistics/"

E = np.loadtxt(B + "Earth_orbits.txt")   # id, a, e, i
M = np.loadtxt(B + "Moon_orbits.txt")
ae, ee, ie = E[:, 1], E[:, 2], E[:, 3]
al, el, il = M[:, 1], M[:, 2], M[:, 3]

def feats(e, l):
    return [ae[e], ee[e], ie[e], al[l], el[l], il[l], abs(ie[e] - il[l]),
            ae[e] * (1 + ee[e]), al[l] * (1 - el[l]), ie[e] + il[l]]

def mass_of(dv):
    return np.exp(-dv / 311.0 / 9.80665) * 5000 - 500.0

# ---- gather real (idE,idL)->min dv from caches ----
best = {}
for f in glob.glob("runs/ch1/*results.json") + glob.glob("/tmp/*results.json"):
    try: d = json.load(open(f))
    except: continue
    if not isinstance(d, dict): continue
    for k, v in d.items():
        try:
            e, l = map(int, k.split(",")); dv = float(v[-1])
        except: continue
        if dv <= 0 or dv > 9000: continue
        if (e, l) not in best or dv < best[(e, l)]:
            best[(e, l)] = dv
X = np.array([feats(e, l) for (e, l) in best]); y = np.array(list(best.values()))
print(f"training samples: {len(y)} real (idE,idL) dv; dv range {y.min():.0f}-{y.max():.0f}", flush=True)

# ---- cross-validated surrogate (trust gate) ----
reg = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_depth=6)
cvp = cross_val_predict(reg, X, y, cv=KFold(5, shuffle=True, random_state=0))
ss_res = ((y - cvp) ** 2).sum(); ss_tot = ((y - y.mean()) ** 2).sum()
r2 = 1 - ss_res / ss_tot; mae = np.abs(y - cvp).mean()
print(f"surrogate 5-fold CV: R2={r2:.3f}  MAE={mae:.0f} m/s", flush=True)
# high-incl reliability: CV error on samples with ie>50deg
hi = ie[np.array([e for (e, l) in best])] > np.radians(50)
print(f"  high-incl(>50deg) training samples: {hi.sum()}; CV MAE there: "
      f"{np.abs(y - cvp)[hi].mean() if hi.sum() else float('nan'):.0f} m/s", flush=True)

reg.fit(X, y)

# ---- predict full 400x400 + exact LAP ----
allX = np.array([feats(e, l) for e in range(400) for l in range(400)])
dv_pred = reg.predict(allX).reshape(400, 400)
m_pred = mass_of(dv_pred); m_pred[m_pred < 0] = 0.0   # negative-mass = not worth filling
row, col = linear_sum_assignment(-m_pred)             # maximize total mass
sel_m = m_pred[row, col]; sel_dv = dv_pred[row, col]
pos = sel_m > 1.0
print(f"\n=== LAP on full 400x400 surrogate matrix ===", flush=True)
print(f"  filled (pos mass): {pos.sum()}/400   predicted TOTAL = {sel_m[pos].sum():.0f} kg "
      f"(bank=249264, r5=372729, r1=473333)", flush=True)
print(f"  mean predicted dv (filled): {sel_dv[pos].mean():.0f} m/s (bank ~3900 refined)", flush=True)
hi_sel = ie[row[pos]] > np.radians(50)
print(f"  high-incl(>50deg) idE filled: {hi_sel.sum()} (bank fills ~0 of the 24 uncovered)", flush=True)
in_cache = sum(1 for e, l in zip(row[pos], col[pos]) if (e, l) in best)
print(f"  of {pos.sum()} selected pairs, {in_cache} are in our real cache, "
      f"{pos.sum()-in_cache} are SURROGATE-ONLY (need real-solver validation)", flush=True)
print(f"\n  CAVEAT: predicted total is surrogate; trust only if CV R2 high AND high-incl MAE sane.", flush=True)
print(f"  VERDICT: if LAP total >> 249k by filling ~400 incl high-incl -> assignment/coverage IS "
      f"the gap (A1/A2/A4 falsified). Next: validate the surrogate-only high-incl pairs with real solver.", flush=True)
