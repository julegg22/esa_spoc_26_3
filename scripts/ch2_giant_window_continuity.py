"""E-710 M0c — THE decisive foundation test: are cheap windows CONTINUOUS in departure-epoch?

M0b shock: the 1d table is 100% faithful, but cheap tofs live in ~0.002d-wide bands -> our prior faithful
walks (0.01-0.05d tof steps) were BLIND to ~89% of cheap edges. So the "stranding wall" may be a tof-
SAMPLING artifact, not a real global obstruction. Decisive discriminator:
  (A) cheap windows are CONTINUOUS in epoch (cheap tof shifts smoothly with departure t) -> the 950-epoch
      grid UNDERSAMPLES a smooth window -> a FINE-tof greedy that root-finds the cheap tof at the ACTUAL
      arrival time threads far past 367 -> the wall is an artifact, rank-1 reachable.
  (B) cheap exists only at isolated (epoch,tof) points -> genuinely narrow -> chaining is hard.
Method: for N table-cheap cells, sweep departure t' around the grid epoch; at each t' do a FINE local tof
search around the smoothly-tracked cheap tof; measure the contiguous cheap-epoch WINDOW width vs grid spacing.
Usage: python ch2_giant_window_continuity.py [n=40]"""
import sys, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]
FIN = np.isfinite(VALS)
GRID_DT = float(np.median(np.diff(EPOCHS)))


def fine_cheap_tof(i, j, t, tof_center, half=0.05, step=0.0005):
    """Fine local tof search around tof_center at departure t; returns the cheap tof (<=dv_thr) or None."""
    lo = max(kt.min_tof, tof_center - half)
    for tof in np.arange(lo, tof_center + half, step):
        if kt.compute_transfer(i, j, t, float(tof)) <= kt.dv_thr:
            return float(tof)
    return None


def main(n=40):
    print(f"[E-710 M0c] epoch-continuity of cheap windows; grid spacing={GRID_DT:.2f}d. {n} cells.", flush=True)
    rng = np.random.default_rng(1)
    cells = np.argwhere(FIN)
    idx = rng.choice(len(cells), size=n, replace=False)
    widths = []; t0 = time.time()
    for k, ii in enumerate(idx):
        row, e = int(cells[ii][0]), int(cells[ii][1])
        i, j = int(KEYS[row][0]), int(KEYS[row][1])
        dep0 = float(EPOCHS[e]); tof0 = float(VALS[row, e])
        # sweep departure outward in both directions; track cheap tof smoothly (seed from last found)
        cheap_eps = [dep0]; ttrack = tof0
        for sign in (+1, -1):
            tc = tof0
            for m in range(1, 25):                                  # up to +-6d in 0.25d steps
                t = dep0 + sign * 0.25 * m
                if t < 0 or t > kt.max_time:
                    break
                ft = fine_cheap_tof(i, j, t, tc)
                if ft is None:
                    break                                          # window edge reached
                cheap_eps.append(t); tc = ft
        width = max(cheap_eps) - min(cheap_eps)
        widths.append(width)
        if (k + 1) % 10 == 0:
            print(f"  {k+1}/{n}: median window so far {np.median(widths):.2f}d [{time.time()-t0:.0f}s]", flush=True)
    w = np.array(widths)
    print(f"\n[E-710 M0c] cheap-epoch WINDOW width: median {np.median(w):.2f}d  p25 {np.percentile(w,25):.2f}d  "
          f"p75 {np.percentile(w,75):.2f}d  (grid spacing {GRID_DT:.2f}d)", flush=True)
    frac_wide = float((w > GRID_DT).mean())
    print(f"  fraction of windows WIDER than the grid spacing: {100*frac_wide:.0f}%", flush=True)
    if np.median(w) > 2 * GRID_DT:
        print(f"[E-710 M0c] -> (A) CONTINUOUS windows, well-sampled by 950-grid; cheap edges abundant & "
              f"servable at any departure via FINE tof root-find. Prior walls were COARSE-TOF blindness. "
              f"Build a fine-tof greedy/beam -> should thread >>367 -> rank-1 reachable. THE FLAW.", flush=True)
    elif np.median(w) > GRID_DT:
        print(f"[E-710 M0c] -> windows ~grid-scale; partly servable. Fine-tof helps but windows real-narrow.", flush=True)
    else:
        print(f"[E-710 M0c] -> (B) windows NARROWER than grid; genuinely isolated cheap points. Chaining hard "
              f"even with fine tof; the time-dependence wall is real, not a sampling artifact.", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
