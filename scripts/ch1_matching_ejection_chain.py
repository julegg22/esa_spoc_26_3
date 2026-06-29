"""E-756 #1 — cardinality-augmenting ejection-tree search for matching-i (the missed attack).

Audit (E-756): bank 33,490.458 is a MAXIMAL matching (0 free insertions), 4479/5000 matched. The 521
unmatched E-nodes have 81% DOUBLE-conflict candidates (both l and d occupied) — so augmenting one
requires displacing TWO selected triples and RE-PLACING both freed E-nodes (a branching ejection
tree, not a simple path). All 4 prior families used fixed-cardinality weight-swaps / loose-LP B&B and
NEVER did this. THIS builds it: stateful depth-limited DFS with backtracking. To match free E-node e
via candidate c=(e,l,d): eject the triples owning l and d, then recursively re-place each freed
E-node via one of ITS other candidates (threading a `forbidden` node set + live tentative ownership
so the tree never reuses a node). A branch CLOSES when a freed E-node finds a free insertion. Net
Δweight = Σ(added) − Σ(removed); a closing tree raises cardinality and is typically net-positive.

BINARY (audit): any net-positive augmenting tree found -> swap-neighborhood too weak, LEVER OPEN.
Full sweep over all 521 unmatched E with branching depth finds none -> augmentation-optimal, wall real.

NOT a submission. Guard-banks matching-i.json (+.bak) only if STRICTLY better & re-verified feasible.
Usage: python ch1_matching_ejection_chain.py [seconds=180] [maxdepth=4] [nodebudget=200000] [seed=0]"""
import sys, json, time, shutil
import numpy as np
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt"
BANKF = f"{ROOT}/solutions/upload/matching-i.json"


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 180.0
    maxdepth = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    nodebudget = int(sys.argv[3]) if len(sys.argv) > 3 else 200000
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    E, L, D, W = [], [], [], []
    for ln in open(INST):
        e, l, d, w = ln.split()
        E.append(int(e)); L.append(int(l)); D.append(int(d)); W.append(float(w))
    E = np.array(E); L = np.array(L); D = np.array(D); W = np.array(W); n = len(W)
    bv = np.array(json.load(open(BANKF))[0]["decisionVector"], dtype=np.int8)
    sel = bv == 1
    candE = defaultdict(list)
    for i in range(n):
        candE[E[i]].append(i)
    selset = set(np.where(sel)[0].tolist())
    ownL, ownD = {}, {}
    for i in selset:
        ownL[L[i]] = i; ownD[D[i]] = i
    allE = set(E.tolist())
    base = W[sel].sum()
    print(f"[E-756#1] bank {base:.3f}, {len(selset)} matched, {len(allE - set(E[i] for i in selset))} "
          f"unmatched E, maxdepth={maxdepth}, budget={nodebudget}, {secs:.0f}s seed{seed}", flush=True)

    visits = [0]

    def _del(T, log):
        selset.discard(T); ownL.pop(L[T], None); ownD.pop(D[T], None); log.append(("a", T))

    def _add(c, log):
        selset.add(c); ownL[L[c]] = c; ownD[D[c]] = c; log.append(("d", c))

    def _rollback(log, mark):
        for act, idx in reversed(log[mark:]):
            if act == "a":
                selset.add(idx); ownL[L[idx]] = idx; ownD[D[idx]] = idx
            else:
                selset.discard(idx); ownL.pop(L[idx], None); ownD.pop(D[idx], None)
        del log[mark:]

    def place(e, depth, forbiddenL, forbiddenD, log, best_choice):
        """Match currently-free E-node e. Returns the chain's delta on success, leaving state mutated
        with the chosen chain applied; None on failure (state restored). If best_choice, picks the
        candidate maximizing delta (evaluate-all, keep best); else first closing chain."""
        visits[0] += 1
        if visits[0] > nodebudget:
            return None
        order = candE[e]
        best = None  # (delta, redo_ops)
        for c in order:
            l, d = L[c], D[c]
            if l in forbiddenL or d in forbiddenD:
                continue
            Ts = set(T for T in (ownL.get(l), ownD.get(d)) if T is not None)
            if Ts and depth <= 0:
                continue
            mark = len(log)
            delta = W[c]
            for T in Ts:
                delta -= W[T]; _del(T, log)
            _add(c, log)
            fL = forbiddenL | {l}; fD = forbiddenD | {d}
            ok = True
            for T in Ts:
                sub = place(E[T], depth - 1, fL, fD, log, best_choice)
                if sub is None:
                    ok = False; break
                delta += sub
            if ok and not best_choice:
                return delta                              # first closing chain, leave applied
            if ok and (best is None or delta > best[0]):
                best = (delta, [(a, i) for a, i in log[mark:]])
            _rollback(log, mark)                          # undo to try the next candidate
        if best is None:
            return None
        # re-apply best chain explicitly (log entries are ('a',T)=was-deleted, ('d',c)=was-added)
        for act, idx in best[1]:
            if act == "a":
                selset.discard(idx); ownL.pop(L[idx], None); ownD.pop(D[idx], None); log.append(("a", idx))
            else:
                selset.add(idx); ownL[L[idx]] = idx; ownD[D[idx]] = idx; log.append(("d", idx))
        return best[0]

    t0 = time.time(); total = base; improved = 0; first = None; passes = 0
    while time.time() - t0 < secs:
        passes += 1
        unE = list(allE - set(E[i] for i in selset))
        np.random.RandomState(seed + passes).shuffle(unE)
        found = False
        rsh = np.random.RandomState(seed + passes * 7919)
        for k in list(candE):                              # shuffle candidate order per pass (escape fixed-order)
            rsh.shuffle(candE[k])
        for e in unE:
            if time.time() - t0 >= secs:
                break
            visits[0] = 0
            log = []
            d0 = place(e, maxdepth, set(), set(), log, True)
            if d0 is not None and d0 > 1e-9:
                total += d0; improved += 1; found = True       # accept (state already mutated)
                if first is None:
                    first = (total, time.time() - t0, len(log))
                    print(f"[E-756#1] FIRST AUGMENTING TREE: {base:.3f} -> {total:.3f} "
                          f"(+{total-base:.3f}, {len(log)} ops) [{time.time()-t0:.0f}s] -> LEVER OPEN", flush=True)
                if improved % 25 == 0:
                    print(f"[E-756#1] +{improved} trees, total {total:.3f} (+{total-base:.3f}) [{time.time()-t0:.0f}s]", flush=True)
            elif d0 is not None:                                # closed but net<=0: undo (no improvement)
                _rollback(log, 0)
            # d0 None -> already restored
        if not found:
            print(f"[E-756#1] pass {passes}: no net-positive augmenting tree over {len(unE)} unmatched E "
                  f"[{time.time()-t0:.0f}s]", flush=True)
            break

    # PHASE 2 — same-cardinality cyclic exchange (k>=3 cycles single-swaps miss). Seed from a MATCHED
    # E-node: remove its triple (free l_old,d_old), re-place e at a DIFFERENT candidate, let the chain
    # close into the freed slot. Net delta = (chain) - W[old]; cardinality unchanged on closure.
    cyc_improved = 0
    while time.time() - t0 < secs:
        matched_triples = list(selset)
        np.random.RandomState(seed + 104729 + cyc_improved).shuffle(matched_triples)
        found = False
        for Told in matched_triples:
            if time.time() - t0 >= secs:
                break
            if Told not in selset:
                continue
            e = E[Told]; wold = W[Told]
            log = [("a", Told)]; selset.discard(Told); ownL.pop(L[Told], None); ownD.pop(D[Told], None)
            visits[0] = 0
            d0 = place(e, maxdepth, set(), set(), log, True)
            if d0 is not None and (d0 - wold) > 1e-6:
                total += (d0 - wold); cyc_improved += 1; found = True
                if first is None:
                    first = (total, time.time() - t0, len(log))
                    print(f"[E-756#1] FIRST CYCLE EXCHANGE: {base:.3f} -> {total:.3f} "
                          f"(+{total-base:.3f}) [{time.time()-t0:.0f}s] -> LEVER OPEN", flush=True)
                if cyc_improved % 25 == 0:
                    print(f"[E-756#1] +{cyc_improved} cycles, total {total:.3f} (+{total-base:.3f}) [{time.time()-t0:.0f}s]", flush=True)
            else:
                _rollback(log, 0)                          # restore (re-add Told + undo any chain)
        if not found:
            print(f"[E-756#1] cyclic-exchange pass: no improving k-cycle over {len(matched_triples)} "
                  f"matched triples [{time.time()-t0:.0f}s]", flush=True)
            break

    print(f"[E-756#1] DONE: {improved} augmenting + {cyc_improved} cyclic, total {total:.3f} "
          f"(bank {base:.3f}, +{total-base:.3f}) [{time.time()-t0:.0f}s]", flush=True)
    if first is None:
        print(f"[E-756#1] VERDICT: NO net-positive augmenting tree (depth<={maxdepth}) -> bank is "
              f"augmentation-optimal for this neighborhood; wall holds. Escalate exp#2 (alt exact-2-DM).", flush=True)
    else:
        bi = np.array(sorted(selset))
        ndE, ndL, ndD = len(set(E[bi])), len(set(L[bi])), len(set(D[bi]))
        feasible = ndE == len(bi) == ndL == ndD
        wsum = W[bi].sum()
        print(f"[E-756#1] VERIFY: {len(bi)} triples, w={wsum:.3f}, distinct E={ndE} L={ndL} D={ndD} "
              f"feasible={feasible}", flush=True)
        if feasible and wsum > base + 1e-3:
            newbv = np.zeros(n, dtype=int); newbv[bi] = 1
            shutil.copy(BANKF, f"{BANKF}.bak_ejection")
            json.dump([{"decisionVector": [int(x) for x in newbv], "problem": "matching-i",
                        "challenge": "spoc-4-luna-tomato-logistics"}], open(BANKF, "w"))
            print(f"[E-756#1] *** GUARD-BANKED matching-i -> {wsum:.3f} (was {base:.3f}) -> ESCALATE re-submit", flush=True)


if __name__ == "__main__":
    main()
