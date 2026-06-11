# CiteCheck

A free, open citation validator. It checks each reference in a bibliography
against public scholarly databases (CrossRef, OpenAlex, Semantic Scholar) and
reports whether the citation can be verified — without treating "I can't verify
this" as "this is fake."

CiteCheck is the tool described in a paper currently under review. This repository
holds the complete code, the evaluation datasets, and the experiment logs behind
every number in that paper.

## What it does

- **Deterministic pass (default, no AI, no account, no cost).** When a citation
  has a DOI, CiteCheck resolves it and cross-checks the metadata; when it doesn't,
  it searches the open databases by title. Each citation is labelled
  *valid*, *warning* (unverifiable — **not** an accusation), *suspicious*, or *invalid*.
- **Optional AI second pass.** Routes only the *warning* citations to a language
  model (Gemini / Claude / GPT-4o / Llama) for a second opinion. Off by default.

The guiding principle: **a citation that cannot be verified is not the same as a
citation that is fabricated.** CiteCheck is built to keep those two apart.

## Layout

```
scripts/         the validator (citation_validator.py) + experiment drivers + requirements
datasets/        the eight evaluation datasets (real and fabricated citation sets)
results/         experiment logs and per-run roll-ups (results/experiments/experiment_log.jsonl)
test_citations/  small worked examples
tests/           unit tests
```

## Quick start

```bash
pip install -r scripts/requirements.txt
python3 scripts/citation_validator.py your-bibliography.bib        # deterministic
python3 scripts/citation_validator.py your-bibliography.bib --ai   # + AI second pass (needs a free API key)
```

See `scripts/README.md` for full options and API-key setup.

## Reproducing the paper's results

```bash
python3 scripts/run_fp_baseline.py            # false-positive baseline (real citations)
python3 scripts/run_benchmark.py              # fabricated-citation detection
python3 scripts/run_citeaudit_validation.py   # external CiteAudit benchmark
```

Each run writes a timestamped record under `results/`, so every figure in the
paper traces back to its source data. Reproduction needs only Python 3.x, an
internet connection, and (for the AI pass) a free-tier API key.

## License

**GNU AGPL-3.0 with the Commons Clause** (see [LICENSE](LICENSE)). You are free to
use, read, modify, share, and self-host CiteCheck for any purpose — and any
networked version must publish its source — but you may **not sell** it. Verification
infrastructure for the scholarly record should stay free and open; this license
keeps it that way.
