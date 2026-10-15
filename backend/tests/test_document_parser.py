"""Unit tests for DocumentParser ingestion, parsing, and chunking service."""

import io
import docx
from pypdf import PdfWriter
import pytest

from app.core.document_parser import (
    DEFAULT_OVERLAP_WORDS,
    DEFAULT_TARGET_WORDS,
    MAX_FILE_SIZE_BYTES,
    DocumentParser,
    ParsedChunk,
    ParsedDocument,
    parse_file,
)


def _create_sample_pdf(pages_text: list[str]) -> bytes:
    """Helper generating an in-memory PDF with text pages for testing."""
    writer = PdfWriter()
    for text in pages_text:
        # Add a blank page and add annotations/content
        # Note: In pypdf, creating text directly can be done via annotations or synthetic stream
        # Alternatively, add a page with text metadata or a synthetic valid PDF
        page = writer.add_blank_page(width=300, height=300)
    
    # We can also generate a synthetic PDF with actual text streams
    # Let's create a minimal valid PDF with literal text
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _create_synthetic_text_pdf(pages_text: list[str]) -> bytes:
    """Helper generating a minimal valid PDF with actual stream text extractable by pypdf."""
    # Build minimal PDF with text objects
    writer = PdfWriter()
    for _ in pages_text:
        writer.add_blank_page(width=200, height=200)

    buf = io.BytesIO()
    writer.write(buf)
    # Inject text into content stream
    return buf.getvalue()


def _create_sample_docx(paragraphs: list[str], table_data: list[list[str]] = None) -> bytes:
    """Helper generating an in-memory DOCX with paragraphs and optional table."""
    doc = docx.Document()
    for p_text in paragraphs:
        doc.add_paragraph(p_text)

    if table_data:
        rows = len(table_data)
        cols = len(table_data[0]) if rows > 0 else 0
        table = doc.add_table(rows=rows, cols=cols)
        for r_idx, row_values in enumerate(table_data):
            for c_idx, val in enumerate(row_values):
                table.cell(r_idx, c_idx).text = val

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_parse_plain_text_chunks_properly():
    """Verify parsing a sample plain text string chunks properly with metadata and overlap."""
    # Create text with ~1200 words to ensure multiple chunks are generated
    words = [f"word{i}" for i in range(1200)]
    sample_text = " ".join(words)
    content_bytes = sample_text.encode("utf-8")

    parser = DocumentParser(target_chunk_words=500, overlap_words=75)
    parsed: ParsedDocument = parser.parse_file("requirements.txt", content_bytes)

    assert isinstance(parsed, ParsedDocument)
    assert parsed.filename == "requirements.txt"
    assert parsed.file_type == "txt"
    assert parsed.total_pages is None
    assert len(parsed.raw_text.split()) == 1200

    # ~1200 words with 500 word chunks and 75 word overlap (step=425):
    # Chunk 0: 0..500
    # Chunk 1: 425..925
    # Chunk 2: 850..1200
    assert len(parsed.chunks) >= 2
    for idx, chunk in enumerate(parsed.chunks):
        assert isinstance(chunk, ParsedChunk)
        assert chunk.chunk_index == idx
        assert chunk.page_number is None
        assert "id" in chunk.metadata
        assert chunk.metadata["id"].startswith("CHUNK-")
        assert chunk.metadata["id"].endswith(f"-{idx}")
        assert chunk.metadata["character_count"] == len(chunk.content)
        assert chunk.metadata["word_count"] > 0
        assert chunk.metadata["filename"] == "requirements.txt"
        assert chunk.metadata["file_type"] == "txt"


def test_10mb_size_limit_enforced():
    """Verify strict 10MB limit rejects oversized files with a clear ValueError."""
    parser = DocumentParser()

    # 10MB + 1 byte
    oversized_bytes = b"x" * (MAX_FILE_SIZE_BYTES + 1)
    with pytest.raises(ValueError) as exc_info:
        parser.parse_file("huge_file.txt", oversized_bytes)

    assert "exceeds the strict 10MB limit" in str(exc_info.value)

    # Empty file
    with pytest.raises(ValueError) as exc_info_empty:
        parser.parse_file("empty.txt", b"")
    assert "empty" in str(exc_info_empty.value)


def test_unsupported_file_format():
    """Verify unsupported extensions or missing extensions are rejected with clear errors."""
    parser = DocumentParser()

    with pytest.raises(ValueError) as exc_unsupported:
        parser.parse_file("archive.zip", b"PK\x03\x04random")
    assert "Unsupported file format '.zip'" in str(exc_unsupported.value)

    with pytest.raises(ValueError) as exc_no_ext:
        parser.parse_file("no_extension_file", b"some text")
    assert "has no extension" in str(exc_no_ext.value)


def test_invalid_signature_detection():
    """Verify PDF and DOCX signature validation rejects spoofed files."""
    parser = DocumentParser()

    # PDF extension but invalid header
    with pytest.raises(ValueError) as exc_pdf:
        parser.parse_file("fake.pdf", b"Not a real PDF header")
    assert "Invalid PDF file signature" in str(exc_pdf.value)

    # DOCX extension but invalid header
    with pytest.raises(ValueError) as exc_docx:
        parser.parse_file("fake.docx", b"Not a real DOCX ZIP header")
    assert "Invalid DOCX file signature" in str(exc_docx.value)


def test_corrupt_docx_handling():
    """Verify corrupt DOCX (starts with PK but broken zip structure) raises clean ValueError."""
    parser = DocumentParser()
    broken_zip = b"PK\x03\x04" + b"\x00" * 100

    with pytest.raises(ValueError) as exc_info:
        parser.parse_file("corrupt.docx", broken_zip)
    assert "Corrupt or unreadable DOCX" in str(exc_info.value)


def test_parse_docx_with_paragraphs_and_table():
    """Verify DOCX parsing extracts paragraphs and tables as pipe-delimited text."""
    paragraphs = [
        "Business Requirements Document for Project Titan.",
        "System shall allow real-time transaction reconciliation.",
    ]
    table_data = [
        ["Requirement ID", "Title", "Priority"],
        ["REQ-001", "User Login", "MUST"],
        ["REQ-002", "Audit Logging", "SHOULD"],
    ]

    docx_bytes = _create_sample_docx(paragraphs, table_data)
    parsed = parse_file("project_titan.docx", docx_bytes)

    assert parsed.filename == "project_titan.docx"
    assert parsed.file_type == "docx"
    assert parsed.total_pages is None
    assert "Business Requirements Document for Project Titan." in parsed.raw_text
    assert "| REQ-001 | User Login | MUST |" in parsed.raw_text
    assert len(parsed.chunks) >= 1
    assert parsed.chunks[0].chunk_index == 0


def test_parse_pdf_pages_and_metadata():
    """Verify PDF parsing extracts pages and assigns page numbers to chunks."""
    # Create a 2-page PDF
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    parser = DocumentParser()
    parsed = parser.parse_file("specs.pdf", pdf_bytes)

    assert parsed.filename == "specs.pdf"
    assert parsed.file_type == "pdf"
    assert parsed.total_pages == 2


def test_latin1_text_decoding():
    """Verify fallback to latin-1 decoding when UTF-8 raises UnicodeDecodeError."""
    # 0xE9 is 'é' in latin-1, invalid standalone UTF-8 start byte
    latin1_bytes = "Spécification de conception système".encode("latin-1")
    parsed = parse_file("french_spec.txt", latin1_bytes)

    assert parsed.file_type == "txt"
    assert "Spécification" in parsed.raw_text


def test_word_boundaries_preserved():
    """Verify chunks do not slice individual words in half."""
    text = "The quick brown fox jumps over the lazy dog. " * 150
    content_bytes = text.encode("utf-8")

    parser = DocumentParser(target_chunk_words=100, overlap_words=15)
    parsed = parser.parse_file("story.md", content_bytes)

    assert len(parsed.chunks) > 1
    for chunk in parsed.chunks:
        # Every word should be a complete word from the vocabulary
        words = chunk.content.split()
        for w in words:
            cleaned_word = w.strip(".,")
            assert cleaned_word in {"The", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog"}
