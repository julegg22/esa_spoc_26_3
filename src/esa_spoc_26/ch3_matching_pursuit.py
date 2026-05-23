"""Ch3 Celestial Morse Code — matching pursuit (sparse signal recovery).

The UDP signal-matching problem:
- 779 orbits (188 DRO + 291 Lyap + 300 Axial)
- Up to 5 spacecraft per orbit, each with a phase ∈ [0, 2π)
- Each spacecraft creates a box-windowed occultation signal
  (DRO: 1 box per period; Lyap/Axial: 2 boxes per period, π apart)
- Target: reconstruct a Morse-code waveform within MSE ≤ 0.05
- Minimise spacecraft count

Matching pursuit (Mallat & Zhang 1993):
1. Discretise phase: P phases per orbit
2. Build candidate column A[:, k] for each (orbit, phase) — a box-
   windowed binary signal
3. Greedy: at each step, find the column maximally correlated with
   the current residual; add to selection; update residual
4. Stop when MSE ≤ 0.05 OR max iterations

Each "candidate column" represents 1 spacecraft on a specific orbit
at a specific phase. We can add multiple spacecraft per orbit (up
to 5) by selecting the same orbit at different phases (or the same).

For the LP-feasibility region, the fitness `clip(A @ ones, 0, 1)`
means saturated signal — adding multiple spacecraft to the same
(orbit, phase) doesn't help (already at amplitude 1). But adding
across phases / orbits can fill different time slots.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np


def find_lta_path():
    """Find the lta_udp module path."""
    p = Path("reference/SpOC4/Challenge 3 Luna Tomato Advertising")
    if p.exists():
        return p
    return None


def load_udp():
    """Load the celestial_morse_code UDP."""
    path = find_lta_path()
    sys.path.insert(0, str(path))
    import lta_udp
    udp = lta_udp.celestial_morse_code()
    return udp


def build_candidate_matrix(udp, n_phases_dro=40, n_phases_other=40):
    """For each orbit family × discretised phase, build the
    occultation column vector.

    Returns:
        A_cand: shape (T, K) — K candidate columns
        meta: list of (orbit_idx, phase, occult_idx) per column
              orbit_idx is global (0..num_orbits-1)
              occult_idx: 0 = primary, 1 = secondary (for Lyap/Axial)
    """
    T = len(udp.t)
    cols = []
    meta = []
    # DRO: 1 occultation per spacecraft
    for orbit_idx in range(udp.num_dro):
        for phase in np.linspace(0, 2 * np.pi, n_phases_dro, endpoint=False):
            ph = float(phase)
            col = udp.amplitudes_dro[orbit_idx] * udp._repeating_box_window(
                udp.t,
                (2 * np.pi - ph) / (2 * np.pi) / udp.frequencies_dro[orbit_idx],
                frequency=udp.frequencies_dro[orbit_idx],
            )
            cols.append(col)
            meta.append(("dro", orbit_idx, ph, 0))
    # Lyap: 2 occultations per spacecraft (combined as one selection)
    for orbit_idx in range(udp.num_lyap):
        for phase in np.linspace(0, 2 * np.pi, n_phases_other,
                                   endpoint=False):
            ph = float(phase)
            col1 = udp.amplitudes_lyap[orbit_idx] * udp._repeating_box_window(
                udp.t,
                (2 * np.pi - ph) / (2 * np.pi) / udp.frequencies_lyap[orbit_idx],
                frequency=udp.frequencies_lyap[orbit_idx],
            )
            col2 = udp.amplitudes_lyap[udp.num_lyap + orbit_idx] \
                * udp._repeating_box_window(
                    udp.t,
                    (ph + np.pi) / udp.frequencies_lyap[udp.num_lyap + orbit_idx],
                    frequency=udp.frequencies_lyap[udp.num_lyap + orbit_idx],
                )
            # ONE spacecraft creates both — combine: take pointwise max
            col = np.clip(col1 + col2, 0, 1)
            cols.append(col)
            meta.append(("lyap", orbit_idx, ph, -1))  # combined
    # Axial: 2 occultations per spacecraft
    for orbit_idx in range(udp.num_axial):
        for phase in np.linspace(0, 2 * np.pi, n_phases_other,
                                   endpoint=False):
            ph = float(phase)
            col1 = udp.amplitudes_axial[orbit_idx] * udp._repeating_box_window(
                udp.t,
                (2 * np.pi - ph) / (2 * np.pi) / udp.frequencies_axial[orbit_idx],
                frequency=udp.frequencies_axial[orbit_idx],
            )
            col2 = udp.amplitudes_axial[udp.num_axial + orbit_idx] \
                * udp._repeating_box_window(
                    udp.t,
                    (ph + np.pi) / udp.frequencies_axial[udp.num_axial + orbit_idx],
                    frequency=udp.frequencies_axial[udp.num_axial + orbit_idx],
                )
            col = np.clip(col1 + col2, 0, 1)
            cols.append(col)
            meta.append(("axial", orbit_idx, ph, -1))
    A = np.array(cols).T  # (T, K)
    return A, meta


def local_search_swap(target, A_cand, meta, selected_idx, mse_thresh=0.05,
                        max_swaps=200, verbose=True):
    """After greedy stops, try swap moves: remove one selected, add a
    different candidate. Greedy improvement."""
    selected = list(selected_idx)
    # Compute current signal
    current = np.zeros_like(target)
    for k in selected:
        current = np.where(A_cand[:, k] > 0.5, 1.0, current)
    cur_mse = float(np.mean((current - target) ** 2))
    swaps = 0
    while swaps < max_swaps:
        # Try removing each selected
        improved = False
        for rm_idx, rm_k in enumerate(selected):
            # Compute current without rm_k
            remaining = [k for k in selected if k != rm_k]
            sig_without = np.zeros_like(target)
            for k in remaining:
                sig_without = np.where(A_cand[:, k] > 0.5, 1.0, sig_without)
            # Try ADDING the best candidate
            target_to_1_sq = (1.0 - target) ** 2
            current_to_target_sq = (sig_without - target) ** 2
            gain = current_to_target_sq - target_to_1_sq
            scores = A_cand.T @ gain
            # Don't re-add same
            scores[rm_k] = -np.inf
            best_add = int(np.argmax(scores))
            new = np.where(A_cand[:, best_add] > 0.5, 1.0, sig_without)
            new_mse = float(np.mean((new - target) ** 2))
            if new_mse < cur_mse - 1e-9:
                selected[rm_idx] = best_add
                current = new
                cur_mse = new_mse
                swaps += 1
                if verbose:
                    print(f"  swap {swaps}: rm idx {rm_idx} (cand {rm_k}) "
                          f"→ add {best_add}, mse={cur_mse:.5f}",
                          flush=True)
                improved = True
                break
        if not improved:
            if verbose:
                print(f"  no improving swap found, stopping",
                      flush=True)
            break
        if cur_mse <= mse_thresh:
            if verbose:
                print(f"  ✓ MSE ≤ {mse_thresh} after swap", flush=True)
            break
    return selected, current, cur_mse


def matching_pursuit(target, A_cand, meta, mse_thresh=0.05, max_iter=300,
                      verbose=True):
    """Greedy matching pursuit accounting for clipping saturation.

    For binary box-window candidates (col[i] ∈ {0, 1}):
    - At positions where col[i] = 1: new[i] = clip(current[i] + 1) = 1
    - At positions where col[i] = 0: new[i] = current[i]

    Per-position delta_mse at i where col[i] = 1:
    - delta_mse_i = (1 - target[i])² - (current[i] - target[i])²

    Total delta_mse = sum over col[i]==1 of (1 - target[i])² - (current[i] - target[i])²
                    = col · ((1 - target)² - (current - target)²)

    We MINIMIZE delta_mse. Negative = improvement.
    """
    T = target.shape[0]
    current = np.zeros_like(target)
    selected_idx = []
    history = []
    cur_mse = float(np.mean((current - target) ** 2))
    history.append(cur_mse)
    for it in range(max_iter):
        # Compute per-position delta if we set col_i = 1
        target_to_1_sq = (1.0 - target) ** 2  # at col_i=1 → new contribution
        current_to_target_sq = (current - target) ** 2  # old contribution
        gain_per_pos = current_to_target_sq - target_to_1_sq
        # Per candidate score: positive = improvement
        scores = A_cand.T @ gain_per_pos  # (K,)
        best_k = int(np.argmax(scores))
        if scores[best_k] <= 1e-9:
            if verbose:
                print(f"  iter {it}: no improving candidate; stopping",
                      flush=True)
            break
        col = A_cand[:, best_k]
        new = np.where(col > 0.5, 1.0, current)
        new_mse = float(np.mean((new - target) ** 2))
        current = new
        selected_idx.append(best_k)
        cur_mse = new_mse
        history.append(cur_mse)
        if verbose and (it < 30 or it % 20 == 0):
            print(f"  iter {it}: {meta[best_k][:2]} ph={meta[best_k][2]:.2f}, "
                  f"score={scores[best_k]:.4f}, mse={cur_mse:.5f}, "
                  f"n_sel={len(selected_idx)}", flush=True)
        if cur_mse <= mse_thresh:
            if verbose:
                print(f"  ✓ MSE ≤ {mse_thresh} at iter {it}, "
                      f"n_selected={len(selected_idx)}", flush=True)
            break
    return selected_idx, current, cur_mse, history


def prune_redundant(udp, A_cand, meta, selected_idx, mse_thresh,
                     verbose=True):
    """Remove spacecraft whose removal doesn't break feasibility.
    After feasibility achieved, greedily prune redundant entries.

    Score by frequency: sort by least-recently-added; try to remove
    each.
    """
    # Build chromosome from selected_meta_list, then check which can
    # be removed without breaking MSE ≤ thresh.
    selected_meta = [meta[k] for k in selected_idx]
    chrom = build_chromosome(udp, selected_meta)
    f_init = udp.fitness(chrom, postprocess=True)
    init_mse = float(f_init[2])
    init_count = int(f_init[1])
    if verbose:
        print(f"  Pre-prune: count={init_count}, mse={init_mse:.5f}",
              flush=True)
    # Convert to (orbit_id, slot) form for fine-grained removal
    # Strategy: try removing each candidate idx one at a time
    kept = list(range(len(selected_idx)))
    n_removed = 0
    progress = True
    while progress:
        progress = False
        for i in range(len(kept) - 1, -1, -1):
            trial = [selected_idx[j] for j in kept if j != kept[i]]
            trial_meta = [meta[k] for k in trial]
            trial_chrom = build_chromosome(udp, trial_meta)
            f_trial = udp.fitness(trial_chrom, postprocess=True)
            trial_mse = float(f_trial[2])
            if trial_mse <= mse_thresh:
                kept.pop(i)
                n_removed += 1
                progress = True
                if verbose and n_removed % 5 == 0:
                    print(f"  prune step: removed {n_removed}, "
                          f"remaining={len(kept)}, mse={trial_mse:.5f}",
                          flush=True)
    final_sel = [selected_idx[j] for j in kept]
    final_meta = [meta[k] for k in final_sel]
    final_chrom = build_chromosome(udp, final_meta)
    f_final = udp.fitness(final_chrom, postprocess=True)
    if verbose:
        print(f"  Post-prune: count={int(f_final[1])}, "
              f"mse={float(f_final[2]):.5f}, removed={n_removed}",
              flush=True)
    return final_sel, final_chrom, f_final


def build_chromosome(udp, selected_meta_list):
    """Construct a UDP-format chromosome.

    selected_meta_list: list of (family, orbit_idx, phase, occult)
    """
    # selections: count of spacecraft per orbit (DRO + Lyap + Axial)
    selections = [0] * udp.num_orbits
    # phases: for each orbit_idx in global space (DRO indices 0..187,
    # Lyap indices 188..478, Axial 479..778), phases[orbit_idx*5 + j]
    # for j-th spacecraft on that orbit
    phases = [0.0] * (udp.num_orbits * udp.max_per_orbit)
    # Track per-orbit spacecraft slot index
    slot = [0] * udp.num_orbits
    for fam, o_local, ph, _ in selected_meta_list:
        if fam == "dro":
            o_global = o_local
        elif fam == "lyap":
            o_global = udp.num_dro + o_local
        else:  # axial
            o_global = udp.num_dro + udp.num_lyap + o_local
        if slot[o_global] >= udp.max_per_orbit:
            # Skip; can't fit more on this orbit
            continue
        selections[o_global] += 1
        phases[o_global * udp.max_per_orbit + slot[o_global]] = ph
        slot[o_global] += 1
    return selections + phases


def main(problem="signal", out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         max_iter=300, n_phases_dro=40, n_phases_other=40):
    print("Loading UDP...", flush=True)
    udp = load_udp()
    print(f"UDP: n_orbits={udp.num_orbits} (DRO={udp.num_dro}, "
          f"Lyap={udp.num_lyap}, Axial={udp.num_axial})", flush=True)
    print(f"target len={len(udp.t)}, mse_thresh={udp.mse_thresh}",
          flush=True)

    print(f"\nBuilding candidate matrix "
          f"(n_phases_dro={n_phases_dro}, n_phases_other={n_phases_other})...",
          flush=True)
    t0 = time.time()
    A_cand, meta = build_candidate_matrix(udp, n_phases_dro, n_phases_other)
    print(f"  A_cand shape: {A_cand.shape}, "
          f"wall={time.time()-t0:.1f}s", flush=True)

    print(f"\nMatching pursuit (max_iter={max_iter})...", flush=True)
    t0 = time.time()
    selected_idx, reconstructed, final_mse, history = matching_pursuit(
        udp.target_signal, A_cand, meta,
        mse_thresh=udp.mse_thresh, max_iter=max_iter)
    print(f"  Wall: {time.time()-t0:.1f}s, n_selected={len(selected_idx)}, "
          f"final_mse={final_mse:.5f}", flush=True)
    feasible = final_mse <= udp.mse_thresh
    print(f"  Feasible (MSE ≤ {udp.mse_thresh})? {feasible}", flush=True)

    if not feasible:
        # Iterate: expand → swap → expand → swap until stable
        for round_idx in range(6):
            print(f"\n--- Round {round_idx + 1} ---", flush=True)
            # Try ADDING more
            current = reconstructed.copy()
            selected_idx_ext = list(selected_idx)
            n_added = 0
            for it in range(max_iter):
                target_to_1_sq = (1.0 - udp.target_signal) ** 2
                current_to_target_sq = (current - udp.target_signal) ** 2
                gain = current_to_target_sq - target_to_1_sq
                scores = A_cand.T @ gain
                best_k = int(np.argmax(scores))
                if scores[best_k] < -1.0:
                    break
                col = A_cand[:, best_k]
                new = np.where(col > 0.5, 1.0, current)
                new_mse = float(np.mean((new - udp.target_signal) ** 2))
                current = new
                selected_idx_ext.append(best_k)
                n_added += 1
                if new_mse <= udp.mse_thresh:
                    feasible = True
                    print(f"  ✓ feasible after add (n={len(selected_idx_ext)})!",
                          flush=True)
                    break
            selected_idx = selected_idx_ext
            reconstructed = current
            final_mse = float(np.mean((current - udp.target_signal) ** 2))
            print(f"  After add: added={n_added}, n={len(selected_idx)}, "
                  f"mse={final_mse:.5f}", flush=True)
            if feasible:
                break
            # Local search swap
            selected_idx, reconstructed, final_mse = local_search_swap(
                udp.target_signal, A_cand, meta, selected_idx,
                mse_thresh=udp.mse_thresh, max_swaps=500, verbose=False)
            feasible = final_mse <= udp.mse_thresh
            print(f"  After swap: n={len(selected_idx)}, mse={final_mse:.5f}, "
                  f"feasible={feasible}", flush=True)
            if feasible:
                break

    # PRUNE REDUNDANT (only if feasible)
    if feasible:
        print(f"\nPruning redundant spacecraft...", flush=True)
        selected_idx, chromosome, f = prune_redundant(
            udp, A_cand, meta, selected_idx, udp.mse_thresh)
    else:
        selected_meta = [meta[k] for k in selected_idx]
        chromosome = build_chromosome(udp, selected_meta)
        f = udp.fitness(chromosome, postprocess=True)
    print(f"\nUDP fitness: {f}", flush=True)
    obj, num_selected, mse_check = f[0][0], f[1], f[2]
    print(f"  obj={obj}, num_selected={num_selected}, mse={mse_check:.5f}",
          flush=True)

    info = {
        "n_orbits": udp.num_orbits,
        "selected_n": int(num_selected),
        "mse": float(mse_check),
        "feasible": bool(mse_check <= udp.mse_thresh),
        "obj": float(obj),
    }
    if info["feasible"]:
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{
            "decisionVector": [float(v) for v in chromosome],
            "problem": problem,
            "challenge": 3,
        }]))
        info["banked"] = str(p)
        print(f"\nBANKED to {p}", flush=True)
    return info


if __name__ == "__main__":
    mi = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    npd = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    npo = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    print(json.dumps(main(max_iter=mi, n_phases_dro=npd,
                          n_phases_other=npo), indent=2))
