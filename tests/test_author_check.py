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
    """Discrepancies only — findings that count against a citation."""
    return CitationValidator(use_ai=False)._check_authors_against_registry(
        bib_author, registry)[0]


def _notes(bib_author, registry):
    """Coverage notes — what could not be checked. Never a finding."""
    return CitationValidator(use_ai=False)._check_authors_against_registry(
        bib_author, registry)[1]


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


# ── Named authors are verified as pairs, not as a bag of surnames ──────────

MODELSCOPE = _authors(("Jiuniu", "Wang"), ("Hangjie", "Yuan"), ("Dayou", "Chen"),
                      ("Yingya", "Zhang"), ("Xiang", "Wang"), ("Shiwei", "Zhang"))


def test_fabricated_authors_sharing_common_surnames_are_caught():
    """citeaudit_rw_2111: a real DOI wearing an invented author list.

    Cited as 'Ziqi Wang, Jing Zhang, and et al' for a paper by Jiuniu Wang,
    Hangjie Yuan, Dayou Chen, Yingya Zhang, Xiang Wang and Shiwei Zhang. Title,
    DOI, venue and year are all correct; only the people are wrong. Wang and
    Zhang both appear in the registry list, so a surname-only check passes it.
    """
    warnings = _check("Ziqi Wang, Jing Zhang, and et al", MODELSCOPE)
    assert warnings
    assert any("ziqi" in w.lower() for w in warnings)
    assert any("jing" in w.lower() for w in warnings)


def test_single_unrecognised_given_name_is_not_an_accusation():
    """'Bill' for 'William' is a familiar form, not a fabrication.

    One unmatched given name never fires; it takes a second to corroborate.
    """
    assert _check("Bill Smith and Robert Jones",
                  _authors(("William", "Smith"), ("Robert", "Jones"))) == []


def test_adjacent_given_name_is_attributed_to_the_right_surname():
    """In 'William Smith, Robert Jones', 'Robert' belongs to Jones, not Smith."""
    assert _check("William Smith, Robert Jones",
                  _authors(("William", "Smith"), ("Robert", "Jones"))) == []


def test_registry_initials_cannot_contradict_anything():
    """If the registry itself only has 'J.', there is nothing to compare."""
    assert _check("Ziqi Wang and Jing Zhang",
                  _authors(("J.", "Wang"), ("Y.", "Zhang"))) == []


# ── 'et al' is coverage, never a finding ───────────────────────────────────

def test_et_al_reports_coverage_not_suspicion():
    """An abbreviated list is correct practice; say what went unchecked."""
    warnings = _check("Jiuniu Wang, Hangjie Yuan, et al", MODELSCOPE)
    notes = _notes("Jiuniu Wang, Hangjie Yuan, et al", MODELSCOPE)
    assert warnings == []          # nothing held against the citation
    assert notes                   # but the gap is stated
    assert "et al" in notes[0]
    assert "2 of 6" in notes[0]


def test_no_et_al_means_no_coverage_note():
    assert _notes("Jiuniu Wang and Hangjie Yuan", MODELSCOPE) == []


def test_middle_initials_do_not_shift_given_names_onto_the_next_author():
    """Real case: the pair check's first draft invented three discrepancies.

    "Matthew M Botvinick, Todd S Braver, ..." -- the backward step lands on the
    middle initial, so an earlier version ran on into the next author and
    reported a 'Todd Botvinick', a 'Cameron Barch' and a 'Deanna Braver'.
    """
    registry = _authors(("Matthew M.", "Botvinick"), ("Todd S.", "Braver"),
                        ("Deanna M.", "Barch"), ("Cameron S.", "Carter"),
                        ("Jonathan D.", "Cohen"))
    bib = ("Matthew M Botvinick, Todd S Braver, Deanna M Barch, "
           "Cameron S Carter, and Jonathan D Cohen")
    assert _check(bib, registry) == []


def test_mixed_initial_styles_across_a_long_list_stay_silent():
    """Some authors carry middle initials, some do not. All correctly cited."""
    registry = _authors(("Timothy J.", "O'Donnell"), ("Alex", "Rubinsteyn"),
                        ("Marius", "Bonsack"), ("Angelika B.", "Riemer"),
                        ("Uri", "Laserson"), ("Jeff", "Hammerbacher"))
    bib = ("Timothy J. O’Donnell, Alex Rubinsteyn, Marius Bonsack, "
           "Angelika B. Riemer, Uri Laserson, and Jeff Hammerbacher")
    assert _check(bib, registry) == []


def test_multi_part_given_names_are_matched_on_any_part():
    """A citation may shorten a given name to any of its parts.

    All three were real false positives: 'Kumar Dhanda' reported against
    'Sandeep Kumar Dhanda', 'Ringel Morris' against 'Meredith Ringel Morris',
    'Yuan Chang' against 'Chia-Yuan Chang'. Comparing only the first token of
    the registered given name made every shortened form an impostor.
    """
    assert _check("Sandeep Kumar Dhanda, Swapnil Mahajan",
                  _authors(("Sandeep Kumar", "Dhanda"), ("Swapnil", "Mahajan"))) == []
    assert _check("Meredith Ringel Morris and Joon Sung Park",
                  _authors(("Meredith Ringel", "Morris"), ("Joon Sung", "Park"))) == []
    assert _check("Chia-Yuan Chang and Chin-Chia Michael Yeh",
                  _authors(("Chia-Yuan", "Chang"), ("Chin-Chia Michael", "Yeh"))) == []


def test_wrong_people_still_caught_after_the_multi_part_fix():
    """citeaudit_rw_2936: 'Hieu Pham' and 'Qin Yang' for Philip Pham, Liu Yang."""
    warnings = _check("Hieu Pham, Qin Yang",
                      _authors(("Philip", "Pham"), ("Liu", "Yang")))
    assert len(warnings) == 2


def test_registry_with_swapped_name_parts_does_not_convict_the_citation():
    """CrossRef holds the XJTU-SY bearing dataset surname-first.

    Its record gives 'WANG' as the given name and 'Biao' as the family name, so
    a perfectly correct "Biao Wang" in the citation read as an impostor. When
    every name part is present somewhere in the registry list, the two sides
    disagree about parsing, not about people.
    """
    registry = _authors(("LEI", "Yaguo"), ("HAN", "Tianyu"), ("WANG", "Biao"),
                        ("LI", "Naipeng"), ("YAN", "Tao"), ("YANG", "Jun"))
    bib = "Yaguo Lei, Tianyu Han, Biao Wang, Naipeng Li, Tao Yan, and Jun Yang"
    assert _check(bib, registry) == []


def test_repeated_surname_does_not_borrow_the_next_given_name():
    """'Tian Tian, Peng Gao' once produced a 'Peng Tian'."""
    assert _check("Peng Zhang, Hao Xu, Tian Tian, Peng Gao",
                  _authors(("Peng", "Zhang"), ("Hao", "Xu"),
                           ("Tian", "Tian"), ("Peng", "Gao"))) == []


def test_systematically_corrupted_author_list_is_caught():
    """citeaudit_rw_2272 (SSDD): real paper, real DOI, given names rewritten.

    Jianwei -> Jia, Israr -> Imran, Chang -> Chao. CiteAudit labels the entry
    real because the work exists; the citation still misnames its authors.
    """
    warnings = _check("Jia Li, Bo Wang, Imran Ahmad, Chao Liu",
                      _authors(("Jianwei", "Li"), ("Baoyou", "Wang"),
                               ("Israr", "Ahmad"), ("Chang", "Liu")))
    assert len(warnings) >= 2


def test_author_string_with_no_latin_words_is_coverage_not_a_crash():
    """A CrossRef random-sample entry killed the 2026-08-04 benchmark run.

    _check_authors_against_registry returned a bare `warnings` on this path
    while every other path returned (warnings, notes), so the caller's
    two-value unpack raised ValueError and took the whole run down mid-dataset.

    An author string with no Latin-script words after folding -- a name written
    wholly in CJK or Cyrillic -- can be compared against nothing. That is a gap
    in coverage, not a discrepancy, and certainly not a crash.
    """
    registry = _authors(("Wei", "Zhang"), ("Ming", "Li"))
    for bib_author in ("张伟", "Иванов", "—", "123"):
        assert _check(bib_author, registry) == []
        assert _notes(bib_author, registry) == []
