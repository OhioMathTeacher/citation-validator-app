#!/usr/bin/env python3
"""
Benchmark runner for the Citation Validator.

Runs a dataset through the validation pipeline (deterministic + optional AI)
and logs structured results to a JSONL experiment log.

Usage:
    python scripts/run_benchmark.py --dataset ansari100 --provider gemini
    python scripts/run_benchmark.py --dataset ansari100 --provider groq
    python scripts/run_benchmark.py --dataset ansari100 --no-ai
    python scripts/run_benchmark.py --list-datasets

Requires:
    - Flask server running at http://localhost:5000
    - API key stored in environment variable (GEMINI_API_KEY, GROQ_API_KEY, etc.)
      OR passed via --api-key
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git_version():
    """Return short commit hash and date, e.g. '9146f23 (2026-04-10)'."""
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%h (%ci)"],
            cwd=REPO_ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        return re.sub(r"\s+[+-]\d{4}\)$", ")", out)
    except Exception:
        return "unknown"
SERVER = "http://localhost:5000"

# ── Dataset registry ─────────────────────────────────────────────────────────
# Maps short names to their manifest info. Mirrors datasets/manifest.json.

def load_manifest():
    """Load datasets from manifest.json."""
    manifest_path = REPO_ROOT / "datasets" / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found", file=sys.stderr)
        sys.exit(1)
    with open(manifest_path) as f:
        entries = json.load(f)
    registry = {}
    for entry in entries:
        # Create short aliases
        ds_id = entry["id"]
        registry[ds_id] = entry

        # Convenience aliases
        if ds_id == "compound-deception-ansari":
            registry["ansari100"] = entry
        elif ds_id == "ojsm-fake-frankenstein":
            registry["frankenstein"] = entry
        elif ds_id == "ojsm-fake-plausible":
            registry["plausible"] = entry
        elif ds_id == "ojsm-fake-nonsense":
            registry["nonsense"] = entry
        elif ds_id == "ojsm-fake-stolen-doi":
            registry["stolen-doi"] = entry
        elif ds_id == "ojsm-real-arxiv":
            registry["real-arxiv"] = entry
        elif ds_id == "ojsm-real-crossref":
            registry["real-crossref"] = entry
    return registry


PROVIDER_MODELS = {
    "gemini": "Gemini 2.5 Flash",
    "groq": "Groq Llama 3.3 70B",
    "openai": "OpenAI GPT-4o",
    "anthropic": "Anthropic Claude Sonnet 5",
}

ENV_KEY_NAMES = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_bibtex(dataset_entry):
    """Concatenate all bib_files for a dataset entry."""
    bib_files = dataset_entry.get("bib_files")
    if not bib_files:
        print(f"ERROR: Dataset has no bib_files", file=sys.stderr)
        sys.exit(1)

    combined = []
    for rel in bib_files:
        path = REPO_ROOT / rel
        if not path.exists():
            print(f"WARNING: {path} not found, skipping", file=sys.stderr)
            continue
        combined.append(path.read_text())
    return "\n\n".join(combined)


def load_ground_truth(dataset_entry):
    """Build {cite_key: ground_truth_label} mapping."""
    gt = {}
    dataset_level = dataset_entry.get("ground_truth")

    meta_file = dataset_entry.get("metadata_file")
    if meta_file:
        meta_path = REPO_ROOT / meta_file
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            citations = meta.get("citations", {})
            for _id, info in citations.items():
                # The cite key in metadata may differ from BibTeX key.
                # For ansari100, the metadata keys ARE the BibTeX keys.
                gt[_id] = info.get("ground_truth", dataset_level)
            return gt

    # Fallback: uniform ground truth from manifest
    if dataset_level and dataset_level != "mixed":
        # We'll populate per-key after we know the keys
        return {"__dataset_level__": dataset_level}

    return gt


def build_prompt(citation):
    """Replicate the frontend's AI analysis prompt."""
    fields = citation.get("fields", {})
    field_lines = "\n".join(
        f"  {k}: {v}" for k, v in fields.items() if v and str(v).strip()
    ) or "  (very sparse - only key and type available)"

    suspicion_reasons = "; ".join(
        (citation.get("issues", []) or []) + (citation.get("warnings", []) or [])
    ) or "(none)"

    db_status = citation.get("status", "unknown")
    meta = citation.get("metadata")
    meta_found = "Yes" if meta else "No"
    meta_title = meta.get("title", "(none)") if meta else "(none)"
    meta_source = meta.get("source", "CrossRef/OpenAlex") if meta else "CrossRef/OpenAlex"

    meta_block = (
        f"Database title: {meta_title}\n  Source: {meta_source}"
        if meta_found == "Yes"
        else "Checked: CrossRef, OpenAlex, Semantic Scholar — not found in any."
    )

    return f"""Analyze this academic citation and determine if it is REAL or FABRICATED.

BibTeX fields:
{field_lines}

DATABASE VERIFICATION RESULTS:
  Status: {db_status}
  Metadata found in databases: {meta_found}
  {meta_block}

Our automated checks found these notes:
{suspicion_reasons}

IMPORTANT INSTRUCTIONS:
- If our database checks found the paper (status=valid), it IS real. Confirm it.
- If the DOI resolved but there's a year mismatch of 1-2 years, that's normal (online vs print publication dates).
- If status=invalid because a DOI didn't resolve, that IS suspicious — real papers have working DOIs.
- If status=warning because we couldn't find it in databases, that does NOT automatically mean it's fake. Very new papers (2026), old papers (pre-2000), or niche journals may not be indexed yet.
- HOWEVER: If a citation has NO DOI and was NOT found in ANY database (CrossRef, OpenAlex, Semantic Scholar), treat that as a significant red flag. Most real published papers appear in at least one database. Increase your suspicion.
- "Not found" in one database means UNVERIFIABLE. "Not found" in ALL databases means LIKELY FABRICATED unless the paper is very new, very old, or from a non-English journal.
- When in doubt between "unable to verify" and "likely hallucinated": if zero databases matched, lean toward suspicious. If at least one partial match exists, lean toward legitimate.

Respond with JSON only:
{{"is_suspicious": true/false, "confidence": 0-100, "reason": "brief explanation"}}"""


def compute_accuracy(details, ground_truth):
    """Compute confusion matrix metrics using standard detection convention.

    Convention (''positive'' = detector flags a citation):
      TP — fake citation correctly flagged       (detector fires, correct)
      FP — real citation incorrectly flagged      (detector fires, wrong)
      TN — real citation correctly NOT flagged     (detector silent, correct)
      FN — fake citation that slips through        (detector silent, wrong)
    """
    tp = tn = fp = fn = skipped = 0
    false_negatives = []
    false_positives = []

    dataset_level = ground_truth.get("__dataset_level__")

    for c in details:
        key = c["key"]
        gt_entry = ground_truth.get(key)
        if gt_entry:
            expected = gt_entry if isinstance(gt_entry, str) else gt_entry
        elif dataset_level:
            expected = dataset_level
        else:
            skipped += 1
            continue

        if expected == "mixed":
            skipped += 1
            continue

        is_flagged = c["status"] in ("suspicious", "invalid")

        if expected == "valid":
            if not is_flagged:
                tn += 1   # Real citation correctly NOT flagged
            else:
                fp += 1   # Real citation incorrectly flagged
                false_positives.append(key)
        elif expected == "invalid":
            if is_flagged:
                tp += 1   # Fake citation correctly flagged
            else:
                fn += 1   # Fake citation slipped through
                false_negatives.append(key)
        else:
            skipped += 1

    total = tp + tn + fp + fn
    if total == 0:
        return None

    accuracy = (tp + tn) / total
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "total": total, "skipped": skipped,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "fpr": round(fpr, 4),
        "fnr": round(fnr, 4),
        "false_negatives": false_negatives,
        "false_positives": false_positives,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def run_benchmark(dataset_name, provider, api_key, use_ai, output_dir, delay=0.0,
                  retries=3, retry_backoff=2.0):
    registry = load_manifest()
    if dataset_name not in registry:
        print(f"ERROR: Unknown dataset '{dataset_name}'")
        print(f"Available: {', '.join(sorted(set(registry.keys())))}")
        sys.exit(1)

    entry = registry[dataset_name]
    ds_id = entry["id"]
    print(f"\n{'='*70}")
    print(f"  BENCHMARK: {entry['name']}")
    print(f"  Dataset:   {ds_id}")
    print(f"  AI:        {'OFF' if not use_ai else f'{provider} ({PROVIDER_MODELS.get(provider, provider)})'}")
    print(f"  Version:   {_git_version()}")
    print(f"{'='*70}\n")

    # 1. Load BibTeX
    bibtex = load_bibtex(entry)
    entry_count = len(re.findall(r'^@', bibtex, re.MULTILINE))
    print(f"Loaded {entry_count} BibTeX entries")

    # 2. Load ground truth
    ground_truth = load_ground_truth(entry)
    gt_count = len([k for k in ground_truth if k != "__dataset_level__"])
    if "__dataset_level__" in ground_truth:
        print(f"Ground truth: dataset-level = {ground_truth['__dataset_level__']}")
    else:
        print(f"Ground truth: {gt_count} per-citation labels loaded")

    # 3. Check server is alive
    try:
        r = requests.get(SERVER, timeout=5)
        r.raise_for_status()
    except Exception as e:
        print(f"\nERROR: Cannot reach {SERVER}")
        print(f"Start the server first: python scripts/webapp.py")
        sys.exit(1)

    # 4. Run deterministic validation
    print(f"\nStep 1/{'2' if use_ai else '1'}: Deterministic validation...")
    t0 = time.time()
    resp = requests.post(
        f"{SERVER}/validate",
        json={"bibtex": bibtex},
        timeout=5400,  # 90min - bumped from 300 for per-host throttle (deterministic on 100+ citations can take 20+ min)
    )
    resp.raise_for_status()
    results = resp.json()
    det_time = time.time() - t0
    print(f"  Done in {det_time:.1f}s — {results['valid']} valid, "
          f"{results['warnings']} warning, {results['suspicious']} suspicious, "
          f"{results['invalid']} invalid")

    # 5. AI analysis (if enabled)
    ai_time = 0
    ai_calls = 0
    ai_errors = 0
    ai_retries = 0      # retry attempts spent
    ai_recovered = 0    # citations that failed once and succeeded on a retry
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    
    if use_ai:
        targets = [c for c in results["details"]
                   if c["status"] in ("suspicious", "invalid", "warning")]
        total = len(targets)
        print(f"\nStep 2/2: AI analysis on {total} citations...")
        t1 = time.time()

        for i, citation in enumerate(targets, 1):
            prompt = build_prompt(citation)

            # Try each citation up to `retries` times. A dropped call is not a
            # visible failure — it leaves the citation unescalated and the run
            # still reports a complete-looking count — so a transient error
            # silently biases the result downward. Retrying is what keeps the
            # denominator honest.
            last_error = None
            for attempt in range(1, retries + 1):
                try:
                    ai_resp = requests.post(
                        f"{SERVER}/analyze",
                        json={"provider": provider, "apiKey": api_key, "prompt": prompt},
                        timeout=60,
                    )
                    if ai_resp.ok:
                        ai_data = ai_resp.json()

                        # Extract token usage metadata
                        metadata = ai_data.get('_metadata', {})
                        if metadata:
                            tokens = metadata.get('tokens', {})
                            total_input_tokens += tokens.get('input_tokens', 0)
                            total_output_tokens += tokens.get('output_tokens', 0)
                            total_tokens += tokens.get('total_tokens', 0)

                        citation["ai_analysis"] = ai_data

                        # Apply AI escalation (mirrors citation_validator.py logic)
                        if isinstance(ai_data, dict):
                            is_susp = ai_data.get("is_suspicious", False)
                            conf = ai_data.get("confidence", 0)
                            if is_susp and conf >= 70:
                                if citation["status"] == "warning":
                                    citation["status"] = "suspicious"
                                elif citation["status"] == "suspicious" and conf >= 85:
                                    citation["status"] = "invalid"

                        ai_calls += 1
                        if attempt > 1:
                            citation["ai_attempts"] = attempt
                            ai_recovered += 1
                            print(f"  AI recovered on {citation['key']} "
                                  f"(attempt {attempt}/{retries})")
                        last_error = None
                        break

                    last_error = {"status_code": ai_resp.status_code,
                                  "message": ai_resp.text[:200]}
                    # Auth and permission failures will not fix themselves;
                    # retrying only burns quota and delays the run.
                    if ai_resp.status_code in (401, 403):
                        break
                except requests.exceptions.Timeout:
                    last_error = {"status_code": "timeout",
                                  "message": "Request timed out"}
                except Exception as e:
                    last_error = {"status_code": "exception",
                                  "message": str(e)[:200]}

                if attempt < retries:
                    ai_retries += 1
                    backoff = retry_backoff * (2 ** (attempt - 1))
                    print(f"  AI {last_error['status_code']} on {citation['key']}, "
                          f"retrying in {backoff:.0f}s ({attempt}/{retries - 1} used)")
                    time.sleep(backoff)

            if last_error is not None:
                ai_errors += 1
                citation["ai_error"] = last_error
                citation["ai_attempts"] = retries
                print(f"  AI FAILED on {citation['key']} after {retries} attempts: "
                      f"{last_error['status_code']}")

            if i % 10 == 0 or i == total:
                print(f"  {i}/{total} complete...")

            # Pace the calls. An unthrottled run that trips a rate limit does
            # not fail — it records ai_errors and leaves those citations
            # unescalated, so the run still looks complete while reporting
            # fewer suspicious citations than it should.
            if delay and i < total:
                time.sleep(delay)

        ai_time = time.time() - t1
        print(f"  AI pass done in {ai_time:.1f}s ({ai_calls} successful calls, {ai_errors} errors)")
        if ai_retries:
            print(f"  Retries: {ai_retries} spent, {ai_recovered} citations recovered")
        if ai_errors:
            print(f"  WARNING: {ai_errors} citations have no AI verdict after "
                  f"{retries} attempts. They were NOT escalated, so the counts "
                  f"below understate detection. Do not average this run.")
        if ai_calls > 0:
            print(f"  Tokens: {total_input_tokens} in, {total_output_tokens} out, {total_tokens} total")
            print(f"  Avg per call: {total_tokens/ai_calls:.0f} tokens")

        # Recount after AI escalation
        results["valid"] = sum(1 for c in results["details"] if c["status"] == "valid")
        results["warnings"] = sum(1 for c in results["details"] if c["status"] == "warning")
        results["suspicious"] = sum(1 for c in results["details"] if c["status"] == "suspicious")
        results["invalid"] = sum(1 for c in results["details"] if c["status"] == "invalid")

    # 6. Compute accuracy
    acc = compute_accuracy(results["details"], ground_truth)

    # 7. Build run record
    now = datetime.now(timezone.utc)
    run_record = {
        "timestamp": now.isoformat(),
        "dataset_id": ds_id,
        "dataset_name": entry["name"],
        "citation_count": results["total"],
        "ai_enabled": use_ai,
        "ai_provider": provider if use_ai else None,
        "ai_model": PROVIDER_MODELS.get(provider) if use_ai else None,
        "ai_calls": ai_calls,
        "ai_errors": ai_errors if use_ai else 0,
        "ai_retries": ai_retries if use_ai else 0,
        "ai_recovered": ai_recovered if use_ai else 0,
        "ai_max_attempts": retries if use_ai else 0,
        "deterministic_seconds": round(det_time, 1),
        "ai_seconds": round(ai_time, 1),
        "total_seconds": round(det_time + ai_time, 1),
        "counts": {
            "valid": results["valid"],
            "warning": results["warnings"],
            "suspicious": results["suspicious"],
            "invalid": results["invalid"],
        },
        "accuracy": acc,
    }
    
    # Add token usage if AI was used
    if use_ai and ai_calls > 0:
        run_record["tokens"] = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "avg_per_call": round(total_tokens / ai_calls, 1) if ai_calls > 0 else 0,
        }

    # 8. Print summary
    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}")
    print(f"  Valid:      {results['valid']}")
    print(f"  Warning:    {results['warnings']}")
    print(f"  Suspicious: {results['suspicious']}")
    print(f"  Invalid:    {results['invalid']}")
    if acc:
        print(f"\n  Accuracy:   {acc['accuracy']*100:.1f}%")
        print(f"  F1 Score:   {acc['f1']*100:.1f}%")
        print(f"  TP: {acc['tp']}  TN: {acc['tn']}  FP: {acc['fp']}  FN: {acc['fn']}  Skipped: {acc['skipped']}")
        if acc["false_negatives"]:
            print(f"\n  False negatives (missed fakes):")
            for key in acc["false_negatives"]:
                print(f"    - {key}")
        if acc["false_positives"]:
            print(f"\n  False positives (wrongly flagged real):")
            for key in acc["false_positives"]:
                print(f"    - {key}")
    print(f"\n  Time: {run_record['total_seconds']}s "
          f"(det: {run_record['deterministic_seconds']}s, ai: {run_record['ai_seconds']}s)")
    print(f"{'='*70}\n")

    # 9. Save to JSONL log
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log_path = output_dir / "experiment_log.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(run_record) + "\n")
    print(f"Run appended to {log_path}")

    # 10. Save detailed results
    slug_provider = provider or "no-ai"
    slug_ts = now.strftime("%Y%m%d-%H%M%S")
    detail_name = f"{ds_id}_{slug_provider}_{slug_ts}.json"
    detail_path = output_dir / detail_name
    full_output = {
        "run": run_record,
        "details": results["details"],
    }
    with open(detail_path, "w") as f:
        json.dump(full_output, f, indent=2)
    print(f"Full details saved to {detail_path}")

    return run_record


def list_datasets():
    registry = load_manifest()
    seen = set()
    print(f"\n{'='*70}")
    print(f"  AVAILABLE DATASETS")
    print(f"{'='*70}\n")
    print(f"  {'Short Name':<25} {'Citations':<10} {'GT':<10} {'Status'}")
    print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10}")
    for key, entry in registry.items():
        ds_id = entry["id"]
        if ds_id in seen:
            continue
        seen.add(ds_id)
        status = entry.get("status", "ready")
        gt = entry.get("ground_truth", "?")
        count = entry.get("citation_count", "?")
        bib = entry.get("bib_files")
        available = "ready" if bib else "pending"
        print(f"  {ds_id:<25} {str(count):<10} {gt:<10} {available}")

    # Also show aliases
    aliases = {k: v["id"] for k, v in registry.items() if k != v["id"]}
    if aliases:
        print(f"\n  Aliases:")
        for alias, target in sorted(aliases.items()):
            print(f"    {alias} → {target}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Run citation validation benchmarks and log results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_benchmark.py --list-datasets
  python scripts/run_benchmark.py --dataset ansari100 --provider gemini
  python scripts/run_benchmark.py --dataset ansari100 --provider groq
  python scripts/run_benchmark.py --dataset ansari100 --no-ai
  python scripts/run_benchmark.py --dataset real-arxiv --provider gemini
        """,
    )
    parser.add_argument("--dataset", "-d", help="Dataset name or alias")
    parser.add_argument("--provider", "-p", choices=["gemini", "groq", "openai", "anthropic"],
                        help="AI provider")
    parser.add_argument("--api-key", "-k", help="API key (default: from env var)")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI analysis")
    parser.add_argument("--output-dir", "-o", default="results/experiments",
                        help="Output directory (default: results/experiments)")
    parser.add_argument("--list-datasets", "-l", action="store_true",
                        help="List available datasets and exit")
    parser.add_argument("--server", "-s", default="http://localhost:5000",
                        help="Server URL (default: http://localhost:5000)")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Seconds to pause between AI calls, to stay under "
                             "provider rate limits (default: 0, unthrottled)")
    parser.add_argument("--retries", type=int, default=3,
                        help="Attempts per citation before giving up "
                             "(default: 3; use 1 to disable retrying)")
    parser.add_argument("--retry-backoff", type=float, default=2.0,
                        help="Base seconds before a retry, doubling each "
                             "attempt (default: 2 -> 2s, 4s)")

    args = parser.parse_args()

    global SERVER
    SERVER = args.server

    if args.list_datasets:
        list_datasets()
        return

    if not args.dataset:
        parser.error("--dataset is required (or use --list-datasets)")

    use_ai = not args.no_ai
    provider = args.provider
    api_key = args.api_key

    if use_ai:
        if not provider:
            parser.error("--provider is required when AI is enabled (or use --no-ai)")
        if not api_key:
            env_name = ENV_KEY_NAMES.get(provider, f"{provider.upper()}_API_KEY")
            api_key = os.environ.get(env_name)
            if not api_key:
                parser.error(f"No API key. Set {env_name} or pass --api-key")

    run_benchmark(args.dataset, provider, api_key, use_ai, args.output_dir,
                  delay=args.delay, retries=max(1, args.retries),
                  retry_backoff=args.retry_backoff)


if __name__ == "__main__":
    main()
