"""Unit and mock tests for Source Documents and Source Chunks persistence in ProjectRepository."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest

from app.db.repository import ProjectRepository
from app.models.document import (
    SourceChunk,
    SourceDocument,
    SourceDocumentStatus,
)


def _mock_query_result(data: list[dict]):
    """Helper returning a mock query result object with .data."""
    res = MagicMock()
    res.data = data
    return res


def test_save_and_get_source_document():
    """Verify inserting/upserting and retrieving a SourceDocument using ProjectRepository."""
    mock_client = MagicMock()
    repo = ProjectRepository(mock_client)

    doc_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())
    doc = SourceDocument(
        id=doc_id,
        project_id=proj_id,
        filename="system_architecture.pdf",
        file_type="pdf",
        status=SourceDocumentStatus.UPLOADED,
        storage_path="documents/system_architecture.pdf",
        error_message=None,
    )

    row_data = {
        "id": doc_id,
        "project_id": proj_id,
        "filename": "system_architecture.pdf",
        "file_type": "pdf",
        "status": "UPLOADED",
        "storage_path": "documents/system_architecture.pdf",
        "error_message": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Mock upsert execute
    mock_client.table().upsert().execute.return_value = _mock_query_result([row_data])

    saved_doc = repo.save_source_document(doc)
    assert saved_doc.id == doc_id
    assert saved_doc.project_id == proj_id
    assert saved_doc.filename == "system_architecture.pdf"
    assert saved_doc.file_type == "pdf"
    assert saved_doc.status == SourceDocumentStatus.UPLOADED

    # Mock get by ID
    mock_client.table().select().eq().execute.return_value = _mock_query_result([row_data])
    fetched_doc = repo.get_source_document_by_id(doc_id)
    assert fetched_doc is not None
    assert fetched_doc.id == doc_id
    assert fetched_doc.filename == "system_architecture.pdf"

    # Mock get non-existent ID
    mock_client.table().select().eq().execute.return_value = _mock_query_result([])
    assert repo.get_source_document_by_id("non-existent-id") is None


def test_save_and_get_source_chunks():
    """Verify batch-inserting and retrieving SourceChunks by document and project."""
    mock_client = MagicMock()
    repo = ProjectRepository(mock_client)

    doc_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())

    chunks = [
        SourceChunk(
            id=f"CHUNK-{doc_id[:8]}-0",
            document_id=doc_id,
            project_id=proj_id,
            text="First paragraph of requirements specifications.",
            page_number=1,
            heading="Introduction",
            chunk_index=0,
        ),
        SourceChunk(
            id=f"CHUNK-{doc_id[:8]}-1",
            document_id=doc_id,
            project_id=proj_id,
            text="Second paragraph discussing authentication.",
            page_number=1,
            heading="Security",
            chunk_index=1,
        ),
    ]

    chunk_rows = [
        {
            "id": f"CHUNK-{doc_id[:8]}-0",
            "document_id": doc_id,
            "project_id": proj_id,
            "text": "First paragraph of requirements specifications.",
            "page_number": 1,
            "heading": "Introduction",
            "chunk_index": 0,
        },
        {
            "id": f"CHUNK-{doc_id[:8]}-1",
            "document_id": doc_id,
            "project_id": proj_id,
            "text": "Second paragraph discussing authentication.",
            "page_number": 1,
            "heading": "Security",
            "chunk_index": 1,
        },
    ]

    # Mock batch upsert
    mock_client.table().upsert().execute.return_value = _mock_query_result(chunk_rows)
    saved_chunks = repo.save_source_chunks(chunks)

    assert len(saved_chunks) == 2
    assert saved_chunks[0].id == f"CHUNK-{doc_id[:8]}-0"
    assert saved_chunks[0].chunk_index == 0
    assert saved_chunks[1].chunk_index == 1

    # Mock get chunks by document
    mock_client.table().select().eq().order().execute.return_value = _mock_query_result(chunk_rows)
    doc_chunks = repo.get_source_chunks_by_document(doc_id)
    assert len(doc_chunks) == 2
    assert doc_chunks[0].heading == "Introduction"
    assert doc_chunks[1].heading == "Security"

    # Mock get chunks by project
    mock_client.table().select().eq().order().order().execute.return_value = _mock_query_result(chunk_rows)
    proj_chunks = repo.get_source_chunks_by_project(proj_id)
    assert len(proj_chunks) == 2
    assert proj_chunks[0].text == "First paragraph of requirements specifications."


def test_get_source_documents_by_project():
    """Verify retrieving all source documents belonging to a project."""
    mock_client = MagicMock()
    repo = ProjectRepository(mock_client)

    proj_id = str(uuid.uuid4())
    doc_rows = [
        {
            "id": str(uuid.uuid4()),
            "project_id": proj_id,
            "filename": "doc1.pdf",
            "file_type": "pdf",
            "status": "READY",
            "storage_path": "doc1.pdf",
            "error_message": None,
            "created_at": "2026-10-15T10:00:00Z",
        },
        {
            "id": str(uuid.uuid4()),
            "project_id": proj_id,
            "filename": "doc2.docx",
            "file_type": "docx",
            "status": "READY",
            "storage_path": "doc2.docx",
            "error_message": None,
            "created_at": "2026-10-15T11:00:00Z",
        },
    ]

    mock_client.table().select().eq().order().execute.return_value = _mock_query_result(doc_rows)
    docs = repo.get_source_documents_by_project(proj_id)

    assert len(docs) == 2
    assert docs[0].filename == "doc1.pdf"
    assert docs[0].status == SourceDocumentStatus.READY
    assert docs[1].filename == "doc2.docx"


def test_save_source_chunks_empty():
    """Verify empty list does not make unnecessary DB calls."""
    mock_client = MagicMock()
    repo = ProjectRepository(mock_client)

    result = repo.save_source_chunks([])
    assert result == []
    mock_client.table.assert_not_called()
