"""Ch1 audit: is the gap a SELECTION/ASSIGNMENT lever (use high-apogee Earth orbits) or per-pair?"""
import json, math, numpy as np, sys
sys.path.insert(0, "src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
Ea, Ee, Ei = udp.earth_data[:, 0], udp.earth_data[:, 1], udp.earth_data[:, 2]
L = 3.84405e8; Vunit = L / 3.7567696752e5
Eapo = Ea * (1 + Ee)
bank = json.load(open("solutions/upload/trajectory.json"))[0]["decisionVector"]
mass = lambda dv: 5000 * math.exp(-dv / 3050.0) - 500

used_e = set(); pairs = []
for i in range(0, len(bank), 21):
    if bank[i] < 0: continue
    r = bank[i:i+21]; e = int(r[0])
    used_e.add(e)
    dv0 = np.linalg.norm(r[10:13]) * Vunit
    dv1 = np.linalg.norm(r[13:16]) * Vunit
    dv2 = np.linalg.norm(r[16:19]) * Vunit
    pairs.append((e, dv0, dv1, dv2, dv0+dv1+dv2, Eapo[e]/L))
P = np.array(pairs)

print("=== dV0/dv1/dv2 split (confirm departure-dominance) ===")
print(f"dv0 (departure): mean {P[:,1].mean():.0f}  | dv1 (mid): mean {P[:,2].mean():.0f} | dv2 (capture): mean {P[:,3].mean():.0f}")
print(f"dv0 share of total: {P[:,1].sum()/P[:,4].sum()*100:.0f}%  | dv0>dv2 in {(P[:,1]>P[:,3]).mean()*100:.0f}% of pairs")

print("\n=== EARTH-APOGEE UTILIZATION (the selection lever) ===")
order = np.argsort(-Eapo)                      # highest apogee first
print(f"all 400 Earth apogee/L: top10 {[f'{Eapo[i]/L:.3f}' for i in order[:10]]}")
print(f"               bottom10 {[f'{Eapo[i]/L:.3f}' for i in order[-10:]]}")
used_mask = np.array([i in used_e for i in range(400)])
ua = Eapo[used_mask] / L; nua = Eapo[~used_mask] / L
print(f"USED (326): apogee/L mean {ua.mean():.3f} median {np.median(ua):.3f} min {ua.min():.3f} max {ua.max():.3f}")
print(f"UNUSED(74): apogee/L mean {nua.mean():.3f} median {np.median(nua):.3f} min {nua.min():.3f} max {nua.max():.3f}")
# are any HIGH-apogee Earth orbits unused? (the smoking gun for a selection bug)
hi_thresh = np.percentile(Eapo/L, 75)
hi_unused = [i for i in range(400) if not used_mask[i] and Eapo[i]/L > hi_thresh]
print(f"HIGH-apogee (>p75={hi_thresh:.3f}) Earth orbits UNUSED: {len(hi_unused)}  apogees {[f'{Eapo[i]/L:.3f}' for i in hi_unused[:15]]}")
print(f"  => if many high-apogee orbits are UNUSED, the bank's (inclination) selection wasted the energy dimension = LEVER")

print("\n=== dV0 vs apogee tightness (is dv0 ~ pure function of apogee?) ===")
print(f"corr(dv0, apogee/L) = {np.corrcoef(P[:,1], P[:,5])[0,1]:.3f}")
# bin dv0 by apogee to see the achievable dv0 per apogee
for lo, hi in [(0.0,0.03),(0.03,0.06),(0.06,0.09),(0.09,0.12)]:
    m = (P[:,5]>=lo)&(P[:,5]<hi)
    if m.sum(): print(f"  apogee/L [{lo:.2f},{hi:.2f}): n={m.sum():3d}  dv0 min {P[m,1].min():.0f} median {np.median(P[m,1]):.0f}  total_dv median {np.median(P[m,4]):.0f}")
