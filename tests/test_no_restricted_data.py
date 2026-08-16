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
    # Walk the working tree, not `git ls-files`. Selecting from the index
    # meant a newly generated result was outside this guard until it had
    # already been committed -- the run/`git add`/commit sequence stages the
    # unredacted file and brings it into scope in one motion, so the check
    # that should have blocked it only ever ran afterwards. Found 2026-08-16.
    # _restricted_ids still reads the index by design: a dataset is
    # restricted exactly when its .bib is untracked.
    tracked = _tracked()
    restricted = _restricted_ids(tracked)
    results_root = REPO / 'results'
    everything = (sorted(str(p.relative_to(REPO))
                         for p in results_root.rglob('*.json'))
                  if results_root.is_dir() else [])
    for rel in everything:
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


def _strings(node):
    if isinstance(node, dict):
        for key, value in node.items():
            for path, text in _strings(value):
                yield f'{key}.{path}' if path else key, text
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)
    elif isinstance(node, str):
        yield '', node


# Nothing legitimate in a stripped record runs long: citation keys, statuses,
# provider names and model identifiers all sit under 40 characters. Prose does
# not. Measured across every tracked restricted file on 2026-08-12, the
# longest survivor was 39 characters and the shortest offender was 220.
MAX_SAFE_LEN = 60


def test_no_long_free_text_anywhere_in_restricted_records():
    """Catch prose by shape, not by key name.

    The three escapes so far were all the same mistake in different clothes.
    `fields` was published for four months; `ai_error.message` kept the raw
    model reply whenever a call hit the token ceiling; `ai_analysis.
    additional_note` appeared once, in a v1.7.0 run, after the first two were
    fixed. Each was found by looking, and each would have been caught here
    without being named, because a key nobody has thought of yet still holds
    a string that is too long to be anything but prose.
    """
    offenders = []
    for rel, blob in _restricted_result_files():
        for c in blob.get('details') or []:
            for path, text in _strings(c):
                if len(text) > MAX_SAFE_LEN and not REDACTED.search(text):
                    offenders.append(
                        f'{rel}: {c.get("key")!r} {path or "<str>"} '
                        f'({len(text)} chars) {text[:70]!r}')
    assert not offenders, (
        f'{len(offenders)} records carry free text longer than '
        f'{MAX_SAFE_LEN} characters.\n' + '\n'.join(offenders[:8]) +
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
