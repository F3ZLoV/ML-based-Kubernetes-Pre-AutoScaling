# `paper_dataset/` — the 84 runs reported in the paper

*Evaluating Predictive Autoscaling Models Across Kubernetes Traffic Archetypes* (JKSCI)

Every number in Tables 4–12 and Figures 2–9 comes from the files in this directory.
The rest of `results/` is working material: earlier zip bundles, per-week scratch output,
and a discarded 2-node batch. **Use this directory, not those.**

---

## Layout

84 runs = **7 scenarios × 4 scalers × 3 repetitions**. One flat directory, three files per run:

```
<scenario>__<model>__run<N>__lead_time.csv
<scenario>__<model>__run<N>__stats.csv
<scenario>__<model>__run<N>__stats_history.csv
```

`scenario ∈ {aws_spike, alibaba_spike, alibaba_periodic, alibaba_wiki, general_spike, step, ramp}`
`model ∈ {hpa, lstm, gru, ensemble}` · `N ∈ {1, 2, 3}`

`manifest.csv` lists all 84 runs with the original path each file was collected from.

### `*__lead_time.csv`

Emitted live by `scripts/lead_time_tracker_v2.py`, one row per scaling event.

| column | meaning |
|---|---|
| `timestamp` | ISO-8601, local time of the observation |
| `model`, `scenario`, `run` | run identity |
| `event_type` | `scale_out` · `scale_down` · `scale_out_partial` |
| `from_replicas` | ready replica count immediately before the event |
| `to_replicas` | ready replica count at completion |
| `lead_time_sec` | Section III.5 lead time (`scale_out` rows only; `0` on `scale_down`) |

`scale_out_partial` marks a scale-out whose target was revised downward mid-flight.
There is exactly **one** such row across all 84 runs, and it is excluded from every mean.

### `*__stats.csv` / `*__stats_history.csv`

Locust CSV output. Read the `Aggregated` row of `*__stats.csv` for the P95 (`95%`),
P99 (`99%`), `Request Count` and `Failure Count` used in Tables 5–7.
`*__stats_history.csv` carries the per-interval `User Count` and `Requests/s` series used
for the safety-guard branch analysis in Section III.4.

---

## Which files back which table

| Paper | Scenario key | Source of the numbers |
|---|---|---|
| Table 4, row *AWS spike* | `aws_spike` | `lead_time`, AWS-trained models |
| Table 4, row *Alibaba spike* | `alibaba_spike` | `lead_time`, same load shape, Alibaba-retrained models |
| Table 4, row *Alibaba periodic* | `alibaba_periodic` | `lead_time` |
| Table 4, row *Alibaba wiki* | `alibaba_wiki` | `lead_time` |
| Table 4, row *Alibaba gen-spike* | `general_spike` | `lead_time` |
| Table 4, row *Alibaba step* | `step` | `lead_time` |
| Table 4, row *Alibaba ramp* | `ramp` | `lead_time` |
| Tables 5, 6, 7 | `general_spike`, `step`, `ramp` | `lead_time` + `stats` |
| Table 9 (Time-to-Peak) | same three | `lead_time` timestamps |
| Table 10 (Aggressiveness) | same three | `lead_time` replica deltas |
| Table 11 (environment control) | `alibaba_wiki` (uncontrolled) vs `ramp` (controlled) | `lead_time` |
| Table 12 (training-data sensitivity) | `aws_spike` vs `alibaba_spike` | `lead_time` |
| Section III.4 branch shares | all seven | `stats_history` |

`aws_spike` and `alibaba_spike` were driven by the **same** `loadtest/locustfile_spike.py`.
They are two experimental conditions over one load shape; only the model's training dataset
differs. This is what makes the Table 12 comparison possible — and it is also why the HPA
rows of those two conditions (3.08 s vs 3.32 s) give a direct read on run-to-run variability,
since HPA has no model to retrain.

---

## Reproducing Table 4

Standard library only — no pandas needed.

```python
import csv, glob, statistics as st

MODELS = ["hpa", "lstm", "gru", "ensemble"]
SCENARIOS = ["aws_spike", "alibaba_spike", "alibaba_periodic", "alibaba_wiki",
             "general_spike", "step", "ramp"]

for scenario in SCENARIOS:
    row = []
    for model in MODELS:
        events = []
        for path in sorted(glob.glob(f"{scenario}__{model}__run?__lead_time.csv")):
            with open(path, newline="") as fh:
                events += [float(r["lead_time_sec"]) for r in csv.DictReader(fh)
                           if r["event_type"] == "scale_out"]
        row.append(st.mean(events))          # pooled mean, not mean-of-run-means
    print(f"{scenario:18s}" + "  ".join(f"{v:.2f}" for v in row))
```

**The published values are pooled means**: all `scale_out` events of the three runs are
concatenated and averaged once. Averaging each run first and then averaging those three
numbers gives materially different values (e.g. `general_spike` / HPA becomes 4.38 s instead
of 3.52 s), because runs contribute unequal event counts.

---

## Totals

| | |
|---|---|
| Runs | 84 |
| `scale_out` events | 545 |
| `scale_down` events | 366 |
| `scale_out_partial` events | 1 |
| **All scaling events** | **912** |
| `stats_history` samples | 31,477 |

All 84 runs ran on a 3-node DOKS pool (`s-2vcpu-4gb × 3`). A preliminary 2-node spike batch
exists in the working tree under `results/backup_2node/` — it is **not** part of this dataset,
is not reported anywhere in the paper, and is git-ignored.
