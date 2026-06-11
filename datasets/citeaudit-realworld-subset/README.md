# CiteAudit — Human-Validated Citation Benchmark

Human-validated citation benchmark (Yuan et al., 2026). Each entry is a free-text reference string labelled real/fake by human annotators. The 'realworld' group is independently sourced from published papers; the 'generated' group is synthetically constructed. This dataset is the 'realworld' group only. Balanced random subset: up to 250 per class (seed 42).

- **Source:** arXiv:2602.23452 (github.com/shiiiikw/CiteAudit)
- **Retrieved:** 2026-05-21
- **Citations:** 500 (250 real, 250 fake)

## Files

- `citeaudit-realworld-subset.bib` — BibTeX entries (parsed from free-text strings)
- `metadata.json` — per-citation ground truth and provenance
