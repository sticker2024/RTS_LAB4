"""Builds terminal-style screenshots of the real console logs -> ../screenshots/"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from term_shot import render
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(R, "screenshots"); os.makedirs(OUT, exist_ok=True)

def lines(path):
    return open(os.path.join(R, path)).read().split("\n")

def shot(name, title, body, size=13, width=None):
    render("\n".join(body), os.path.join(OUT, name), title, size=size, width_chars=width)

l = lines("mp4_1_sampling_jitter/results/console_log.txt")
shot("mp4_1_console_run.png", "$ python rt_sampling_sim.py   (Mini Project 4.1: header, sanity check, figure configs, sweep)",
     ["$ python rt_sampling_sim.py"] + l[:27], size=12, width=150)
shot("mp4_1_console_labtasks.png", "Mini Project 4.1 - lab tasks 1-4 output", l[27:], size=12, width=150)
m = lines("mp4_2_multirate_pipeline/results/console_log.txt")
blocks = open(os.path.join(R, "mp4_2_multirate_pipeline/results/console_log.txt")).read().strip().split("\n\n")
shot("mp4_2_console_run.png", "$ python multirate_pipeline.py   (header + FP/3 streams + RR/3 streams)",
     ["$ python multirate_pipeline.py"] + blocks[0].split("\n") + [""] + blocks[1].split("\n") + [""] + blocks[3].split("\n"), size=12, width=140)
shot("mp4_2_console_4streams.png", "Mini Project 4.2 - four-stream load: FP vs RR",
     blocks[4].split("\n") + [""] + blocks[6].split("\n"), size=12, width=140)
shot("mp4_2_console_montecarlo.png", "Mini Project 4.2 - Monte-Carlo comparison over 100 seeds", blocks[7].split("\n"), size=13)
e = lines("mp4_3_edge_vs_cloud/results/console_log.txt")
shot("mp4_3_console_run.png", "$ python edge_vs_cloud.py", ["$ python edge_vs_cloud.py"] + e, size=13, width=120)
print("RTS screenshots done")
