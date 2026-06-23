"""E-704 — trajectory ΔV-cost ASSIGNMENT re-match: SAMPLE test before the full realization.

The headroom check showed the bank's Earth<->Moon matching is inclination-suboptimal (mean |iE-iL|
18.63deg vs Hungarian-optimal 13.45deg, 391/400 re-matchable). But the mass upside is bounded by the
plane-change cost (cheap at lunar apogee). This measures the ACTUAL realized Δmass on a sample of
re-matched pairs (solve the new (e,l_new) via the eccentric backward-shoot solver, compare to the bank's
realized mass for that Earth orbit) -> decides whether the ~13h full re-assignment is worth it.

Usage: python ch1_assign_sample.py [n_sample=12] [seed=0]"""
import sys, json, time
import numpy as np
from scipy.optimize import linear_sum_assignment
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V
from ch1_ecc_fleet import solve_pair
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def main(n_sample=12, seed=0):
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    ed, md = udp.earth_data, udp.moon_data
    dv = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    n = len(dv) // 21
    # bank pairs: (slot, idE, idL, idD, bank_mass)
    rows = []
    for i in range(n):
        r = dv[i * 21:i * 21 + 21]
        if r[0] < 0:
            continue
        m = udp.fitness(r)[0]
        rows.append({"e": int(r[0]), "l": int(r[1]), "d": int(r[2]),
                     "bank_mass": -m if m < 0 else 0.0})
    usedE = np.array([r["e"] for r in rows]); usedL = np.array([r["l"] for r in rows])
    # Hungarian min Σ|iE-iL| over the same orbit sets
    C = np.abs(ed[usedE, 2][:, None] - md[usedL, 2][None, :])
    ri, ci = linear_sum_assignment(C)
    l_new = {int(usedE[a]): int(usedL[b]) for a, b in zip(ri, ci)}
    # sample re-matched Earth orbits (new Moon != bank Moon)
    rng = np.random.default_rng(seed)
    changed = [r for r in rows if l_new[r["e"]] != r["l"]]
    samp = list(rng.choice(len(changed), size=min(n_sample, len(changed)), replace=False))
    print(f"[E-704] {len(changed)}/{len(rows)} re-matched; sampling {len(samp)} to realize", flush=True)
    print(f"[E-704] mean|iE-iL| bank {np.degrees(np.abs(ed[usedE,2]-md[usedL,2]).mean()):.2f} -> "
          f"opt {np.degrees(C[ri,ci].mean()):.2f} deg", flush=True)
    t0 = time.time(); d_old = d_new = 0.0; wins = 0
    for k in samp:
        r = changed[k]; e = r["e"]; lo = r["l"]; ln = l_new[e]; d = r["d"]
        res = solve_pair(udp, e, ln, d, restarts=6, gen=180)
        nm = res[2] if res is not None else 0.0
        d_old += r["bank_mass"]; d_new += nm; wins += (nm > r["bank_mass"])
        print(f"  E{e}: bank(l{lo})={r['bank_mass']:.0f} -> remix(l{ln})={nm:.0f} "
              f"(Δ{nm-r['bank_mass']:+.0f}) [{time.time()-t0:.0f}s]", flush=True)
    gain = d_new - d_old
    print(f"\n[E-704] SAMPLE: {wins}/{len(samp)} improved; Σ bank {d_old:.0f} -> remix {d_new:.0f} "
          f"(Δ{gain:+.0f} kg over {len(samp)} pairs = {gain/len(samp):+.0f}/pair)", flush=True)
    extrap = gain / len(samp) * len(changed)
    print(f"[E-704] EXTRAPOLATED full re-assignment gain ~{extrap:+.0f} kg over {len(changed)} pairs "
          f"(vs +42k needed for rank-5).", flush=True)
    if gain / len(samp) > 30:
        print(f"[E-704] -> worth the full realization (build sharded re-solve of all {len(changed)} re-matched pairs).", flush=True)
    else:
        print(f"[E-704] -> marginal; the inclination re-match does NOT translate to enough mass (plane change cheap). "
              f"Departure-energy wall holds. Reconsider before the ~13h build.", flush=True)


if __name__ == "__main__":
    ns = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    main(ns, sd)
