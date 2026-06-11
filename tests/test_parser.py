"""Tests for the BibTeX parser in citation_validator.py."""

import sys
from pathlib import Path

# Allow importing from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from citation_validator import CitationValidator


def _parse(bibtex_string):
    """Helper: parse a BibTeX string and return entries."""
    v = CitationValidator()
    return v._parse_bibtex_string(bibtex_string)


# ── Basic parsing ──────────────────────────────────────────────────────────

def test_single_article():
    bib = """@article{doe2024,
  author = {Doe, Jane},
  title = {A Simple Test},
  journal = {Journal of Testing},
  year = {2024}
}"""
    entries = _parse(bib)
    assert len(entries) == 1
    e = entries[0]
    assert e["type"] == "article"
    assert e["key"] == "doe2024"
    assert e["fields"]["author"] == "Doe, Jane"
    assert e["fields"]["title"] == "A Simple Test"
    assert e["fields"]["year"] == "2024"


def test_multiple_entries():
    bib = """@article{a, title = {First}}
@inproceedings{b, title = {Second}}
@book{c, title = {Third}}"""
    entries = _parse(bib)
    assert len(entries) == 3
    assert [e["key"] for e in entries] == ["a", "b", "c"]


def test_nested_braces():
    bib = r"""@article{nested,
  title = {A {Nested {Brace}} Test},
  author = {Smith, J.}
}"""
    entries = _parse(bib)
    assert len(entries) == 1
    assert entries[0]["fields"]["title"] == "A {Nested {Brace}} Test"


def test_quoted_values():
    bib = '@article{quoted, title = "Quoted Value", year = "2024"}'
    entries = _parse(bib)
    assert len(entries) == 1
    assert entries[0]["fields"]["title"] == "Quoted Value"
    assert entries[0]["fields"]["year"] == "2024"


def test_bare_numeric_values():
    bib = "@article{bare, year = 2024, volume = 10}"
    entries = _parse(bib)
    assert len(entries) == 1
    assert entries[0]["fields"]["year"] == "2024"
    assert entries[0]["fields"]["volume"] == "10"


def test_empty_string():
    entries = _parse("")
    assert entries == []


def test_field_names_case_insensitive():
    bib = "@article{casetest, Title = {Hello}, AUTHOR = {World}}"
    entries = _parse(bib)
    assert "title" in entries[0]["fields"]
    assert "author" in entries[0]["fields"]


# ── Jaccard similarity ─────────────────────────────────────────────────────

def test_jaccard_identical():
    assert CitationValidator._jaccard_words("hello world", "hello world") == 1.0


def test_jaccard_no_overlap():
    assert CitationValidator._jaccard_words("cat dog", "fish bird") == 0.0


def test_jaccard_partial():
    sim = CitationValidator._jaccard_words("deep learning models", "deep learning for NLP")
    # shared: {deep, learning} = 2, union: {deep, learning, models, for, nlp} = 5
    assert abs(sim - 2 / 5) < 0.01


def test_jaccard_case_insensitive():
    assert CitationValidator._jaccard_words("Hello World", "hello world") == 1.0


def test_jaccard_empty():
    assert CitationValidator._jaccard_words("", "hello") == 0.0
    assert CitationValidator._jaccard_words("", "") == 0.0
