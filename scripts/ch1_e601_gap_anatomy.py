"""E-601 — Ch1 trajectory gap anatomy: where is the mass gap to the leaders?

Bank 236,420 kg / 301 filled pairs. R3~463k, leaders' implied ~1180 kg/pair.
Decompose: (a) per-pair dv level (our avg vs the sub-Hohmann leaders),
(b) the 99 EMPTY slots (which Earth/Moon/Dest orbits are unused, and are the
unused Earth orbits the hard high-inclination ones?).
Pure arithmetic on the bank + orbit tables. Diagnostic, no bank write.
"""
import json
import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
D = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics"
BANK = f"{ROOT}/solutions/upload/trajectory.json"
L = 3.84405000e8
T = 3.7567696752e5
V = L / T
G0 = 9.80665
SEC2DAY = 1.0 / 86400.0

earth = np.loadtxt(f"{D}/Earth_orbits.txt", skiprows=1)[:, 1:]  # a,e,i
moon = np.loadtxt(f"{D}/Moon_orbits.txt", skiprows=1)[:, 1:]
bank = np.array(json.load(open(BANK))[0]["decisionVector"]).reshape(-1, 21)
filled = bank[bank[:, 0] >= 0]
idE = filled[:, 0].astype(int)
idL = filled[:, 1].astype(int)
idD = filled[:, 2].astype(int)
DVs = filled[:, 10:19].reshape(-1, 3, 3)
dv = np.sum(np.linalg.norm(DVs, axis=2), axis=1) * V
DT = np.sum(filled[:, 19:21], axis=1) * T * SEC2DAY
mass = np.exp(-dv / 311.0 / G0) * 5000.0 - 500.0

print("=== (a) per-pair dv / mass level ===")
print(f"dv m/s: min {dv.min():.0f} p25 {np.percentile(dv,25):.0f} "
      f"med {np.median(dv):.0f} mean {dv.mean():.0f} "
      f"p75 {np.percentile(dv,75):.0f} max {dv.max():.0f}")
print(f"mass kg: mean {mass.mean():.0f} total {mass.sum():,.0f}")
# what would total be at leaders' avg dv 3320?
m3320 = np.exp(-3320.0 / 311.0 / G0) * 5000.0 - 500.0
print(f"if every filled pair had dv=3320 (leader avg): {m3320:.0f} kg/pair "
      f"-> {m3320*len(filled):,.0f} kg (filled only)")
print(f"impulsive Hohmann floor ~3940 -> "
      f"{(np.exp(-3940/311/G0)*5000-500):.0f} kg/pair")
# dv vs Earth inclination
iE_deg = np.degrees(earth[idE, 2])
print(f"\ndv vs Earth incl: corr(dv,iE)={np.corrcoef(dv,iE_deg)[0,1]:.2f}")
for lo, hi in [(0, 10), (10, 40), (40, 70), (70, 200)]:
    m = (iE_deg >= lo) & (iE_deg < hi)
    if m.sum():
        print(f"  iE[{lo:3d},{hi:3d})deg: n={m.sum():3d} "
              f"dv_mean={dv[m].mean():.0f} mass_mean={mass[m].mean():.0f}")

print("\n=== (b) the 99 empty slots ===")
usedE, usedL, usedD = set(idE), set(idL), set(idD)
freeE = sorted(set(range(400)) - usedE)
freeL = sorted(set(range(400)) - usedL)
freeD = sorted(set(range(400)) - usedD)
print(f"unused Earth={len(freeE)} Moon={len(freeL)} Dest={len(freeD)}")
ie_free = np.degrees(earth[freeE, 2])
ie_used = np.degrees(earth[list(usedE), 2])
print(f"unused Earth incl deg: min {ie_free.min():.1f} med "
      f"{np.median(ie_free):.1f} max {ie_free.max():.1f}")
print(f"used   Earth incl deg: min {ie_used.min():.1f} med "
      f"{np.median(ie_used):.1f} max {ie_used.max():.1f}")
# inclination histogram of ALL 400 earth orbits vs used
allie = np.degrees(earth[:, 2])
for lo, hi in [(0, 10), (10, 40), (40, 70), (70, 200)]:
    tot = ((allie >= lo) & (allie < hi)).sum()
    usd = ((ie_used >= lo) & (ie_used < hi)).sum()
    print(f"  iE[{lo:3d},{hi:3d})deg: used {usd:3d}/{tot:3d} "
          f"({100*usd/max(tot,1):.0f}%)")
il_free = np.degrees(moon[freeL, 2])
print(f"unused Moon incl deg: min {il_free.min():.1f} med "
      f"{np.median(il_free):.1f} max {il_free.max():.1f}")
print(f"\nGAP SUMMARY: bank {mass.sum():,.0f} | fill-99-at-current-avg "
      f"+{mass.mean()*99:,.0f} -> {mass.sum()+mass.mean()*99:,.0f} | "
      f"+dv-to-3320 on 400 -> {m3320*400:,.0f}")
