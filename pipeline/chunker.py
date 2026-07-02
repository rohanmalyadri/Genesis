import tiktoken
import ast
from typing import List

class Chunker:
    def __init__(self, max_tokens: int = 512, overlap: int = 64):
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.separators = ["\n\n", "\n", ". ", " "]

    def _count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def split_text(self, text: str, file_ext: str = "") -> List[str]:
        # Special handling for code files using AST
        if file_ext == ".py":
            try:
                return self._split_python_code(text)
            except Exception as e:
                print(f"Chunker AST parsing failed: {e}. Falling back to recursive splitting.")
                
        return self._recursive_split(text, self.separators)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        final_chunks = []
        
        # If text is small enough, return as is
        if self._count_tokens(text) <= self.max_tokens:
            return [text]
            
        # Recursive splitting logic
        if separators:
            sep = separators[0]
            parts = text.split(sep)
            
            current_chunk = ""
            for part in parts:
                if self._count_tokens(current_chunk + sep + part) <= self.max_tokens:
                    current_chunk += (sep if current_chunk else "") + part
                else:
                    if current_chunk:
                        final_chunks.append(current_chunk)
                    # If the part itself is too large, split it with the next separator
                    if self._count_tokens(part) > self.max_tokens:
                        final_chunks.extend(self._recursive_split(part, separators[1:]))
                        current_chunk = ""
                    else:
                        current_chunk = part
            if current_chunk:
                final_chunks.append(current_chunk)
        else:
            # Absolute fallback: split by tokens if no separators left
            tokens = self.tokenizer.encode(text)
            for i in range(0, len(tokens), self.max_tokens - self.overlap):
                chunk_tokens = tokens[i:i + self.max_tokens]
                final_chunks.append(self.tokenizer.decode(chunk_tokens))
                
        return final_chunks

    def _split_python_code(self, code: str) -> List[str]:
        """Split Python code using AST nodes as boundaries."""
        tree = ast.parse(code)
        chunks = []
        current_chunk = []
        
        for node in ast.iter_child_nodes(tree):
            node_code = ast.get_source_segment(code, node) or ""
            if self._count_tokens("\n".join(current_chunk) + "\n" + node_code) <= self.max_tokens:
                current_chunk.append(node_code)
            else:
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                current_chunk = [node_code]
                
        if current_chunk:
            chunks.append("\n".join(current_chunk))
            
        return chunks

chunker = Chunker()
