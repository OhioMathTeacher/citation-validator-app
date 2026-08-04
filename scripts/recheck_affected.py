#!/usr/bin/env python3
"""Re-run stored citations whose verdict the current code could change.

The published figures come from runs dated 2026-05-24. When the validator
changes, the honest question is not "do the old numbers still hold?" but
"which of them could have moved, and did they?" Re-running every dataset
costs days of throttled API calls; re-running the citations the change can
actually reach costs minutes.

Only DOI-bearing citations are re-run. The author and date checks live on the
DOI path, so a citation with no DOI cannot be touched by them -- in the
CiteAudit real-world set that is roughly nine in ten.

Usage:
    python3 scripts/recheck_affected.py \\
        --baseline results/experiments/citeaudit_citeaudit-realworld_det_*.json \\
        --output results/recheck-YYYYMMDD/affected-recheck.json

Every row records the old and new status and warnings, so the delta can be
audited entry by entry rather than taken on trust. Rows whose baseline warning
was a transient network failure are marked: those measure the network, not the
code, and must not be reported as behaviour changes.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from citation_validator import CitationValidator, __version__

TRANSIENT_MARKERS = ("could not be verified", "unreachable", "rate limit")


def _doi_of(entry: dict) -> str | None:
    doi = (entry.get("fields") or {}).get("doi")
    return doi.strip().lower() if doi else None


def load_baseline(patterns: list[str]) -> dict[str, dict]:
    """Map DOI -> the stored record, keeping the most recent run per DOI."""
    by_doi: dict[str, dict] = {}
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            data = json.loads(Path(path).read_text())
            for record in data.get("details") or data.get("results") or []:
                doi = _doi_of(record)
                if doi:
                    by_doi[doi] = record
    return by_doi


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", nargs="+", required=True,
                        help="Stored deterministic result JSON (globs allowed)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None,
                        help="Re-check only the first N (for a smoke run)")
    args = parser.parse_args()

    baseline = load_baseline(args.baseline)
    dois = sorted(baseline)[: args.limit]
    print(f"{len(baseline)} DOI-bearing citations in baseline; re-checking {len(dois)}")

    validator = CitationValidator(use_ai=False)
    started = time.time()
    rows, changed, errors = [], 0, 0

    for i, doi in enumerate(dois, 1):
        record = baseline[doi]
        entry = {"key": record["key"], "type": record.get("type", "misc"),
                 "fields": record["fields"]}
        old_status = record.get("status")
        old_warnings = record.get("warnings") or []
        try:
            fresh = validator.check_citation(entry)
            new_status, new_warnings = fresh["status"], fresh.get("warnings") or []
            note = fresh.get("coverage_notes") or []
            error = None
        except Exception as exc:                       # noqa: BLE001
            new_status, new_warnings, note, error = None, [], [], str(exc)
            errors += 1

        # A baseline 'warning' that was really a timeout is not a finding the
        # code later reversed; it is the network having been down that day.
        baseline_transient = any(
            any(m in w.lower() for m in TRANSIENT_MARKERS) for w in old_warnings)

        row = {"doi": doi, "key": record["key"],
               "old_status": old_status, "new_status": new_status,
               "old_warnings": old_warnings, "new_warnings": new_warnings,
               "coverage_notes": note,
               "baseline_transient": baseline_transient,
               "changed": old_status != new_status, "error": error}
        rows.append(row)
        if row["changed"]:
            changed += 1
        if i % 25 == 0:
            print(f"  {i}/{len(dois)}  changed={changed}  errors={errors}")

    elapsed = round(time.time() - started, 1)
    code_attributable = sum(
        1 for r in rows if r["changed"] and not r["baseline_transient"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "version": __version__,
        "baseline": args.baseline,
        "checked": len(rows),
        "changed": changed,
        "changed_excluding_transient_baseline": code_attributable,
        "errors": errors,
        "elapsed_seconds": elapsed,
        "rows": rows,
    }, indent=2))

    print(f"\n{len(rows)} checked, {changed} changed "
          f"({code_attributable} code-attributable), {errors} errors, {elapsed}s")
    print(f"Written to {args.output}")


if __name__ == "__main__":
    main()
