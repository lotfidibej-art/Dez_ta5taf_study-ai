import io
import logging
import re
import urllib.parse
import uuid
from dataclasses import dataclass
from typing import List, Optional

import fitz  # PyMuPDF
import psycopg
import trafilatura

try:
    import pytesseract
    from PIL import Image
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False
from youtube_transcript_api import YouTubeTranscriptApi

from app.db.migrations import get_db_connection
from app.schemas.contracts import ResourceChunk
from app.services.local_models import LocalMLService

logger = logging.getLogger(__name__)

YOUTUBE_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
)


@dataclass
class ExtractedSegment:
    content: str
    source_name: str
    source_location: str


_OCR_MIN_CHARS = 50  # Pages with fewer chars trigger OCR fallback


def _ocr_page(page: fitz.Page) -> str:
    """Render a PDF page to an image and run Tesseract OCR on it."""
    if not _OCR_AVAILABLE:
        logger.warning("pytesseract/Pillow not installed — OCR fallback unavailable")
        return ""
    try:
        # 200 DPI gives good OCR quality without excessive memory usage
        mat = fitz.Matrix(200 / 72, 200 / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang="fra+eng")
        return text.strip()
    except Exception as exc:
        logger.warning("OCR failed on page: %s", exc)
        return ""


def parse_pdf(file_bytes: bytes, filename: str) -> List[ExtractedSegment]:
    """Extract text page-by-page from a PDF.

    For scanned / image-only PDFs that return very little embedded text,
    automatically falls back to Tesseract OCR (french + english) so that
    real content is still captured.
    """
    segments: List[ExtractedSegment] = []
    ocr_pages = 0
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_text = page.get_text("text").strip()

            # OCR fallback: if native text extraction yields almost nothing
            if len(page_text) < _OCR_MIN_CHARS:
                logger.info(
                    "Page %d of %s has only %d chars — attempting OCR",
                    page_idx + 1, filename, len(page_text),
                )
                ocr_text = _ocr_page(page)
                if len(ocr_text) > len(page_text):
                    page_text = ocr_text
                    ocr_pages += 1

            if page_text:
                segments.append(
                    ExtractedSegment(
                        content=page_text,
                        source_name=filename,
                        source_location=f"Page {page_idx + 1}",
                    )
                )

        logger.info(
            "Parsed %d pages from PDF %s (%d via OCR)", len(segments), filename, ocr_pages
        )
    except Exception as e:
        logger.error("Failed to parse PDF %s: %s", filename, e, exc_info=True)
    return segments


def parse_youtube(url: str) -> List[ExtractedSegment]:
    """Extracts YouTube transcript segments and groups them into ~300-word blocks with timestamps."""
    segments: List[ExtractedSegment] = []
    match = YOUTUBE_REGEX.search(url)
    if not match:
        logger.warning("Could not extract valid video_id from YouTube URL: %s", url)
        return segments

    video_id = match.group(1)
    logger.info("Fetching YouTube transcript for video_id: %s", video_id)
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "fr", "es"])
        current_words: List[str] = []
        start_time = 0.0

        for entry in transcript_list:
            text = entry.get("text", "").strip()
            if not text:
                continue
            if not current_words:
                start_time = float(entry.get("start", 0.0))

            words = text.split()
            current_words.extend(words)

            if len(current_words) >= 300:
                mins = int(start_time // 60)
                secs = int(start_time % 60)
                segments.append(
                    ExtractedSegment(
                        content=" ".join(current_words),
                        source_name=f"YouTube ({video_id})",
                        source_location=f"{mins:02d}:{secs:02d}",
                    )
                )
                current_words = []

        if current_words:
            mins = int(start_time // 60)
            secs = int(start_time % 60)
            segments.append(
                ExtractedSegment(
                    content=" ".join(current_words),
                    source_name=f"YouTube ({video_id})",
                    source_location=f"{mins:02d}:{secs:02d}",
                )
            )
        logger.info("Extracted %d transcript blocks from YouTube video %s", len(segments), video_id)
    except Exception as e:
        logger.warning("YouTube transcript extraction failed for %s: %s", url, e)
    return segments


def parse_web_article(url: str) -> List[ExtractedSegment]:
    """Extracts clean article body from web URL via trafilatura."""
    segments: List[ExtractedSegment] = []
    # If it is a YouTube URL, route directly to YouTube parser
    if YOUTUBE_REGEX.search(url):
        return parse_youtube(url)

    logger.info("Fetching web article from: %s", url)
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                favor_recall=True,
            )
            if extracted and extracted.strip():
                domain = urllib.parse.urlparse(url).netloc or url
                segments.append(
                    ExtractedSegment(
                        content=extracted.strip(),
                        source_name=domain,
                        source_location="Web Excerpt",
                    )
                )
                logger.info("Extracted %d characters from %s", len(extracted), url)
            else:
                logger.warning("Trafilatura extracted empty content from %s", url)
        else:
            logger.warning("Trafilatura failed to download URL: %s", url)
    except Exception as e:
        logger.error("Web extraction error for %s: %s", url, e)
    return segments


def split_into_overlapping_chunks(
    segments: List[ExtractedSegment], target_words: int = 350, overlap_words: int = 50
) -> List[ExtractedSegment]:
    """Splits long extracted segments into overlapping ~350-word chunks preserving citation metadata."""
    chunked: List[ExtractedSegment] = []
    step = max(50, target_words - overlap_words)

    for seg in segments:
        words = seg.content.split()
        if len(words) <= target_words + 30:
            chunked.append(seg)
        else:
            for start_idx in range(0, len(words), step):
                chunk_words = words[start_idx : start_idx + target_words]
                if not chunk_words:
                    break
                chunked.append(
                    ExtractedSegment(
                        content=" ".join(chunk_words),
                        source_name=seg.source_name,
                        source_location=seg.source_location,
                    )
                )
                if start_idx + target_words >= len(words):
                    break
    return chunked


def ingest_and_embed_resources(
    session_id: str,
    student_id: str,
    files: Optional[List[tuple[str, bytes]]] = None,
    urls: Optional[List[str]] = None,
) -> List[ResourceChunk]:
    """Orchestrates parsing, chunking, 384-d embedding, and PostgreSQL persistence of study resources."""
    raw_segments: List[ExtractedSegment] = []

    # 1. Parse uploaded files
    if files:
        for filename, file_bytes in files:
            if filename.lower().endswith(".pdf"):
                raw_segments.extend(parse_pdf(file_bytes, filename))
            elif filename.lower().endswith((".txt", ".md", ".py")):
                try:
                    text = file_bytes.decode("utf-8", errors="replace").strip()
                    if text:
                        raw_segments.append(
                            ExtractedSegment(
                                content=text,
                                source_name=filename,
                                source_location="Document Text",
                            )
                        )
                except Exception as e:
                    logger.warning("Failed to decode text file %s: %s", filename, e)

    # 2. Parse URLs
    if urls:
        for url in urls:
            url_clean = url.strip()
            if not url_clean:
                continue
            if YOUTUBE_REGEX.search(url_clean):
                raw_segments.extend(parse_youtube(url_clean))
            else:
                raw_segments.extend(parse_web_article(url_clean))

    if not raw_segments:
        logger.info("No multimodal resources provided for session %s; proceeding with canonical curriculum.", session_id)
        return []

    # 3. Overlapping chunking
    chunks = split_into_overlapping_chunks(raw_segments, target_words=350, overlap_words=50)
    logger.info("Generated %d chunks from %d raw segments for session %s", len(chunks), len(raw_segments), session_id)

    # 4. Generate 384-d vector embeddings in batches via LocalMLService
    ml_service = LocalMLService.get_instance()
    texts = [c.content for c in chunks]
    embeddings = ml_service.embed_text(texts)

    # 5. Persist to PostgreSQL resource_chunks table
    persisted_chunks: List[ResourceChunk] = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for idx, (c, emb) in enumerate(zip(chunks, embeddings)):
                    chunk_id = str(uuid.uuid4())
                    cur.execute(
                        """
                        INSERT INTO resource_chunks 
                            (chunk_id, session_id, student_id, content, source_name, source_location, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            chunk_id,
                            session_id,
                            student_id,
                            c.content,
                            c.source_name,
                            c.source_location,
                            emb,
                        ),
                    )
                    persisted_chunks.append(
                        ResourceChunk(
                            chunk_id=chunk_id,
                            session_id=session_id,
                            student_id=student_id,
                            content=c.content,
                            source_name=c.source_name,
                            source_location=c.source_location,
                        )
                    )
        logger.info("Persisted %d resource_chunks into PostgreSQL for session %s", len(persisted_chunks), session_id)
    except Exception as e:
        logger.error("Failed to persist resource_chunks: %s", e, exc_info=True)

    return persisted_chunks
