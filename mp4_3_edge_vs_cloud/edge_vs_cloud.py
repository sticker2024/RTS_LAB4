#!/usr/bin/env python3
"""
Real-Time Systems - Unit 4 - Mini Project 4.3
Edge-versus-cloud latency simulator for a real-time IoT decision task
(Section 4.9 end-to-end latency budget / edge computing; Section 4.8 URLLC bounded latency).

Task: every sensor reading needs one "decide" computation (is this vibration/temperature
reading an anomaly that needs local action?) before an application deadline (100 ms).

Model (all numbers in milliseconds; every value is an ASSUMPTION that you can change in the
PARAMETERS block - see README):

  EDGE   : limited local hardware -> longer compute, but tiny and low-variance transport.
           easy decision : lognormal, median 45 ms, sigma 0.12
           hard decision : lognormal, median 75 ms, sigma 0.12   (bigger model on weak CPU)
           + 1 ms local bus transport, + 0.5 % chance of a 20-40 ms hiccup (GC / interrupt)
  CLOUD  : upload leg + remote compute + download leg
           each network leg: lognormal, median 20 ms*(1+congestion), sigma 0.25
           with probability p_spike = SPIKE_P_MAX * congestion a leg ALSO gets a heavy-tailed
           (Pareto, alpha=1.6, xm=40 ms) congestion spike
           remote compute: lognormal, median 6 ms (powerful server), sigma 0.2
  HYBRID : easy decisions are made on the edge; "hard" decisions (HARD_FRAC of events) try the
           edge first (cheap 8 ms confidence gate) and, when it is not confident, escalate to
           the cloud -> latency = gate + cloud.
  Correctness proxy (extra, to make the hybrid trade-off visible):
           edge accuracy 99 % (easy) / 85 % (hard); cloud accuracy 99 % / 98 %.

Both architectures see the SAME event sequence (same easy/hard flags and same random streams).

Run:  python edge_vs_cloud.py
"""
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

# ----------------------------------------------------------------- PARAMETERS
N_EVENTS = 20000
RATE_HZ = 10                  # nominal sensor rate (events are independent, so only N matters)
DEADLINE = 100.0              # ms
HARD_FRAC = 0.20              # share of decisions that need the bigger model
BASE_CONGESTION = 0.30        # baseline cloud stress for the results table
EDGE_MED_EASY, EDGE_MED_HARD, EDGE_SIGMA = 45.0, 75.0, 0.12
EDGE_TRANSPORT = 1.0
EDGE_HICCUP_P, EDGE_HICCUP_RANGE = 0.005, (20.0, 40.0)
LEG_MED, LEG_SIGMA = 20.0, 0.25
SPIKE_P_MAX = 0.20            # per-leg spike probability at congestion = 1
PARETO_ALPHA, PARETO_XM = 1.6, 40.0
CLOUD_COMP_MED, CLOUD_COMP_SIGMA = 6.0, 0.20
GATE_MS = 8.0                 # hybrid: edge confidence gate before escalating
ACC_EDGE = (0.99, 0.85)       # (easy, hard)
ACC_CLOUD = (0.99, 0.98)


# -------------------------------------------------------------- latency models
def edge_latency(rng, hard=False):
    med = EDGE_MED_HARD if hard else EDGE_MED_EASY
    lat = rng.lognormvariate(math.log(med), EDGE_SIGMA) + EDGE_TRANSPORT
    if rng.random() < EDGE_HICCUP_P:
        lat += rng.uniform(*EDGE_HICCUP_RANGE)
    return lat


def _leg(rng, congestion):
    lat = rng.lognormvariate(math.log(LEG_MED * (1 + congestion)), LEG_SIGMA)
    if rng.random() < SPIKE_P_MAX * congestion:
        lat += PARETO_XM * rng.paretovariate(PARETO_ALPHA)       # heavy-tailed spike
    return lat


def cloud_latency(rng, congestion):
    up = _leg(rng, congestion)
    comp = rng.lognormvariate(math.log(CLOUD_COMP_MED), CLOUD_COMP_SIGMA)
    down = _leg(rng, congestion)
    return up + comp + down


# --------------------------------------------------------------- experiments
def make_events(n, seed):
    rng = random.Random(seed)
    return [rng.random() < HARD_FRAC for _ in range(n)]


def simulate(congestion, seed=1, n=N_EVENTS, deadline=DEADLINE):
    hard = make_events(n, seed)
    # separate, independent random streams per path => same events, fair comparison
    r_edge, r_cloud, r_acc = random.Random(seed + 1), random.Random(seed + 2), random.Random(seed + 3)
    edge, cloud, hybrid = [], [], []
    ok_edge = ok_cloud = ok_hyb = 0
    for h in hard:
        e = edge_latency(r_edge, h)
        c = cloud_latency(r_cloud, congestion)
        u = r_acc.random()
        edge.append(e); cloud.append(c)
        if h:
            hyb = GATE_MS + c                      # gate on edge, then escalate to the cloud
            correct_h = u < ACC_CLOUD[1]
            correct_e = u < ACC_EDGE[1]
        else:
            hyb = e                                # easy decision stays on the edge
            correct_h = u < ACC_EDGE[0]
            correct_e = u < ACC_EDGE[0]
        hybrid.append(hyb)
        correct_c = u < (ACC_CLOUD[1] if h else ACC_CLOUD[0])
        ok_edge += (e <= deadline) and correct_e
        ok_cloud += (c <= deadline) and correct_c
        ok_hyb += (hyb <= deadline) and correct_h
    return {"hard": hard, "edge": edge, "cloud": cloud, "hybrid": hybrid,
            "ontime_correct": {"edge": 100 * ok_edge / n, "cloud": 100 * ok_cloud / n, "hybrid": 100 * ok_hyb / n}}


def pct(data, p):
    s = sorted(data)
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def stats(lat, deadline=DEADLINE):
    return {"mean": st.mean(lat), "p95": pct(lat, 95), "p99": pct(lat, 99), "worst": max(lat),
            "compliance": 100.0 * sum(1 for x in lat if x <= deadline) / len(lat)}


# ---------------------------------------------------------------------- driver
def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(RES_DIR, exist_ok=True)
    print("Mini Project 4.3 - edge vs cloud latency simulator")
    print(f"events={N_EVENTS}  deadline={DEADLINE:.0f} ms  hard-decision share={int(HARD_FRAC*100)}%  "
          f"baseline congestion={BASE_CONGESTION}\n")

    sim = simulate(BASE_CONGESTION)
    rows = []
    print(f"{'path':<8}{'mean(ms)':>10}{'p95(ms)':>10}{'p99(ms)':>10}{'worst(ms)':>11}{'deadline met %':>16}{'on-time&correct %':>19}")
    for name in ("edge", "cloud", "hybrid"):
        s = stats(sim[name])
        s["ontime_correct"] = sim["ontime_correct"][name]
        rows.append({"path": name, **s})
        print(f"{name:<8}{s['mean']:>10.1f}{s['p95']:>10.1f}{s['p99']:>10.1f}{s['worst']:>11.1f}"
              f"{s['compliance']:>16.2f}{s['ontime_correct']:>19.2f}")
    with open(os.path.join(RES_DIR, "results_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    # split edge latency by easy / hard for the write-up
    e_easy = [l for l, h in zip(sim["edge"], sim["hard"]) if not h]
    e_hard = [l for l, h in zip(sim["edge"], sim["hard"]) if h]
    print(f"\nedge easy decisions : mean {st.mean(e_easy):.1f} ms, p99 {pct(e_easy,99):.1f} ms, "
          f"met {100*sum(1 for x in e_easy if x<=DEADLINE)/len(e_easy):.2f} %")
    print(f"edge hard decisions : mean {st.mean(e_hard):.1f} ms, p99 {pct(e_hard,99):.1f} ms, "
          f"met {100*sum(1 for x in e_hard if x<=DEADLINE)/len(e_hard):.2f} %")

    # ---- Figure 1: overlaid latency distributions (histogram + empirical CDF)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
    bins = [i * 4 for i in range(0, 101)]
    for name, col in (("edge", "tab:green"), ("cloud", "tab:red"), ("hybrid", "tab:blue")):
        a1.hist([min(x, 400) for x in sim[name]], bins=bins, alpha=0.45, color=col, label=name, density=True)
        xs = sorted(sim[name]); n = len(xs)
        a2.plot(xs, [(i + 1) / n for i in range(n)], color=col, label=name)
    a1.axvline(DEADLINE, color="k", ls="--", label=f"deadline {DEADLINE:.0f} ms")
    a2.axvline(DEADLINE, color="k", ls="--")
    a1.set_xlim(0, 300); a2.set_xlim(0, 400)
    a1.set_xlabel("end-to-end latency (ms)"); a1.set_ylabel("density"); a1.legend()
    a1.set_title(f"Figure 1a - latency distributions (congestion = {BASE_CONGESTION})")
    a2.set_xlabel("end-to-end latency (ms)"); a2.set_ylabel("P(latency <= x)")
    a2.set_title("Figure 1b - empirical CDF (cloud tail is what breaks the deadline)")
    a2.set_ylim(0.75, 1.005); a2.legend(loc="lower right"); a2.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(FIG_DIR, "fig1_latency_distributions.png"), dpi=140); plt.close(fig)

    # ---- Figure 2: compliance vs congestion sweep
    print("\nCongestion sweep (deadline-compliance %)")
    print(f"{'congestion':>10}{'cloud':>9}{'edge':>9}{'hybrid':>9}{'cloud p99(ms)':>15}")
    levels = [i * 0.05 for i in range(0, 21)]
    c_comp, e_comp, h_comp, c_p99 = [], [], [], []
    sweep_rows = []
    for lv in levels:
        s = simulate(lv, seed=5, n=8000)
        cs, es, hs = stats(s["cloud"]), stats(s["edge"]), stats(s["hybrid"])
        c_comp.append(cs["compliance"]); e_comp.append(es["compliance"]); h_comp.append(hs["compliance"])
        c_p99.append(cs["p99"])
        sweep_rows.append({"congestion": round(lv, 2), "cloud": cs["compliance"], "edge": es["compliance"],
                           "hybrid": hs["compliance"], "cloud_p99": cs["p99"]})
        if round(lv * 20) % 2 == 0:
            print(f"{lv:>10.2f}{cs['compliance']:>9.2f}{es['compliance']:>9.2f}{hs['compliance']:>9.2f}{cs['p99']:>15.1f}")
    with open(os.path.join(RES_DIR, "congestion_sweep.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sweep_rows[0].keys())); w.writeheader(); w.writerows(sweep_rows)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.plot(levels, c_comp, "o-", color="tab:red", label="cloud")
    ax.plot(levels, h_comp, "s-", color="tab:blue", label="hybrid")
    ax.plot(levels, e_comp, "--", color="tab:green", label="edge (flat reference)")
    ax.axhline(99.0, color="0.5", ls=":", lw=1); ax.text(0.01, 99.2, "99 % target", fontsize=8, color="0.4")
    ax.set_xlabel("cloud congestion level"); ax.set_ylabel(f"deadline compliance (% <= {DEADLINE:.0f} ms)")
    ax.set_title("Figure 2 - compliance vs congestion"); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(FIG_DIR, "fig2_compliance_vs_congestion.png"), dpi=140); plt.close(fig)

    # ---- where does the cloud stop being compliant? (first level below target)
    for target in (99.0, 95.0):
        ok = [lv for lv, c in zip(levels, c_comp) if c >= target]
        print(f"\ncloud stays >= {target:.0f}% compliant up to congestion = {max(ok) if ok else 'never (even at 0)'}")

    # ---- sensitivity to deadline
    print("\nDeadline sensitivity at baseline congestion (compliance %)")
    print(f"{'deadline':>9}{'edge':>8}{'cloud':>8}{'hybrid':>8}")
    for dl in (60, 80, 100, 150, 200):
        print(f"{dl:>8}ms{stats(sim['edge'], dl)['compliance']:>8.2f}{stats(sim['cloud'], dl)['compliance']:>8.2f}"
              f"{stats(sim['hybrid'], dl)['compliance']:>8.2f}")
    print("\nFigures -> ./figures   tables -> ./results")


if __name__ == "__main__":
    main()
