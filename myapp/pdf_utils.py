"""
pdf_utils.py — Lossless PDF compression before Dropbox upload.

Strategy (in order of preference):
  1. pikepdf  — strips dead objects, compresses streams, normalises xref tables.
               Typically achieves 20-60 % reduction on scan-heavy PDFs.
  2. pypdf    — pure-Python fallback; recompresses content streams with zlib.
               Lighter savings (~5-20 %) but zero system dependencies.
  3. passthrough — if both fail, returns the original bytes unchanged so the
               upload always continues.

All compression is *lossless*: text, vector graphics, and already-compressed
images are never degraded.
"""

import io
import logging

logger = logging.getLogger(__name__)


def _compress_with_pikepdf(data: bytes) -> bytes:
    """Use pikepdf (libqpdf) to linearise and recompress the PDF."""
    import pikepdf

    with pikepdf.open(io.BytesIO(data)) as pdf:
        out = io.BytesIO()
        pdf.save(
            out,
            compress_streams=True,       # deflate all uncompressed streams
            stream_decode_level=pikepdf.StreamDecodeLevel.generalized,
            recompress_flate=True,       # re-deflate already-flate streams
            object_stream_mode=pikepdf.ObjectStreamMode.generate,  # pack small objects
            linearize=False,             # linearisation adds size; skip it
        )
        return out.getvalue()


def _compress_with_pypdf(data: bytes) -> bytes:
    """Use pypdf to rewrite the PDF with compressed streams."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    # Compress every content stream
    for page in writer.pages:
        page.compress_content_streams()

    # Copy document metadata so nothing is stripped for users
    if reader.metadata:
        writer.add_metadata(reader.metadata)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def compress_pdf(file_obj) -> tuple[bytes, int, int, str]:
    """
    Read *file_obj* (a Django UploadedFile or any file-like with .read()),
    compress it, and return:

        (compressed_bytes, original_size_bytes, compressed_size_bytes, method_used)

    *method_used* is one of 'pikepdf', 'pypdf', or 'passthrough'.
    The function never raises — failures fall through to the next strategy.
    """
    file_obj.seek(0)
    original_data = file_obj.read()
    original_size = len(original_data)

    # ── 1. Try pikepdf ─────────────────────────────────────────────────────────
    try:
        compressed = _compress_with_pikepdf(original_data)
        # Only accept if the result is actually smaller (pathological PDFs can
        # grow slightly after recompression e.g. already-optimal files).
        if len(compressed) < original_size:
            return compressed, original_size, len(compressed), 'pikepdf'
        # pikepdf succeeded but didn't shrink the file — fall through to pypdf
    except ImportError:
        logger.info('pdf_utils: pikepdf not available, trying pypdf')
    except Exception as exc:
        logger.warning('pdf_utils: pikepdf failed (%s), trying pypdf', exc)

    # ── 2. Try pypdf ───────────────────────────────────────────────────────────
    try:
        compressed = _compress_with_pypdf(original_data)
        if len(compressed) < original_size:
            return compressed, original_size, len(compressed), 'pypdf'
    except ImportError:
        logger.info('pdf_utils: pypdf not available, using passthrough')
    except Exception as exc:
        logger.warning('pdf_utils: pypdf failed (%s), using passthrough', exc)

    # ── 3. Passthrough — return original unchanged ─────────────────────────────
    return original_data, original_size, original_size, 'passthrough'


def human_size(n_bytes: int) -> str:
    """Return a human-readable file size string, e.g. '45.2 MB'."""
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n_bytes < 1024:
            return f'{n_bytes:.1f} {unit}'
        n_bytes /= 1024
    return f'{n_bytes:.1f} TB'
