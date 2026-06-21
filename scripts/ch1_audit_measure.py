"""Ch1-trajectory FRESH audit measurements (2026-06-21, user override: HRI used NO sophisticated
physics, so the gap is STRUCTURAL/ALGORITHMIC). Measures the unchecked assumptions."""
import json, math, numpy as np, sys
sys.path.insert(0, "src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, MU_EARTH, MU_MOON
udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
Ea, Ee, Ei = udp.earth_data[:, 0], udp.earth_data[:, 1], udp.earth_data[:, 2]
Ma, Me, Mi = udp.moon_data[:, 0], udp.moon_data[:, 1], udp.moon_data[:, 2]
Vunit = 3.84405e8 / 3.7567696752e5
L = 3.84405e8
bank = json.load(open("solutions/upload/trajectory.json"))[0]["decisionVector"]


def mass(dv): return 5000 * math.exp(-dv / 3050.0) - 500


print("=== A. ORBIT ENERGY STRUCTURE (never checked the Earth-orbit apogees!) ===")
Eapo = Ea * (1 + Ee); Eperi = Ea * (1 - Ee)
print(f"Earth a: {Ea.min():.3e}..{Ea.max():.3e} (in L={L:.2e} units: {Ea.min()/L:.3f}..{Ea.max()/L:.3f})")
print(f"Earth apogee r_a: {Eapo.min():.3e}..{Eapo.max():.3e}  (Moon dist L; apogee/L: {Eapo.min()/L:.3f}..{Eapo.max()/L:.3f})")
print(f"  Earth orbits with apogee > 0.5 Moon-dist (HIGH, cheap departure): {(Eapo>0.5*L).sum()}/400")
print(f"  Earth orbits with apogee > 0.9 Moon-dist (reaches Moon ballistic): {(Eapo>0.9*L).sum()}/400")
print(f"Earth ecc: {Ee.min():.3f}..{Ee.max():.3f} median {np.median(Ee):.3f} | incl(deg) {np.degrees(Ei.min()):.0f}..{np.degrees(Ei.max()):.0f}")
print(f"Moon  a: {Ma.min():.3e}..{Ma.max():.3e} ({Ma.min()/1.737e6:.1f}..{Ma.max()/1.737e6:.1f} R_moon)")

print("\n=== B. EMPTY SLOTS (we fly 326/400 - are the unused fillable?) ===")
used_e, used_l, used_d = set(), set(), set()
for i in range(0, len(bank), 21):
    if bank[i] < 0: continue
    used_e.add(int(bank[i])); used_l.add(int(bank[i+1])); used_d.add(int(bank[i+2]))
free_e = [i for i in range(400) if i not in used_e]
free_l = [i for i in range(400) if i not in used_l]
free_d = [i for i in range(400) if i not in used_d]
print(f"unused: {len(free_e)} Earth, {len(free_l)} Moon, {len(free_d)} D")
print(f"unused Moon ecc: {[f'{Me[l]:.2f}' for l in free_l[:20]]}")
print(f"unused Moon: circular(e<0.1)={sum(1 for l in free_l if Me[l]<0.1)} eccentric(e>0.5)={sum(1 for l in free_l if Me[l]>0.5)}")
print(f"unused Earth apogee/L: {[f'{Eapo[e]/L:.2f}' for e in free_e[:20]]}")

print("\n=== C. is the bank ENERGY-matched? (apogee of idE vs perilune need of idL) ===")
# for each filled pair, does a high-apogee Earth orbit pair with the (expensive) circular Moon orbit?
pairs = []
for i in range(0, len(bank), 21):
    if bank[i] < 0: continue
    r = bank[i:i+21]; e, l = int(r[0]), int(r[1])
    dv = (np.linalg.norm(r[10:13])+np.linalg.norm(r[13:16])+np.linalg.norm(r[16:19]))*Vunit
    pairs.append((e, l, dv, Eapo[e]/L, Me[l]))
pairs = np.array(pairs)
# corr of dv with Earth apogee (high apogee -> cheap?)
print(f"corr(bank dv, Earth-apogee/L) = {np.corrcoef(pairs[:,2], pairs[:,3])[0,1]:.3f}")
print(f"corr(bank dv, Earth-ecc)       = {np.corrcoef(pairs[:,2], [Ee[int(e)] for e in pairs[:,0]])[0,1]:.3f}")
# expensive circular pairs: what Earth apogee did they get?
exp = pairs[(pairs[:,2]>=4800)&(pairs[:,4]<0.1)]
cheap = pairs[(pairs[:,2]<2500)]
print(f"expensive circular pairs (n={len(exp)}): median Earth-apogee/L = {np.median(exp[:,3]):.3f}")
print(f"cheap pairs (dv<2500, n={len(cheap)}):    median Earth-apogee/L = {np.median(cheap[:,3]):.3f}")
print(f"  => if cheap pairs use HIGH-apogee Earth orbits and expensive use LOW, the ASSIGNMENT (energy match) is the lever")
