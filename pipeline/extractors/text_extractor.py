import chardet

class TextExtractor:
    def extract(self, file_path: str) -> str:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'
            return raw_data.decode(encoding)

text_extractor = TextExtractor()
