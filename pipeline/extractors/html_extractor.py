from bs4 import BeautifulSoup
import re

class HTMLExtractor:
    def extract(self, html_content: str) -> str:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1. Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
            
        # 2. Preserve headings by adding markdown markers
        for i in range(1, 7):
            for heading in soup.find_all(f"h{i}"):
                heading.insert_before(f"\n{'#' * i} ")
                heading.insert_after("\n")
                
        # 3. Extract text
        text = soup.get_text(separator="\n")
        
        # 4. Cleanup
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        return text

html_extractor = HTMLExtractor()
