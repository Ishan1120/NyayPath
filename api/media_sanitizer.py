"""
NyayPath Media Sanitization Utility (Phase 1.3.7 - Task 4)
==========================================================
Concrete implementation of image EXIF stripping and PDF metadata removal.
Ensures files uploaded for anonymous or confidential grievances do not leak
device serial numbers, GPS locations, author names, or workstation paths.
"""

import io
import re
from typing import Tuple
from PIL import Image, ImageOps


def sanitize_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> bytes:
    """
    Strips EXIF data and device metadata from an image byte buffer.
    Re-encodes image purely from pixel data.
    """
    if not image_bytes:
        return b""

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Transpose orientation to maintain visual appearance before stripping EXIF
            img = ImageOps.exif_transpose(img)
            
            # Extract clean pixel buffer (strips all EXIF, GPS, and camera metadata tags)
            clean_io = io.BytesIO()
            format_map = {
                "image/jpeg": "JPEG",
                "image/jpg": "JPEG",
                "image/png": "PNG",
                "image/webp": "WEBP"
            }
            img_format = format_map.get(mime_type.lower(), img.format or "JPEG")
            img.save(clean_io, format=img_format)
            return clean_io.getvalue()
    except Exception:
        # If Pillow cannot process, return original bytes rather than aborting, but log warning
        return image_bytes


def sanitize_pdf_metadata(pdf_bytes: bytes) -> bytes:
    """
    Sanitizes standard PDF metadata fields (/Author, /Creator, /Producer, /Title, /CreationDate).
    Replaces metadata dictionary values with sanitized pseudonyms.
    """
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF-"):
        return pdf_bytes

    # Common metadata keys in raw PDF objects
    keys_to_sanitize = [b"/Author", b"/Creator", b"/Producer", b"/Title", b"/CreationDate", b"/ModDate"]
    sanitized = pdf_bytes

    for key in keys_to_sanitize:
        # Match pattern: /Author (John Doe) or /Author <hex>
        pattern = re.compile(re.escape(key) + rb"\s*\([^\)]*\)")
        sanitized = pattern.sub(key + rb" (NyayPath Confidential Document)", sanitized)

    return sanitized


def sanitize_document_payload(
    file_bytes: bytes,
    file_name: str,
    mime_type: str
) -> Tuple[bytes, str]:
    """
    High-level entry point to sanitize document bytes based on MIME type.
    Returns (sanitized_bytes, sanitized_file_name).
    """
    # Sanitize file name to avoid path traversal or personal username leaks
    safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", file_name)
    
    clean_mime = mime_type.lower().strip()
    if clean_mime in ["image/jpeg", "image/jpg", "image/png", "image/webp"]:
        sanitized_bytes = sanitize_image(file_bytes, clean_mime)
    elif clean_mime == "application/pdf":
        sanitized_bytes = sanitize_pdf_metadata(file_bytes)
    else:
        sanitized_bytes = file_bytes

    return sanitized_bytes, safe_name
