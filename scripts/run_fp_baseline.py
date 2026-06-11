#!/usr/bin/env python3
"""
Citation Validation Baseline Runner
====================================
Runs the citation validator directly (no Flask server needed) against
real and fake citation datasets.

Usage:
    python scripts/run_fp_baseline.py                  # Step 1: FP baseline (real citations)
    python scripts/run_fp_baseline.py --step 2         # Step 2: FP root cause analysis
    python scripts/run_fp_baseline.py --step 3         # Step 3: AI comparison (needs Flask)
    python scripts/run_fp_baseline.py --step 4         # Step 4: fake detection (recall test)
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from scripts/
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))


def _git_version():
    """Return short commit hash and date, e.g. '9146f23 (2026-04-10)'."""
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%h (%ci)"],
            cwd=REPO_ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        # Trim timezone offset from commit date for readability
        return re.sub(r"\s+[+-]\d{4}\)$", ")", out)
    except Exception:
        return "unknown"

from citation_validator import CitationValidator

# ── Datasets ────────────────────────────────────────────────────────────────

REAL_DATASETS = [
    {
        "id": "ojsm-real-arxiv",
        "name": "Real arXiv CS Citations (2024)",
        "ground_truth": "valid",
        "bib_files": [
            "test_citations/real_citations/arxiv_cs_2024/arxiv_2604.05875.bib",
            "test_citations/real_citations/arxiv_cs_2024/arxiv_2604.05952.bib",
        ],
    },
    {
        "id": "ojsm-real-crossref",
        "name": "Real CrossRef Random Sample",
        "ground_truth": "valid",
        "bib_files": [
            "test_citations/real_citations/crossref_random/crossref_sample_0001.bib",
            "test_citations/real_citations/crossref_random/crossref_sample_0002.bib",
        ],
    },
    {
        "id": "nature-article-refs",
        "name": "Nature Article References",
        "ground_truth": "valid",
        "bib_files": ["datasets/nature-article/refs.bib"],
    },
]

FAKE_DATASETS = [
    {
        "id": "compound-deception-ansari",
        "name": "Ansari 100 — NeurIPS 2025 Fakes",
        "ground_truth": "invalid",
        "bib_files": ["datasets/compound-deception-ansari/ansari100.bib"],
    },
    {
        "id": "ojsm-fake-frankenstein",
        "name": "Frankenstein Citations (real author + real journal + fake title)",
        "ground_truth": "invalid",
        "bib_files": [
            "test_citations/false_negative_tests/frankenstein/frankenstein_0001.bib",
            "test_citations/false_negative_tests/frankenstein/frankenstein_0002.bib",
        ],
    },
    {
        "id": "ojsm-fake-stolen-doi",
        "name": "Stolen DOI Citations (real DOI + wrong metadata)",
        "ground_truth": "invalid",
        "bib_files": [
            "test_citations/false_negative_tests/stolen_doi/stolen_doi_0001.bib",
            "test_citations/false_negative_tests/stolen_doi/stolen_doi_0002.bib",
        ],
    },
    {
        "id": "ojsm-fake-plausible",
        "name": "Plausible Fakes (entirely fabricated but realistic)",
        "ground_truth": "invalid",
        "bib_files": [
            "test_citations/false_negative_tests/plausible/plausible_0001.bib",
            "test_citations/false_negative_tests/plausible/plausible_0002.bib",
        ],
    },
    {
        "id": "ojsm-fake-nonsense",
        "name": "Nonsense Citations (obviously wrong, sanity check)",
        "ground_truth": "invalid",
        "bib_files": [
            "test_citations/false_negative_tests/nonsense/nonsense_0001.bib",
            "test_citations/false_negative_tests/nonsense/nonsense_0002.bib",
        ],
    },
]

RESULTS_DIR = REPO_ROOT / "results" / "fp-baseline"


# ── Helpers ─────────────────────────────────────────────────────────────────

def load_bibtex(dataset):
    combined = []
    for rel in dataset["bib_files"]:
        path = REPO_ROOT / rel
        if path.exists():
            combined.append(path.read_text())
        else:
            print(f"  WARNING: {path} not found, skipping")
    return "\n\n".join(combined)


def classify_result(citation):
    """Classify a single citation result for the confusion matrix."""
    is_flagged = citation["status"] in ("suspicious", "invalid")
    # All datasets here are ground-truth VALID (real citations).
    # FP = real citation incorrectly flagged.
    # TN = real citation correctly NOT flagged.
    return "fp" if is_flagged else "tn"


def print_bar(label, count, total, char="█"):
    pct = count / total * 100 if total > 0 else 0
    bar_len = int(pct / 2)
    print(f"  {label:>12s}: {count:>4d}/{total}  {char * bar_len} {pct:.1f}%")


# ── Step 1: Deterministic Baseline ──────────────────────────────────────────

def run_step1():
    print("\n" + "=" * 70)
    print("  STEP 1: DETERMINISTIC FALSE-POSITIVE BASELINE")
    print("  Testing real citations — every flag is a false positive.")
    print(f"  Version: {_git_version()}")
    print("=" * 70)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_results = {}

    validator = CitationValidator(verbose=False, use_ai=False)

    for ds in REAL_DATASETS:
        ds_id = ds["id"]
        print(f"\n{'─' * 60}")
        print(f"  Dataset: {ds['name']} ({ds_id})")
        print(f"{'─' * 60}")

        bibtex = load_bibtex(ds)
        entries = validator._parse_bibtex_string(bibtex)
        print(f"  Loaded {len(entries)} citations")

        t0 = time.time()
        details = []
        for i, entry in enumerate(entries, 1):
            result = validator.check_citation(entry)
            details.append(result)
            if i % 25 == 0 or i == len(entries):
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0
                print(f"  [{i}/{len(entries)}] {rate:.1f} cit/s", end="\r")

        elapsed = time.time() - t0
        print(f"  Completed in {elapsed:.1f}s" + " " * 30)

        # Tally
        counts = {"valid": 0, "warning": 0, "suspicious": 0, "invalid": 0}
        fp_details = []
        for d in details:
            counts[d["status"]] = counts.get(d["status"], 0) + 1
            if d["status"] in ("suspicious", "invalid"):
                fp_details.append(d)

        total = len(details)
        tn = counts["valid"] + counts["warning"]  # not flagged
        fp = counts["suspicious"] + counts["invalid"]  # flagged
        fpr = fp / total if total > 0 else 0

        print(f"\n  Results:")
        print_bar("Valid", counts["valid"], total, "█")
        print_bar("Warning", counts["warning"], total, "▒")
        print_bar("Suspicious", counts["suspicious"], total, "░")
        print_bar("Invalid", counts["invalid"], total, "░")
        print(f"\n  FALSE POSITIVE RATE: {fp}/{total} = {fpr*100:.1f}%", end="")
        if fpr <= 0.05:
            print("  <<<  PASS (target < 5%)")
        else:
            print("  <<<  FAIL (target < 5%)")

        # Show FP details
        if fp_details:
            print(f"\n  False positives ({len(fp_details)}):")
            for d in fp_details:
                print(f"    [{d['status'].upper():>10s}] {d['key']}")
                for issue in d.get("issues", []):
                    print(f"      issue:   {issue}")
                for warning in d.get("warnings", []):
                    print(f"      warning: {warning}")

        all_results[ds_id] = {
            "dataset": ds["name"],
            "total": total,
            "counts": counts,
            "fp": fp,
            "tn": tn,
            "fpr": round(fpr, 4),
            "elapsed_seconds": round(elapsed, 1),
            "false_positives": [
                {
                    "key": d["key"],
                    "status": d["status"],
                    "issues": d.get("issues", []),
                    "warnings": d.get("warnings", []),
                    "fields": {k: v[:80] for k, v in d.get("fields", {}).items()},
                }
                for d in fp_details
            ],
        }

    # Summary
    total_all = sum(r["total"] for r in all_results.values())
    fp_all = sum(r["fp"] for r in all_results.values())
    fpr_all = fp_all / total_all if total_all > 0 else 0

    print(f"\n{'=' * 70}")
    print(f"  OVERALL FALSE-POSITIVE RATE: {fp_all}/{total_all} = {fpr_all*100:.1f}%")
    if fpr_all <= 0.05:
        print(f"  STATUS: PASS (target < 5%)")
    else:
        print(f"  STATUS: FAIL (target < 5%)")
    print(f"{'=' * 70}\n")

    # Save
    out_path = RESULTS_DIR / "step1_deterministic.json"
    payload = {
        "step": 1,
        "description": "Deterministic false-positive baseline (no AI)",
        "version": _git_version(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_fpr": round(fpr_all, 4),
        "overall_fp": fp_all,
        "overall_total": total_all,
        "datasets": all_results,
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Results saved to {out_path}")

    return all_results


# ── Step 2: Analyze FP Causes ──────────────────────────────────────────────

def run_step2():
    """Load step 1 results and analyze WHY each false positive was flagged."""
    results_path = RESULTS_DIR / "step1_deterministic.json"
    if not results_path.exists():
        print("ERROR: Run step 1 first.")
        sys.exit(1)

    data = json.loads(results_path.read_text())

    print("\n" + "=" * 70)
    print("  STEP 2: FALSE-POSITIVE ROOT CAUSE ANALYSIS")
    print(f"  Version: {_git_version()}")
    print("=" * 70)

    all_fps = []
    for ds_id, ds_data in data["datasets"].items():
        for fp in ds_data["false_positives"]:
            fp["dataset"] = ds_id
            all_fps.append(fp)

    if not all_fps:
        print("\n  No false positives to analyze! FPR = 0%.")
        print("  Step 2 complete — nothing to fix.\n")
        return

    # Categorize by root cause
    causes = {}
    for fp in all_fps:
        reasons = fp.get("issues", []) + fp.get("warnings", [])
        for reason in reasons:
            # Simplify the reason to a category
            if "DOI" in reason and ("not found" in reason or "Invalid" in reason):
                cat = "DOI_NOT_FOUND"
            elif "OpenAlex" in reason or "not in OpenAlex" in reason:
                cat = "NOT_IN_OPENALEX"
            elif "not found in any database" in reason.lower():
                cat = "NOT_IN_ANY_DB"
            elif "similarity" in reason.lower():
                cat = "LOW_SIMILARITY"
            elif "mismatch" in reason.lower():
                cat = "METADATA_MISMATCH"
            elif "Generic" in reason or "generic" in reason:
                cat = "GENERIC_PATTERN"
            elif "Semantic Scholar" in reason:
                cat = "SEMANTIC_SCHOLAR"
            else:
                cat = "OTHER"

            if cat not in causes:
                causes[cat] = []
            causes[cat].append(fp)

    print(f"\n  Total false positives: {len(all_fps)}")
    print(f"\n  Root cause breakdown:")
    print(f"  {'─' * 50}")
    for cat, fps in sorted(causes.items(), key=lambda x: -len(x[1])):
        print(f"  {cat:<25s} {len(fps):>3d} citations")

    print(f"\n  Detail per false positive:")
    print(f"  {'─' * 50}")
    for fp in all_fps:
        print(f"\n  [{fp['status'].upper()}] {fp['key']}  (dataset: {fp['dataset']})")
        fields = fp.get("fields", {})
        if "title" in fields:
            print(f"    Title:  {fields['title'][:70]}")
        if "doi" in fields:
            print(f"    DOI:    {fields['doi'][:60]}")
        if "author" in fields:
            print(f"    Author: {fields['author'][:60]}")
        for issue in fp.get("issues", []):
            print(f"    ISSUE:   {issue}")
        for warning in fp.get("warnings", []):
            print(f"    WARNING: {warning}")

    # Save analysis
    out_path = RESULTS_DIR / "step2_fp_analysis.json"
    analysis = {
        "step": 2,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_false_positives": len(all_fps),
        "cause_counts": {cat: len(fps) for cat, fps in causes.items()},
        "false_positives": all_fps,
    }
    out_path.write_text(json.dumps(analysis, indent=2))
    print(f"\n  Analysis saved to {out_path}")
    print()


# ── Step 3: Run with AI ───────────────────────────────────────────────────

def run_step3():
    """Re-run false positives from step 1 through AI to see if AI helps or hurts."""
    results_path = RESULTS_DIR / "step1_deterministic.json"
    if not results_path.exists():
        print("ERROR: Run step 1 first.")
        sys.exit(1)

    # Check for API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY environment variable.")
        print("  Get a free key at https://aistudio.google.com/app/apikey")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("  STEP 3: AI ANALYSIS ON FALSE POSITIVES (Gemini 2.5 Flash)")
    print("  Testing whether AI corrects or worsens false positive rate.")
    print(f"  Version: {_git_version()}")
    print("=" * 70)

    # For step 3, we re-validate the datasets that had false positives
    # and apply AI analysis to the flagged citations.
    # We need the Flask server for AI proxy — OR we call Gemini directly.

    print("\n  Step 3 requires the Flask server for AI proxy.")
    print("  Start the server in another terminal:")
    print("    cd Ohio-Journal-of-School-Mathematics && python scripts/webapp.py")
    print("\n  Then re-run:  python scripts/run_fp_baseline.py --step 3")
    print("\n  Alternatively, run benchmarks via:")
    print("    python scripts/run_benchmark.py --dataset ojsm-real-arxiv --provider gemini")
    print("    python scripts/run_benchmark.py --dataset ojsm-real-crossref --provider gemini")
    print()


# ── Step 4: Fake Detection Regression Test ─────────────────────────────────

def run_step4():
    """Run fake-citation datasets to measure detection rate (recall).
    Every fake that is NOT flagged is a false negative."""
    print("\n" + "=" * 70)
    print("  STEP 4: FAKE-CITATION DETECTION (RECALL TEST)")
    print("  Testing fabricated citations — every miss is a false negative.")
    print(f"  Version: {_git_version()}")
    print("=" * 70)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_results = {}

    validator = CitationValidator(verbose=False, use_ai=False)

    for ds in FAKE_DATASETS:
        ds_id = ds["id"]
        print(f"\n{'─' * 60}")
        print(f"  Dataset: {ds['name']} ({ds_id})")
        print(f"{'─' * 60}")

        bibtex = load_bibtex(ds)
        if not bibtex.strip():
            print(f"  WARNING: No bib files found, skipping")
            continue

        entries = validator._parse_bibtex_string(bibtex)
        print(f"  Loaded {len(entries)} citations")

        if not entries:
            print(f"  WARNING: 0 entries parsed, skipping")
            continue

        t0 = time.time()
        details = []
        for i, entry in enumerate(entries, 1):
            result = validator.check_citation(entry)
            details.append(result)
            if i % 25 == 0 or i == len(entries):
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0
                print(f"  [{i}/{len(entries)}] {rate:.1f} cit/s", end="\r")

        elapsed = time.time() - t0
        print(f"  Completed in {elapsed:.1f}s" + " " * 30)

        # Tally — for fakes, flagged = correct (TP), not flagged = miss (FN)
        counts = {"valid": 0, "warning": 0, "suspicious": 0, "invalid": 0}
        fn_details = []
        for d in details:
            counts[d["status"]] = counts.get(d["status"], 0) + 1
            if d["status"] not in ("suspicious", "invalid"):
                fn_details.append(d)

        total = len(details)
        tp = counts["suspicious"] + counts["invalid"]  # correctly flagged
        fn = counts["valid"] + counts["warning"]  # missed
        detection_rate = tp / total if total > 0 else 0

        print(f"\n  Results:")
        print_bar("Valid", counts["valid"], total, "░")
        print_bar("Warning", counts["warning"], total, "░")
        print_bar("Suspicious", counts["suspicious"], total, "█")
        print_bar("Invalid", counts["invalid"], total, "█")
        print(f"\n  DETECTION RATE: {tp}/{total} = {detection_rate*100:.1f}%", end="")
        if detection_rate >= 0.95:
            print("  <<<  PASS (target >= 95%)")
        else:
            print("  <<<  FAIL (target >= 95%)")

        # Show missed fakes
        if fn_details:
            print(f"\n  Missed fakes ({len(fn_details)}):")
            for d in fn_details[:20]:  # Cap display at 20
                print(f"    [{d['status'].upper():>10s}] {d['key']}")
                for issue in d.get("issues", []):
                    print(f"      issue:   {issue}")
                for warning in d.get("warnings", []):
                    print(f"      warning: {warning}")
            if len(fn_details) > 20:
                print(f"    ... and {len(fn_details) - 20} more")

        all_results[ds_id] = {
            "dataset": ds["name"],
            "total": total,
            "counts": counts,
            "tp": tp,
            "fn": fn,
            "detection_rate": round(detection_rate, 4),
            "elapsed_seconds": round(elapsed, 1),
            "false_negatives": [
                {
                    "key": d["key"],
                    "status": d["status"],
                    "issues": d.get("issues", []),
                    "warnings": d.get("warnings", []),
                    "fields": {k: v[:80] for k, v in d.get("fields", {}).items()},
                }
                for d in fn_details
            ],
        }

    # Summary
    total_all = sum(r["total"] for r in all_results.values())
    tp_all = sum(r["tp"] for r in all_results.values())
    fn_all = sum(r["fn"] for r in all_results.values())
    rate_all = tp_all / total_all if total_all > 0 else 0

    print(f"\n{'=' * 70}")
    print(f"  OVERALL DETECTION RATE: {tp_all}/{total_all} = {rate_all*100:.1f}%")
    print(f"  FALSE NEGATIVES (missed fakes): {fn_all}")
    if rate_all >= 0.95:
        print(f"  STATUS: PASS (target >= 95%)")
    else:
        print(f"  STATUS: FAIL (target >= 95%)")
    print(f"{'=' * 70}\n")

    # Save
    out_path = RESULTS_DIR / "step4_fake_detection.json"
    payload = {
        "step": 4,
        "description": "Fake-citation detection regression test (no AI)",
        "version": _git_version(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_detection_rate": round(rate_all, 4),
        "overall_tp": tp_all,
        "overall_fn": fn_all,
        "overall_total": total_all,
        "datasets": all_results,
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Results saved to {out_path}")

    return all_results


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Citation validation baseline runner (no Flask server needed for steps 1, 2, 4)."
    )
    parser.add_argument(
        "--step", type=int, default=1, choices=[1, 2, 3, 4],
        help="Which step to run: 1=FP baseline, 2=FP root cause, 3=AI comparison, 4=fake detection (default: 1)"
    )
    args = parser.parse_args()

    if args.step == 1:
        run_step1()
    elif args.step == 2:
        run_step2()
    elif args.step == 3:
        run_step3()
    elif args.step == 4:
        run_step4()


if __name__ == "__main__":
    main()
