"""Premise reassessment: what TOF regime does the bank use, and is ΔV driven by tof?
If the bank uses long transfers and short (3-8d) ones are cleaner, the per-pair 'floor' is a
tof-regime artifact. Also re-examine the assignment: is dv truly apogee-separable (assignment
can't help) or pair-coupled (assignment is a lever)?"""
import json, math, numpy as np, sys
sys.path.insert(0, "src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, T
udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
L = 3.84405e8; Vunit = L / 3.7567696752e5
Tday = T / 86400.0
Ea, Ee = udp.earth_data[:, 0], udp.earth_data[:, 1]
Eapo = Ea * (1 + Ee)
bank = json.load(open("solutions/upload/trajectory.json"))[0]["decisionVector"]
rows = []
for i in range(0, len(bank), 21):
    if bank[i] < 0:
        continue
    r = bank[i:i + 21]
    dv0 = np.linalg.norm(r[10:13]) * Vunit; dv1 = np.linalg.norm(r[13:16]) * Vunit; dv2 = np.linalg.norm(r[16:19]) * Vunit
    tof_d = (r[19] + r[20]) * Tday
    rows.append((int(r[0]), int(r[1]), dv0, dv1, dv2, dv0 + dv1 + dv2, tof_d, Eapo[int(r[0])] / L))
P = np.array(rows)
tof = P[:, 6]; tot = P[:, 5]; dv0 = P[:, 2]; dv2 = P[:, 4]; apo = P[:, 7]
print("=== BANK TOF REGIME ===")
print(f"tof (days): min {tof.min():.1f} p25 {np.percentile(tof,25):.1f} median {np.median(tof):.1f} p75 {np.percentile(tof,75):.1f} max {tof.max():.1f}")
print(f"tof<8d: {(tof<8).sum()}  8-20d: {((tof>=8)&(tof<20)).sum()}  20-40d: {((tof>=20)&(tof<40)).sum()}  >40d: {(tof>=40).sum()}")
print(f"corr(total dv, tof) = {np.corrcoef(tot,tof)[0,1]:.3f} | corr(dv2 capture, tof) = {np.corrcoef(dv2,tof)[0,1]:.3f}")
# for low-apogee (expensive) pairs, does short tof correlate with lower total?
lo = apo < 0.03
print(f"\nlow-apogee pairs (n={lo.sum()}): tof median {np.median(tof[lo]):.1f}d  total median {np.median(tot[lo]):.0f}")
for a, b in [(0, 8), (8, 20), (20, 40), (40, 200)]:
    m = lo & (tof >= a) & (tof < b)
    if m.sum():
        print(f"  tof[{a},{b})d: n={m.sum():3d}  total dv median {np.median(tot[m]):.0f}  dv0 {np.median(dv0[m]):.0f}  dv2 {np.median(dv2[m]):.0f}")
print("\n=== ASSIGNMENT COUPLING: is dv ~ f(apogee) alone (separable -> assignment useless) or pair-coupled? ===")
# fit dv0 ~ apogee; residual variance = the pair-coupled part the assignment could exploit
from numpy.polynomial import polynomial as Pl
coef = np.polyfit(apo, dv0, 2); pred = np.polyval(coef, apo)
resid = dv0 - pred
print(f"dv0 ~ quad(apogee): R^2 = {1 - resid.var()/dv0.var():.3f}  residual std = {resid.std():.0f} m/s")
print(f"  => high R^2 (~1) means dv0 is APOGEE-SEPARABLE -> assignment can't lower fleet dv0 (only fill matters)")
print(f"  => low R^2 means dv0 is PAIR-COUPLED -> a better idE->idL assignment IS a lever")
