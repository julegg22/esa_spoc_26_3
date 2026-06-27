"""E-731 — precompute ALL cheap-edge windows for the medium order search at a given resolution, saved to the
shared base pkl. Then finder chains load it and run DP-ONLY (no per-move edge scans) -> ~ms/iter instead of ~3.7s.
Multi-threaded (numba parallel scan) -> ~45min for 3152 cheap edges at 0.05d. Usage: CH2_TQ=0.05 python ch2_medium_precompute_all.py"""
import os, sys, time, pickle
os.environ.setdefault("CH2_TQ", "0.05"); os.environ.setdefault("CH2_TOFSTEP", "0.02")
import importlib.util
spec = importlib.util.spec_from_file_location("ms", "/home/julian/Projects/esa_spoc_26_3/scripts/ch2_medium_order_search.py")
ms = importlib.util.module_from_spec(spec); spec.loader.exec_module(ms)
edges = sorted(ms.CHEAP)
print(f"[pre-all] TQ={ms.TQ} scanning {len(edges)} cheap edges; base has {len(ms._EDGE)} already", flush=True)
t0 = time.time()
for k, (i, j) in enumerate(edges):
    ms._edge_win(i, j)                                          # scans + caches into ms._EDGE
    if k % 200 == 199:
        pickle.dump(ms._EDGE, open(ms._BASE, "wb"))
        print(f"[pre-all] {k+1}/{len(edges)} ({len(ms._EDGE)} cached) [{time.time()-t0:.0f}s]", flush=True)
pickle.dump(ms._EDGE, open(ms._BASE, "wb"))
print(f"[pre-all] DONE {len(ms._EDGE)} edge-windows -> {ms._BASE} [{time.time()-t0:.0f}s]", flush=True)
