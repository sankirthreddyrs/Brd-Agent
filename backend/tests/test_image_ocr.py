"""Unit tests for Image Ingestion and Multimodal Vision OCR."""

import uuid
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app import config
from app.api.deps import get_llm_client, get_repository
from app.core.document_parser import (
    MAX_FILE_SIZE_BYTES,
    DocumentParser,
    ParsedChunk,
    ParsedDocument,
    parse_image,
)
from tests.test_api_persistence import InMemoryProjectRepository
from app.llm.llm_client import LLMClient
from app.main import app
from app.models.project import Project, ProjectStatus

SAMPLE_WHITEBOARD_TRANSCRIPTION = """# System Architecture Diagram
[Mobile App] -> [API Gateway] -> [Order Service] -> [PostgreSQL DB]
                      |
                      v
             [Notification Service] -> [Push Provider]

## Handwritten Notes
- Requirement: System must process orders within 500ms
- Security: All API requests require JWT Bearer authentication
- Constraint: Max 10,000 concurrent sessions
"""


def _create_sample_png_bytes(extra: bytes = b"mock png image content") -> bytes:
    """Generate minimal valid PNG magic signature bytes."""
    return b"\x89PNG\r\n\x1a\n" + extra


def _create_sample_jpeg_bytes(extra: bytes = b"mock jpeg image content") -> bytes:
    """Generate minimal valid JPEG magic signature bytes."""
    return b"\xff\xd8\xff\xe0\x00\x10JFIF" + extra


def _create_sample_webp_bytes(extra: bytes = b"mock webp image content") -> bytes:
    """Generate minimal valid WEBP magic signature bytes."""
    return b"RIFF\x24\x00\x00\x00WEBPVP8 " + extra


def test_parse_image_png_success():
    """Verify PNG image parsing uses transcribe_image and creates valid chunks with UUIDs and metadata."""
    png_bytes = _create_sample_png_bytes()

    mock_llm = MagicMock()
    mock_llm.transcribe_image.return_value = SAMPLE_WHITEBOARD_TRANSCRIPTION

    parser = DocumentParser()
    parsed = parser.parse_image("architecture_whiteboard.png", png_bytes, mock_llm)

    assert isinstance(parsed, ParsedDocument)
    assert parsed.filename == "architecture_whiteboard.png"
    assert parsed.file_type == "image"
    assert parsed.total_pages == 1
    assert "System Architecture Diagram" in parsed.raw_text

    mock_llm.transcribe_image.assert_called_once_with(png_bytes, "image/png")

    assert len(parsed.chunks) >= 1
    for idx, chunk in enumerate(parsed.chunks):
        assert isinstance(chunk, ParsedChunk)
        assert chunk.chunk_index == idx
        assert chunk.page_number == 1
        # Validate UUID
        parsed_uuid = uuid.UUID(chunk.id)
        assert str(parsed_uuid) == chunk.id

        assert chunk.metadata["file_type"] == "image"
        assert chunk.metadata["mime_type"] == "image/png"
        assert chunk.metadata["page_number"] == 1
        assert chunk.metadata["chunk_label"].startswith("CHUNK-")
        assert chunk.metadata["chunk_label"].endswith(f"-{idx}")
        assert chunk.metadata["character_count"] == len(chunk.content)
        assert chunk.metadata["word_count"] > 0


def test_parse_image_jpeg_and_webp_mime_detection():
    """Verify JPEG and WEBP image formats correctly detect mime types and pass them to LLM."""
    jpeg_bytes = _create_sample_jpeg_bytes()
    webp_bytes = _create_sample_webp_bytes()

    mock_llm = MagicMock()
    mock_llm.transcribe_image.return_value = "Transcribed diagram notes: Actor -> System"

    # Test JPEG
    parsed_jpeg = parse_image("diagram.jpg", jpeg_bytes, mock_llm)
    assert parsed_jpeg.file_type == "image"
    mock_llm.transcribe_image.assert_called_with(jpeg_bytes, "image/jpeg")

    # Test WEBP
    parsed_webp = parse_image("flowchart.webp", webp_bytes, mock_llm)
    assert parsed_webp.file_type == "image"
    mock_llm.transcribe_image.assert_called_with(webp_bytes, "image/webp")


def test_parse_image_invalid_signatures():
    """Verify spoofed image files with invalid headers are rejected with descriptive errors."""
    parser = DocumentParser()
    mock_llm = MagicMock()

    # Fake PNG
    with pytest.raises(ValueError) as exc_png:
        parser.parse_image("fake.png", b"NOT_A_PNG", mock_llm)
    assert "Invalid PNG image signature" in str(exc_png.value)

    # Fake JPEG
    with pytest.raises(ValueError) as exc_jpg:
        parser.parse_image("fake.jpeg", b"NOT_A_JPEG", mock_llm)
    assert "Invalid JPEG image signature" in str(exc_jpg.value)

    # Fake WEBP
    with pytest.raises(ValueError) as exc_webp:
        parser.parse_image("fake.webp", b"NOT_A_WEBP_HEADER", mock_llm)
    assert "Invalid WEBP image signature" in str(exc_webp.value)


def test_parse_image_size_limit():
    """Verify image files exceeding 10MB are rejected."""
    parser = DocumentParser()
    mock_llm = MagicMock()

    oversized = b"\x89PNG\r\n\x1a\n" + (b"0" * (MAX_FILE_SIZE_BYTES + 10))
    with pytest.raises(ValueError) as exc_size:
        parser.parse_image("huge.png", oversized, mock_llm)
    assert "exceeds the strict 10MB limit" in str(exc_size.value)


def test_llm_client_transcribe_image_payload():
    """Verify LLMClient.transcribe_image formats base64 data URI and calls Groq vision model."""
    client = LLMClient(api_key="mock_groq_key")
    client.client = MagicMock()

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="## Architecture Notes\n[User] -> [System]"))
    ]
    client.client.chat.completions.create.return_value = mock_response

    sample_bytes = b"\x89PNG\r\n\x1a\nimage_data_here"
    transcription = client.transcribe_image(sample_bytes, "image/png")

    assert "## Architecture Notes" in transcription
    client.client.chat.completions.create.assert_called_once()
    call_kwargs = client.client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == config.GROQ_VISION_MODEL
    messages = call_kwargs["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    user_content = messages[0]["content"]
    assert isinstance(user_content, list)
    text_part = next(part for part in user_content if part["type"] == "text")
    assert "technical business analyst" in text_part["text"]
    image_part = next(part for part in user_content if part["type"] == "image_url")
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")


def test_upload_image_source_route():
    """Verify POST /projects/{project_id}/sources processes uploaded image and persists chunks."""
    repo = InMemoryProjectRepository()
    mock_llm = MagicMock()
    mock_llm.transcribe_image.return_value = SAMPLE_WHITEBOARD_TRANSCRIPTION

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_llm_client] = lambda: mock_llm

    client = TestClient(app)
    try:
        # Create a draft project
        proj_resp = client.post(
            "/projects",
            json={"title": "Vision Project", "idea": "Testing whiteboard upload"},
        )
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()["project"]["id"]

        png_bytes = _create_sample_png_bytes()
        files = {"file": ("whiteboard.png", png_bytes, "image/png")}
        resp = client.post(f"/projects/{project_id}/sources", files=files)

        assert resp.status_code == 201
        data = resp.json()
        assert data["file_type"] == "image"
        assert data["filename"] == "whiteboard.png"
        assert data["chunk_count"] >= 1

        # Check repository persistence
        chunks = repo.get_source_chunks_by_document(data["id"])
        assert len(chunks) == data["chunk_count"]
        for ch in chunks:
            assert ch.document_id == data["id"]
            assert ch.project_id == project_id
            assert ch.page_number == 1
            assert ch.chunk_label.startswith("CHUNK-")
            # Verify valid UUID
            uuid.UUID(ch.id)
    finally:
        app.dependency_overrides.clear()
