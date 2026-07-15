import pytest
import asyncio
from testcontainers.neo4j import Neo4jContainer
from retrieval.graph_store import GraphStore
from app.models import EntityNode, RelationEdge
from app.config import settings

@pytest.fixture(scope="module")
def neo4j_container():
    with Neo4jContainer("neo4j:5.12.0") as neo4j:
        yield neo4j

@pytest.fixture(scope="module")
async def graph_store(neo4j_container):
    # Override settings with container info
    settings.NEO4J_URI = neo4j_container.get_connection_url()
    settings.NEO4J_USER = "neo4j"
    settings.NEO4J_PASSWORD = "password" # Testcontainers default
    
    store = GraphStore()
    await store.connect()
    yield store
    await store.close()

@pytest.mark.asyncio
async def test_upsert_and_retrieve_entity(graph_store):
    entity = EntityNode(
        id="ent1",
        name="Albert Einstein",
        type="Person",
        aliases=["Einstein"],
        doc_ids=["doc1"],
        embedding=[0.1, 0.2, 0.3]
    )
    
    eid = await graph_store.upsert_entity(entity)
    assert eid == "ent1"
    
    # Search by name
    results = await graph_store.search_entities_by_name("Einstein", fuzzy=True)
    assert len(results) > 0
    assert results[0].name == "Albert Einstein"

@pytest.mark.asyncio
async def test_upsert_relation_and_neighbors(graph_store):
    # Ensure entities exist
    e1 = EntityNode(id="e1", name="Python", type="Language")
    e2 = EntityNode(id="e2", name="FastAPI", type="Framework")
    await graph_store.upsert_entity(e1)
    await graph_store.upsert_entity(e2)
    
    # Create relation
    rel = RelationEdge(
        source_id="e2",
        target_id="e1",
        relation="BUILT_WITH",
        confidence=0.9
    )
    await graph_store.upsert_relation(rel)
    
    # Get neighbors
    neighbors = await graph_store.get_neighbors("e2")
    assert len(neighbors) > 0
    assert neighbors[0].entity.id == "e1"
    assert neighbors[0].relation == "BUILT_WITH"
    assert neighbors[0].confidence == 0.9

@pytest.mark.asyncio
async def test_shortest_path(graph_store):
    # e1 -> e2 -> e3
    e3 = EntityNode(id="e3", name="Uvicorn", type="Server")
    await graph_store.upsert_entity(e3)
    
    rel2 = RelationEdge(source_id="e3", target_id="e2", relation="RUNS")
    await graph_store.upsert_relation(rel2)
    
    path = await graph_store.get_shortest_path("e3", "e1")
    assert len(path) == 3 # e3 -> e2 -> e1
    assert path[0].entity.id == "e3"
    assert path[1].entity.id == "e2"
    assert path[2].entity.id == "e1"

@pytest.mark.asyncio
async def test_ping(graph_store):
    is_alive = await graph_store.ping()
    assert is_alive is True
