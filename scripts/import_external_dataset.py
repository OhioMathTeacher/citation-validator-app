#!/usr/bin/env python3
"""Generic importer template for external citation-validation benchmarks.

When CiteAudit (Yuan et al., 2602.23452), the Rao 931-paper benchmark
(Rao & Callison-Burch, 2604.03159), or the HalluCitation list (Sakai
et al., 2601.18724) lands in a publicly accessible form, copy this
file to ``import_<name>_dataset.py`` and customize the four functions
flagged with TODO_PER_DATASET.

The validator's downstream pipeline expects the canonical layout
already used by ``import_ansari_dataset.py``:

    datasets/<dataset-id>/
        <bib-name>.bib       BibTeX entries, one per citation
        metadata.json        per-citation ground-truth labels and provenance
        README.md            short human-readable description + provenance
        <source-snapshot>    raw source file as retrieved (csv/json/etc.)

After running this importer, append a manifest entry to
``datasets/manifest.json`` (the script prints a ready-to-paste JSON
snippet at the end) and flip the dataset's ``status`` from ``pending``
to ``active`` in ``web/citation-validator.html``.

Usage:
    python3 scripts/import_external_dataset.py \\
        --input path/to/source.{csv,json,bib} \\
        --dataset-id citeaudit-benchmark \\
        --output-dir datasets/citeaudit-benchmark
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Iterable


# Canonical record schema produced by parse_input(). Every importer
# must yield dicts with at least these keys; extra keys are passed
# through to metadata.json verbatim.
RECORD_SCHEMA = {
    "key":           "Stable BibTeX cite-key (str). Must be unique within the dataset.",
    "ground_truth":  "'valid' | 'invalid'. The label for evaluation.",
    "type":          "BibTeX entry type ('article', 'misc', 'inproceedings', ...).",
    "fields":        "Dict of BibTeX fields (title, author, year, doi, journal, ...).",
    "provenance":    "Dict of dataset-specific provenance fields kept in metadata.json.",
}


# ---------------------------------------------------------------------------
# TODO_PER_DATASET #1 — describe the source.
# ---------------------------------------------------------------------------
DATASET_NAME = "External Benchmark (template)"
DATASET_AUTHORS = "Author et al. (2026)"
DATASET_ARXIV = "XXXX.XXXXX"
DATASET_DESCRIPTION = (
    "Replace this string with a one-paragraph description of the dataset, "
    "including counts of real vs. fake citations and source coverage."
)


# ---------------------------------------------------------------------------
# TODO_PER_DATASET #2 — parse the input file into canonical records.
# ---------------------------------------------------------------------------
def parse_input(path: Path) -> Iterable[dict]:
    """Yield records matching RECORD_SCHEMA.

    Implementations should:
      * Read ``path`` (CSV, JSON, BibTeX — whatever the dataset ships).
      * Normalize each row into the canonical record dict.
      * Use a deterministic key derivation so re-imports don't churn
        the BibTeX cite-keys.

    The default implementation handles JSON files with a list of dicts
    that already contain ('key', 'ground_truth', 'type', 'fields',
    'provenance'). Override for CSV or BibTeX inputs.
    """
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"Expected JSON list at top level, got {type(data).__name__}")
        for row in data:
            for required in ("key", "ground_truth", "type", "fields"):
                if required not in row:
                    raise ValueError(f"Record missing required key {required!r}: {row}")
            row.setdefault("provenance", {})
            yield row
    else:
        raise NotImplementedError(
            f"parse_input does not yet handle {path.suffix} inputs. "
            "Customize this function for your dataset's source format."
        )


# ---------------------------------------------------------------------------
# TODO_PER_DATASET #3 — emit a BibTeX entry from a canonical record.
# ---------------------------------------------------------------------------
def record_to_bibtex(record: dict) -> str:
    """Render one canonical record as a BibTeX block."""
    field_lines = []
    for name, value in record["fields"].items():
        if value in (None, ""):
            continue
        escaped = str(value).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        field_lines.append(f"  {name} = {{{escaped}}}")
    body = ",\n".join(field_lines)
    return f"@{record['type']}{{{record['key']},\n{body}\n}}\n"


# ---------------------------------------------------------------------------
# TODO_PER_DATASET #4 — sanity-check the parsed dataset before writing.
# ---------------------------------------------------------------------------
def sanity_check(records: list[dict], expected_count: int | None = None) -> None:
    """Raise if records look malformed; print a one-line summary otherwise."""
    if not records:
        raise ValueError("No records parsed — refusing to write empty dataset.")
    if expected_count and len(records) != expected_count:
        raise ValueError(
            f"Expected {expected_count} records, parsed {len(records)}."
        )
    keys = [r["key"] for r in records]
    if len(set(keys)) != len(keys):
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        raise ValueError(f"Duplicate cite-keys: {dupes[:5]}{'...' if len(dupes) > 5 else ''}")
    labels = [r["ground_truth"] for r in records]
    valid_count = labels.count("valid")
    invalid_count = labels.count("invalid")
    other = [l for l in labels if l not in ("valid", "invalid")]
    if other:
        raise ValueError(f"Unexpected ground_truth labels: {set(other)}")
    print(f"  parsed {len(records)} records — {valid_count} valid, {invalid_count} invalid")


# ---------------------------------------------------------------------------
# Generic write step — usually no per-dataset changes needed below.
# ---------------------------------------------------------------------------
def write_dataset(records: list[dict], dataset_id: str, output_dir: Path,
                  source_snapshot: Path | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    today = str(date.today())

    bib_path = output_dir / f"{dataset_id}.bib"
    meta_path = output_dir / "metadata.json"
    readme_path = output_dir / "README.md"

    bib_path.write_text(
        f"% {DATASET_NAME} ({len(records)} entries)\n"
        f"% Source: arXiv:{DATASET_ARXIV}\n"
        f"% Retrieved: {today}\n\n"
        + "\n".join(record_to_bibtex(r) for r in records),
        encoding="utf-8",
    )

    metadata = {
        "dataset": dataset_id,
        "name": DATASET_NAME,
        "authors": DATASET_AUTHORS,
        "arxiv": DATASET_ARXIV,
        "retrieved_on": today,
        "citation_count": len(records),
        "citations": {
            r["key"]: {
                "ground_truth": r["ground_truth"],
                **r.get("provenance", {}),
            }
            for r in records
        },
    }
    meta_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    valid_count = sum(1 for r in records if r["ground_truth"] == "valid")
    invalid_count = sum(1 for r in records if r["ground_truth"] == "invalid")
    readme_path.write_text(
        f"# {DATASET_NAME}\n\n"
        f"{DATASET_DESCRIPTION}\n\n"
        f"- **Source:** arXiv:{DATASET_ARXIV}\n"
        f"- **Retrieved:** {today}\n"
        f"- **Citations:** {len(records)} ({valid_count} real, {invalid_count} fake)\n\n"
        f"## Files\n\n"
        f"- `{bib_path.name}` — BibTeX entries\n"
        f"- `metadata.json` — per-citation ground truth and provenance\n"
        + (f"- `{source_snapshot.name}` — source snapshot for reproducibility\n"
           if source_snapshot else ""),
        encoding="utf-8",
    )

    print(f"\nWrote:")
    print(f"  {bib_path}")
    print(f"  {meta_path}")
    print(f"  {readme_path}")

    print("\nManifest snippet (paste into datasets/manifest.json):")
    print(json.dumps({
        "id": dataset_id,
        "name": DATASET_NAME,
        "authors": DATASET_AUTHORS,
        "arxiv": DATASET_ARXIV,
        "description": DATASET_DESCRIPTION,
        "citation_count": len(records),
        "ground_truth": "mixed" if (valid_count and invalid_count) else
                        ("valid" if valid_count else "invalid"),
        "tags": ["benchmark", "external", "human-validated"],
        "bib_files": [str(bib_path)],
        "metadata_file": str(meta_path),
        "status": "active",
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True,
                        help="Path to source dataset file (csv|json|bib)")
    parser.add_argument("--dataset-id", required=True,
                        help="Slug used for filenames and manifest id")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Output directory under datasets/")
    parser.add_argument("--expected-count", type=int, default=None,
                        help="If set, fail if parsed record count differs")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")

    print(f"Parsing {args.input}...")
    records = list(parse_input(args.input))
    sanity_check(records, expected_count=args.expected_count)
    write_dataset(records, args.dataset_id, args.output_dir,
                  source_snapshot=args.input if args.input.suffix != ".bib" else None)


if __name__ == "__main__":
    main()
