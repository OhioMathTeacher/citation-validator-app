#!/usr/bin/env python3
"""
Compare benchmark runs from the experiment log.

Usage:
    python scripts/compare_runs.py
    python scripts/compare_runs.py --last 5
    python scripts/compare_runs.py --dataset ansari100
    python scripts/compare_runs.py --provider gemini groq
"""

import argparse
import json
import sys
from pathlib import Path


def load_runs(log_path, dataset_filter=None, provider_filter=None, last_n=None):
    """Load runs from JSONL, optionally filtered."""
    if not log_path.exists():
        print(f"No experiment log found at {log_path}")
        print("Run a benchmark first: python scripts/run_benchmark.py --dataset ansari100 --provider gemini")
        sys.exit(1)

    runs = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            run = json.loads(line)
            if dataset_filter and run.get("dataset_id") not in dataset_filter:
                continue
            if provider_filter:
                p = run.get("ai_provider") or "no-ai"
                if p not in provider_filter:
                    continue
            runs.append(run)

    if last_n:
        runs = runs[-last_n:]
    return runs


def print_comparison_table(runs):
    """Print a table comparing runs."""
    if not runs:
        print("No matching runs found.")
        return

    # Header
    print(f"\n{'='*100}")
    print(f"  EXPERIMENT COMPARISON ({len(runs)} runs)")
    print(f"{'='*100}\n")

    # Column widths
    cols = {
        "Timestamp": 20,
        "Dataset": 22,
        "Provider": 14,
        "Citations": 9,
        "Accuracy": 9,
        "F1": 7,
        "TP": 4,
        "TN": 4,
        "FP": 4,
        "FN": 4,
        "Time": 7,
    }

    header = "  ".join(f"{k:<{v}}" for k, v in cols.items())
    separator = "  ".join("-" * v for v in cols.values())
    print(f"  {header}")
    print(f"  {separator}")

    for run in runs:
        ts = run.get("timestamp", "?")[:19].replace("T", " ")
        ds = run.get("dataset_id", "?")[:22]
        provider = run.get("ai_provider") or "no-ai"
        n = run.get("citation_count", "?")
        acc = run.get("accuracy")
        acc_str = f"{acc['accuracy']*100:.1f}%" if acc else "N/A"
        f1_str = f"{acc['f1']*100:.1f}%" if acc else "N/A"
        tp = acc["tp"] if acc else "-"
        tn = acc["tn"] if acc else "-"
        fp = acc["fp"] if acc else "-"
        fn = acc["fn"] if acc else "-"
        time_s = f"{run.get('total_seconds', 0):.0f}s"

        row_data = [
            f"{ts:<{cols['Timestamp']}}",
            f"{ds:<{cols['Dataset']}}",
            f"{provider:<{cols['Provider']}}",
            f"{str(n):<{cols['Citations']}}",
            f"{acc_str:<{cols['Accuracy']}}",
            f"{f1_str:<{cols['F1']}}",
            f"{str(tp):<{cols['TP']}}",
            f"{str(tn):<{cols['TN']}}",
            f"{str(fp):<{cols['FP']}}",
            f"{str(fn):<{cols['FN']}}",
            f"{time_s:<{cols['Time']}}",
        ]
        print(f"  {'  '.join(row_data)}")

    print()

    # Summary: group by provider for same dataset
    datasets = set(r.get("dataset_id") for r in runs)
    if len(datasets) == 1:
        print_provider_comparison(runs)
    else:
        print_dataset_summary(runs)


def print_provider_comparison(runs):
    """When comparing multiple providers on the same dataset."""
    by_provider = {}
    for run in runs:
        p = run.get("ai_provider") or "no-ai"
        if p not in by_provider:
            by_provider[p] = []
        by_provider[p].append(run)

    if len(by_provider) <= 1:
        return

    print(f"  Provider Comparison:")
    print(f"  {'-'*50}")
    for provider, provider_runs in sorted(by_provider.items()):
        # Use the latest run for each provider
        latest = provider_runs[-1]
        acc = latest.get("accuracy")
        if acc:
            print(f"  {provider:<15} Accuracy: {acc['accuracy']*100:.1f}%  "
                  f"F1: {acc['f1']*100:.1f}%  "
                  f"FN: {acc['fn']}  FP: {acc['fp']}  "
                  f"Time: {latest.get('total_seconds', 0):.0f}s")
        else:
            print(f"  {provider:<15} No accuracy data")
    print()


def print_dataset_summary(runs):
    """When comparing multiple datasets."""
    by_ds = {}
    for run in runs:
        ds = run.get("dataset_id", "?")
        if ds not in by_ds:
            by_ds[ds] = []
        by_ds[ds].append(run)

    print(f"  Dataset Summary:")
    print(f"  {'-'*50}")
    for ds, ds_runs in sorted(by_ds.items()):
        accuracies = [r["accuracy"]["accuracy"] for r in ds_runs if r.get("accuracy")]
        if accuracies:
            avg = sum(accuracies) / len(accuracies)
            best = max(accuracies)
            print(f"  {ds:<25} Runs: {len(ds_runs)}  "
                  f"Avg: {avg*100:.1f}%  Best: {best*100:.1f}%")
        else:
            print(f"  {ds:<25} Runs: {len(ds_runs)}  No accuracy data")
    print()


def main():
    parser = argparse.ArgumentParser(description="Compare benchmark experiment runs.")
    parser.add_argument("--log", default="results/experiments/experiment_log.jsonl",
                        help="Path to experiment log")
    parser.add_argument("--last", "-n", type=int, help="Show last N runs")
    parser.add_argument("--dataset", "-d", nargs="+", help="Filter by dataset ID(s)")
    parser.add_argument("--provider", "-p", nargs="+", help="Filter by provider(s)")

    args = parser.parse_args()
    log_path = Path(args.log)

    runs = load_runs(log_path, args.dataset, args.provider, args.last)
    print_comparison_table(runs)


if __name__ == "__main__":
    main()
