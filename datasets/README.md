# Datasets

Datasets built here, and everything in `../results/`, are **CC BY 4.0** — see
[LICENSE](LICENSE). The code is licensed separately and more restrictively.
The third-party data below is not ours to license and is not redistributed.

Eight datasets back the evaluation: three of known-real citations, which measure
the false-positive rate, and five of known-fabricated ones, which measure
detection. Six were built here and are ours to license. **Two are other
people's, and this repository redistributes neither:**

- **CiteAudit real-world group** — Kaiwen Shi, Weixiang Sun, Zheyuan Zhang,
  Lichao Sun, Nitesh V. Chawla and Yanfang Ye ([arXiv:2602.23452](https://arxiv.org/abs/2602.23452)).
- **Ansari 100** — derived from GPTZero's public table of NeurIPS 2025
  hallucinations, which Ansari (2026) references. GPTZero owns the table;
  Ansari is the paper that points to it.

## Correction, 2026-08-11

**Between April and 11 August 2026 that claim was not true of this repository.**
The two datasets above were withheld from `datasets/`, as described, but the
per-citation JSON under `results/` carried each citation's `fields` — author,
title, identifier and the original note — so both corpora were published
through the results instead. 48 files, 28,685 citation records. The sentence
above about `../results/` being CC BY 4.0 therefore applied this project's
licence to a compilation that is not ours to license.

It was found by an audit of what the repository actually contains rather than
what it says, which is the method the accompanying paper argues for, applied
here to its own artefact.

**Fixed forward:** `scripts/strip_restricted_results.py` removes citation text
from results belonging to any dataset whose source `.bib` is withheld, keeping
the verdicts, the registry that settled each lookup, and the AI judgements, so
every result remains checkable. `tests/test_no_restricted_data.py` fails if it
comes back. Saved UI exports and editor backups under `results/` are no longer
tracked, having slipped past the first two passes of the stripper.

**Not fixed, and cannot be:** releases already archived on Zenodo (v1.5.x and
v1.6.0) contain the unredacted files. Zenodo records are immutable by design.
Git history likewise still contains them; rewriting it would break the
`/blob/v1.6.0/` permalinks the paper cites, which we judged the worse trade.
Anyone wanting either dataset should go to its source, linked above.

Those two sources supply four of the directories listed below, because CiteAudit
is cut three ways (full benchmark, real-world group, balanced subset).
Permission is owed per owner, not per derived file.

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
entries whose citation text disagrees with the record its DOI points to.
**No reply as of 2026-08-05.** Nothing here changes unless one arrives.

No request has gone to the owners of the Ansari 100. It derives from a public
GPTZero table that states no terms of reuse, and there is no obvious
corresponding author to write to; it stays fetch-only for that reason.

## Attribution

- **CiteAudit** — Shi, Sun, Zhang, Sun, Chawla & Ye (2026), arXiv:2602.23452,
  <https://github.com/shiiiikw/CiteAudit>. 9,442 human-labelled citations; this
  project uses the `realworld` group (3,356) and a balanced 500-entry subset.
- **Ansari 100** — derived from the public GPTZero NeurIPS 2025 hallucination
  table referenced by Ansari (2026). 100 real fabrications that passed peer
  review.
