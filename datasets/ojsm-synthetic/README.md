# OJSM Synthetic Test Data

The BibTeX files for our synthetic test data live in `test_citations/` (the canonical location).
The `manifest.json` entries for these datasets point to paths relative to the `datasets/` directory.

To avoid duplicating files, the Benchmark Library in the HTML app resolves these paths
and can also load directly from `test_citations/` when running locally.

For GitHub Pages deployment, a build step would copy the relevant .bib files here.
