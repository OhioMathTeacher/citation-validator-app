# CiteCheck

A free, open citation validator. It checks each reference in a bibliography
against public scholarly databases (CrossRef, OpenAlex, Semantic Scholar) and
reports whether the citation can be verified — without treating "I can't verify
this" as "this is fake."

This repository holds the complete code, the evaluation datasets, and the
experiment logs behind every number in the papers that describe the tool. It is
also the engine behind the hosted version, which needs no installation:

**<https://huggingface.co/spaces/ojsm/citation-validator>**

("CiteCheck" was a pseudonym used while the technical paper was under
double-blind review. The tool's name is **Citation Validator**; the repository
keeps the old name so existing links continue to work.)

## What it does

- **Deterministic pass (default, no AI, no account, no cost).** When a citation
  has a DOI, it resolves the DOI and cross-checks the registry record against the
  author, title, and year as written; when there is no DOI, it searches the open
  databases by title. Each citation is labelled *valid*, *warning*, *suspicious*,
  or *invalid*.
- **Optional AI second pass.** Routes only the flagged citations to a language
  model (Gemini / Claude / GPT-4o / Llama) for a second opinion. Off by default,
  and it is never asked whether a reference with a resolving DOI is fabricated —
  the registry has already settled that.

The guiding principle: **a citation that cannot be verified is not the same as a
citation that is fabricated.** The tool is built to keep those two apart, and the
interface says so out loud. A reference whose registry record contradicts the
citation is shown as a **discrepancy**; a reference that could not be checked at
all is shown as **unverified**, in grey, with a note that this is not a finding
against it. Those are different claims and they never share a colour.

## Layout

```
scripts/         the validator (citation_validator.py) + experiment drivers + requirements
web/             the browser interface served by scripts/webapp.py
datasets/        the eight evaluation datasets (real and fabricated citation sets)
results/         experiment logs and per-run roll-ups (results/experiments/experiment_log.jsonl)
test_citations/  small worked examples
tests/           unit tests
VERSION          the version reported by the UI, /version, and every exported report
```

## Quick start

```bash
pip install -r scripts/requirements.txt
python3 scripts/citation_validator.py your-bibliography.bib        # deterministic
python3 scripts/citation_validator.py your-bibliography.bib --ai   # + AI second pass (needs a free API key)
```

To run the web interface locally:

```bash
python3 scripts/webapp.py            # then open http://localhost:5000
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
