import sys
sys.path.insert(0, 'src')
from esa_spoc_26.ch1_trajectory import LtlTrajectory
from esa_spoc_26.ch1_traj_lambert_dc import best_lambert_seed, lambert_dc
udp = LtlTrajectory('reference/SpOC4/Challenge 1 Luna Tomato Logistics/')
for e, l in [(241, 50), (139, 31), (249, 22)]:
    print(f"\n##### pair ({e},{l}) #####", flush=True)
    seed = best_lambert_seed(udp, e, l)
    print(f"  lambert seed total dv = {seed['total']:.0f} (dv1={seed['dv1_mag']:.0f} dv2={seed['dv2_mag']:.0f} tof={seed['tof_d']}d)", flush=True)
    # default nfev
    r60 = lambert_dc(udp, e, l, seed, max_nfev=60, verbose=True)
    print(f"  nfev=60 -> {'None' if r60 is None else ('fit=%.4f' % r60[1])}", flush=True)
    # stronger
    r400 = lambert_dc(udp, e, l, seed, max_nfev=400, verbose=True)
    print(f"  nfev=400 -> {'None' if r400 is None else ('fit=%.4f cost=%.2e' % (r400[1], r400[2]))}", flush=True)
