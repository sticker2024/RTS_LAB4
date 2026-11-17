# Real-Time Systems - Unit 4 Mini Projects (code + lab report)

```
report/RTS_Unit4_Lab_Report.docx   <- the lab report (PDF copy alongside), all figures and screenshots embedded
mp4_1_sampling_jitter/             rt_sampling_sim.py   -> figures/, results/
mp4_2_multirate_pipeline/          multirate_pipeline.py -> figures/, results/
mp4_3_edge_vs_cloud/               edge_vs_cloud.py     -> figures/, results/
screenshots/                       console screenshots used in the report
tools/                             make_screenshots.py, term_shot.py, report_lib.py
```

## Run (Python 3.10+)
```
pip install -r requirements.txt
cd mp4_1_sampling_jitter   && python rt_sampling_sim.py          # add --quick for fewer Monte-Carlo seeds
cd mp4_2_multirate_pipeline && python multirate_pipeline.py
cd mp4_3_edge_vs_cloud     && python edge_vs_cloud.py
python tools/make_screenshots.py && python report/build_report.py   # rebuild screenshots + report
```
All random processes are seeded: re-running reproduces the numbers in the report.

## Things to know
* Every latency / timing parameter (computation times, congestion spike model, accuracy proxy) is an *assumption*
  documented at the top of each script. Change them and re-run if your manual specifies other values.
* The console "screenshots" are images rendered from the real captured console logs, not OS screen grabs.
* Fill in your name / ID on the report's title page.
