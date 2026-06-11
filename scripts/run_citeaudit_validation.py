#!/usr/bin/env python3
"""External-validation driver for the CiteAudit benchmark.

Runs a CiteAudit dataset (registered in datasets/manifest.json) through
the deterministic validator IN-PROCESS — no Flask server, no batch HTTP
timeout — then optionally a Gemini AI tier, and scores the result
against CiteAudit's human-validated ground truth.

This exists because run_benchmark.py routes the whole batch through the
Flask /validate endpoint with a 300s client timeout, which is too short
for thousand-citation datasets. run_fp_baseline.py has the right
in-process approach but hardcodes its datasets. This driver is the
manifest-driven, in-process combination of the two.

Usage:
    # Deterministic only (full real-world group)
    python3 scripts/run_citeaudit_validation.py --dataset citeaudit-realworld

    # Deterministic + Gemini AI tier (balanced subset)
    python3 scripts/run_citeaudit_validation.py \\
        --dataset citeaudit-realworld-subset --ai gemini

Scoring convention (matches RESEARCH_LOG.md):
    flagged  = status in {suspicious, invalid}
    TP = fake correctly flagged    FN = fake missed
    FP = real wrongly flagged      TN = real correctly silent
    'warning' is NOT counted as flagged.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from citation_validator import CitationValidator  # noqa: E402

GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/"
              "models/gemini-2.5-flash:generateContent")
FLAGGED = {"suspicious", "invalid"}


def load_dataset(dataset_id: str) -> dict:
    """Return the manifest entry for dataset_id, or exit."""
    manifest = json.loads((REPO_ROOT / "datasets" / "manifest.json").read_text())
    for entry in manifest:
        if entry["id"] == dataset_id:
            return entry
    sys.exit(f"ERROR: dataset '{dataset_id}' not in manifest.json")


def load_ground_truth(entry: dict) -> dict:
    """Build {cite_key: 'valid'|'invalid'} from the dataset's metadata_file."""
    meta = json.loads((REPO_ROOT / entry["metadata_file"]).read_text())
    return {k: v["ground_truth"] for k, v in meta.get("citations", {}).items()}


def build_prompt(citation: dict) -> str:
    """Replicate the frontend AI prompt (mirrors run_benchmark.build_prompt)."""
    fields = citation.get("fields", {})
    field_lines = "\n".join(
        f"  {k}: {v}" for k, v in fields.items() if v and str(v).strip()
    ) or "  (very sparse - only key and type available)"
    suspicion = "; ".join(
        (citation.get("issues") or []) + (citation.get("warnings") or [])
    ) or "(none)"
    meta = citation.get("metadata")
    if meta:
        meta_block = (f"Database title: {meta.get('title', '(none)')}\n"
                      f"  Source: {meta.get('source', 'CrossRef/OpenAlex')}")
        meta_found = "Yes"
    else:
        meta_block = ("Checked: CrossRef, OpenAlex, Semantic Scholar — "
                      "not found in any.")
        meta_found = "No"
    return f"""Analyze this academic citation and determine if it is REAL or FABRICATED.

BibTeX fields:
{field_lines}

DATABASE VERIFICATION RESULTS:
  Status: {citation.get('status', 'unknown')}
  Metadata found in databases: {meta_found}
  {meta_block}

Our automated checks found these notes:
{suspicion}

IMPORTANT INSTRUCTIONS:
- If our database checks found the paper (status=valid), it IS real. Confirm it.
- If the DOI resolved but there's a year mismatch of 1-2 years, that's normal.
- If status=invalid because a DOI didn't resolve, that IS suspicious.
- If status=warning because we couldn't find it, that does NOT automatically mean fake. Very new, very old, or niche-journal papers may not be indexed.
- HOWEVER: NO DOI and NOT found in ANY database is a significant red flag.
- "Not found" in ALL databases means LIKELY FABRICATED unless very new, very old, or non-English.

Respond with JSON only:
{{"is_suspicious": true/false, "confidence": 0-100, "reason": "brief explanation"}}"""


def call_gemini(prompt: str, api_key: str) -> tuple[dict | None, int, str | None]:
    """Return (parsed_json, total_tokens, error). Mirrors webapp.py gemini branch."""
    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": 2048,
                    "temperature": 0.1,
                    "responseMimeType": "application/json",
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
            timeout=60,
        )
    except requests.RequestException as e:
        return None, 0, f"request failed: {e}"
    if not resp.ok:
        return None, 0, f"HTTP {resp.status_code}: {resp.text[:160]}"
    data = resp.json()
    cands = data.get("candidates", [])
    content = (cands[0].get("content", {}).get("parts", [{}])[0].get("text", "")
               if cands else "")
    tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
    content = re.sub(r"^```(?:json)?\s*", "", content.strip())
    content = re.sub(r"\s*```$", "", content.strip())
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        return None, tokens, "no JSON in response"
    try:
        return json.loads(m.group(0)), tokens, None
    except json.JSONDecodeError as e:
        return None, tokens, f"JSON parse error: {e}"


def score(details: list[dict], gt: dict) -> dict:
    """Compute the confusion matrix and detection metrics."""
    tp = fp = tn = fn = unlabelled = 0
    for d in details:
        label = gt.get(d["key"])
        if label is None:
            unlabelled += 1
            continue
        flagged = d["status"] in FLAGGED
        if label == "invalid":          # fake
            tp += flagged
            fn += not flagged
        else:                            # real
            fp += flagged
            tn += not flagged
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    fpr = fp / (fp + tn) if (fp + tn) else None
    f1 = (2 * prec * rec / (prec + rec)) if (prec and rec) else None
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn, "unlabelled": unlabelled,
        "precision": prec, "recall": rec, "fpr": fpr, "f1": f1,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True, help="Manifest dataset id")
    ap.add_argument("--ai", choices=["gemini"], help="Run the AI tier (Gemini)")
    ap.add_argument("--limit", type=int, help="Validate only the first N entries (smoke test)")
    ap.add_argument("--output-dir", default="results/experiments")
    args = ap.parse_args()

    entry = load_dataset(args.dataset)
    gt = load_ground_truth(entry)

    validator = CitationValidator(verbose=False)
    bibtex = "\n\n".join(
        (REPO_ROOT / rel).read_text() for rel in entry["bib_files"])
    entries = validator._parse_bibtex_string(bibtex)
    if args.limit:
        entries = entries[:args.limit]
    n = len(entries)

    print(f"{'='*68}\n  CiteAudit external validation — {entry['name']}")
    print(f"  Dataset: {args.dataset}  ({n} citations)")
    print(f"  AI tier: {args.ai or 'OFF'}\n{'='*68}\n")

    # --- Deterministic tier (in-process) -----------------------------------
    print(f"Step 1: deterministic validation ({n} citations)...")
    t0 = time.time()
    details = []
    for i, e in enumerate(entries, 1):
        try:
            details.append(validator.check_citation(e))
        except Exception as ex:  # one bad citation must not kill the run
            details.append({"key": e.get("key", f"_err_{i}"), "status": "error",
                            "issues": [f"validator exception: {ex}"],
                            "warnings": [], "fields": e.get("fields", {})})
        if i % 100 == 0 or i == n:
            print(f"  {i}/{n}  ({time.time()-t0:.0f}s elapsed)", flush=True)
    det_time = time.time() - t0
    det_score = score(details, gt)
    print(f"  deterministic done in {det_time:.0f}s")

    # --- AI tier -----------------------------------------------------------
    ai_time = ai_calls = ai_errors = ai_tokens = 0
    if args.ai == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            sys.exit("ERROR: GEMINI_API_KEY not set (run: source .env)")
        targets = [d for d in details if d["status"] in {"warning", *FLAGGED}]
        print(f"\nStep 2: Gemini AI tier on {len(targets)} non-valid citations...")
        t1 = time.time()
        for i, d in enumerate(targets, 1):
            parsed, tokens, err = call_gemini(build_prompt(d), api_key)
            ai_tokens += tokens
            if err:
                ai_errors += 1
                d["ai_error"] = err
            else:
                ai_calls += 1
                d["ai_analysis"] = parsed
                if parsed.get("is_suspicious") and parsed.get("confidence", 0) >= 70:
                    if d["status"] == "warning":
                        d["status"] = "suspicious"
                    elif d["status"] == "suspicious" and parsed.get("confidence", 0) >= 85:
                        d["status"] = "invalid"
            if i % 50 == 0 or i == len(targets):
                print(f"  {i}/{len(targets)}  ({ai_tokens} tokens, "
                      f"{ai_errors} errors)", flush=True)
            time.sleep(0.1)
        ai_time = time.time() - t1
        print(f"  AI tier done in {ai_time:.0f}s")

    final_score = score(details, gt)

    # --- Report ------------------------------------------------------------
    def pct(x):
        return "n/a" if x is None else f"{x*100:.1f}%"

    def status_breakdown(label):
        keys = {k for k, v in gt.items() if v == label}
        c = {"valid": 0, "warning": 0, "suspicious": 0, "invalid": 0, "error": 0}
        for d in details:
            if d["key"] in keys:
                c[d["status"]] = c.get(d["status"], 0) + 1
        return c

    real, fake = status_breakdown("valid"), status_breakdown("invalid")
    print(f"\n{'='*68}\n  RESULTS — {args.dataset}\n{'='*68}")
    print(f"  {'':16}{'valid':>9}{'warning':>9}{'suspic.':>9}{'invalid':>9}{'error':>8}")
    print(f"  real citations  {real['valid']:>9}{real['warning']:>9}"
          f"{real['suspicious']:>9}{real['invalid']:>9}{real['error']:>8}")
    print(f"  fake citations  {fake['valid']:>9}{fake['warning']:>9}"
          f"{fake['suspicious']:>9}{fake['invalid']:>9}{fake['error']:>8}")
    s = final_score
    print(f"\n  Confusion matrix:  TP={s['tp']}  FP={s['fp']}  "
          f"TN={s['tn']}  FN={s['fn']}")
    print(f"  False-positive rate (FPR): {pct(s['fpr'])}   "
          f"<- key claim: real citations wrongly flagged")
    print(f"  Recall (fake detection):   {pct(s['recall'])}")
    print(f"  Precision:                 {pct(s['precision'])}")
    print(f"  F1:                        {pct(s['f1'])}")
    if args.ai:
        print(f"\n  Deterministic-only FPR was {pct(det_score['fpr'])}, "
              f"recall {pct(det_score['recall'])} "
              f"(before the AI tier)")
        print(f"  AI tier: {ai_calls} calls, {ai_errors} errors, "
              f"{ai_tokens} tokens (~{ai_tokens/1_000_000*100:.1f}% of Gemini's daily free quota)")
    print(f"{'='*68}\n")

    # --- Persist -----------------------------------------------------------
    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"citeaudit_{args.dataset}_{'ai' if args.ai else 'det'}_{stamp}.json"
    out_path.write_text(json.dumps({
        "dataset": args.dataset,
        "timestamp": stamp,
        "citation_count": n,
        "ai_tier": args.ai,
        "deterministic_seconds": round(det_time, 1),
        "ai_seconds": round(ai_time, 1),
        "ai_calls": ai_calls,
        "ai_errors": ai_errors,
        "ai_tokens": ai_tokens,
        "deterministic_score": det_score,
        "final_score": final_score,
        "status_breakdown": {"real": real, "fake": fake},
        "details": details,
    }, indent=2, default=str))
    print(f"Saved: {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
