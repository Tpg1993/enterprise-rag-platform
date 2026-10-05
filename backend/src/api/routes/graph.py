import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from src.api.schemas import (
    GraphEntitiesResponse,
    GraphEntityItem,
    GraphLink,
    GraphNode,
    GraphStatsResponse,
    GraphSubgraphResponse,
)
from src.graph.neo4j_store import get_graph_store
from src.storage.history import get_history_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


@router.get("/stats", response_model=GraphStatsResponse)
async def get_knowledge_graph_stats(
    tenant_id: str = Query("default_tenant", description="Tenant ID to query graph stats for"),
) -> GraphStatsResponse:
    """Returns knowledge graph structural metrics, entity types, and graph density."""
    try:
        store = get_graph_store()
        stats = store.get_graph_stats(tenant_id=tenant_id)
        return GraphStatsResponse(
            tenant_id=stats["tenant_id"],
            total_nodes=stats["total_nodes"],
            total_relationships=stats["total_relationships"],
            type_counts=stats.get("type_counts", {}),
            top_connected=stats.get("top_connected", []),
            density=stats.get("density", 0.0),
        )
    except Exception as e:
        logger.error(f"Error fetching graph stats for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch graph stats: {e!s}")


@router.get("/entities", response_model=GraphEntitiesResponse)
async def list_knowledge_graph_entities(
    tenant_id: str = Query("default_tenant", description="Tenant ID"),
    limit: int = Query(50, ge=1, le=500, description="Max entities to return"),
    entity_type: str | None = Query(None, description="Optional entity category filter"),
) -> GraphEntitiesResponse:
    """Returns distinct entities in tenant knowledge graph with connectivity degrees."""
    try:
        store = get_graph_store()
        raw_entities = store.get_entities(tenant_id=tenant_id, limit=limit, entity_type=entity_type)
        entities = [
            GraphEntityItem(
                name=ent["name"],
                type=ent.get("type", "CONCEPT"),
                degree=ent.get("degree", 0),
            )
            for ent in raw_entities
        ]
        return GraphEntitiesResponse(
            tenant_id=tenant_id,
            total_entities=len(entities),
            entities=entities,
        )
    except Exception as e:
        logger.error(f"Error listing entities for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list graph entities: {e!s}")


@router.get("/subgraph", response_model=GraphSubgraphResponse)
async def get_knowledge_graph_subgraph(
    tenant_id: str = Query("default_tenant", description="Tenant ID"),
    entity: str | None = Query(None, description="Focal/seed entity name"),
    depth: int = Query(2, ge=1, le=5, description="Traversal hop depth"),
    limit: int = Query(50, ge=1, le=200, description="Max links to traverse"),
) -> GraphSubgraphResponse:
    """Extracts node-link neighborhood formatted for interactive visualization."""
    try:
        store = get_graph_store()
        subgraph_data = store.get_subgraph(
            entity=entity, tenant_id=tenant_id, depth=depth, limit=limit
        )
        nodes = [
            GraphNode(
                id=n["id"],
                label=n["label"],
                type=n.get("type", "CONCEPT"),
            )
            for n in subgraph_data.get("nodes", [])
        ]
        links = [
            GraphLink(
                source=edge["source"],
                target=edge["target"],
                label=edge["label"],
                confidence=edge.get("confidence", 0.9),
            )
            for edge in subgraph_data.get("links", [])
        ]
        return GraphSubgraphResponse(
            tenant_id=tenant_id,
            seed_entity=entity,
            total_nodes=len(nodes),
            total_links=len(links),
            nodes=nodes,
            links=links,
        )
    except Exception as e:
        logger.error(f"Error fetching subgraph for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch subgraph: {e!s}")


@router.delete("", response_model=dict[str, Any])
async def clear_knowledge_graph(
    tenant_id: str = Query("default_tenant", description="Tenant ID to wipe"),
) -> dict[str, Any]:
    """Clears all knowledge graph entities and relations for specified tenant."""
    try:
        store = get_graph_store()
        store.clear_tenant(tenant_id=tenant_id)

        get_history_store().record_audit_event(
            event_type="GRAPH_CLEAR",
            user_id="analyst",
            tenant_id=tenant_id,
            action="DELETE",
            resource=f"graph:{tenant_id}",
            status="SUCCESS",
            details={"tenant_id": tenant_id},
        )

        return {"status": "cleared", "tenant_id": tenant_id}
    except Exception as e:
        logger.error(f"Error clearing graph for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear knowledge graph: {e!s}")
