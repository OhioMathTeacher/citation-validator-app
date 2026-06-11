#!/usr/bin/env python3
"""
Generate fake citations for testing false negative detection
Creates various types of hallucinated/fabricated citations
"""

import random
import sys
import json
from pathlib import Path
from datetime import datetime

# Real author names (for Frankenstein citations)
REAL_AUTHORS = [
    "Geoffrey Hinton", "Yann LeCun", "Yoshua Bengio", "Andrew Ng", "Fei-Fei Li",
    "Demis Hassabis", "Ian Goodfellow", "Jurgen Schmidhuber", "Judea Pearl",
    "Michael Jordan", "Daphne Koller", "Sebastian Thrun", "Peter Norvig",
    "Stuart Russell", "Turing, Alan", "Shannon, Claude", "Knuth, Donald",
    "Dijkstra, Edsger", "Hopper, Grace", "Rivest, Ronald"
]

# Real journal names
REAL_JOURNALS = [
    "Nature", "Science", "Cell", "The Lancet", "PNAS",
    "Journal of Machine Learning Research", "Neural Information Processing Systems",
    "IEEE Transactions on Pattern Analysis and Machine Intelligence",
    "Communications of the ACM", "Artificial Intelligence",
    "Physical Review Letters", "Journal of the American Chemical Society"
]

# Fake but plausible journal names
FAKE_JOURNALS = [
    "International Journal of Advanced AI Systems",
    "Journal of Computational Intelligence and Deep Learning",
    "Transactions on Neural Networks and Applications",
    "Proceedings of the Global AI Conference",
    "Journal of Machine Intelligence Research",
    "Advances in Artificial Intelligence and Robotics"
]

# Generic/suspicious titles
GENERIC_TITLES = [
    "A Study of {topic}",
    "An Overview of {topic}",
    "Recent Advances in {topic}",
    "A Survey of {topic} Methods",
    "New Approaches to {topic}",
    "Improving {topic} Systems",
    "Analysis of {topic} Techniques"
]

TOPICS = [
    "Machine Learning", "Deep Learning", "Neural Networks", "Computer Vision",
    "Natural Language Processing", "Reinforcement Learning", "AI Safety",
    "Quantum Computing", "Blockchain", "Data Science"
]

def generate_frankenstein(count, source_bib_file=None):
    """
    Generate Frankenstein citations: real components mixed incorrectly
    Type 1: Real author + fake title + real journal
    """
    citations = []
    
    for i in range(count):
        author = random.choice(REAL_AUTHORS)
        title = random.choice(GENERIC_TITLES).format(topic=random.choice(TOPICS))
        journal = random.choice(REAL_JOURNALS)
        year = random.randint(2020, 2025)
        volume = random.randint(100, 999)
        pages = f"{random.randint(1, 500)}--{random.randint(501, 999)}"
        
        cite_key = f"frankenstein{i+1:04d}"
        
        bib = f"""@article{{{cite_key},
  author = {{{author}}},
  title = {{{title}}},
  journal = {{{journal}}},
  year = {{{year}}},
  volume = {{{volume}}},
  pages = {{{pages}}}
}}"""
        
        citations.append({
            'bib': bib,
            'type': 'frankenstein',
            'note': 'Real author + generic title + real journal (fabricated combination)'
        })
    
    return citations

def generate_stolen_doi(count):
    """
    Generate citations with real DOIs but completely wrong metadata
    """
    # Real DOIs from well-known papers
    real_dois = [
        "10.1038/nature14539",  # AlphaGo paper
        "10.1126/science.1127647",  # CRISPR
        "10.1038/s41586-019-1799-6",  # Quantum supremacy
        "10.48550/arXiv.1706.03762",  # Attention is all you need
        "10.1038/s41586-021-03819-2"  # AlphaFold
    ]
    
    citations = []
    
    for i in range(count):
        doi = random.choice(real_dois)
        fake_author = f"Smith, John Q. and Johnson, Mary R."
        fake_title = random.choice(GENERIC_TITLES).format(topic=random.choice(TOPICS))
        fake_journal = random.choice(FAKE_JOURNALS)
        year = random.randint(2020, 2025)
        
        cite_key = f"stolen_doi{i+1:04d}"
        
        bib = f"""@article{{{cite_key},
  author = {{{fake_author}}},
  title = {{{fake_title}}},
  journal = {{{fake_journal}}},
  year = {{{year}}},
  doi = {{{doi}}}
}}"""
        
        citations.append({
            'bib': bib,
            'type': 'stolen_doi',
            'note': f'Real DOI ({doi}) with completely fabricated metadata'
        })
    
    return citations

def generate_plausible_fake(count):
    """
    Generate completely fake citations with plausible-looking DOIs
    """
    citations = []
    
    for i in range(count):
        author = f"{random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones'])}, {random.choice(['A', 'B', 'C', 'D'])}. {random.choice(['M', 'R', 'T', 'K'])}."
        title = random.choice(GENERIC_TITLES).format(topic=random.choice(TOPICS))
        journal = random.choice(FAKE_JOURNALS)
        year = random.randint(2020, 2025)
        volume = random.randint(1, 200)
        pages = f"{random.randint(1000, 9000)}--{random.randint(9001, 9999)}"
        
        # Generate plausible but fake DOI
        fake_doi = f"10.{random.randint(1000, 9999)}/{random.choice(['j', 's', 'article'])}.{year}.{random.randint(100000, 999999)}"
        
        cite_key = f"plausible{i+1:04d}"
        
        bib = f"""@article{{{cite_key},
  author = {{{author}}},
  title = {{{title}}},
  journal = {{{journal}}},
  year = {{{year}}},
  volume = {{{volume}}},
  pages = {{{pages}}},
  doi = {{{fake_doi}}}
}}"""
        
        citations.append({
            'bib': bib,
            'type': 'plausible_fake',
            'note': 'Completely fabricated citation with plausible format'
        })
    
    return citations

def generate_nonsense(count):
    """
    Generate obviously fake citations (future years, impossible dates, etc.)
    """
    citations = []
    
    # Type 1: Future year
    for i in range(count // 4):
        cite_key = f"future{i+1:04d}"
        year = random.randint(2027, 2030)
        
        bib = f"""@article{{{cite_key},
  author = {{Anderson, Future}},
  title = {{Predictive Analysis of {random.choice(TOPICS)}}},
  journal = {{{random.choice(FAKE_JOURNALS)}}},
  year = {{{year}}}
}}"""
        
        citations.append({
            'bib': bib,
            'type': 'nonsense_future_year',
            'note': f'Future year ({year})'
        })
    
    # Type 2: Very generic title
    for i in range(count // 4):
        cite_key = f"generic{i+1:04d}"
        
        bib = f"""@article{{{cite_key},
  author = {{Generic, Author}},
  title = {{A Study}},
  journal = {{Journal}},
  year = {{2020}}
}}"""
        
        citations.append({
            'bib': bib,
            'type': 'nonsense_generic',
            'note': 'Extremely generic title and metadata'
        })
    
    # Type 3: Random string DOI
    for i in range(count // 4):
        cite_key = f"random_doi{i+1:04d}"
        random_doi = f"10.{random.randint(1000,9999)}/{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=12))}"
        
        bib = f"""@article{{{cite_key},
  author = {{Person, Random}},
  title = {{{random.choice(GENERIC_TITLES).format(topic=random.choice(TOPICS))}}},
  journal = {{{random.choice(FAKE_JOURNALS)}}},
  year = {{2024}},
  doi = {{{random_doi}}}
}}"""
        
        citations.append({
            'bib': bib,
            'type': 'nonsense_random_doi',
            'note': f'Random string DOI'
        })
    
    # Type 4: Ancient year for modern topic
    for i in range(count - len(citations)):
        cite_key = f"anachronism{i+1:04d}"
        
        bib = f"""@article{{{cite_key},
  author = {{Historical, Anachronism}},
  title = {{Deep Neural Networks for Image Classification}},
  journal = {{Journal of Computer Science}},
  year = {{1985}}
}}"""
        
        citations.append({
            'bib': bib,
            'type': 'nonsense_anachronism',
            'note': 'Modern topic (deep learning) with impossible early year'
        })
    
    return citations

def save_citations(citations, output_dir, citation_type):
    """Save generated citations to files"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save ground truth
    ground_truth = []
    
    # Group into files of 50 citations
    batch_size = 50
    file_num = 1
    
    for i in range(0, len(citations), batch_size):
        batch = citations[i:i + batch_size]
        output_file = output_path / f"{citation_type}_{file_num:04d}.bib"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"% Fake citations for testing: {citation_type}\n")
            f.write(f"% Generated: {datetime.now().isoformat()}\n")
            f.write(f"% Expected result: INVALID (fabricated citations)\n\n")
            
            for cit in batch:
                f.write(cit['bib'])
                f.write("\n\n")
                
                # Record ground truth
                ground_truth.append({
                    'file': str(output_file),
                    'type': cit['type'],
                    'expected': 'INVALID',
                    'note': cit['note']
                })
        
        print(f"✓ Saved {len(batch)} citations to {output_file}")
        file_num += 1
    
    # Save ground truth JSON
    gt_file = output_path / f"ground_truth_{citation_type}.json"
    with open(gt_file, 'w') as f:
        json.dump(ground_truth, f, indent=2)
    
    print(f"✓ Saved ground truth to {gt_file}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_fake_citations.py --type <type> --count <n> --output <dir>")
        print("\nTypes:")
        print("  frankenstein  - Real components mixed incorrectly")
        print("  stolen_doi    - Real DOIs with wrong metadata")
        print("  plausible     - Completely fake but looks real")
        print("  nonsense      - Obviously fake (future years, etc.)")
        print("  all           - Generate all types")
        print("\nExamples:")
        print("  python generate_fake_citations.py --type frankenstein --count 100 --output false_negative_tests/frankenstein/")
        print("  python generate_fake_citations.py --type all --count 400 --output false_negative_tests/")
        sys.exit(1)
    
    # Parse arguments
    args = {sys.argv[i]: sys.argv[i+1] for i in range(1, len(sys.argv)-1, 2) if sys.argv[i].startswith('--')}
    
    citation_type = args.get('--type', 'frankenstein')
    count = int(args.get('--count', '100'))
    output_dir = args.get('--output', 'false_negative_tests/')
    
    print(f"Generating {count} {citation_type} citations...\n")
    
    if citation_type == 'all':
        # Generate all types
        per_type = count // 4
        
        for ctype, generator in [
            ('frankenstein', generate_frankenstein),
            ('stolen_doi', generate_stolen_doi),
            ('plausible', generate_plausible_fake),
            ('nonsense', generate_nonsense)
        ]:
            print(f"\nGenerating {per_type} {ctype} citations...")
            citations = generator(per_type)
            save_citations(citations, f"{output_dir}/{ctype}/", ctype)
    else:
        # Generate specific type
        generators = {
            'frankenstein': generate_frankenstein,
            'stolen_doi': generate_stolen_doi,
            'plausible': generate_plausible_fake,
            'nonsense': generate_nonsense
        }
        
        if citation_type not in generators:
            print(f"Error: Unknown type '{citation_type}'")
            sys.exit(1)
        
        citations = generators[citation_type](count)
        save_citations(citations, output_dir, citation_type)
    
    print(f"\n✓ Done! Generated {count} fake citations")

if __name__ == '__main__':
    main()
