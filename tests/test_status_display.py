"""Regression tests for doi_resolved, the flag the web UI reads to tell
"could not be checked" apart from "was checked and something is off".

web/citation-validator.html, displayStatus(), splits a `warning` two ways:

    doi_resolved === true   -> DISCREPANCY   amber
    doi_resolved === false  -> UNVERIFIED    slate
    (absent)                -> WARNING       amber

That split is the whole argument of the project rendered as one interface
decision, so the flag has to be present on every path that can produce a
warning. It was not: the transient branch in check_citation returns early,
ahead of the assignment, so a registry that never answered -- the purest
"could not verify" the tool produces -- fell through to amber WARNING, while a
title search that found nothing correctly rendered slate UNVERIFIED. Two routes
to the same nothing, two different labels, and the wrong one privileged.

Found 2026-08-07 while drawing the validation flowchart for the Code4Lib
article: the diagram needed to show where each status comes from, and this
path could not be drawn consistently with the others.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from citation_validator import CitationValidator


def _entry(**fields):
    f = {
        "title": "A real paper about things",
        "author": "Doe, Jane",
        "year": "2020",
        "journal": "Journal of Things",
    }
    f.update(fields)
    return {"key": "x", "type": "article", "fields": f}


def _validator(doi_result):
    v = CitationValidator(use_ai=False)
    v.validate_doi = lambda doi: doi_result
    return v


def _display_status(result):
    """Mirror of displayStatus() in web/citation-validator.html.

    Kept in step with that function by hand. If the JS changes, change this.
    """
    if result.get("status") != "warning":
        return result["status"].upper()
    if result.get("doi_resolved") is True:
        return "DISCREPANCY"
    if result.get("doi_resolved") is False:
        return "UNVERIFIED"
    return "WARNING"


TRANSIENT = (False, {"transient": True, "error": "429 rate limited"})
NOT_REGISTERED = (False, {"error": "DOI not found in any registry"})


def test_rate_limited_doi_is_marked_unresolved():
    """The bug. A 429 must not leave doi_resolved absent."""
    result = _validator(TRANSIENT).check_citation(_entry(doi="10.1234/abc"))
    assert result["status"] == "warning"
    assert result["doi_resolved"] is False


def test_rate_limited_doi_renders_as_unverified_not_warning():
    result = _validator(TRANSIENT).check_citation(_entry(doi="10.1234/abc"))
    assert _display_status(result) == "UNVERIFIED"


def test_missing_doi_and_failed_lookup_get_the_same_label():
    """Two routes to the same nothing must not render differently."""
    no_answer = _validator(TRANSIENT).check_citation(_entry(doi="10.1234/abc"))

    no_doi = CitationValidator(use_ai=False)
    no_doi.search_by_title = lambda *a, **k: []
    nothing_found = no_doi.check_citation(_entry())

    assert _display_status(no_answer) == _display_status(nothing_found) == "UNVERIFIED"


def test_unregistered_doi_stays_invalid():
    """The definitive case is a finding, and must not be softened by the fix."""
    result = _validator(NOT_REGISTERED).check_citation(_entry(doi="10.9999/nope"))
    assert result["status"] == "invalid"


def test_every_warning_path_carries_the_flag():
    """The invariant behind the bug: a warning without doi_resolved renders
    amber whatever it means, so no path may leave the key unset."""
    cases = []

    cases.append(_validator(TRANSIENT).check_citation(_entry(doi="10.1234/abc")))

    no_doi = CitationValidator(use_ai=False)
    no_doi.search_by_title = lambda *a, **k: []
    cases.append(no_doi.check_citation(_entry()))

    for result in cases:
        if result["status"] == "warning":
            assert "doi_resolved" in result, result
