import pdfplumber
import pytesseract
from PIL import Image
from tabulate import tabulate
from typing import List, Tuple

class PDFExtractor:
    def extract(self, file_path: str) -> str:
        content = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                
                # 1. Fallback to OCR if text is sparse
                if len(page_text.strip()) < 50:
                    print(f"PDFExtractor: Sparse text on page {i}, falling back to OCR...")
                    pil_image = page.to_image(resolution=300).original
                    page_text = pytesseract.image_to_string(pil_image, lang='eng', config='--psm 6')
                
                content.append(page_text)
                
                # 2. Extract tables and convert to markdown
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        # Clean table data (remove None, replace newlines)
                        clean_table = [[str(cell).replace("\n", " ") if cell is not None else "" for cell in row] for row in table]
                        md_table = tabulate(clean_table, tablefmt="github", headers="firstrow")
                        content.append(f"\n\n{md_table}\n\n")
                        
        return "\n".join(content)

pdf_extractor = PDFExtractor()
