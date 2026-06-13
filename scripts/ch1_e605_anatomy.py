"""E-605 Ch1 trajectory gap anatomy (NEW audit, HRI=parallel-compute ground truth).
Pure arithmetic on the BANKED decision vector — DV and DT come straight from the
vector, NO heyoka propagation needed. Reconstructs the exact objective + decomposes
per-pair: binding term (mass vs time), DV distribution, headroom to the 4500 cap."""
import json, numpy as np

L = 3.84405000e8; Tn = 3.7567696752e5; V = L / Tn
SEC2DAY = 1.1574074074074073e-05; G0 = 9.80665
ROOT = "/home/julian/Projects/esa_spoc_26_3"
DATA = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"

ltl_raw = np.loadtxt(DATA + "LTL.txt", skiprows=1)
ltl = {(int(a), int(b)): w for a, b, w in ltl_raw}
moon = np.loadtxt(DATA + "Moon_orbits.txt", skiprows=1)[:, 1:]   # a,e,i
earth = np.loadtxt(DATA + "Earth_orbits.txt", skiprows=1)[:, 1:]

dv_vec = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
sol = np.array(dv_vec).reshape(-1, 21)
print("lines (slots):", len(sol))

rows = []
total = 0.0
for line in sol:
    ide = line[0]
    if ide < 0:
        continue
    ide, idl, idd = int(line[0]), int(line[1]), int(line[2])
    DVs = line[10:19].reshape(3, 3)
    T1, T2 = line[19], line[20]
    DV = sum(np.linalg.norm(d) for d in DVs) * V           # m/s
    DT = (T1 + T2) * Tn * SEC2DAY                            # days
    mass = np.exp(-DV / 311. / G0) * 5000 - 500
    cld = ltl[(idl, idd)]
    timeterm = (200 - DT) * cld
    real = timeterm if timeterm < mass else mass
    total += real
    rows.append((ide, idl, idd, DV, DT, mass, cld, timeterm, real,
                 "TIME" if timeterm < mass else "MASS", moon[idl][1], moon[idl][2], earth[ide][2]))

import numpy as np
a = np.array([(r[3], r[4], r[5], r[6], r[7], r[8], r[10], r[11], r[12]) for r in rows])
binding = [r[9] for r in rows]
print(f"\nRECONSTRUCTED TOTAL = {total:,.1f} kg   (bank ~236,420)")
print(f"filled pairs = {len(rows)} / 400   ({400-len(rows)} empty)")
print(f"avg per filled pair = {total/len(rows):,.1f} kg   (HRI 463,513 total)")
print(f"\n--- binding term ---")
from collections import Counter
print(Counter(binding))
mass_bound = [r for r in rows if r[9]=="MASS"]; time_bound=[r for r in rows if r[9]=="TIME"]
print(f"MASS-bound: {len(mass_bound)} pairs, sum score {sum(r[8] for r in mass_bound):,.0f}")
print(f"TIME-bound: {len(time_bound)} pairs, sum score {sum(r[8] for r in time_bound):,.0f}")
print(f"\n--- DV (m/s) over filled pairs ---")
print(f"  min {a[:,0].min():.0f}  p25 {np.percentile(a[:,0],25):.0f}  med {np.median(a[:,0]):.0f}  p75 {np.percentile(a[:,0],75):.0f}  max {a[:,0].max():.0f}")
print(f"--- DT (days) ---")
print(f"  min {a[:,1].min():.1f}  med {np.median(a[:,1]):.1f}  max {a[:,1].max():.1f}")
print(f"--- mass (kg) per pair ---")
print(f"  min {a[:,2].min():.0f}  med {np.median(a[:,2]):.0f}  max {a[:,2].max():.0f}   (cap at DV=0 is 4500)")
print(f"\n--- HEADROOM to mass cap ---")
cap = 4500.0
gap_to_cap = sum(min(cap, (200)*r[6]) - r[8] for r in rows)  # if DV->0 and DT->0
print(f"  if every filled pair went DV->0 (mass->4500, capped by time-term at DT->0): total -> {sum(min(cap,200*r[6]) for r in rows):,.0f}")
print(f"--- how many MASS-bound pairs have DV>3940 (above the supposed Hohmann floor) ---")
print(f"  {sum(1 for r in rows if r[3]>3940)} / {len(rows)}")
print(f"--- DV<3320 (leaders avg) pairs ---")
print(f"  {sum(1 for r in rows if r[3]<3320)} / {len(rows)}")
# eL of mass-bound expensive pairs
print(f"\n--- mass-bound DV percentiles by Moon eL ---")
for lo,hi,lbl in [(0,0.2,'low-eL'),(0.2,0.5,'mid-eL'),(0.5,1.0,'high-eL')]:
    sub=[r for r in mass_bound if lo<=r[10]<hi]
    if sub: print(f"  {lbl}: n={len(sub)} medDV={np.median([r[3] for r in sub]):.0f} medMass={np.median([r[5] for r in sub]):.0f}")
