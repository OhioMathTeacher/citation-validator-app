#!/usr/bin/env python3
"""Build a local Ansari benchmark subset from the public GPTZero NeurIPS table.

Usage:
  python scripts/import_ansari_dataset.py --limit 50
  python scripts/import_ansari_dataset.py --limit 100 --output-dir datasets/compound-deception-ansari
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path
from urllib.request import urlopen

SOURCE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "14hIuCK7HCnGhdCuxfwp1wIYbbHMn-K3FNvY9NgWGW0Y/export?format=csv"
)
SOURCE_DOC_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "14hIuCK7HCnGhdCuxfwp1wIYbbHMn-K3FNvY9NgWGW0Y/edit?usp=sharing"
)


def clean(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split()).strip()


def esc_bib(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def build_files(rows: list[dict[str, str]], limit: int, output_dir: Path) -> tuple[Path, Path]:
    subset = rows[:limit]
    today = str(date.today())

    bib_file = output_dir / f"ansari{limit}.bib"
    meta_file = output_dir / "metadata.json"
    snapshot_file = output_dir / "gptzero_neurips_100_source.csv"
    readme_file = output_dir / "README.md"

    bib_lines = [
        f"% Ansari benchmark seed ({limit} rows) extracted from GPTZero NeurIPS 2025 table",
        f"% Source sheet: {SOURCE_DOC_URL}",
        f"% Retrieved: {today}",
        "% NOTE: Entries are represented as @misc from free-text hallucination strings.",
        "",
    ]

    metadata: dict[str, object] = {
        "dataset": "compound-deception-ansari",
        "subset": f"ansari{limit}",
        "source": "GPTZero NeurIPS 2025 public table, referenced by Ansari (2026)",
        "source_url": SOURCE_DOC_URL,
        "retrieved_on": today,
        "citation_count": len(subset),
        "citations": {},
    }

    for idx, row in enumerate(subset, start=1):
        key = f"ansari{limit}_{idx:03d}"
        paper = clean(row.get("Published Paper", ""))
        scan = clean(row.get("GPTZero Scan", ""))
        hallucination = clean(row.get("Example of Verified Hallucination", ""))
        comment = clean(row.get("Comment", ""))

        parts = [p.strip() for p in hallucination.split(". ") if p.strip()]
        author = parts[0] if parts else ""
        title = parts[1] if len(parts) > 1 else hallucination[:140]

        year_matches = re.findall(r"(?:19|20)\d{2}", hallucination)
        year = year_matches[-1] if year_matches else ""

        doi_match = re.search(r"10\.\d{4,9}/[^\s,;]+", hallucination, re.IGNORECASE)
        doi = doi_match.group(0).rstrip(".,;") if doi_match else ""

        arxiv_match = re.search(
            r"arXiv\s*:?\s*([0-9]{4}\.[0-9]{4,5}|[0-9]{7})",
            hallucination,
            re.IGNORECASE,
        )
        arxiv_id = arxiv_match.group(1) if arxiv_match else ""

        bib_lines.append(f"@misc{{{key},")
        if author:
            bib_lines.append(f"  author = {{{esc_bib(author)}}},")
        if title:
            bib_lines.append(f"  title = {{{esc_bib(title)}}},")
        if year:
            bib_lines.append(f"  year = {{{year}}},")
        if arxiv_id:
            bib_lines.append(f"  eprint = {{{arxiv_id}}},")
            bib_lines.append("  archivePrefix = {arXiv},")
        if doi:
            bib_lines.append(f"  doi = {{{doi}}},")
        bib_lines.append(f"  note = {{{esc_bib(hallucination)}}}")
        bib_lines.append("}")
        bib_lines.append("")

        metadata["citations"][key] = {
            "ground_truth": "invalid",
            "fabrication_type": "mixed",
            "source_paper_title": paper,
            "gptzero_scan": scan,
            "hallucinated_citation_text": hallucination,
            "comment": comment,
            "source_row": idx,
            "source": "GPTZero table row",
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    bib_file.write_text("\n".join(bib_lines), encoding="utf-8")
    meta_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    readme_file.write_text(
        "\n".join(
            [
                f"# Compound Deception (Ansari) - ansari{limit} Seed Dataset",
                "",
                f"This dataset is a {limit}-entry subset derived from the public GPTZero NeurIPS 2025 hallucination table referenced by Ansari (2026).",
                "",
                f"- Source sheet: {SOURCE_DOC_URL}",
                f"- Retrieved: {today}",
                f"- Included entries: first {limit} rows from the 100-row public table snapshot",
                "",
                "Files:",
                f"- ansari{limit}.bib: BibTeX-formatted @misc entries with extracted title/author/year when possible",
                "- metadata.json: per-entry ground truth and provenance metadata",
                "- gptzero_neurips_100_source.csv: source snapshot for reproducibility",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return bib_file, snapshot_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50, help="Number of rows to include (1-100)")
    parser.add_argument(
        "--output-dir",
        default="datasets/compound-deception-ansari",
        help="Output directory for generated files",
    )
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 100:
        raise SystemExit("--limit must be between 1 and 100")

    with urlopen(SOURCE_SHEET_URL) as resp:
        csv_text = resp.read().decode("utf-8")

    rows = list(csv.DictReader(csv_text.splitlines()))
    if not rows:
        raise SystemExit("No rows found in source sheet")

    output_dir = Path(args.output_dir)
    bib_file, snapshot_file = build_files(rows, args.limit, output_dir)
    snapshot_file.write_text(csv_text, encoding="utf-8")

    print(f"Generated {args.limit} entries")
    print(f"BibTeX: {bib_file}")
    print(f"CSV snapshot: {snapshot_file}")


if __name__ == "__main__":
    main()
