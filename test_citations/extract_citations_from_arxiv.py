#!/usr/bin/env python3
"""
Extract BibTeX citations from arXiv paper source files
Processes the existing arXiv papers we already have in test_citations/
"""

import os
import re
import sys
import json
from pathlib import Path

def extract_bib_from_file(filepath):
    """Extract BibTeX entries from a .bib or .tex file"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        return []
    
    # Match BibTeX entries
    pattern = r'@(\w+)\{([^,]+),\s*\n((?:[^@])*?)\n\}'
    matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
    
    entries = []
    for entry_type, cite_key, fields in matches:
        entry = f"@{entry_type}{{{cite_key},\n{fields}\n}}"
        entries.append(entry)
    
    return entries

def extract_from_arxiv_folder(arxiv_folder):
    """Extract all citations from an arXiv paper folder"""
    folder_path = Path(arxiv_folder)
    
    if not folder_path.exists():
        print(f"ERROR: Folder not found: {arxiv_folder}")
        return []
    
    all_citations = []
    
    # Look for .bib files first
    bib_files = list(folder_path.glob('*.bib')) + list(folder_path.glob('**/*.bib'))
    
    for bib_file in bib_files:
        citations = extract_bib_from_file(bib_file)
        all_citations.extend(citations)
        print(f"  Found {len(citations)} citations in {bib_file.name}")
    
    # Also check .tex files for inline bibliography
    tex_files = list(folder_path.glob('*.tex')) + list(folder_path.glob('**/*.tex'))
    
    for tex_file in tex_files:
        citations = extract_bib_from_file(tex_file)
        if citations:
            all_citations.extend(citations)
            print(f"  Found {len(citations)} citations in {tex_file.name}")
    
    return all_citations

def save_citations(citations, output_file, arxiv_id):
    """Save citations to a .bib file"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"% Citations extracted from arXiv paper {arxiv_id}\n")
        f.write(f"% Extraction date: {__import__('datetime').datetime.now().isoformat()}\n\n")
        
        for i, citation in enumerate(citations, 1):
            f.write(citation)
            f.write("\n\n")
    
    print(f"✓ Saved {len(citations)} citations to {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_citations_from_arxiv.py <arxiv_folder> [output_file]")
        print("\nExample:")
        print("  python extract_citations_from_arxiv.py 2604.05875/")
        print("  python extract_citations_from_arxiv.py 2604.05875/ real_citations/sample_001.bib")
        print("\nProcess all arXiv folders:")
        print("  python extract_citations_from_arxiv.py --all")
        sys.exit(1)
    
    if sys.argv[1] == '--all':
        # Process all arXiv folders in current directory
        arxiv_folders = [d for d in Path('.').iterdir() if d.is_dir() and re.match(r'\d{4}\.\d{5}', d.name)]
        
        print(f"Found {len(arxiv_folders)} arXiv folders\n")
        
        for i, folder in enumerate(arxiv_folders, 1):
            print(f"[{i}/{len(arxiv_folders)}] Processing {folder.name}...")
            citations = extract_from_arxiv_folder(folder)
            
            if citations:
                output_file = f"real_citations/arxiv_cs_2024/arxiv_{folder.name}.bib"
                save_citations(citations, output_file, folder.name)
            else:
                print(f"  No citations found in {folder.name}")
            
            print()
    else:
        # Process single folder
        arxiv_folder = sys.argv[1]
        arxiv_id = Path(arxiv_folder).name
        
        print(f"Processing arXiv paper: {arxiv_id}...")
        citations = extract_from_arxiv_folder(arxiv_folder)
        
        if not citations:
            print("No citations found!")
            sys.exit(1)
        
        if len(sys.argv) >= 3:
            output_file = sys.argv[2]
        else:
            output_file = f"real_citations/arxiv_cs_2024/arxiv_{arxiv_id}.bib"
        
        save_citations(citations, output_file, arxiv_id)

if __name__ == '__main__':
    main()
