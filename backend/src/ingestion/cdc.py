"""Change Data Capture (CDC) engine for tracking document checksums and versioning."""

import hashlib

from pydantic import BaseModel


class DocumentVersionRecord(BaseModel):
    document_id: str
    checksum: str
    version: int = 1
    tenant_id: str = "default_tenant"
    status: str = "active"


class ChangeDataCaptureEngine:
    """In-memory & DB-backed CDC manager preventing redundant processing of unchanged documents."""

    def __init__(self) -> None:
        # Cache of document_id -> DocumentVersionRecord
        self._registry: dict[str, DocumentVersionRecord] = {}

    @staticmethod
    def compute_checksum(file_bytes: bytes) -> str:
        return hashlib.md5(file_bytes).hexdigest()

    def inspect_change(
        self, document_id: str, new_checksum: str, tenant_id: str = "default_tenant"
    ) -> str:
        """Determines change type: 'UNCHANGED', 'NEW', or 'MODIFIED'."""
        record = self._registry.get(document_id)
        if not record:
            return "NEW"
        if record.checksum == new_checksum and record.tenant_id == tenant_id:
            return "UNCHANGED"
        return "MODIFIED"

    def record_ingestion(
        self, document_id: str, checksum: str, tenant_id: str = "default_tenant"
    ) -> int:
        """Records or updates document ingestion version."""
        record = self._registry.get(document_id)
        new_version = (record.version + 1) if record else 1
        self._registry[document_id] = DocumentVersionRecord(
            document_id=document_id,
            checksum=checksum,
            version=new_version,
            tenant_id=tenant_id,
            status="active",
        )
        return new_version

    def invalidate(self, document_id: str) -> None:
        """Invalidates a document version record."""
        if document_id in self._registry:
            self._registry[document_id].status = "invalidated"
