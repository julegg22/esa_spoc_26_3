"""E-602 — Ch1 trajectory: is the MATCHING leaving plane-change value on the
table, independent of the solver? (Phase-4 experiment 2, violates A2.)

Two questions, pure arithmetic on the bank + orbit tables (no propagation):

(A) MATCHING STRUCTURE. The plane-change cost is driven by |iE-iL|. Compare the
    current bank matching's |iE-iL| against an OPTIMAL |iE-iL|-minimizing perfect
    matching over all 400 Earth x 400 Moon (Hungarian). Does the current matching
    strand high-incl Earth orbits that an inclination-aware matching would pair
    with the (existing, unused) high-incl Moon orbits?

(B) dv DRIVER. Regress the 301 realized bank dv on geometric features
    (|iE-iL|, iE, iL, eL, ...). If |iE-iL| dominates -> matching/re-pairing lever.
    If dv stays high even at small |iE-iL| -> the cost is intrinsic to the
    impulsive architecture (-> WSB), not the matching.

Diagnostic only, no bank write.
"""
import json
import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT = "/home/julian/Projects/esa_spoc_26_3"
D = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics"
BANK = f"{ROOT}/solutions/upload/trajectory.json"
L = 3.84405000e8
T = 3.7567696752e5
V = L / T
G0 = 9.80665
SEC2DAY = 1.0 / 86400.0
MU_E = 398600435507000.0  # m^3/s^2

earth = np.loadtxt(f"{D}/Earth_orbits.txt", skiprows=1)[:, 1:]  # a(m),e,i(rad)
moon = np.loadtxt(f"{D}/Moon_orbits.txt", skiprows=1)[:, 1:]
bank = np.array(json.load(open(BANK))[0]["decisionVector"]).reshape(-1, 21)
filled = bank[bank[:, 0] >= 0]
idE = filled[:, 0].astype(int)
idL = filled[:, 1].astype(int)
DVs = filled[:, 10:19].reshape(-1, 3, 3)
dv = np.sum(np.linalg.norm(DVs, axis=2), axis=1) * V
iE_all = np.degrees(earth[:, 2])
iL_all = np.degrees(moon[:, 2])

# ---------- (A) matching structure: |iE - iL| ----------
di_cur = np.abs(iE_all[idE] - iL_all[idL])
print("=== (A) |iE-iL| plane-change angle ===")
print(f"current matching |iE-iL| deg: mean {di_cur.mean():.1f} "
      f"med {np.median(di_cur):.1f} max {di_cur.max():.1f}")
hi = iE_all[idE] > 70
print(f"  filled high-incl (iE>70): n={hi.sum()} "
      f"mean|di|={di_cur[hi].mean():.1f} (these cost the most dv)")

# plane-change dv proxy at lunar-distance apogee: dv_pc = 2 v_apo sin(di/2)
r_apo = L  # ~ lunar distance
def vapo(a_e):
    a_tr = (7.0e6 + r_apo) / 2.0  # LEO peri ~7000 km -> lunar apo
    return np.sqrt(MU_E * (2.0 / r_apo - 1.0 / a_tr))
v_a = vapo(None)
print(f"  v_apo at lunar dist ~ {v_a:.1f} m/s -> dv_pc(90deg) "
      f"~ {2*v_a*np.sin(np.radians(90)/2):.1f} m/s "
      f"(apogee plane change is CHEAP geometrically)")

# optimal perfect |iE-iL| matching over ALL 400x400
C = np.abs(iE_all[:, None] - iL_all[None, :])  # 400x400 angle cost
ri, cj = linear_sum_assignment(C)
di_opt = C[ri, cj]
print(f"optimal |iE-iL| matching (all 400 paired): mean {di_opt.mean():.1f} "
      f"med {np.median(di_opt):.1f} max {di_opt.max():.1f}")
print(f"  => an inclination-aware matching can pair ALL 400 with "
      f"mean plane-change {di_opt.mean():.1f} deg vs current {di_cur.mean():.1f}")
# can stranded high-incl Earth get a compatible Moon?
usedE = set(idE)
freeE = [i for i in range(400) if i not in usedE]
freeE_hi = [i for i in freeE if iE_all[i] > 70]
# nearest-incl Moon for each stranded high-incl Earth (over ALL moons)
print(f"\n  stranded high-incl Earth (iE>70, unused): n={len(freeE_hi)}")
nn = [np.min(np.abs(iE_all[i] - iL_all)) for i in freeE_hi]
print(f"  min available |iE-iL| for each (over all 400 Moon orbits): "
      f"mean {np.mean(nn):.1f} med {np.median(nn):.1f} max {np.max(nn):.1f}")
print(f"  => {sum(1 for x in nn if x < 5)}/{len(freeE_hi)} have a Moon orbit "
      f"within 5 deg inclination (plane-change-compatible)")

# ---------- (B) dv driver regression ----------
print("\n=== (B) what drives realized dv? (301 filled pairs) ===")
feats = {
    "|iE-iL|": di_cur,
    "iE": iE_all[idE],
    "iL": iL_all[idL],
    "eL": moon[idL, 1],
    "eE": earth[idE, 1],
}
for name, f in feats.items():
    print(f"  corr(dv, {name:7s}) = {np.corrcoef(dv, f)[0,1]:+.2f}")
# multiple linear regression
X = np.column_stack([np.ones(len(dv))] + [f for f in feats.values()])
coef, *_ = np.linalg.lstsq(X, dv, rcond=None)
pred = X @ coef
ss_res = np.sum((dv - pred) ** 2)
ss_tot = np.sum((dv - dv.mean()) ** 2)
print(f"  linear model R^2 = {1 - ss_res/ss_tot:.2f}")
# dv at SMALL |iE-iL| -- is it still high? (intrinsic floor test)
small = di_cur < 5
print(f"  pairs with |iE-iL|<5deg: n={small.sum()} "
      f"dv_mean={dv[small].mean():.0f} (Hohmann floor ~3940)")
big = di_cur > 40
if big.sum():
    print(f"  pairs with |iE-iL|>40deg: n={big.sum()} "
          f"dv_mean={dv[big].mean():.0f}")
print("\nINTERPRETATION: if |iE-iL|<5 pairs still sit well above 3940 m/s, the "
      "cost is intrinsic to the impulsive architecture (->WSB), not matchable away.")
