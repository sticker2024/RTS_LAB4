#!/usr/bin/env python3
"""Builds RTS_Unit4_Lab_Report.docx from the result files in ../mp4_*/ (run all three simulations first)."""
import csv, glob, os, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, "tools"))
from report_lib import *

def rd(p): return list(csv.DictReader(open(os.path.join(R, p))))
def f(x, n=1): return f"{float(x):.{n}f}"
SH = os.path.join(R, "screenshots"); P1 = "mp4_1_sampling_jitter"; P2 = "mp4_2_multirate_pipeline"; P3 = "mp4_3_edge_vs_cloud"

d = new_doc()
title_page(d, "Real-Time Systems", "Unit 4 - Mini Projects: Lab Report",
           "Mini Project 4.1 Sampling jitter & overruns | 4.2 Multi-rate monitoring pipeline | 4.3 Edge-vs-cloud latency")

# ============================================================ 0. overview
h(d, "1. Overview and how to reproduce")
para(d, "This report covers the three Unit 4 Real-Time Systems mini projects. All three are pure-Python simulations (standard library plus matplotlib); "
        "no hardware or network is needed. Every number, table and figure below was produced by the scripts in the accompanying folder and can be regenerated with one command per project.")
table(d, ["Project", "Script", "Command", "Outputs"],
      [["4.1 Sampling jitter / overruns", "mp4_1_sampling_jitter/rt_sampling_sim.py", "python rt_sampling_sim.py", "figures/ (6 PNG), results/*.csv, console_log.txt"],
       ["4.2 Multi-rate pipeline", "mp4_2_multirate_pipeline/multirate_pipeline.py", "python multirate_pipeline.py", "figures/ (12 PNG), results/*.csv"],
       ["4.3 Edge vs cloud", "mp4_3_edge_vs_cloud/edge_vs_cloud.py", "python edge_vs_cloud.py", "figures/ (2 PNG), results/*.csv"]],
      widths=[1.5, 2.2, 1.5, 1.6], size=8.5, caption="Table 1 - Project files")
para(d, "Environment: Python 3.12, matplotlib 3.11. All random processes use fixed seeds, so results are reproducible. "
        "The console 'screenshots' in this report are images rendered from the real captured console output of each run (see tools/make_screenshots.py); "
        "replace them with genuine OS screenshots if your instructor requires that.", italic=True, size=10)

# ============================================================ 4.1
h(d, "2. Mini Project 4.1 - Sampling jitter and processing overruns")
h(d, "2.1 Objective", 2)
para(d, "Build a simulation of a fixed-period sensing-and-control loop (Section 4.1 timing budget, Section 4.5 PLC scan cycle), inject sampling jitter and processing overruns, "
        "and measure how they distort the sampled signal and delay a threshold controller compared with an ideal loop.")
h(d, "2.2 Method (mapping to the procedure)", 2)
table(d, ["Manual step", "Implementation in rt_sampling_sim.py"],
      [["1-2 signal, T_nominal, N", "true_signal(t) = sin (period 2 s) + two small sinusoids as 'continuous noise'; T = 50 ms (20 Hz), run 20 s, N = 400 scheduled samples"],
       ["3 ideal baseline", "ideal_run(): t_k = k*T, constant computation time 0.1 T"],
       ["4 jitter", "actual start = k*T + jitter_k, jitter_k = random.uniform(-J, J), J = 10 / 30 / 50 % of T"],
       ["5 overruns", "c_k ~ U(0.05T, 0.15T) normally; with probability p, c_k ~ U(1.2T, 3.0T) (a WCET violation)"],
       ["6 event loop", "running clock 'free'; if a tick is due while the previous cycle still runs it starts late, extra ticks inside the overrun are lost (like an overrunning PLC scan)"],
       ["7 controller", "threshold 0.5, rising crossing; actuation issued when the computation for that sample ends"],
       ["8 statistics", "mean/std of inter-sample interval, max overrun, % cycles missing the period (c_k > T), dropped ticks"],
       ["9 control quality", "each ideal actuation matched to the nearest jittered actuation (+-1 s) -> delay"],
       ["10-11 figures", "Figure 1 (signal + samples, interval error), Figure 2 (actuation instants + mean/max delay)"],
       ["12 sweep", "3 jitter bounds x 3 overrun probabilities, mean of 200 seeds"]],
      widths=[1.5, 5.3], size=8.5, caption="Table 2 - Procedure-to-code mapping")
h(d, "2.3 Results", 2)
figure(d, os.path.join(SH, "mp4_1_console_run.png"), "Screenshot 1 - console output of rt_sampling_sim.py (sanity check, figure configurations, sweep)", 6.5)
para(d, "Sanity check: with J = 0 and p = 0 all 10 threshold crossings match the baseline and the actuation difference is only 1.5 ms on average (2.4 ms max), caused solely by the random 5-15 % computation time versus the ideal constant 10 %. The implementation is therefore correct.")
for tag, lab, extra in (("A_jitter_only", "A - jitter only (J = 30 % of T, p = 0)", ""),
                        ("B_overrun_only", "B - overruns only (J = 0, p = 10 %)", ""),
                        ("C_combined", "C - combined (J = 30 % of T, p = 10 %)", "")):
    figure(d, os.path.join(R, P1, "figures", f"fig1_{tag}.png"), f"Figure 1 ({lab}) - true signal with ideal and actual sample points (top, first 6 s); per-cycle interval error (bottom)", 6.2)
    figure(d, os.path.join(R, P1, "figures", f"fig2_{tag}.png"), f"Figure 2 ({lab}) - actuation instants of the ideal and the degraded controller", 6.2)
sw = rd(P1 + "/results/sweep_grid.csv")
table(d, ["Jitter J", "Overrun p", "std dt (ms)", "max overrun (ms)", "cycles c>T (%)", "dt>1.5T (%)", "dropped ticks", "mean |delay| (ms)", "max |delay| (ms)", "P-rule RMS err"],
      [[f"{int(float(r['jitter_frac_T'])*100)} % T", f"{int(float(r['p_overrun'])*100)} %", f(r["std_interval_ms"]), f(r["max_overrun_ms"]), f(r["missed_period_pct"]), f(r["gt15T_pct"]),
        f(r["dropped_ticks"]), f(r["mean_abs_delay_ms"]), f(abs(float(r["max_delay_ms"]))), f(r["P_rms_err"], 4)] for r in sw],
      widths=[0.6, 0.6, 0.65, 0.7, 0.7, 0.65, 0.65, 0.7, 0.7, 0.7], size=8, caption="Table 3 - Configuration sweep (Monte-Carlo mean of 200 seeds, T = 50 ms)")
h(d, "2.4 Lab tasks", 2)
lt = rd(P1 + "/results/labtask1_equal_disturbance.csv")
rows = []
for r in sorted(lt, key=lambda r: (float(r["d_over_T"]), r["kind"] != "jitter")):
    rows.append([f"{float(r['d_over_T']):.2f} T", "jitter-only" if r["kind"] == "jitter" else f"overrun-only (p={float(r['p'])*100:.1f} %)",
                 f(r["std_interval_ms"]), f(r["mean_delay_ms"], 2), f(abs(float(r["max_delay_ms"]))), f(r["P_rms_err"], 4)])
table(d, ["Mean disturbance d", "hazard", "std dt (ms)", "mean signed delay (ms)", "max |delay| (ms)", "P-rule RMS err"], rows,
      widths=[1.0, 1.9, 0.8, 1.1, 0.9, 0.9], size=8.5, caption="Table 4 - Lab task 1: jitter vs overrun at equal average timing disturbance")
bullets(d, [("Task 1. ", "At equal mean disturbance, overruns do more damage: e.g. at d = 0.10 T the threshold controller's mean signed delay is +14.0 ms for overruns versus 0.09 ms for jitter (jitter averages out), the worst single delay is 85 ms versus 0.6 ms, and the P-rule output error is 2.4 times larger (0.087 vs 0.036)."),
            ("Task 2 (P-type rule). ", "Replacing the threshold rule by u = Kp(0 - y) with zero-order hold, the RMS output error versus the ideal loop is 0.044 (jitter 30 % T), 0.092 (overruns 10 %) and 0.098 (combined). The continuous rule is more sensitive than the threshold rule because every late or lost sample changes the output, not only the crossings; the ranking of hazards is unchanged."),
            ("Task 3 (compliance metric). ", "Percentage of intervals > 1.5 T versus interval std: jitter J = 50 % T gives std 20.4 ms and 12.5 % > 1.5 T, overruns p = 10 % give std 20.9 ms and 8.3 % > 1.5 T with an 18.5 ms vs 15.8 ms mean |delay|. The std cannot tell symmetric jitter from one-sided lateness, whereas the 1.5 T metric counts only long intervals; for an embedded system with deadlines the compliance metric (together with the maximum) is more useful, though it can also flag harmless jitter."),
            ("Task 4 (halve T). ", "Holding jitter at 15 ms and the overrun duration fixed, halving T from 50 to 25 ms doubles relative jitter (std 12.2 ms = 24 % of T becomes 12.0 ms = 48 % of T) and raises intervals > 1.5 T from 1.3 % to 16.8 %; the overrun-only case drops 170 instead of 23 ticks. Faster sampling is only beneficial if timing precision improves with it - the same lesson as the sampling-regularity discussion of Section 4.7 (patient monitors).")])
figure(d, os.path.join(SH, "mp4_1_console_labtasks.png"), "Screenshot 2 - console output for lab tasks 1-4", 6.5)
h(d, "2.5 Observations versus the expected behaviour", 2)
bullets(d, ["J = 0, p = 0 reproduces the baseline (confirmed).",
            "Jitter scatters samples symmetrically; the mean actuation delay stays near zero even though individual delays reach about +-20 ms (Table 4, d = 0.20 T).",
            "Overruns give a persistent, one-directional (always late) delay and lost ticks - 5-37 dropped ticks per 400 in Table 3.",
            "At high overrun probability crossings are detected a full cycle or more late; none were missed outright here because the signal is slow (10 samples per period) and the match window is half a signal period."])
h(d, "2.6 Summary (Sections 4.1 and 4.5)", 2)
s41 = ("Section 4.1 splits a loop deadline into a timing budget whose computation share must survive worst-case execution time, not typical behaviour. The simulation shows why. "
       "Jitter alone (J = 30 % of the 50 ms period) widened the interval standard deviation to about 12 ms, yet the controller's mean actuation delay remained near zero because early and late samples cancel, and the worst single delay was only about 14 to 20 ms. "
       "Overruns, the WCET violation, behaved differently: with 10 % of cycles overrunning, the interval std rose to roughly 21 ms, the mean absolute actuation delay to about 18 ms, individual delays reached 85 to 150 ms, and 20 to 30 ticks per run were lost. "
       "At equal average disturbance the overrun-only loop produced a P-rule output error 2.4 times that of the jitter-only loop. This matches the scan-cycle argument of Section 4.5: a PLC's stability margin depends on a short and consistent scan, and one long scan delays the next cycle, so the lateness is one-directional and cannot average out. "
       "Combining both effects (configuration C) was slightly worse than overruns alone for the P-type rule (0.098 versus 0.092), confirming that the two hazards add. "
       "The compliance metric (intervals above 1.5 T) and the maximum overrun are better design indicators than the standard deviation, because deadlines are one-sided. "
       "Overruns were therefore the more damaging hazard, and the practical consequence is to bound worst-case computation time (static WCET analysis, priorities, watchdogs) before spending effort on reducing interrupt jitter.")
para(d, s41); assert 200 <= words(s41) <= 400, words(s41)
para(d, f"(Summary length: {words(s41)} words.)", italic=True, size=9)

# ============================================================ 4.2
d.add_page_break()
h(d, "3. Mini Project 4.2 - Multi-rate environmental monitoring pipeline")
h(d, "3.1 Objective and design", 2)
para(d, "A single gateway loop services several simulated sensors with different required sampling periods, decides which due stream to read next with a documented rule, "
        "injects long-tailed processing times, raises threshold alerts and reports timing compliance per stream.")
table(d, ["Stream", "Required period", "Typical read time", "Alert threshold", "Notes"],
      [["temperature", "0.5 s", "30 ms", "26 degC", "slow sine + 1.7 s ripple"],
       ["humidity", "1.3 s", "45 ms", "60 %RH", "non-harmonic with the others"],
       ["air_quality", "3.0 s", "140 ms", "65 AQI", "slow sensor, expensive read"],
       ["vibration (4th stream)", "0.1 s", "18 ms", "1.4 mm/s", "added in the heavy-load configuration"]],
      widths=[1.5, 1.2, 1.2, 1.1, 1.8], size=8.5, caption="Table 5 - Streams (periods differ by at least a factor of two)")
bullets(d, [("Processing time: ", "0.7-1.3 x typical, but with 5 % probability an overrun of 4-10 x typical (long tail)."),
            ("Scheduling rules compared: ", "FP = fixed priority, shortest period first; EDF = earliest deadline (release + period) first; RR = round-robin over streams with a pending job. The gateway is non-preemptive: a read in progress always completes."),
            ("Classification: ", "lateness = service start - release. On-time if <= 10 % of the period; late if served after that but before the next release; missed if the next release arrives first (the old sample is dropped)."),
            ("Alerts: ", "a rising crossing between two consecutive served samples raises the alert; alert latency = detection time - true (analytically bisected) crossing time."),
            ("Link to Section 4.2: ", "like CAN arbitration the highest-priority pending message goes first, and the worst-case wait of any message is bounded by the longest non-preemptible frame (here: the longest read).")])
h(d, "3.2 Results (seed 11, 60 s simulated)", 2)
figure(d, os.path.join(SH, "mp4_2_console_run.png"), "Screenshot 3 - console report: FP and RR with three streams", 6.4)
figure(d, os.path.join(SH, "mp4_2_console_4streams.png"), "Screenshot 4 - console report: FP and RR with four streams (gateway utilisation about 40 %)", 6.4)
rs = rd(P2 + "/results/compliance_single_seed.csv")
for rule, ns in (("FP", "3"), ("RR", "3"), ("FP", "4"), ("RR", "4")):
    sub = [r for r in rs if r["rule"] == rule and r["streams"] == ns]
    table(d, ["stream", "period (s)", "required", "on-time", "late", "missed", "on-time %", "mean overrun (ms)", "max overrun (ms)", "mean alert latency (ms)"],
          [[r["stream"], r["period"], r["required"], r["on_time"], r["late"], r["missed"], f(r["on_time_pct"]), f(r["mean_overrun_ms"]), f(r["max_overrun_ms"]), f(r["mean_alert_latency_ms"])] for r in sub],
          widths=[1.0, 0.6, 0.65, 0.6, 0.45, 0.55, 0.65, 0.8, 0.8, 0.9], size=8,
          caption=f"Table - compliance report, {rule} scheduling, {ns} streams (utilisation {float(sub[0]['util'])*100:.1f} %). EDF output is identical to FP here and is in results/.")
for tag, lab in (("FP_3streams", "FP, 3 streams"), ("RR_3streams", "RR, 3 streams"), ("FP_4streams", "FP, 4 streams"), ("RR_4streams", "RR, 4 streams")):
    figure(d, os.path.join(R, P2, "figures", f"signals_{tag}.png"), f"Figure - true signal, threshold, serviced samples, late (orange) and missed (red) samples - {lab}", 6.3)
    figure(d, os.path.join(R, P2, "figures", f"compliance_{tag}.png"), f"Figure - on-time / late / missed counts per stream - {lab}", 4.6)
mc = rd(P2 + "/results/compliance_monte_carlo.csv")
names = ["temperature", "humidity", "air_quality", "vibration"]
rows = []
for rule in ("FP", "EDF", "RR"):
    for ns in ("3", "4"):
        line = [rule, ns]
        for n in names:
            m = [r for r in mc if r["rule"] == rule and r["streams"] == ns and r["stream"] == n]
            line.append(f(m[0]["mean_on_time_pct"]) if m else "-")
        rows.append(line)
table(d, ["rule", "streams"] + names, rows, widths=[0.7, 0.8, 1.2, 1.2, 1.2, 1.2], size=9,
      caption="Table 6 - Mean on-time % per stream over 100 random seeds")
figure(d, os.path.join(SH, "mp4_2_console_montecarlo.png"), "Screenshot 5 - Monte-Carlo comparison", 5.2)
h(d, "3.3 Report (Sections 4.1 and 4.2)", 2)
r42 = ("The documented rule is non-preemptive fixed priority: whenever the gateway is idle it reads the pending stream with the shortest required period, so the fastest sensor behaves like the highest-priority CAN identifier of Section 4.2. "
       "Earliest-deadline-first (deadline = release + period) and round-robin were compared against it. With three streams the load is light (18 % utilisation) and FP gives temperature 98.3 %, humidity 100 % and air quality 100 % on-time, while round-robin degrades temperature, the fastest stream, to 77.5 % because it keeps waiting behind the slow 140 ms air-quality reads. "
       "Adding a fourth, very fast vibration stream raises utilisation to about 41 % and shows the real cost of sharing one loop. Under FP vibration is on time 84.8 % of the time (55 late, 36 missed) and the three slower streams fall to 87.5 to 91.5 %, because a tail overrun of one read blocks everything behind it. "
       "Under round-robin the slower streams recover to 98 to 100 % but vibration collapses to 65.3 % (169 late, 39 missed). Over 100 seeds the same pattern holds: vibration on-time is 86.1 % under FP and only 63.5 % under round-robin. The stream that suffered most is therefore the fastest one, and which stream suffers is a policy choice. "
       "EDF behaved almost identically to FP because deadlines are one period after release, so deadline order equals period order unless a backlog exceeds the difference between periods, which happens rarely at this load. "
       "Alert latency is bounded by the sampling period plus queueing: vibration alerts were detected within about 45 ms of the true crossing, humidity within about 0.5 s and air quality within about 2 s. "
       "The Section 4.1 lesson is that the timing budget must be allocated per stream against worst-case read time: a 5 % tail of 4 to 10 times longer reads, not the average, determines late and missed samples. "
       "As in CAN, bounded worst-case latency comes from priority plus a bound on the longest non-preemptible unit; shortening or splitting the slow air-quality read would help every other stream more than any scheduling rule.")
para(d, r42); assert 300 <= words(r42) <= 500, words(r42)
para(d, f"(Report length: {words(r42)} words.)", italic=True, size=9)

# ============================================================ 4.3
d.add_page_break()
h(d, "4. Mini Project 4.3 - Edge versus cloud latency simulator")
h(d, "4.1 Objective and model", 2)
para(d, "Compare on-device (edge) and cloud processing for a repeated real-time decision with a 100 ms deadline, 20 000 events, the same event sequence for every architecture. All parameters are assumptions in the PARAMETERS block of the script.")
table(d, ["Path", "Model"],
      [["Edge", "lognormal compute, median 45 ms (easy) / 75 ms (hard decisions, 20 % of events), sigma 0.12; 1 ms bus transport; 0.5 % chance of a 20-40 ms hiccup"],
       ["Cloud", "upload leg + remote compute (median 6 ms) + download leg; each leg lognormal, median 20 ms x (1 + congestion); with probability 0.2 x congestion a leg also gets a Pareto spike (alpha 1.6, xm 40 ms) - a genuinely long tail"],
       ["Hybrid", "easy decisions on the edge; hard decisions pass an 8 ms edge gate and then escalate to the cloud (bigger model, higher accuracy)"],
       ["Accuracy proxy", "edge 99 % / 85 % (easy / hard), cloud 99 % / 98 % - used only for the 'on-time and correct' column"]],
      widths=[1.0, 5.8], size=8.5, caption="Table 7 - Latency models")
h(d, "4.2 Results", 2)
figure(d, os.path.join(SH, "mp4_3_console_run.png"), "Screenshot 6 - console output of edge_vs_cloud.py", 5.6)
rt = rd(P3 + "/results/results_table.csv")
table(d, ["Path", "mean (ms)", "p95 (ms)", "p99 (ms)", "worst (ms)", "deadline met (%)", "on-time and correct (%)"],
      [[r["path"], f(r["mean"]), f(r["p95"]), f(r["p99"]), f(r["worst"]), f(r["compliance"], 2), f(r["ontime_correct"], 2)] for r in rt],
      widths=[0.9, 0.9, 0.9, 0.9, 0.9, 1.1, 1.3], size=9, caption="Table 8 - Results at baseline congestion 0.30 (deadline 100 ms)")
figure(d, os.path.join(R, P3, "figures", "fig1_latency_distributions.png"), "Figure 1 - overlaid latency histograms (a) and empirical CDFs (b) with the deadline marked", 6.5)
figure(d, os.path.join(R, P3, "figures", "fig2_compliance_vs_congestion.png"), "Figure 2 - deadline compliance versus cloud congestion; edge shown as a flat reference", 5.0)
sw3 = rd(P3 + "/results/congestion_sweep.csv")
table(d, ["congestion", "cloud met (%)", "cloud p99 (ms)", "edge met (%)", "hybrid met (%)"],
      [[r["congestion"], f(r["cloud"], 2), f(r["cloud_p99"]), f(r["edge"], 2), f(r["hybrid"], 2)] for r in sw3 if round(float(r["congestion"]) * 20) % 2 == 0],
      widths=[1.0, 1.2, 1.2, 1.2, 1.2], size=9, caption="Table 9 - Congestion sweep (8 000 events per level)")
h(d, "4.3 Report (Sections 4.8 and 4.9)", 2)
r43 = ("With a 100 ms deadline the edge path met the deadline for about 99.7 % of decisions at every congestion level: its easy decisions never missed and only the heavier decisions on the limited local CPU occasionally did (p99 93 ms, worst 127 ms). "
       "The cloud path is only deadline-compliant when the network is essentially uncongested. At congestion 0 it met 100 %, but at 0.05 it already dropped to 98.9 % with p99 above 100 ms, it stayed above 95 % only up to a congestion of about 0.15, and at the baseline of 0.30 it met just 89.4 %. At full congestion it met only half of the deadlines. "
       "The reason is the tail, not the average: at baseline the cloud's mean latency of 71 ms looks comfortable, yet the p99 is 260 ms and the worst case 1.6 s because rare congestion spikes are heavy tailed. "
       "This is exactly the Section 4.8 URLLC argument that a real-time link must give bounded, deterministic latency with a very high reliability target; a good mean says nothing about whether the 99.9th percentile fits the budget. "
       "Relaxing the deadline helps the cloud only slowly: at 200 ms it still met just 98.2 %, whereas at a tight 60 ms edge and hybrid are far better than the cloud (78.9 % and 82.3 % versus 48.1 %). "
       "This supports the Section 4.9 rationale for edge computing: processing near the sensor removes the uplink, the shared network and the remote queue from the end-to-end budget, leaving only a short, low-variance path. "
       "The hybrid policy shows the trade-off. Keeping easy decisions local and escalating the hard 20 % to the cloud gave 97.6 % deadline compliance (between edge and cloud), but the best on-time and correct rate, 96.4 % versus 95.8 % for pure edge, because the cloud's larger model is more accurate on hard cases. "
       "Hybrid is therefore appropriate when decision quality matters and a fallback to the local result is defined for late cloud answers; for safety-critical actions within 100 ms the edge path should own the deadline.")
para(d, r43); assert 300 <= words(r43) <= 500, words(r43)
para(d, f"(Report length: {words(r43)} words.)", italic=True, size=9)

# ============================================================ conclusions + appendix
h(d, "5. Conclusions")
bullets(d, ["Timing hazards must be judged by their worst case and by direction: overruns (one-sided, accumulating lateness) damage control far more than symmetric jitter of the same average size.",
            "In a shared non-preemptive loop, scheduling decides who pays for the tail overruns; priority protects the fast stream at the expense of the slow ones, round-robin does the reverse.",
            "Latency budgets are decided by tail percentiles, not means; edge processing keeps the tail short, the cloud offers accuracy but cannot guarantee a tight deadline under congestion."])
h(d, "Appendix A - Deliverables checklist", 1)
table(d, ["Requirement", "Where"],
      [["4.1 rt_sampling_sim.py, 2 figures x 3 configs, stats table, 200-400 word summary", "mp4_1_sampling_jitter/ ; Sections 2.3-2.6"],
       ["4.2 source, compliance report x2+ configs, 2 figures per config, 300-500 word report", "mp4_2_multirate_pipeline/ ; Section 3 (6 configurations)"],
       ["4.3 source with hybrid, results table, 2 figures, 300-500 word report", "mp4_3_edge_vs_cloud/ ; Section 4"]],
      widths=[4.3, 2.5], size=9)
d.add_page_break()
h(d, "Appendix B - Source code", 1)
for sub, fn in ((P1, "rt_sampling_sim.py"), (P2, "multirate_pipeline.py"), (P3, "edge_vs_cloud.py")):
    h(d, f"{sub}/{fn}", 2)
    code_block(d, open(os.path.join(R, sub, fn)).read())
    d.add_page_break()
out = os.path.join(R, "report", "RTS_Unit4_Lab_Report.docx")
d.save(out); print("saved", out)
