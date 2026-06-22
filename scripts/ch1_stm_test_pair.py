"""E-701 step 2: drive the STM corrector on a real expensive pair.
CMA gets a near-feasible backward-shot (penalty ~1.3e4, Earth-side orbit match ~1km); the STM Newton
corrector should close it to 384m/1e-6 and pass official udp.fitness — where finite-diff DC stalled."""
import sys, time, numpy as np
import pygmo as pg
from scipy.optimize import minimize
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, state2earth, V, L
from ch1_backshoot_global import UDPBack, official_row, precise_dc_back
from ch1_stm_corrector import stm_newton_back, _pre_from_x, back_state_stm, _resid

ROOT = "/home/julian/Projects/esa_spoc_26_3"
IDE, IDL = 241, 50            # the canonical expensive circular pair, bank dv=6617

udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
prob_obj = UDPBack(udp, IDE, IDL)
aM, eM, iM = prob_obj.aM, prob_obj.eM, prob_obj.iM
aE, eE, iE = prob_obj.aE, prob_obj.eE, prob_obj.iE
prob = pg.problem(UDPBack(udp, IDE, IDL))
lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
cma = pg.algorithm(pg.cmaes(gen=250, force_bounds=True, ftol=1e-7, xtol=1e-7))

print(f"[E-701] STM corrector test on ({IDE},{IDL}) bank dv=6617", flush=True)
t0 = time.time()
seeds = []
for rs in range(10):
    rng = np.random.default_rng(7 * rs + 13)
    pop = pg.population(prob, size=0)
    for _ in range(24):
        pop.push_back(lb + rng.random(8) * (ub - lb))
    pop = cma.evolve(pop)
    xb = pop.champion_x; fb = float(pop.champion_f[0])
    seeds.append((fb, np.array(xb)))
    print(f"  cma rs{rs}: champ f={fb:.1f}  [{time.time()-t0:.0f}s]", flush=True)
seeds.sort(key=lambda s: s[0])

print(f"\n[E-701] best CMA seed f={seeds[0][0]:.1f}; applying correctors to the {min(4,len(seeds))} best seeds", flush=True)
best_official = None
for fb, xb in seeds[:4]:
    # baseline: where does the seed's Earth-side orbit sit before correction?
    ap, vp = _pre_from_x(xb, aM, eM, iM)
    o = back_state_stm(ap, vp, xb[6], xb[7])
    if o is None:
        print(f"  seed f={fb:.0f}: back-prop failed", flush=True); continue
    r0 = _resid(o[0], aE, eE, iE)
    print(f"  seed f={fb:.0f}: pre-DC a_miss={abs(r0[0])*L:.0f}m e={abs(r0[1]):.2e} i={abs(r0[2]):.2e}", flush=True)
    # STM Newton corrector
    xc, info = stm_newton_back(xb, aM, eM, iM, aE, eE, iE, iters=40, verbose=True)
    print(f"     -> STM-DC: ok={info['ok']} a_miss={info['a_miss_m']:.1f}m |r|={info['rnorm']:.2e} it={info['iters']}", flush=True)
    ov = official_row(udp, IDE, IDL, xc)
    if ov is not None:
        print(f"     ** OFFICIAL VALID dv={ov[1]:.0f} mass={ov[2]:.0f} (bank 6617, Δ{6617-ov[1]:+.0f}) **", flush=True)
        if best_official is None or ov[1] < best_official[1]:
            best_official = ov
    else:
        print(f"     official: rejected", flush=True)

print(f"\n[E-701] VERDICT: {'OFFICIAL-VALID sub-bank capture dv=%.0f' % best_official[1] if best_official else 'no official-valid solution'} [{time.time()-t0:.0f}s]", flush=True)
