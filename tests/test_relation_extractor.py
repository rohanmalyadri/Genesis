import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from pipeline.relation_extractor import RelationExtractor
from app.models import EntityNode, RelationEdge

@pytest.fixture
async def extractor():
    # Mock models to avoid downloading 2GB of data during tests
    with patch("transformers.AutoTokenizer.from_pretrained") as mock_tok, \
         patch("transformers.AutoModelForSeq2SeqLM.from_pretrained") as mock_model, \
         patch("spacy.load") as mock_spacy:
        
        # Mock spaCy
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_ent = MagicMock()
        mock_ent.text = "Steve Jobs"
        mock_ent.label_ = "PERSON"
        mock_doc.ents = [mock_ent]
        mock_doc.sents = [MagicMock(text="Steve Jobs founded Apple.")]
        mock_nlp.return_value = mock_doc
        mock_spacy.return_value = mock_nlp
        
        # Mock REBEL
        mock_model_inst = MagicMock()
        mock_model_inst.generate.return_value = MagicMock(sequences=[[1, 2, 3]])
        mock_model.return_value = mock_model_inst
        
        mock_tok_inst = MagicMock()
        # Simulated REBEL output for "Steve Jobs founded Apple."
        mock_tok_inst.decode.return_value = "<triplet> Steve Jobs <subj> Apple <obj> founded"
        mock_tok.return_value = mock_tok_inst
        
        ex = RelationExtractor()
        yield ex

@pytest.mark.asyncio
async def test_normalization(extractor):
    assert extractor._normalize_entity(" USA ") == "United States"
    assert extractor._normalize_entity("fastapi") == "Fastapi"

@pytest.mark.asyncio
async def test_triplet_decoding(extractor):
    raw = "<triplet> Albert Einstein <subj> Relativity <obj> developed"
    triplets = extractor._extract_triplets(raw)
    assert len(triplets) == 1
    assert triplets[0]['head'] == "Albert Einstein"
    assert triplets[0]['tail'] == "Relativity"
    assert triplets[0]['type'] == "developed"

@pytest.mark.asyncio
async def test_extraction_logic(extractor):
    # Mock graph_store to avoid DB connection
    with patch("retrieval.graph_store.graph_store.search_entities_by_name", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [] # No existing entities
        
        entities, relations = await extractor.extract("Steve Jobs founded Apple.", "doc1")
        
        assert len(entities) >= 2
        assert any(e.name == "Steve Jobs" for e in entities)
        assert any(e.name == "Apple" for e in entities)
        
        assert len(relations) == 1
        assert relations[0].relation == "FOUNDED"
        assert relations[0].confidence >= 0.7
        assert "Steve Jobs" in relations[0].sentence
