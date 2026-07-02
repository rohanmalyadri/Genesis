import docx
from tabulate import tabulate

class DOCXExtractor:
    def extract(self, file_path: str) -> str:
        doc = docx.Document(file_path)
        content = []
        
        for element in doc.element.body:
            # Handle Paragraphs (including Headings)
            if element.tag.endswith('p'):
                para = docx.text.paragraph.Paragraph(element, doc)
                text = para.text.strip()
                if not text:
                    continue
                    
                # Detect heading levels
                if para.style.name.startswith('Heading'):
                    try:
                        level = int(para.style.name.split()[-1])
                        content.append(f"\n{'#' * level} {text}\n")
                    except:
                        content.append(text)
                else:
                    content.append(text)
                    
            # Handle Tables
            elif element.tag.endswith('tbl'):
                table = docx.table.Table(element, doc)
                data = []
                for row in table.rows:
                    data.append([cell.text.replace("\n", " ").strip() for cell in row.cells])
                
                if data:
                    md_table = tabulate(data, tablefmt="github", headers="firstrow")
                    content.append(f"\n\n{md_table}\n\n")
                    
        return "\n".join(content)

docx_extractor = DOCXExtractor()
