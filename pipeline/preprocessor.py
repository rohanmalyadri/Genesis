import unicodedata
import re
import hashlib
from typing import List, Dict

class Preprocessor:
    def __init__(self):
        self.header_footer_hashes: Dict[str, int] = {}
        self.threshold = 3

    def normalize(self, text: str) -> str:
        # 1. Unicode normalization (NFKC)
        text = unicodedata.normalize('NFKC', text)
        
        # 2. Collapse whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def strip_headers_footers(self, pages: List[str]) -> List[str]:
        """Detect and strip repeated headers/footers across multiple pages."""
        if len(pages) < self.threshold:
            return pages
            
        header_hashes = {}
        footer_hashes = {}
        
        # Count hashes of first and last 100 chars
        for page in pages:
            if len(page) < 200: continue
            h = hashlib.md5(page[:100].strip().encode()).hexdigest()
            f = hashlib.md5(page[-100:].strip().encode()).hexdigest()
            header_hashes[h] = header_hashes.get(h, 0) + 1
            footer_hashes[f] = footer_hashes.get(f, 0) + 1
            
        # Clean pages
        clean_pages = []
        for page in pages:
            if len(page) < 200:
                clean_pages.append(page)
                continue
                
            h = hashlib.md5(page[:100].strip().encode()).hexdigest()
            f = hashlib.md5(page[-100:].strip().encode()).hexdigest()
            
            start_idx = 100 if header_hashes.get(h, 0) >= self.threshold else 0
            end_idx = -100 if footer_hashes.get(f, 0) >= self.threshold else None
            
            clean_pages.append(page[start_idx:end_idx].strip())
            
        return clean_pages

preprocessor = Preprocessor()
