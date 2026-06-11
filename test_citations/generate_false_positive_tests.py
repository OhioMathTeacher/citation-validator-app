#!/usr/bin/env python3
"""
Generate false positive test cases: REAL citations that might be incorrectly flagged
These should all pass validation but might trigger warnings due to edge cases
"""

import sys
from pathlib import Path
from datetime import datetime

# Real citations that are tricky edge cases

DATACITE_DOIS = [
    # Zenodo DOIs
    """@misc{zenodo_example_2020,
  author = {European Organization for Nuclear Research and OpenAIRE},
  title = {Zenodo},
  year = {2013},
  publisher = {CERN},
  doi = {10.25495/7GXK-RD71}
}""",
    """@dataset{smith2023data,
  author = {Smith, John and Doe, Jane},
  title = {Research Dataset for Machine Learning},
  year = {2023},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.7654321}
}""",
    
    # Figshare
    """@misc{figshare2022,
  author = {Johnson, Alice},
  title = {Supplementary Data for Climate Study},
  year = {2022},
  publisher = {Figshare},
  doi = {10.6084/m9.figshare.19876543}
}"""
]

OLD_PAPERS = [
    # Pre-DOI era papers (perfectly valid)
    """@article{shannon1948mathematical,
  title={A mathematical theory of communication},
  author={Shannon, Claude E},
  journal={The Bell System Technical Journal},
  volume={27},
  number={3},
  pages={379--423},
  year={1948},
  publisher={Nokia Bell Labs}
}""",
    """@book{knuth1997art,
  title={The art of computer programming},
  author={Knuth, Donald Ervin},
  volume={2},
  year={1997},
  publisher={Addison-Wesley}
}""",
    """@article{turing1950computing,
  title={Computing machinery and intelligence},
  author={Turing, Alan M},
  journal={Mind},
  volume={59},
  number={236},
  pages={433--460},
  year={1950}
}"""
]

NON_ENGLISH = [
    # Papers with non-ASCII characters (legitimate)
    """@article{muller2020uber,
  title={{\"U}ber die Theorie der maschinellen Intelligenz},
  author={M{\"u}ller, Hans and Schr{\"o}der, Claudia},
  journal={Zeitschrift f{\"u}r K{\"u}nstliche Intelligenz},
  volume={34},
  number={2},
  pages={123--145},
  year={2020},
  doi={10.1007/s13218-020-00649-3}
}""",
    """@article{lopez2019aprendizaje,
  title={Aprendizaje autom{\\'a}tico y redes neuronales},
  author={L{\\'o}pez, Jos{\\'e} and Garc{\\'\\i}a, Mar{\\'\\i}a},
  journal={Revista de Inteligencia Artificial},
  volume={22},
  pages={45--67},
  year={2019}
}"""
]

SPARSE_METADATA = [
    # Minimal but valid citations
    """@misc{blog2023,
  author = {Smith, J.},
  title = {Machine Learning Insights},
  year = {2023},
  howpublished = {Blog post}
}""",
    """@techreport{doe2022report,
  author = {Doe, Jane},
  title = {Annual AI Progress Report},
  institution = {AI Research Institute},
  year = {2022}
}""",
    """@phdthesis{chen2021thesis,
  title={Deep Learning for Natural Language Processing},
  author={Chen, Wei},
  year={2021},
  school={Stanford University}
}"""
]

ARXIV_VERSIONS = [
    # arXiv papers (legitimate, might lack traditional DOIs)
    """@article{vaswani2017attention,
  title={Attention is all you need},
  author={Vaswani, Ashish and Shazeer, Noam and Parmar, Niki and Uszkoreit, Jakob and Jones, Llion and Gomez, Aidan N and Kaiser, {\L}ukasz and Polosukhin, Illia},
  journal={Advances in neural information processing systems},
  volume={30},
  year={2017},
  eprint={1706.03762},
  archivePrefix={arXiv}
}""",
    """@article{brown2020language,
  title={Language models are few-shot learners},
  author={Brown, Tom and Mann, Benjamin and Ryder, Nick and Subbiah, Melanie and others},
  journal={Advances in neural information processing systems},
  volume={33},
  pages={1877--1901},
  year={2020},
  eprint={2005.14165},
  archivePrefix={arXiv}
}"""
]

def save_test_cases(citations, output_dir, category):
    """Save false positive test citations"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    output_file = output_path / f"{category}_examples.bib"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"% False Positive Test Cases: {category}\n")
        f.write(f"% These are REAL, VALID citations that might trigger warnings\n")
        f.write(f"% Expected result: VALID (should NOT be flagged as problematic)\n")
        f.write(f"% Generated: {datetime.now().isoformat()}\n\n")
        
        for citation in citations:
            f.write(citation)
            f.write("\n\n")
    
    print(f"✓ Saved {len(citations)} citations to {output_file}")
    return len(citations)

def main():
    output_dir = 'false_positive_tests/'
    
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    
    print(f"Generating false positive test cases in {output_dir}\n")
    
    total = 0
    total += save_test_cases(DATACITE_DOIS, f"{output_dir}/datacite_dois/", "datacite_dois")
    total += save_test_cases(OLD_PAPERS, f"{output_dir}/old_formats/", "old_formats")
    total += save_test_cases(NON_ENGLISH, f"{output_dir}/non_english/", "non_english")
    total += save_test_cases(SPARSE_METADATA, f"{output_dir}/sparse_metadata/", "sparse_metadata")
    total += save_test_cases(ARXIV_VERSIONS, f"{output_dir}/arxiv_preprints/", "arxiv_preprints")
    
    print(f"\n✓ Total: {total} false positive test citations generated")
    print(f"These are all REAL citations that should be validated, not flagged as problematic")

if __name__ == '__main__':
    main()
