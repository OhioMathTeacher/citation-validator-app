"""Tracked results must not republish datasets the repository withholds.

`.gitignore` withholds `datasets/citeaudit-*` and
`datasets/compound-deception-ansari/*`, and `datasets/README.md` says this
repository redistributes neither. For months the per-citation JSON under
`results/` carried each citation's `fields` -- author, title, eprint and the
original `note` -- so the withheld corpora were published through the results
instead of the datasets. 44 tracked files, 28,736 citation records.

Withholding a dataset and publishing its contents two directories away is the
kind of gap between a stated policy and an artefact that this project exists to
report. This test closes it: a dataset is restricted when its own .bib is not
tracked, and a restricted citation record may carry verdicts but never text
that identifies the cited work.

Run `python scripts/strip_restricted_results.py --apply` if this fails.
"""

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

FORBIDDEN_KEYS = ('fields',)
# Free text that has been seen quoting titles and author lists.
TEXT_KEYS = ('warnings', 'issues', 'suspicion_reasons', 'coverage_notes')
REDACTED = re.compile(r'redacted', re.I)


def _tracked():
    out = subprocess.check_output(['git', '-C', str(REPO), 'ls-files'], text=True)
    return set(out.split('\n'))


def _restricted_ids(tracked):
    manifest = json.loads((REPO / 'datasets/manifest.json').read_text())
    out = set()
    for entry in manifest:
        ds = entry.get('id') or entry.get('short_name')
        bibs = entry.get('bib_files') or []
        if bibs and not any(b in tracked for b in bibs):
            out.add(ds)
    return out


def _dataset_of(path, blob):
    for key in ('dataset_id', 'dataset', 'dataset_name'):
        if blob.get(key):
            return str(blob[key])
    run = blob.get('run_info') or {}
    return str(run.get('dataset_id') or path.name)


def _restricted_result_files():
    tracked = _tracked()
    restricted = _restricted_ids(tracked)
    for rel in sorted(f for f in tracked
                      if f.startswith('results/') and f.endswith('.json')):
        path = REPO / rel
        try:
            blob = json.loads(path.read_text())
        except Exception:
            continue
        ds = _dataset_of(path, blob)
        if any(r and (r in ds or ds in r) for r in restricted):
            yield rel, blob


def test_some_datasets_are_actually_restricted():
    """Guard the guard: if nothing is restricted, this test proves nothing."""
    assert _restricted_ids(_tracked()), (
        'No dataset looks restricted, so this test would pass vacuously. '
        'Either the manifest changed or a withheld .bib became tracked.'
    )


def test_no_citation_fields_in_tracked_results():
    offenders = []
    for rel, blob in _restricted_result_files():
        for c in blob.get('details') or []:
            if any(c.get(k) for k in FORBIDDEN_KEYS):
                offenders.append(f'{rel}: citation {c.get("key")!r} carries fields')
                break
    assert not offenders, (
        f'{len(offenders)} tracked result files republish withheld citation '
        f'text.\n' + '\n'.join(offenders[:8]) +
        '\n\nRun: python scripts/strip_restricted_results.py --apply'
    )


def test_no_unredacted_free_text_in_tracked_results():
    """Warning strings quote titles, so they must be reduced to reason codes."""
    offenders = []
    for rel, blob in _restricted_result_files():
        for c in blob.get('details') or []:
            for key in TEXT_KEYS:
                for text in (c.get(key) or []):
                    if isinstance(text, str) and "'" in text and not REDACTED.search(text):
                        offenders.append(f'{rel}: {c.get("key")!r} {key} quotes text')
                        break
    assert not offenders, (
        f'{len(offenders)} records carry quoted citation text.\n'
        + '\n'.join(offenders[:8]) +
        '\n\nRun: python scripts/strip_restricted_results.py --apply'
    )
