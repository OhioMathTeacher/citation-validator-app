# Citation Validator — Scientific Testing Methodology
**Last updated:** April 2026

This document describes the scientific principles behind how we test the validator, our fabrication taxonomy, how our categories map to published research, and our plan for integrating external benchmark datasets.

---

## Testing Philosophy

A citation validator has four types of outcomes, and all four matter:

| Outcome | Meaning | Priority |
|---------|---------|----------|
| **True Positive (TP)** | Real citation correctly validated | — |
| **True Negative (TN)** | Fake citation correctly flagged | — |
| **False Positive (FP)** | Real citation incorrectly flagged | High concern — creates friction for honest authors |
| **False Negative (FN)** | Fake citation passes undetected | High concern — the whole point of the tool |

We optimize for **low FPR** (don't harass real authors) while maintaining **low FNR** (catch actual hallucinations). An F1 score > 0.92 is our target, but we care more about the individual rates than the aggregate.

**Critical evaluation principle:** We evaluate per-citation, not per-file. A file with 50 fakes where 1 gets flagged is not a "caught" file — it's 49 false negatives. Our test runner (updated April 2026) now correctly attributes every individual citation.

---

## Our Fabrication Taxonomy

We use four categories of synthetic fake citations, each targeting a different failure mode of the validator:

### Category 1: Frankenstein Citations
**Definition:** Real components from multiple papers combined incorrectly.
Examples:
- Real author name + fabricated title + real journal
- Real title + wrong author + wrong year
- Metadata from Paper A mixed with DOI from Paper B

**Why they're hard to catch:** Each individual component may check out. The DOI may resolve; the author may exist; the journal may be real. The validator must compare the full set of metadata against verified data to spot the inconsistency.

**Corresponds to:** Ansari's "Partial Attribute Corruption" (27% of real-world NeurIPS hallucinations)

### Category 2: Stolen DOI
**Definition:** A real, valid DOI paired with completely fabricated metadata.
Examples:
- Real DOI resolves to Paper A, but title/author/year are from Paper B or entirely invented
- Designed to exploit validators that stop at "DOI resolves → valid"

**Why they're hard to catch:** The DOI check passes. Only a metadata comparison catches it. Our fix (April 2026) ensures title Jaccard similarity is checked after DOI resolution.

**Corresponds to:** Ansari's "Identifier Hijacking" (4% of NeurIPS hallucinations) — though likely underrepresented in the wild since it requires knowing a real DOI

### Category 3: Plausible Fakes
**Definition:** Completely fabricated citations that look entirely plausible — realistic author names, realistic journal names, realistic titles, realistic years. No real component.

**Why they're hard to catch:** Nothing is technically wrong with the format. Detection relies on the DOI not resolving and no OpenAlex match being found — which also applies to legitimate papers not yet indexed.

**Corresponds to:** Ansari's "Total Fabrication" (66% of NeurIPS hallucinations) — the most common real-world type

### Category 4: Nonsense
**Definition:** Citations with obvious anomalies — future publication years, invalid DOI formats, journal names that don't exist, impossibly old dates.

**Why they exist in the test suite:** A baseline sanity check. If the validator can't catch these, something is seriously wrong.

**Corresponds to:** Ansari's "Placeholder Hallucination" (2%) and some of "Total Fabrication"

---

## Published Research Benchmarks

Five major research groups have published benchmark data on citation hallucinations. These provide external ground truth independent of our synthetic test data.

### 1. HalluCitation — Sakai, Kamigaito & Watanabe (arXiv:2601.18724)
**What they did:** Analyzed all papers at ACL, NAACL, and EMNLP 2024 and 2025 — main conference, Findings, and workshops. Manually verified hallucinated references.

**Key finding:** 20 papers with hallucinated citations in 2024 → 275 in 2025 (13× increase in one year).

**Data available:** Appendix B lists the specific hallucinated papers with their hallucinated references.

**Methodology:** Exploited the assumption that "the majority of citations are correct" to identify outliers, then manually verified each candidate.

**Value for us:** Real-world confirmed hallucinations from NLP conferences with known ground truth. The hardest type to detect — they're plausible fakes written by researchers, not our synthetic generators.

### 2. Compound Deception — Ansari (arXiv:2602.05930)
**What they did:** Analyzed 100 AI-generated hallucinated citations in 53 accepted NeurIPS 2025 papers.

**Key finding:** Taxonomy of 5 failure modes; these citations evaded detection by 3-5 expert reviewers per paper.

**Data available:** The 100 citations are described in the paper with their taxonomy classifications.

**Taxonomy breakdown:**
- Total Fabrication: 66%
- Partial Attribute Corruption: 27%
- Identifier Hijacking: 4%
- Placeholder Hallucination: 2%
- Semantic Hallucination: 1%

**Value for us:** The most detailed taxonomy of real-world hallucination types. Our four categories map directly onto these five. Perfect for calibrating our detector against real cases that fooled expert humans.

### 3. BibTeX Citation Hallucinations — Rao & Callison-Burch (arXiv:2604.03159)
**What they did:** Built a 931-paper benchmark across 4 scientific domains and 3 citation tiers (popular, low-citation, recent post-cutoff). Tested GPT-5, Claude Sonnet 4.6, and Gemini-3 Flash on generating BibTeX entries, scoring 9 fields each with a 6-way error taxonomy.

**Key findings:**
- Only 50.9% of LLM-generated BibTeX entries fully correct overall
- Accuracy drops 27.7pp from popular to recent papers (LLMs rely on memorized training data)
- Their `clibib` tool (deterministic BibTeX retrieval via Zotero + CrossRef) improved accuracy to 78.3% fully correct

**Data available:** Full benchmark and error taxonomy released publicly. ~23,000 field-level observations.

**Value for us:** The most rigorous existing benchmark. Has field-level ground truth (not just "valid/invalid" but which specific fields are wrong). Lets us test our metadata comparison logic specifically.

### 4. GhostCite / CiteVerifier (arXiv:2602.06718)
**What they did:** Two analyses: (1) evaluated 13 LLMs on 375,440 citations across 40 domains; (2) analyzed 2.2M real citations from 56,381 papers published 2020-2025.

**Key findings:**
- LLM hallucination rates: 14%–95% depending on the model
- In real published papers: 604/56,381 papers (1.07%) had invalid citations, with 80.9% increase in 2025
- Evidence of hallucination propagation — fabricated citations get re-cited by other LLMs

**Data available:** CiteVerifier open-source framework.

**Value for us:** The 2.2M real citation corpus is a massive real-world baseline for false-positive testing. The LLM evaluation data shows how different models hallucinate differently.

### 5. CheckIfExist — Abbonato (arXiv:2602.15871)
**What they did:** Built an open-source citation validator using CrossRef, Semantic Scholar, and OpenAlex — structurally very similar to our tool.

**Data available:** Full source code at github.com/zabbonat/References-Validation (MIT license).

**Value for us:** An apples-to-apples comparison target. We can run the same inputs through both tools and compare detection rates. Also: Semantic Scholar is a third database we could add as a fallback.

### 6. The Case of the Mysterious Citations — Bienz, Pearson & Garcia de Gonzalo (arXiv:2602.05867)
**What they did:** Examined proceedings of 4 major HPC conferences comparing 2021 vs. 2025 papers.

**Key finding:** 0% of 2021 papers had hallucinated citations; 2-6% of 2025 papers did. This is the source of Nature's headline figure.

**Value for us:** Longitudinal data showing the problem emerging. Good for context and for testing against domain-specific (HPC/supercomputing) citations.

---

## Evaluation Metrics

### Primary metrics
- **False Positive Rate (FPR)** — real citations incorrectly flagged. Target: < 5%
- **False Negative Rate (FNR)** — fake citations that pass. Target: < 10%
- **F1 Score** — harmonic mean of precision and recall. Target: > 0.92

### Why FPR matters as much as FNR
A tool with 0% FNR but 30% FPR is useless — editors will ignore it after being burned by false alarms too many times. We need both to be low. The right tradeoff: we accept slightly higher FNR to keep FPR low, because false positives destroy trust.

### Evaluation granularity
All metrics are computed **per citation**, not per file. A batch file with 50 fake citations where only 1 is caught contributes 1 TN and 49 FNs to the metrics — not 1 TN.

### Confusion matrix shape
For each citation, we classify:
- Is the ground truth **VALID** or **INVALID**?
- Did the validator say **flagged** (suspicious/invalid) or **not flagged** (valid/warning)?

"Warning" status is considered **not flagged** — it's informational, not an accusation of fabrication.

---

## Ground Truth Methodology

### Our synthetic test data
Ground truth is encoded in the directory structure:
- `real_citations/` → VALID (real papers from CrossRef and arXiv)
- `false_negative_tests/` → INVALID (synthetically generated fakes)

Every synthetic fake was generated with a documented process and checked to confirm the DOI/title/author combination does not actually exist.

### External benchmark data
For published benchmarks, ground truth comes from the original researchers' manual verification. We store it in per-dataset sidecar JSON files (see `datasets/` directory structure below).

### Sidecar metadata format
```json
{
  "cite_key_here": {
    "ground_truth": "INVALID",
    "fabrication_type": "frankenstein",
    "source_paper": "Ansari 2602.05930",
    "confidence": "confirmed",
    "notes": "Real author (LeCun) + fabricated title + real journal (JMLR)"
  }
}
```

---

## Dataset Directory Structure (Target)

```
datasets/
├── manifest.json                        ← master index of all datasets
├── our-synthetic/
│   ├── real/
│   │   ├── arxiv_cs_2024.bib
│   │   ├── crossref_random.bib
│   │   └── metadata.json
│   └── fake/
│       ├── frankenstein.bib
│       ├── stolen_doi.bib
│       ├── plausible.bib
│       ├── nonsense.bib
│       └── metadata.json
├── hallucitation-sakai-2026/
│   ├── hallucinated.bib                 ← from Appendix B
│   └── metadata.json
├── compound-deception-ansari-2026/
│   ├── fabricated_neurips.bib
│   └── metadata.json                    ← includes taxonomy labels
├── bibtex-hallucinations-rao-2026/
│   ├── benchmark_931.bib
│   └── metadata.json                    ← field-level error annotations
├── ghostcite-2026/
│   ├── real_papers_sample.bib
│   └── metadata.json
└── nature-article-refs/
    ├── refs.bib
    └── metadata.json
```

The `manifest.json` describes each dataset:
```json
[
  {
    "id": "compound-deception-ansari-2026",
    "name": "Compound Deception at NeurIPS 2025",
    "authors": "Ansari (2026)",
    "arxiv": "2602.05930",
    "description": "100 AI-fabricated citations found in 53 accepted NeurIPS 2025 papers",
    "citation_count": 100,
    "ground_truth_available": true,
    "breakdown": {
      "real": 0,
      "fake": 100,
      "fabrication_types": ["total_fabrication", "partial_corruption", "identifier_hijacking"]
    }
  }
]
```

---

## Scientific Rigor Checklist

- [x] Per-citation evaluation (not per-file)
- [x] Ground truth labels for all synthetic data
- [x] Balanced test set (49% real, 51% fake)
- [x] Reproducible (scripts + data in version control)
- [x] Documented methodology (this file)
- [x] Multiple fabrication types tested independently
- [ ] Integration with published external benchmarks
- [ ] Cross-domain testing (CS, biology, medicine, HPC)
- [ ] Statistical confidence intervals on metrics
- [ ] Cross-tool comparison (vs. CheckIfExist)
