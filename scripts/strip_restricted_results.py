#!/usr/bin/env python3
"""Remove third-party citation text from tracked experiment results.

The problem this fixes
----------------------
`.gitignore` withholds `datasets/citeaudit-*` and
`datasets/compound-deception-ansari/*`, and `datasets/README.md` says this
repository redistributes neither. But the per-citation JSON under
`results/experiments/` carried each citation's `fields` -- author, title,
eprint and the original `note` -- so 3,233 withheld citations were published
through the results instead of the datasets. Found 2026-08-11.

What is kept and what goes
--------------------------
Everything that makes the results scientifically checkable is kept: the
citation key, the verdict, whether the DOI resolved, which registry settled it,
the AI verdict and confidence, and a coarse reason code. A reader can still
audit every judgement the tool made.

Everything that identifies the cited work is removed, because that is the
corpus itself: `fields`, and any free text that quotes a title or an author --
warning strings, AI reasons, and the registry record's own title, which for a
correctly-resolved citation simply repeats the cited title.

Which datasets are restricted is derived, not hard-coded: a dataset is
restricted when its source .bib is not tracked in git. Withholding the source
and publishing the contents is the contradiction being fixed, so the source is
the authority.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Keys whose values are free text that can quote a title or an author.
TEXT_KEYS = ('warnings', 'issues', 'suspicion_reasons', 'coverage_notes')

# A warning reads like "Title mismatch (similarity 0.00): BibTeX='...' vs ...".
# Keep the part before the colon; that is the finding. Drop the quoted evidence.
REASON_HEAD = re.compile(r'^([^:]{3,60}?)(?::|$)')

REDACTION = '[redacted: third-party dataset]'


def tracked_files():
    out = subprocess.check_output(['git', '-C', str(REPO), 'ls-files'],
                                  text=True)
    return set(out.split('\n'))


def restricted_dataset_ids(tracked):
    """A dataset is restricted when its own .bib is withheld from the repo."""
    manifest = json.loads((REPO / 'datasets/manifest.json').read_text())
    restricted = set()
    for entry in manifest:
        ds_id = entry.get('id') or entry.get('short_name')
        bibs = entry.get('bib_files') or []
        if bibs and not any(b in tracked for b in bibs):
            restricted.add(ds_id)
    return restricted


def redact_reason(text):
    if not isinstance(text, str):
        return text
    if REDACTION in text:
        return text        # already redacted; the marker contains a colon
    m = REASON_HEAD.match(text.strip())
    head = (m.group(1) if m else text)[:60].strip()
    return f'{head} {REDACTION}'


def strip_citation(c):
    """Return the citation record with identifying text removed."""
    changed = False
    if c.pop('fields', None) is not None:
        changed = True

    for key in TEXT_KEYS:
        if isinstance(c.get(key), list) and c[key]:
            new = [redact_reason(t) for t in c[key]]
            if new != c[key]:
                c[key] = new
                changed = True

    vm = c.get('verified_metadata')
    if isinstance(vm, dict):
        # The registry's own record repeats the cited title whenever the
        # citation was correct, so it reconstructs the corpus. Source and
        # year are facts about the lookup, not about the withheld list.
        for k in ('title', 'authors', 'author', 'container-title', 'journal'):
            if vm.pop(k, None) is not None:
                changed = True

    ai = c.get('ai_analysis')
    if isinstance(ai, dict):
        # Verdict and confidence stay; the prose quotes titles. Must be
        # idempotent: re-running has to report nothing, or the dry run can
        # never be used to prove the tree is clean.
        for key in ('reason', 'raw'):
            val = ai.get(key)
            if isinstance(val, str) and REDACTION not in val:
                ai[key] = REDACTION
                changed = True
    return changed


def dataset_of(path, blob):
    # Result files come from three eras and name the dataset three ways:
    # `dataset_id`, a bare `dataset`, or only in the filename.
    for key in ('dataset_id', 'dataset', 'dataset_name'):
        if blob.get(key):
            return str(blob[key])
    run = blob.get('run_info') or {}
    return str(run.get('dataset_id') or path.name)


def looks_like_citation(node):
    return isinstance(node, dict) and (
        'fields' in node or ('key' in node and 'status' in node))


def walk(node, restricted, in_scope, counter):
    """Redact citation records inside restricted-dataset subtrees only.

    Scope matters: one file mixes `compound-deception-ansari` with the
    ojsm-fake-* sets, which are the author's own and stay published. Files also
    nest records three ways -- `details`, `datasets.<name>.false_negatives`,
    and bare lists -- so this recurses instead of assuming a shape. Assuming a
    shape is what let the CiteAudit files and then these four escape.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            child_scope = in_scope or any(
                r and (r in str(key) or str(key) in r) for r in restricted)
            walk(value, restricted, child_scope, counter)
        if in_scope and looks_like_citation(node):
            if strip_citation(node):
                counter[0] += 1
    elif isinstance(node, list):
        for item in node:
            walk(item, restricted, in_scope, counter)


def main():
    apply = '--apply' in sys.argv
    tracked = tracked_files()
    restricted = restricted_dataset_ids(tracked)
    print(f'restricted datasets (source withheld): {sorted(restricted)}\n')

    touched = total = 0
    for rel in sorted(f for f in tracked
                      if f.startswith('results/') and f.endswith('.json')):
        path = REPO / rel
        try:
            blob = json.loads(path.read_text())
        except Exception:
            continue
        ds = dataset_of(path, blob)
        file_scope = any(r and (r in ds or ds in r) for r in restricted)
        counter = [0]
        walk(blob, restricted, file_scope, counter)
        if not counter[0]:
            continue
        touched += 1
        total += counter[0]
        print(f'  {rel}  {counter[0]} citations redacted')
        if apply:
            path.write_text(json.dumps(blob, indent=2) + '\n')

    print(f'\n{touched} files, {total} citation records')
    if not apply:
        print('DRY RUN. Re-run with --apply to write.')


if __name__ == '__main__':
    main()
