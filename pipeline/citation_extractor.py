import re
import json
import redis.asyncio as redis
from typing import List, Dict, Any, Literal
from urllib.parse import urlparse, urlunparse
from app.config import settings
from app.models import CitationEdge

class CitationExtractor:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.url_regex = r'https?://[^\s<>"{}|\\^`\[\]]+(?<![.,;!?])'
        self.crossref_patterns = [
            r'(?i)(?:see|refer to|described in)\s+(?:Section|Chapter|Appendix)\s+([A-Z0-9.]+)',
            r'(?i)(?:see|described in|refer to)\s+\[([A-Za-z]+[0-9]{4})\]',
            r'(?i)refer\s+to\s+([A-Za-z]+\s+[A-Z0-9.]+)'
        ]
        self.footnote_patterns = [
            r'\[(\d+)\]',
            r'\(([A-Za-z]+,\s+\d{4})\)',
            r'(?i)\bibid\b'
        ]

    def _normalize_url(self, url: str) -> str:
        """Resolve to canonical URL (strip query params, normalize trailing slash)."""
        parsed = urlparse(url)
        # Normalize: strip query and fragment, lower case netloc
        normalized_path = parsed.path
        if not normalized_path.endswith('/') and '.' not in os.path.basename(normalized_path):
            normalized_path += '/'
        
        clean_url = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            normalized_path,
            '', # params
            '', # query
            ''  # fragment
        ))
        return clean_url

    def extract(self, doc_id: str, content: str, metadata: dict) -> List[CitationEdge]:
        edges = []
        
        # 1. Hyperlinks
        urls = re.findall(self.url_regex, content)
        for url in urls:
            normalized = self._normalize_url(url)
            edges.append(CitationEdge(
                source_doc_id=doc_id,
                target_doc_id=normalized,
                citation_type='hyperlink',
                weight=1.0,
                raw_text=url
            ))

        # 2. Cross-references
        for pattern in self.crossref_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                target_id = match.group(1) if match.groups() else match.group(0)
                edges.append(CitationEdge(
                    source_doc_id=doc_id,
                    target_doc_id=target_id,
                    citation_type='crossref',
                    weight=0.8,
                    raw_text=match.group(0)
                ))

        # 3. Footnotes/Endnotes
        for pattern in self.footnote_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                target_id = match.group(1) if match.groups() else match.group(0)
                edges.append(CitationEdge(
                    source_doc_id=doc_id,
                    target_doc_id=target_id,
                    citation_type='footnote',
                    weight=0.6,
                    raw_text=match.group(0)
                ))

        return self._aggregate_edges(edges)

    def _aggregate_edges(self, edges: List[CitationEdge]) -> List[CitationEdge]:
        """Sum weights and cap at 3.0 for same source-target pair."""
        agg = {} # (source, target) -> {total_weight, type, texts}
        
        for edge in edges:
            key = (edge.source_doc_id, edge.target_doc_id)
            if key not in agg:
                agg[key] = {
                    "weight": 0.0,
                    "type": edge.citation_type,
                    "texts": []
                }
            agg[key]["weight"] = min(agg[key]["weight"] + edge.weight, 3.0)
            agg[key]["texts"].append(edge.raw_text)
            
        return [
            CitationEdge(
                source_doc_id=k[0],
                target_doc_id=k[1],
                citation_type=v["type"],
                weight=v["weight"],
                raw_text="; ".join(v["texts"][:3]) # Limit display text
            ) for k, v in agg.items()
        ]

    async def store_edges(self, edges: List[CitationEdge]):
        """Store edges in Redis as sorted sets and a global list."""
        client = redis.from_url(self.redis_url)
        async with client.pipeline(transaction=True) as pipe:
            for edge in edges:
                # Local index
                pipe.zadd(f"citations:{edge.source_doc_id}", {edge.target_doc_id: edge.weight})
                # Reverse index
                pipe.zadd(f"cited_by:{edge.target_doc_id}", {edge.source_doc_id: edge.weight})
                # Global list for PageRank
                edge_json = f"{edge.source_doc_id},{edge.target_doc_id},{edge.weight}"
                pipe.rpush("citation_graph:edges", edge_json)
            await pipe.execute()

import os
citation_extractor = CitationExtractor()
