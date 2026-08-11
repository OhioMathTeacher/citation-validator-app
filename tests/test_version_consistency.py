"""The version the app reports must match the version it is released as.

v1.6.0 was tagged and released with VERSION still reading 1.5.1, because the
release procedure bumped CITATION.cff and nothing else. `/version` reads
VERSION, so the deployed Space -- and every report saved from it -- claimed
1.5.1, a version that does not contain the v1.6.0 code, while Zenodo archived
it as 1.6.0. A citation checker that cannot say which version produced a
result has the defect it exists to detect.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

REPO_ROOT = Path(__file__).resolve().parent.parent

from citation_validator import __version__ as APP_VERSION


def _cff_version():
    text = (REPO_ROOT / "CITATION.cff").read_text()
    match = re.search(r"^version:\s*['\"]?([0-9]+\.[0-9]+\.[0-9]+)", text, re.M)
    assert match, "CITATION.cff has no parsable version field"
    return match.group(1)


def _version_file():
    return (REPO_ROOT / "VERSION").read_text().strip()


def test_version_file_is_semver():
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", _version_file()), (
        f"VERSION reads {_version_file()!r}, which is not a semantic version"
    )


def test_citation_cff_matches_version_file():
    assert _cff_version() == _version_file(), (
        f"CITATION.cff says {_cff_version()} but VERSION says {_version_file()}. "
        "Bump both, or a release will claim one version and report another."
    )


def test_app_reports_the_version_file():
    """What /version serves is what the release is labelled."""
    assert APP_VERSION == _version_file(), (
        f"citation_validator.__version__ is {APP_VERSION!r} but VERSION reads "
        f"{_version_file()!r}"
    )
