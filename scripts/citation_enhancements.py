"""
Enhanced Citation Validation Heuristics
Improvements for detecting hallucinated citations
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple


class EnhancedValidator:
    """Additional heuristics for detecting suspicious citations."""
    
    @staticmethod
    def check_suspicious_patterns(entry: Dict) -> List[str]:
        """Check for patterns common in hallucinated citations."""
        warnings = []
        fields = entry['fields']
        
        # 1. Check for generic/vague titles
        title = fields.get('title', '').lower()
        generic_terms = [
            'a study of', 'an analysis of', 'research on', 
            'investigation into', 'overview of', 'review of'
        ]
        if any(term in title for term in generic_terms) and len(title) < 50:
            warnings.append("Generic title pattern (common in hallucinations)")
        
        # 2. Check for suspiciously generic author names
        author = fields.get('author', '')
        if author:
            # Common AI-generated names or patterns
            generic_authors = ['smith', 'jones', 'johnson', 'et al', 'unknown']
            if any(gen in author.lower() for gen in generic_authors) and len(author) < 20:
                warnings.append("Generic author name pattern")
        
        # 3. Check for year-related issues
        year = fields.get('year', '')
        if year:
            try:
                year_int = int(year)
                current_year = datetime.now().year
                if year_int > current_year:
                    warnings.append(f"Future year ({year}) - likely hallucinated")
                elif year_int < 1900:
                    warnings.append(f"Suspiciously old year ({year})")
            except ValueError:
                warnings.append(f"Invalid year format: {year}")
        
        # 4. Check for malformed URLs/DOIs
        url = fields.get('url', '')
        if url and not url.startswith(('http://', 'https://', 'www.')):
            warnings.append("Malformed URL")
        
        # 5. Check for inconsistent venue information
        journal = fields.get('journal', '')
        booktitle = fields.get('booktitle', '')
        if journal and booktitle:
            # Shouldn't have both for same entry
            warnings.append("Both journal and booktitle present (inconsistent)")
        
        # 6. Check for missing critical fields
        entry_type = entry['type'].lower()
        if entry_type == 'article' and not journal and not fields.get('doi'):
            warnings.append("Article entry missing journal and DOI")
        elif entry_type == 'inproceedings' and not booktitle:
            warnings.append("Conference paper missing booktitle")
        
        # 7. Check for suspiciously short or long field values
        if title and len(title) < 5:
            warnings.append("Suspiciously short title")
        if author and len(author) < 5:
            warnings.append("Suspiciously short author")
        
        # 8. arXiv papers with a proper arXiv DOI are legitimate — skip
        #    Only check the DOI field, not all fields (a fake citation
        #    mentioning "arxiv" in a note/url shouldn't get a free pass).
        if fields.get('doi', '').lower().startswith('10.48550/arxiv.'):
            return warnings

        return warnings
    
    @staticmethod
    def extract_author_list(author_string: str) -> List[str]:
        """Parse author string into list of names."""
        if not author_string:
            return []
        
        # Split on 'and' or ','
        authors = re.split(r'\s+and\s+|,\s+', author_string)
        # Clean up
        authors = [a.strip() for a in authors if a.strip()]
        return authors
    
    @staticmethod
    def calculate_metadata_similarity(bib_fields: Dict, verified_data: Dict) -> float:
        """Calculate similarity score between BibTeX and verified metadata."""
        score = 0.0
        checks = 0
        
        # Compare title
        if 'title' in bib_fields and 'title' in verified_data:
            checks += 1
            bib_title = bib_fields['title'].lower().strip()
            ver_title = str(verified_data['title']).lower().strip()
            
            # Jaccard similarity of words
            bib_words = set(re.findall(r'\w+', bib_title))
            ver_words = set(re.findall(r'\w+', ver_title))
            
            if bib_words and ver_words:
                overlap = len(bib_words & ver_words)
                union = len(bib_words | ver_words)
                score += overlap / union if union > 0 else 0
        
        # Compare year
        if 'year' in bib_fields:
            checks += 1
            bib_year = str(bib_fields['year'])
            
            # Extract year from verified data (could be in various formats)
            ver_year = None
            if 'published' in verified_data:
                date_parts = verified_data['published'].get('date-parts', [[]])[0]
                if date_parts:
                    ver_year = str(date_parts[0])
            elif 'publication_year' in verified_data:
                ver_year = str(verified_data['publication_year'])
            
            if ver_year and bib_year == ver_year:
                score += 1.0
        
        # Compare authors
        if 'author' in bib_fields and 'author' in verified_data:
            checks += 1
            bib_authors = EnhancedValidator.extract_author_list(bib_fields['author'])
            
            # Verified authors might be in different format
            ver_authors = []
            if isinstance(verified_data['author'], list):
                for author in verified_data['author']:
                    if isinstance(author, dict):
                        name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                        ver_authors.append(name)
                    else:
                        ver_authors.append(str(author))
            
            if bib_authors and ver_authors:
                # Check for any overlapping author names
                bib_names_lower = [a.lower() for a in bib_authors]
                ver_names_lower = [a.lower() for a in ver_authors]
                
                overlap = any(
                    any(b_name in v_name or v_name in b_name 
                        for v_name in ver_names_lower)
                    for b_name in bib_names_lower
                )
                score += 1.0 if overlap else 0.0
        
        return score / checks if checks > 0 else 0.0
    
    @staticmethod
    def check_temporal_consistency(cite_year: str, referencing_year: str = "2026") -> List[str]:
        """Check if citation year makes sense given when it's being cited."""
        warnings = []
        
        try:
            cite_y = int(cite_year)
            ref_y = int(referencing_year)
            
            if cite_y > ref_y:
                warnings.append(f"Citation from future ({cite_y} > {ref_y})")
            elif cite_y == ref_y:
                # Same year citations are fine but noteworthy
                pass
            elif ref_y - cite_y > 50:
                warnings.append(f"Very old citation ({cite_y}, {ref_y - cite_y} years old)")
        except ValueError:
            pass
        
        return warnings
    
    @staticmethod
    def improved_ai_prompt(entry: Dict, metadata: Dict, suspicion_reasons: List[str]) -> str:
        """Generate enhanced prompt for AI analysis with more context."""
        fields = entry['fields']
        
        prompt = f"""You are an expert at detecting AI-hallucinated academic citations. Analyze this citation for signs of fabrication.

**Citation Details:**
- Title: {fields.get('title', 'N/A')}
- Author(s): {fields.get('author', 'N/A')}
- Year: {fields.get('year', 'N/A')}
- Venue: {fields.get('journal', fields.get('booktitle', 'N/A'))}
- DOI: {fields.get('doi', 'N/A')}
- Type: {entry['type']}

**Verified Database Results:**
{metadata if metadata else 'No match found in CrossRef or OpenAlex'}

**Automated Suspicion Flags:**
{chr(10).join(f'- {reason}' for reason in suspicion_reasons) if suspicion_reasons else 'None detected'}

**Common Hallucination Patterns:**
- "Frankenstein citations": Mixing real author names with fake titles/venues
- Generic titles with real-sounding but fabricated metadata
- Plausible but non-existent DOIs
- Real venues with fabricated article titles
- Mixing year/author/title from different papers

**Your Task:**
Assess if this citation shows signs of being AI-generated or fabricated. Consider:
1. Internal consistency of metadata
2. Match with verified data (if any)
3. Presence of generic/suspicious patterns
4. Overall plausibility

Return ONLY valid JSON:
{{
  "is_suspicious": true/false,
  "confidence": 0-100,  
  "reason": "specific explanation of why suspicious/not",
  "hallucination_type": "frankenstein|generic|fake|none",
  "red_flags": ["list", "of", "specific", "concerns"]
}}"""
        
        return prompt
