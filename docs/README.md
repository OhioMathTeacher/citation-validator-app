# Documentation

## `supplement.pdf`

Supplementary material for the article *"Whose Writing Is This, Anyway?:
Lessons from Building a Free and Open Citation Hallucination Detector"*
(Michael Todd Edwards, submitted to *The Code4Lib Journal*).

The article refers to this document as **Supplement A** and **Supplement B**.
It holds the material kept out of the article's running text:

- **Supplement A — Statistical and algorithmic details.** The Jaccard
  title-matching formula, every match threshold and confidence cutoff, the
  Wilson score interval and the intervals for each headline proportion, and
  the definitions of precision, recall, and false-positive rate.
- **Supplement B — Validation procedure in detail.** Step 1 (DOI resolution)
  and Step 2 (title search) in full, including backup services, request
  pacing, the retry policy, and the rule that a lookup which fails is treated
  as *unverified* rather than fabricated.

It lives here rather than in the article because *The Code4Lib Journal* caps
articles at roughly 5,000 words and allows extensive algorithmic material to
be hosted in a repository. Keeping it beside the code means a reader checking
a threshold can see the stated value and the line that implements it without
leaving the repository.

Built from `supplement-Code4Lib.tex` in the manuscript repository. Regenerate
with:

```
lualatex supplement-Code4Lib.tex
biber supplement-Code4Lib
lualatex supplement-Code4Lib.tex
lualatex supplement-Code4Lib.tex
```

Archived with each release under the Zenodo concept DOI
[10.5281/zenodo.21795712](https://doi.org/10.5281/zenodo.21795712), which
always resolves to the latest version.
