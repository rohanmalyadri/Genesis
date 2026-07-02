from neo4j import AsyncGraphDatabase
import asyncio
import logging
from typing import List, Optional, Dict, Any
from app.config import settings
from app.models import (
    EntityNode, RelationEdge, NeighborResult, PathStep, EntityContext
)

logger = logging.getLogger("GraphStore")

class GraphStore:
    def __init__(self):
        self.driver = None

    async def connect(self):
        """Initialize the Neo4j async driver and connection pool."""
        if not self.driver:
            logger.info(f"Connecting to Neo4j at {settings.NEO4J_URI}")
            self.driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_pool_size=50
            )
            await self._init_db()

    async def _init_db(self):
        """Run schema constraints and indexes on startup."""
        constraints = [
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)"
        ]
        async with self.driver.session() as session:
            for query in constraints:
                try:
                    await session.run(query)
                except Exception as e:
                    logger.error(f"Failed to run constraint/index: {query}. Error: {e}")

    async def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            await self.driver.close()
            self.driver = None

    async def ping(self) -> bool:
        """Health check for Neo4j connectivity."""
        if not self.driver:
            return False
        try:
            async with self.driver.session() as session:
                await session.run("RETURN 1")
                return True
        except Exception as e:
            logger.error(f"Neo4j ping failed: {e}")
            return False

    async def upsert_entity(self, entity: EntityNode) -> str:
        """Create or update an Entity node."""
        query = """
        MERGE (e:Entity {id: $id})
        SET e.name = $name,
            e.type = $type,
            e.aliases = $aliases,
            e.doc_ids = $doc_ids,
            e.embedding = $embedding
        RETURN e.id
        """
        async with self.driver.session() as session:
            result = await session.run(query, entity.model_dump())
            record = await result.single()
            return record["e.id"]

    async def upsert_relation(self, rel: RelationEdge) -> None:
        """
        Create or update a RELATED_TO relationship.
        Accumulates confidence as a running average.
        """
        query = """
        MERGE (s:Entity {id: $source_id})
        MERGE (t:Entity {id: $target_id})
        MERGE (s)-[r:RELATED_TO {relation: $relation}]->(t)
        ON CREATE SET r.confidence = $confidence, 
                      r.doc_id = $doc_id, 
                      r.sentence = $sentence,
                      r.count = 1
        ON MATCH SET r.confidence = (r.confidence * r.count + $confidence) / (r.count + 1),
                     r.count = r.count + 1,
                     r.doc_id = CASE WHEN $doc_id IS NOT NULL THEN $doc_id ELSE r.doc_id END
        """
        async with self.driver.session() as session:
            await session.run(query, rel.model_dump())

    async def upsert_all(self, entities: List[EntityNode], relations: List[RelationEdge]) -> None:
        """Batch upsert entities and relations in a single transaction."""
        async with self.driver.session() as session:
            async with await session.begin_transaction() as tx:
                # 1. Upsert Entities
                entity_query = """
                UNWIND $entities AS ent
                MERGE (e:Entity {id: ent.id})
                SET e.name = ent.name,
                    e.type = ent.type,
                    e.aliases = ent.aliases,
                    e.doc_ids = ent.doc_ids,
                    e.embedding = ent.embedding
                """
                await tx.run(entity_query, {"entities": [e.model_dump() for e in entities]})

                # 2. Upsert Relations
                rel_query = """
                UNWIND $rels AS rel
                MATCH (s:Entity {id: rel.source_id})
                MATCH (t:Entity {id: rel.target_id})
                MERGE (s)-[r:RELATED_TO {relation: rel.relation}]->(t)
                ON CREATE SET r.confidence = rel.confidence, 
                              r.doc_id = rel.doc_id, 
                              r.sentence = rel.sentence,
                              r.count = 1
                ON MATCH SET r.confidence = (r.confidence * r.count + rel.confidence) / (r.count + 1),
                             r.count = r.count + 1,
                             r.doc_id = CASE WHEN rel.doc_id IS NOT NULL THEN rel.doc_id ELSE r.doc_id END
                """
                await tx.run(rel_query, {"rels": [r.model_dump() for r in relations]})

    async def get_neighbors(
        self, 
        entity_id: str, 
        relation_types: List[str] = None, 
        min_confidence: float = 0.5, 
        limit: int = 20
    ) -> List[NeighborResult]:
        """Retrieve neighboring entities based on relation types and confidence."""
        # Note: relation_types filter is simplified here to RELATED_TO as per schema
        query = """
        MATCH (s:Entity {id: $entity_id})-[r:RELATED_TO]->(t:Entity)
        WHERE r.confidence >= $min_confidence
        RETURN t, r.relation, r.confidence
        LIMIT $limit
        """
        neighbors = []
        async with self.driver.session() as session:
            result = await session.run(query, {
                "entity_id": entity_id,
                "min_confidence": min_confidence,
                "limit": limit
            })
            async for record in result:
                node = record["t"]
                neighbors.append(NeighborResult(
                    entity=EntityNode(
                        id=node["id"],
                        name=node["name"],
                        type=node["type"],
                        aliases=node.get("aliases", []),
                        doc_ids=node.get("doc_ids", []),
                        embedding=node.get("embedding")
                    ),
                    relation=record["r.relation"],
                    confidence=record["r.confidence"]
                ))
        return neighbors

    async def get_shortest_path(self, source_id: str, target_id: str, max_hops: int = 5) -> List[PathStep]:
        """Find the shortest path between two entities."""
        query = """
        MATCH (start:Entity {id: $source_id}), (end:Entity {id: $target_id})
        MATCH p = shortestPath((start)-[:RELATED_TO*..$max_hops]-(end))
        RETURN p
        """
        async with self.driver.session() as session:
            result = await session.run(query, {
                "source_id": source_id,
                "target_id": target_id,
                "max_hops": max_hops
            })
            record = await result.single()
            if not record:
                return []
            
            path = record["p"]
            steps = []
            
            # Start node
            start_node = path.start_node
            steps.append(PathStep(
                entity=EntityNode(
                    id=start_node["id"],
                    name=start_node["name"],
                    type=start_node["type"]
                )
            ))
            
            # Relationships and intermediate nodes
            for rel in path.relationships:
                target_node = rel.end_node if rel.start_node == start_node else rel.start_node
                direction = "out" if rel.start_node == start_node else "in"
                
                steps.append(PathStep(
                    entity=EntityNode(
                        id=target_node["id"],
                        name=target_node["name"],
                        type=target_node["type"]
                    ),
                    relation=rel["relation"],
                    direction=direction
                ))
                start_node = target_node
                
            return steps

    async def search_entities_by_name(self, name: str, fuzzy: bool = True, limit: int = 10) -> List[EntityNode]:
        """Search entities by name using fuzzy matching (requires APOC) or standard ILIKE."""
        if fuzzy:
            query = """
            CALL apoc.index.search('entity_name', $name + '~') YIELD node, weight
            RETURN node LIMIT $limit
            """
            # Fallback if APOC index is not configured yet
            fallback_query = """
            MATCH (e:Entity)
            WHERE e.name =~ ('(?i).*' + $name + '.*')
            RETURN e LIMIT $limit
            """
        else:
            query = """
            MATCH (e:Entity)
            WHERE e.name = $name
            RETURN e LIMIT $limit
            """

        async with self.driver.session() as session:
            try:
                result = await session.run(query, {"name": name, "limit": limit})
                records = await result.list()
            except Exception:
                if fuzzy:
                    result = await session.run(fallback_query, {"name": name, "limit": limit})
                    records = await result.list()
                else:
                    return []

            entities = []
            for record in records:
                node = record.get("node") or record.get("e")
                entities.append(EntityNode(
                    id=node["id"],
                    name=node["name"],
                    type=node["type"],
                    aliases=node.get("aliases", []),
                    doc_ids=node.get("doc_ids", []),
                    embedding=node.get("embedding")
                ))
            return entities

    async def get_entity_context(self, entity_id: str) -> EntityContext:
        """Get entity details, its relations, and top appearing documents."""
        # 1. Get Entity
        query_entity = "MATCH (e:Entity {id: $entity_id}) RETURN e"
        async with self.driver.session() as session:
            res_e = await session.run(query_entity, {"entity_id": entity_id})
            rec_e = await res_e.single()
            if not rec_e:
                raise ValueError(f"Entity {entity_id} not found")
            
            node = rec_e["e"]
            entity = EntityNode(
                id=node["id"],
                name=node["name"],
                type=node["type"],
                aliases=node.get("aliases", []),
                doc_ids=node.get("doc_ids", []),
                embedding=node.get("embedding")
            )

            # 2. Get Relations
            relations = await self.get_neighbors(entity_id, limit=10)

            # 3. Get Top Documents
            query_docs = """
            MATCH (e:Entity {id: $entity_id})-[r:MENTIONED_IN]->(d:Document)
            RETURN d.id, d.title, d.source, d.pagerank_score
            ORDER BY r.count DESC LIMIT 3
            """
            res_d = await session.run(query_docs, {"entity_id": entity_id})
            top_docs = []
            async for rec in res_d:
                top_docs.append({
                    "id": rec["d.id"],
                    "title": rec["d.title"],
                    "source": rec["d.source"],
                    "pagerank_score": rec["d.pagerank_score"]
                })

            return EntityContext(
                entity=entity,
                relations=relations,
                top_docs=top_docs
            )

graph_store = GraphStore()
