"""E-731 — Ch2-MEDIUM harvester: the fast 0.05d finder chains save proxy-best ORDERS; this re-times each at
0.025d (ZERO handicap) + official kt.fitness, and banks the global best < 189.10 (better-bank) / < 186.27 (RANK-1).
The two-stage decoupling: fast 0.05d search finds good orders, fine 0.025d re-time reveals true makespan.
Runs continuously (light: only re-times when a finder's proxy-best changes). Usage: python ch2_medium_harvest.py"""
import os, sys, json, time, hashlib
os.environ["CH2_TQ"] = "0.025"; os.environ["CH2_TOFSTEP"] = "0.02"
import importlib.util
spec = importlib.util.spec_from_file_location("ms", "/home/julian/Projects/esa_spoc_26_3/scripts/ch2_medium_order_search.py")
ms = importlib.util.module_from_spec(spec); spec.loader.exec_module(ms)
ROOT = "/home/julian/Projects/esa_spoc_26_3"
BANK = 189.10
best = BANK; seen = {}
print(f"[harvest] 0.025d re-validation of finder proxy-bests; bank={BANK}, live r1=186.27", flush=True)
t0 = time.time()
while True:
    for tag in ["m1", "m2", "m3", "m4"]:
        f = f"{ROOT}/cache/ch2_medium_proxybest_{tag}.json"
        try:
            o = json.load(open(f)); order = [int(c) for c in o["order"]]
        except Exception:
            continue
        h = hashlib.md5(str(order).encode()).hexdigest()
        if seen.get(tag) == h:
            continue                                            # unchanged proxy-best, skip
        seen[tag] = h
        mk, ti, tf, eu = ms.retime(order)
        if ti is None:
            continue
        dv = list(ti) + list(tf) + [float(c) for c in order]
        fit = ms.kt.fitness(dv); omk = float(fit[0]); viols = [float(x) for x in fit[1:]]
        feas = max(viols) <= 1e-6
        if feas and omk < best - 1e-6:
            best = omk
            out = f"{ROOT}/cache/ch2_medium_BEST_{omk:.3f}.json"
            json.dump([{"decisionVector": dv, "problem": "medium",
                        "challenge": "spoc-4-keplerian-tomato-traveling-salesperson"}], open(out, "w"))
            json.dump([{"decisionVector": dv}], open(f"{ROOT}/cache/ch2_medium_BEST.json", "w"))
            tg = "*** RANK-1 (<186.27)! ESCALATE" if omk < 186.27 else "better-than-bank"
            print(f"[harvest] {tag}: 0.05-proxy {o.get('proxy',0):.2f} -> OFFICIAL {omk:.3f}d feasible -> {tg} "
                  f"(saved {out}) [{time.time()-t0:.0f}s]", flush=True)
        elif feas:
            print(f"[harvest] {tag}: official {omk:.3f}d (not < best {best:.3f}) [{time.time()-t0:.0f}s]", flush=True)
    time.sleep(45)
