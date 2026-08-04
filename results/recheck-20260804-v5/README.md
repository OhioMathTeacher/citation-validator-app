# Re-check v5 — the delta the paper should report

Supersedes `recheck-20260804`, `-v2`, `-v3` and `-v4`, all of which were
intermediate rounds during the same day's work. Reproduce with:

```bash
python3 scripts/recheck_affected.py \
    --baseline "results/experiments/*det*.json" \
    --output results/recheck-20260804-v5/affected-recheck.json
```

Baseline: the 2026-05-24 deterministic runs. Comparison set: the 85 DOI-bearing
citations in those runs. Only DOI-bearing citations can move, because the author
and date checks live on the DOI path — and in the CiteAudit real-world set that
is **85 of 3,356 citations, 2.5%**. The other 97.5% carry no DOI, so nothing
added here can reach them at all.

That ratio is worth reporting in its own right. These are references harvested
from published papers, not a synthetic sample, and it puts a hard ceiling on
what *any* identifier-based checker can verify: the DOI boundary is not a
narrow edge case, it is where almost the entire real-world bibliography sits.

**85 checked, 15 changed, 13 code-attributable, 0 errors.** Two changes had a
baseline `warning` that was an arXiv timeout rather than a finding — those
measure the network on the day of the May run, not the software, and are
excluded throughout.

## The thirteen

Nine agree with CiteAudit's human labels:

| Change | n |
|---|---|
| `valid` → `warning`/`suspicious` on citations labelled fabricated | 6 |
| `warning` → `valid` on citations labelled real | 3 |

Four flag citations CiteAudit labels **real**. None is a false positive. The
labels answer *"is this a real piece of work?"*; the checks added here answer
*"does the citation as written match the record its DOI points to?"* Those are
different questions, and all four citations fail the second one:

- **`citeaudit_rw_2272`** — the SSDD dataset paper. Real DOI, correct title, and
  **12 of its 16 authors misnamed**: Jianwei → Jia, Baoyou → Xiang, Israr →
  Imran, Chang → Chao, Dece → Dong, Shunjun → Shaoyi, Tianjiao → Tao, Xiaowo →
  Xiang, Yanqin → Yahui, Yue → Yanan, Jun → Jie, Xiao → Xiaozhi. A Frankenstein
  citation on the *author* axis, sitting on the DOI-bearing side of the DOI
  boundary — the case the paper's §"Frankenstein Citations" says a resolving
  identifier cannot settle.
- **`citeaudit_rw_2015`** — the IEDB 2018 update. Swapnil → Shuchismita,
  Sheridan → Silvia, Daniel K. → Derin K.
- **`citeaudit_rw_2265`** — SEFEPNet. Linfeng → Liyuan, Tianming → Ting, and a
  'Jie Tian' the registry does not list.
- **`citeaudit_rw_2365`** — cited as *SphereFace*, but the DOI resolves to
  *Binary Coding for Partial…*. The reference is real; the identifier attached
  to it belongs to a different paper.

**Zero change in the arXiv 285 and CrossRef 96 false-positive sets.** The 0%
false-positive figure in the abstract is untouched.

## What produced the changes

- **The arXiv publication date.** `_validate_arxiv` returned no `published`
  key, and the year comparison is guarded on `'published' in doi_data`, so the
  year check was skipped for *every arXiv DOI in the corpus*. That is how
  `citeaudit_rw_2936` passed clean while dated **2011** for a paper posted in
  November 2020 — the arXiv identifier's YYMM prefix read as a year.
- **The author pair check.** Named authors are verified as (given, family)
  pairs rather than searched for as loose surnames.
- **`et al` as coverage.** An abbreviated author list is reported as a gap in
  what could be checked, and never escalates.

## Three false positives found by running at scale, not by unit tests

Every one was in the new code, and none would have been caught by tests written
from cases already imagined. They are now regression tests drawn from the real
citations that exposed them.

1. **Middle initials.** "Matthew M Botvinick, Todd S Braver" — the backward
   step landed on the initial, so the scan ran on into the next author and
   reported a *Todd Botvinick*, a *Cameron Barch* and a *Deanna Braver*.
2. **Multi-part given names.** Comparing only the first token made every
   shortened form an impostor: *Kumar Dhanda* against Sandeep **Kumar** Dhanda,
   *Ringel Morris* against Meredith **Ringel** Morris, *Yuan Chang* against
   Chia-**Yuan** Chang.
3. **The registry's own name parsing.** CrossRef holds the XJTU-SY bearing
   dataset surname-first — `given: WANG`, `family: Biao` — so a correct "Biao
   Wang" read as an impostor. A repeated surname ("Tian Tian, Peng Gao") caused
   the same class of error. Both are silenced by checking the pooled registry
   name parts before accusing: when every component is present somewhere, the
   two sides disagree about parsing, not about people.

That last one is worth stating plainly in the paper. A tool built to argue that
*unverifiable* must not be read as *fabricated* spent three rounds manufacturing
accusations out of its own parsing assumptions, and only a run against real
citations exposed it.

## Still open

`10.48550/arXiv.2308.06571` is now caught, but the general bound stands: with
common surnames and an `et al`, author matching has limited purchase. Worth
reporting as a limit of the method rather than engineering around.
