import shutil
import subprocess
from typing import List, Tuple

import pdfplumber
import pytesseract
from PIL import Image
from tabulate import tabulate

class PDFExtractor:
    def extract(self, file_path: str) -> str:
        return "\n".join(self.extract_pages(file_path))

    def extract_pages(self, file_path: str) -> List[str]:
        """Return one text block per PDF page."""
        from app.config import settings
        if settings.PDF_ENGINE == "poppler" and shutil.which("pdftotext"):
            return self._extract_pages_poppler(file_path)
        return self._extract_pages_pdfplumber(file_path)

    def _extract_pages_poppler(self, file_path: str) -> List[str]:
        """Fast, low-memory text extraction with poppler's pdftotext (pages are split by form feeds).
        Pages with almost no text fall back to the OCR path of the pdfplumber extractor."""
        out = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", file_path, "-"],
            capture_output=True, check=True, timeout=120,
        ).stdout.decode("utf-8", errors="replace")
        pages = out.split("\f")
        if pages and not pages[-1].strip():
            pages.pop()  # trailing form feed
        if any(len(p.strip()) < 50 for p in pages):
            return self._extract_pages_pdfplumber(file_path)  # scanned pages need OCR
        return pages

    def _extract_pages_pdfplumber(self, file_path: str) -> List[str]:
        """Page text plus tables rendered as markdown; OCR for pages without text."""
        pages: List[str] = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                content = []
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
                pages.append("\n".join(content))
                page.flush_cache()  # release this page's parsed objects before the next one
                del page_text
        import gc
        gc.collect()
        return pages

pdf_extractor = PDFExtractor()
