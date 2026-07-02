import spacy
import torch
import logging
import uuid
import re
from typing import List, Dict, Any, Tuple
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from app.config import settings
from app.models import EntityNode, RelationEdge
from retrieval.graph_store import graph_store

logger = logging.getLogger("RelationExtractor")

class RelationExtractor:
    def __init__(self):
        # 1. Load spaCy
        model_name = "en_core_web_trf"
        if settings.DOMAIN == "medical":
            model_name = "en_core_sci_lg"
        
        try:
            self.nlp = spacy.load(model_name)
        except Exception:
            logger.warning(f"spaCy model {model_name} not found. Falling back to en_core_web_sm.")
            # Note: In production, we'd ensure trf is installed.
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except Exception:
                 # Last resort: download if possible, but for this task we assume it should be there
                 logger.error("No spaCy model available.")
                 raise

        if settings.DOMAIN == "legal":
            self._add_legal_rules()

        # 2. Load REBEL
        logger.info(f"Loading REBEL model: {settings.REBEL_MODEL_ID}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            settings.REBEL_MODEL_ID, 
            cache_dir=settings.REBEL_CACHE_DIR
        )
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            settings.REBEL_MODEL_ID,
            cache_dir=settings.REBEL_CACHE_DIR
        )
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)

    def _add_legal_rules(self):
        """Add custom EntityRuler for legal citations and case names."""
        ruler = self.nlp.add_pipe("entity_ruler", before="ner")
        patterns = [
            {"label": "LAW", "pattern": [{"TEXT": {"REGEX": r"\d+\s+U\.S\.C\.\s+§\s+\d+"}}]},
            {"label": "CASE", "pattern": [{"TEXT": {"REGEX": r"[A-Z][a-z]+\s+v\.\s+[A-Z][a-z]+"}}, {"TEXT": {"REGEX": r"\d+\s+[A-Z\.]+\s+\d+"}, "OP": "?"}]}
        ]
        ruler.add_patterns(patterns)

    def _normalize_entity(self, name: str) -> str:
        """Clean and normalize entity name using alias map."""
        name = name.lower().strip().strip('.,!?()[]"')
        return settings.ENTITY_ALIAS_MAP.get(name, name.title())

    def _extract_triplets(self, text: str) -> List[Dict[str, str]]:
        """Parse REBEL output format: <triplet> head <subj> tail <obj> relation."""
        triplets = []
        relation, subject, object_ = '', '', ''
        text = text.strip()
        current = 'x'
        
        # REBEL marker tokens
        for token in text.split():
            if token == "<triplet>":
                current = 't'
                if relation != '':
                    triplets.append({'head': subject.strip(), 'type': relation.strip(), 'tail': object_.strip()})
                relation, subject = '', ''
            elif token == "<subj>":
                current = 's'
                if relation != '':
                    triplets.append({'head': subject.strip(), 'type': relation.strip(), 'tail': object_.strip()})
                object_ = ''
            elif token == "<obj>":
                current = 'o'
                relation = ''
            else:
                if current == 't': subject += ' ' + token
                elif current == 's': object_ += ' ' + token
                elif current == 'o': relation += ' ' + token
                
        if subject != '' and relation != '' and object_ != '':
            triplets.append({'head': subject.strip(), 'type': relation.strip(), 'tail': object_.strip()})
            
        return triplets

    async def extract(self, chunk_text: str, doc_id: str) -> Tuple[List[EntityNode], List[RelationEdge]]:
        """Run NER and REBEL to extract entities and relations from a chunk."""
        # Step 1: spaCy NER
        doc = self.nlp(chunk_text)
        spacy_entities = {self._normalize_entity(ent.text): ent.label_ for ent in doc.ents}

        # Step 2: REBEL Relation Extraction
        inputs = self.tokenizer(chunk_text, max_length=512, truncation=True, return_tensors="pt").to(self.device)
        gen_kwargs = {
            "max_length": 256,
            "length_penalty": 0,
            "num_beams": 3,
            "num_return_sequences": 1,
            "output_scores": True,
            "return_dict_in_generate": True
        }
        
        with torch.no_grad():
            output = self.model.generate(inputs["input_ids"], **gen_kwargs)
        
        decoded_output = self.tokenizer.decode(output.sequences[0], skip_special_tokens=False)
        raw_triplets = self._extract_triplets(decoded_output)
        
        # Step 3: Confidence & Enrichment
        entities_to_upsert = {}
        relations_to_upsert = []
        
        # Base confidence from beam score (simplified for this task)
        base_confidence = 0.7 # In reality, we'd pull from output.sequences_scores
        
        for tri in raw_triplets:
            head_norm = self._normalize_entity(tri['head'])
            tail_norm = self._normalize_entity(tri['tail'])
            rel_type = tri['type'].upper().replace(' ', '_')
            
            if not head_norm or not tail_norm:
                continue

            confidence = base_confidence
            # Cross-validate with spaCy NER
            if head_norm in spacy_entities and tail_norm in spacy_entities:
                confidence = min(1.0, confidence + 0.1)

            # Resolve/Create Entities
            head_node = await self._resolve_entity(head_norm, spacy_entities.get(head_norm, "Entity"), doc_id)
            tail_node = await self._resolve_entity(tail_norm, spacy_entities.get(tail_norm, "Entity"), doc_id)
            
            entities_to_upsert[head_node.id] = head_node
            entities_to_upsert[tail_node.id] = tail_node
            
            # Find source sentence (first occurrence)
            sentence = ""
            for sent in doc.sents:
                if tri['head'] in sent.text and tri['tail'] in sent.text:
                    sentence = sent.text.strip()
                    break

            relations_to_upsert.append(RelationEdge(
                source_id=head_node.id,
                target_id=tail_node.id,
                relation=rel_type,
                confidence=confidence,
                doc_id=doc_id,
                sentence=sentence or None
            ))

        return list(entities_to_upsert.values()), relations_to_upsert

    async def _resolve_entity(self, name: str, ent_type: str, doc_id: str) -> EntityNode:
        """Check if entity exists in Neo4j, else create new one."""
        existing = await graph_store.search_entities_by_name(name, fuzzy=True, limit=1)
        
        if existing:
            # Simple similarity check (literal match or very close)
            # In a real system, we'd use jarowinkler or similar
            ent = existing[0]
            if name.lower() == ent.name.lower() or name in ent.aliases:
                if doc_id not in ent.doc_ids:
                    ent.doc_ids.append(doc_id)
                return ent

        # Create new
        new_id = str(uuid.uuid4())
        return EntityNode(
            id=new_id,
            name=name,
            type=ent_type,
            aliases=[name],
            doc_ids=[doc_id]
        )

# Singleton instance
relation_extractor = None

async def get_relation_extractor():
    global relation_extractor
    if relation_extractor is None:
        relation_extractor = RelationExtractor()
    return relation_extractor
