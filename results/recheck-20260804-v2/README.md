# Re-check v2 — what the 14 changes actually show

Baseline: the 2026-05-24 runs. Comparison set: the 152 of 11,555 stored records
capable of changing under the 2026-08-04 edits (the other 10,987 carry no DOI,
so the author and year checks cannot reach them). 152 checked, 14 changed.

**Eight of the fourteen are not code changes.** In all eight the baseline status
was `warning` carrying `DOI could not be verified: arXiv API unreachable`
(HTTP 429 or a read timeout). The May run was rate-limited by arXiv; the August
run was not. The tool behaved correctly on both occasions — it reported
*unverifiable* rather than *fabricated*, which is the distinction the paper is
about — but the delta between them measures the network, not the software.

That leaves **six code-attributable changes**, all in the same direction:

| DOI | change | CiteAudit label | why it fired |
|---|---|---|---|
| `10.1145/3539597.3570464` | valid → warning | invalid | first author 'Ji' absent |
| `10.3389/fimmu.2025.1616113` | valid → warning | invalid | first author 'Nilsson' absent |
| `10.18653/v1/2021.emnlp-main.629` | valid → suspicious | invalid | title similarity 0.00 |
| `10.1016/j.compbiomed.2022.105238` | valid → suspicious | invalid | title similarity 0.07 |
| `10.1016/j.artint.2019.103216` | valid → warning | **valid** | year 1902 vs 2020 |
| `10.1109/cvpr.2017.712` | valid → suspicious | **valid** | title similarity 0.06; first author 'Qin' absent |

The last two are labelled `valid` but are not false positives. CiteAudit's labels
answer *"is this a real piece of work?"*; the checks added here answer *"does the
citation as written match the record its DOI points to?"* A citation dated **1902**
for a 2020 article is a real discrepancy whatever the underlying work. And
`10.1109/cvpr.2017.712`, cited as SphereFace, resolves to *Binary Coding for
Partial…* — the reference is real, the DOI attached to it is not its own.

So: **six changes, six correct detections, zero false positives.** Every one of
them is a citation whose text disagrees with its registry record.

**Zero change in the arXiv 285 and CrossRef 96 sets**, so the 0% false-positive
figure in the abstract is untouched. 6/3356 = 0.18% of `citeaudit-realworld`.

## Correction to the earlier reading

An earlier pass scored this as "10 correct-direction, 4 wrong" and attributed two
`warning → valid` changes on fabricated citations to the Semantic Scholar
promotion rule (`author_match or year_match`). That diagnosis does not hold. Both
citations reach `valid` on the **DOI path**, with `verified_metadata` set and no
warning raised; the Semantic Scholar fallback is gated on
`not verified_metadata or status not in ('valid',)` and never runs. Author-check
warnings already set `doi_field_conflict`, which guards the promotion. The rule is
permissive, but it is not what cleared these two.

What cleared them was a missing check, since fixed:

- `citeaudit_rw_2936` (`10.48550/arXiv.2011.04006`) is cited as **2011** for a paper
  posted in **November 2020** — the arXiv identifier's YYMM prefix read as a year.
  `_validate_arxiv` returned no `published` key, and `check_citation` guards the
  year comparison on `'published' in doi_data`, so the year check was skipped for
  every arXiv DOI in the corpus. Now fixed; this citation is caught.
- `citeaudit_rw_2111` (`10.48550/arXiv.2308.06571`) is cited to "Ziqi Wang, Jing
  Zhang, and et al" for a paper by Jiuniu Wang, Hangjie Yuan, Dayou Chen, Yingya
  Zhang, Xiang Wang and Shiwei Zhang. The surnames Wang and Zhang both appear, so
  the corroboration rule is satisfied and the given names are too far apart to
  register as misspellings. It carries no year field to check. **This one still
  passes clean, and is a genuine limit of surname matching** rather than a defect:
  with common surnames and an `et al`, the check has nothing left to disagree with.
  Worth reporting in the paper as a bound on the method.
