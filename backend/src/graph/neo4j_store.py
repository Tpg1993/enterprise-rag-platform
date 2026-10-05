"""Neo4j Graph Database client supporting multi-hop Cypher retrieval,
tenant isolation, and in-memory fallback.
"""

import logging
from collections import deque
from typing import Any

from src.config.loader import get_settings
from src.graph.extractor import EntityTriple

logger = logging.getLogger(__name__)


class Neo4jGraphStore:
    """Manages knowledge graph storage and multi-hop Cypher queries in Neo4j
    with tenant isolation.
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        settings = get_settings()
        self.uri = uri or settings.graph_store.neo4j_uri
        self.user = user or settings.graph_store.neo4j_user
        self.password = password or settings.graph_store.neo4j_password
        self.max_hops = settings.graph_store.max_hops

        self.driver: Any = None
        self._memory_nodes: dict[str, dict[str, Any]] = {}
        self._memory_edges: list[dict[str, Any]] = []

        self._connect()

    def _connect(self) -> None:
        """Attempts connection to Neo4j; falls back gracefully to in-memory mode."""
        try:
            from neo4j import GraphDatabase

            # Test connection with short timeout
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                connection_timeout=0.5,
                max_connection_lifetime=30,
            )
            # Verify connectivity
            with self.driver.session() as session:
                session.run("RETURN 1 AS ping")
            logger.info(f"Connected successfully to Neo4j at {self.uri}")
        except Exception as e:
            logger.warning(
                f"Could not connect to Neo4j at {self.uri} ({e}). "
                "Operating in resilient in-memory graph mode."
            )
            self.driver = None

    def close(self) -> None:
        """Closes Neo4j driver connection if initialized."""
        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
            self.driver = None

    def upsert_triples(
        self,
        triples: list[EntityTriple],
        tenant_id: str,
        doc_id: str = "doc_default",
        chunk_id: str = "chunk_default",
    ) -> int:
        """Upserts entity nodes and directed relationships with tenant isolation."""
        if not triples:
            return 0

        if self.driver:
            try:
                return self._upsert_triples_neo4j(triples, tenant_id, doc_id, chunk_id)
            except Exception as e:
                logger.error(f"Neo4j upsert error ({e}), falling back to memory store.")

        # In-memory store fallback
        count = 0
        for t in triples:
            s_name = t.subject.strip()
            o_name = t.object.strip()
            pred = t.predicate.strip().upper().replace(" ", "_")

            s_key = f"{tenant_id}::{s_name.lower()}"
            o_key = f"{tenant_id}::{o_name.lower()}"

            self._memory_nodes[s_key] = {
                "name": s_name,
                "type": t.subject_type,
                "tenant_id": tenant_id,
            }
            self._memory_nodes[o_key] = {
                "name": o_name,
                "type": t.object_type,
                "tenant_id": tenant_id,
            }

            # Check if edge already exists
            exists = any(
                e["source"].lower() == s_name.lower()
                and e["target"].lower() == o_name.lower()
                and e["predicate"] == pred
                and e["tenant_id"] == tenant_id
                for e in self._memory_edges
            )
            if not exists:
                self._memory_edges.append(
                    {
                        "source": s_name,
                        "predicate": pred,
                        "target": o_name,
                        "tenant_id": tenant_id,
                        "doc_id": doc_id,
                        "chunk_id": chunk_id,
                        "confidence": t.confidence,
                    }
                )
                count += 1
            else:
                count += 1

        return count

    def _upsert_triples_neo4j(
        self,
        triples: list[EntityTriple],
        tenant_id: str,
        doc_id: str,
        chunk_id: str,
    ) -> int:
        """Executes Cypher MERGE commands for entities and relationships in Neo4j."""
        cypher = """
        UNWIND $batch AS item
        MERGE (s:Entity {tenant_id: $tenant_id, name: item.subject})
          ON CREATE SET s.type = item.subject_type
        MERGE (o:Entity {tenant_id: $tenant_id, name: item.object})
          ON CREATE SET o.type = item.object_type
        MERGE (s)-[r:RELATION {predicate: item.predicate, tenant_id: $tenant_id}]->(o)
          ON CREATE SET r.doc_id = $doc_id, r.chunk_id = $chunk_id, r.confidence = item.confidence
        RETURN count(r) AS upserted_count
        """
        batch = [
            {
                "subject": t.subject.strip(),
                "predicate": t.predicate.strip().upper().replace(" ", "_"),
                "object": t.object.strip(),
                "subject_type": t.subject_type,
                "object_type": t.object_type,
                "confidence": t.confidence,
            }
            for t in triples
        ]

        with self.driver.session() as session:
            result = session.run(
                cypher,
                batch=batch,
                tenant_id=tenant_id,
                doc_id=doc_id,
                chunk_id=chunk_id,
            )
            record = result.single()
            return record["upserted_count"] if record else len(batch)

    def search_subgraph(
        self,
        query_entities: list[str],
        tenant_id: str,
        max_hops: int | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Multi-hop knowledge graph traversal starting from specified seed entities."""
        hops = max_hops or self.max_hops
        cleaned_entities = [e.strip().lower() for e in query_entities if e.strip()]

        if not cleaned_entities:
            return []

        if self.driver:
            try:
                return self._search_subgraph_neo4j(cleaned_entities, tenant_id, hops, limit)
            except Exception as e:
                logger.warning(f"Neo4j subgraph search error ({e}), falling back to memory.")

        # In-memory multi-hop BFS traversal
        return self._search_subgraph_memory(cleaned_entities, tenant_id, hops, limit)

    def _search_subgraph_neo4j(
        self,
        entities: list[str],
        tenant_id: str,
        hops: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Cypher variable length path query with tenant filtering."""
        cypher = f"""
        MATCH (s:Entity {{tenant_id: $tenant_id}})
        WHERE toLower(s.name) IN $entities
        MATCH path = (s)-[r:RELATION*1..{hops}]-(target:Entity {{tenant_id: $tenant_id}})
        UNWIND relationships(path) AS rel
        WITH DISTINCT startNode(rel) AS src, rel, endNode(rel) AS tgt
        RETURN src.name AS source, rel.predicate AS predicate, tgt.name AS target,
               rel.doc_id AS doc_id, rel.chunk_id AS chunk_id, rel.confidence AS confidence
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(
                cypher,
                tenant_id=tenant_id,
                entities=entities,
                limit=limit,
            )
            return [
                {
                    "source": rec["source"],
                    "predicate": rec["predicate"],
                    "target": rec["target"],
                    "doc_id": rec.get("doc_id", ""),
                    "chunk_id": rec.get("chunk_id", ""),
                    "confidence": rec.get("confidence", 1.0),
                }
                for rec in result
            ]

    def _search_subgraph_memory(
        self,
        entities: list[str],
        tenant_id: str,
        hops: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """BFS multi-hop traversal in memory store."""
        results: list[dict[str, Any]] = []
        visited_nodes: set[str] = set()
        queue: deque[tuple[str, int]] = deque()

        def _norm(text: str) -> str:
            import re
            return re.sub(r"[^a-zA-Z0-9]+", "", text.lower())

        # Seed the queue with matching entities
        for ent in entities:
            norm_ent = _norm(ent)
            if not norm_ent:
                continue
            for node_key, node_data in self._memory_nodes.items():
                if node_data["tenant_id"] == tenant_id:
                    name_lower = node_data["name"].lower()
                    norm_node = _norm(name_lower)
                    if (
                        ent in name_lower
                        or name_lower in ent
                        or (len(norm_ent) > 2 and (norm_ent in norm_node or norm_node in norm_ent))
                    ):
                        if node_data["name"].lower() not in visited_nodes:
                            queue.append((node_data["name"], 0))
                            visited_nodes.add(node_data["name"].lower())

        seen_edges: set[tuple[str, str, str]] = set()

        while queue and len(results) < limit:
            curr_node, curr_hop = queue.popleft()
            if curr_hop >= hops:
                continue

            # Traverse adjacent edges (both outgoing and incoming)
            for edge in self._memory_edges:
                if edge["tenant_id"] != tenant_id:
                    continue

                matched = False
                neighbor = None

                if edge["source"].lower() == curr_node.lower():
                    matched = True
                    neighbor = edge["target"]
                elif edge["target"].lower() == curr_node.lower():
                    matched = True
                    neighbor = edge["source"]

                if matched and neighbor:
                    edge_key = (edge["source"].lower(), edge["predicate"], edge["target"].lower())
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        results.append(
                            {
                                "source": edge["source"],
                                "predicate": edge["predicate"],
                                "target": edge["target"],
                                "doc_id": edge.get("doc_id", ""),
                                "chunk_id": edge.get("chunk_id", ""),
                                "confidence": edge.get("confidence", 0.9),
                            }
                        )
                    if neighbor.lower() not in visited_nodes:
                        visited_nodes.add(neighbor.lower())
                        queue.append((neighbor, curr_hop + 1))

        return results[:limit]

    def get_graph_stats(self, tenant_id: str) -> dict[str, Any]:
        """Calculates graph metrics, entity type distributions, and connectivity."""
        nodes = [v for v in self._memory_nodes.values() if v["tenant_id"] == tenant_id]
        edges = [e for e in self._memory_edges if e["tenant_id"] == tenant_id]

        type_counts: dict[str, int] = {}
        for n in nodes:
            t = n.get("type", "CONCEPT")
            type_counts[t] = type_counts.get(t, 0) + 1

        degrees: dict[str, int] = {}
        for e in edges:
            src = e["source"]
            tgt = e["target"]
            degrees[src] = degrees.get(src, 0) + 1
            degrees[tgt] = degrees.get(tgt, 0) + 1

        sorted_connected = sorted(
            [{"name": k, "degree": v} for k, v in degrees.items()],
            key=lambda x: x["degree"],
            reverse=True,
        )

        n_count = len(nodes)
        density = (2.0 * len(edges)) / (n_count * (n_count - 1)) if n_count > 1 else 0.0

        return {
            "tenant_id": tenant_id,
            "total_nodes": n_count,
            "total_relationships": len(edges),
            "type_counts": type_counts,
            "top_connected": sorted_connected[:6],
            "density": round(density, 4),
        }

    def get_entities(
        self,
        tenant_id: str,
        limit: int = 50,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Returns distinct entities belonging to tenant with degrees and types."""
        nodes = [v for v in self._memory_nodes.values() if v["tenant_id"] == tenant_id]
        edges = [e for e in self._memory_edges if e["tenant_id"] == tenant_id]

        degrees: dict[str, int] = {}
        for e in edges:
            degrees[e["source"]] = degrees.get(e["source"], 0) + 1
            degrees[e["target"]] = degrees.get(e["target"], 0) + 1

        results = []
        for n in nodes:
            t = n.get("type", "CONCEPT")
            if entity_type and t.upper() != entity_type.upper():
                continue
            results.append(
                {
                    "name": n["name"],
                    "type": t,
                    "degree": degrees.get(n["name"], 0),
                }
            )

        results.sort(key=lambda x: x["degree"], reverse=True)
        return results[:limit]

    def get_subgraph(
        self,
        entity: str | None,
        tenant_id: str,
        depth: int = 2,
        limit: int = 40,
    ) -> dict[str, Any]:
        """Extracts node-link neighborhood structure formatted for visualization."""
        if entity:
            edges = self.search_subgraph([entity], tenant_id, max_hops=depth, limit=limit)
        else:
            edges = [e for e in self._memory_edges if e["tenant_id"] == tenant_id][:limit]

        # Gather node references
        node_names = set()
        for e in edges:
            node_names.add(e["source"])
            node_names.add(e["target"])

        nodes_data = []
        for name in node_names:
            key = f"{tenant_id}::{name.lower()}"
            node_info = self._memory_nodes.get(key, {})
            nodes_data.append(
                {
                    "id": name,
                    "label": name,
                    "type": node_info.get("type", "CONCEPT"),
                }
            )

        links_data = [
            {
                "source": e["source"],
                "target": e["target"],
                "label": e["predicate"],
                "confidence": e.get("confidence", 0.9),
            }
            for e in edges
        ]

        return {
            "tenant_id": tenant_id,
            "seed_entity": entity,
            "total_nodes": len(nodes_data),
            "total_links": len(links_data),
            "nodes": nodes_data,
            "links": links_data,
        }

    def clear_tenant(self, tenant_id: str) -> None:
        """Deletes all graph nodes and edges belonging to tenant_id."""
        if self.driver:
            try:
                cypher = """
                MATCH (n:Entity {tenant_id: $tenant_id})
                DETACH DELETE n
                """
                with self.driver.session() as session:
                    session.run(cypher, tenant_id=tenant_id)
            except Exception as e:
                logger.error(f"Failed to clear tenant from Neo4j ({e})")

        # Clear from memory
        keys_to_del = [k for k, v in self._memory_nodes.items() if v["tenant_id"] == tenant_id]
        for k in keys_to_del:
            del self._memory_nodes[k]
        self._memory_edges = [e for e in self._memory_edges if e["tenant_id"] != tenant_id]


# Global singleton instance
_global_graph_store: Neo4jGraphStore | None = None


def get_graph_store() -> Neo4jGraphStore:
    """Returns singleton Neo4jGraphStore instance."""
    global _global_graph_store
    if _global_graph_store is None:
        _global_graph_store = Neo4jGraphStore()
    return _global_graph_store
