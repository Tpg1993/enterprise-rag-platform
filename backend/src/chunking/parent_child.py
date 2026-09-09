"""Parent-Child hierarchical chunker generating small child chunks linked to large parent chunks."""

import uuid

from src.chunking.base import BaseChunker, Chunk


class ParentChildChunker(BaseChunker):
    """Generates large parent chunks (e.g. 1024 chars) and small child chunks (e.g. 256 chars)."""

    def __init__(self, parent_size: int = 1024, child_size: int = 256, child_overlap: int = 30):
        self.parent_size = parent_size
        self.child_size = child_size
        self.child_overlap = child_overlap

    def chunk(self, text: str, document_id: str, tenant_id: str = "default_tenant") -> list[Chunk]:
        if not text:
            return []

        all_chunks = []
        parent_idx = 0
        child_global_idx = 0

        # Step 1: Create parent chunks
        for start in range(0, len(text), self.parent_size):
            end = min(start + self.parent_size, len(text))
            parent_text = text[start:end].strip()
            if not parent_text:
                continue

            parent_id = f"{document_id}_parent_{parent_idx}_{uuid.uuid4().hex[:6]}"
            parent_chunk = Chunk(
                chunk_id=parent_id,
                document_id=document_id,
                tenant_id=tenant_id,
                parent_id=None,
                chunk_index=parent_idx,
                content=parent_text,
                token_count=len(parent_text.split()),
                metadata={"is_parent": True, "chunk_strategy": "parent_child"},
            )
            all_chunks.append(parent_chunk)

            # Step 2: Create child chunks inside parent
            c_start = 0
            p_len = len(parent_text)
            c_local_idx = 0

            while c_start < p_len:
                c_end = min(c_start + self.child_size, p_len)
                child_text = parent_text[c_start:c_end].strip()

                if child_text:
                    child_id = f"{parent_id}_child_{c_local_idx}_{uuid.uuid4().hex[:4]}"
                    all_chunks.append(
                        Chunk(
                            chunk_id=child_id,
                            document_id=document_id,
                            tenant_id=tenant_id,
                            parent_id=parent_id,
                            chunk_index=child_global_idx,
                            content=child_text,
                            token_count=len(child_text.split()),
                            metadata={
                                "is_parent": False,
                                "parent_id": parent_id,
                                "parent_content": parent_text,
                                "chunk_strategy": "parent_child",
                            },
                        )
                    )
                    c_local_idx += 1
                    child_global_idx += 1

                step = max(1, self.child_size - self.child_overlap)
                c_start += step

            parent_idx += 1

        return all_chunks
