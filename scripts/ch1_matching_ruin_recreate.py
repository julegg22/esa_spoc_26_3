"""E-756 lever — ruin-and-recreate LNS with EXACT CP-SAT rebuild + SA acceptance for matching-i.

E-756 verdict: bank 33,490 is locally optimal under SIX neighborhoods (swap/LNS/MILP/augmentation/
k-cycle/Lagrangian) — the +65 to the leader is a DIFFERENT-BASIN gap, reachable only by global
diversification. THIS implements the large-destroy + exact-rebuild basin-crosser:
  1. state = selected triples (start from bank).
  2. DESTROY: remove K random selected triples, freeing their E/L/D nodes.
  3. RECREATE: gather every candidate triple whose e,l,d are ALL currently free, solve that sub max-
     weight-3-DM EXACTLY with CP-SAT (each node <=1), re-insert the optimal set. Exact rebuild over a
     large freed region is what escapes the basin (joint, not one-at-a-time).
  4. ACCEPT via SA (worsening accepted with prob exp(-Δ/T)); keep global best.
Because recreate is EXACT on the sub-instance, a no-improve iteration provably re-finds an optimum of
that region; improvement requires the destroy to have spanned across basins — hence large/varied K.

Guard-banks matching-i.json (+.bak) only if STRICTLY > bank and re-verified feasible. NOT a submission.
Usage: python ch1_matching_ruin_recreate.py [seconds=1800] [Kmin=150] [Kmax=600] [seed=0]"""
import sys, json, time, shutil, math
import numpy as np
from ortools.sat.python import cp_model
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt"
BANKF = f"{ROOT}/solutions/upload/matching-i.json"


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 1800.0
    Kmin = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    Kmax = int(sys.argv[3]) if len(sys.argv) > 3 else 600
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    E, L, D, W = [], [], [], []
    for ln in open(INST):
        e, l, d, w = ln.split()
        E.append(int(e)); L.append(int(l)); D.append(int(d)); W.append(float(w))
    E = np.array(E); L = np.array(L); D = np.array(D); W = np.array(W); n = len(W)
    from collections import defaultdict
    byL = defaultdict(list); byD = defaultdict(list); byE = defaultdict(list)
    for i in range(n):
        byE[E[i]].append(i); byL[L[i]].append(i); byD[D[i]].append(i)
    bv = np.array(json.load(open(BANKF))[0]["decisionVector"], dtype=np.int8)
    cur = set(np.where(bv == 1)[0].tolist())
    base = W[list(cur)].sum()
    print(f"[E-756rr] bank {base:.3f}, {len(cur)} matched. ruin-recreate K∈[{Kmin},{Kmax}] {secs:.0f}s seed{seed}", flush=True)

    rng = np.random.RandomState(seed)
    best = set(cur); best_w = base; cur_w = base
    T = 3.0; t0 = time.time(); it = 0; acc = 0

    def recreate(free_triples, time_limit, noise=0.0):
        """max-weight 3-DM over candidate triples whose e,l,d are all free. With noise>0 the objective
        is PERTURBED (true weight + per-triple uniform noise) so the optimal rebuild genuinely DIFFERS
        from the current selection — the basin-crossing move (the un-noised rebuild just re-finds the
        bank, which is cluster-optimal). Returned weight is recomputed on TRUE W by the caller."""
        if not free_triples:
            return [], 0.0
        m = cp_model.CpModel()
        x = {i: m.NewBoolVar(f"x{i}") for i in free_triples}
        for grp, arr in ((defaultdict(list), E), (defaultdict(list), L), (defaultdict(list), D)):
            for i in free_triples:
                grp[arr[i]].append(i)
            for node, idxs in grp.items():
                if len(idxs) > 1:
                    m.AddAtMostOne(x[i] for i in idxs)
        if noise > 0:
            pert = {i: int(round((W[i] + rng.uniform(-noise, noise)) * 1000)) for i in free_triples}
            m.Maximize(sum(pert[i] * x[i] for i in free_triples))
        else:
            m.Maximize(sum(int(round(W[i] * 1000)) * x[i] for i in free_triples))
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = time_limit
        s.parameters.num_search_workers = 1
        st = s.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return [], 0.0
        pick = [i for i in free_triples if s.Value(x[i]) == 1]
        return pick, float(W[pick].sum() if pick else 0.0)

    while time.time() - t0 < secs:
        it += 1
        K = rng.randint(Kmin, Kmax + 1)
        # ownership of current selection (for related-removal BFS)
        ownL = {}; ownD = {}
        for i in cur:
            ownL[L[i]] = i; ownD[D[i]] = i
        # RELATED (Shaw) removal: grow a candidate-connected cluster from a random seed so the freed
        # region has many internal candidate triples (random scattered removal frees disconnected
        # nodes -> recreate just re-picks victims). Follow each victim-E's candidates to the selected
        # triples owning their L/D nodes.
        victims = set(); frontier = [int(rng.choice(list(cur)))]
        while frontier and len(victims) < K:
            t = frontier.pop()
            if t in victims:
                continue
            victims.add(t)
            for c in byE[E[t]]:
                for owner in (ownL.get(L[c]), ownD.get(D[c])):
                    if owner is not None and owner not in victims:
                        frontier.append(owner)
            if len(frontier) > 4 * K:
                rng.shuffle(frontier); frontier = frontier[:2 * K]
        kept = cur - victims
        usedE = set(E[i] for i in kept); usedL = set(L[i] for i in kept); usedD = set(D[i] for i in kept)
        # candidate triples for recreate: e,l,d all free w.r.t. kept (now candidate-connected cluster)
        freeset = []
        for e in set(E[i] for i in victims):
            for i in byE[e]:
                if E[i] not in usedE and L[i] not in usedL and D[i] not in usedD:
                    freeset.append(i)
        freeset = list(set(freeset))
        # perturb the rebuild (noise ~ a few % of mean weight 5) so it differs from the cluster-optimal
        # current config -> enables basin crossing; SA accepts the TRUE-weight delta below.
        pick, _ = recreate(freeset, time_limit=max(0.5, min(4.0, secs - (time.time() - t0))), noise=0.6)
        new = kept | set(pick)
        new_w = W[list(new)].sum()
        d = new_w - cur_w
        if d > -1e-9 or rng.random() < math.exp(d / max(T, 1e-3)):
            cur = new; cur_w = new_w; acc += 1
            if new_w > best_w + 1e-6:
                best = set(new); best_w = new_w
                print(f"[E-756rr] it{it}: NEW BEST {best_w:.3f} (+{best_w-base:.3f}) K={K} [{time.time()-t0:.0f}s]", flush=True)
        T *= 0.9995
        if it % 50 == 0:
            print(f"[E-756rr] it{it}: cur {cur_w:.3f} best {best_w:.3f} (+{best_w-base:.3f}) T={T:.3f} acc{acc} [{time.time()-t0:.0f}s]", flush=True)
            if T < 0.05:
                T = 2.0; cur = set(best); cur_w = best_w

    print(f"[E-756rr] DONE it{it}: best {best_w:.3f} (bank {base:.3f}, +{best_w-base:.3f}) [{time.time()-t0:.0f}s]", flush=True)
    bi = np.array(sorted(best))
    feasible = len(set(E[bi])) == len(bi) == len(set(L[bi])) == len(set(D[bi]))
    print(f"[E-756rr] VERIFY best: {len(bi)} triples w={W[bi].sum():.3f} feasible={feasible}", flush=True)
    if feasible and best_w > base + 1e-3:
        newbv = np.zeros(n, dtype=int); newbv[bi] = 1
        shutil.copy(BANKF, f"{BANKF}.bak_ruinrecreate")
        json.dump([{"decisionVector": [int(x) for x in newbv], "problem": "matching-i",
                    "challenge": "spoc-4-luna-tomato-logistics"}], open(BANKF, "w"))
        print(f"[E-756rr] *** GUARD-BANKED matching-i -> {best_w:.3f} (was {base:.3f}) -> ESCALATE re-submit", flush=True)


if __name__ == "__main__":
    main()
