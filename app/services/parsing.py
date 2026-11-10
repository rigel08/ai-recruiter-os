"""Turn uploaded resume files into plain text."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import PurePath
from xml.etree import ElementTree

from pypdf import PdfReader

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")

# Caps the size of the DOCX's text part once unzipped, so a small
# malicious file can't expand into gigabytes of memory.
_MAX_DOCX_XML_BYTES = 20 * 1024 * 1024
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Two-column detection (see split_columns). Long documents aren't resumes, so they skip the check.
_MAX_PAGES_FOR_COLUMN_CHECK = 6
_COLUMN_GAP = re.compile(r" {4,}")
_MIN_COLUMN_LINES = 6
_MIN_COLUMN_SHARE = 0.5
_MIN_RIGHT_WORDS = 3


class UnreadableDocument(Exception):
    """The file can't be turned into text. The message says why, for a recruiter."""


def extract_text(file_name: str, data: bytes) -> str:
    extension = PurePath(file_name).suffix.lower()
    if extension == ".pdf":
        return _pdf_text(data)
    if extension == ".docx":
        return _docx_text(data)
    if extension == ".txt":
        return data.decode("utf-8", errors="replace")
    if extension == ".doc":
        raise UnreadableDocument(".doc isn't supported. Upload PDF, DOCX or TXT. To convert it, open it in Word and use Save As.")
    if extension in (".jpg", ".jpeg", ".png", ".heic"):
        raise UnreadableDocument(f"{extension} isn't supported. Upload PDF, DOCX or TXT. A photo or scan of a resume can't be read.")
    shown = extension or "files without an extension"
    raise UnreadableDocument(f"{shown} isn't supported. Upload PDF, DOCX or TXT.")


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # Many "protected" PDFs only restrict printing and open with an
            # empty password. Anything else really is locked.
            reader.decrypt("")
        pages = [page.extract_text() or "" for page in reader.pages]
        if len(reader.pages) <= _MAX_PAGES_FOR_COLUMN_CHECK:
            pages = [_by_column(page) or plain for page, plain in zip(reader.pages, pages)]
    except Exception as exc:  # pypdf raises many different types on damaged files
        raise UnreadableDocument("The PDF couldn't be opened. It may be damaged or password-protected.") from exc
    return "\n".join(pages)


def _by_column(page) -> str | None:
    """The page's text read down the left column and then the right, or None if it isn't two columns.

    Some resume builders save two-column pages row by row. Read naively, that gives lines such as
    "Notice Period Expected CTC: 24 LPA", with one column's label glued to the other's value.
    """
    try:
        layout = page.extract_text(extraction_mode="layout") or ""
    except Exception:  # layout mode is newer and stricter; the plain text is always the fallback
        return None
    return split_columns(layout)


def split_columns(layout: str) -> str | None:
    """Split text that keeps its page spacing into left-then-right order, if it is clearly two columns.

    A line belongs to both columns when it has one wide gap with text on each side. To avoid
    pulling apart ordinary rows such as "Notice Period      30 Days" or a date set to the right,
    most lines must have the gap and the right-hand pieces must read like prose, not single values.
    """
    lines = [line.rstrip() for line in layout.splitlines() if line.strip()]
    left: list[str] = []
    right: list[str] = []
    for line in lines:
        gaps = list(_COLUMN_GAP.finditer(line.lstrip()))
        if not gaps:
            left.append(line.strip())
            continue
        gap = max(gaps, key=lambda match: len(match.group(0)))
        text = line.lstrip()
        left.append(text[: gap.start()].strip())
        right.append(text[gap.end():].strip())
    if len(right) < _MIN_COLUMN_LINES or len(right) < len(lines) * _MIN_COLUMN_SHARE:
        return None
    words = sorted(len(piece.split()) for piece in right)
    if words[len(words) // 2] < _MIN_RIGHT_WORDS:
        return None
    return "\n".join(left + right)


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > _MAX_DOCX_XML_BYTES:
                raise UnreadableDocument("The DOCX file is too large to read.")
            root = ElementTree.fromstring(archive.read(info))
    except UnreadableDocument:
        raise
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise UnreadableDocument("The DOCX file couldn't be opened. It may be damaged.") from exc
    paragraphs = (
        "".join(node.text or "" for node in paragraph.iter(f"{_WORD_NS}t"))
        for paragraph in root.iter(f"{_WORD_NS}p")
    )
    return "\n".join(paragraphs)
