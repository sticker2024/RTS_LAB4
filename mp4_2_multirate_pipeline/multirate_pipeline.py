#!/usr/bin/env python3
"""
Real-Time Systems - Unit 4 - Mini Project 4.2
Multi-rate environmental monitoring pipeline with timing-compliance reporting.

One gateway loop services several simulated sensor streams, each with its own
required sampling period (Section 4.1 timing budget).  The loop picks which due
stream to service with a documented rule - analogous to priority-based servicing
in CAN arbitration (Section 4.2): the highest-priority pending message goes first.

Scheduling rules implemented
  FP  fixed priority      : shortest required period = highest priority (rate-monotonic style)
  EDF earliest deadline   : deadline = release time + period; earliest deadline first
  RR  round-robin         : cycle through streams, skipping those with nothing pending

Job model (per stream i, required period P_i):
  release r_k = k * P_i  (the k-th required sample)
  The gateway can only serve one read at a time; a read takes a random processing time
  (short, with an occasional long tail = overrun).
  lateness L = service_start - release
    on-time : L <= TOL * P_i               (TOL = 10 %)
    late    : TOL * P_i < L < P_i          (served, but after the tolerance)
    missed  : the next release of the same stream arrived before this one was served
              -> the old sample is dropped (overwritten) and counted as missed
  period overrun (per stream) = max(0, actual interval between consecutive served
              samples - P_i)

Run:  python multirate_pipeline.py
"""
import heapq
import math
import os
import random
import statistics as st
from dataclasses import dataclass, field

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(HERE, "figures")
RES_DIR = os.path.join(HERE, "results")

SIM_LEN = 60.0       # simulated seconds
TOL = 0.10           # on-time tolerance (fraction of period)
P_TAIL = 0.05        # probability that a read is an overrun (long tail)
TAIL_RANGE = (4.0, 10.0)   # overrun = base_time * U(4,10)


# ----------------------------------------------------------------- stream model
@dataclass
class Stream:
    name: str
    period: float                 # required sampling period (s)
    base_time: float              # typical processing time of one read (s)
    signal: callable              # true underlying signal y(t)
    threshold: float              # alert threshold (rising crossing)
    unit: str = ""
    # --- run-time state ---
    pending: float = None         # release time of the pending job (None = nothing pending)
    next_k: int = 0               # index of next release not yet admitted
    served_times: list = field(default_factory=list)      # sample (service-start) times
    served_vals: list = field(default_factory=list)
    on_time: int = 0
    late: int = 0
    missed: int = 0
    missed_release: list = field(default_factory=list)
    late_release: list = field(default_factory=list)
    lateness: list = field(default_factory=list)
    alerts: list = field(default_factory=list)            # (detect_time, true_cross_time)
    _prev_val: float = None
    _alerted_cross: set = field(default_factory=set)

    def reset(self):
        self.pending = None; self.next_k = 0
        self.served_times = []; self.served_vals = []
        self.on_time = self.late = self.missed = 0
        self.missed_release = []; self.late_release = []; self.lateness = []
        self.alerts = []; self._prev_val = None; self._alerted_cross = set()

    @property
    def required(self):
        return math.ceil(SIM_LEN / self.period - 1e-9)   # releases k*P < SIM_LEN


def make_streams(four=False):
    s = [
        Stream("temperature", 0.5, 0.030,
               lambda t: 22 + 6 * math.sin(2 * math.pi * t / 20) + 0.3 * math.sin(2 * math.pi * t / 1.7),
               26.0, "degC"),
        Stream("humidity", 1.3, 0.045,
               lambda t: 50 + 15 * math.sin(2 * math.pi * t / 25 + 1.0) + 0.5 * math.sin(2 * math.pi * t / 3.1),
               60.0, "%RH"),
        Stream("air_quality", 3.0, 0.140,
               lambda t: 40 + 30 * math.sin(2 * math.pi * t / 30 + 2.0) + 4 * math.sin(2 * math.pi * t / 5.3),
               65.0, "AQI"),
    ]
    if four:
        s.append(Stream("vibration", 0.1, 0.018,
                        lambda t: 1.0 + 0.8 * math.sin(2 * math.pi * t / 9) + 0.04 * math.sin(2 * math.pi * t / 1.3),
                        1.4, "mm/s"))
    return s


def true_crossings(stream, thr, t_end):
    """Exact rising threshold-crossing instants of the underlying signal (1 ms grid + bisection)."""
    out, dt = [], 0.001
    prev_t, prev_y = 0.0, stream.signal(0.0)
    t = dt
    while t <= t_end:
        y = stream.signal(t)
        if prev_y < thr <= y:
            lo, hi = prev_t, t
            for _ in range(30):
                mid = 0.5 * (lo + hi)
                if stream.signal(mid) < thr:
                    lo = mid
                else:
                    hi = mid
            out.append(hi)
        prev_t, prev_y = t, y
        t += dt
    return out


# ------------------------------------------------------------------- scheduler
def processing_time(stream, rng):
    if rng.random() < P_TAIL:
        return stream.base_time * rng.uniform(*TAIL_RANGE)       # overrun / long tail
    return stream.base_time * rng.uniform(0.7, 1.3)


def run(streams, rule, seed):
    """Event-driven simulation of the single gateway loop."""
    rng = random.Random(seed)
    for s in streams:
        s.reset()
    # heap of (release_time, stream_index) - the next not-yet-admitted release of each stream
    rel = [(0.0, i) for i in range(len(streams))]
    heapq.heapify(rel)
    now = 0.0
    rr_ptr = 0
    busy_time = 0.0

    def admit(upto):
        while rel and rel[0][0] <= upto and rel[0][0] < SIM_LEN - 1e-9:
            r, i = heapq.heappop(rel)
            s = streams[i]
            if s.pending is not None:           # old job never served -> dropped (missed)
                s.missed += 1
                s.missed_release.append(s.pending)
            s.pending = r
            s.next_k += 1
            heapq.heappush(rel, (s.next_k * s.period, i))

    while now < SIM_LEN:
        admit(now)
        due = [i for i, s in enumerate(streams) if s.pending is not None]
        if not due:
            if not rel or rel[0][0] >= SIM_LEN - 1e-9:
                break
            now = rel[0][0]
            continue
        if rule == "FP":
            i = min(due, key=lambda j: streams[j].period)
        elif rule == "EDF":
            i = min(due, key=lambda j: (streams[j].pending + streams[j].period, streams[j].period))
        elif rule == "RR":
            for off in range(len(streams)):
                j = (rr_ptr + off) % len(streams)
                if j in due:
                    i = j
                    break
            rr_ptr = (i + 1) % len(streams)
        else:
            raise ValueError(rule)
        s = streams[i]
        r = s.pending
        s.pending = None
        lat = now - r
        s.lateness.append(lat)
        if lat <= TOL * s.period:
            s.on_time += 1
        else:
            s.late += 1
            s.late_release.append(r)
        # sample is taken at service start
        y = s.signal(now)
        s.served_times.append(now)
        s.served_vals.append(y)
        # alert rule: rising crossing between consecutive *served* samples
        if s._prev_val is not None and s._prev_val < s.threshold <= y:
            s.alerts.append(now)
        s._prev_val = y
        c = processing_time(s, rng)
        busy_time += c
        now += c
    # jobs still pending (or released while the last read was running) when the run ends were never served
    admit(SIM_LEN)
    for s in streams:
        if s.pending is not None:
            s.missed += 1
            s.missed_release.append(s.pending)
            s.pending = None
    util = busy_time / SIM_LEN
    return util


def report(streams, util, title):
    lines = [f"--- {title} ---  (gateway utilisation {100*util:.1f} %)",
             f"{'stream':<13}{'period':>8}{'required':>9}{'on-time':>8}{'late':>6}{'missed':>7}"
             f"{'on-time%':>9}{'meanOvr(ms)':>12}{'maxOvr(ms)':>11}{'alertLat(ms)':>13}"]
    summary = []
    for s in streams:
        iv = [b - a for a, b in zip(s.served_times[:-1], s.served_times[1:])]
        ov = [max(0.0, x - s.period) for x in iv]
        # alert latency: detection time - true crossing time, matched in order
        tc = true_crossings(s, s.threshold, SIM_LEN)
        lats = []
        det = sorted(s.alerts)
        for idx, c in enumerate(tc):
            limit = tc[idx + 1] if idx + 1 < len(tc) else SIM_LEN + 10.0
            hit = [d for d in det if c - 1e-9 <= d < limit]       # first detection before next crossing
            if hit:
                lats.append(hit[0] - c)
        
        row = {
            "stream": s.name, "period": s.period, "required": s.required,
            "on_time": s.on_time, "late": s.late, "missed": s.missed,
            "on_time_pct": 100 * s.on_time / s.required,
            "mean_overrun_ms": 1000 * (st.mean(ov) if ov else 0.0),
            "max_overrun_ms": 1000 * (max(ov) if ov else 0.0),
            "mean_alert_latency_ms": 1000 * (st.mean(lats) if lats else float("nan")),
            "true_crossings": len(tc), "alerts_detected": len(lats),
        }
        summary.append(row)
        lines.append(f"{s.name:<13}{s.period:>8.2f}{s.required:>9}{s.on_time:>8}{s.late:>6}{s.missed:>7}"
                     f"{row['on_time_pct']:>9.1f}{row['mean_overrun_ms']:>12.1f}{row['max_overrun_ms']:>11.1f}"
                     f"{row['mean_alert_latency_ms']:>13.1f}   ({len(lats)}/{len(tc)} crossings alerted)")
        s.alert_log = (tc, lats)
    return summary, "\n".join(lines)


# --------------------------------------------------------------------- plotting
def plot_signals(streams, title, path):
    n = len(streams)
    fig, axes = plt.subplots(n, 1, figsize=(11, 2.6 * n), sharex=True)
    if n == 1:
        axes = [axes]
    for ax, s in zip(axes, streams):
        tt = [i * 0.02 for i in range(int(SIM_LEN / 0.02))]
        ax.plot(tt, [s.signal(x) for x in tt], color="0.7", lw=1, label="true signal")
        ax.axhline(s.threshold, color="k", ls=":", lw=1, label="alert threshold")
        ax.plot(s.served_times, s.served_vals, ".", ms=3 if s.period > 0.3 else 1.5, color="tab:blue",
                label="serviced samples")
        if s.late_release:
            ax.plot(s.late_release, [s.signal(x) for x in s.late_release], "o", mfc="none", ms=6,
                    color="tab:orange", label=f"late ({len(s.late_release)})")
        if s.missed_release:
            ax.plot(s.missed_release, [s.signal(x) for x in s.missed_release], "x", ms=7, color="tab:red",
                    label=f"missed ({len(s.missed_release)})")
        tc, _ = s.alert_log
        for c in tc:
            ax.axvline(c, color="tab:green", alpha=0.35, lw=1)
        ax.set_ylabel(f"{s.name}\n[{s.unit}]")
        ax.legend(loc="upper right", fontsize=7, ncol=5)
    axes[-1].set_xlabel("time (s)   (green lines = true threshold crossings)")
    axes[0].set_title(title)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def plot_bars(summary, title, path):
    names = [r["stream"] for r in summary]
    x = range(len(names))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    on = [r["on_time"] for r in summary]
    la = [r["late"] for r in summary]
    mi = [r["missed"] for r in summary]
    w = 0.26
    ax.bar([i - w for i in x], on, w, label="on-time", color="tab:green")
    ax.bar(list(x), la, w, label="late", color="tab:orange")
    ax.bar([i + w for i in x], mi, w, label="missed", color="tab:red")
    ax.set_xticks(list(x)); ax.set_xticklabels(names)
    ax.set_yscale("symlog", linthresh=10)
    ax.set_ylabel("number of required samples (symlog)")
    ax.set_title(title); ax.legend()
    for i, r in enumerate(summary):
        ax.text(i, max(on[i], 1) * 1.15, f"{r['on_time_pct']:.0f}% on-time", ha="center", fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


# ----------------------------------------------------------------------- driver
def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(RES_DIR, exist_ok=True)
    SEED = 11
    all_rows = []
    configs = [("FP", False), ("EDF", False), ("RR", False), ("FP", True), ("EDF", True), ("RR", True)]
    print("Mini Project 4.2 - multi-rate environmental monitoring pipeline")
    print(f"simulated length {SIM_LEN:.0f} s | on-time tolerance {int(TOL*100)}% of period | "
          f"tail probability {int(P_TAIL*100)}% | seed {SEED}\n")
    for rule, four in configs:
        streams = make_streams(four)
        util = run(streams, rule, SEED)
        title = f"{rule} scheduling, {len(streams)} streams"
        summary, text = report(streams, util, title)
        print(text + "\n")
        for r in summary:
            all_rows.append({"rule": rule, "streams": len(streams), "util": util, **r})
        tag = f"{rule}_{len(streams)}streams"
        plot_signals(streams, f"Signals, serviced samples, late/missed - {title}",
                     os.path.join(FIG_DIR, f"signals_{tag}.png"))
        plot_bars(summary, f"On-time / late / missed per stream - {title}",
                  os.path.join(FIG_DIR, f"compliance_{tag}.png"))

    # Monte-Carlo comparison of the rules over many seeds
    print("Monte-Carlo comparison over 100 seeds (mean on-time % per stream)")
    print(f"{'rule':<5}{'streams':>8}{'util%':>7}" + "".join(f"{n:>14}" for n in
          ["temperature", "humidity", "air_quality", "vibration"]))
    mc_rows = []
    for rule, four in configs:
        acc, us = {}, []
        for sd in range(100, 200):
            streams = make_streams(four)
            us.append(run(streams, rule, sd))
            for s in streams:
                acc.setdefault(s.name, []).append(100 * s.on_time / s.required)
        line = f"{rule:<5}{(4 if four else 3):>8}{100*st.mean(us):>7.1f}"
        for n in ["temperature", "humidity", "air_quality", "vibration"]:
            line += f"{st.mean(acc[n]):>14.1f}" if n in acc else f"{'-':>14}"
            if n in acc:
                mc_rows.append({"rule": rule, "streams": 4 if four else 3, "stream": n,
                                "mean_on_time_pct": st.mean(acc[n])})
        print(line)

    import csv
    with open(os.path.join(RES_DIR, "compliance_single_seed.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys())); w.writeheader(); w.writerows(all_rows)
    with open(os.path.join(RES_DIR, "compliance_monte_carlo.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mc_rows[0].keys())); w.writeheader(); w.writerows(mc_rows)
    print("\nFigures -> ./figures   tables -> ./results")


if __name__ == "__main__":
    main()
