# Datasets

Eight datasets back the evaluation: three of known-real citations, which measure
the false-positive rate, and five of known-fabricated ones, which measure
detection. Five were built here. **Three come from other people, and this
repository does not redistribute them.**

## What is here, and what is fetched

| Dataset | Origin | In this repo |
|---|---|---|
| `ojsm-synthetic` (Frankenstein, Stolen DOI, Plausible, Nonsense) | built here | yes |
| real arXiv CS, CrossRef random, *Nature* article | collected here | yes |
| `citeaudit-benchmark`, `citeaudit-realworld`, `citeaudit-realworld-subset` | Shi et al. | **fetched on demand** |
| `compound-deception-ansari` | GPTZero / Ansari | **fetched on demand** |

Rebuild the fetched sets with:

```bash
python3 scripts/import_citeaudit_dataset.py --fetch \
    --dataset-id citeaudit-realworld --source-type realworld \
    --output-dir datasets/citeaudit-realworld
python3 scripts/import_ansari_dataset.py --limit 100
```

Each importer prints the SHA-256 of the upstream file and warns if it differs
from the snapshot the published figures were computed against
(`0bf0a7b2…b1bae5` for CiteAudit, retrieved 2026-05-21). A rebuild from the
same upstream reproduces the derived BibTeX byte for byte apart from the
retrieval date stamp — verified 2026-08-04.

## Why they are fetched rather than mirrored

The CiteAudit repository carries no licence, which under GitHub's terms means
all rights are reserved. The Ansari set derives from a public Google Sheet whose
terms of reuse are unstated. Neither grants redistribution.

Mirroring them anyway would probably have gone unremarked. It would also have
been this project quietly helping itself to other researchers' work while
arguing that provenance in the scholarly record should be checkable — the exact
gap between what a tool claims and what it does that the accompanying paper is
about. Fetching costs one command and leaves the attribution where it belongs.

`results/` is unaffected: every experiment log is this project's own output and
stays in the repository, so each figure in the paper still traces to its source
run without needing anyone else's data.

## Licence request

**Sent 2026-08-04** to Yanfang Ye (yye7@nd.edu), corresponding author, cc
S. Asli Ozgun-Koca and Gregory Foley. Text as sent:
[`permission-request-citeaudit.txt`](permission-request-citeaudit.txt). It asks whether
redistribution with attribution is acceptable, and passes back three real-world
entries whose citation text disagrees with the record its DOI points to. Awaiting
a reply; nothing here changes unless one arrives.

## Attribution

- **CiteAudit** — Shi, Sun, Zhang, Sun, Chawla & Ye (2026), arXiv:2602.23452,
  <https://github.com/shiiiikw/CiteAudit>. 9,442 human-labelled citations; this
  project uses the `realworld` group (3,356) and a balanced 500-entry subset.
- **Ansari 100** — derived from the public GPTZero NeurIPS 2025 hallucination
  table referenced by Ansari (2026). 100 real fabrications that passed peer
  review.
