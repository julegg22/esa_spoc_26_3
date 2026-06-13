"""E-609: feasibility-aware global order search for Ch2 small.

Inner timing oracle = scripts/ch2_dp_fast.makespan_fast (validated vs trusted
ch2_dp_numba). We search ONLY node orders; the DP handles timing + exc
allocation optimally. Goal: beat the bank makespan 116.3755.

Strategy (mix of SA + ruin-and-recreate, all feasibility-preserving):
  - moves: segment reversal, segment relocation, node relocation, component
    block reordering, and ruin-and-recreate (remove k nodes, regret-reinsert).
  - pre-screen every candidate with the "ever-feasible" (cheap-or-exc) directed
    mask so we never DP-time an order with a hopeless leg; track the feasible
    construction rate.
  - accept on DP makespan with SA temperature; periodic restarts from
    diversified starts.
Any order beating bank is dumped to /tmp for trusted re-verification.
"""
from __future__ import annotations
import json, sys, time, random, warnings
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, 'scripts')
from ch2_dp_fast import makespan_fast
from esa_spoc_26.ch2_kttsp import KTTSP

BASE = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/easy.kttsp")
kt = KTTSP(BASE)
d = np.load('/tmp/ch2_small_tcoupled_ultrafine.npz')
cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
N = 49
N_EXC = kt.n_exc

# directed feasibility masks
cheap_fin = np.isfinite(cheap_tab).any(axis=2)      # cheap edge ever exists
ever_fin = cheap_fin | np.isfinite(exc_tab).any(axis=2)  # cheap-or-exc
np.fill_diagonal(cheap_fin, False)
np.fill_diagonal(ever_fin, False)

bank = json.load(open('solutions/upload/small.json'))
PERM0 = [int(round(x)) for x in bank[0]['decisionVector'][-49:]]
BANK_MK = 116.3755

# cheap components
undir = cheap_fin | cheap_fin.T
_seen = [-1] * N
COMPS = []
for s in range(N):
    if _seen[s] >= 0:
        continue
    cid = len(COMPS); stack = [s]; mem = []
    while stack:
        u = stack.pop()
        if _seen[u] >= 0:
            continue
        _seen[u] = cid; mem.append(u)
        for v in range(N):
            if undir[u, v] and _seen[v] < 0:
                stack.append(v)
    COMPS.append(sorted(mem))
COMP_OF = np.array(_seen)


def n_exc_lower_bound(perm):
    """Count legs with no cheap edge -> must use exc. If > N_EXC, infeasible."""
    c = 0
    for k in range(N - 1):
        if not cheap_fin[perm[k], perm[k + 1]]:
            c += 1
            if c > N_EXC:
                return c
    return c


def prescreen(perm):
    """Cheap reject before DP: no hopeless leg, and exc lower bound <= budget."""
    for k in range(N - 1):
        if not ever_fin[perm[k], perm[k + 1]]:
            return False
    if n_exc_lower_bound(perm) > N_EXC:
        return False
    return True


# stats
STATS = {'constructed': 0, 'prescreen_pass': 0, 'dp_feasible': 0}


def dp_mk(perm):
    STATS['constructed'] += 1
    if not prescreen(perm):
        return None
    STATS['prescreen_pass'] += 1
    mk = makespan_fast(perm, cheap_tab, exc_tab, q, T, N_EXC)
    if mk is not None:
        STATS['dp_feasible'] += 1
    return mk


# ---------- move operators ----------
def mv_reverse(p, rng):
    i, j = sorted(rng.sample(range(N), 2))
    return p[:i] + p[i:j + 1][::-1] + p[j + 1:]


def mv_relocate_node(p, rng):
    i = rng.randrange(N)
    node = p[i]
    rest = p[:i] + p[i + 1:]
    j = rng.randrange(N)
    return rest[:j] + [node] + rest[j:]


def mv_relocate_seg(p, rng):
    L = rng.randint(2, 6)
    i = rng.randrange(0, N - L)
    seg = p[i:i + L]
    rest = p[:i] + p[i + L:]
    j = rng.randrange(len(rest) + 1)
    if rng.random() < 0.4:
        seg = seg[::-1]
    return rest[:j] + seg + rest[j:]


def mv_swap(p, rng):
    i, j = rng.sample(range(N), 2)
    p = p[:]
    p[i], p[j] = p[j], p[i]
    return p


def ruin_recreate(p, rng, k=None):
    """Remove k nodes, regret-reinsert biased toward cheap edges."""
    if k is None:
        k = rng.randint(4, 12)
    idx = sorted(rng.sample(range(N), k), reverse=True)
    removed = [p[i] for i in idx]
    base = p[:]
    for i in idx:
        base.pop(i)
    rng.shuffle(removed)
    for node in removed:
        best_pos = None; best_score = None
        for pos in range(len(base) + 1):
            left = base[pos - 1] if pos > 0 else None
            right = base[pos] if pos < len(base) else None
            # score: prefer positions where both adjacencies are cheap, then
            # cheap-or-exc; reject if any adjacency is hopeless.
            ok = True; score = 0
            if left is not None:
                if not ever_fin[left, node]:
                    ok = False
                elif cheap_fin[left, node]:
                    score += 0
                else:
                    score += 1
            if right is not None:
                if not ever_fin[node, right]:
                    ok = False
                elif cheap_fin[node, right]:
                    score += 0
                else:
                    score += 1
            if not ok:
                continue
            score += rng.random() * 0.3
            if best_score is None or score < best_score:
                best_score = score; best_pos = pos
        if best_pos is None:
            best_pos = rng.randrange(len(base) + 1)
        base.insert(best_pos, node)
    return base


def mv_relocate_node_feas(p, rng):
    """Relocate one node to an insertion point that keeps both new adjacencies
    ever-feasible (preserves the connectivity precondition)."""
    i = rng.randrange(N)
    node = p[i]
    rest = p[:i] + p[i + 1:]
    m = len(rest)
    # candidate positions j (0..m) where left=rest[j-1], right=rest[j] both ok
    cands = []
    for j in range(m + 1):
        left = rest[j - 1] if j > 0 else None
        right = rest[j] if j < m else None
        if left is not None and not ever_fin[left, node]:
            continue
        if right is not None and not ever_fin[node, right]:
            continue
        cands.append(j)
    if not cands:
        return p
    j = rng.choice(cands)
    return rest[:j] + [node] + rest[j:]


def mv_reverse_feas(p, rng):
    """Reverse a segment only if the two new boundary adjacencies stay
    ever-feasible; sample a few times."""
    for _ in range(8):
        i, j = sorted(rng.sample(range(N), 2))
        if j - i < 1:
            continue
        a = p[i - 1] if i > 0 else None      # before segment
        b = p[j + 1] if j + 1 < N else None  # after segment
        # after reversal: a -> p[j] ... p[i] -> b
        if a is not None and not ever_fin[a, p[j]]:
            continue
        if b is not None and not ever_fin[p[i], b]:
            continue
        return p[:i] + p[i:j + 1][::-1] + p[j + 1:]
    return p


def mv_relocate_seg_feas(p, rng):
    """Relocate a contiguous segment to a feasibility-ok insertion point."""
    L = rng.randint(2, 5)
    if N - L <= 0:
        return p
    i = rng.randrange(0, N - L)
    seg = p[i:i + L]
    rest = p[:i] + p[i + L:]
    m = len(rest)
    rev = rng.random() < 0.4
    s = seg[::-1] if rev else seg
    cands = []
    for j in range(m + 1):
        left = rest[j - 1] if j > 0 else None
        right = rest[j] if j < m else None
        if left is not None and not ever_fin[left, s[0]]:
            continue
        if right is not None and not ever_fin[s[-1], right]:
            continue
        cands.append(j)
    if not cands:
        return p
    j = rng.choice(cands)
    return rest[:j] + s + rest[j:]


MOVES = [mv_reverse_feas, mv_relocate_node_feas, mv_relocate_seg_feas,
         mv_relocate_node, mv_relocate_seg, mv_reverse, mv_swap]
MOVE_W = [0.30, 0.30, 0.20, 0.05, 0.05, 0.05, 0.05]


def gen_move(p, rng):
    r = rng.random()
    if r < 0.20:
        return ruin_recreate(p, rng)
    return rng.choices(MOVES, weights=MOVE_W)[0](p, rng)


# ---------- diversified starts ----------
# precompute adjacency lists for fast constructor
CHEAP_SUCC = [np.where(cheap_fin[v])[0].tolist() for v in range(N)]
EVER_SUCC = [np.where(ever_fin[v])[0].tolist() for v in range(N)]


def cheap_guided_start(rng, max_restart=200):
    """Randomized greedy Hamiltonian path on the ever-feasible directed graph,
    strongly preferring cheap edges (keeps exc count low), with restart on
    dead-ends. Returns a perm with all legs ever-feasible and exc_LB <= budget,
    or None if it could not build one within max_restart attempts."""
    for _ in range(max_restart):
        start = rng.randrange(N)
        used = np.zeros(N, dtype=bool)
        used[start] = True
        path = [start]
        exc_count = 0
        dead = False
        while len(path) < N:
            cur = path[-1]
            cheap_c = [v for v in CHEAP_SUCC[cur] if not used[v]]
            if cheap_c:
                nxt = rng.choice(cheap_c)
            else:
                # need an exc step; only if budget remains
                if exc_count >= N_EXC:
                    dead = True
                    break
                ever_c = [v for v in EVER_SUCC[cur] if not used[v]]
                if not ever_c:
                    dead = True
                    break
                # prefer successors that themselves have an unused cheap exit
                scored = []
                for v in ever_c:
                    has_cheap_exit = any(not used[w] and w != v
                                         for w in CHEAP_SUCC[v])
                    scored.append((0 if has_cheap_exit else 1, rng.random(), v))
                scored.sort()
                nxt = scored[0][2]
                exc_count += 1
            used[nxt] = True
            path.append(nxt)
        if not dead and len(path) == N and exc_count <= N_EXC:
            return path
    return None


def run(seed, time_budget, log_every=2000):
    rng = random.Random(seed)
    t0 = time.time()
    # start from bank or diversified
    best_global = PERM0[:]
    best_global_mk = BANK_MK
    found = []
    restart = 0
    while time.time() - t0 < time_budget:
        if restart == 0:
            cur = PERM0[:]
        elif restart % 2 == 1:
            # perturbed bank
            cur = PERM0[:]
            for _ in range(rng.randint(3, 10)):
                cur = gen_move(cur, rng)
        else:
            cur = cheap_guided_start(rng)
            if cur is None:
                cur = PERM0[:]
        cur_mk = dp_mk(cur)
        # if start infeasible, repair by ruin-recreate a few times
        tries = 0
        while cur_mk is None and tries < 30:
            cur = ruin_recreate(cur, rng, k=rng.randint(6, 14))
            cur_mk = dp_mk(cur)
            tries += 1
        if cur_mk is None:
            restart += 1
            continue
        best_local = cur[:]; best_local_mk = cur_mk
        # SA inner loop
        Temp = 2.0
        cool = 0.9995
        it = 0
        stale = 0
        while time.time() - t0 < time_budget and stale < 4000:
            it += 1
            cand = gen_move(cur, rng)
            mk = dp_mk(cand)
            if mk is None:
                stale += 1
                continue
            d_mk = mk - cur_mk
            if d_mk < 0 or rng.random() < np.exp(-d_mk / max(Temp, 1e-3)):
                cur = cand; cur_mk = mk
                if mk < best_local_mk - 1e-9:
                    best_local = cand[:]; best_local_mk = mk
                    stale = 0
                else:
                    stale += 1
            else:
                stale += 1
            Temp *= cool
            if it % log_every == 0:
                fr = STATS['dp_feasible'] / max(STATS['constructed'], 1)
                print('[s%d r%d it%d] cur=%.4f best=%.4f T=%.3f feas_rate=%.1f%% '
                      'constructed=%d' % (seed, restart, it, cur_mk,
                      best_global_mk, Temp, 100 * fr, STATS['constructed']),
                      flush=True)
        if best_local_mk < best_global_mk - 1e-9:
            best_global_mk = best_local_mk; best_global = best_local[:]
            print('  *** NEW BEST mk=%.4f (bank %.4f) seed=%d' %
                  (best_global_mk, BANK_MK, seed), flush=True)
            found.append((best_global_mk, best_global[:]))
        restart += 1
    fr = STATS['dp_feasible'] / max(STATS['constructed'], 1)
    print('[seed %d DONE] best=%.4f feas_rate=%.1f%% constructed=%d '
          'prescreen_pass=%d dp_feasible=%d' % (seed, best_global_mk, 100 * fr,
          STATS['constructed'], STATS['prescreen_pass'], STATS['dp_feasible']),
          flush=True)
    return best_global_mk, best_global, found, STATS


if __name__ == '__main__':
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 1200.0
    bm, bp, found, stats = run(seed, budget)
    out = {'seed': seed, 'best_mk': bm, 'best_perm': bp, 'bank_mk': BANK_MK,
           'beat': bm < BANK_MK - 1e-9, 'stats': stats,
           'found': [{'mk': m, 'perm': p} for m, p in found]}
    json.dump(out, open('/tmp/ch2_small_e609_s%d.json' % seed, 'w'))
    print('wrote /tmp/ch2_small_e609_s%d.json' % seed)
