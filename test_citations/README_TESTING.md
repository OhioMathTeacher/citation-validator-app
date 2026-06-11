# Citation Validator — Testing Infrastructure Guide
**Last updated:** April 2026

This document covers what test data we have, how the test runner works, and how to expand the test suite.

---

## Current Test Inventory

### Synthetic test data (785 citations)

```
test_citations/
├── real_citations/                       # Ground truth: VALID
│   ├── arxiv_cs_2024/
│   │   ├── arxiv_2604.05875.bib         # 205 citations from arXiv paper
│   │   └── arxiv_2604.05952.bib         # 80 citations from arXiv paper
│   └── crossref_random/
│       ├── crossref_sample_0001.bib     # 50 random CrossRef papers
│       └── crossref_sample_0002.bib     # 50 random CrossRef papers
│
├── false_negative_tests/                 # Ground truth: INVALID
│   ├── frankenstein/                    # Real parts, wrong combinations
│   │   ├── frankenstein_0001.bib        # 50 citations
│   │   ├── frankenstein_0002.bib        # 50 citations
│   │   └── ground_truth_frankenstein.json
│   ├── stolen_doi/                      # Real DOIs, fake metadata
│   │   ├── stolen_doi_0001.bib          # 50 citations
│   │   ├── stolen_doi_0002.bib          # 50 citations
│   │   └── ground_truth_stolen_doi.json
│   ├── plausible/                       # Completely fake, looks real
│   │   ├── plausible_0001.bib           # 50 citations
│   │   ├── plausible_0002.bib           # 50 citations
│   │   └── ground_truth_plausible.json
│   └── nonsense/                        # Obvious anomalies
│       ├── nonsense_0001.bib            # 50 citations
│       ├── nonsense_0002.bib            # 50 citations
│       └── ground_truth_nonsense.json
│
├── false_positive_tests/                 # Ground truth: VALID (edge cases)
│   └── (empty — see roadmap below)
│
└── nature_article_refs.bib              # 10 refs from the Nature article
```

**Total: 785 citations | 385 real (49%) | 400 fake (51%)**

### Published benchmark data (incoming)
See `datasets/` directory (being populated). These are external ground-truth datasets from published research — see `TEST_DESIGN.md` for full descriptions of each source.

---

## Running the Test Suite

### Quick sanity check
```bash
cd test_citations/
python3 run_all_tests.py --limit 20
```

### Full synthetic test suite (785 citations, ~10 min)
```bash
python3 run_all_tests.py --output test_results_full.json
```

### Target specific categories
```bash
# Only real citations (false positive testing)
python3 run_all_tests.py --test-dirs real_citations/

# Only fake citations (false negative testing)
python3 run_all_tests.py --test-dirs false_negative_tests/

# Specific fabrication type
python3 run_all_tests.py --test-dirs false_negative_tests/frankenstein/
```

### How the test runner works
The test runner (`run_all_tests.py`) imports the validator as a Python library to get per-citation results. For each `.bib` file:
1. Determines expected ground truth from directory structure (`real_citations/` → VALID, `false_negative_tests/` → INVALID)
2. Runs the validator on every citation in the file
3. Classifies each citation individually as TP/TN/FP/FN
4. Aggregates into precision, recall, F1, FPR, FNR

Results are printed to stdout and saved as JSON.

---

## Generating More Synthetic Test Data

### More real citations (CrossRef API)
```bash
# Random sample across all disciplines
python3 download_crossref_sample.py 500 real_citations/crossref_random/

# Filter by date or type
python3 download_crossref_sample.py 1000 real_citations/crossref_recent/ 'from-pub-date:2023'
python3 download_crossref_sample.py 1000 real_citations/crossref_older/ 'from-pub-date:2010,until-pub-date:2020'
```

### More fake citations (synthetic generator)
```bash
# One type at a time
python3 generate_fake_citations.py --type frankenstein --count 100 --output false_negative_tests/frankenstein/
python3 generate_fake_citations.py --type stolen_doi   --count 100 --output false_negative_tests/stolen_doi/
python3 generate_fake_citations.py --type plausible    --count 100 --output false_negative_tests/plausible/
python3 generate_fake_citations.py --type nonsense     --count 100 --output false_negative_tests/nonsense/

# All types at once (splits count evenly)
python3 generate_fake_citations.py --type all --count 400 --output false_negative_tests/
```

### From arXiv papers
```bash
python3 extract_citations_from_arxiv.py 2604.05875/   # specific paper folder
python3 extract_citations_from_arxiv.py --all          # all paper folders in directory
```

---

## Adding Published Benchmark Datasets

These need to be populated from the source papers (network access required). Each goes under `datasets/` with a `.bib` file and a sidecar `metadata.json` containing per-citation ground truth labels.

See `TEST_DESIGN.md` for full descriptions and data availability for each source.

| Dataset | Source | Status |
|---------|--------|--------|
| Compound Deception (Ansari) | arXiv:2602.05930 | Pending |
| HalluCitation (Sakai et al.) | arXiv:2601.18724 Appendix B | Pending |
| BibTeX Hallucinations benchmark (Rao & Callison-Burch) | arXiv:2604.03159 | Pending |
| GhostCite real citation corpus | arXiv:2602.06718 | Pending |
| Nature article refs | `nature_article_refs.bib` | Partial (needs full titles/DOIs) |

To run tests against a published benchmark once populated:
```bash
python3 run_all_tests.py --test-dirs ../datasets/compound-deception-ansari-2026/
```

---

## False Positive Edge Cases (Planned)

The `false_positive_tests/` directory is currently empty. High priority categories to populate:

| Category | Why it's tricky | How to get it |
|----------|-----------------|---------------|
| DataCite DOIs (Zenodo, Figshare) | Not in CrossRef; our DOI resolver fallback handles these, but it's worth verifying | Search Zenodo for any dataset with a DOI |
| Pre-2000 papers | No DOIs, OpenAlex coverage patchy | Manual BibTeX from old literature |
| Non-English papers | Unicode in titles/authors can trip up tokenization | Search OpenAlex with `language:fr` etc. |
| Very long author lists | ≥20 authors; some heuristics misbehave | CERN physics papers commonly have these |
| Retracted papers | Exist in CrossRef but are scientifically invalid | CrossRef marks them; test that we handle gracefully |
| arXiv version ambiguity | v1 DOI vs v2 DOI of same paper | Any frequently revised arXiv preprint |

---

## Performance Targets

| Metric | Target | Current Status |
|--------|--------|----------------|
| False Positive Rate | < 5% | Not yet measured post-bugfix |
| False Negative Rate | < 10% | Not yet measured post-bugfix |
| F1 Score | > 0.92 | Not yet measured post-bugfix |
| Test corpus size | 10,000+ | 785 synthetic (expanding) |

The 9 bug fixes in April 2026 are expected to significantly improve all metrics, particularly FNR (the OpenAlex and title comparison fixes target the biggest false negative sources) and FPR (the JS status logic fix and DOI confirmation protection reduce false flags). A full re-evaluation against the test suite is the next priority.

---

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `run_all_tests.py` | Main test runner — evaluates validator against ground truth |
| `generate_fake_citations.py` | Creates synthetic fake citations (4 types) |
| `download_crossref_sample.py` | Downloads random real citations from CrossRef |
| `extract_citations_from_arxiv.py` | Extracts citations from downloaded arXiv source files |
| `download_scholar_citations.py` | Google Scholar interface (limited by rate limits) |
| `generate_false_positive_tests.py` | Generates tricky real citations (DataCite, pre-DOI era, etc.) |
