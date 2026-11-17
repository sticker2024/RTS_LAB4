#!/usr/bin/env python3
"""
Real-Time Systems - Unit 4 - Mini Project 4.1
Simulating sampling jitter and processing overruns in an embedded
sensing-and-control loop (Section 4.1 timing budget, Section 4.5 PLC scan cycle).

Pure-Python simulation (stdlib + matplotlib).  Run:

    python rt_sampling_sim.py            # full experiment -> figures/ + results/
    python rt_sampling_sim.py --quick    # fewer Monte-Carlo seeds

TIMING MODEL (documented so the results can be audited)
-------------------------------------------------------
* The loop is time-triggered: tick k is *scheduled* for  k * T_NOMINAL.
* Sampling jitter  : the actual start of tick k is   k*T + jitter_k,
                     jitter_k ~ U(-J, +J).  (interrupt latency / scheduling noise)
* Computation time : c_k is short (U(0.05T, 0.15T)) with probability 1-p, and is an
                     overrun, U(1.2T, 3.0T), with probability p   (a WCET violation).
* Overrun handling : exactly like an overrunning PLC scan (Section 4.5) the
                     processing of cycle k must finish before the loop can start
                     again.  The first tick that was due during the overrun starts
                     late, at the moment processing finishes; any further ticks that
                     were also due inside the overrun are lost (missed ticks).
* Actuation        : the controller issues its command when the computation for
                     the sample has finished, i.e. at  t_sample + c_k.
* Ideal baseline   : zero jitter, zero overrun, constant computation time C_IDEAL.
"""
import argparse
import csv
import math
import os
import random
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(HERE, "figures")
RES_DIR = os.path.join(HERE, "results")

# ----------------------------------------------------------------- parameters
T_NOMINAL = 0.05          # s  (20 Hz)
RUN_LEN = 20.0            # s
AMPLITUDE = 1.0
SIGNAL_PERIOD = 2.0       # s
THRESHOLD = 0.5           # controller threshold (rising crossing)
C_IDEAL_FRAC = 0.10       # ideal computation time = 0.10 T
C_NORMAL = (0.05, 0.15)   # normal computation time range, fractions of T
C_OVERRUN = (1.2, 3.0)    # overrun computation time range, fractions of T
MATCH_WINDOW = SIGNAL_PERIOD / 2.0


# ------------------------------------------------------------- true process
def true_signal(t):
    """Slowly varying analogue quantity (sine) + small continuous 'noise'.
    The noise is a sum of two fast low-amplitude sinusoids so the function is
    deterministic: ideal and jittered runs observe exactly the same physical process."""
    base = AMPLITUDE * math.sin(2 * math.pi * t / SIGNAL_PERIOD)
    noise = 0.010 * math.sin(2 * math.pi * 7.3 * t) + 0.005 * math.sin(2 * math.pi * 13.1 * t + 1.0)
    return base + noise


# ------------------------------------------------------------- run builders
def ideal_run(T=T_NOMINAL, run_len=RUN_LEN):
    """Zero-jitter, zero-overrun baseline (the ideal fixed-period scan cycle)."""
    n = int(round(run_len / T))
    t = [k * T for k in range(n)]
    y = [true_signal(x) for x in t]
    c = [C_IDEAL_FRAC * T] * n
    return {"t": t, "y": y, "c": c, "jitter": [0.0] * n, "overrun": [False] * n,
            "late_start": [0.0] * n, "dropped": 0, "T": T}


def jittered_run(J, p_over, rng, T=T_NOMINAL, run_len=RUN_LEN, over_scale=1.0):
    """Event loop with sampling jitter J (seconds, absolute) and overrun probability p_over."""
    n = int(round(run_len / T))
    t_s, y_s, c_s, jit, over, late = [], [], [], [], [], []
    free = 0.0            # time at which the loop is free to start the next cycle
    dropped = 0
    k = 0
    while k < n:
        j = rng.uniform(-J, J) if J > 0 else 0.0
        sched = k * T + j
        if sched < free:                 # tick was due while the previous cycle still ran
            start = free                 # starts late (PLC: next scan delayed)
            lateness = free - sched
            # any later ticks whose scheduled instant is also <= start are lost
            while k + 1 < n and (k + 1) * T <= start:
                k += 1
                dropped += 1
        else:
            start = sched
            lateness = 0.0
        if rng.random() < p_over:
            c = rng.uniform(*C_OVERRUN) * T * over_scale
            is_over = True
        else:
            c = rng.uniform(*C_NORMAL) * T
            is_over = False
        t_s.append(start)
        y_s.append(true_signal(start))
        c_s.append(c)
        jit.append(j)
        over.append(is_over)
        late.append(lateness)
        free = start + c
        k += 1
    return {"t": t_s, "y": y_s, "c": c_s, "jitter": jit, "overrun": over,
            "late_start": late, "dropped": dropped, "T": T}


# --------------------------------------------------------------- controller
def threshold_actuations(run, thr=THRESHOLD):
    """Times at which the threshold controller issues a command (rising crossing)."""
    acts = []
    for i in range(1, len(run["t"])):
        if run["y"][i - 1] < thr <= run["y"][i]:
            acts.append(run["t"][i] + run["c"][i])
    return acts


def actuation_delays(ideal_acts, jit_acts, window=MATCH_WINDOW):
    """Match each ideal actuation with the nearest jittered one (within `window`)."""
    delays, missed = [], 0
    for a in ideal_acts:
        cand = [b for b in jit_acts if abs(b - a) <= window]
        if not cand:
            missed += 1
            continue
        b = min(cand, key=lambda x: abs(x - a))
        delays.append(b - a)
    return delays, missed


def p_controller_rms_error(run, ideal, kp=1.0, setpoint=0.0, T=T_NOMINAL, run_len=RUN_LEN):
    """P-type rule u = Kp*(setpoint - y), held (ZOH) between updates.
    Returns RMS difference between the jittered controller output and the ideal one."""
    def hold(r):
        times = [t + c for t, c in zip(r["t"], r["c"])]
        us = [kp * (setpoint - y) for y in r["y"]]
        return times, us

    def u_at(times, us, x):
        lo, hi = 0, len(times) - 1
        if x < times[0]:
            return 0.0
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if times[mid] <= x:
                lo = mid
            else:
                hi = mid - 1
        return us[lo]

    ti, ui = hold(ideal)
    tj, uj = hold(run)
    grid = [i * 0.001 for i in range(int(run_len * 1000))]
    se = sum((u_at(ti, ui, x) - u_at(tj, uj, x)) ** 2 for x in grid)
    return math.sqrt(se / len(grid))


# --------------------------------------------------------------- statistics
def timing_stats(run):
    t = run["t"]
    iv = [b - a for a, b in zip(t[:-1], t[1:])]
    T = run["T"]
    n = len(iv)
    over_pct = 100.0 * sum(run["overrun"]) / len(run["overrun"])
    return {
        "mean_interval_ms": 1000 * st.mean(iv),
        "std_interval_ms": 1000 * (st.pstdev(iv) if len(iv) > 1 else 0.0),
        "max_overrun_ms": 1000 * max(0.0, max(c - T for c in run["c"])),
        "missed_period_pct": over_pct,                      # cycles whose computation exceeded T
        "gt15T_pct": 100.0 * sum(1 for x in iv if x > 1.5 * T) / n,   # compliance metric (lab task)
        "dropped_ticks": run["dropped"],
        "intervals": iv,
    }


def evaluate(J, p_over, seed, T=T_NOMINAL, run_len=RUN_LEN, full=True, over_scale=1.0):
    rng = random.Random(seed)
    ideal = ideal_run(T, run_len)
    run = jittered_run(J, p_over, rng, T, run_len, over_scale)
    ia = threshold_actuations(ideal)
    ja = threshold_actuations(run)
    d, missed = actuation_delays(ia, ja)
    ts = timing_stats(run)
    out = dict(ts)
    out.update({
        "n_cross": len(ia), "n_matched": len(d), "n_missed_cross": missed,
        "mean_delay_ms": 1000 * st.mean(d) if d else float("nan"),
        "mean_abs_delay_ms": 1000 * st.mean(abs(x) for x in d) if d else float("nan"),
        "max_delay_ms": 1000 * max(d, key=abs) if d else float("nan"),
        "P_rms_err": p_controller_rms_error(run, ideal, T=T, run_len=run_len) if full else float("nan"),
    })
    return ideal, run, ia, ja, d, out


def monte_carlo(J, p_over, seeds, T=T_NOMINAL, run_len=RUN_LEN, over_scale=1.0):
    keys = ["mean_interval_ms", "std_interval_ms", "max_overrun_ms", "missed_period_pct",
            "gt15T_pct", "dropped_ticks", "n_missed_cross", "mean_delay_ms", "mean_abs_delay_ms",
            "max_delay_ms", "P_rms_err"]
    acc = {k: [] for k in keys}
    for s in seeds:
        *_, o = evaluate(J, p_over, s, T, run_len, over_scale=over_scale)
        for k in keys:
            if not math.isnan(o[k]):
                acc[k].append(o[k])
    return {k: (st.mean(v) if v else float("nan")) for k, v in acc.items()}


# ----------------------------------------------------------------- plotting
def figure1(ideal, run, T, title, path):
    """Figure 1: true signal + sample points (top), per-cycle interval error (bottom)."""
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7.5), gridspec_kw={"height_ratios": [2, 1]})
    tt = [i * 0.002 for i in range(int(RUN_LEN / 0.002))]
    a1.plot(tt, [true_signal(x) for x in tt], color="0.65", lw=1.2, label="true signal (continuous)")
    a1.plot(ideal["t"], ideal["y"], "o", ms=4, color="tab:blue", label="ideal samples")
    a1.plot(run["t"], run["y"], "x", ms=6, color="tab:red", label="jittered / overrun samples")
    a1.axhline(THRESHOLD, color="k", ls=":", lw=1, label=f"threshold = {THRESHOLD}")
    a1.set_xlim(0, 6); a1.set_xlabel("time (s) - zoomed to first 6 s"); a1.set_ylabel("signal")
    a1.set_title(title); a1.legend(loc="lower right", fontsize=8, ncol=2)
    iv = [b - a - T for a, b in zip(run["t"][:-1], run["t"][1:])]
    a2.plot(range(len(iv)), [1000 * x for x in iv], ".-", lw=0.7, ms=3, color="tab:red")
    a2.axhline(0, color="k", lw=1)
    a2.set_xlabel("cycle index k"); a2.set_ylabel("interval - T_nominal (ms)")
    a2.set_title("Per-cycle inter-sample interval error")
    fig.tight_layout(); fig.savefig(path, dpi=140); plt.close(fig)


def figure2(ia, ja, delays, title, path):
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.eventplot([ia], lineoffsets=1, linelengths=0.6, colors="tab:blue")
    ax.eventplot([ja], lineoffsets=0, linelengths=0.6, colors="tab:red")
    ax.set_yticks([0, 1]); ax.set_yticklabels(["jittered / overrun", "ideal"])
    ax.set_xlim(0, RUN_LEN); ax.set_xlabel("time (s)")
    if delays:
        txt = (f"mean delay = {1000*st.mean(delays):+.1f} ms | max |delay| = "
               f"{1000*max(abs(d) for d in delays):.1f} ms | matched {len(delays)} crossings")
    else:
        txt = "no matched crossings"
    ax.set_title(title + "\n" + txt, fontsize=10)
    fig.tight_layout(); fig.savefig(path, dpi=140); plt.close(fig)


# ------------------------------------------------------------------- driver
def fmt_row(label, o):
    return (f"{label:<26} {o['mean_interval_ms']:7.2f} {o['std_interval_ms']:7.2f} "
            f"{o['max_overrun_ms']:8.1f} {o['missed_period_pct']:7.1f} {o['gt15T_pct']:7.1f} "
            f"{o['dropped_ticks']:7.1f} {o['n_missed_cross']:6.2f} {o['mean_delay_ms']:8.2f} "
            f"{o['max_delay_ms']:8.2f} {o['P_rms_err']:7.4f}")


HDR = (f"{'configuration':<26} {'mean_dt':>7} {'std_dt':>7} {'maxOver':>8} {'over%':>7} "
       f"{'>1.5T%':>7} {'drops':>7} {'miss':>6} {'meanDly':>8} {'maxDly':>8} {'P_rms':>7}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="use 20 Monte-Carlo seeds instead of 200")
    args = ap.parse_args()
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(RES_DIR, exist_ok=True)
    seeds = list(range(100, 120 if args.quick else 300))
    T = T_NOMINAL
    N = int(round(RUN_LEN / T))
    print("=" * 100)
    print(f"Mini Project 4.1 - sampling jitter / overrun simulation   T_nominal={T*1000:.0f} ms "
          f"({1/T:.0f} Hz)  run={RUN_LEN:.0f} s  N={N} scheduled samples  threshold={THRESHOLD}")
    print("=" * 100)

    # ---- 1. sanity check: J=0, p=0 must reproduce the baseline
    _, run0, ia0, ja0, d0, o0 = evaluate(0.0, 0.0, 1)
    print(f"[sanity] J=0, p=0 -> {o0['n_matched']}/{o0['n_cross']} crossings matched, "
          f"mean |delay| = {o0['mean_abs_delay_ms']:.2f} ms, max |delay| = {abs(o0['max_delay_ms']):.2f} ms "
          f"(difference only from the c_k draw, c in 5..15% of T)")

    # ---- 2. three required figure configurations (single seed, for display)
    cfgs = [("A  jitter only  J=30% T, p=0", 0.30 * T, 0.0, "A_jitter_only"),
            ("B  overruns only J=0, p=10%", 0.0, 0.10, "B_overrun_only"),
            ("C  combined  J=30% T, p=10%", 0.30 * T, 0.10, "C_combined")]
    print("\nFigure configurations (single seed = 7):")
    print(HDR)
    for label, J, p, tag in cfgs:
        ideal, run, ia, ja, d, o = evaluate(J, p, 7)
        print(fmt_row(label, o))
        figure1(ideal, run, T, f"Figure 1 - configuration {label}", os.path.join(FIG_DIR, f"fig1_{tag}.png"))
        figure2(ia, ja, d, f"Figure 2 - actuation instants, configuration {label}",
                os.path.join(FIG_DIR, f"fig2_{tag}.png"))

    # ---- 3. sweep: 3 jitter bounds x 3 overrun probabilities (Monte-Carlo mean)
    print(f"\nSweep: Monte-Carlo means over {len(seeds)} seeds")
    print(HDR)
    rows = []
    for jf in (0.10, 0.30, 0.50):
        for p in (0.02, 0.05, 0.15):
            o = monte_carlo(jf * T, p, seeds)
            lab = f"J={int(jf*100)}%T p={int(p*100)}%"
            print(fmt_row(lab, o))
            rows.append({"jitter_frac_T": jf, "p_overrun": p, **o})
    with open(os.path.join(RES_DIR, "sweep_grid.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    # ---- 4. Lab task 1: equal average disturbance, jitter-only vs overrun-only
    print("\nLab task 1 - equal mean disturbance d (mean |timing disturbance| per cycle, as fraction of T)")
    print("  jitter-only : J = 2d  (mean |U(-J,J)| = J/2 = d)")
    print("  overrun-only: p = d / E[excess] with E[excess] = mean(c_overrun) - T = 1.1 T")
    print(HDR)
    t1 = []
    for d in (0.05, 0.10, 0.20):
        oj = monte_carlo(2 * d * T, 0.0, seeds)
        p = d / 1.1
        oo = monte_carlo(0.0, p, seeds)
        print(fmt_row(f"jitter-only  d={d:.2f}T", oj))
        print(fmt_row(f"overrun-only d={d:.2f}T (p={p*100:.1f}%)", oo))
        t1.append({"d_over_T": d, "kind": "jitter", **oj})
        t1.append({"d_over_T": d, "kind": "overrun", "p": p, **oo})
    with open(os.path.join(RES_DIR, "labtask1_equal_disturbance.csv"), "w", newline="") as f:
        keys = sorted({k for r in t1 for k in r})
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(t1)

    # ---- 5. Lab task 2: P-type controller sensitivity (already in P_rms column) - summary
    print("\nLab task 2 - P-type rule u = Kp(0 - y), ZOH output; RMS error vs ideal output (column P_rms above)")
    for label, J, p in (("jitter-only  J=30%T", 0.3 * T, 0.0), ("overrun-only p=10%", 0.0, 0.10),
                        ("combined", 0.3 * T, 0.10)):
        o = monte_carlo(J, p, seeds)
        print(f"  {label:<22} P-rule RMS error = {o['P_rms_err']:.4f} | threshold-rule mean |delay| = "
              f"{o['mean_abs_delay_ms']:.2f} ms, missed crossings = {o['n_missed_cross']:.2f}")

    # ---- 6. Lab task 3: compliance metric vs std
    print("\nLab task 3 - compliance metric (% intervals > 1.5 T) vs raw interval std")
    for label, J, p in (("jitter-only  J=30%T", 0.3 * T, 0.0), ("jitter-only  J=50%T", 0.5 * T, 0.0),
                        ("overrun-only p=2%", 0.0, 0.02), ("overrun-only p=10%", 0.0, 0.10)):
        o = monte_carlo(J, p, seeds)
        print(f"  {label:<22} std = {o['std_interval_ms']:6.2f} ms   >1.5T = {o['gt15T_pct']:5.2f} %   "
              f"mean|delay| = {o['mean_abs_delay_ms']:6.2f} ms")

    # ---- 7. Lab task 4: halve T, keep absolute jitter / overrun magnitudes
    print("\nLab task 4 - halve T_nominal while holding ABSOLUTE jitter (15 ms bound) and ABSOLUTE")
    print("  overrun duration (mean 105 ms, p = 10% per cycle) fixed (over_scale = 0.05/T keeps seconds constant)")
    for Tn in (0.05, 0.025):
        sc = 0.05 / Tn
        o_j = monte_carlo(0.015, 0.0, seeds, T=Tn)
        o_o = monte_carlo(0.0, 0.10, seeds, T=Tn, over_scale=sc)
        print(f"  T={Tn*1000:5.1f} ms | jitter-only : std={o_j['std_interval_ms']:5.2f} ms = {100*o_j['std_interval_ms']/(1000*Tn):3.0f}% of T, "
              f">1.5T={o_j['gt15T_pct']:5.1f}%, mean|delay|={o_j['mean_abs_delay_ms']:5.2f} ms, dropped={o_j['dropped_ticks']:4.1f}")
        print(f"  {'':>12} | overrun-only: std={o_o['std_interval_ms']:5.2f} ms = {100*o_o['std_interval_ms']/(1000*Tn):3.0f}% of T, "
              f">1.5T={o_o['gt15T_pct']:5.1f}%, mean|delay|={o_o['mean_abs_delay_ms']:5.2f} ms, dropped={o_o['dropped_ticks']:4.1f}")

    print("\nFigures written to ./figures, tables to ./results")


if __name__ == "__main__":
    main()
