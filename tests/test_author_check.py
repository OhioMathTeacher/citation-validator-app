"""Regression tests for the author and date checks on the DOI path.

Every case here is drawn from a citation the tool got wrong at some point.
The four "silenced" cases were correctly cited work the check accused; the
four "firing" cases are real discrepancies confirmed by hand against the
registry. Together they fix the boundary the check has to hold: report a
mismatch, never manufacture one.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from citation_validator import CitationValidator


def _authors(*pairs):
    return [{"given": g, "family": f} for g, f in pairs]


def _check(bib_author, registry):
    return CitationValidator(use_ai=False)._check_authors_against_registry(
        bib_author, registry)


# ── Must stay silent: correctly cited work ─────────────────────────────────

def test_curly_apostrophe_matches_straight():
    """O'Donnell with U+2019 is the same surname as the registry's."""
    assert _check("O’Donnell, Ciaran and Smith, Jane",
                  _authors(("Ciaran", "O'Donnell"), ("Jane", "Smith"))) == []


def test_diacritics_folded():
    assert _check("Blomhoj, Morten", _authors(("Morten", "Blomhøj"),
                                              ("Anna", "Jensen"))) == []


def test_given_name_not_matched_across_the_author_list():
    """'Jianwei Li' is not a misspelling of a 'Tianwen' seven names away.

    The check once searched the whole author string for a near-miss, so on a
    long list some other author's given name always landed within edit
    distance of this one.
    """
    registry = _authors(
        ("Jianwei", "Li"), ("Tianwen", "Zhao"), ("Chang", "Liu"),
        ("Zhang", "Wei"), ("Ming", "Chen"), ("Hao", "Wu"))
    bib = ("Li, Jianwei and Zhao, Tianwen and Liu, Chang and "
           "Wei, Zhang and Chen, Ming and Wu, Hao")
    assert _check(bib, registry) == []


def test_organisational_author_is_not_accused():
    """A parsing artifact names nobody; there is nothing to corroborate.

    Reporting a missing first author here would blame the author for a
    bibliography the tool itself failed to parse.
    """
    assert _check("Molecular Transformer",
                  _authors(("Philippe", "Schwaller"), ("Teodoro", "Laino"))) == []


def test_initials_only_stays_silent():
    """'J. Smith' is a citation style, not a misspelling of 'Jane'."""
    assert _check("Smith, J. and Doe, A.",
                  _authors(("Jane", "Smith"), ("Alan", "Doe"))) == []


# ── Must fire: real discrepancies, all confirmed against Crossref ──────────

def test_misspelled_surname_reported():
    """Greg Foley's list: 'Pardis' for 'Paradis'."""
    warnings = _check("Pardis, Audrey and Wilson, Mark",
                      _authors(("Audrey", "Paradis"), ("Mark", "Wilson")))
    assert warnings
    assert any("paradis" in w.lower() for w in warnings)


def test_misspelled_given_name_reported():
    """'Younggon' for 'Yonggon' -- adjacent to its own surname, so in window."""
    warnings = _check("Bae, Younggon and Lee, Soo",
                      _authors(("Yonggon", "Bae"), ("Soo", "Lee")))
    assert warnings


def test_wrong_given_name_form_reported():
    """'Michelle' for 'Michèle' survives accent folding as a real difference."""
    warnings = _check("Artigue, Michelle and Douady, Regine",
                      _authors(("Michèle", "Artigue"), ("Regine", "Douady")))
    assert warnings


def test_missing_first_author_reported_when_others_corroborate():
    """The other registry surnames are present, so the omission is real."""
    warnings = _check("Jiang, Zhimeng and Rakesh, Vineeth",
                      _authors(("Chia-Yuan", "Chang"), ("Zhimeng", "Jiang"),
                               ("Vineeth", "Rakesh")))
    assert warnings
    assert any("chang" in w.lower() for w in warnings)


# ── arXiv records must carry a publication date ────────────────────────────

ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title type="html">ArXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2011.04006v1</id>
    <updated>2020-11-08T18:31:44Z</updated>
    <published>2020-11-08T18:31:44Z</published>
    <title>Long Range Arena: A Benchmark for Efficient Transformers</title>
    <author><name>Yi Tay</name></author>
    <author><name>Mostafa Dehghani</name></author>
  </entry>
</feed>
"""


def test_arxiv_record_reports_publication_year(monkeypatch):
    """Without a 'published' key the year check is skipped for every arXiv DOI.

    arXiv identifiers carry a YYMM prefix, so 2011.04006 -- posted November
    2020 -- invites a bibliography to record the year as 2011. That is a
    nine-year gap the tool has to see.
    """
    v = CitationValidator(use_ai=False)
    monkeypatch.setattr(v, "_http_get", lambda *a, **k: ARXIV_ATOM.encode())

    ok, record = v._validate_arxiv("2011.04006")

    assert ok
    assert record["published"]["date-parts"][0][0] == 2020


def test_arxiv_author_names_are_not_reversed(monkeypatch):
    """arXiv writes names given-first; the family name is the last token."""
    v = CitationValidator(use_ai=False)
    monkeypatch.setattr(v, "_http_get", lambda *a, **k: ARXIV_ATOM.encode())

    _, record = v._validate_arxiv("2011.04006")

    assert record["author"][0] == {"given": "Yi", "family": "Tay"}
