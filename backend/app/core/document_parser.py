"""Document ingestion, parsing, and chunking service for BRD Agent.

Supports PDF, DOCX, and TXT/Markdown formats. Enforces a strict 10MB size limit,
validates file signatures, extracts text while tracking page numbers, and divides
documents into overlapping chunks with stable identifiers and metadata.
"""

import hashlib
import io
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

import docx
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from pydantic import BaseModel, Field
import pypdf

logger = logging.getLogger(__name__)

# Strict 10MB file size limitation
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10,485,760 bytes

# Supported file extensions
SUPPORTED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
SUPPORTED_EXTENSIONS = {"pdf", "docx", "txt", "text", "md"} | SUPPORTED_IMAGE_EXTENSIONS

# Chunking defaults: ~500 to 800 words (~1500 to 2500 characters) with 15% overlap
DEFAULT_TARGET_WORDS: int = 600
DEFAULT_OVERLAP_WORDS: int = 90  # 15% of 600
MIN_CHUNK_WORDS: int = 30


def get_image_mime_type(filename: str) -> str:
    """Return image MIME type for supported image formats."""
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix == "png":
        return "image/png"
    elif suffix in ("jpg", "jpeg"):
        return "image/jpeg"
    elif suffix == "webp":
        return "image/webp"
    raise ValueError(f"Unsupported image format '.{suffix}'. Supported formats: png, jpg, jpeg, webp.")


class ParsedChunk(BaseModel):
    """Chunk of parsed document content with positioning and traceability metadata."""

    id: Optional[str] = Field(default=None, description="UUID string identifier")
    chunk_index: int = Field(..., ge=0, description="0-indexed position of chunk in document")
    content: str = Field(..., description="Textual content slice of this chunk")
    page_number: Optional[int] = Field(
        default=None,
        description="1-indexed source page number for paginated formats (e.g. PDF)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Positioning, word/char counts, chunk ID, and source document metadata",
    )


class ParsedDocument(BaseModel):
    """Complete parsed document containing full text, chunks, and metadata."""

    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="Normalized document type: 'pdf', 'docx', 'txt', or 'image'")
    raw_text: str = Field(..., description="Complete extracted textual content")
    chunks: List[ParsedChunk] = Field(default_factory=list, description="Extracted chunks list")
    total_pages: Optional[int] = Field(
        default=None,
        description="Total page count if the document is paginated (e.g. PDF)",
    )


def _clean_text(text: str) -> str:
    """Normalize whitespace and line endings while preserving paragraph breaks."""
    if not text:
        return ""
    # Normalize Windows and Mac carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Clean out non-breaking spaces and excessive inline horizontal tabs/spaces
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3 or more consecutive newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text_slice(
    text: str,
    target_words: int = DEFAULT_TARGET_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> List[str]:
    """Divide a continuous string into chunks of ~target_words with overlap without splitting words."""
    words = text.split()
    if not words:
        return []
    if len(words) <= target_words:
        return [" ".join(words)]

    chunks: List[str] = []
    step = max(1, target_words - overlap_words)
    start = 0
    total_words = len(words)

    while start < total_words:
        end = min(start + target_words, total_words)
        chunk_words = words[start:end]
        if not chunk_words:
            break

        # If a small trailing slice remains and previous chunks exist, merge if small
        if len(chunk_words) < MIN_CHUNK_WORDS and chunks:
            if end == total_words:
                break

        chunks.append(" ".join(chunk_words))
        if end >= total_words:
            break
        start += step

    return chunks


class DocumentParser:
    """Service for validating, parsing, and chunking uploaded documents."""

    def __init__(
        self,
        max_size_bytes: int = MAX_FILE_SIZE_BYTES,
        target_chunk_words: int = DEFAULT_TARGET_WORDS,
        overlap_words: int = DEFAULT_OVERLAP_WORDS,
    ) -> None:
        self.max_size_bytes = max_size_bytes
        self.target_chunk_words = target_chunk_words
        self.overlap_words = overlap_words

    def validate_file_size(self, content_bytes: bytes) -> None:
        """Enforce strict file size limit."""
        size = len(content_bytes)
        if size == 0:
            raise ValueError("File content is completely empty (0 bytes).")
        if size > self.max_size_bytes:
            raise ValueError(
                f"File size ({size:,} bytes) exceeds the strict 10MB limit "
                f"({self.max_size_bytes:,} bytes)."
            )

    def detect_and_validate_format(self, filename: str, content_bytes: bytes) -> str:
        """Detect file format from extension and validate file magic signatures."""
        suffix = Path(filename).suffix.lower().lstrip(".")
        if not suffix:
            raise ValueError(
                f"File '{filename}' has no extension. Supported formats are: pdf, docx, txt, png, jpg, jpeg, webp."
            )

        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '.{suffix}' for '{filename}'. "
                f"Supported formats are: pdf, docx, txt, png, jpg, jpeg, webp."
            )

        # Normalize format name
        if suffix in ("txt", "text", "md"):
            norm_type = "txt"
        elif suffix in SUPPORTED_IMAGE_EXTENSIONS:
            norm_type = "image"
        else:
            norm_type = suffix

        # Signature validation
        if norm_type == "pdf":
            if not content_bytes.startswith(b"%PDF"):
                raise ValueError(
                    f"Invalid PDF file signature for '{filename}'. "
                    f"File does not start with standard '%PDF' magic header."
                )
        elif norm_type == "docx":
            # DOCX files are standard ZIP archives starting with PK\x03\x04
            if not content_bytes.startswith(b"PK\x03\x04"):
                raise ValueError(
                    f"Invalid DOCX file signature for '{filename}'. "
                    f"File is not a valid Office Open XML ZIP package."
                )
        elif norm_type == "image":
            if suffix == "png":
                if not content_bytes.startswith(b"\x89PNG"):
                    raise ValueError(f"Invalid PNG image signature for '{filename}'.")
            elif suffix in ("jpg", "jpeg"):
                if not content_bytes.startswith(b"\xff\xd8\xff"):
                    raise ValueError(f"Invalid JPEG image signature for '{filename}'.")
            elif suffix == "webp":
                if not (content_bytes.startswith(b"RIFF") and b"WEBP" in content_bytes[8:12]):
                    raise ValueError(f"Invalid WEBP image signature for '{filename}'.")

        return norm_type

    def _parse_pdf(self, filename: str, content_bytes: bytes) -> Tuple[str, List[Tuple[str, int]], int]:
        """Extract text page-by-page using pypdf.

        Returns:
            Tuple of (full_raw_text, list_of_(page_text, page_number), total_pages)
        """
        try:
            stream = io.BytesIO(content_bytes)
            reader = pypdf.PdfReader(stream)
            total_pages = len(reader.pages)
        except Exception as err:
            logger.error("Failed to parse corrupt PDF '%s': %s", filename, err)
            raise ValueError(f"Corrupt or unreadable PDF file '{filename}': {err}") from err

        page_entries: List[Tuple[str, int]] = []
        raw_parts: List[str] = []

        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            try:
                extracted = page.extract_text() or ""
            except Exception as page_err:
                logger.warning("Error extracting text on page %d of '%s': %s", page_num, filename, page_err)
                extracted = ""

            cleaned = _clean_text(extracted)
            if cleaned:
                page_entries.append((cleaned, page_num))
                raw_parts.append(cleaned)

        raw_text = "\n\n".join(raw_parts)
        return raw_text, page_entries, total_pages

    def _parse_docx(self, filename: str, content_bytes: bytes) -> str:
        """Extract paragraphs and tables from DOCX using python-docx."""
        try:
            stream = io.BytesIO(content_bytes)
            doc = docx.Document(stream)
        except Exception as err:
            logger.error("Failed to parse corrupt DOCX '%s': %s", filename, err)
            raise ValueError(f"Corrupt or unreadable DOCX file '{filename}': {err}") from err

        elements: List[str] = []

        # Iterate through document body children in order to preserve paragraph and table layout
        for child in doc.element.body:
            if isinstance(child, CT_P):
                p = Paragraph(child, doc)
                text = _clean_text(p.text)
                if text:
                    elements.append(text)
            elif isinstance(child, CT_Tbl):
                t = Table(child, doc)
                table_lines: List[str] = []
                for row in t.rows:
                    cells = [_clean_text(cell.text) for cell in row.cells]
                    if any(cells):
                        table_lines.append("| " + " | ".join(cells) + " |")
                if table_lines:
                    elements.append("\n".join(table_lines))

        # Fallback if body iteration produced nothing but paragraphs exist
        if not elements and doc.paragraphs:
            for p in doc.paragraphs:
                cleaned = _clean_text(p.text)
                if cleaned:
                    elements.append(cleaned)

        return "\n\n".join(elements)

    def _parse_txt(self, filename: str, content_bytes: bytes) -> str:
        """Decode plain text file using UTF-8 with fallback to latin-1."""
        try:
            decoded = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                decoded = content_bytes.decode("latin-1")
            except Exception as err:
                raise ValueError(f"Failed to decode text file '{filename}': {err}") from err
        return _clean_text(decoded)

    def parse_file(
        self,
        filename: str,
        content_bytes: bytes,
        llm_client: Optional[Any] = None,
    ) -> ParsedDocument:
        """Validate, parse, and chunk an uploaded document file.

        Args:
            filename: Original name of the uploaded file.
            content_bytes: Raw binary bytes of the file.
            llm_client: Optional LLMClient required when parsing image files.

        Returns:
            ParsedDocument containing raw text and chunked representations.

        Raises:
            ValueError: If file size exceeds 10MB, format is unsupported,
                        signature is invalid, or file is corrupt.
        """
        # 1. Enforce size constraint (<= 10MB)
        self.validate_file_size(content_bytes)

        # 2. Detect format & validate signature
        file_type = self.detect_and_validate_format(filename, content_bytes)

        if file_type == "image":
            if llm_client is None:
                raise ValueError(
                    f"Cannot parse image '{filename}' without an LLMClient for vision transcription."
                )
            return self.parse_image(filename, content_bytes, llm_client)

        # Compute stable document hash prefix for chunk IDs
        doc_hash = hashlib.sha256(content_bytes).hexdigest()[:8]

        total_pages: Optional[int] = None
        chunks: List[ParsedChunk] = []
        raw_text: str = ""

        # 3. Extract text according to format
        if file_type == "pdf":
            raw_text, page_entries, total_pages = self._parse_pdf(filename, content_bytes)
            chunk_idx = 0
            for page_text, page_num in page_entries:
                text_slices = _chunk_text_slice(
                    page_text,
                    target_words=self.target_chunk_words,
                    overlap_words=self.overlap_words,
                )
                for slice_text in text_slices:
                    chunk_uuid = str(uuid.uuid4())
                    chunk_label = f"CHUNK-{doc_hash}-{chunk_idx}"
                    metadata = {
                        "id": chunk_label,
                        "uuid": chunk_uuid,
                        "chunk_label": chunk_label,
                        "chunk_index": chunk_idx,
                        "page_number": page_num,
                        "character_count": len(slice_text),
                        "word_count": len(slice_text.split()),
                        "filename": filename,
                        "file_type": file_type,
                    }
                    chunks.append(
                        ParsedChunk(
                            id=chunk_uuid,
                            chunk_index=chunk_idx,
                            content=slice_text,
                            page_number=page_num,
                            metadata=metadata,
                        )
                    )
                    chunk_idx += 1

        elif file_type == "docx":
            raw_text = self._parse_docx(filename, content_bytes)
            total_pages = None
            text_slices = _chunk_text_slice(
                raw_text,
                target_words=self.target_chunk_words,
                overlap_words=self.overlap_words,
            )
            for chunk_idx, slice_text in enumerate(text_slices):
                chunk_uuid = str(uuid.uuid4())
                chunk_label = f"CHUNK-{doc_hash}-{chunk_idx}"
                metadata = {
                    "id": chunk_label,
                    "uuid": chunk_uuid,
                    "chunk_label": chunk_label,
                    "chunk_index": chunk_idx,
                    "page_number": None,
                    "character_count": len(slice_text),
                    "word_count": len(slice_text.split()),
                    "filename": filename,
                    "file_type": file_type,
                }
                chunks.append(
                    ParsedChunk(
                        id=chunk_uuid,
                        chunk_index=chunk_idx,
                        content=slice_text,
                        page_number=None,
                        metadata=metadata,
                    )
                )

        else:  # txt
            raw_text = self._parse_txt(filename, content_bytes)
            total_pages = None
            text_slices = _chunk_text_slice(
                raw_text,
                target_words=self.target_chunk_words,
                overlap_words=self.overlap_words,
            )
            for chunk_idx, slice_text in enumerate(text_slices):
                chunk_uuid = str(uuid.uuid4())
                chunk_label = f"CHUNK-{doc_hash}-{chunk_idx}"
                metadata = {
                    "id": chunk_label,
                    "uuid": chunk_uuid,
                    "chunk_label": chunk_label,
                    "chunk_index": chunk_idx,
                    "page_number": None,
                    "character_count": len(slice_text),
                    "word_count": len(slice_text.split()),
                    "filename": filename,
                    "file_type": file_type,
                }
                chunks.append(
                    ParsedChunk(
                        id=chunk_uuid,
                        chunk_index=chunk_idx,
                        content=slice_text,
                        page_number=None,
                        metadata=metadata,
                    )
                )

        return ParsedDocument(
            filename=filename,
            file_type=file_type,
            raw_text=raw_text,
            chunks=chunks,
            total_pages=total_pages,
        )

    def parse_image(
        self,
        filename: str,
        content_bytes: bytes,
        llm_client: Any,
    ) -> ParsedDocument:
        """Validate, transcribe, and chunk an image document using multimodal vision OCR.

        Args:
            filename: Original image file name (.png, .jpg, .jpeg, .webp).
            content_bytes: Raw binary bytes of the image file.
            llm_client: LLMClient instance implementing transcribe_image.

        Returns:
            ParsedDocument with file_type='image', total_pages=1, and chunked text.
        """
        self.validate_file_size(content_bytes)
        self.detect_and_validate_format(filename, content_bytes)
        mime_type = get_image_mime_type(filename)

        raw_transcription = llm_client.transcribe_image(content_bytes, mime_type)
        cleaned_text = _clean_text(raw_transcription or "")

        doc_hash = hashlib.sha256(content_bytes).hexdigest()[:8]
        chunks: List[ParsedChunk] = []

        if cleaned_text:
            text_slices = _chunk_text_slice(
                cleaned_text,
                target_words=self.target_chunk_words,
                overlap_words=self.overlap_words,
            )
            for chunk_idx, slice_text in enumerate(text_slices):
                chunk_uuid = str(uuid.uuid4())
                chunk_label = f"CHUNK-{doc_hash}-{chunk_idx}"
                metadata = {
                    "id": chunk_label,
                    "uuid": chunk_uuid,
                    "chunk_label": chunk_label,
                    "chunk_index": chunk_idx,
                    "page_number": 1,
                    "character_count": len(slice_text),
                    "word_count": len(slice_text.split()),
                    "filename": filename,
                    "file_type": "image",
                    "mime_type": mime_type,
                }
                chunks.append(
                    ParsedChunk(
                        id=chunk_uuid,
                        chunk_index=chunk_idx,
                        content=slice_text,
                        page_number=1,
                        metadata=metadata,
                    )
                )

        return ParsedDocument(
            filename=filename,
            file_type="image",
            raw_text=cleaned_text,
            chunks=chunks,
            total_pages=1,
        )


def parse_file(
    filename: str,
    content_bytes: bytes,
    llm_client: Optional[Any] = None,
) -> ParsedDocument:
    """Convenience functional wrapper for DocumentParser.parse_file."""
    parser = DocumentParser()
    return parser.parse_file(filename, content_bytes, llm_client=llm_client)


def parse_image(
    filename: str,
    content_bytes: bytes,
    llm_client: Any,
) -> ParsedDocument:
    """Convenience functional wrapper for DocumentParser.parse_image."""
    parser = DocumentParser()
    return parser.parse_image(filename, content_bytes, llm_client)
