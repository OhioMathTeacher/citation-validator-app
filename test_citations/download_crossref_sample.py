#!/usr/bin/env python3
"""
Download random citation samples from CrossRef API
No authentication required - uses public REST API
"""

import requests
import json
import time
import sys
from pathlib import Path

def fetch_crossref_sample(count=100, filter_params=None):
    """
    Fetch random samples from CrossRef
    
    Args:
        count: Number of works to sample
        filter_params: Optional filters (e.g., 'from-pub-date:2020,until-pub-date:2024')
    """
    base_url = "https://api.crossref.org/works"
    
    params = {
        'sample': min(count, 100),  # API limits to 100 per request
        'mailto': 'citation-validator@example.com'  # Polite API usage
    }
    
    if filter_params:
        params['filter'] = filter_params
    
    try:
        print(f"Fetching {params['sample']} samples from CrossRef...")
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        items = data.get('message', {}).get('items', [])
        
        print(f"✓ Received {len(items)} works")
        return items
    
    except requests.exceptions.RequestException as e:
        print(f"✗ Error fetching from CrossRef: {e}")
        return []

def convert_to_bibtex(work):
    """Convert CrossRef work metadata to BibTeX format"""
    
    # Determine entry type
    work_type = work.get('type', 'article')
    type_map = {
        'journal-article': 'article',
        'book-chapter': 'inbook',
        'proceedings-article': 'inproceedings',
        'book': 'book',
        'monograph': 'book',
        'dissertation': 'phdthesis'
    }
    entry_type = type_map.get(work_type, 'article')
    
    # Generate cite key from first author + year
    authors = work.get('author', [])
    if authors:
        first_author = authors[0].get('family', 'Unknown')
    else:
        first_author = 'Unknown'
    
    year = work.get('published', {}).get('date-parts', [[None]])[0][0]
    if not year:
        year = work.get('created', {}).get('date-parts', [[2020]])[0][0]
    
    cite_key = f"{first_author.lower().replace(' ', '')}{year}"
    
    # Build BibTeX entry
    bib_lines = [f"@{entry_type}{{{cite_key},"]
    
    # Title
    title = work.get('title', ['Unknown'])[0]
    bib_lines.append(f"  title = {{{title}}},")
    
    # Authors
    if authors:
        author_str = " and ".join([
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in authors[:5]  # Limit to first 5 authors
        ])
        if len(authors) > 5:
            author_str += " and others"
        bib_lines.append(f"  author = {{{author_str}}},")
    
    # Year
    bib_lines.append(f"  year = {{{year}}},")
    
    # Journal/Venue
    if 'container-title' in work and work['container-title']:
        venue = work['container-title'][0]
        if entry_type == 'article':
            bib_lines.append(f"  journal = {{{venue}}},")
        elif entry_type == 'inproceedings':
            bib_lines.append(f"  booktitle = {{{venue}}},")
    
    # Volume, Issue, Pages
    if 'volume' in work:
        bib_lines.append(f"  volume = {{{work['volume']}}},")
    if 'issue' in work:
        bib_lines.append(f"  number = {{{work['issue']}}},")
    if 'page' in work:
        bib_lines.append(f"  pages = {{{work['page']}}},")
    
    # DOI
    if 'DOI' in work:
        bib_lines.append(f"  doi = {{{work['DOI']}}},")
    
    # Publisher
    if 'publisher' in work:
        bib_lines.append(f"  publisher = {{{work['publisher']}}},")
    
    bib_lines.append("}")
    
    return "\n".join(bib_lines)

def download_samples(total_count=1000, output_dir='real_citations/crossref_random/', 
                     filter_params=None, batch_size=100):
    """Download multiple batches of CrossRef samples"""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    all_works = []
    batches_needed = (total_count + batch_size - 1) // batch_size
    
    print(f"Downloading {total_count} citations in {batches_needed} batches...\n")
    
    for batch_num in range(batches_needed):
        batch_count = min(batch_size, total_count - len(all_works))
        
        print(f"Batch {batch_num + 1}/{batches_needed}:")
        works = fetch_crossref_sample(batch_count, filter_params)
        all_works.extend(works)
        
        print(f"Total collected: {len(all_works)}/{total_count}\n")
        
        # Be polite - wait between requests
        if batch_num < batches_needed - 1:
            time.sleep(1)
    
    # Convert to BibTeX and save
    print("Converting to BibTeX format...")
    
    batch_file_count = 50  # citations per file
    file_num = 1
    
    for i in range(0, len(all_works), batch_file_count):
        batch = all_works[i:i + batch_file_count]
        output_file = output_path / f"crossref_sample_{file_num:04d}.bib"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"% CrossRef random sample\n")
            f.write(f"% Downloaded: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            if filter_params:
                f.write(f"% Filter: {filter_params}\n")
            f.write(f"\n")
            
            for work in batch:
                bib_entry = convert_to_bibtex(work)
                f.write(bib_entry)
                f.write("\n\n")
        
        print(f"✓ Saved {len(batch)} citations to {output_file.name}")
        file_num += 1
    
    print(f"\n✓ Total: {len(all_works)} citations downloaded")
    print(f"✓ Saved to {len(range(0, len(all_works), batch_file_count))} files in {output_dir}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python download_crossref_sample.py <count> [output_dir] [filter]")
        print("\nExamples:")
        print("  python download_crossref_sample.py 1000")
        print("  python download_crossref_sample.py 500 real_citations/crossref_2024/")
        print("  python download_crossref_sample.py 1000 real_citations/crossref_recent/ 'from-pub-date:2023'")
        print("\nAvailable filters:")
        print("  from-pub-date:YYYY - Published after year")
        print("  until-pub-date:YYYY - Published before year")
        print("  type:journal-article - Only journal articles")
        print("  has-references:true - Only works with references")
        print("  has-orcid:true - Only works with ORCID IDs")
        sys.exit(1)
    
    count = int(sys.argv[1])
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else 'real_citations/crossref_random/'
    filter_params = sys.argv[3] if len(sys.argv) >= 4 else None
    
    download_samples(count, output_dir, filter_params)

if __name__ == '__main__':
    main()
