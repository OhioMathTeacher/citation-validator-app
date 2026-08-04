#!/usr/bin/env python3
"""Importer for the CiteAudit benchmark (Yuan et al., arXiv:2602.23452).

Source: https://github.com/shiiiikw/CiteAudit  (data/benchmark.json)

CiteAudit ships 9,442 citations as free-text reference strings, each
labelled with a boolean ground truth (GT) and a source group:

    {"source_type": "realworld"|"generated",
     "citation": "<free-text reference string>",
     "GT": true|false,        # true  -> real citation
     "Predict": true|false}   # CiteAudit's own tool prediction

Our validator expects BibTeX with parsed fields. This importer parses
each reference string into BibTeX fields (doi, arxiv eprint, year, and
a heuristic author/title split), always preserving the original string
verbatim in the ``note`` field so the AI tier sees ground truth input.

Customized from scripts/import_external_dataset.py per its instructions.

Usage:
    # Full benchmark (9,442) — fills the pending manifest entry
    python3 scripts/import_citeaudit_dataset.py \\
        --input ../CiteAudit/data/benchmark.json \\
        --dataset-id citeaudit-benchmark \\
        --output-dir datasets/citeaudit-benchmark

    # Real-world group only (3,356 — independently sourced)
    python3 scripts/import_citeaudit_dataset.py \\
        --input ../CiteAudit/data/benchmark.json \\
        --dataset-id citeaudit-realworld --source-type realworld \\
        --output-dir datasets/citeaudit-realworld

    # Balanced subset for the AI run (250 real + 250 fake)
    python3 scripts/import_citeaudit_dataset.py \\
        --input ../CiteAudit/data/benchmark.json \\
        --dataset-id citeaudit-realworld-subset --source-type realworld \\
        --sample 250 --output-dir datasets/citeaudit-realworld-subset
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.request import urlopen


# Upstream lives in the CiteAudit repository, which carries no licence. This
# project therefore does not redistribute it: the data is fetched on demand
# and the derived BibTeX is rebuilt locally. See datasets/README.md.
UPSTREAM_URL = ("https://raw.githubusercontent.com/shiiiikw/CiteAudit/"
                "main/data/benchmark.json")
# The snapshot every published figure in this project was computed against.
UPSTREAM_SHA256 = "0bf0a7b23d13f2ee355ee0742ffadf9b8bf7f8c025226dc9363d8ea012b1bae5"


def fetch_upstream(cache: Path) -> Path:
    """Download CiteAudit's benchmark.json, reusing a cached copy if present."""
    if cache.exists():
        print(f"Using cached upstream copy: {cache}")
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {UPSTREAM_URL}")
    with urlopen(UPSTREAM_URL) as response:
        cache.write_bytes(response.read())
    return cache


# ---------------------------------------------------------------------------
# TODO_PER_DATASET #1 — describe the source.
# ---------------------------------------------------------------------------
DATASET_NAME = "CiteAudit — Human-Validated Citation Benchmark"
DATASET_AUTHORS = "Yuan, Shi, Zhang, Sun, Chawla & Ye (2026)"
DATASET_ARXIV = "2602.23452"
DATASET_DESCRIPTION = (
    "Human-validated citation benchmark (Yuan et al., 2026). Each entry is "
    "a free-text reference string labelled real/fake by human annotators. "
    "The 'realworld' group is independently sourced from published papers; "
    "the 'generated' group is synthetically constructed."
)


# ---------------------------------------------------------------------------
# Reference-string parser.
# ---------------------------------------------------------------------------
# DOIs in CiteAudit's free-text strings carry PDF-extraction artifact
# spaces (e.g. "10.1016/j. tics.2004.10.003"). The regex tolerates a
# space only when the next character continues a DOI (digit or
# lowercase) — never before "URL", "DOI", or a capitalized word, which
# is where a real DOI ends. _clean_doi() then strips the spaces.
DOI_RE = re.compile(r"\b10\.\d{4,9}/(?:[-._;()/:a-zA-Z0-9]|\s(?=[-._0-9a-z]))+")
_DOI_VIEW_SUFFIX = re.compile(r"/(?:full|abstract|pdf|epdf|html|meta|summary)$", re.I)


def _clean_doi(raw: str) -> str:
    """Normalize an extracted DOI: drop artifact spaces and view suffixes."""
    doi = re.sub(r"\s+", "", raw).rstrip(".,;)")
    return _DOI_VIEW_SUFFIX.sub("", doi)


ARXIV_RE = re.compile(r"arxiv\s*[:/]?\s*(\d{4}\.\d{4,5})(v\d+)?", re.I)
ARXIV_ABS_RE = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})(v\d+)?", re.I)
URL_RE = re.compile(r"https?://\S+")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# Split on a period+space that follows a lowercase letter, digit, or
# closing bracket — avoids splitting after an initial like "A. Smith".
SENT_SPLIT_RE = re.compile(r"(?<=[a-z0-9\)\]])\.\s+")


def parse_reference(text: str) -> dict:
    """Parse a free-text reference string into BibTeX fields.

    DOI and arXiv extraction are regex-exact and reliable. The
    author/title split is heuristic: imperfect splits degrade only the
    database-search tier (a real citation that fails to match lands at
    'warning', never 'suspicious'), so they cannot manufacture a false
    positive. The verbatim string is always kept in ``note``.
    """
    text = " ".join(text.split())  # normalize whitespace
    fields: dict[str, str] = {}

    m = DOI_RE.search(text)
    if m:
        fields["doi"] = _clean_doi(m.group(0))

    am = ARXIV_RE.search(text) or ARXIV_ABS_RE.search(text)
    if am:
        fields["eprint"] = am.group(1)
        fields["archivePrefix"] = "arXiv"

    years = [y for y in YEAR_RE.findall(text) if 1900 <= int(y) <= 2027]
    if years:
        fields["year"] = years[-1]

    # Strip identifiers before the author/title split so trailing
    # "doi: ..." / "URL ..." fragments don't pollute the venue chunk.
    clean = URL_RE.sub("", text)
    clean = DOI_RE.sub("", clean)
    clean = re.sub(r"\bdoi\s*:?\s*", "", clean, flags=re.I)
    clean = re.sub(r"\barxiv\s*[:/]?\s*\S+", "", clean, flags=re.I)
    parts = [p.strip() for p in SENT_SPLIT_RE.split(clean) if p.strip()]
    if len(parts) >= 2:
        fields["author"] = parts[0]
        fields["title"] = parts[1].rstrip(".")
    elif parts:
        fields["title"] = parts[0].rstrip(".")

    fields["note"] = text
    return fields


# ---------------------------------------------------------------------------
# TODO_PER_DATASET #2 — parse benchmark.json into canonical records.
# ---------------------------------------------------------------------------
def parse_input(path: Path, source_type: str = "all") -> Iterable[dict]:
    """Yield canonical records from CiteAudit's benchmark.json."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    data = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    counters: dict[str, int] = {}
    for rec in data:
        st = rec.get("source_type", "unknown")
        if source_type != "all" and st != source_type:
            continue
        counters[st] = counters.get(st, 0) + 1
        prefix = {"realworld": "rw", "generated": "gen"}.get(st, st[:3])
        citation_text = rec["citation"]
        yield {
            "key": f"citeaudit_{prefix}_{counters[st]:04d}",
            "ground_truth": "valid" if rec["GT"] else "invalid",
            "type": "misc",
            "fields": parse_reference(citation_text),
            "provenance": {
                "source_type": st,
                "citeaudit_predict": rec.get("Predict"),
                "citation_text": citation_text,
            },
        }


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
def sanity_check(records: list[dict]) -> None:
    """Raise if records look malformed; print a one-line summary otherwise."""
    if not records:
        raise ValueError("No records parsed — refusing to write empty dataset.")
    keys = [r["key"] for r in records]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate cite-keys detected.")
    labels = [r["ground_truth"] for r in records]
    other = {l for l in labels if l not in ("valid", "invalid")}
    if other:
        raise ValueError(f"Unexpected ground_truth labels: {other}")
    with_doi = sum(1 for r in records if r["fields"].get("doi"))
    with_arxiv = sum(1 for r in records if r["fields"].get("eprint"))
    with_title = sum(1 for r in records if r["fields"].get("title"))
    print(f"  parsed {len(records)} records — "
          f"{labels.count('valid')} valid, {labels.count('invalid')} invalid")
    print(f"  field coverage — doi: {with_doi}, arxiv: {with_arxiv}, "
          f"title: {with_title}/{len(records)}")


def write_dataset(records: list[dict], dataset_id: str, output_dir: Path,
                  description: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    today = str(date.today())
    bib_path = output_dir / f"{dataset_id}.bib"
    meta_path = output_dir / "metadata.json"
    readme_path = output_dir / "README.md"

    bib_path.write_text(
        f"% {DATASET_NAME} ({len(records)} entries)\n"
        f"% Source: arXiv:{DATASET_ARXIV} — github.com/shiiiikw/CiteAudit\n"
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
            r["key"]: {"ground_truth": r["ground_truth"], **r.get("provenance", {})}
            for r in records
        },
    }
    meta_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    valid_count = sum(1 for r in records if r["ground_truth"] == "valid")
    invalid_count = len(records) - valid_count
    readme_path.write_text(
        f"# {DATASET_NAME}\n\n{description}\n\n"
        f"- **Source:** arXiv:{DATASET_ARXIV} (github.com/shiiiikw/CiteAudit)\n"
        f"- **Retrieved:** {today}\n"
        f"- **Citations:** {len(records)} ({valid_count} real, {invalid_count} fake)\n\n"
        f"## Files\n\n"
        f"- `{bib_path.name}` — BibTeX entries (parsed from free-text strings)\n"
        f"- `metadata.json` — per-citation ground truth and provenance\n",
        encoding="utf-8",
    )

    print(f"\nWrote:\n  {bib_path}\n  {meta_path}\n  {readme_path}")
    print("\nManifest snippet (paste into datasets/manifest.json):")
    print(json.dumps({
        "id": dataset_id,
        "name": DATASET_NAME,
        "authors": DATASET_AUTHORS,
        "arxiv": DATASET_ARXIV,
        "description": description,
        "citation_count": len(records),
        "ground_truth": "mixed" if (valid_count and invalid_count) else
                        ("valid" if valid_count else "invalid"),
        "tags": ["benchmark", "external", "human-validated", "citeaudit"],
        "bib_files": [f"datasets/{dataset_id}/{bib_path.name}"],
        "metadata_file": f"datasets/{dataset_id}/metadata.json",
        "status": "active",
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=None,
                        help="Path to a local CiteAudit benchmark.json. Omit to "
                             "download it from upstream (see --fetch).")
    parser.add_argument("--fetch", action="store_true",
                        help="Download benchmark.json from the CiteAudit repository. "
                             "This project does not redistribute CiteAudit's data; "
                             "see datasets/README.md.")
    parser.add_argument("--cache", type=Path,
                        default=Path(".cache/citeaudit-benchmark.json"),
                        help="Where --fetch stores the download (git-ignored)")
    parser.add_argument("--dataset-id", required=True,
                        help="Slug used for filenames and manifest id")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Output directory under datasets/")
    parser.add_argument("--source-type", default="all",
                        choices=["all", "realworld", "generated"],
                        help="Restrict to one CiteAudit source group")
    parser.add_argument("--sample", type=int, default=None,
                        help="If set, randomly sample N records per ground-truth "
                             "class (balanced subset, seed 42)")
    args = parser.parse_args()

    if args.fetch or args.input is None:
        source = fetch_upstream(args.cache)
    else:
        source = args.input
        if not source.exists():
            raise SystemExit(f"Input not found: {source}")

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    print(f"Source SHA-256: {digest}")
    if digest != UPSTREAM_SHA256:
        print("  WARNING: upstream differs from the snapshot this project's "
              "published figures were computed against")
        print(f"  expected {UPSTREAM_SHA256}")

    print(f"Parsing {source} (source-type={args.source_type})...")
    records = list(parse_input(source, source_type=args.source_type))

    description = DATASET_DESCRIPTION
    if args.source_type != "all":
        description += f" This dataset is the '{args.source_type}' group only."
    if args.sample:
        rng = random.Random(42)
        by_label: dict[str, list] = {"valid": [], "invalid": []}
        for r in records:
            by_label[r["ground_truth"]].append(r)
        sampled = []
        for label, pool in by_label.items():
            n = min(args.sample, len(pool))
            sampled.extend(rng.sample(pool, n))
            if n < args.sample:
                print(f"  note: only {n} '{label}' records available "
                      f"(requested {args.sample})")
        rng.shuffle(sampled)
        records = sampled
        description += (f" Balanced random subset: up to {args.sample} per class "
                        f"(seed 42).")

    sanity_check(records)
    write_dataset(records, args.dataset_id, args.output_dir, description)


if __name__ == "__main__":
    main()
