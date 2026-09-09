"""RAG Strategy Router returning BaseRAGStrategy instance by name."""

import logging

from src.rag.base import BaseRAGStrategy
from src.rag.basic.strategy import BasicRAGStrategy
from src.rag.hybrid.strategy import HybridRAGStrategy
from src.rag.mmr.strategy import MMRRAGStrategy
from src.rag.reranked.strategy import RerankedRAGStrategy

logger = logging.getLogger(__name__)

# Singletons cache
_strategies: dict[str, BaseRAGStrategy] = {}


def get_rag_strategy(strategy_name: str = "AUTO") -> BaseRAGStrategy:
    """Factory router matching strategy_name to BaseRAGStrategy implementation."""
    s_clean = (strategy_name or "AUTO").strip()
    s_upper = s_clean.upper()

    if s_clean not in _strategies:
        logger.info(f"Initializing RAG Strategy '{s_clean}'...")
        if s_upper == "HYBRID":
            from src.rag.hybrid.strategy import HybridRAGStrategy

            _strategies[s_clean] = HybridRAGStrategy()
        elif s_upper == "MMR":
            from src.rag.mmr.strategy import MMRRAGStrategy

            _strategies[s_clean] = MMRRAGStrategy()
        elif s_upper in ("RERANKED", "RERANK"):
            from src.rag.reranked.strategy import RerankedRAGStrategy

            _strategies[s_clean] = RerankedRAGStrategy()
        elif s_upper in ("PARENT-CHILD", "PARENT_CHILD", "PARENTCHILD"):
            from src.rag.parent_child.strategy import ParentChildRAGStrategy

            _strategies[s_clean] = ParentChildRAGStrategy()
        elif s_upper in ("MULTI-QUERY", "MULTI_QUERY", "MULTIQUERY"):
            from src.rag.multi_query.strategy import MultiQueryRAGStrategy

            _strategies[s_clean] = MultiQueryRAGStrategy()
        elif s_upper == "HYDE":
            from src.rag.hyde.strategy import HyDERAGStrategy

            _strategies[s_clean] = HyDERAGStrategy()
        elif s_upper in ("ADAPTIVE", "AUTO"):
            from src.rag.adaptive.strategy import AdaptiveRAGStrategy

            _strategies[s_clean] = AdaptiveRAGStrategy()
        elif s_upper in ("CORRECTIVE", "CRAG"):
            from src.rag.corrective.strategy import CorrectiveRAGStrategy

            _strategies[s_clean] = CorrectiveRAGStrategy()
        elif s_upper in ("SELF-RAG", "SELFRAG", "SELF_RAG"):
            from src.rag.self_rag.strategy import SelfRAGStrategy

            _strategies[s_clean] = SelfRAGStrategy()
        elif s_upper in ("REACT", "REACT-RAG"):
            from src.rag.react.strategy import ReActRAGStrategy

            _strategies[s_clean] = ReActRAGStrategy()
        elif s_upper in ("GRAPHRAG", "GRAPH-RAG", "GRAPH_RAG", "GRAPH"):
            from src.rag.graph_rag.strategy import GraphRAGStrategy

            _strategies[s_clean] = GraphRAGStrategy()
        else:
            from src.rag.basic.strategy import BasicRAGStrategy

            _strategies[s_clean] = BasicRAGStrategy()

    return _strategies[s_clean]
