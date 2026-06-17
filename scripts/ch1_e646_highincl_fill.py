"""E-646 (E1b) — DECISIVE: are the 24 uncovered high-incl idE fillable at good mass?

The cache generator (bcp_apogee_expand) scored candidate idL by a Hohmann bound that
IGNORES inclination, top-3 only -> high-incl idE were tried against wrong (coplanar)
idL or not at all (24 have ZERO entries). E-047 concluded empties ~1kg, but it may
have tested the wrong pairings. Here: real-solve each of the 24 uncovered idE against
its 6 INCLINATION-MATCHED unused idL (the |iE-iL| key), trusted BCP-apogee 3-impulse.

If most fill at mass>500kg -> high-incl region IS fillable with the right idL ->
the gap is COVERAGE/ASSIGNMENT (A2/A4 falsified, E-047 was wrong pairing) -> build
the dense-matrix assignment pipeline. If ~1kg -> E-047 stands.
Read-only (/tmp). Usage: python ch1_e646_highincl_fill.py [n_idL_per_e=6] [nworkers=4]
"""
import sys, json, glob, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
B = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = {}

def _init():
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    _UDP[0] = LtlTrajectory(B)

def solve_pair(args):
    from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
    idE, idL = args; udp = _UDP[0]; best = None
    for raan_e in np.linspace(0, 2*np.pi, 4, endpoint=False):   # coarse: 4x2x2x2x2x2=128
        for argp_e in (0.0, np.pi):
            for ea_dep in (0.0, np.pi):
                for t0_val in (0.0, np.pi):
                    for ea_arr in (0.0, np.pi):
                        for t2_d in (0.4, 1.0):
                            res = try_bcp_apogee_3impulse(udp, idE, idL, raan_e, argp_e,
                                  ea_dep, t0_val, 0.0, 0.0, ea_arr, t2_d=t2_d)
                            if res is not None and (best is None or res[0] > best[0]):
                                best = res
    return idE, idL, (best[0] if best else None)

def main(nidl=6, nw=4):
    E = np.loadtxt(B+"Earth_orbits.txt"); M = np.loadtxt(B+"Moon_orbits.txt")
    ie = E[:,3]; il = M[:,3]
    # uncovered idE (zero cache entries)
    cov=set()
    for f in glob.glob(f"{ROOT}/runs/ch1/*results.json")+glob.glob("/tmp/*results.json"):
        try: d=json.load(open(f))
        except: continue
        if isinstance(d,dict):
            for k in d:
                try: cov.add(int(k.split(",")[0]))
                except: pass
    uncovered = sorted(set(range(400))-cov)
    # bank-used idL
    dv = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    used_l = set(int(dv[i+1]) for i in range(0,len(dv),21) if dv[i]>=0)
    free_l = [l for l in range(400) if l not in used_l]
    print(f"E-646: {len(uncovered)} uncovered idE (incl {np.degrees(ie[uncovered]).min():.0f}-"
          f"{np.degrees(ie[uncovered]).max():.0f}deg); {len(free_l)} free idL", flush=True)
    # build pairs: each uncovered idE x its nidl inclination-closest FREE idL
    pairs=[]
    for e in uncovered:
        order=sorted(free_l, key=lambda l: abs(ie[e]-il[l]))[:nidl]
        for l in order: pairs.append((e,l))
    print(f"solving {len(pairs)} real pairs ({nidl} incl-matched idL per idE), ~{len(pairs)*60/nw/60:.0f}min", flush=True)
    bestmass={}; ndone=0
    with mp.Pool(nw, initializer=_init) as p:
        for e,l,m in p.imap_unordered(solve_pair, pairs, chunksize=1):
            ndone+=1
            if m is not None and (e not in bestmass or m>bestmass[e][1]):
                bestmass[e]=(l,m)
            if m is not None and m>50:
                print(f"  [{ndone}/{len(pairs)}] idE {e} (i={np.degrees(ie[e]):.0f}) -> idL {l}: {m:.0f} kg", flush=True)
            elif ndone%8==0:
                print(f"  [{ndone}/{len(pairs)}] ... (idE {e} best so far {bestmass.get(e,('-',0))[1]:.0f}kg)", flush=True)
    print(f"\n=== E-646 RESULT (best inclination-matched fill per uncovered idE) ===", flush=True)
    masses=[]
    for e in uncovered:
        if e in bestmass:
            l,m=bestmass[e]; masses.append(m)
            print(f"  idE {e:3d} (i={np.degrees(ie[e]):.1f}deg) -> idL {l:3d} (i={np.degrees(il[l]):.1f}): {m:.0f} kg", flush=True)
        else:
            print(f"  idE {e:3d} (i={np.degrees(ie[e]):.1f}deg) -> NO feasible", flush=True)
    masses=np.array(masses)
    if len(masses):
        print(f"\n  fillable: {len(masses)}/{len(uncovered)}; mass med={np.median(masses):.0f} "
              f"mean={masses.mean():.0f} >500kg={int((masses>500).sum())} >100kg={int((masses>100).sum())}", flush=True)
        print(f"  E-047 claimed ~1kg. If med>>1kg -> A4 FALSIFIED, fill lever REAL, build dense pipeline.", flush=True)
        if len(masses): print(f"  potential fill mass (these {len(masses)} idE): +{masses.sum():.0f} kg toward bank", flush=True)

if __name__=="__main__":
    nidl=int(sys.argv[1]) if len(sys.argv)>1 else 6
    nw=int(sys.argv[2]) if len(sys.argv)>2 else 4
    main(nidl,nw)
